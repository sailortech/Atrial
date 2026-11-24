import os
import re
import secrets
import unicodedata
from datetime import date, datetime, timedelta
from functools import wraps
from pathlib import Path

import click
from flask import (
    Flask, abort, flash, redirect, render_template, request, session, url_for
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
    # Atendimento encerrado: concluído OU "não compareceu" (ver status)
    concluido_em = db.Column(db.DateTime)

    # Para onde o paciente foi chamado (o NOME de um Local). Guardamos o
    # nome, e não o id, de propósito: é o registro do que aconteceu.
    # Se o local for desativado depois, o histórico continua igual.
    # Vazio em quem foi chamado antes de existir esta coluna.
    local = db.Column(db.String(50))

    # Quando foi chamado pela ÚLTIMA vez (no painel). Igual a chamado_em,
    # a não ser que tenha sido chamado de novo por não ter aparecido.
    # chamado_em continua sendo a 1ª chamada: é ela que mede a espera.
    ultima_chamada = db.Column(db.DateTime)

    @property
    def foi_rechamado(self):
        """True se o paciente foi chamado mais de uma vez."""
        return (
            self.ultima_chamada is not None
            and self.chamado_em is not None
            and self.ultima_chamada > self.chamado_em
        )

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

    # Papel: administração (True) pode mexer em locais e usuários;
    # recepção (False) só atende a fila e vê o relatório.
    admin = db.Column(db.Boolean, nullable=False, default=False)

    # Desativado = não consegue mais entrar (ex.: saiu da clínica).
    # Não apagamos: o registro de quem existiu continua no banco.
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    # True quando a senha foi definida pela ADMINISTRAÇÃO (cadastro ou
    # "esqueci a senha"): no próximo acesso a pessoa é obrigada a criar
    # a sua. Assim ninguém além dela conhece a senha definitiva.
    trocar_senha = db.Column(db.Boolean, nullable=False, default=False)

    # "Versão" das sessões deste usuário. O cookie de login guarda
    # id + versão (veja get_id). Trocar a versão invalida TODOS os
    # cookies antigos: quem estiver logado em outro computador cai.
    versao_sessao = db.Column(
        db.String(32), nullable=False, default=lambda: secrets.token_hex(16)
    )

    def get_id(self):
        # O Flask-Login guarda no cookie o que esta função devolver
        # (o padrão seria só o id). Ex.: "7:3f9a1c..."
        return f"{self.id}:{self.versao_sessao}"

    def encerrar_sessoes(self):
        """Derruba todas as sessões abertas deste usuário."""
        self.versao_sessao = secrets.token_hex(16)

    @property
    def is_active(self):
        # O Flask-Login consulta is_active no login_user(): para um
        # usuário inativo, ele se recusa a fazer o login.
        return self.ativo

    @property
    def papel(self):
        return "Administração" if self.admin else "Recepção"

    def definir_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)
        # Senha nova = sessões antigas não valem mais. Fica AQUI (e não
        # em cada rota) para nenhum jeito de trocar a senha esquecer disso.
        self.encerrar_sessoes()

    def confere_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)


PRIORIDADES = ["Normal", "Preferencial", "Urgente"]

# Status de quem já saiu da fila e do atendimento (vão para o histórico)
STATUS_ENCERRADOS = ["Concluído", "Não compareceu"]

# Para onde os pacientes podem ser chamados (triagem, consultórios...).
# Cadastrados pela página /locais.
class Local(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), nullable=False, unique=True)

    # Local desativado some do "Chamar para...", mas NÃO é apagado:
    # o histórico dos pacientes continua mostrando o nome dele.
    ativo = db.Column(db.Boolean, nullable=False, default=True)


def nomes_dos_locais_ativos():
    """['Consultório 1', 'Triagem', ...] em ordem alfabética."""
    return [
        local.nome
        for local in Local.query.filter_by(ativo=True).order_by(Local.nome)
    ]


@app.context_processor
def locais_nos_templates():
    """Tudo que esta função devolve fica disponível em TODOS os templates.

    Antes, LOCAIS era uma lista fixa no código (jinja_env.globals).
    Agora vem do banco e pode mudar a qualquer momento, então precisa
    ser lido de novo a cada página. O context_processor faz isso.
    (Passamos a FUNÇÃO, sem os parênteses: o banco só é consultado
    se o template chamar locais_ativos().)
    """
    return {"locais_ativos": nomes_dos_locais_ativos}

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
def carregar_usuario(id_da_sessao):
    """A sessão (o cookie) guarda "id:versão" (veja Usuario.get_id).
    A cada página, o Flask-Login chama esta função para buscar o
    usuário completo. Devolver None = "não está logado".

    - Versão diferente da do banco: a senha mudou depois deste login
      (ou o usuário foi desativado), então este cookie não vale mais.
    - Usuário desativado: é posto para fora NA HORA, mesmo que esteja
      com o sistema aberto (e não só no próximo login).
    """
    usuario_id, _, versao = id_da_sessao.partition(":")
    if not usuario_id.isdigit():
        return None

    usuario = db.session.get(Usuario, int(usuario_id))
    if usuario is None or not usuario.ativo:
        return None

    # compare_digest compara sem "vazar" pelo tempo de resposta quantos
    # caracteres acertou (hábito bom sempre que se compara um segredo)
    if not secrets.compare_digest(versao, usuario.versao_sessao):
        return None

    return usuario


def admin_obrigatorio(rota):
    """Decorador: a rota só abre para quem é da administração.

        @app.route("/locais")
        @admin_obrigatorio
        def locais(): ...

    Um decorador "embrulha" a função da rota: o Python troca locais
    por permitir(locais), que confere o papel ANTES de chamar a rota.
    (O login em si já foi exigido pelo before_request.)
    """
    @wraps(rota)  # mantém o nome da função (o Flask usa no url_for)
    def permitir(*args, **kwargs):
        if not current_user.admin:
            flash("Só a administração pode acessar essa página.", "erro")
            return redirect(url_for("pacientes"))
        return rota(*args, **kwargs)

    # Uma "etiqueta" na função: os testes procuram todas as rotas
    # com ela para conferir que nenhuma ficou sem teste de permissão.
    permitir.so_admin = True
    return permitir


def validar_novo_usuario(login, nome, senha):
    """Regras para criar usuário (usadas pela página e pelo comando).
    Devolve a lista de erros; vazia = tudo certo."""
    erros = []

    if not nome:
        erros.append("Informe o nome.")
    if not re.fullmatch(r"[a-z0-9._-]{3,50}", login):
        erros.append(
            "O usuário deve ter de 3 a 50 caracteres: letras sem acento, "
            "números, ponto, hífen ou sublinhado."
        )
    elif Usuario.query.filter_by(login=login).first():
        erros.append(f"Já existe o usuário '{login}'.")

    return erros + validar_senha(senha)


def validar_senha(senha, confirmacao=None):
    """Regras de toda senha nova (cadastro, troca e redefinição).
    confirmacao=None: o formulário não tem campo de confirmação."""
    erros = []

    if len(senha) < 8:
        erros.append("A senha precisa ter pelo menos 8 caracteres.")
    if confirmacao is not None and senha != confirmacao:
        erros.append("A confirmação não é igual à nova senha.")

    return erros


# Páginas que qualquer um pode ver, sem login.
# O painel fica na TV da recepção, então não pode pedir senha.
PAGINAS_PUBLICAS = {"login", "static", "painel", "painel_dados"}


@app.before_request
def exigir_login():
    """Roda ANTES de toda rota. Quem não entrou vai para o login.

    Proteger tudo por padrão é mais seguro do que marcar rota por rota:
    uma rota nova já nasce protegida, mesmo que alguém esqueça.
    """
    if request.endpoint in PAGINAS_PUBLICAS:
        return None  # pode seguir para a rota

    if current_user.is_authenticated:
        # Senha provisória (dada pela administração)? Até criar a própria,
        # a pessoa só consegue trocar a senha ou sair.
        if current_user.trocar_senha and request.endpoint not in {"minha_senha", "logout"}:
            flash("Crie uma senha sua para continuar.", "erro")
            return redirect(url_for("minha_senha"))
        return None

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
            # Só contamos que o usuário está desativado para quem acertou
            # a senha: assim isso não vira um jeito de descobrir logins.
            if not usuario.ativo:
                flash("Este usuário foi desativado. Fale com a administração.", "erro")
                return render_template("login.html", login=login_digitado, proxima=proxima)

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
@click.option("--admin", is_flag=True, help="Cria como administração.")
def criar_usuario(login, nome, senha, admin):
    """Cria um usuário. Uso:

        flask --app app criar-usuario maria
        flask --app app criar-usuario layanne --admin

    Serve para criar o PRIMEIRO administrador; depois disso, a
    administração pode cadastrar os outros pela página Usuários.
    """
    login = login.strip().lower()
    nome = nome.strip()

    erros = validar_novo_usuario(login, nome, senha)
    if erros:
        raise click.ClickException(" ".join(erros))

    usuario = Usuario(nome=nome, login=login, admin=admin)
    usuario.definir_senha(senha)
    db.session.add(usuario)
    db.session.commit()

    papel = "administração" if admin else "recepção"
    click.echo(f"Usuário '{login}' criado ({papel}).")


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

    # Histórico: os encerrados (atendidos ou ausentes), mais recentes primeiro
    concluidos = filtrar_busca(
        Paciente.query.filter(Paciente.status.in_(STATUS_ENCERRADOS)), termo
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
    encerrados = [p for p in pacientes if no_dia(p.concluido_em, dia)]
    # Só quem foi atendido de verdade entra em "atendidos" e na duração
    concluidos = [p for p in encerrados if p.status == "Concluído"]
    ausentes = [p for p in encerrados if p.status == "Não compareceu"]

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
        "nao_compareceram": len(ausentes),
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
            for local in locais_do_relatorio(concluidos)
        ],
    }


def locais_do_relatorio(concluidos):
    """Os locais ativos hoje + qualquer outro que tenha atendido no dia.

    Assim, um consultório desativado ontem ainda aparece no relatório
    dos dias em que funcionou.
    """
    nomes = set(nomes_dos_locais_ativos())
    nomes.update(p.local for p in concluidos if p.local)
    return sorted(nomes)


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

    # Últimas chamadas: quem foi chamado mais recentemente vem primeiro
    # (contando o "chamar de novo": quem foi chamado outra vez volta ao topo).
    # Inclui quem já foi concluído, para a lista não "sumir" na TV.
    chamados = Paciente.query.filter(
        Paciente.ultima_chamada.isnot(None)
    ).order_by(
        Paciente.ultima_chamada.desc()
    ).limit(5).all()

    def resumo(paciente):
        return {
            # id + horário identificam UMA chamada; o JavaScript
            # usa isso para saber quando alguém foi chamado (de novo ou não)
            "chave": f"{paciente.id}-{paciente.ultima_chamada.isoformat()}",
            "nome": primeiro_nome_e_inicial(paciente.nome),
            "prioridade": paciente.prioridade,
            "hora": formatar_hora(paciente.ultima_chamada),
            "local": paciente.local,  # None em chamadas antigas
            "de_novo": paciente.foi_rechamado,
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

    if local not in nomes_dos_locais_ativos():
        flash("Escolha para qual local o paciente será chamado.", "erro")
        return redirect(url_for("pacientes"))

    # Lembra o local escolhido (na sessão de quem está logado):
    # quem atende no Consultório 2 não precisa escolhê-lo toda vez.
    session["ultimo_local"] = local

    paciente = buscar_por_status("Aguardando").first()

    if paciente:
        agora = datetime.now()
        paciente.status = "Em atendimento"
        paciente.chamado_em = agora
        paciente.ultima_chamada = agora
        paciente.local = local
        db.session.commit()
        flash(
            f"Chamando {paciente.nome} ({paciente.prioridade}) para {local}.",
            "sucesso"
        )
    else:
        flash("Não há pacientes aguardando na fila.", "erro")

    return redirect(url_for("pacientes"))


@app.route("/pacientes/chamar-de-novo/<int:id>", methods=["POST"])
def chamar_de_novo(id):
    """O paciente foi chamado mas não apareceu: chama outra vez.

    Só muda ultima_chamada. Isso basta para o painel mostrar o nome
    de novo (e tocar o som), sem estragar o tempo de espera do relatório.
    """
    paciente = db.get_or_404(Paciente, id)

    if paciente.status == "Em atendimento":
        paciente.ultima_chamada = datetime.now()
        db.session.commit()
        flash(f"Chamando {paciente.nome} novamente.", "sucesso")

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


@app.route("/pacientes/nao-compareceu/<int:id>", methods=["POST"])
def nao_compareceu(id):
    """Foi chamado (talvez mais de uma vez) e não apareceu.

    Encerra como "Não compareceu": sai de "Em atendimento", vai para o
    histórico, mas NÃO conta como atendido nem entra na duração média.
    """
    paciente = db.get_or_404(Paciente, id)

    if paciente.status == "Em atendimento":
        paciente.status = "Não compareceu"
        paciente.concluido_em = datetime.now()
        db.session.commit()
        flash(f"{paciente.nome} marcado como não compareceu.", "sucesso")

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


# ---------- Locais (cadastro) ----------

@app.route("/locais", methods=["GET", "POST"])
@admin_obrigatorio
def locais():

    if request.method == "POST":
        # " consultório  4 " -> "consultório 4" (tira espaços sobrando)
        nome = " ".join(request.form.get("nome", "").split())

        # Compara sem acentos/maiúsculas: "consultorio 1" e "Consultório 1"
        # seriam o mesmo local, só digitado diferente.
        repetido = any(
            normalizar(local.nome) == normalizar(nome)
            for local in Local.query.all()
        )

        if not nome:
            flash("Informe o nome do local.", "erro")
        elif len(nome) > 50:
            flash("O nome pode ter no máximo 50 caracteres.", "erro")
        elif repetido:
            flash(f"Já existe um local chamado \"{nome}\" (veja a lista abaixo).", "erro")
        else:
            db.session.add(Local(nome=nome))
            db.session.commit()
            flash(f"Local \"{nome}\" adicionado.", "sucesso")

        return redirect(url_for("locais"))

    return render_template(
        "locais.html",
        # Ativos primeiro; dentro de cada grupo, em ordem alfabética
        locais=Local.query.order_by(Local.ativo.desc(), Local.nome).all(),
    )


@app.route("/locais/<int:id>/alternar", methods=["POST"])
@admin_obrigatorio
def alternar_local(id):
    """Desativa um local ativo, ou reativa um desativado."""
    local = db.get_or_404(Local, id)

    if local.ativo and len(nomes_dos_locais_ativos()) == 1:
        # Sem nenhum local ativo, ninguém conseguiria chamar pacientes
        flash("É preciso ter pelo menos um local ativo.", "erro")
        return redirect(url_for("locais"))

    local.ativo = not local.ativo
    db.session.commit()

    situacao = "reativado" if local.ativo else "desativado"
    flash(f"Local \"{local.nome}\" {situacao}.", "sucesso")

    return redirect(url_for("locais"))


# ---------- Usuários (só administração) ----------

@app.route("/usuarios", methods=["GET", "POST"])
@admin_obrigatorio
def usuarios():

    if request.method == "POST":
        login = request.form.get("login", "").strip().lower()
        nome = request.form.get("nome", "").strip()
        senha = request.form.get("senha", "")
        # Caixa de seleção: só vem no formulário quando está marcada
        admin = request.form.get("admin") == "sim"

        erros = validar_novo_usuario(login, nome, senha)

        if erros:
            mostrar_erros(erros)
            # Devolve o que foi digitado (MENOS a senha, por segurança)
            return render_template(
                "usuarios.html", usuarios=lista_de_usuarios(),
                dados={"login": login, "nome": nome, "admin": admin},
            )

        # trocar_senha=True: a senha inicial foi escolhida pela administração
        usuario = Usuario(nome=nome, login=login, admin=admin, trocar_senha=True)
        usuario.definir_senha(senha)
        db.session.add(usuario)
        db.session.commit()

        flash(
            f"Usuário '{login}' criado ({usuario.papel}). "
            "No primeiro acesso, a pessoa vai criar a própria senha.",
            "sucesso"
        )
        return redirect(url_for("usuarios"))

    return render_template("usuarios.html", usuarios=lista_de_usuarios(), dados={})


def lista_de_usuarios():
    # Ativos primeiro; depois por nome
    return Usuario.query.order_by(Usuario.ativo.desc(), Usuario.nome).all()


@app.route("/usuarios/<int:id>/<acao>", methods=["POST"])
@admin_obrigatorio
def alterar_usuario(id, acao):
    """acao: 'ativo' (desativa/reativa) ou 'admin' (troca o papel)."""
    usuario = db.get_or_404(Usuario, id)

    if acao not in ("ativo", "admin"):
        abort(404)

    # Ninguém mexe no PRÓPRIO acesso: evita alguém se trancar fora
    # sem querer (ex.: o único admin tirando o próprio papel).
    #
    # Essa regra sozinha já garante que o sistema nunca fica sem admin:
    # quem está aqui é um admin ativo (o decorador garante), e ele só
    # pode mexer nos OUTROS. Então sempre sobra pelo menos ele mesmo.
    if usuario.id == current_user.id:
        flash("Você não pode alterar o seu próprio acesso.", "erro")
        return redirect(url_for("usuarios"))

    if acao == "ativo":
        usuario.ativo = not usuario.ativo
        mensagem = "reativado" if usuario.ativo else "desativado"
        if not usuario.ativo:
            # Sem isso, o cookie antigo "ressuscitaria" se a pessoa
            # fosse reativada: ela teria que entrar com a senha de novo.
            usuario.encerrar_sessoes()
    else:
        usuario.admin = not usuario.admin
        mensagem = f"agora é da {usuario.papel.lower()}"

    db.session.commit()
    flash(f"Usuário '{usuario.login}' {mensagem}.", "sucesso")

    return redirect(url_for("usuarios"))


# ---------- Senhas ----------

@app.route("/minha-senha", methods=["GET", "POST"])
def minha_senha():
    """Qualquer pessoa logada troca a PRÓPRIA senha."""

    if request.method == "POST":
        atual = request.form.get("atual", "")
        nova = request.form.get("nova", "")
        confirmacao = request.form.get("confirmacao", "")

        erros = []
        # Pedir a senha atual protege quem deixou o computador logado:
        # quem sentar ali não consegue trocar a senha e "roubar" a conta.
        if not current_user.confere_senha(atual):
            erros.append("A senha atual está incorreta.")
        erros += validar_senha(nova, confirmacao)
        if not erros and nova == atual:
            erros.append("A nova senha precisa ser diferente da atual.")

        if erros:
            mostrar_erros(erros)
            return render_template("minha_senha.html")

        current_user.definir_senha(nova)  # também derruba as outras sessões
        current_user.trocar_senha = False
        db.session.commit()

        # ...inclusive ESTA. Então logamos de novo aqui, gravando no
        # cookie a versão nova: a pessoa continua dentro, e só os outros
        # computadores (talvez de quem descobriu a senha antiga) caem.
        login_user(current_user._get_current_object())

        flash("Senha alterada.", "sucesso")
        return redirect(url_for("pacientes"))

    return render_template("minha_senha.html")


@app.route("/usuarios/<int:id>/senha", methods=["GET", "POST"])
@admin_obrigatorio
def redefinir_senha(id):
    """A administração dá uma senha PROVISÓRIA para quem esqueceu a sua."""
    usuario = db.get_or_404(Usuario, id)

    if usuario.id == current_user.id:
        # Para a própria senha existe "Minha senha" (que pede a atual)
        return redirect(url_for("minha_senha"))

    if request.method == "POST":
        nova = request.form.get("nova", "")
        erros = validar_senha(nova)

        if erros:
            mostrar_erros(erros)
            return render_template("redefinir_senha.html", usuario=usuario)

        usuario.definir_senha(nova)
        usuario.trocar_senha = True  # no próximo acesso, cria a própria
        db.session.commit()

        flash(
            f"Senha provisória definida para '{usuario.login}'. "
            "No próximo acesso, a pessoa vai criar a própria senha.",
            "sucesso"
        )
        return redirect(url_for("usuarios"))

    return render_template("redefinir_senha.html", usuario=usuario)


if __name__ == "__main__":
    # A estrutura do banco agora é criada/atualizada com:
    #   flask --app app db upgrade
    app.run(debug=True)
