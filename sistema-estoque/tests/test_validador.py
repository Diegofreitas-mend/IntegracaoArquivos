import pytest

from src.produto_estoque import ProdutoEstoque
from src.validador import ErroValidacao, validar_venda


@pytest.fixture
def produtos():
    return {1: ProdutoEstoque(1, "Mouse", 10), 2: ProdutoEstoque(2, "Teclado", 5)}


def venda(itens, venda_id=1):
    return {"venda_id": venda_id, "data_hora": "2026-10-20T10:00:00", "itens": itens}


def test_venda_valida(produtos):
    resultado = validar_venda(venda([{"produto_id": 1, "quantidade": 2}]), produtos)

    assert resultado.venda_id == 1
    assert resultado.itens[0].produto_id == 1
    assert resultado.itens[0].quantidade == 2


def test_conteudo_nao_e_objeto(produtos):
    with pytest.raises(ErroValidacao, match="objeto JSON"):
        validar_venda([1, 2, 3], produtos)


def test_venda_id_ausente(produtos):
    with pytest.raises(ErroValidacao, match="venda_id"):
        validar_venda({"itens": [{"produto_id": 1, "quantidade": 1}]}, produtos)


@pytest.mark.parametrize("itens", [None, [], "abc"])
def test_itens_ausentes_ou_vazios(produtos, itens):
    with pytest.raises(ErroValidacao, match="itens"):
        validar_venda({"venda_id": 1, "itens": itens}, produtos)


def test_produto_inexistente(produtos):
    with pytest.raises(ErroValidacao, match="não existe"):
        validar_venda(venda([{"produto_id": 99, "quantidade": 1}]), produtos)


@pytest.mark.parametrize("quantidade", [0, -3, 1.5, "2", None, True])
def test_quantidade_invalida(produtos, quantidade):
    with pytest.raises(ErroValidacao, match="quantidade"):
        validar_venda(venda([{"produto_id": 1, "quantidade": quantidade}]), produtos)


def test_estoque_insuficiente(produtos):
    with pytest.raises(ErroValidacao, match="insuficiente"):
        validar_venda(venda([{"produto_id": 2, "quantidade": 6}]), produtos)


def test_estoque_insuficiente_somando_itens_repetidos(produtos):
    itens = [{"produto_id": 2, "quantidade": 3}, {"produto_id": 2, "quantidade": 3}]
    with pytest.raises(ErroValidacao, match="insuficiente"):
        validar_venda(venda(itens), produtos)
