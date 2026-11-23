"""RF01: ponto de entrada do Sistema de Vendas via terminal."""

import argparse
from pathlib import Path

from banco import ErroBanco

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
    try:
        servico = ServicoVendas(raiz)
    except ErroBanco as erro:
        print(f"Não foi possível acessar o banco de dados: {erro}")
        return
    print(f"Banco de dados: {servico.banco.descricao}")
    executar_menu(servico)
    servico.banco.fechar()


if __name__ == "__main__":
    main()
