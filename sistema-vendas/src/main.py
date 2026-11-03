from src.banco_dados import BancoVendas, ErroBancoDados
from src.exportador import exportar_venda


def ler_inteiro(mensagem: str) -> int | None:
    texto = input(mensagem).strip()
    try:
        return int(texto)
    except ValueError:
        print("Valor inválido: informe um número inteiro.")
        return None


def ler_decimal(mensagem: str) -> float | None:
    texto = input(mensagem).strip().replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        print("Valor inválido: informe um número.")
        return None


def mostrar_produtos(banco: BancoVendas) -> None:
    print("\n  ID | Produto                | Preço")
    print("  ---+------------------------+-----------")
    for p in banco.listar_produtos():
        print(f"  {p.produto_id:>2} | {p.nome:<22} | R$ {p.preco:>8.2f}")


def cadastrar_produto(banco: BancoVendas) -> None:
    produto_id = ler_inteiro("ID do novo produto (use o mesmo ID do estoque): ")
    if produto_id is None:
        return
    nome = input("Nome: ")
    preco = ler_decimal("Preço: ")
    if preco is None:
        return
    try:
        banco.cadastrar_produto(produto_id, nome, preco)
        print("Produto cadastrado.")
    except ErroBancoDados as erro:
        print(f"Erro: {erro}")


def registrar_venda(banco: BancoVendas) -> None:
    mostrar_produtos(banco)
    print("\nInforme os itens da venda. ID 0 encerra.")
    itens: list[tuple[int, int]] = []
    while True:
        produto_id = ler_inteiro("ID do produto: ")
        if produto_id is None:
            continue
        if produto_id == 0:
            break
        quantidade = ler_inteiro("Quantidade: ")
        if quantidade is None:
            continue
        itens.append((produto_id, quantidade))

    if not itens:
        print("Venda cancelada: nenhum item informado.")
        return
    try:
        venda = banco.registrar_venda(itens)
    except ErroBancoDados as erro:
        print(f"Erro: {erro}")
        return
    print(f"Venda {venda.venda_id} registrada. Total: R$ {venda.calcular_total():.2f}")
    try:
        arquivo = exportar_venda(venda)
        print(f"Arquivo gerado: {arquivo}")
    except OSError as erro:
        print(f"Erro ao gerar o arquivo da venda: {erro}")


def mostrar_vendas(banco: BancoVendas) -> None:
    vendas = banco.listar_vendas()
    if not vendas:
        print("\nNenhuma venda registrada.")
        return
    for venda in vendas:
        print(f"\nVenda {venda.venda_id} - {venda.data_hora:%d/%m/%Y %H:%M:%S}")
        for item in venda.itens:
            print(
                f"  {item.qnt} x {item.produto.nome:<20} R$ {item.calcular_subtotal():>9.2f}"
            )
        print(f"  {'Total':<24} R$ {venda.calcular_total():>9.2f}")


def main() -> None:
    banco = BancoVendas()

    while True:
        print("\n=== Sistema de Vendas ===")
        print("1 - Ver produtos")
        print("2 - Registrar venda")
        print("3 - Ver vendas")
        print("4 - Cadastrar produto")
        print("0 - Sair")
        opcao = input("Opção: ").strip()

        if opcao == "1":
            mostrar_produtos(banco)
        elif opcao == "2":
            registrar_venda(banco)
        elif opcao == "3":
            mostrar_vendas(banco)
        elif opcao == "4":
            cadastrar_produto(banco)
        elif opcao == "0":
            print("Até logo!")
            break
        else:
            print("Opção inválida.")


if __name__ == "__main__":
    main()
