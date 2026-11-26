import os
import re
import secrets
import unicodedata
from datetime import date, datetime, timedelta
from functools import wraps
from pathlib import Path

import click
from flask import (
    Flask, jsonify, redirect, request, send_from_directory, session,
)

from flask_login import (
    LoginManager, UserMixin, current_user, login_user, logout_user
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import validates
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFError, CSRFProtect, generate_csrf
from werkzeug.security import check_password_hash, generate_password_hash, safe_join


# static_folder=None: o Flask não serve mais CSS/JS próprios. As telas
# são do React, entregues em /app/ (veja frontend_react).
app = Flask(__name__, static_folder=None)

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

# Onde está o React pronto (gerado com "npm run build" em frontend/).
# ATRIAL_FRONTEND_DIST troca a pasta (os testes usam uma pasta de mentira).
app.config["FRONTEND_DIST"] = os.environ.get(
    "ATRIAL_FRONTEND_DIST", str(Path(app.root_path).parent / "frontend" / "dist")
)

db = SQLAlchemy(app)

# Migrations: cuidam das mudanças na estrutura do banco
# (ex.: adicionar uma coluna) sem perder os dados.
migrate = Migrate(app, db)

# Proteção contra CSRF: todo pedido que muda algo (POST, PUT, DELETE)
# precisa mandar um código secreto que só o próprio Atrial conhece (o
# React o recebe em /api/sessao e manda no cabeçalho X-CSRFToken).
# Assim, um site malicioso aberto em outra aba não consegue fazer
# nada (excluir paciente, chamar próximo...) em seu nome.
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


# ---------- Proteção contra "chutar" senhas ----------

LIMITE_DE_ERROS = 5                    # senhas erradas seguidas...
TEMPO_DE_BLOQUEIO = timedelta(minutes=15)  # ...bloqueiam por este tempo


def agora():
    """datetime.now() numa função própria: nos testes dá para trocá-la
    (monkeypatch) e "avançar o relógio" sem esperar 15 minutos."""
    return datetime.now()


class TentativaLogin(db.Model):
    """Erros de senha por LOGIN DIGITADO, exista o usuário ou não.

    Contar também logins que não existem é de propósito: se só contas
    reais fossem bloqueadas, o bloqueio revelaria quais logins existem.
    """
    login = db.Column(db.String(50), primary_key=True)
    erros = db.Column(db.Integer, nullable=False, default=0)
    ultimo_erro = db.Column(db.DateTime)
    bloqueado_ate = db.Column(db.DateTime)

    def bloqueado(self):
        return self.bloqueado_ate is not None and self.bloqueado_ate > agora()

    def minutos_restantes(self):
        segundos = (self.bloqueado_ate - agora()).total_seconds()
        return max(1, int(-(-segundos // 60)))  # arredonda para cima

    def registrar_erro(self):
        # Erros antigos "vencem": 5 erros espalhados num mês não bloqueiam
        if self.ultimo_erro and agora() - self.ultimo_erro > TEMPO_DE_BLOQUEIO:
            self.erros = 0

        self.erros += 1
        self.ultimo_erro = agora()

        if self.erros >= LIMITE_DE_ERROS:
            self.bloqueado_ate = agora() + TEMPO_DE_BLOQUEIO
            self.erros = 0  # depois do bloqueio, começa a contar de novo


# Hash de uma senha qualquer, calculado uma vez quando o app inicia.
# Serve para gastar o MESMO tempo quando o login digitado não existe
# (veja a rota de login).
HASH_PARA_IGUALAR_TEMPO = generate_password_hash(secrets.token_hex(16))


PRIORIDADES = ["Normal", "Preferencial", "Urgente"]

# Status de quem já saiu da fila e do atendimento (vão para o histórico)
STATUS_ENCERRADOS = ["Concluído", "Não compareceu"]

# Para onde os pacientes podem ser chamados (triagem, consultórios...).
# Cadastrados pela administração (tela Locais).
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


def formatar_cpf(cpf):
    """'12345678909' -> '123.456.789-09'"""
    if len(cpf) != 11:
        return cpf
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"


def formatar_hora(momento):
    """datetime -> '14:32'   (None -> '-')"""
    if momento is None:
        return "-"
    return momento.strftime("%H:%M")


def formatar_duracao(inicio, fim=None):
    """Tempo entre dois horários, em texto ('15 min').
    Sem fim: de inicio até agora."""
    if inicio is None:
        return "-"

    fim = fim or datetime.now()
    return formatar_minutos((fim - inicio).total_seconds() / 60)


def formatar_minutos(minutos):
    """135 -> '2h 15min'   (None -> '-')"""
    if minutos is None:
        return "-"

    minutos = int(minutos)

    if minutos < 1:
        return "menos de 1 min"
    if minutos < 60:
        return f"{minutos} min"

    horas, minutos = divmod(minutos, 60)
    return f"{horas}h {minutos:02d}min"


def ler_formulario(origem, paciente_id=None):
    """Lê, limpa e valida os campos do formulário de paciente.

    origem = o JSON que o React mandou (um dicionário).

    Devolve (dados, erros). erros é um dicionário campo -> mensagem
    (ex.: {"cpf": "CPF inválido..."}); vazio = tudo certo. Por campo
    para o React poder mostrar cada erro embaixo do seu campo.
    Na edição, passe paciente_id para o próprio paciente
    não ser acusado de CPF duplicado.
    """
    def campo(nome):
        # str(): no JSON pode vir número ou null; no formulário é sempre texto
        valor = origem.get(nome)
        return "" if valor is None else str(valor).strip()

    dados = {
        "nome": campo("nome"),
        "nascimento": campo("nascimento"),
        "cpf": somente_digitos(campo("cpf")),
        "prioridade": campo("prioridade"),
        "telefone": campo("telefone"),
        "email": campo("email"),
        "observacoes": campo("observacoes"),
    }

    erros = {}

    if not dados["nome"]:
        erros["nome"] = "Informe o nome do paciente."

    try:
        if date.fromisoformat(dados["nascimento"]) > date.today():
            erros["nascimento"] = "A data de nascimento não pode estar no futuro."
    except ValueError:
        erros["nascimento"] = "Informe uma data de nascimento válida."

    if not cpf_valido(dados["cpf"]):
        erros["cpf"] = "CPF inválido. Confira os números digitados."
    else:
        mesmo_cpf = Paciente.query.filter_by(cpf=dados["cpf"])

        if paciente_id is not None:
            mesmo_cpf = mesmo_cpf.filter(Paciente.id != paciente_id)

        if mesmo_cpf.first():
            erros["cpf"] = "Já existe um paciente cadastrado com este CPF."

    if dados["prioridade"] not in PRIORIDADES:
        erros["prioridade"] = "Escolha uma prioridade válida."

    return dados, erros


def acao_cadastrar_paciente(dados):
    """Cria o paciente (já validado) e o coloca no fim da fila."""
    paciente = Paciente(**dados, status="Aguardando", chegada=datetime.now())
    db.session.add(paciente)
    db.session.commit()
    return paciente


def acao_excluir_paciente(paciente):
    """Apaga o paciente de vez (some também do histórico e do relatório).
    Devolve a mensagem de confirmação."""
    # Guarda o nome antes: depois de excluído, o objeto não pode mais ser lido
    nome = paciente.nome
    db.session.delete(paciente)
    db.session.commit()
    return f"Paciente {nome} excluído."


def acao_editar_paciente(paciente, dados):
    """Atualiza os dados (já validados). Status e horários não mudam."""
    for nome, valor in dados.items():
        setattr(paciente, nome, valor)
    db.session.commit()


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

        @app.get("/api/locais")
        @admin_obrigatorio
        def api_locais(): ...

    Um decorador "embrulha" a função da rota: o Python troca api_locais
    por permitir(api_locais), que confere o papel ANTES de chamar a rota.
    (O login em si já foi exigido pelo before_request.)
    """
    @wraps(rota)  # mantém o nome da função (o Flask usa como nome da rota)
    def permitir(*args, **kwargs):
        if not current_user.admin:
            # 403 = "sei quem você é, mas você não pode"
            return jsonify(erro="Só a administração pode fazer isso."), 403
        return rota(*args, **kwargs)

    # Uma "etiqueta" na função: os testes procuram todas as rotas
    # com ela para conferir que nenhuma ficou sem teste de permissão.
    permitir.so_admin = True
    return permitir


def validar_novo_usuario(login, nome, senha):
    """Regras para criar usuário (usadas pela API e pelo comando). Devolve erros por campo (campo -> mensagem); vazio = ok."""
    erros = {}

    if not nome:
        erros["nome"] = "Informe o nome."
    if not re.fullmatch(r"[a-z0-9._-]{3,50}", login):
        erros["login"] = (
            "O usuário deve ter de 3 a 50 caracteres: letras sem acento, "
            "números, ponto, hífen ou sublinhado."
        )
    elif Usuario.query.filter_by(login=login).first():
        erros["login"] = f"Já existe o usuário '{login}'."
    for erro in validar_senha(senha):
        erros["senha"] = erro

    return erros


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
PAGINAS_PUBLICAS = {
    "painel_dados",
    # API do React: ver se está logado e fazer o login
    "api_sessao", "api_login",
    # Os arquivos do React (HTML, JS, CSS) não têm dados: quem pede
    # login é o próprio React, perguntando à API
    "frontend_react",
    # Endereços antigos (/pacientes, /painel...): só redirecionam para /app/
    "endereco_antigo",
}

# O que quem está com senha provisória ainda pode usar
LIBERADAS_COM_SENHA_PROVISORIA = {"api_sessao", "api_logout", "api_minha_senha"}


@app.before_request
def exigir_login():
    """Roda ANTES de toda rota. Sem login, só as PAGINAS_PUBLICAS abrem.

    Proteger tudo por padrão é mais seguro do que marcar rota por rota:
    uma rota nova já nasce protegida, mesmo que alguém esqueça.

    A resposta é JSON com o código HTTP certo: quem decide qual tela
    mostrar (login, troca de senha) é o React.
    """
    if request.endpoint in PAGINAS_PUBLICAS:
        return None  # pode seguir para a rota

    if request.endpoint is None:
        return None  # endereço que não existe: segue para o 404 normal

    if current_user.is_authenticated:
        # Senha provisória (dada pela administração)? Até criar a própria,
        # a pessoa só consegue trocar a senha ou sair.
        if current_user.trocar_senha and request.endpoint not in LIBERADAS_COM_SENHA_PROVISORIA:
            return jsonify(erro="Crie uma senha sua para continuar.", trocar_senha=True), 403
        return None

    # 401 = "não autenticado": o React mostra a tela de login
    return jsonify(erro="Faça login para continuar."), 401


def autenticar(login_digitado, senha):
    """Confere login e senha, com todas as proteções. Devolve
    (usuario, None) se deu certo ou (None, mensagem_de_erro).

    Usada pela API (/api/login). Fica separada da rota para as regras
    de segurança poderem ser lidas (e testadas) sozinhas.
    """
    tentativa = db.session.get(TentativaLogin, login_digitado)

    # Bloqueado? Nem confere a senha: senão daria para continuar
    # "chutando" e só descobrir qual acertou depois do bloqueio.
    if tentativa and tentativa.bloqueado():
        return None, (
            "Muitas tentativas com senha errada. Tente de novo em "
            f"{tentativa.minutos_restantes()} min."
        )

    usuario = Usuario.query.filter_by(login=login_digitado).first()

    if usuario:
        senha_certa = usuario.confere_senha(senha)
    else:
        # Login inexistente: confere contra um hash qualquer só para
        # DEMORAR o mesmo tanto. Sem isso, a resposta rápida entregaria
        # que o login não existe (quem mede o tempo descobriria).
        check_password_hash(HASH_PARA_IGUALAR_TEMPO, senha)
        senha_certa = False

    if not senha_certa:
        if login_digitado:
            tentativa = tentativa or TentativaLogin(login=login_digitado, erros=0)
            tentativa.registrar_erro()
            db.session.add(tentativa)
            db.session.commit()

        # Mesma mensagem para usuário inexistente e senha errada:
        # assim ninguém descobre quais logins existem testando.
        return None, "Usuário ou senha incorretos."

    # Acertou: zera os erros deste login
    if tentativa:
        db.session.delete(tentativa)
        db.session.commit()

    # Só contamos que o usuário está desativado para quem acertou
    # a senha: assim isso não vira um jeito de descobrir logins.
    if not usuario.ativo:
        return None, "Este usuário foi desativado. Fale com a administração."

    return usuario, None


def login_digitado_do(texto):
    # [:50]: o login vira chave na tabela de tentativas; não deixamos
    # alguém mandar um texto enorme para encher o banco
    return (texto or "").strip().lower()[:50]


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
        raise click.ClickException(" ".join(erros.values()))

    usuario = Usuario(nome=nome, login=login, admin=admin)
    usuario.definir_senha(senha)
    db.session.add(usuario)
    db.session.commit()

    papel = "administração" if admin else "recepção"
    click.echo(f"Usuário '{login}' criado ({papel}).")


@app.errorhandler(CSRFError)
def erro_csrf(erro):
    """Pedido sem o código CSRF ou com um código inválido.

    Na prática quase sempre é inofensivo (ex.: a pessoa saiu e entrou
    de novo em outra aba, e a página antiga ficou com o código velho).
    Em vez da página de erro 400 do Flask, uma mensagem que o React mostra.
    """
    return jsonify(erro="Sessão desatualizada. Recarregue a página."), 400


# ---------- Fila de pacientes ----------

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


def listas_de_pacientes(termo):
    """As três listas da tela de pacientes (usadas pela API)."""
    # A posição na fila vem da fila COMPLETA: se a busca esconder
    # alguém, quem sobrou não pode "subir" de posição.
    posicoes = {
        paciente.id: numero
        for numero, paciente in enumerate(buscar_por_status("Aguardando"), start=1)
    }

    return {
        "em_atendimento": filtrar_busca(
            buscar_por_status("Em atendimento"), termo
        ).all(),
        "fila": filtrar_busca(buscar_por_status("Aguardando"), termo).all(),
        "posicoes": posicoes,
        # Histórico: os encerrados (atendidos ou ausentes), mais recentes primeiro
        "concluidos": filtrar_busca(
            Paciente.query.filter(Paciente.status.in_(STATUS_ENCERRADOS)), termo
        ).order_by(Paciente.id.desc()).all(),
    }


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


def horas_do_grafico(por_hora):
    """As horas do eixo: pelo menos o horário comercial (7h às 18h),
    e mais se houve movimento fora dele. O React desenha o gráfico
    com estas horas (todas, inclusive as sem ninguém)."""
    return list(range(min(7, *por_hora), max(18, *por_hora) + 1))


def dia_do_pedido():
    """?dia=2026-11-18 escolhe o dia; sem nada (ou inválido), é hoje."""
    try:
        return date.fromisoformat(request.args.get("dia", ""))
    except ValueError:
        return date.today()


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


# Pública: a TV não faz login. Mostra só primeiro nome + inicial.
@app.get("/painel/dados")
def painel_dados():
    # Um dicionário devolvido por uma rota vira JSON automaticamente
    return dados_do_painel()


# ---------- Ações de atendimento ----------
# Cada ação é uma função que devolve (deu_certo, mensagem); a API
# transforma isso em JSON (resposta_da_acao). Separar a REGRA da rota
# deixa a regra fácil de ler e de testar.

def acao_chamar_proximo(local):
    if local not in nomes_dos_locais_ativos():
        return False, "Escolha para qual local o paciente será chamado."

    # Lembra o local escolhido (na sessão de quem está logado):
    # quem atende no Consultório 2 não precisa escolhê-lo toda vez.
    session["ultimo_local"] = local

    paciente = buscar_por_status("Aguardando").first()
    if not paciente:
        return False, "Não há pacientes aguardando na fila."

    agora = datetime.now()
    paciente.status = "Em atendimento"
    paciente.chamado_em = agora
    paciente.ultima_chamada = agora
    paciente.local = local
    db.session.commit()
    return True, f"Chamando {paciente.nome} ({paciente.prioridade}) para {local}."


def acao_chamar_de_novo(paciente):
    """O paciente foi chamado mas não apareceu: chama outra vez.

    Só muda ultima_chamada. Isso basta para o painel mostrar o nome
    de novo (e tocar o som), sem estragar o tempo de espera do relatório.
    """
    if paciente.status != "Em atendimento":
        return False, "Este paciente não está em atendimento."

    paciente.ultima_chamada = datetime.now()
    db.session.commit()
    return True, f"Chamando {paciente.nome} novamente."


def acao_concluir(paciente):
    if paciente.status != "Em atendimento":
        return False, "Este paciente não está em atendimento."

    paciente.status = "Concluído"
    paciente.concluido_em = datetime.now()
    db.session.commit()
    return True, f"Atendimento de {paciente.nome} concluído."


def acao_nao_compareceu(paciente):
    """Foi chamado (talvez mais de uma vez) e não apareceu.

    Encerra como "Não compareceu": sai de "Em atendimento", vai para o
    histórico, mas NÃO conta como atendido nem entra na duração média.
    """
    if paciente.status != "Em atendimento":
        return False, "Este paciente não está em atendimento."

    paciente.status = "Não compareceu"
    paciente.concluido_em = datetime.now()
    db.session.commit()
    return True, f"{paciente.nome} marcado como não compareceu."


# ---------- Locais (cadastro) ----------

def lista_de_locais():
    # Ativos primeiro; dentro de cada grupo, em ordem alfabética
    return Local.query.order_by(Local.ativo.desc(), Local.nome).all()


def validar_nome_de_local(texto, local_id=None):
    """Limpa e confere o nome de um local. Devolve (nome, erro); erro
    None = pode usar.

    Ao RENOMEAR, passe local_id: o próprio local não conta como
    repetido (assim dá para corrigir "triagem" para "Triagem")."""
    # " consultório  4 " -> "consultório 4" (tira espaços sobrando)
    nome = " ".join(str(texto or "").split())

    # Compara sem acentos/maiúsculas: "consultorio 1" e "Consultório 1"
    # seriam o mesmo local, só digitado diferente.
    repetido = any(
        normalizar(local.nome) == normalizar(nome)
        for local in Local.query.all()
        if local.id != local_id
    )

    if not nome:
        return nome, "Informe o nome do local."
    if len(nome) > 50:
        return nome, "O nome pode ter no máximo 50 caracteres."
    if repetido:
        return nome, f"Já existe um local chamado \"{nome}\" (veja a lista abaixo)."
    return nome, None


def acao_adicionar_local(nome):
    db.session.add(Local(nome=nome))
    db.session.commit()
    return f"Local \"{nome}\" adicionado."


def acao_renomear_local(local, nome):
    """Troca o nome (já validado). Devolve a mensagem.

    Os pacientes já chamados para este local continuam com o nome
    ANTIGO (Paciente.local guarda o texto, de propósito): é o registro
    de para onde foram chamados. Só as próximas chamadas usam o novo.
    """
    antigo = local.nome
    local.nome = nome
    db.session.commit()
    if antigo == nome:
        return f"O local \"{nome}\" continua com o mesmo nome."
    return f"Local \"{antigo}\" agora se chama \"{nome}\"."


def acao_alternar_local(local):
    """Desativa um local ativo, ou reativa um desativado.
    Devolve (deu_certo, mensagem), como as ações de atendimento."""
    if local.ativo and len(nomes_dos_locais_ativos()) == 1:
        # Sem nenhum local ativo, ninguém conseguiria chamar pacientes
        return False, "É preciso ter pelo menos um local ativo."

    local.ativo = not local.ativo
    db.session.commit()

    situacao = "reativado" if local.ativo else "desativado"
    return True, f"Local \"{local.nome}\" {situacao}."


# ---------- Usuários (só administração) ----------

def acao_criar_usuario(nome, login, senha, admin):
    """Cria o usuário (já validado). Devolve a mensagem de confirmação."""
    # trocar_senha=True: a senha inicial foi escolhida pela administração
    usuario = Usuario(nome=nome, login=login, admin=admin, trocar_senha=True)
    usuario.definir_senha(senha)
    db.session.add(usuario)
    db.session.commit()
    return (
        f"Usuário '{login}' criado ({usuario.papel}). "
        "No primeiro acesso, a pessoa vai criar a própria senha."
    )


def lista_de_usuarios():
    # Ativos primeiro; depois por nome
    return Usuario.query.order_by(Usuario.ativo.desc(), Usuario.nome).all()


def acao_alterar_usuario(usuario, acao):
    """acao 'ativo' (desativa/reativa) ou 'admin' (troca o papel).
    Devolve (deu_certo, mensagem)."""

    # Ninguém mexe no PRÓPRIO acesso: evita alguém se trancar fora
    # sem querer (ex.: o único admin tirando o próprio papel).
    #
    # Essa regra sozinha já garante que o sistema nunca fica sem admin:
    # quem está aqui é um admin ativo (o decorador garante), e ele só
    # pode mexer nos OUTROS. Então sempre sobra pelo menos ele mesmo.
    if usuario.id == current_user.id:
        return False, "Você não pode alterar o seu próprio acesso."

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
    return True, f"Usuário '{usuario.login}' {mensagem}."


# ---------- Senhas ----------

def erros_da_troca_de_senha(atual, nova, confirmacao):
    """Confere a troca da PRÓPRIA senha. Devolve erros por campo
    (dicionário campo -> mensagem, como em ler_formulario); vazio = ok."""
    erros = {}
    # Pedir a senha atual protege quem deixou o computador logado:
    # quem sentar ali não consegue trocar a senha e "roubar" a conta.
    if not current_user.confere_senha(atual):
        erros["atual"] = "A senha atual está incorreta."
    for erro in validar_senha(nova):
        erros["nova"] = erro
    if nova != confirmacao:
        erros["confirmacao"] = "A confirmação não é igual à nova senha."
    if not erros and nova == atual:
        erros["nova"] = "A nova senha precisa ser diferente da atual."
    return erros


def acao_trocar_minha_senha(nova):
    current_user.definir_senha(nova)  # também derruba as outras sessões
    current_user.trocar_senha = False
    db.session.commit()

    # ...inclusive ESTA. Então logamos de novo aqui, gravando no
    # cookie a versão nova: a pessoa continua dentro, e só os outros
    # computadores (talvez de quem descobriu a senha antiga) caem.
    login_user(current_user._get_current_object())


def acao_redefinir_senha(usuario, nova):
    """Senha PROVISÓRIA (já validada) para quem esqueceu a sua."""
    usuario.definir_senha(nova)  # também derruba as sessões dela
    usuario.trocar_senha = True  # no próximo acesso, cria a própria
    db.session.commit()
    return (
        f"Senha provisória definida para '{usuario.login}'. "
        "No próximo acesso, a pessoa vai criar a própria senha."
    )


# ---------- React pronto, servido pelo Flask ----------
#
# As telas do sistema são todas em React (pasta frontend/). No
# desenvolvimento, o React roda no Vite (npm run dev, porta 5173).
# Para USAR o sistema, não precisa do Vite: "npm run build" gera os
# arquivos prontos em frontend/dist/, e o Flask os entrega aqui, em
# /app/... Um servidor só, uma porta só.

# As páginas antigas (feitas em Flask, com templates) foram
# aposentadas. Os endereços delas continuam funcionando e levam para a
# tela equivalente do React: um favorito antigo (como o /painel da
# TV) não quebra.
@app.get("/", defaults={"caminho": ""})
@app.get("/<any(pacientes, relatorio, painel, locais, usuarios, login):caminho>")
@app.get("/pacientes/novo", defaults={"caminho": "pacientes/novo"})
@app.get("/minha-senha", defaults={"caminho": "minha-senha"})
@app.get("/pacientes/editar/<int:id>", defaults={"caminho": "editar"})
def endereco_antigo(caminho, id=None):
    if caminho == "login":
        caminho = "pacientes"  # /login não existe no React: as telas pedem login sozinhas
    elif caminho == "editar":
        caminho = f"pacientes/{id}/editar"  # no React o id vem antes
    destino = "/app/" + caminho
    if request.query_string:  # mantém o ?q=... / ?dia=...
        destino += "?" + request.query_string.decode()
    return redirect(destino)


@app.get("/app/", defaults={"caminho": ""})
@app.get("/app/<path:caminho>")
def frontend_react(caminho):
    pasta = app.config["FRONTEND_DIST"]

    if not os.path.isfile(os.path.join(pasta, "index.html")):
        return (
            "O React ainda não foi gerado. Dentro de frontend/, rode: "
            "npm install (uma vez) e npm run build.",
            404,
            {"Content-Type": "text/plain; charset=utf-8"},
        )

    # Um arquivo que existe de verdade (JS, CSS, imagem)? Entrega ele.
    # safe_join recusa truques como /app/../../app.py (devolve None).
    arquivo = safe_join(pasta, caminho) if caminho else None
    if arquivo and os.path.isfile(arquivo):
        # Os arquivos de assets/ têm um código no nome (index-BBQzGiAg.js)
        # que muda a cada build: o navegador pode guardá-los por 1 ano.
        guardar_por = 365 * 24 * 3600 if caminho.startswith("assets/") else None
        return send_from_directory(pasta, caminho, max_age=guardar_por)

    # Qualquer outro endereço (/app/pacientes, /app/relatorio?dia=...)
    # é uma TELA do React, e não um arquivo. Entregamos sempre o
    # index.html, e o React Router decide o que desenhar. É isso que
    # faz o F5 e os links diretos funcionarem.
    resposta = send_from_directory(pasta, "index.html")
    # index.html nunca fica guardado: é ele que aponta para os assets
    # do build mais novo
    resposta.headers["Cache-Control"] = "no-cache"
    return resposta


# ---------- API JSON (usada pelo frontend em React) ----------
#
# O Flask responde com DADOS (JSON), e quem desenha a tela é o React.
#
# - Login: o cookie de sessão do Flask. O React vem do mesmo endereço
#   (/app/, ou o Vite no desenvolvimento), então o navegador manda o cookie.
# - CSRF: o React pega o código em /api/sessao e manda de volta no
#   cabeçalho X-CSRFToken de todo POST/PUT/DELETE (o Flask-WTF confere).
# - Erros: código HTTP + {"erro": "mensagem"}.

def usuario_json(usuario):
    return {
        "nome": usuario.nome,
        "login": usuario.login,
        "admin": usuario.admin,
        "trocar_senha": usuario.trocar_senha,
    }


def paciente_json(paciente, posicao=None):
    """Um paciente em formato de dicionário (vira JSON).

    Os horários e durações já vão FORMATADOS ("14:32", "15 min"):
    assim o React só mostra, e a formatação fica igual à do Flask.
    """
    return {
        "id": paciente.id,
        "nome": paciente.nome,
        "cpf": formatar_cpf(paciente.cpf),
        "telefone": paciente.telefone or "",
        "observacoes": paciente.observacoes or "",
        "prioridade": paciente.prioridade,
        "status": paciente.status,
        "local": paciente.local,
        "posicao": posicao,
        "chegada": formatar_hora(paciente.chegada),
        "chamado_em": formatar_hora(paciente.chamado_em),
        "esperando_ha": formatar_duracao(paciente.chegada),
        "esperou": formatar_duracao(paciente.chegada, paciente.chamado_em),
        "duracao": formatar_duracao(paciente.chamado_em, paciente.concluido_em),
        "encerrado_em": (
            paciente.concluido_em.strftime("%d/%m %H:%M") if paciente.concluido_em else None
        ),
        "foi_rechamado": paciente.foi_rechamado,
        "ultima_chamada": formatar_hora(paciente.ultima_chamada),
    }


def resposta_da_acao(resultado):
    """API: (deu_certo, mensagem) -> JSON. 409 = "não deu, por causa do
    estado atual" (ex.: fila vazia, paciente que já saiu do atendimento)."""
    deu_certo, mensagem = resultado
    if deu_certo:
        return jsonify(mensagem=mensagem)
    return jsonify(erro=mensagem), 409


@app.get("/api/sessao")
def api_sessao():
    """Quem está logado (ou null) + o código CSRF para os próximos POSTs.

    É a primeira coisa que o React pede ao abrir.
    """
    usuario = usuario_json(current_user) if current_user.is_authenticated else None
    return jsonify(usuario=usuario, csrf=generate_csrf())


@app.post("/api/login")
def api_login():
    dados = request.get_json(silent=True) or {}
    login_digitado = login_digitado_do(dados.get("login"))

    # Todas as regras de segurança ficam em autenticar() (bloqueio, tempo igual...)
    usuario, erro = autenticar(login_digitado, str(dados.get("senha", "")))
    if erro:
        return jsonify(erro=erro), 401

    login_user(usuario)
    return jsonify(usuario=usuario_json(usuario))


@app.post("/api/logout")
def api_logout():
    logout_user()
    return jsonify(mensagem="Você saiu do sistema.")


@app.get("/api/pacientes")
def api_pacientes():
    termo = request.args.get("q", "").strip()
    listas = listas_de_pacientes(termo)
    posicoes = listas["posicoes"]

    return jsonify(
        em_atendimento=[paciente_json(p) for p in listas["em_atendimento"]],
        fila=[paciente_json(p, posicoes[p.id]) for p in listas["fila"]],
        historico=[paciente_json(p) for p in listas["concluidos"]],
        # Fila COMPLETA (mesmo com busca): para ligar/desligar "Chamar próximo"
        total_na_fila=len(posicoes),
        locais=nomes_dos_locais_ativos(),
        ultimo_local=session.get("ultimo_local"),
    )


@app.post("/api/pacientes/chamar-proximo")
def api_chamar_proximo():
    dados = request.get_json(silent=True) or {}
    return resposta_da_acao(acao_chamar_proximo(str(dados.get("local", ""))))


# Uma rota para as três ações sobre um paciente em atendimento
ACOES_DE_ATENDIMENTO = {
    "concluir": acao_concluir,
    "chamar-de-novo": acao_chamar_de_novo,
    "nao-compareceu": acao_nao_compareceu,
}


@app.post("/api/pacientes/<int:id>/<acao>")
def api_acao_paciente(id, acao):
    if acao not in ACOES_DE_ATENDIMENTO:
        return jsonify(erro="Ação desconhecida."), 404

    paciente = db.session.get(Paciente, id)
    if paciente is None:
        return jsonify(erro="Paciente não encontrado."), 404

    return resposta_da_acao(ACOES_DE_ATENDIMENTO[acao](paciente))


# ---------- API: cadastro e edição de paciente ----------

def paciente_para_formulario(paciente):
    """Os dados CRUS que o formulário de edição precisa (data no formato
    AAAA-MM-DD do <input type="date">, e-mail...). paciente_json é para
    MOSTRAR; este é para EDITAR."""
    return {
        "id": paciente.id,
        "nome": paciente.nome,
        "nascimento": paciente.nascimento,
        "cpf": formatar_cpf(paciente.cpf),
        "prioridade": paciente.prioridade,
        "telefone": paciente.telefone or "",
        "email": paciente.email or "",
        "observacoes": paciente.observacoes or "",
        "status": paciente.status,
    }


def erros_de_validacao(erros):
    """422 = "entendi o pedido, mas os dados não passam na validação"."""
    return jsonify(erro="Confira os campos destacados.", erros=erros), 422


@app.get("/api/pacientes/prioridades")
def api_prioridades():
    # A lista vem do servidor: quem decide o que é válido é o Flask
    return jsonify(prioridades=PRIORIDADES)


@app.post("/api/pacientes")
def api_cadastrar_paciente():
    dados, erros = ler_formulario(request.get_json(silent=True) or {})
    if erros:
        return erros_de_validacao(erros)

    paciente = acao_cadastrar_paciente(dados)
    # 201 = "criado"
    return jsonify(
        mensagem=f"Paciente {paciente.nome} cadastrado com sucesso!",
        paciente=paciente_para_formulario(paciente),
    ), 201


@app.get("/api/pacientes/<int:id>")
def api_paciente(id):
    paciente = db.session.get(Paciente, id)
    if paciente is None:
        return jsonify(erro="Paciente não encontrado."), 404
    return jsonify(paciente=paciente_para_formulario(paciente))


# PUT = "substitua os dados deste paciente por estes"
@app.put("/api/pacientes/<int:id>")
def api_editar_paciente(id):
    paciente = db.session.get(Paciente, id)
    if paciente is None:
        return jsonify(erro="Paciente não encontrado."), 404

    dados, erros = ler_formulario(request.get_json(silent=True) or {}, paciente_id=id)
    if erros:
        return erros_de_validacao(erros)

    acao_editar_paciente(paciente, dados)
    return jsonify(
        mensagem=f"Dados de {paciente.nome} atualizados.",
        paciente=paciente_para_formulario(paciente),
    )


# DELETE = "apague este paciente". Mesmo endereço do GET e do PUT:
# na API, o MÉTODO diz o que fazer e o endereço diz com quem.
@app.delete("/api/pacientes/<int:id>")
def api_excluir_paciente(id):
    paciente = db.session.get(Paciente, id)
    if paciente is None:
        return jsonify(erro="Paciente não encontrado."), 404
    return jsonify(mensagem=acao_excluir_paciente(paciente))


# ---------- API: relatório ----------

@app.get("/api/relatorio")
def api_relatorio():
    """Os números do dia. O desenho do gráfico NÃO vai pronto: vão só
    os dados (hora, total) e o React calcula as barras. Os tempos vão
    formatados ("12 min"), como em paciente_json."""
    dia = dia_do_pedido()
    dados = relatorio_do_dia(dia)
    por_hora = dados["por_hora"]

    return jsonify(
        dia=dia.isoformat(),
        hoje=date.today().isoformat(),
        anterior=(dia - timedelta(days=1)).isoformat(),
        seguinte=(dia + timedelta(days=1)).isoformat(),
        chegaram=dados["chegaram"],
        atendidos=dados["atendidos"],
        nao_compareceram=dados["nao_compareceram"],
        espera_media=formatar_minutos(dados["espera_media"]),
        maior_espera=formatar_minutos(dados["maior_espera"]),
        duracao_media=formatar_minutos(dados["duracao_media"]),
        # Todas as horas do eixo, inclusive as com zero (o React não
        # precisa saber a regra do horário comercial)
        por_hora=[
            {"hora": hora, "total": por_hora.get(hora, 0)}
            for hora in (horas_do_grafico(por_hora) if por_hora else [])
        ],
        por_prioridade=[
            {**linha, "espera_media": formatar_minutos(linha["espera_media"])}
            for linha in dados["por_prioridade"]
        ],
        por_local=[
            {**linha, "duracao_media": formatar_minutos(linha["duracao_media"])}
            for linha in dados["por_local"]
        ],
    )


# ---------- API: minha senha ----------

@app.post("/api/minha-senha")
def api_minha_senha():
    dados = request.get_json(silent=True) or {}
    atual, nova, confirmacao = (
        str(dados.get(campo) or "") for campo in ("atual", "nova", "confirmacao")
    )

    erros = erros_da_troca_de_senha(atual, nova, confirmacao)
    if erros:
        return erros_de_validacao(erros)

    acao_trocar_minha_senha(nova)
    return jsonify(mensagem="Senha alterada.", usuario=usuario_json(current_user))


# ---------- API: locais (só administração) ----------

def local_json(local):
    return {"id": local.id, "nome": local.nome, "ativo": local.ativo}


@app.get("/api/locais")
@admin_obrigatorio
def api_locais():
    return jsonify(locais=[local_json(local) for local in lista_de_locais()])


@app.post("/api/locais")
@admin_obrigatorio
def api_adicionar_local():
    dados = request.get_json(silent=True) or {}
    nome, erro = validar_nome_de_local(dados.get("nome"))
    if erro:
        return erros_de_validacao({"nome": erro})
    return jsonify(mensagem=acao_adicionar_local(nome)), 201


@app.put("/api/locais/<int:id>")
@admin_obrigatorio
def api_renomear_local(id):
    local = db.session.get(Local, id)
    if local is None:
        return jsonify(erro="Local não encontrado."), 404

    nome, erro = validar_nome_de_local(
        (request.get_json(silent=True) or {}).get("nome"), local_id=local.id
    )
    if erro:
        return erros_de_validacao({"nome": erro})
    return jsonify(mensagem=acao_renomear_local(local, nome))


@app.post("/api/locais/<int:id>/alternar")
@admin_obrigatorio
def api_alternar_local(id):
    local = db.session.get(Local, id)
    if local is None:
        return jsonify(erro="Local não encontrado."), 404
    return resposta_da_acao(acao_alternar_local(local))


# ---------- API: usuários (só administração) ----------

def usuario_da_lista_json(usuario):
    return {
        **usuario_json(usuario),
        "id": usuario.id,
        "ativo": usuario.ativo,
        "papel": usuario.papel,
        # Para o React esconder os botões da própria linha
        "voce": usuario.id == current_user.id,
    }


@app.get("/api/usuarios")
@admin_obrigatorio
def api_usuarios():
    return jsonify(usuarios=[usuario_da_lista_json(u) for u in lista_de_usuarios()])


@app.post("/api/usuarios")
@admin_obrigatorio
def api_criar_usuario():
    dados = request.get_json(silent=True) or {}
    login = str(dados.get("login") or "").strip().lower()
    nome = str(dados.get("nome") or "").strip()
    senha = str(dados.get("senha") or "")
    admin = dados.get("admin") is True  # só o true de verdade vale

    erros = validar_novo_usuario(login, nome, senha)
    if erros:
        return erros_de_validacao(erros)

    return jsonify(mensagem=acao_criar_usuario(nome, login, senha, admin)), 201


@app.post("/api/usuarios/<int:id>/senha")
@admin_obrigatorio
def api_redefinir_senha(id):
    usuario = db.session.get(Usuario, id)
    if usuario is None:
        return jsonify(erro="Usuário não encontrado."), 404
    if usuario.id == current_user.id:
        # Para a própria senha existe "Minha senha" (que pede a atual)
        return jsonify(erro="Para a sua senha, use Minha senha."), 409

    nova = str((request.get_json(silent=True) or {}).get("nova") or "")
    erros = validar_senha(nova)
    if erros:
        return erros_de_validacao({"nova": erros[0]})

    return jsonify(mensagem=acao_redefinir_senha(usuario, nova))


@app.post("/api/usuarios/<int:id>/<acao>")
@admin_obrigatorio
def api_alterar_usuario(id, acao):
    if acao not in ("ativo", "admin"):
        return jsonify(erro="Ação desconhecida."), 404
    usuario = db.session.get(Usuario, id)
    if usuario is None:
        return jsonify(erro="Usuário não encontrado."), 404
    return resposta_da_acao(acao_alterar_usuario(usuario, acao))


if __name__ == "__main__":
    # A estrutura do banco agora é criada/atualizada com:
    #   flask --app app db upgrade
    app.run(debug=True)
