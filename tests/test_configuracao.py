"""Testes da configuração: de onde vem a SECRET_KEY."""

from app import app, carregar_chave_secreta


def test_cria_uma_chave_aleatoria_na_primeira_vez(tmp_path, monkeypatch):
    # tmp_path: pasta temporária que o pytest cria (e apaga) para o teste
    # monkeypatch: muda o ambiente só durante este teste
    monkeypatch.delenv("SECRET_KEY", raising=False)

    chave = carregar_chave_secreta(tmp_path)

    assert len(chave) == 64  # 32 bytes em hexadecimal
    assert (tmp_path / "secret_key").read_text() == chave


def test_reaproveita_a_chave_ja_criada(tmp_path, monkeypatch):
    """Se a chave mudasse a cada reinício, todo mundo seria deslogado."""
    monkeypatch.delenv("SECRET_KEY", raising=False)

    primeira = carregar_chave_secreta(tmp_path)
    segunda = carregar_chave_secreta(tmp_path)

    assert primeira == segunda


def test_pastas_diferentes_ganham_chaves_diferentes(tmp_path, monkeypatch):
    """Cada instalação tem a sua: ninguém compartilha a mesma chave."""
    monkeypatch.delenv("SECRET_KEY", raising=False)

    assert carregar_chave_secreta(tmp_path / "a") != carregar_chave_secreta(tmp_path / "b")


def test_variavel_de_ambiente_tem_prioridade(tmp_path, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "chave-do-servidor")

    assert carregar_chave_secreta(tmp_path) == "chave-do-servidor"
    assert not (tmp_path / "secret_key").exists()  # nem criou o arquivo


def test_chave_antiga_de_desenvolvimento_nao_e_mais_usada():
    assert app.config["SECRET_KEY"] != "chave-de-desenvolvimento"


def test_cookie_de_login_protegido():
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    # HttpOnly: o JavaScript da página não consegue ler o cookie
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
