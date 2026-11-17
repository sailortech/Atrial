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

# Banco em memória: some ao fim de cada teste e NUNCA toca no atrial.db.
# Precisa vir antes do "import app", que é quando a configuração é lida.
os.environ["DATABASE_URL"] = "sqlite://"

# Deixa o "import app" funcionar a partir da pasta tests/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import app as flask_app, db, Paciente  # noqa: E402


@pytest.fixture
def app():
    """App com um banco vazio, criado do zero para cada teste."""
    flask_app.config["TESTING"] = True

    with flask_app.app_context():
        db.create_all()
        yield flask_app      # aqui o teste roda
        db.session.remove()  # e depois limpamos tudo
        db.drop_all()


@pytest.fixture
def cliente(app):
    """Um "navegador de mentira" para fazer GET/POST nas rotas."""
    return app.test_client()


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
