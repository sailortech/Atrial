"""Testes do login: quem entra, quem não entra e o que fica protegido."""

import pytest

from app import PAGINAS_PUBLICAS, Paciente, Usuario, app, endereco_seguro
from conftest import SENHA_TESTE


# ---------- Páginas protegidas ----------

@pytest.mark.parametrize("pagina", ["/", "/pacientes", "/pacientes/novo"])
def test_sem_login_vai_para_a_tela_de_login(cliente_anonimo, pagina):
    resposta = cliente_anonimo.get(pagina)

    assert resposta.status_code == 302
    assert resposta.location.startswith("/login")


def test_sem_login_nao_consegue_excluir(cliente_anonimo, criar_paciente):
    paciente = criar_paciente("Bruno")

    cliente_anonimo.post(f"/pacientes/excluir/{paciente.id}")

    assert Paciente.query.count() == 1  # continua lá


def test_sem_login_nao_consegue_chamar(cliente_anonimo, criar_paciente):
    criar_paciente("Bruno")

    cliente_anonimo.post("/pacientes/chamar-proximo")

    assert Paciente.query.one().status == "Aguardando"


@pytest.mark.parametrize("pagina", ["/painel", "/painel/dados", "/login"])
def test_paginas_publicas_abrem_sem_login(cliente_anonimo, pagina):
    assert cliente_anonimo.get(pagina).status_code == 200


def test_todas_as_rotas_novas_nascem_protegidas(cliente_anonimo):
    """Rede de segurança: percorre TODAS as rotas do app.
    Se alguém criar uma rota e ela abrir sem login, este teste avisa."""
    # Escrita AQUI de propósito (e comparada com a do app): tornar uma
    # página pública exige mexer nos dois lugares, ou seja, uma decisão.
    publicas = {"login", "static", "painel", "painel_dados", "api_sessao", "api_login"}
    assert PAGINAS_PUBLICAS == publicas

    for regra in app.url_map.iter_rules():
        if regra.endpoint in publicas:
            continue
        # Troca <int:id> e <acao> por valores para montar um endereço de verdade
        endereco = regra.rule.replace("<int:id>", "1").replace("<acao>", "concluir")
        metodo = "post" if "POST" in regra.methods else "get"

        resposta = getattr(cliente_anonimo, metodo)(endereco)

        if endereco.startswith("/api/"):
            # API: responde 401 em JSON (o React mostra a tela de login)
            assert resposta.status_code == 401, f"{endereco} abriu sem login!"
        else:
            assert resposta.status_code == 302, f"{endereco} abriu sem login!"
            assert resposta.location.startswith("/login")


# ---------- Entrar e sair ----------

def test_login_certo_entra(cliente_anonimo, usuario):
    resposta = cliente_anonimo.post(
        "/login", data={"login": "ana", "senha": SENHA_TESTE},
        follow_redirects=True,
    )

    assert "Olá, Ana Recepção!" in resposta.get_data(as_text=True)
    assert cliente_anonimo.get("/pacientes").status_code == 200


def test_login_ignora_maiusculas_e_espacos_no_usuario(cliente_anonimo, usuario):
    cliente_anonimo.post("/login", data={"login": "  ANA ", "senha": SENHA_TESTE})

    assert cliente_anonimo.get("/pacientes").status_code == 200


@pytest.mark.parametrize("login, senha", [
    ("ana", "senha-errada"),
    ("ninguem", SENHA_TESTE),
    ("ana", ""),
])
def test_login_errado_nao_entra(cliente_anonimo, usuario, login, senha):
    resposta = cliente_anonimo.post("/login", data={"login": login, "senha": senha})

    # Mesma mensagem nos dois casos: não revela quais usuários existem
    assert "Usuário ou senha incorretos." in resposta.get_data(as_text=True)
    assert cliente_anonimo.get("/pacientes").status_code == 302


def test_sair_bloqueia_de_novo(cliente):
    cliente.post("/logout")

    assert cliente.get("/pacientes").status_code == 302


def test_depois_do_login_volta_para_a_pagina_pedida(cliente_anonimo, usuario):
    pedido = cliente_anonimo.get("/pacientes?q=ana")

    resposta = cliente_anonimo.post(
        pedido.location,  # /login?proxima=/pacientes?q=ana
        data={"login": "ana", "senha": SENHA_TESTE},
    )

    assert resposta.location == "/pacientes?q=ana"


def test_pagina_sem_busca_volta_sem_interrogacao(cliente_anonimo, usuario):
    pedido = cliente_anonimo.get("/pacientes/novo")

    resposta = cliente_anonimo.post(
        pedido.location, data={"login": "ana", "senha": SENHA_TESTE}
    )

    assert resposta.location == "/pacientes/novo"


def test_login_nao_redireciona_para_outro_site(cliente_anonimo, usuario):
    resposta = cliente_anonimo.post(
        "/login?proxima=https://site-falso.com",
        data={"login": "ana", "senha": SENHA_TESTE},
    )

    assert resposta.location == "/pacientes"


@pytest.mark.parametrize("endereco, seguro", [
    ("/pacientes", True),
    ("/pacientes?q=ana", True),
    ("https://site-falso.com", False),
    ("//site-falso.com", False),
    ("/\\site-falso.com", False),
    ("", False),
])
def test_endereco_seguro(endereco, seguro):
    assert endereco_seguro(endereco) == seguro


# ---------- Senha ----------

def test_senha_nao_e_guardada_como_texto(usuario):
    assert SENHA_TESTE not in usuario.senha_hash
    assert usuario.confere_senha(SENHA_TESTE)
    assert not usuario.confere_senha("outra")


def test_comando_criar_usuario(app):
    resultado = app.test_cli_runner().invoke(
        args=["criar-usuario", "Maria", "--nome", "Maria Souza", "--senha", "12345678"]
    )

    assert "criado" in resultado.output
    maria = Usuario.query.filter_by(login="maria").one()  # login em minúsculas
    assert maria.confere_senha("12345678")


def test_comando_recusa_senha_curta(app):
    resultado = app.test_cli_runner().invoke(
        args=["criar-usuario", "maria", "--nome", "Maria", "--senha", "123"]
    )

    assert resultado.exit_code != 0
    assert Usuario.query.count() == 0
