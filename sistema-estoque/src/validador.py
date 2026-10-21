from src.produto_estoque import ProdutoEstoque
from src.venda_recebida import ItemRecebido, VendaRecebida


class ErroValidacao(Exception):
    """Arquivo recebido não passou nas regras de validação (RF03)."""


def _eh_inteiro(valor) -> bool:
    # bool é subclasse de int em Python; True/False não são quantidades válidas.
    return isinstance(valor, int) and not isinstance(valor, bool)


def validar_venda(
    dados, produtos: dict[int, ProdutoEstoque]
) -> VendaRecebida:
    """Valida o conteúdo (já convertido de JSON) de um arquivo de venda.

    Regras:
      - estrutura: objeto com `venda_id` e `itens` (lista não vazia);
      - cada item tem `produto_id` e `quantidade`;
      - o produto existe no cadastro do estoque;
      - a quantidade é um inteiro maior que zero;
      - há saldo suficiente (somando itens repetidos do mesmo produto).

    Levanta ErroValidacao com o motivo, sem alterar nada.
    """
    if not isinstance(dados, dict):
        raise ErroValidacao("o conteúdo do arquivo deve ser um objeto JSON")

    venda_id = dados.get("venda_id")
    if venda_id is None or isinstance(venda_id, bool):
        raise ErroValidacao("campo 'venda_id' ausente ou inválido")
    if not (_eh_inteiro(venda_id) or (isinstance(venda_id, str) and venda_id.strip())):
        raise ErroValidacao("campo 'venda_id' ausente ou inválido")

    data_hora = dados.get("data_hora")
    if data_hora is not None and not isinstance(data_hora, str):
        raise ErroValidacao("campo 'data_hora' deve ser texto")

    itens_brutos = dados.get("itens")
    if not isinstance(itens_brutos, list) or not itens_brutos:
        raise ErroValidacao("campo 'itens' ausente, vazio ou não é uma lista")

    itens: list[ItemRecebido] = []
    for posicao, item in enumerate(itens_brutos, start=1):
        if not isinstance(item, dict):
            raise ErroValidacao(f"item {posicao}: deve ser um objeto")

        produto_id = item.get("produto_id")
        if not _eh_inteiro(produto_id):
            raise ErroValidacao(f"item {posicao}: 'produto_id' ausente ou inválido")
        if produto_id not in produtos:
            raise ErroValidacao(
                f"item {posicao}: produto {produto_id} não existe no cadastro"
            )

        quantidade = item.get("quantidade")
        if not _eh_inteiro(quantidade) or quantidade <= 0:
            raise ErroValidacao(
                f"item {posicao}: quantidade inválida ({quantidade!r}); "
                "deve ser um inteiro maior que zero"
            )

        itens.append(ItemRecebido(produto_id, quantidade))

    totais: dict[int, int] = {}
    for item in itens:
        totais[item.produto_id] = totais.get(item.produto_id, 0) + item.quantidade
    for produto_id, total in totais.items():
        disponivel = produtos[produto_id].quantidade
        if total > disponivel:
            raise ErroValidacao(
                f"estoque insuficiente para o produto {produto_id}: "
                f"pedido {total}, disponível {disponivel}"
            )

    return VendaRecebida(venda_id, data_hora, tuple(itens))
