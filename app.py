import os
import re
import unicodedata
from datetime import date, datetime

from flask import Flask, render_template, request, redirect, url_for, flash

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import validates
from flask_migrate import Migrate


app = Flask(__name__)

# Chave usada para "assinar" a sessão do usuário (o flash depende dela).
# Em produção, defina a variável de ambiente SECRET_KEY com um valor secreto.
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "chave-de-desenvolvimento")

# Configuração do banco de dados
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///atrial.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# Migrations: cuidam das mudanças na estrutura do banco
# (ex.: adicionar uma coluna) sem perder os dados.
migrate = Migrate(app, db)


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


PRIORIDADES = ["Normal", "Preferencial", "Urgente"]

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
    minutos = int((fim - inicio).total_seconds() // 60)

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

    paciente = buscar_por_status("Aguardando").first()

    if paciente:
        paciente.status = "Em atendimento"
        paciente.chamado_em = datetime.now()
        db.session.commit()
        flash(f"Chamando {paciente.nome} ({paciente.prioridade}).", "sucesso")
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
