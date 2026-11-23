import pytest

from banco import Banco, ErroBanco
from src.repositorio_estoque import ErroRepositorio, RepositorioEstoque
from src.venda_recebida import ItemRecebido, VendaRecebida


def nova_venda(venda_id=1, produto_id=1, quantidade=2):
    return VendaRecebida(venda_id, None, (ItemRecebido(produto_id, quantidade),))


def test_cria_estoque_inicial_se_arquivo_nao_existe(tmp_path):
    repo = RepositorioEstoque(Banco(tmp_path / "estoque.db"))

    assert len(repo.listar()) > 0
    assert (tmp_path / "estoque.db").exists()


def test_aplicar_venda_baixa_estoque_e_persiste(tmp_path):
    caminho = tmp_path / "estoque.db"
    repo = RepositorioEstoque(Banco(caminho))
    antes = repo.produtos[1].quantidade

    repo.aplicar_venda(nova_venda(quantidade=3), "v1.json", "hash1")

    assert repo.produtos[1].quantidade == antes - 3
    # recarregando do disco, o estado se mantém (inclusive o controle de duplicidade)
    recarregado = RepositorioEstoque(Banco(caminho))
    assert recarregado.produtos[1].quantidade == antes - 3
    assert recarregado.motivo_duplicidade("hash1") is not None


def test_duplicidade_por_hash_e_por_venda_id(tmp_path):
    repo = RepositorioEstoque(Banco(tmp_path / "estoque.db"))
    repo.aplicar_venda(nova_venda(venda_id=7), "v7.json", "hashA")

    assert repo.motivo_duplicidade("hashA") is not None
    assert repo.motivo_duplicidade("outro-hash", venda_id=7) is not None
    assert repo.motivo_duplicidade("outro-hash", venda_id=8) is None


def test_aplicar_venda_que_deixaria_negativo_nao_altera_nada(tmp_path):
    repo = RepositorioEstoque(Banco(tmp_path / "estoque.db"))
    antes = repo.produtos[1].quantidade

    with pytest.raises(ErroRepositorio):
        repo.aplicar_venda(nova_venda(quantidade=antes + 1), "v.json", "h")

    assert repo.produtos[1].quantidade == antes
    assert repo.processados == []


def test_cadastrar_produto_e_repor(tmp_path):
    repo = RepositorioEstoque(Banco(tmp_path / "estoque.db"))

    repo.cadastrar_produto(50, "Webcam", 4)
    repo.repor(50, 6)

    assert repo.produtos[50].quantidade == 10
    with pytest.raises(ErroRepositorio):
        repo.cadastrar_produto(50, "Duplicado", 1)
    with pytest.raises(ErroRepositorio):
        repo.repor(50, 0)
    with pytest.raises(ErroRepositorio):
        repo.repor(999, 1)


def test_banco_de_estoque_corrompido(tmp_path):
    caminho = tmp_path / "estoque.db"
    caminho.write_text("isto não é um banco de dados " * 100, encoding="utf-8")

    with pytest.raises(ErroBanco):
        RepositorioEstoque(Banco(caminho))


def test_banco_recusa_segunda_baixa_da_mesma_venda(tmp_path):
    """Mesmo se dois processos passarem pela checagem de duplicidade ao mesmo
    tempo, a chave única do banco impede a segunda baixa (RF05)."""
    banco = Banco(tmp_path / "estoque.db")
    primeiro, segundo = RepositorioEstoque(banco), RepositorioEstoque(banco)
    antes = primeiro.produtos[1].quantidade

    primeiro.aplicar_venda(nova_venda(venda_id=3), "a.json", "hash-a")
    with pytest.raises(ErroRepositorio, match="já foi processada"):
        segundo.aplicar_venda(nova_venda(venda_id=3), "b.json", "hash-b")

    assert primeiro.produtos[1].quantidade == antes - 2
    assert len(primeiro.processados) == 1


def test_estado_e_lido_do_banco_a_cada_consulta(tmp_path):
    """Duas instâncias (ex.: terminal e web) enxergam as alterações uma da outra."""
    banco_terminal = Banco(tmp_path / "estoque.db")
    banco_web = Banco(tmp_path / "estoque.db")
    terminal, web = RepositorioEstoque(banco_terminal), RepositorioEstoque(banco_web)

    web.repor(1, 5)

    assert terminal.produtos[1].quantidade == web.produtos[1].quantidade
