"""Testes com banco e rotas: ordem da fila, fluxo de status,
cadastro, busca e painel."""

from app import Paciente, buscar_por_status, db


def nomes(pacientes):
    return [p.nome for p in pacientes]


# ---------- Ordem da fila ----------

def test_fila_ordena_por_prioridade(criar_paciente):
    criar_paciente("Normal")
    criar_paciente("Preferencial", prioridade="Preferencial")
    criar_paciente("Urgente", prioridade="Urgente")

    assert nomes(buscar_por_status("Aguardando")) == [
        "Urgente", "Preferencial", "Normal"
    ]


def test_mesma_prioridade_quem_chegou_primeiro_vem_antes(criar_paciente):
    criar_paciente("Primeira")
    criar_paciente("Segunda")

    assert nomes(buscar_por_status("Aguardando")) == ["Primeira", "Segunda"]


# ---------- Fluxo de status ----------

def test_chamar_proximo_pega_o_mais_prioritario(cliente, criar_paciente):
    criar_paciente("Ana")
    criar_paciente("Bruno", prioridade="Urgente")

    cliente.post("/pacientes/chamar-proximo")

    bruno = Paciente.query.filter_by(nome="Bruno").one()
    assert bruno.status == "Em atendimento"
    assert bruno.chamado_em is not None
    assert Paciente.query.filter_by(nome="Ana").one().status == "Aguardando"


def test_chamar_proximo_com_fila_vazia_avisa(cliente):
    resposta = cliente.post("/pacientes/chamar-proximo", follow_redirects=True)

    assert "Não há pacientes aguardando" in resposta.get_data(as_text=True)


def test_fluxo_completo_aguardando_atendimento_concluido(cliente, criar_paciente):
    paciente = criar_paciente("Ana")

    cliente.post("/pacientes/chamar-proximo")
    cliente.post(f"/pacientes/finalizar/{paciente.id}")

    db.session.refresh(paciente)  # relê do banco o que as rotas mudaram
    assert paciente.status == "Concluído"
    assert paciente.chegada <= paciente.chamado_em <= paciente.concluido_em


def test_nao_finaliza_quem_ainda_esta_na_fila(cliente, criar_paciente):
    paciente = criar_paciente("Ana")

    cliente.post(f"/pacientes/finalizar/{paciente.id}")

    db.session.refresh(paciente)
    assert paciente.status == "Aguardando"
    assert paciente.concluido_em is None


# ---------- Cadastro ----------

def formulario(**campos):
    dados = {
        "nome": "Carla Dias",
        "nascimento": "1985-03-20",
        "cpf": "529.982.247-25",
        "prioridade": "Normal",
    }
    dados.update(campos)
    return dados


def test_cadastro_valido_entra_na_fila(cliente):
    resposta = cliente.post("/pacientes/novo", data=formulario())

    assert resposta.status_code == 302  # redirecionou para /pacientes
    paciente = Paciente.query.one()
    assert paciente.cpf == "52998224725"  # salvo só com os dígitos
    assert paciente.status == "Aguardando"
    assert paciente.chegada is not None


def test_cadastro_com_cpf_invalido_e_recusado(cliente):
    resposta = cliente.post("/pacientes/novo", data=formulario(cpf="123.456.789-00"))

    assert "CPF inválido" in resposta.get_data(as_text=True)
    assert Paciente.query.count() == 0


def test_cadastro_com_cpf_repetido_e_recusado(cliente, criar_paciente):
    criar_paciente("Já cadastrada", cpf="52998224725")

    resposta = cliente.post("/pacientes/novo", data=formulario())

    assert "Já existe um paciente" in resposta.get_data(as_text=True)
    assert Paciente.query.count() == 1


def test_cadastro_com_nascimento_no_futuro_e_recusado(cliente):
    resposta = cliente.post("/pacientes/novo", data=formulario(nascimento="2999-01-01"))

    assert "não pode estar no futuro" in resposta.get_data(as_text=True)


def test_editar_mantendo_o_proprio_cpf_funciona(cliente, criar_paciente):
    paciente = criar_paciente("Ana", cpf="52998224725")

    cliente.post(
        f"/pacientes/editar/{paciente.id}",
        data=formulario(nome="Ana Souza"),
    )

    db.session.refresh(paciente)
    assert paciente.nome == "Ana Souza"


# ---------- Busca e página ----------

def test_busca_por_nome_e_por_cpf(cliente, criar_paciente):
    criar_paciente("Mariana", cpf="52998224725")
    criar_paciente("Bruno", cpf="11144477735")

    por_nome = cliente.get("/pacientes?q=ana").get_data(as_text=True)
    assert "Mariana" in por_nome and "Bruno" not in por_nome

    por_cpf = cliente.get("/pacientes?q=111.444").get_data(as_text=True)
    assert "Bruno" in por_cpf and "Mariana" not in por_cpf


def test_busca_nao_muda_a_posicao_na_fila(cliente, criar_paciente):
    criar_paciente("Ana")
    criar_paciente("Bruno")

    pagina = cliente.get("/pacientes?q=bruno").get_data(as_text=True)

    assert "2º" in pagina  # Bruno continua em 2º, mesmo sozinho na busca


def test_versao_parcial_vem_sem_menu(cliente, criar_paciente):
    criar_paciente("Ana")

    parcial = cliente.get("/pacientes?parcial=1").get_data(as_text=True)

    assert 'data-fila="1"' in parcial
    assert "<nav>" not in parcial


# ---------- Painel ----------

def test_painel_mostra_o_ultimo_chamado(cliente, criar_paciente):
    criar_paciente("Ana Lima")
    criar_paciente("Bruno Costa")

    cliente.post("/pacientes/chamar-proximo")  # Ana
    cliente.post("/pacientes/chamar-proximo")  # Bruno

    dados = cliente.get("/painel/dados").get_json()

    assert dados["atual"]["nome"] == "Bruno C."
    assert [c["nome"] for c in dados["anteriores"]] == ["Ana L."]
    assert dados["aguardando"] == 0


def test_painel_vazio(cliente):
    dados = cliente.get("/painel/dados").get_json()

    assert dados == {"atual": None, "anteriores": [], "aguardando": 0}
