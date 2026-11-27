"""Liga o Atrial para USAR no dia a dia (e não para programar).

    venv\\Scripts\\python servidor.py      (ou dois cliques em iniciar.cmd)

Diferenças para o "flask run --debug" (que continua sendo o jeito de
programar):

- Usa o Waitress, um servidor feito para uso de verdade. O do Flask
  avisa ele mesmo que é só para desenvolvimento: é mais lento e, com
  --debug, mostra o código do sistema quando dá erro.
- Ouve na rede (0.0.0.0), e não só neste computador: assim a TV da
  sala de espera consegue abrir o painel. O endereço para a TV aparece
  na tela ao ligar.
- Antes de ligar, confere se o React foi gerado (npm run build) e se
  não está desatualizado em relação ao código.
"""

import os
import socket
import sys
from pathlib import Path

PORTA_PADRAO = 5000


def vai_so_para_os_testes(caminho):
    """Mensagem.test.jsx, testes/simularApi.js...: não entram no build,
    então mudar um deles não deixa o build desatualizado."""
    return ".test." in caminho.name or "testes" in caminho.parts


def problemas_do_build(dist, src):
    """Confere o React pronto. Devolve (erros, avisos), duas listas de textos.

    erro  = não dá para ligar (não existe build)
    aviso = liga, mas o build é mais velho que algum arquivo do código
    """
    dist, src = Path(dist), Path(src)
    index = dist / "index.html"

    if not index.is_file():
        return [
            "O React ainda não foi gerado. Dentro da pasta frontend, rode: "
            "npm install (só na primeira vez) e npm run build"
        ], []

    gerado_em = index.stat().st_mtime
    mais_novos = sorted(
        str(arquivo.relative_to(src))
        for arquivo in src.rglob("*")
        if arquivo.is_file()
        and arquivo.stat().st_mtime > gerado_em
        and not vai_so_para_os_testes(arquivo.relative_to(src))
    )
    if mais_novos:
        exemplo = ", ".join(mais_novos[:3]) + (" ..." if len(mais_novos) > 3 else "")
        return [], [
            f"O código do React mudou depois do último build ({exemplo}). "
            "Para ver as mudanças, rode npm run build dentro de frontend."
        ]
    return [], []


def ip_na_rede():
    """O endereço deste computador na rede local (ex.: 192.168.0.12), ou None.

    Truque comum: "conectar" um socket UDP a um endereço qualquer não
    manda nada pela rede, mas faz o sistema escolher a placa de rede
    que seria usada, e o endereço dela é o que a TV precisa.
    """
    conexao = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        conexao.connect(("10.255.255.255", 1))
        ip = conexao.getsockname()[0]
        return None if ip.startswith("127.") else ip
    except OSError:
        return None  # sem rede
    finally:
        conexao.close()


def main():
    # Importado aqui (e não no topo) para os testes poderem usar as
    # funções acima sem carregar o app inteiro
    from waitress import serve

    from app import app

    pasta_frontend = Path(__file__).resolve().parent.parent / "frontend"
    erros, avisos = problemas_do_build(app.config["FRONTEND_DIST"], pasta_frontend / "src")
    for erro in erros:
        print(f"\n  ERRO: {erro}\n")
    if erros:
        sys.exit(1)

    porta = int(os.environ.get("ATRIAL_PORTA", PORTA_PADRAO))
    # 0.0.0.0 = aceita conexões da rede (TV, outros computadores).
    # ATRIAL_HOST=127.0.0.1 deixa só este computador (ex.: para testar).
    host = os.environ.get("ATRIAL_HOST", "0.0.0.0")
    ip = ip_na_rede() if host == "0.0.0.0" else None

    print()
    print("  Atrial ligado. Para desligar: Ctrl+C (ou feche esta janela).")
    print()
    print(f"  Neste computador:   http://127.0.0.1:{porta}")
    if ip:
        print(f"  Na TV (painel):     http://{ip}:{porta}/app/painel")
        print(f"  Outros computadores: http://{ip}:{porta}")
    else:
        print("  (Só este computador consegue abrir o Atrial.)")
    for aviso in avisos:
        print(f"\n  AVISO: {aviso}")
    print()

    # threads: quantos pedidos ao mesmo tempo (recepção, TV, consultórios)
    serve(app, host=host, port=porta, threads=8)


if __name__ == "__main__":
    main()
