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
from werkzeug.security import generate_password_hash

# Banco em memória: some ao fim de cada teste e NUNCA toca no atrial.db.
# Precisa vir antes do "import app", que é quando a configuração é lida.
os.environ["DATABASE_URL"] = "sqlite://"

# Deixa o "import app" funcionar a partir da pasta tests/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import app as flask_app, db, Paciente, Usuario  # noqa: E402


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
def cliente(app, usuario):
    """Navegador de mentira já logado. É o que a maioria dos testes usa."""
    cliente = app.test_client()

    # Atalho: em vez de preencher o formulário (e esperar o hash),
    # escrevemos direto na sessão o que o login_user() escreveria.
    # O formulário de verdade é testado em test_login.py.
    with cliente.session_transaction() as sessao:
        sessao["_user_id"] = str(usuario.id)
        sessao["_fresh"] = True

    return cliente


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

        paciente = Paciente(nome=nome, **dados)
        db.session.add(paciente)
        db.session.commit()
        return paciente

    return criar
