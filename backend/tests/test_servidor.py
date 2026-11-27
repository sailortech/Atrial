"""Testes do servidor.py (o jeito de ligar o Atrial para usar)."""

import os
import time

from servidor import ip_na_rede, problemas_do_build


def criar(caminho, texto="x", ha_segundos=0):
    """Cria um arquivo com a "data de modificação" no passado, se pedido."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(texto, encoding="utf-8")
    momento = time.time() - ha_segundos
    os.utime(caminho, (momento, momento))


def test_sem_build_nao_liga(tmp_path):
    erros, avisos = problemas_do_build(tmp_path / "dist", tmp_path / "src")

    assert len(erros) == 1 and "npm run build" in erros[0]
    assert avisos == []


def test_build_em_dia(tmp_path):
    criar(tmp_path / "src" / "App.jsx", ha_segundos=100)
    criar(tmp_path / "dist" / "index.html", ha_segundos=10)  # gerado DEPOIS

    assert problemas_do_build(tmp_path / "dist", tmp_path / "src") == ([], [])


def test_codigo_mais_novo_que_o_build_avisa(tmp_path):
    criar(tmp_path / "dist" / "index.html", ha_segundos=100)
    criar(tmp_path / "src" / "App.jsx", ha_segundos=200)              # antigo: ok
    criar(tmp_path / "src" / "paginas" / "Locais.jsx", ha_segundos=5)  # mudou depois

    erros, avisos = problemas_do_build(tmp_path / "dist", tmp_path / "src")

    assert erros == []
    assert len(avisos) == 1
    assert "Locais.jsx" in avisos[0] and "App.jsx" not in avisos[0]
    assert "npm run build" in avisos[0]


def test_muitos_arquivos_mudados_mostra_so_alguns(tmp_path):
    criar(tmp_path / "dist" / "index.html", ha_segundos=100)
    for numero in range(5):
        criar(tmp_path / "src" / f"arquivo{numero}.jsx")

    _, avisos = problemas_do_build(tmp_path / "dist", tmp_path / "src")

    assert avisos[0].count(".jsx") == 3 and "..." in avisos[0]


def test_ip_na_rede_e_um_endereco_ou_nada():
    ip = ip_na_rede()

    # Depende da máquina (com ou sem rede), mas nunca o "127." deste computador
    assert ip is None or (ip.count(".") == 3 and not ip.startswith("127."))


def test_mudar_so_os_testes_nao_avisa(tmp_path):
    """Arquivos de teste não entram no build."""
    criar(tmp_path / "dist" / "index.html", ha_segundos=100)
    criar(tmp_path / "src" / "paginas" / "Locais.test.jsx")
    criar(tmp_path / "src" / "testes" / "simularApi.js")

    assert problemas_do_build(tmp_path / "dist", tmp_path / "src") == ([], [])
