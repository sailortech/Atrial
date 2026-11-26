"""Testes do React pronto servido pelo Flask em /app/...

Não dependem de rodar "npm run build": cada teste monta uma pasta
dist/ de mentira, com um index.html e um asset pequenos.
"""

import pytest

from app import app as flask_app


@pytest.fixture
def dist(app, tmp_path):
    """Uma pasta dist/ falsa (tmp_path = pasta temporária do pytest)."""
    (tmp_path / "index.html").write_text("<div id=root>REACT</div>", encoding="utf-8")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "index-abc123.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "favicon.svg").write_text("<svg/>", encoding="utf-8")

    anterior = flask_app.config["FRONTEND_DIST"]
    flask_app.config["FRONTEND_DIST"] = str(tmp_path)
    yield tmp_path
    flask_app.config["FRONTEND_DIST"] = anterior


@pytest.mark.parametrize("endereco", [
    "/app/", "/app/pacientes", "/app/pacientes/7/editar", "/app/relatorio?dia=2026-11-25",
])
def test_telas_do_react_recebem_o_index(cliente_anonimo, dist, endereco):
    """Sem login mesmo: quem mostra a tela de login é o React."""
    resposta = cliente_anonimo.get(endereco)

    assert resposta.status_code == 200
    assert "REACT" in resposta.get_data(as_text=True)
    assert resposta.headers["Cache-Control"] == "no-cache"


def test_assets_sao_entregues_e_guardados_por_muito_tempo(cliente_anonimo, dist):
    resposta = cliente_anonimo.get("/app/assets/index-abc123.js")

    assert resposta.status_code == 200
    assert resposta.get_data(as_text=True) == "console.log(1)"
    assert "max-age=31536000" in resposta.headers["Cache-Control"]


def test_outros_arquivos_sem_cache_longo(cliente_anonimo, dist):
    resposta = cliente_anonimo.get("/app/favicon.svg")

    assert resposta.status_code == 200
    assert "max-age=31536000" not in resposta.headers.get("Cache-Control", "")


@pytest.mark.parametrize("endereco", ["/app/../app.py", "/app/..%2F..%2Fbackend%2Fapp.py"])
def test_nao_deixa_sair_da_pasta(cliente_anonimo, dist, endereco):
    resposta = cliente_anonimo.get(endereco)

    # Ou cai no index.html do React, ou dá 404, mas nunca entrega o código
    assert "SQLAlchemy" not in resposta.get_data(as_text=True)


def test_sem_build_explica_o_que_fazer(cliente_anonimo, app, tmp_path):
    flask_app.config["FRONTEND_DIST"], anterior = str(tmp_path / "nao-existe"), flask_app.config["FRONTEND_DIST"]
    try:
        resposta = cliente_anonimo.get("/app/pacientes")
    finally:
        flask_app.config["FRONTEND_DIST"] = anterior

    assert resposta.status_code == 404
    assert "npm run build" in resposta.get_data(as_text=True)


def test_api_continua_exigindo_login(cliente_anonimo, dist):
    # Servir o React sem login não abre os DADOS: a API continua fechada
    assert cliente_anonimo.get("/api/pacientes").status_code == 401
