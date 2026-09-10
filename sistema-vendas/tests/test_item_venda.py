from src.produto import Produto
from src.item_venda import ItemVenda


def test_item_venda():
    produto = Produto(1, "Mouse", 79.90)
    item_venda = ItemVenda(produto, 1)

    assert item_venda.produto == produto
    assert item_venda.qnt == 1
    assert item_venda.calcular_subtotal() == 79.90
