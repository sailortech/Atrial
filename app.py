import os
import re
from datetime import date

from flask import Flask, render_template, request, redirect, url_for, flash

from flask_sqlalchemy import SQLAlchemy


app = Flask(__name__)

# Chave usada para "assinar" a sessão do usuário (o flash depende dela).
# Em produção, defina a variável de ambiente SECRET_KEY com um valor secreto.
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "chave-de-desenvolvimento")

# Configuração do banco de dados
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///atrial.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


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

        paciente = Paciente(**dados, status="Aguardando")

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


@app.route("/pacientes")
def pacientes():

    em_atendimento = buscar_por_status("Em atendimento").all()
    fila = buscar_por_status("Aguardando").all()

    # Histórico: os concluídos mais recentes primeiro
    concluidos = Paciente.query.filter_by(
        status="Concluído"
    ).order_by(
        Paciente.id.desc()
    ).all()

    return render_template(
        "pacientes.html",
        em_atendimento=em_atendimento,
        fila=fila,
        concluidos=concluidos
    )


@app.route("/pacientes/editar/<int:id>", methods=["GET", "POST"])
def editar_paciente(id):

    paciente = Paciente.query.get_or_404(id)

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
        db.session.commit()
        flash(f"Chamando {paciente.nome} ({paciente.prioridade}).", "sucesso")
    else:
        flash("Não há pacientes aguardando na fila.", "erro")

    return redirect(url_for("pacientes"))


@app.route("/pacientes/finalizar/<int:id>", methods=["POST"])
def finalizar_atendimento(id):
    paciente = Paciente.query.get_or_404(id)

    if paciente.status == "Em atendimento":
        paciente.status = "Concluído"
        db.session.commit()
        flash(f"Atendimento de {paciente.nome} concluído.", "sucesso")

    return redirect(url_for("pacientes"))


@app.route("/pacientes/excluir/<int:id>", methods=["POST"])
def excluir_paciente(id):
    paciente = Paciente.query.get_or_404(id)

    # Guarda o nome antes: depois de excluído, o objeto não pode mais ser lido
    nome = paciente.nome

    db.session.delete(paciente)
    db.session.commit()

    flash(f"Paciente {nome} excluído.", "sucesso")

    return redirect(url_for("pacientes"))


if __name__ == "__main__":

    with app.app_context():

        db.create_all()

        # Atualiza bancos antigos que ainda não possuem a coluna status
        try:
            db.session.execute(
                db.text(
                    "ALTER TABLE paciente "
                    "ADD COLUMN status VARCHAR(20) "
                    "NOT NULL DEFAULT 'Aguardando'"
                )
            )

            db.session.commit()

            print("Coluna status adicionada ao banco.")

        except Exception:
            db.session.rollback()

    app.run(debug=True)
