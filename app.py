from flask import Flask, render_template, request, redirect, url_for

from flask_sqlalchemy import SQLAlchemy


app = Flask(__name__)

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


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/pacientes/novo", methods=["GET", "POST"])
def cadastro_paciente():

    if request.method == "POST":

        nome = request.form["nome"]
        nascimento = request.form["nascimento"]
        cpf = request.form["cpf"]
        prioridade = request.form["prioridade"]
        telefone = request.form["telefone"]
        email = request.form["email"]
        observacoes = request.form["observacoes"]

        paciente = Paciente(
            nome=nome,
            nascimento=nascimento,
            cpf=cpf,
            prioridade=prioridade,
            telefone=telefone,
            email=email,
            observacoes=observacoes,
            status="Aguardando"
        )

        db.session.add(paciente)
        db.session.commit()

        print("Paciente cadastrado com sucesso!")

        return redirect(url_for("pacientes"))

    return render_template("cadastros.html")


@app.route("/pacientes")
def pacientes():

    pacientes = Paciente.query.order_by(
        db.case(
            (Paciente.prioridade == "Urgente", 1),
            (Paciente.prioridade == "Preferencial", 2),
            (Paciente.prioridade == "Normal", 3)
        ),
        Paciente.id
    ).all()

    return render_template(
        "pacientes.html",
        pacientes=pacientes
    )


@app.route("/pacientes/editar/<int:id>", methods=["GET", "POST"])
def editar_paciente(id):

    paciente = Paciente.query.get_or_404(id)

    if request.method == "POST":

        paciente.nome = request.form["nome"]
        paciente.nascimento = request.form["nascimento"]
        paciente.cpf = request.form["cpf"]
        paciente.prioridade = request.form["prioridade"]
        paciente.telefone = request.form["telefone"]
        paciente.email = request.form["email"]
        paciente.observacoes = request.form["observacoes"]

        db.session.commit()

        return redirect(url_for("pacientes"))

    return render_template(
        "editar_paciente.html",
        paciente=paciente
    )


@app.route("/pacientes/chamar-proximo", methods=["POST"])
def chamar_proximo():

    paciente = Paciente.query.filter_by(
        status="Aguardando"
    ).order_by(
        db.case(
            (Paciente.prioridade == "Urgente", 1),
            (Paciente.prioridade == "Preferencial", 2),
            (Paciente.prioridade == "Normal", 3)
        ),
        Paciente.id
    ).first()

    if paciente:
        paciente.status = "Em atendimento"
        db.session.commit()

    return redirect(url_for("pacientes"))


@app.route("/pacientes/finalizar/<int:id>", methods=["POST"])
def finalizar_atendimento(id):
    paciente = Paciente.query.get_or_404(id)

    if paciente.status == "Em atendimento":
        paciente.status = "Concluído"
        db.session.commit()

    return redirect(url_for("pacientes"))


@app.route("/pacientes/excluir/<int:id>", methods=["POST"])
def excluir_paciente(id):
    paciente = Paciente.query.get_or_404(id)

    db.session.delete(paciente)
    db.session.commit()

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
