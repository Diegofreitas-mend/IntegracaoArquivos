import time

from src.config import Pastas
from src.log_config import configurar_logging
from src.processador import Status, processar_pendentes
from src.repositorio_estoque import ErroRepositorio, RepositorioEstoque

INTERVALO_MONITOR = 3  # segundos


def ler_inteiro(mensagem: str) -> int | None:
    texto = input(mensagem).strip()
    try:
        return int(texto)
    except ValueError:
        print("Valor inválido: informe um número inteiro.")
        return None


def mostrar_estoque(repositorio: RepositorioEstoque) -> None:
    print("\n  ID | Produto                | Quantidade")
    print("  ---+------------------------+-----------")
    for p in repositorio.listar():
        print(f"  {p.produto_id:>2} | {p.nome:<22} | {p.quantidade:>9}")


def processar(repositorio: RepositorioEstoque, pastas: Pastas) -> None:
    resultados = processar_pendentes(repositorio, pastas)
    if not resultados:
        print("\nNenhum arquivo na pasta de entrada.")
        return
    ok = sum(r.status is Status.PROCESSADO for r in resultados)
    print(f"\n{len(resultados)} arquivo(s) lido(s): {ok} processado(s), {len(resultados) - ok} com erro/duplicado.")


def monitorar(repositorio: RepositorioEstoque, pastas: Pastas) -> None:
    print(f"\nMonitorando {pastas.entrada} a cada {INTERVALO_MONITOR}s. Ctrl+C para parar.")
    try:
        while True:
            processar_pendentes(repositorio, pastas)
            time.sleep(INTERVALO_MONITOR)
    except KeyboardInterrupt:
        print("\nMonitoramento encerrado.")


def cadastrar_produto(repositorio: RepositorioEstoque) -> None:
    produto_id = ler_inteiro("ID do novo produto: ")
    if produto_id is None:
        return
    nome = input("Nome: ")
    quantidade = ler_inteiro("Quantidade inicial: ")
    if quantidade is None:
        return
    try:
        repositorio.cadastrar_produto(produto_id, nome, quantidade)
        print("Produto cadastrado.")
    except ErroRepositorio as erro:
        print(f"Erro: {erro}")


def repor_estoque(repositorio: RepositorioEstoque) -> None:
    produto_id = ler_inteiro("ID do produto: ")
    if produto_id is None:
        return
    quantidade = ler_inteiro("Quantidade a repor: ")
    if quantidade is None:
        return
    try:
        repositorio.repor(produto_id, quantidade)
        print("Estoque atualizado.")
    except ErroRepositorio as erro:
        print(f"Erro: {erro}")


def main() -> None:
    pastas = Pastas.padrao()
    pastas.criar()
    configurar_logging(pastas.arquivo_log)
    repositorio = RepositorioEstoque(pastas.arquivo_estoque)

    while True:
        print("\n=== Sistema de Estoque ===")
        print("1 - Ver estoque")
        print("2 - Processar arquivos da pasta de entrada")
        print("3 - Monitorar pasta de entrada (automático)")
        print("4 - Cadastrar produto")
        print("5 - Repor estoque")
        print("0 - Sair")
        opcao = input("Opção: ").strip()

        if opcao == "1":
            mostrar_estoque(repositorio)
        elif opcao == "2":
            processar(repositorio, pastas)
        elif opcao == "3":
            monitorar(repositorio, pastas)
        elif opcao == "4":
            cadastrar_produto(repositorio)
        elif opcao == "5":
            repor_estoque(repositorio)
        elif opcao == "0":
            print("Até logo!")
            break
        else:
            print("Opção inválida.")


if __name__ == "__main__":
    main()
