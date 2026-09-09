from src.produto import Produto


def test_criar_produto():
    produto = Produto(1, "Mouse", 79.90)

    assert produto.produto_id == 1
    assert produto.nome == "Mouse"
    assert produto.preco == 79.90
