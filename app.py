import os
import re
import secrets
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path

import click
from flask import (
    Flask, flash, redirect, render_template, request, session, url_for
)

from flask_login import (
    LoginManager, UserMixin, current_user, login_user, logout_user
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import validates
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFError, CSRFProtect
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)

def carregar_chave_secreta(pasta):
    """Devolve a SECRET_KEY, a chave que assina o cookie de login
    e os códigos CSRF. Quem souber a chave consegue FORJAR um login,
    então ela não pode estar no código (nem no GitHub).

    1. Variável de ambiente SECRET_KEY, se existir (uso em servidor).
    2. Senão, o arquivo <pasta>/secret_key; na primeira vez ele é
       criado com uma chave aleatória. A pasta instance/ está no
       .gitignore, então a chave nunca vai para o Git.
    """
    chave = os.environ.get("SECRET_KEY")
    if chave:
        return chave

    arquivo = Path(pasta) / "secret_key"

    if not arquivo.exists():
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        # secrets (e não random): feito para gerar valores imprevisíveis
        arquivo.write_text(secrets.token_hex(32), encoding="utf-8")

    return arquivo.read_text(encoding="utf-8").strip()


app.config["SECRET_KEY"] = carregar_chave_secreta(app.instance_path)

# O navegador só manda o cookie de login quando a navegação começa no
# próprio Atrial (ou num link clicado). Formulários enviados por outros
# sites vão sem cookie: mais uma barreira contra CSRF, além do csrf_token.
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# Configuração do banco de dados
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///atrial.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# Migrations: cuidam das mudanças na estrutura do banco
# (ex.: adicionar uma coluna) sem perder os dados.
migrate = Migrate(app, db)

# Proteção contra CSRF: todo formulário POST precisa mandar um código
# secreto (csrf_token) que só as páginas do próprio Atrial conhecem.
# Assim, um site malicioso aberto em outra aba não consegue enviar
# formulários (excluir paciente, chamar próximo...) em seu nome.
#
# TIME_LIMIT = None: o código vale enquanto a pessoa estiver logada.
# O padrão (1 hora) daria erro em quem deixa a página aberta o dia
# todo na recepção e clica em "Chamar próximo" à tarde.
app.config["WTF_CSRF_TIME_LIMIT"] = None
csrf = CSRFProtect(app)


def normalizar(texto):
    """Deixa o texto pronto para comparar: sem acentos e em minúsculas.

    'João da CONCEIÇÃO' -> 'joao da conceicao'

    NFKD separa a letra do acento ('ã' vira 'a' + '~'); depois
    jogamos fora os acentos soltos (combining) e o casefold()
    faz o papel do lower(), cobrindo mais idiomas.
    """
    separado = unicodedata.normalize("NFKD", texto or "")
    sem_acento = "".join(c for c in separado if not unicodedata.combining(c))
    return sem_acento.casefold()


# Modelo do paciente
class Paciente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    nascimento = db.Column(db.String(20), nullable=False)
    cpf = db.Column(db.String(14), nullable=False)
    telefone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    observacoes = db.Column(db.Text)

    prioridade = db.Column(
        db.String(20),
        nullable=False,
        default="Normal"
    )

    # Status do atendimento
    status = db.Column(
        db.String(20),
        nullable=False,
        default="Aguardando"
    )

    # Horários do atendimento (vazios em pacientes antigos)
    chegada = db.Column(db.DateTime)       # entrou na fila
    chamado_em = db.Column(db.DateTime)    # foi chamado para atendimento
    concluido_em = db.Column(db.DateTime)  # atendimento terminou

    # Para onde o paciente foi chamado (um dos LOCAIS).
    # Vazio em quem foi chamado antes de existir esta coluna.
    local = db.Column(db.String(50))

    # Nome sem acentos e em minúsculas, só para a busca:
    # "João da Conceição" -> "joao da conceicao". Nunca é mostrado na tela.
    nome_busca = db.Column(db.String(100))

    @validates("nome")
    def _preencher_nome_busca(self, chave, nome):
        # Roda sozinho sempre que alguém faz paciente.nome = ...
        # (no cadastro, na edição...), então as duas colunas nunca
        # ficam diferentes uma da outra.
        self.nome_busca = normalizar(nome)
        return nome


# Quem trabalha na recepção (quem pode entrar no sistema)
# UserMixin dá ao modelo o que o Flask-Login espera de um usuário
# (is_authenticated, get_id()...), sem precisarmos escrever.
class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    login = db.Column(db.String(50), nullable=False, unique=True)

    # NUNCA guardamos a senha em si, só um "hash": uma impressão
    # digital dela que não dá para desfazer. Para conferir, calculamos
    # o hash do que foi digitado e comparamos.
    senha_hash = db.Column(db.String(255), nullable=False)

    def definir_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def confere_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)


PRIORIDADES = ["Normal", "Preferencial", "Urgente"]

# Para onde os pacientes podem ser chamados. Para mudar os locais
# da clínica, basta editar esta lista (e reiniciar o servidor).
LOCAIS = ["Triagem", "Consultório 1", "Consultório 2", "Consultório 3"]
app.jinja_env.globals["LOCAIS"] = LOCAIS

# Deixa a lista disponível em todos os templates
app.jinja_env.globals["PRIORIDADES"] = PRIORIDADES


# ---------- Validação ----------

def somente_digitos(texto):
    """Remove tudo que não é número: '123.456.789-09' -> '12345678909'."""
    return re.sub(r"\D", "", texto)


def cpf_valido(cpf):
    """Confere o tamanho e os dois dígitos verificadores do CPF."""

    # 11 dígitos, e não pode ser tudo igual (111.111.111-11 passa na conta!)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False

    # 1º verificador: 9 primeiros dígitos com pesos 10, 9, ..., 2
    # 2º verificador: 10 primeiros dígitos com pesos 11, 10, ..., 2
    for posicao in (9, 10):
        soma = sum(
            int(cpf[i]) * (posicao + 1 - i)
            for i in range(posicao)
        )
        digito = soma * 10 % 11 % 10

        if digito != int(cpf[posicao]):
            return False

    return True


@app.template_filter("cpf")
def formatar_cpf(cpf):
    """Filtro do Jinja: {{ paciente.cpf|cpf }} -> 123.456.789-09"""
    if len(cpf) != 11:
        return cpf
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"


@app.template_filter("hora")
def formatar_hora(momento):
    """{{ paciente.chegada|hora }} -> 14:32"""
    if momento is None:
        return "-"
    return momento.strftime("%H:%M")


@app.template_filter("duracao")
def formatar_duracao(inicio, fim=None):
    """Tempo entre dois horários, em texto.

    {{ paciente.chegada|duracao }}                     -> de chegada até agora
    {{ paciente.chegada|duracao(paciente.chamado_em) }} -> entre os dois
    """
    if inicio is None:
        return "-"

    fim = fim or datetime.now()
    return formatar_minutos((fim - inicio).total_seconds() / 60)


@app.template_filter("minutos")
def formatar_minutos(minutos):
    """{{ 135|minutos }} -> 2h 15min   (None -> '-')"""
    if minutos is None:
        return "-"

    minutos = int(minutos)

    if minutos < 1:
        return "menos de 1 min"
    if minutos < 60:
        return f"{minutos} min"

    horas, minutos = divmod(minutos, 60)
    return f"{horas}h {minutos:02d}min"


def ler_formulario(paciente_id=None):
    """Lê, limpa e valida os campos do formulário de paciente.

    Devolve (dados, erros). Lista de erros vazia = tudo certo.
    Na edição, passe paciente_id para o próprio paciente
    não ser acusado de CPF duplicado.
    """

    dados = {
        "nome": request.form.get("nome", "").strip(),
        "nascimento": request.form.get("nascimento", "").strip(),
        "cpf": somente_digitos(request.form.get("cpf", "")),
        "prioridade": request.form.get("prioridade", ""),
        "telefone": request.form.get("telefone", "").strip(),
        "email": request.form.get("email", "").strip(),
        "observacoes": request.form.get("observacoes", "").strip(),
    }

    erros = []

    if not dados["nome"]:
        erros.append("Informe o nome do paciente.")

    try:
        if date.fromisoformat(dados["nascimento"]) > date.today():
            erros.append("A data de nascimento não pode estar no futuro.")
    except ValueError:
        erros.append("Informe uma data de nascimento válida.")

    if not cpf_valido(dados["cpf"]):
        erros.append("CPF inválido. Confira os números digitados.")
    else:
        mesmo_cpf = Paciente.query.filter_by(cpf=dados["cpf"])

        if paciente_id is not None:
            mesmo_cpf = mesmo_cpf.filter(Paciente.id != paciente_id)

        if mesmo_cpf.first():
            erros.append("Já existe um paciente cadastrado com este CPF.")

    if dados["prioridade"] not in PRIORIDADES:
        erros.append("Escolha uma prioridade válida.")

    return dados, erros


def mostrar_erros(erros):
    for erro in erros:
        flash(erro, "erro")


# ---------- Login ----------

login_manager = LoginManager(app)


@login_manager.user_loader
def carregar_usuario(usuario_id):
    """A sessão (o cookie) guarda só o id do usuário. A cada página,
    o Flask-Login chama esta função para buscar o usuário completo."""
    return db.session.get(Usuario, int(usuario_id))


# Páginas que qualquer um pode ver, sem login.
# O painel fica na TV da recepção, então não pode pedir senha.
PAGINAS_PUBLICAS = {"login", "static", "painel", "painel_dados"}


@app.before_request
def exigir_login():
    """Roda ANTES de toda rota. Quem não entrou vai para o login.

    Proteger tudo por padrão é mais seguro do que marcar rota por rota:
    uma rota nova já nasce protegida, mesmo que alguém esqueça.
    """
    if request.endpoint in PAGINAS_PUBLICAS or current_user.is_authenticated:
        return None  # pode seguir para a rota

    # Guarda para onde a pessoa queria ir, para mandá-la de volta depois.
    # (full_path inclui o ?q=..., mas deixa um "?" sobrando quando não há)
    proxima = request.full_path if request.query_string else request.path
    return redirect(url_for("login", proxima=proxima))


def endereco_seguro(endereco):
    """Só aceita endereços DESTE site ('/pacientes'), nunca de outro.

    Sem isso, alguém poderia mandar um link como
    /login?proxima=https://site-falso.com, e depois de digitar a senha
    a pessoa cairia num site falso achando que ainda está no Atrial.
    """
    return (
        bool(endereco)
        and endereco.startswith("/")
        and not endereco.startswith("//")   # //site.com também é outro site
        and "\\" not in endereco             # alguns navegadores leem \ como /
    )


@app.route("/login", methods=["GET", "POST"])
def login():

    if current_user.is_authenticated:
        return redirect(url_for("pacientes"))

    proxima = request.args.get("proxima", "")

    if request.method == "POST":
        login_digitado = request.form.get("login", "").strip().lower()
        senha = request.form.get("senha", "")

        usuario = Usuario.query.filter_by(login=login_digitado).first()

        if usuario and usuario.confere_senha(senha):
            login_user(usuario)
            flash(f"Olá, {usuario.nome}!", "sucesso")
            return redirect(proxima if endereco_seguro(proxima) else url_for("pacientes"))

        # Mesma mensagem para usuário inexistente e senha errada:
        # assim ninguém descobre quais logins existem testando.
        flash("Usuário ou senha incorretos.", "erro")
        return render_template("login.html", login=login_digitado, proxima=proxima)

    return render_template("login.html", login="", proxima=proxima)


# POST (e não um link comum) para que outro site não consiga
# deslogar alguém só colocando uma imagem apontando para /logout
@app.route("/logout", methods=["POST"])
def logout():
    logout_user()
    flash("Você saiu do sistema.", "sucesso")
    return redirect(url_for("login"))


@app.cli.command("criar-usuario")
@click.argument("login")
@click.option("--nome", prompt="Nome de quem vai usar")
@click.password_option("--senha", prompt="Senha")
def criar_usuario(login, nome, senha):
    """Cria um usuário da recepção. Uso:

        flask --app app criar-usuario maria

    (Não existe página de "criar conta": só quem tem acesso
    ao servidor pode cadastrar quem entra no sistema.)
    """
    login = login.strip().lower()

    if Usuario.query.filter_by(login=login).first():
        raise click.ClickException(f"Já existe o usuário '{login}'.")

    if len(senha) < 8:
        raise click.ClickException("A senha precisa ter pelo menos 8 caracteres.")

    usuario = Usuario(nome=nome.strip(), login=login)
    usuario.definir_senha(senha)
    db.session.add(usuario)
    db.session.commit()

    click.echo(f"Usuário '{login}' criado.")


@app.errorhandler(CSRFError)
def erro_csrf(erro):
    """Formulário chegou sem o código ou com um código inválido.

    Na prática quase sempre é inofensivo (ex.: a pessoa saiu e entrou
    de novo em outra aba, e a página antiga ficou com o código velho).
    Em vez da página de erro 400 do Flask, explicamos e recomeçamos.
    """
    flash("A página estava desatualizada. Confira e tente de novo.", "erro")
    return redirect(url_for("pacientes"))


# ---------- Rotas ----------

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/pacientes/novo", methods=["GET", "POST"])
def cadastro_paciente():

    if request.method == "POST":

        dados, erros = ler_formulario()

        if erros:
            mostrar_erros(erros)
            # Mostra o formulário de novo, com o que já foi digitado
            return render_template("cadastros.html", dados=dados)

        paciente = Paciente(
            **dados,
            status="Aguardando",
            chegada=datetime.now()
        )

        db.session.add(paciente)
        db.session.commit()

        flash(f"Paciente {paciente.nome} cadastrado com sucesso!", "sucesso")

        return redirect(url_for("pacientes"))

    return render_template("cadastros.html", dados={})


def buscar_por_status(status):
    """Pacientes com o status informado, na ordem da fila:
    Urgente > Preferencial > Normal e, no empate, quem chegou primeiro."""

    return Paciente.query.filter_by(
        status=status
    ).order_by(
        db.case(
            (Paciente.prioridade == "Urgente", 1),
            (Paciente.prioridade == "Preferencial", 2),
            else_=3
        ),
        Paciente.id
    )


def filtrar_busca(consulta, termo):
    """Mantém só os pacientes cujo nome ou CPF contém o termo.

    'ana' acha 'Ana' e 'Mariana'; '529.982' acha o CPF 52998224725.
    Termo vazio = não filtra nada.
    """
    if not termo:
        return consulta

    # Compara versões normalizadas dos dois lados: 'joao' acha 'João'
    # e 'José' acha 'Jose'. (O SQLite sozinho só ignora maiúsculas
    # em letras sem acento: para ele, 'ã' e 'Ã' são diferentes.)
    # autoescape: um '%' ou '_' digitado é tratado como texto comum
    condicoes = [
        Paciente.nome_busca.contains(normalizar(termo), autoescape=True)
    ]

    digitos = somente_digitos(termo)
    if digitos:
        condicoes.append(Paciente.cpf.contains(digitos))

    return consulta.filter(db.or_(*condicoes))


@app.route("/pacientes")
def pacientes():

    # ?q=... na URL (vem do campo de busca)
    termo = request.args.get("q", "").strip()

    em_atendimento = filtrar_busca(
        buscar_por_status("Em atendimento"), termo
    ).all()

    # A posição na fila vem da fila COMPLETA: se a busca esconder
    # alguém, quem sobrou não pode "subir" de posição.
    posicoes = {
        paciente.id: numero
        for numero, paciente in enumerate(buscar_por_status("Aguardando"), start=1)
    }

    fila = filtrar_busca(buscar_por_status("Aguardando"), termo).all()

    # Histórico: os concluídos mais recentes primeiro
    concluidos = filtrar_busca(
        Paciente.query.filter_by(status="Concluído"), termo
    ).order_by(
        Paciente.id.desc()
    ).all()

    # ?parcial=1: o JavaScript da página só quer as listas atualizadas,
    # sem cabeçalho, menu etc. (veja _listas_pacientes.html)
    if request.args.get("parcial"):
        template = "_listas_pacientes.html"
    else:
        template = "pacientes.html"

    return render_template(
        template,
        termo=termo,
        em_atendimento=em_atendimento,
        fila=fila,
        posicoes=posicoes,
        concluidos=concluidos
    )


# ---------- Relatório do dia ----------

def minutos_entre(inicio, fim):
    """Minutos entre dois horários; None se faltar algum deles."""
    if inicio is None or fim is None:
        return None
    return (fim - inicio).total_seconds() / 60


def media(valores):
    valores = [v for v in valores if v is not None]
    return sum(valores) / len(valores) if valores else None


def no_dia(momento, dia):
    return momento is not None and momento.date() == dia


def relatorio_do_dia(dia):
    """Números de um dia de atendimento. Devolve um dicionário.

    Cada número usa o horário que faz sentido para ele:
    - chegaram: quem CHEGOU no dia
    - espera: quem foi CHAMADO no dia (chegada -> chamada)
    - atendidos/duração: quem foi CONCLUÍDO no dia (chamada -> conclusão)
    """
    inicio = datetime.combine(dia, datetime.min.time())
    fim = inicio + timedelta(days=1)

    def entre(coluna):
        return coluna >= inicio, coluna < fim

    # Todo mundo que teve ALGUM momento no dia. As contas são feitas
    # em Python (e não em SQL) por serem mais fáceis de ler; para o
    # movimento de um dia, são poucas linhas.
    pacientes = Paciente.query.filter(db.or_(
        db.and_(*entre(Paciente.chegada)),
        db.and_(*entre(Paciente.chamado_em)),
        db.and_(*entre(Paciente.concluido_em)),
    )).all()

    chegaram = [p for p in pacientes if no_dia(p.chegada, dia)]
    chamados = [p for p in pacientes if no_dia(p.chamado_em, dia)]
    concluidos = [p for p in pacientes if no_dia(p.concluido_em, dia)]

    esperas = [minutos_entre(p.chegada, p.chamado_em) for p in chamados]
    esperas = [e for e in esperas if e is not None]

    por_prioridade = []
    for prioridade in PRIORIDADES:
        do_grupo = [p for p in chamados if p.prioridade == prioridade]
        por_prioridade.append({
            "prioridade": prioridade,
            "chegaram": sum(1 for p in chegaram if p.prioridade == prioridade),
            "chamados": len(do_grupo),
            "espera_media": media(
                minutos_entre(p.chegada, p.chamado_em) for p in do_grupo
            ),
        })

    # Chegadas por hora: {8: 3, 9: 5, ...}
    por_hora = {}
    for p in chegaram:
        por_hora[p.chegada.hour] = por_hora.get(p.chegada.hour, 0) + 1

    return {
        "dia": dia,
        "chegaram": len(chegaram),
        "atendidos": len(concluidos),
        "espera_media": media(esperas),
        "maior_espera": max(esperas) if esperas else None,
        "duracao_media": media(
            minutos_entre(p.chamado_em, p.concluido_em) for p in concluidos
        ),
        "por_prioridade": por_prioridade,
        "por_hora": por_hora,
        # Quantos atendimentos cada local concluiu no dia
        "por_local": [
            {
                "local": local,
                "atendidos": sum(1 for p in concluidos if p.local == local),
                "duracao_media": media(
                    minutos_entre(p.chamado_em, p.concluido_em)
                    for p in concluidos if p.local == local
                ),
            }
            for local in LOCAIS
        ],
    }


def grafico_por_hora(por_hora):
    """Calcula o desenho (em SVG) do gráfico de chegadas por hora.

    Devolve as medidas prontas; o template só desenha. Fazer a
    conta aqui deixa o template simples e permite testar.
    """
    if not por_hora:
        return None

    # Pelo menos o horário comercial, e mais se houve movimento fora dele
    horas = list(range(min(7, *por_hora), max(18, *por_hora) + 1))

    largura, altura = 720, 240
    esquerda, direita, topo, base = 36, 8, 12, 28
    area_l = largura - esquerda - direita
    area_a = altura - topo - base

    # Topo do eixo: um número "redondo" com no máximo ~5 marcas
    maior = max(por_hora.values())
    passo = next(p for p in (1, 2, 5, 10, 20, 50, 100) if maior / p <= 5)
    topo_eixo = -(-maior // passo) * passo  # arredonda para cima

    def y(valor):
        return topo + area_a - valor / topo_eixo * area_a

    coluna = area_l / len(horas)
    barra_l = min(coluna * 0.6, 32)  # barras finas

    barras = []
    for i, hora in enumerate(horas):
        total = por_hora.get(hora, 0)
        x = esquerda + i * coluna + (coluna - barra_l) / 2
        barras.append({
            "hora": hora,
            "total": total,
            "x": round(x, 1),
            "largura": round(barra_l, 1),
            "caminho": caminho_barra(x, y(total), barra_l, y(0)) if total else None,
            # Área de passar o mouse: a coluna inteira, maior que a barra
            "alvo_x": round(esquerda + i * coluna, 1),
            "alvo_largura": round(coluna, 1),
            "centro": round(esquerda + i * coluna + coluna / 2, 1),
        })

    return {
        "largura": largura,
        "altura": altura,
        "esquerda": esquerda,
        "direita": largura - direita,
        "topo": topo,
        "chao": y(0),
        "marcas": [
            {"valor": v, "y": round(y(v), 1)}
            for v in range(0, topo_eixo + 1, passo)
        ],
        "barras": barras,
    }


def caminho_barra(x, y_topo, largura, y_chao):
    """Contorno de uma barra com só os cantos de CIMA arredondados
    (a base fica reta, "apoiada" no eixo)."""
    r = min(4, largura / 2, y_chao - y_topo)
    return (
        f"M{x:.1f},{y_chao:.1f} "
        f"V{y_topo + r:.1f} "
        f"Q{x:.1f},{y_topo:.1f} {x + r:.1f},{y_topo:.1f} "
        f"H{x + largura - r:.1f} "
        f"Q{x + largura:.1f},{y_topo:.1f} {x + largura:.1f},{y_topo + r:.1f} "
        f"V{y_chao:.1f} Z"
    )


@app.route("/relatorio")
def relatorio():
    # ?dia=2026-11-18 escolhe o dia; sem nada, é hoje
    try:
        dia = date.fromisoformat(request.args.get("dia", ""))
    except ValueError:
        dia = date.today()

    dados = relatorio_do_dia(dia)

    return render_template(
        "relatorio.html",
        dados=dados,
        grafico=grafico_por_hora(dados["por_hora"]),
        anterior=dia - timedelta(days=1),
        seguinte=dia + timedelta(days=1),
        hoje=date.today(),
    )


# ---------- Painel de chamada (TV da recepção) ----------

def primeiro_nome_e_inicial(nome):
    """'Maria da Silva Souza' -> 'Maria S.'

    O painel fica numa tela pública: mostrar o nome completo
    expõe o paciente sem necessidade.
    """
    partes = nome.split()
    if len(partes) == 1:
        return partes[0]
    return f"{partes[0]} {partes[-1][0]}."


def dados_do_painel():
    """O que a TV precisa mostrar, em formato de dicionário
    (vira JSON na rota /painel/dados)."""

    # Últimas chamadas: quem foi chamado mais recentemente vem primeiro.
    # Inclui quem já foi concluído, para a lista não "sumir" na TV.
    chamados = Paciente.query.filter(
        Paciente.chamado_em.isnot(None)
    ).order_by(
        Paciente.chamado_em.desc()
    ).limit(5).all()

    def resumo(paciente):
        return {
            # id + horário identificam UMA chamada; o JavaScript
            # usa isso para saber quando alguém novo foi chamado
            "chave": f"{paciente.id}-{paciente.chamado_em.isoformat()}",
            "nome": primeiro_nome_e_inicial(paciente.nome),
            "prioridade": paciente.prioridade,
            "hora": formatar_hora(paciente.chamado_em),
            "local": paciente.local,  # None em chamadas antigas
        }

    return {
        "atual": resumo(chamados[0]) if chamados else None,
        "anteriores": [resumo(p) for p in chamados[1:]],
        "aguardando": buscar_por_status("Aguardando").count(),
    }


@app.route("/painel")
def painel():
    # A página já vem preenchida; depois o JavaScript só atualiza
    return render_template("painel.html", dados=dados_do_painel())


@app.route("/painel/dados")
def painel_dados():
    # Um dicionário devolvido por uma rota vira JSON automaticamente
    return dados_do_painel()


@app.route("/pacientes/editar/<int:id>", methods=["GET", "POST"])
def editar_paciente(id):

    paciente = db.get_or_404(Paciente, id)

    if request.method == "POST":

        dados, erros = ler_formulario(paciente_id=id)

        if erros:
            mostrar_erros(erros)
            return render_template("editar_paciente.html", dados=dados)

        paciente.nome = dados["nome"]
        paciente.nascimento = dados["nascimento"]
        paciente.cpf = dados["cpf"]
        paciente.prioridade = dados["prioridade"]
        paciente.telefone = dados["telefone"]
        paciente.email = dados["email"]
        paciente.observacoes = dados["observacoes"]

        db.session.commit()

        flash(f"Dados de {paciente.nome} atualizados.", "sucesso")

        return redirect(url_for("pacientes"))

    # No GET, o formulário começa preenchido com os dados do banco
    return render_template("editar_paciente.html", dados=paciente)


@app.route("/pacientes/chamar-proximo", methods=["POST"])
def chamar_proximo():

    local = request.form.get("local", "")

    if local not in LOCAIS:
        flash("Escolha para qual local o paciente será chamado.", "erro")
        return redirect(url_for("pacientes"))

    # Lembra o local escolhido (na sessão de quem está logado):
    # quem atende no Consultório 2 não precisa escolhê-lo toda vez.
    session["ultimo_local"] = local

    paciente = buscar_por_status("Aguardando").first()

    if paciente:
        paciente.status = "Em atendimento"
        paciente.chamado_em = datetime.now()
        paciente.local = local
        db.session.commit()
        flash(
            f"Chamando {paciente.nome} ({paciente.prioridade}) para {local}.",
            "sucesso"
        )
    else:
        flash("Não há pacientes aguardando na fila.", "erro")

    return redirect(url_for("pacientes"))


@app.route("/pacientes/finalizar/<int:id>", methods=["POST"])
def finalizar_atendimento(id):
    paciente = db.get_or_404(Paciente, id)

    if paciente.status == "Em atendimento":
        paciente.status = "Concluído"
        paciente.concluido_em = datetime.now()
        db.session.commit()
        flash(f"Atendimento de {paciente.nome} concluído.", "sucesso")

    return redirect(url_for("pacientes"))


@app.route("/pacientes/excluir/<int:id>", methods=["POST"])
def excluir_paciente(id):
    paciente = db.get_or_404(Paciente, id)

    # Guarda o nome antes: depois de excluído, o objeto não pode mais ser lido
    nome = paciente.nome

    db.session.delete(paciente)
    db.session.commit()

    flash(f"Paciente {nome} excluído.", "sucesso")

    return redirect(url_for("pacientes"))


if __name__ == "__main__":
    # A estrutura do banco agora é criada/atualizada com:
    #   flask --app app db upgrade
    app.run(debug=True)
