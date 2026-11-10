"""RF01: registrar vendas no terminal e publicar os respectivos arquivos JSON."""

from .servico import ServicoVendas
from .repositorio_vendas import ErroExportacao


def moeda(valor: float) -> str:
    return f"R$ {valor:.2f}".replace(".", ",")


def mostrar_catalogo(catalogo: list[dict]) -> None:
    print("\nCódigo | Produto              | Preço")
    print("-------+----------------------+--------------")
    for produto in catalogo:
        print(
            f"{produto['produto_id']:>6} | {produto['nome']:<20} | {moeda(produto['preco'])}"
        )


def registrar_venda(servico: ServicoVendas) -> None:
    catalogo = servico.catalogo_terminal()
    produtos = {p["produto_id"]: p for p in catalogo}
    quantidades: dict[int, int] = {}
    mostrar_catalogo(catalogo)
    print("Informe os itens. Enter conclui o pedido; 0 cancela a venda.")
    while True:
        codigo = input("Código do produto: ").strip()
        if codigo == "0":
            print("Venda cancelada. Nenhum arquivo foi gerado.")
            return
        if not codigo:
            break
        try:
            produto_id = int(codigo)
            if produto_id not in produtos:
                print("Produto não encontrado no catálogo.")
                continue
            quantidade = int(input("Quantidade: ").strip())
            if quantidade <= 0:
                raise ValueError
        except ValueError:
            print(
                "Informe código e quantidade inteiros; a quantidade deve ser maior que zero."
            )
            continue
        quantidades[produto_id] = quantidades.get(produto_id, 0) + quantidade
        print(f"Adicionado: {produtos[produto_id]['nome']} x {quantidade}.")

    if not quantidades:
        print("Pedido vazio. Nenhum arquivo foi gerado.")
        return
    print("\nResumo do pedido")
    total_centavos = 0
    for pid, quantidade in quantidades.items():
        subtotal = round(produtos[pid]["preco"] * 100) * quantidade
        total_centavos += subtotal
        print(f"  {produtos[pid]['nome']} x {quantidade}: {moeda(subtotal / 100)}")
    print(f"Total: {moeda(total_centavos / 100)}")
    print("O estoque validará o saldo ao receber o arquivo.")
    if input("Confirmar venda? [s/N]: ").strip().lower() != "s":
        print("Venda cancelada. Nenhum arquivo foi gerado.")
        return
    venda = servico.criar(
        [
            {"produto_id": pid, "quantidade": quantidade}
            for pid, quantidade in quantidades.items()
        ],
        catalogo,
    )
    print(f"Venda #{venda['venda_id']} registrada: {moeda(venda['total'])}.")
    print(
        f"JSON gerado: {servico.repositorio.pasta_saida / ('venda_' + str(venda['venda_id']) + '.json')}"
    )
    print(
        "Arquivo aguardando transferência. Encaminhe o JSON à pasta de entrada do estoque."
    )


def mostrar_historico(servico: ServicoVendas) -> None:
    vendas = servico.repositorio.listar()
    if not vendas:
        print("Nenhuma venda registrada.")
        return
    print("\nVenda | Data e hora | Total")
    for venda in vendas:
        print(f"#{venda['venda_id']} | {venda['data_hora']} | {moeda(venda['total'])}")


def executar_menu(servico: ServicoVendas) -> None:
    while True:
        print("\n=== Arvendro | Sistema de Vendas ===")
        print("1 - Nova venda")
        print("2 - Consultar catálogo")
        print("3 - Histórico de vendas")
        print("0 - Sair")
        try:
            opcao = input("Opção: ").strip()
            if opcao == "0":
                print("Sistema de Vendas encerrado.")
                return
            if opcao == "1":
                registrar_venda(servico)
            elif opcao == "2":
                mostrar_catalogo(servico.catalogo_terminal())
            elif opcao == "3":
                mostrar_historico(servico)
            else:
                print("Opção inválida.")
        except (EOFError, KeyboardInterrupt):
            print("\nOperação encerrada. Itens não confirmados não foram salvos.")
            return
        except ErroExportacao as erro:
            print(erro)
        except (OSError, ValueError) as erro:
            print(f"Não foi possível concluir: {erro}")
