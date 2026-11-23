"""Inicia a interface local dos dois sistemas: python app.py."""

import argparse
from pathlib import Path

from banco import ErroBanco, ler_url
from interface.servidor import criar_servidor


def main() -> None:
    parser = argparse.ArgumentParser(description="Arvendro Gestão — vendas e estoque")
    parser.add_argument("--porta", type=int, default=8000)
    parser.add_argument(
        "--dados",
        type=Path,
        help="Raiz alternativa para os dados (demonstrações/testes)",
    )
    argumentos = parser.parse_args()
    raiz = argumentos.dados or Path(__file__).resolve().parent
    try:
        servidor = criar_servidor(raiz, argumentos.porta)
    except ErroBanco as erro:
        print(f"Não foi possível acessar o banco de dados: {erro}")
        return
    with servidor:
        print(f"Arvendro Gestão: http://127.0.0.1:{servidor.server_port}", flush=True)
        banco = "Supabase (PostgreSQL)" if ler_url(raiz) else "SQLite local, sem .env"
        print(f"Banco de dados: {banco}", flush=True)
        print(
            "Use Ctrl+C para encerrar. Execute apenas uma instância para cada pasta de dados.",
            flush=True,
        )
        try:
            servidor.serve_forever()
        except KeyboardInterrupt:
            print("\nServidor encerrado.")


if __name__ == "__main__":
    main()
