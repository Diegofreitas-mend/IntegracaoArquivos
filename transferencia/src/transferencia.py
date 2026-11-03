import os
import sys
import time
from datetime import datetime
from pathlib import Path

# transferencia/src/transferencia.py -> parents[2] é a raiz do repositório
INTEGRACAO = Path(__file__).resolve().parents[2] / "integracao"
INTERVALO_MONITOR = 3  # segundos


def transferir(origem: Path, destino: Path) -> list[Path]:
    """Move os *.json de `origem` (saída do Vendas) para `destino` (entrada do Estoque).

    Arquivos .tmp ainda sendo gravados pelo Vendas são ignorados. Se já existir
    um arquivo com o mesmo nome no destino, ele não é sobrescrito: o arquivo
    movido ganha um carimbo de data/hora no nome.
    """
    origem, destino = Path(origem), Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    movidos = []
    for arquivo in sorted(origem.glob("*.json")):
        if not arquivo.is_file():
            continue
        alvo = destino / arquivo.name
        if alvo.exists():
            carimbo = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            alvo = destino / f"{arquivo.stem}_{carimbo}{arquivo.suffix}"
        os.replace(arquivo, alvo)  # mesma partição: troca atômica
        movidos.append(alvo)
    return movidos


def main() -> None:
    origem, destino = INTEGRACAO / "saida", INTEGRACAO / "entrada"
    origem.mkdir(parents=True, exist_ok=True)
    monitorar = "--monitorar" in sys.argv[1:]

    if monitorar:
        print(f"Transferindo {origem} -> {destino} a cada {INTERVALO_MONITOR}s. Ctrl+C para parar.")
    try:
        while True:
            for arquivo in transferir(origem, destino):
                print(f"{datetime.now():%H:%M:%S} | TRANSFERIDO | {arquivo.name}")
            if not monitorar:
                break
            time.sleep(INTERVALO_MONITOR)
    except KeyboardInterrupt:
        print("\nTransferência encerrada.")


if __name__ == "__main__":
    main()
