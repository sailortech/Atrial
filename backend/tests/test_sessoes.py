"""Testes de sessão: senha nova derruba os logins antigos.

Cenário típico: alguém descobriu a senha da Ana e entrou "em outro
computador". Ana troca a senha (ou a administração redefine): o
intruso tem que cair, e a Ana continuar dentro.
"""

from conftest import SENHA_TESTE, navegador_logado

NOVA = "senha-nova-789"


def esta_logado(navegador):
    """Pergunta à API quem está logado (como o React faz ao abrir).

    (Não basta olhar se /api/pacientes abre: quem está com senha
    provisória recebe 403 lá, mas continua logado. Confundir os dois
    deixaria um teste passar sem a proteção existir; aconteceu
    enquanto este arquivo era escrito.)
    """
    return navegador.get("/api/sessao").get_json()["usuario"] is not None


def test_cookie_guarda_id_e_versao(usuario):
    id_, versao = usuario.get_id().split(":")

    assert id_ == str(usuario.id)
    assert len(versao) == 32


def test_cada_usuario_tem_uma_versao_diferente(usuario, admin):
    assert usuario.versao_sessao != admin.versao_sessao


def test_trocar_a_senha_derruba_os_outros_computadores(app, cliente, usuario):
    intruso = navegador_logado(app, usuario)  # "outro computador"
    assert esta_logado(intruso)

    cliente.post("/api/minha-senha", json={
        "atual": SENHA_TESTE, "nova": NOVA, "confirmacao": NOVA,
    })

    assert not esta_logado(intruso)   # caiu
    assert esta_logado(cliente)       # quem trocou continua dentro


def test_senha_errada_na_troca_nao_derruba_ninguem(app, cliente, usuario):
    outro = navegador_logado(app, usuario)

    cliente.post("/api/minha-senha", json={
        "atual": "errada", "nova": NOVA, "confirmacao": NOVA,
    })

    assert esta_logado(outro) and esta_logado(cliente)


def test_redefinir_pela_administracao_derruba_todos(app, cliente_admin, cliente, usuario):
    cliente_admin.post(f"/api/usuarios/{usuario.id}/senha", json={"nova": "provisoria-1"})

    assert not esta_logado(cliente)


def test_reativado_precisa_entrar_de_novo(app, cliente_admin, cliente, usuario):
    cliente_admin.post(f"/api/usuarios/{usuario.id}/ativo")  # desativa
    cliente_admin.post(f"/api/usuarios/{usuario.id}/ativo")  # reativa

    # O cookie de antes da desativação não pode "ressuscitar"
    assert not esta_logado(cliente)


def test_mudar_o_papel_nao_derruba_ninguem(cliente_admin, cliente, usuario):
    cliente_admin.post(f"/api/usuarios/{usuario.id}/admin")

    assert esta_logado(cliente)


def test_login_normal_continua_funcionando(cliente_anonimo, usuario):
    cliente_anonimo.post("/api/login", json={"login": "ana", "senha": SENHA_TESTE})

    assert esta_logado(cliente_anonimo)


def test_cookie_antigo_so_com_o_id_nao_vale(app, usuario):
    """Cookies de antes desta mudança guardavam só o id ("2")."""
    navegador = app.test_client()
    with navegador.session_transaction() as sessao:
        sessao["_user_id"] = str(usuario.id)

    assert not esta_logado(navegador)


def test_versao_inventada_nao_vale(app, usuario):
    navegador = app.test_client()
    with navegador.session_transaction() as sessao:
        sessao["_user_id"] = f"{usuario.id}:{'0' * 32}"

    assert not esta_logado(navegador)


def test_id_estranho_nao_quebra(app):
    navegador = app.test_client()
    with navegador.session_transaction() as sessao:
        sessao["_user_id"] = "abc:def"

    assert navegador.get("/api/pacientes").status_code == 401  # sem erro 500
