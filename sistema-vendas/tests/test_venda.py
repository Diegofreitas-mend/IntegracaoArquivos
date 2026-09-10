import pytest

from src.venda import Venda
from src.produto import Produto
from src.item_venda import ItemVenda


def test_criar_venda():
    produto = Produto(1, "Mouse", 79.90)
    item = ItemVenda(produto, 2)
    venda = Venda(1, [item])

    assert venda.venda_id == 1
    assert venda.itens == [item]
    assert venda.calcular_total() == 159.80
