"""Testes de papéis (recepção x administração) e do cadastro de usuários."""

import pytest

from app import Local, Usuario, app as flask_app, db
from conftest import SENHA_TESTE, navegador_logado

# Rotas que SÓ a administração pode usar: (método, endereço)
ROTAS_DE_ADMIN = [
    ("get", "/api/locais"),
    ("post", "/api/locais"),
    ("post", "/api/locais/1/alternar"),
    ("put", "/api/locais/1"),
    ("get", "/api/usuarios"),
    ("post", "/api/usuarios"),
    ("post", "/api/usuarios/1/ativo"),
    ("post", "/api/usuarios/1/senha"),
]


def usuario(login):
    return Usuario.query.filter_by(login=login).one()


def alterar(cliente, alguem, acao):
    return cliente.post(f"/api/usuarios/{alguem.id}/{acao}")


def criar(cliente, **dados):
    return cliente.post("/api/usuarios", json=dados)


def entrar(navegador, login="ana", senha=SENHA_TESTE):
    return navegador.post("/api/login", json={"login": login, "senha": senha})


# ---------- Recepção x administração ----------

@pytest.mark.parametrize("metodo, endereco", ROTAS_DE_ADMIN)
def test_recepcao_nao_usa_as_rotas_de_admin(cliente, metodo, endereco):
    resposta = getattr(cliente, metodo)(endereco, json={
        "nome": "Invasor", "login": "invasor", "senha": "12345678", "admin": True,
    })

    assert resposta.status_code == 403
    assert "administração" in resposta.get_json()["erro"]
    assert Local.query.filter_by(nome="Invasor").first() is None
    assert Usuario.query.filter_by(login="invasor").first() is None


def test_recepcao_nao_consegue_mudar_nada(cliente, admin):
    cliente.post("/api/locais/1/alternar")
    alterar(cliente, admin, "ativo")
    alterar(cliente, admin, "admin")

    assert db.session.get(Local, 1).ativo
    assert usuario("bia").ativo and usuario("bia").admin


def test_sessao_diz_o_papel(cliente, cliente_admin):
    """É por aqui que o React decide mostrar (ou não) Locais e Usuários."""
    assert cliente.get("/api/sessao").get_json()["usuario"]["admin"] is False
    assert cliente_admin.get("/api/sessao").get_json()["usuario"]["admin"] is True


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
        for metodo, endereco in ROTAS_DE_ADMIN
    }

    assert so_admin, "nenhuma rota com a etiqueta? o decorador mudou?"
    assert so_admin == testadas


# ---------- Criar usuário ----------

def test_admin_cria_usuario_da_recepcao(cliente_admin):
    criar(cliente_admin, nome="Carla Dias", login="Carla.Dias", senha="senha-boa-123")

    carla = usuario("carla.dias")  # login sempre em minúsculas
    assert not carla.admin and carla.ativo
    assert carla.confere_senha("senha-boa-123")
    assert "senha-boa-123" not in carla.senha_hash


def test_admin_cria_outro_admin(cliente_admin):
    criar(cliente_admin, nome="Davi", login="davi", senha="senha-boa-123", admin=True)

    assert usuario("davi").admin


@pytest.mark.parametrize("dados, campo, erro", [
    ({"nome": "", "login": "novo", "senha": "senha-boa-123"}, "nome", "Informe o nome"),
    ({"nome": "X", "login": "ab", "senha": "senha-boa-123"}, "login", "de 3 a 50 caracteres"),
    ({"nome": "X", "login": "joão", "senha": "senha-boa-123"}, "login", "letras sem acento"),
    ({"nome": "X", "login": "com espaço", "senha": "senha-boa-123"}, "login", "letras sem acento"),
    ({"nome": "X", "login": "bia", "senha": "senha-boa-123"}, "login", "Já existe o usuário"),
    ({"nome": "X", "login": "novo", "senha": "curta"}, "senha", "pelo menos 8"),
])
def test_criar_usuario_invalido(cliente_admin, dados, campo, erro):
    resposta = criar(cliente_admin, **dados)

    assert erro in resposta.get_json()["erros"][campo]
    assert Usuario.query.count() == 1  # só a própria bia


def test_erro_nao_devolve_a_senha(cliente_admin):
    resposta = criar(cliente_admin, nome="Carla", login="ca", senha="senha-secreta-999")

    assert "senha-secreta-999" not in resposta.get_data(as_text=True)


# ---------- Desativar ----------

def test_desativado_nao_consegue_entrar(cliente_admin, usuario, cliente_anonimo):
    alterar(cliente_admin, usuario, "ativo")

    resposta = entrar(cliente_anonimo)

    assert "foi desativado" in resposta.get_json()["erro"]
    assert cliente_anonimo.get("/api/pacientes").status_code == 401


def test_desativado_e_posto_para_fora_na_hora(cliente_admin, usuario, cliente):
    """A Ana estava com o sistema aberto quando foi desativada."""
    assert cliente.get("/api/pacientes").status_code == 200

    alterar(cliente_admin, usuario, "ativo")

    assert cliente.get("/api/pacientes").status_code == 401  # o React mostra o login


def test_senha_errada_de_desativado_nao_revela_nada(cliente_admin, usuario, cliente_anonimo):
    alterar(cliente_admin, usuario, "ativo")

    resposta = entrar(cliente_anonimo, senha="errada")

    assert resposta.get_json()["erro"] == "Usuário ou senha incorretos."


def test_reativar(cliente_admin, usuario):
    alterar(cliente_admin, usuario, "ativo")
    alterar(cliente_admin, usuario, "ativo")

    assert usuario.ativo


# ---------- Travas de segurança ----------

def test_ninguem_mexe_no_proprio_acesso(cliente_admin, admin):
    for acao in ("ativo", "admin", "senha"):
        resposta = cliente_admin.post(f"/api/usuarios/{admin.id}/{acao}", json={"nova": "x" * 8})
        assert resposta.status_code == 409

    assert "seu próprio acesso" in alterar(cliente_admin, admin, "ativo").get_json()["erro"]
    assert admin.ativo and admin.admin


def test_admin_pode_tirar_outro_admin(cliente_admin):
    """Pode: quem está logada (Bia) continua admin, então o sistema
    nunca fica sem administração (ela não pode mexer em si mesma)."""
    davi = Usuario(nome="Davi", login="davi", senha_hash="x", admin=True)
    db.session.add(davi)
    db.session.commit()

    alterar(cliente_admin, davi, "admin")
    assert not davi.admin

    alterar(cliente_admin, davi, "ativo")
    assert not davi.ativo

    assert Usuario.query.filter_by(admin=True, ativo=True).count() == 1  # a Bia


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
