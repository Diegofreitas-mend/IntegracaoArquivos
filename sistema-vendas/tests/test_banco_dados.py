import pytest

from src.banco_dados import PRODUTOS_INICIAIS, BancoVendas, ErroBancoDados


def test_cria_banco_com_produtos_iniciais(tmp_path):
    banco = BancoVendas(tmp_path / "vendas.db")

    assert (tmp_path / "vendas.db").exists()
    assert [p.produto_id for p in banco.listar_produtos()] == [
        p.produto_id for p in PRODUTOS_INICIAIS
    ]


def test_reabrir_banco_nao_duplica_produtos_iniciais(tmp_path):
    caminho = tmp_path / "vendas.db"
    BancoVendas(caminho)

    banco = BancoVendas(caminho)

    assert len(banco.listar_produtos()) == len(PRODUTOS_INICIAIS)


def test_cadastrar_e_buscar_produto(tmp_path):
    banco = BancoVendas(tmp_path / "vendas.db")

    banco.cadastrar_produto(50, "Webcam", 199.90)

    produto = banco.buscar_produto(50)
    assert produto.nome == "Webcam"
    assert produto.preco == 199.90
    assert banco.buscar_produto(999) is None


def test_cadastrar_produto_invalido(tmp_path):
    banco = BancoVendas(tmp_path / "vendas.db")

    with pytest.raises(ErroBancoDados, match="já existe"):
        banco.cadastrar_produto(1, "Outro mouse", 10.0)
    with pytest.raises(ErroBancoDados):
        banco.cadastrar_produto(60, "   ", 10.0)
    with pytest.raises(ErroBancoDados):
        banco.cadastrar_produto(61, "Cabo", -1.0)


def test_registrar_venda_persiste_venda_e_itens(tmp_path):
    caminho = tmp_path / "vendas.db"
    banco = BancoVendas(caminho)

    venda = banco.registrar_venda([(1, 2), (2, 1)])

    recarregada = BancoVendas(caminho).buscar_venda(venda.venda_id)
    assert recarregada.data_hora == venda.data_hora
    assert [(i.produto.produto_id, i.qnt) for i in recarregada.itens] == [(1, 2), (2, 1)]
    assert recarregada.calcular_total() == pytest.approx(venda.calcular_total())


def test_venda_ids_sao_unicos_e_sequenciais(tmp_path):
    banco = BancoVendas(tmp_path / "vendas.db")

    primeira = banco.registrar_venda([(1, 1)])
    segunda = banco.registrar_venda([(2, 1)])

    assert segunda.venda_id > primeira.venda_id
    assert [v.venda_id for v in banco.listar_vendas()] == [primeira.venda_id, segunda.venda_id]


def test_mesmo_produto_repetido_vira_um_item(tmp_path):
    banco = BancoVendas(tmp_path / "vendas.db")

    venda = banco.registrar_venda([(1, 2), (1, 3)])

    assert [(i.produto.produto_id, i.qnt) for i in venda.itens] == [(1, 5)]


@pytest.mark.parametrize(
    "itens, mensagem",
    [
        ([], "pelo menos um item"),
        ([(1, 0)], "quantidade inválida"),
        ([(1, -2)], "quantidade inválida"),
        ([(1, 1), (999, 1)], "não existe"),
    ],
)
def test_venda_invalida_nao_grava_nada(tmp_path, itens, mensagem):
    banco = BancoVendas(tmp_path / "vendas.db")

    with pytest.raises(ErroBancoDados, match=mensagem):
        banco.registrar_venda(itens)

    assert banco.listar_vendas() == []


def test_buscar_venda_inexistente(tmp_path):
    banco = BancoVendas(tmp_path / "vendas.db")

    assert banco.buscar_venda(9999) is None
