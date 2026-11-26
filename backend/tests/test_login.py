"""Testes do login: quem entra, quem não entra e o que fica protegido."""

import pytest

from app import PAGINAS_PUBLICAS, Paciente, Usuario, app
from conftest import SENHA_TESTE


def entrar(navegador, login="ana", senha=SENHA_TESTE):
    return navegador.post("/api/login", json={"login": login, "senha": senha})


def esta_logado(navegador):
    return navegador.get("/api/sessao").get_json()["usuario"] is not None


# ---------- O que fica protegido ----------

def test_sem_login_nao_consegue_excluir(cliente_anonimo, criar_paciente):
    paciente = criar_paciente("Bruno")

    resposta = cliente_anonimo.delete(f"/api/pacientes/{paciente.id}")

    assert resposta.status_code == 401
    assert Paciente.query.count() == 1  # continua lá


def test_sem_login_nao_consegue_chamar(cliente_anonimo, criar_paciente):
    criar_paciente("Bruno")

    cliente_anonimo.post("/api/pacientes/chamar-proximo", json={"local": "Triagem"})

    assert Paciente.query.one().status == "Aguardando"


@pytest.mark.parametrize("endereco", ["/painel/dados", "/api/sessao"])
def test_enderecos_publicos_abrem_sem_login(cliente_anonimo, endereco):
    assert cliente_anonimo.get(endereco).status_code == 200


def test_todas_as_rotas_novas_nascem_protegidas(cliente_anonimo):
    """Rede de segurança: percorre TODAS as rotas do app.
    Se alguém criar uma rota e ela abrir sem login, este teste avisa."""
    # Escrita AQUI de propósito (e comparada com a do app): tornar uma
    # rota pública exige mexer nos dois lugares, ou seja, uma decisão.
    publicas = {
        "painel_dados", "api_sessao", "api_login",
        # Só os arquivos do React (sem dados); a API continua fechada.
        # Ver test_frontend.py::test_api_continua_exigindo_login
        "frontend_react",
        # Só redirecionam para /app/ (ver test_frontend.py)
        "endereco_antigo",
    }
    assert PAGINAS_PUBLICAS == publicas

    testadas = 0
    for regra in app.url_map.iter_rules():
        if regra.endpoint in publicas or regra.endpoint == "static":
            continue
        # Troca <int:id> e <acao> por valores para montar um endereço de verdade
        endereco = regra.rule.replace("<int:id>", "1").replace("<acao>", "concluir")

        for metodo in regra.methods - {"HEAD", "OPTIONS"}:
            resposta = cliente_anonimo.open(endereco, method=metodo)
            # 401 em JSON: o React mostra a tela de login
            assert resposta.status_code == 401, f"{metodo} {endereco} abriu sem login!"
            testadas += 1

    assert testadas > 15  # o teste percorreu mesmo as rotas da API (eram 19)


# ---------- Entrar e sair ----------

def test_login_certo_entra(cliente_anonimo, usuario):
    resposta = entrar(cliente_anonimo)

    assert resposta.get_json()["usuario"]["nome"] == "Ana Recepção"
    assert cliente_anonimo.get("/api/pacientes").status_code == 200


def test_login_ignora_maiusculas_e_espacos_no_usuario(cliente_anonimo, usuario):
    entrar(cliente_anonimo, login="  ANA ")

    assert esta_logado(cliente_anonimo)


@pytest.mark.parametrize("login, senha", [
    ("ana", "senha-errada"),
    ("ninguem", SENHA_TESTE),
    ("ana", ""),
])
def test_login_errado_nao_entra(cliente_anonimo, usuario, login, senha):
    resposta = entrar(cliente_anonimo, login=login, senha=senha)

    assert resposta.status_code == 401
    # Mesma mensagem nos dois casos: não revela quais usuários existem
    assert resposta.get_json()["erro"] == "Usuário ou senha incorretos."
    assert not esta_logado(cliente_anonimo)


def test_sair_bloqueia_de_novo(cliente):
    cliente.post("/api/logout")

    assert cliente.get("/api/pacientes").status_code == 401


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
