"""Inicialização do terminal de estoque a partir da raiz do projeto."""

from importlib import import_module

if __name__ == "__main__":
    import_module("sistema-estoque.src.main").main()
