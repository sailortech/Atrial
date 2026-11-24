"""Testes com banco e rotas: ordem da fila, fluxo de status,
cadastro, busca e painel."""

from datetime import datetime, timedelta

import pytest

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

    cliente.post("/pacientes/chamar-proximo", data={"local": "Triagem"})

    bruno = Paciente.query.filter_by(nome="Bruno").one()
    assert bruno.status == "Em atendimento"
    assert bruno.chamado_em is not None
    assert Paciente.query.filter_by(nome="Ana").one().status == "Aguardando"


def test_chamar_proximo_com_fila_vazia_avisa(cliente):
    resposta = cliente.post("/pacientes/chamar-proximo", data={"local": "Triagem"}, follow_redirects=True)

    assert "Não há pacientes aguardando" in resposta.get_data(as_text=True)


def test_fluxo_completo_aguardando_atendimento_concluido(cliente, criar_paciente):
    paciente = criar_paciente("Ana")

    cliente.post("/pacientes/chamar-proximo", data={"local": "Triagem"})
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


@pytest.mark.parametrize("termo", ["joao", "JOÃO", "João", "conceicao", "CONCEIÇÃO"])
def test_busca_ignora_acentos_e_maiusculas(cliente, criar_paciente, termo):
    criar_paciente("João da Conceição")
    criar_paciente("Bruno")

    pagina = cliente.get(f"/pacientes?q={termo}").get_data(as_text=True)

    assert "João da Conceição" in pagina and "Bruno" not in pagina


def test_busca_acentuada_acha_nome_sem_acento(cliente, criar_paciente):
    # Recepcionista digitou com acento, mas o cadastro foi feito sem
    criar_paciente("Jose Antonio")

    pagina = cliente.get("/pacientes?q=José Antônio").get_data(as_text=True)

    assert "Jose Antonio" in pagina


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

    cliente.post("/pacientes/chamar-proximo", data={"local": "Triagem"})  # Ana
    cliente.post("/pacientes/chamar-proximo", data={"local": "Triagem"})  # Bruno

    dados = cliente.get("/painel/dados").get_json()

    assert dados["atual"]["nome"] == "Bruno C."
    assert [c["nome"] for c in dados["anteriores"]] == ["Ana L."]
    assert dados["aguardando"] == 0


def test_painel_vazio(cliente):
    dados = cliente.get("/painel/dados").get_json()

    assert dados == {"atual": None, "anteriores": [], "aguardando": 0}


# ---------- Locais (guichês/consultórios) ----------

def test_chamar_registra_o_local(cliente, criar_paciente):
    paciente = criar_paciente("Ana")

    resposta = cliente.post(
        "/pacientes/chamar-proximo", data={"local": "Consultório 2"},
        follow_redirects=True,
    )

    db.session.refresh(paciente)
    assert paciente.local == "Consultório 2"
    assert "para Consultório 2" in resposta.get_data(as_text=True)


@pytest.mark.parametrize("local", ["", "Sala Secreta"])
def test_chamar_sem_local_valido_nao_chama_ninguem(cliente, criar_paciente, local):
    paciente = criar_paciente("Ana")

    resposta = cliente.post(
        "/pacientes/chamar-proximo", data={"local": local}, follow_redirects=True
    )

    db.session.refresh(paciente)
    assert paciente.status == "Aguardando"
    assert "Escolha para qual local" in resposta.get_data(as_text=True)


def test_ultimo_local_ja_vem_escolhido(cliente, criar_paciente):
    criar_paciente("Ana")

    cliente.post("/pacientes/chamar-proximo", data={"local": "Consultório 3"})
    pagina = cliente.get("/pacientes").get_data(as_text=True)

    assert '<option value="Consultório 3" selected>' in pagina


def test_primeira_vez_pede_para_escolher(cliente):
    pagina = cliente.get("/pacientes").get_data(as_text=True)

    assert "Chamar para..." in pagina
    assert " selected>" not in pagina.replace("selected disabled>", "")


def test_painel_mostra_o_local(cliente, criar_paciente):
    criar_paciente("Ana Lima")
    criar_paciente("Bruno Costa")

    cliente.post("/pacientes/chamar-proximo", data={"local": "Triagem"})
    cliente.post("/pacientes/chamar-proximo", data={"local": "Consultório 1"})

    dados = cliente.get("/painel/dados").get_json()
    assert dados["atual"]["local"] == "Consultório 1"
    assert dados["anteriores"][0]["local"] == "Triagem"

    html = cliente.get("/painel").get_data(as_text=True)
    assert "→ Consultório 1" in html


def test_painel_com_chamada_antiga_sem_local(cliente, criar_paciente):
    criar_paciente("Antigo Silva", status="Em atendimento",
                   chamado_em=datetime.now(), local=None)

    html = cliente.get("/painel").get_data(as_text=True)

    assert "Antigo S." in html
    assert "→" not in html.split("<script>")[0]  # nada de "→ None"


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

    cliente.post(f"/pacientes/chamar-de-novo/{ana.id}")

    dados = cliente.get("/painel/dados").get_json()
    assert dados["atual"]["nome"] == "Ana L."          # Ana voltou para o topo
    assert dados["atual"]["local"] == "Triagem"        # para o mesmo local
    assert dados["atual"]["de_novo"] is True
    assert dados["atual"]["chave"] != chave_antes      # o painel vai piscar e tocar
    assert [c["nome"] for c in dados["anteriores"]] == ["Bruno C."]  # sem repetir a Ana


def test_chamar_de_novo_nao_muda_o_tempo_de_espera(cliente, criar_paciente):
    paciente = em_atendimento(criar_paciente, "Ana", "Triagem", chamado_ha_min=5)
    primeira_chamada = paciente.chamado_em

    cliente.post(f"/pacientes/chamar-de-novo/{paciente.id}")

    db.session.refresh(paciente)
    assert paciente.chamado_em == primeira_chamada   # a espera continua a mesma
    assert paciente.ultima_chamada > primeira_chamada
    assert paciente.foi_rechamado


def test_so_chama_de_novo_quem_esta_em_atendimento(cliente, criar_paciente):
    paciente = criar_paciente("Ana")  # ainda na fila

    cliente.post(f"/pacientes/chamar-de-novo/{paciente.id}")

    db.session.refresh(paciente)
    assert paciente.ultima_chamada is None
    assert paciente.status == "Aguardando"


def test_primeira_chamada_nao_conta_como_de_novo(cliente, criar_paciente):
    criar_paciente("Ana")
    cliente.post("/pacientes/chamar-proximo", data={"local": "Triagem"})

    dados = cliente.get("/painel/dados").get_json()

    assert dados["atual"]["de_novo"] is False
    assert "Chamando agora" in cliente.get("/painel").get_data(as_text=True)


def test_pagina_mostra_quando_foi_chamado_de_novo(cliente, criar_paciente):
    paciente = em_atendimento(criar_paciente, "Ana", "Triagem", chamado_ha_min=5)

    cliente.post(f"/pacientes/chamar-de-novo/{paciente.id}")

    html = cliente.get("/pacientes").get_data(as_text=True)
    assert "Chamar de novo" in html
    assert "chamado de novo às" in html
    assert "Chamando novamente" in cliente.get("/painel").get_data(as_text=True)
