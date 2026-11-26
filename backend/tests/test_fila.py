"""Testes com banco e rotas: ordem da fila, fluxo de status,
cadastro, busca e painel (tudo pela API, como o React usa)."""

from datetime import datetime, timedelta

import pytest

from app import Paciente, buscar_por_status, db


def nomes(pacientes):
    return [p.nome for p in pacientes]


def chamar(cliente, local="Triagem"):
    return cliente.post("/api/pacientes/chamar-proximo", json={"local": local})


def listas(cliente, termo=""):
    return cliente.get(f"/api/pacientes?q={termo}").get_json()


def nomes_em(lista):
    return [p["nome"] for p in lista]


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

    chamar(cliente)

    bruno = Paciente.query.filter_by(nome="Bruno").one()
    assert bruno.status == "Em atendimento"
    assert bruno.chamado_em is not None
    assert Paciente.query.filter_by(nome="Ana").one().status == "Aguardando"


def test_chamar_proximo_com_fila_vazia_avisa(cliente):
    resposta = chamar(cliente)

    assert resposta.status_code == 409
    assert "Não há pacientes aguardando" in resposta.get_json()["erro"]


def test_fluxo_completo_aguardando_atendimento_concluido(cliente, criar_paciente):
    paciente = criar_paciente("Ana")

    chamar(cliente)
    cliente.post(f"/api/pacientes/{paciente.id}/concluir")

    db.session.refresh(paciente)  # relê do banco o que as rotas mudaram
    assert paciente.status == "Concluído"
    assert paciente.chegada <= paciente.chamado_em <= paciente.concluido_em


def test_nao_finaliza_quem_ainda_esta_na_fila(cliente, criar_paciente):
    paciente = criar_paciente("Ana")

    resposta = cliente.post(f"/api/pacientes/{paciente.id}/concluir")

    assert resposta.status_code == 409
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
    resposta = cliente.post("/api/pacientes", json=formulario())

    assert resposta.status_code == 201
    paciente = Paciente.query.one()
    assert paciente.cpf == "52998224725"  # salvo só com os dígitos
    assert paciente.status == "Aguardando"
    assert paciente.chegada is not None


@pytest.mark.parametrize("campos, campo, erro", [
    ({"cpf": "123.456.789-00"}, "cpf", "CPF inválido"),
    ({"nascimento": "2999-01-01"}, "nascimento", "não pode estar no futuro"),
    ({"nascimento": "ontem"}, "nascimento", "data de nascimento válida"),
    ({"nome": "   "}, "nome", "Informe o nome"),
])
def test_cadastro_invalido_e_recusado(cliente, campos, campo, erro):
    resposta = cliente.post("/api/pacientes", json=formulario(**campos))

    assert resposta.status_code == 422
    assert erro in resposta.get_json()["erros"][campo]
    assert Paciente.query.count() == 0


def test_cadastro_com_cpf_repetido_e_recusado(cliente, criar_paciente):
    criar_paciente("Já cadastrada", cpf="52998224725")

    resposta = cliente.post("/api/pacientes", json=formulario())

    assert "Já existe um paciente" in resposta.get_json()["erros"]["cpf"]
    assert Paciente.query.count() == 1


def test_editar_mantendo_o_proprio_cpf_funciona(cliente, criar_paciente):
    paciente = criar_paciente("Ana", cpf="52998224725")

    cliente.put(f"/api/pacientes/{paciente.id}", json=formulario(nome="Ana Souza"))

    db.session.refresh(paciente)
    assert paciente.nome == "Ana Souza"


# ---------- Busca ----------

def test_busca_por_nome_e_por_cpf(cliente, criar_paciente):
    criar_paciente("Mariana", cpf="52998224725")
    criar_paciente("Bruno", cpf="11144477735")

    assert nomes_em(listas(cliente, "ana")["fila"]) == ["Mariana"]
    assert nomes_em(listas(cliente, "111.444")["fila"]) == ["Bruno"]


@pytest.mark.parametrize("termo", ["joao", "JOÃO", "João", "conceicao", "CONCEIÇÃO"])
def test_busca_ignora_acentos_e_maiusculas(cliente, criar_paciente, termo):
    criar_paciente("João da Conceição")
    criar_paciente("Bruno")

    assert nomes_em(listas(cliente, termo)["fila"]) == ["João da Conceição"]


def test_busca_acentuada_acha_nome_sem_acento(cliente, criar_paciente):
    # Recepcionista digitou com acento, mas o cadastro foi feito sem
    criar_paciente("Jose Antonio")

    assert nomes_em(listas(cliente, "José Antônio")["fila"]) == ["Jose Antonio"]


def test_busca_nao_muda_a_posicao_na_fila(cliente, criar_paciente):
    criar_paciente("Ana")
    criar_paciente("Bruno")

    dados = listas(cliente, "bruno")

    assert [(p["nome"], p["posicao"]) for p in dados["fila"]] == [("Bruno", 2)]
    assert dados["total_na_fila"] == 2  # "Chamar próximo" olha a fila toda


def test_busca_com_porcentagem_e_texto_comum(cliente, criar_paciente):
    """'%' e '_' são curingas no SQL; aqui têm que valer como texto."""
    criar_paciente("Ana")

    assert listas(cliente, "%25")["fila"] == []   # %25 = "%" no endereço


# ---------- Painel ----------

def test_painel_mostra_o_ultimo_chamado(cliente, criar_paciente):
    criar_paciente("Ana Lima")
    criar_paciente("Bruno Costa")

    chamar(cliente)  # Ana
    chamar(cliente)  # Bruno

    dados = cliente.get("/painel/dados").get_json()

    assert dados["atual"]["nome"] == "Bruno C."
    assert [c["nome"] for c in dados["anteriores"]] == ["Ana L."]
    assert dados["aguardando"] == 0


def test_painel_vazio(cliente):
    dados = cliente.get("/painel/dados").get_json()

    assert dados == {"atual": None, "anteriores": [], "aguardando": 0}


def test_painel_nao_pede_login(cliente_anonimo, criar_paciente):
    criar_paciente("Ana Lima", status="Em atendimento", chamado_em=datetime.now())

    dados = cliente_anonimo.get("/painel/dados").get_json()

    assert dados["atual"]["nome"] == "Ana L."  # só primeiro nome + inicial


# ---------- Locais (guichês/consultórios) ----------

def test_chamar_registra_o_local(cliente, criar_paciente):
    paciente = criar_paciente("Ana")

    resposta = chamar(cliente, "Consultório 2")

    db.session.refresh(paciente)
    assert paciente.local == "Consultório 2"
    assert "para Consultório 2" in resposta.get_json()["mensagem"]


@pytest.mark.parametrize("local", ["", "Sala Secreta"])
def test_chamar_sem_local_valido_nao_chama_ninguem(cliente, criar_paciente, local):
    paciente = criar_paciente("Ana")

    resposta = chamar(cliente, local)

    db.session.refresh(paciente)
    assert paciente.status == "Aguardando"
    assert "Escolha para qual local" in resposta.get_json()["erro"]


def test_ultimo_local_ja_vem_escolhido(cliente, criar_paciente):
    criar_paciente("Ana")

    chamar(cliente, "Consultório 3")

    assert listas(cliente)["ultimo_local"] == "Consultório 3"


def test_primeira_vez_pede_para_escolher(cliente):
    assert listas(cliente)["ultimo_local"] is None


def test_painel_mostra_o_local(cliente, criar_paciente):
    criar_paciente("Ana Lima")
    criar_paciente("Bruno Costa")

    chamar(cliente, "Triagem")
    chamar(cliente, "Consultório 1")

    dados = cliente.get("/painel/dados").get_json()
    assert dados["atual"]["local"] == "Consultório 1"
    assert dados["anteriores"][0]["local"] == "Triagem"


def test_painel_com_chamada_antiga_sem_local(cliente, criar_paciente):
    criar_paciente("Antigo Silva", status="Em atendimento",
                   chamado_em=datetime.now(), local=None)

    atual = cliente.get("/painel/dados").get_json()["atual"]

    assert atual["nome"] == "Antigo S."
    assert atual["local"] is None  # o React não mostra "→ None"


# ---------- Chamar de novo ----------
# Os pacientes começam "chamados há alguns minutos" (horários no passado).
# Assim a nova chamada é sempre mais recente, por mais rápido que o
# teste rode (no Windows, duas chamadas seguidas a datetime.now()
# podem devolver exatamente o mesmo horário).

def ha_minutos(minutos):
    return datetime.now() - timedelta(minutes=minutos)


def em_atendimento(criar_paciente, nome, local, chamado_ha_min):
    return criar_paciente(nome, status="Em atendimento", local=local,
                          chegou_ha_min=chamado_ha_min + 10,
                          chamado_em=ha_minutos(chamado_ha_min))


def test_chamar_de_novo_volta_ao_painel(cliente, criar_paciente):
    ana = em_atendimento(criar_paciente, "Ana Lima", "Triagem", chamado_ha_min=5)
    em_atendimento(criar_paciente, "Bruno Costa", "Consultório 1", chamado_ha_min=2)
    chave_antes = cliente.get("/painel/dados").get_json()["atual"]["chave"]

    cliente.post(f"/api/pacientes/{ana.id}/chamar-de-novo")

    dados = cliente.get("/painel/dados").get_json()
    assert dados["atual"]["nome"] == "Ana L."          # Ana voltou para o topo
    assert dados["atual"]["local"] == "Triagem"        # para o mesmo local
    assert dados["atual"]["de_novo"] is True
    assert dados["atual"]["chave"] != chave_antes      # o painel vai piscar e tocar
    assert [c["nome"] for c in dados["anteriores"]] == ["Bruno C."]  # sem repetir a Ana


def test_chamar_de_novo_nao_muda_o_tempo_de_espera(cliente, criar_paciente):
    paciente = em_atendimento(criar_paciente, "Ana", "Triagem", chamado_ha_min=5)
    primeira_chamada = paciente.chamado_em

    cliente.post(f"/api/pacientes/{paciente.id}/chamar-de-novo")

    db.session.refresh(paciente)
    assert paciente.chamado_em == primeira_chamada   # a espera continua a mesma
    assert paciente.ultima_chamada > primeira_chamada
    assert paciente.foi_rechamado


def test_so_chama_de_novo_quem_esta_em_atendimento(cliente, criar_paciente):
    paciente = criar_paciente("Ana")  # ainda na fila

    cliente.post(f"/api/pacientes/{paciente.id}/chamar-de-novo")

    db.session.refresh(paciente)
    assert paciente.ultima_chamada is None
    assert paciente.status == "Aguardando"


def test_primeira_chamada_nao_conta_como_de_novo(cliente, criar_paciente):
    criar_paciente("Ana")
    chamar(cliente)

    dados = cliente.get("/painel/dados").get_json()

    assert dados["atual"]["de_novo"] is False


def test_lista_mostra_quando_foi_chamado_de_novo(cliente, criar_paciente):
    paciente = em_atendimento(criar_paciente, "Ana", "Triagem", chamado_ha_min=5)

    cliente.post(f"/api/pacientes/{paciente.id}/chamar-de-novo")

    ana = listas(cliente)["em_atendimento"][0]
    assert ana["foi_rechamado"] is True
    assert ana["ultima_chamada"] != ana["chamado_em"]


# ---------- Não compareceu ----------

def test_nao_compareceu_encerra_e_vai_para_o_historico(cliente, criar_paciente):
    paciente = em_atendimento(criar_paciente, "Ana", "Triagem", chamado_ha_min=5)

    cliente.post(f"/api/pacientes/{paciente.id}/nao-compareceu")

    db.session.refresh(paciente)
    assert paciente.status == "Não compareceu"
    assert paciente.concluido_em is not None

    dados = listas(cliente)
    assert dados["em_atendimento"] == []  # saiu de "Em atendimento"
    assert [(p["nome"], p["status"]) for p in dados["historico"]] == [("Ana", "Não compareceu")]


def test_nao_compareceu_so_vale_para_quem_esta_em_atendimento(cliente, criar_paciente):
    paciente = criar_paciente("Ana")  # ainda na fila

    cliente.post(f"/api/pacientes/{paciente.id}/nao-compareceu")

    db.session.refresh(paciente)
    assert paciente.status == "Aguardando"
