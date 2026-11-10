"""RF01: ponto de entrada do Sistema de Vendas via terminal."""

import argparse
from pathlib import Path

from .servico import ServicoVendas
from .terminal import executar_menu


def main() -> None:
    parser = argparse.ArgumentParser(description="Arvendro - terminal de vendas")
    parser.add_argument(
        "--dados", type=Path, help="Raiz alternativa para os dados de demonstração"
    )
    argumentos = parser.parse_args()
    raiz = (
        argumentos.dados.resolve()
        if argumentos.dados
        else Path(__file__).resolve().parents[2]
    )
    executar_menu(ServicoVendas(raiz))


if __name__ == "__main__":
    main()
