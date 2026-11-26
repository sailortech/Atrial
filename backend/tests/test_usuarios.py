"""Testes de papéis (recepção x administração) e da página Usuários."""

import pytest

from app import Local, Usuario, app as flask_app, db
from conftest import SENHA_TESTE, navegador_logado

# Rotas que SÓ a administração pode usar: (método, endereço)
ROTAS_DE_ADMIN = [
    ("get", "/locais"),
    ("post", "/locais"),
    ("post", "/locais/1/alternar"),
    ("get", "/usuarios"),
    ("post", "/usuarios"),
    ("post", "/usuarios/1/ativo"),
    ("post", "/usuarios/1/admin"),
    ("get", "/usuarios/1/senha"),
    ("post", "/usuarios/1/senha"),
]

# As mesmas proteções na API do React (lá a resposta é JSON 403)
ROTAS_DE_ADMIN_API = [
    ("get", "/api/locais"),
    ("post", "/api/locais"),
    ("post", "/api/locais/1/alternar"),
    ("get", "/api/usuarios"),
    ("post", "/api/usuarios"),
    ("post", "/api/usuarios/1/ativo"),
    ("post", "/api/usuarios/1/senha"),
]


def usuario(login):
    return Usuario.query.filter_by(login=login).one()


# ---------- Recepção x administração ----------

@pytest.mark.parametrize("metodo, endereco", ROTAS_DE_ADMIN)
def test_recepcao_nao_entra_nas_paginas_de_admin(cliente, metodo, endereco):
    resposta = getattr(cliente, metodo)(endereco, data={"nome": "X", "login": "xyz"})

    assert resposta.status_code == 302
    assert resposta.location == "/pacientes"


@pytest.mark.parametrize("metodo, endereco", ROTAS_DE_ADMIN_API)
def test_recepcao_nao_usa_a_api_de_admin(cliente, metodo, endereco):
    resposta = getattr(cliente, metodo)(endereco, json={"nome": "Invasor", "login": "invasor", "senha": "12345678", "admin": True})

    assert resposta.status_code == 403
    assert "administração" in resposta.get_json()["erro"]
    assert Local.query.filter_by(nome="Invasor").first() is None
    assert Usuario.query.filter_by(login="invasor").first() is None


def test_recepcao_nao_consegue_mudar_nada(cliente, admin):
    cliente.post("/locais", data={"nome": "Invasor"})
    cliente.post("/locais/1/alternar")
    cliente.post("/usuarios", data={"nome": "X", "login": "hacker", "senha": "12345678", "admin": "sim"})
    cliente.post(f"/usuarios/{admin.id}/ativo")

    assert Local.query.filter_by(nome="Invasor").first() is None
    assert db.session.get(Local, 1).ativo
    assert Usuario.query.filter_by(login="hacker").first() is None
    assert usuario("bia").ativo


def test_menu_da_recepcao_nao_mostra_paginas_de_admin(cliente):
    html = cliente.get("/pacientes").get_data(as_text=True)

    assert 'href="/usuarios"' not in html and 'href="/locais"' not in html


def test_menu_da_administracao_mostra_tudo(cliente_admin):
    html = cliente_admin.get("/pacientes").get_data(as_text=True)

    assert 'href="/usuarios"' in html and 'href="/locais"' in html


def test_toda_rota_de_admin_esta_na_lista():
    """Rede de segurança: o decorador @admin_obrigatorio deixa uma
    etiqueta (so_admin) em cada rota. Se alguém criar uma rota de admin
    e não colocar em ROTAS_DE_ADMIN acima, este teste avisa."""
    so_admin = {
        endpoint
        for endpoint, funcao in flask_app.view_functions.items()
        if getattr(funcao, "so_admin", False)
    }

    # Descobre qual rota (endpoint) atende cada endereço da lista
    mapa = flask_app.url_map.bind("localhost")
    testadas = {
        mapa.match(endereco, method=metodo.upper())[0]
        for metodo, endereco in ROTAS_DE_ADMIN + ROTAS_DE_ADMIN_API
    }

    assert so_admin, "nenhuma rota com a etiqueta? o decorador mudou?"
    assert so_admin == testadas


# ---------- Criar usuário pela página ----------

def test_admin_cria_usuario_da_recepcao(cliente_admin):
    cliente_admin.post("/usuarios", data={
        "nome": "Carla Dias", "login": "Carla.Dias", "senha": "senha-boa-123",
    })

    carla = usuario("carla.dias")  # login sempre em minúsculas
    assert not carla.admin and carla.ativo
    assert carla.confere_senha("senha-boa-123")
    assert "senha-boa-123" not in carla.senha_hash


def test_admin_cria_outro_admin(cliente_admin):
    cliente_admin.post("/usuarios", data={
        "nome": "Davi", "login": "davi", "senha": "senha-boa-123", "admin": "sim",
    })

    assert usuario("davi").admin


@pytest.mark.parametrize("dados, erro", [
    ({"nome": "", "login": "novo", "senha": "senha-boa-123"}, "Informe o nome"),
    ({"nome": "X", "login": "ab", "senha": "senha-boa-123"}, "de 3 a 50 caracteres"),
    ({"nome": "X", "login": "joão", "senha": "senha-boa-123"}, "letras sem acento"),
    ({"nome": "X", "login": "com espaço", "senha": "senha-boa-123"}, "letras sem acento"),
    ({"nome": "X", "login": "bia", "senha": "senha-boa-123"}, "Já existe o usuário"),
    ({"nome": "X", "login": "novo", "senha": "curta"}, "pelo menos 8"),
])
def test_criar_usuario_invalido(cliente_admin, dados, erro):
    resposta = cliente_admin.post("/usuarios", data=dados)

    assert erro in resposta.get_data(as_text=True)
    assert Usuario.query.count() == 1  # só a própria bia


def test_erro_devolve_o_formulario_sem_a_senha(cliente_admin):
    resposta = cliente_admin.post("/usuarios", data={
        "nome": "Carla", "login": "ca", "senha": "senha-secreta-999",
    })
    html = resposta.get_data(as_text=True)

    assert 'value="Carla"' in html               # o nome volta preenchido
    assert "senha-secreta-999" not in html       # a senha, não


# ---------- Desativar ----------

def test_desativado_nao_consegue_entrar(cliente_admin, usuario, cliente_anonimo):
    cliente_admin.post(f"/usuarios/{usuario.id}/ativo")

    resposta = cliente_anonimo.post("/login", data={"login": "ana", "senha": SENHA_TESTE})

    assert "foi desativado" in resposta.get_data(as_text=True)
    assert cliente_anonimo.get("/pacientes").status_code == 302


def test_desativado_e_posto_para_fora_na_hora(cliente_admin, usuario, cliente):
    """A Ana estava com o sistema aberto quando foi desativada."""
    assert cliente.get("/pacientes").status_code == 200

    cliente_admin.post(f"/usuarios/{usuario.id}/ativo")

    assert cliente.get("/pacientes").status_code == 302  # foi para o login


def test_senha_errada_de_desativado_nao_revela_nada(cliente_admin, usuario, cliente_anonimo):
    cliente_admin.post(f"/usuarios/{usuario.id}/ativo")

    resposta = cliente_anonimo.post("/login", data={"login": "ana", "senha": "errada"})

    html = resposta.get_data(as_text=True)
    assert "Usuário ou senha incorretos" in html
    assert "desativado" not in html


def test_reativar(cliente_admin, usuario):
    cliente_admin.post(f"/usuarios/{usuario.id}/ativo")
    cliente_admin.post(f"/usuarios/{usuario.id}/ativo")

    assert usuario.ativo


# ---------- Travas de segurança ----------

def test_ninguem_mexe_no_proprio_acesso(cliente_admin, admin):
    resposta = cliente_admin.post(f"/usuarios/{admin.id}/ativo", follow_redirects=True)
    cliente_admin.post(f"/usuarios/{admin.id}/admin")

    assert "seu próprio acesso" in resposta.get_data(as_text=True)
    assert admin.ativo and admin.admin


def test_admin_pode_tirar_outro_admin(cliente_admin):
    """Pode: quem está logada (Bia) continua admin, então o sistema
    nunca fica sem administração (ela não pode mexer em si mesma)."""
    davi = Usuario(nome="Davi", login="davi", senha_hash="x", admin=True)
    db.session.add(davi)
    db.session.commit()

    cliente_admin.post(f"/usuarios/{davi.id}/admin")
    assert not davi.admin

    cliente_admin.post(f"/usuarios/{davi.id}/ativo")
    assert not davi.ativo

    assert Usuario.query.filter_by(admin=True, ativo=True).count() == 1  # a Bia


def test_acao_desconhecida(cliente_admin, usuario):
    assert cliente_admin.post(f"/usuarios/{usuario.id}/apagar").status_code == 404


# ---------- Comando de terminal ----------

def test_comando_cria_admin(app):
    resultado = app.test_cli_runner().invoke(args=[
        "criar-usuario", "chefe", "--nome", "Chefe", "--senha", "12345678", "--admin",
    ])

    assert "administração" in resultado.output
    assert usuario("chefe").admin


# ---------- API (React) ----------

def test_api_lista_usuarios(cliente_admin, admin, usuario):
    lista = cliente_admin.get("/api/usuarios").get_json()["usuarios"]

    por_login = {u["login"]: u for u in lista}
    assert por_login[admin.login]["voce"] is True
    assert por_login["ana"]["voce"] is False
    assert por_login["ana"]["papel"] == "Recepção"
    assert all("senha_hash" not in u for u in lista)  # nada de senha na resposta


def test_api_cria_usuario(cliente_admin):
    resposta = cliente_admin.post("/api/usuarios", json={
        "nome": " Carla Dias ", "login": "Carla.Dias", "senha": "senha-boa-123", "admin": True,
    })

    assert resposta.status_code == 201
    carla = usuario("carla.dias")
    assert carla.nome == "Carla Dias" and carla.admin
    assert carla.trocar_senha  # senha escolhida pela admin = provisória


def test_api_admin_so_com_true_de_verdade(cliente_admin):
    cliente_admin.post("/api/usuarios", json={
        "nome": "Davi", "login": "davi", "senha": "senha-boa-123", "admin": "sim",
    })
    assert not usuario("davi").admin


def test_api_cria_usuario_com_erros_por_campo(cliente_admin, usuario):
    resposta = cliente_admin.post("/api/usuarios", json={
        "nome": "", "login": "ana", "senha": "curta",
    })

    assert resposta.status_code == 422
    erros = resposta.get_json()["erros"]
    assert set(erros) == {"nome", "login", "senha"}
    assert "Já existe" in erros["login"]


def test_api_alterna_papel_e_situacao(cliente_admin, usuario):
    resposta = cliente_admin.post(f"/api/usuarios/{usuario.id}/admin")
    assert resposta.get_json()["mensagem"] == "Usuário 'ana' agora é da administração."
    assert usuario.admin

    cliente_admin.post(f"/api/usuarios/{usuario.id}/ativo")
    assert not usuario.ativo


def test_api_nao_mexe_no_proprio_acesso(cliente_admin, admin):
    for acao in ("ativo", "admin", "senha"):
        resposta = cliente_admin.post(f"/api/usuarios/{admin.id}/{acao}", json={"nova": "x" * 8})
        assert resposta.status_code == 409
    assert admin.admin and admin.ativo


def test_api_redefine_senha(app, cliente_admin, usuario):
    computador_da_ana = navegador_logado(app, usuario)

    resposta = cliente_admin.post(f"/api/usuarios/{usuario.id}/senha", json={"nova": "provisoria-1"})

    assert resposta.status_code == 200
    assert usuario.confere_senha("provisoria-1") and usuario.trocar_senha
    assert computador_da_ana.get("/api/pacientes").status_code == 401  # caiu


def test_api_redefine_senha_curta(cliente_admin, usuario):
    resposta = cliente_admin.post(f"/api/usuarios/{usuario.id}/senha", json={"nova": "curta"})

    assert resposta.status_code == 422
    assert "nova" in resposta.get_json()["erros"]
    assert usuario.confere_senha(SENHA_TESTE)


@pytest.mark.parametrize("endereco", ["/api/usuarios/999/ativo", "/api/usuarios/999/senha",
                                      "/api/usuarios/1/apagar"])
def test_api_usuario_ou_acao_inexistente(cliente_admin, endereco):
    assert cliente_admin.post(endereco, json={"nova": "x" * 8}).status_code == 404
