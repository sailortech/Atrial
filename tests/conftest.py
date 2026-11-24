"""Configuração compartilhada pelos testes.

O pytest lê este arquivo sozinho, antes dos testes. As "fixtures"
definidas aqui podem ser pedidas por qualquer teste só colocando
o nome delas como parâmetro: def test_algo(cliente): ...
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from flask import g
from flask.testing import FlaskClient
from werkzeug.security import generate_password_hash

# Banco em memória: some ao fim de cada teste e NUNCA toca no atrial.db.
# Precisa vir antes do "import app", que é quando a configuração é lida.
os.environ["DATABASE_URL"] = "sqlite://"

# Chave fixa nos testes: assim eles não criam o arquivo instance/secret_key
os.environ["SECRET_KEY"] = "chave-so-para-testes"

# Deixa o "import app" funcionar a partir da pasta tests/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import app as flask_app, db, Local, Paciente, Usuario  # noqa: E402

LOCAIS_INICIAIS = ["Triagem", "Consultório 1", "Consultório 2", "Consultório 3"]


class ClienteDeTeste(FlaskClient):
    """Navegador de mentira que começa cada requisição "do zero".

    Por quê: a fixture app deixa o contexto da aplicação aberto durante
    o teste todo, e o Flask então REAPROVEITA esse contexto (e o g) em
    todas as requisições. O Flask-Login guarda o usuário da requisição
    em g._login_user; sem limpar, o navegador anônimo "herdaria" o login
    feito por outro navegador no mesmo teste, e um teste de segurança
    poderia passar quando deveria falhar.
    No servidor de verdade cada requisição tem seu próprio g, então
    isso só acontece aqui nos testes.
    """

    def open(self, *args, **kwargs):
        g.pop("_login_user", None)
        return super().open(*args, **kwargs)


flask_app.test_client_class = ClienteDeTeste


@pytest.fixture
def app():
    """App com um banco vazio, criado do zero para cada teste."""
    flask_app.config["TESTING"] = True

    # A maioria dos testes confere OUTRAS regras (fila, cadastro...),
    # então desligamos o CSRF para não ter que pegar o código toda vez.
    # Ele é testado ligado em test_csrf.py (fixture csrf_ligado).
    flask_app.config["WTF_CSRF_ENABLED"] = False

    with flask_app.app_context():
        db.create_all()

        # Os mesmos locais que a migration cria no banco de verdade
        db.session.add_all(Local(nome=nome) for nome in LOCAIS_INICIAIS)
        db.session.commit()

        yield flask_app      # aqui o teste roda
        db.session.remove()  # e depois limpamos tudo
        db.drop_all()


SENHA_TESTE = "senha-de-teste-123"

# O hash da senha é lento DE PROPÓSITO (~0,3s), para dificultar quem
# tenta adivinhar senhas. Nos testes, calculamos uma vez só e reaproveitamos.
HASH_TESTE = generate_password_hash(SENHA_TESTE)


@pytest.fixture
def usuario(app):
    """Uma recepcionista cadastrada: login 'ana', senha SENHA_TESTE."""
    usuario = Usuario(nome="Ana Recepção", login="ana", senha_hash=HASH_TESTE)
    db.session.add(usuario)
    db.session.commit()
    return usuario


@pytest.fixture
def cliente_anonimo(app):
    """Um "navegador de mentira" de quem ainda NÃO entrou no sistema."""
    return app.test_client()


@pytest.fixture
def admin(app):
    """Uma administradora: login 'bia', senha SENHA_TESTE."""
    admin = Usuario(nome="Bia Admin", login="bia", senha_hash=HASH_TESTE, admin=True)
    db.session.add(admin)
    db.session.commit()
    return admin


def navegador_logado(app, usuario):
    cliente = app.test_client()

    # Atalho: em vez de preencher o formulário (e esperar o hash),
    # escrevemos direto na sessão o que o login_user() escreveria.
    # O formulário de verdade é testado em test_login.py.
    with cliente.session_transaction() as sessao:
        sessao["_user_id"] = str(usuario.id)
        sessao["_fresh"] = True

    return cliente


@pytest.fixture
def cliente(app, usuario):
    """Navegador logado como RECEPÇÃO. É o que a maioria dos testes usa:
    cada teste tem só o acesso de que precisa."""
    return navegador_logado(app, usuario)


@pytest.fixture
def cliente_admin(app, admin):
    """Navegador logado como ADMINISTRAÇÃO."""
    return navegador_logado(app, admin)


# CPFs válidos (passam na conta dos dígitos verificadores)
CPFS_VALIDOS = ["52998224725", "11144477735", "39053344705", "15350946056"]


@pytest.fixture
def criar_paciente(app):
    """Fábrica de pacientes: criar_paciente("Ana", prioridade="Urgente").

    Preenche o que o teste não informar com valores padrão.
    """
    contador = iter(CPFS_VALIDOS)

    def criar(nome, chegou_ha_min=0, **campos):
        dados = {
            "nascimento": "1990-05-10",
            "cpf": next(contador),
            "prioridade": "Normal",
            "status": "Aguardando",
            "chegada": datetime.now() - timedelta(minutes=chegou_ha_min),
        }
        dados.update(campos)

        # Quem já foi chamado tem a última chamada igual à primeira
        # (a não ser que o teste diga outra coisa) — igual à migration
        # faz com os pacientes antigos do banco.
        dados.setdefault("ultima_chamada", dados.get("chamado_em"))

        paciente = Paciente(nome=nome, **dados)
        db.session.add(paciente)
        db.session.commit()
        return paciente

    return criar
