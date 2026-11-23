import json

import pytest

from banco import Banco
from src.item_venda import ItemVenda
from src.produto import Produto
from src.repositorio_vendas import RepositorioVendas
from src.venda import Venda

PRECOS = {1: 79.90, 2: 149.90}


@pytest.fixture
def banco(tmp_path):
    return Banco(tmp_path / "vendas.db")


def novo_repositorio(banco, tmp_path):
    return RepositorioVendas(banco, tmp_path / "saida", PRECOS)


def nova_venda(venda_id=1001):
    itens = [
        ItemVenda(Produto(2, "Teclado", 149.90), 1),
        ItemVenda(Produto(1, "Mouse", 79.90), 2),
    ]
    return Venda(venda_id, itens).para_dict()


def test_venda_salva_volta_igual_ao_json_exportado(banco, tmp_path):
    repo = novo_repositorio(banco, tmp_path)
    venda = nova_venda()

    repo.salvar(venda)

    # Reabre o banco: o histórico tem exatamente o conteúdo exportado,
    # inclusive a ordem dos itens e os centavos.
    (salva,) = novo_repositorio(Banco(tmp_path / "vendas.db"), tmp_path).listar()
    exportada = json.loads((tmp_path / "saida" / "venda_1001.json").read_text(encoding="utf-8"))
    assert salva == venda == exportada
    assert [item["produto_id"] for item in salva["itens"]] == [2, 1]
    assert salva["total"] == 309.70


def test_historico_listado_do_mais_recente(banco, tmp_path):
    repo = novo_repositorio(banco, tmp_path)
    for venda_id in (1001, 1003, 1002):
        repo.salvar(nova_venda(venda_id))

    assert [v["venda_id"] for v in repo.listar()] == [1003, 1002, 1001]


def test_numero_de_venda_repetido_nao_grava_nem_exporta(banco, tmp_path):
    repo = novo_repositorio(banco, tmp_path)
    repo.salvar(nova_venda())
    (tmp_path / "saida" / "venda_1001.json").unlink()

    with pytest.raises(ValueError, match="acabou de ser usado"):
        repo.salvar(nova_venda())

    assert len(repo.listar()) == 1
    assert not (tmp_path / "saida" / "venda_1001.json").exists()


def test_precos_iniciais_e_alteracao_persistem(banco, tmp_path):
    repo = novo_repositorio(banco, tmp_path)
    assert repo.precos() == PRECOS

    repo.definir_preco(1, 0.10)
    repo.definir_preco(4, 99.90)

    # Reabrir não restaura os preços iniciais por cima dos alterados.
    reaberto = novo_repositorio(Banco(tmp_path / "vendas.db"), tmp_path)
    assert reaberto.precos() == {1: 0.10, 2: 149.90, 4: 99.90}
