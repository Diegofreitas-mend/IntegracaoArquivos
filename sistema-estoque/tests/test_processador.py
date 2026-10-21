import json

import pytest

from src.config import Pastas
from src.processador import Status, processar_arquivo, processar_pendentes
from src.repositorio_estoque import RepositorioEstoque


@pytest.fixture
def pastas(tmp_path):
    p = Pastas.dentro_de(tmp_path)
    p.criar()
    return p


@pytest.fixture
def repo(pastas):
    return RepositorioEstoque(pastas.arquivo_estoque)


def escrever_venda(pastas, nome, venda_id, itens):
    caminho = pastas.entrada / nome
    caminho.write_text(
        json.dumps({"venda_id": venda_id, "data_hora": "2026-10-20T10:00:00", "itens": itens}),
        encoding="utf-8",
    )
    return caminho


def test_arquivo_valido_atualiza_estoque_e_vai_para_processados(pastas, repo):
    antes = repo.produtos[1].quantidade
    caminho = escrever_venda(pastas, "venda_1.json", 1, [{"produto_id": 1, "quantidade": 4}])

    resultado = processar_arquivo(caminho, repo, pastas)

    assert resultado.status is Status.PROCESSADO
    assert repo.produtos[1].quantidade == antes - 4
    assert not caminho.exists()
    assert (pastas.processados / "venda_1.json").exists()


def test_json_malformado_vai_para_erros(pastas, repo):
    caminho = pastas.entrada / "ruim.json"
    caminho.write_text('{ "venda_id": 1, "itens": [', encoding="utf-8")

    resultado = processar_arquivo(caminho, repo, pastas)

    assert resultado.status is Status.ERRO
    assert "malformado" in resultado.motivo
    assert (pastas.erros / "ruim.json").exists()


def test_arquivo_que_nao_e_utf8_vai_para_erros(pastas, repo):
    caminho = pastas.entrada / "binario.json"
    caminho.write_bytes(b"\xff\xfe\x00\x01")

    resultado = processar_arquivo(caminho, repo, pastas)

    assert resultado.status is Status.ERRO
    assert (pastas.erros / "binario.json").exists()


def test_produto_inexistente_nao_altera_estoque(pastas, repo):
    antes = [vars(p).copy() for p in repo.listar()]
    caminho = escrever_venda(pastas, "v.json", 2, [{"produto_id": 999, "quantidade": 1}])

    resultado = processar_arquivo(caminho, repo, pastas)

    assert resultado.status is Status.ERRO
    assert [vars(p) for p in repo.listar()] == antes
    assert (pastas.erros / "v.json").exists()


def test_quantidade_invalida_vai_para_erros(pastas, repo):
    caminho = escrever_venda(pastas, "v.json", 3, [{"produto_id": 1, "quantidade": 0}])

    resultado = processar_arquivo(caminho, repo, pastas)

    assert resultado.status is Status.ERRO
    assert (pastas.erros / "v.json").exists()


def test_item_invalido_no_meio_nao_baixa_nenhum_item(pastas, repo):
    antes = repo.produtos[1].quantidade
    itens = [{"produto_id": 1, "quantidade": 2}, {"produto_id": 999, "quantidade": 1}]
    caminho = escrever_venda(pastas, "v.json", 4, itens)

    processar_arquivo(caminho, repo, pastas)

    assert repo.produtos[1].quantidade == antes  # tudo ou nada


def test_mesmo_arquivo_reenviado_nao_e_processado_de_novo(pastas, repo):
    itens = [{"produto_id": 1, "quantidade": 2}]
    primeiro = escrever_venda(pastas, "venda_5.json", 5, itens)
    processar_arquivo(primeiro, repo, pastas)
    depois_do_primeiro = repo.produtos[1].quantidade

    # mesmo nome e mesmo conteúdo chegam outra vez
    segundo = escrever_venda(pastas, "venda_5.json", 5, itens)
    resultado = processar_arquivo(segundo, repo, pastas)

    assert resultado.status is Status.DUPLICADO
    assert repo.produtos[1].quantidade == depois_do_primeiro
    assert len(list(pastas.erros.glob("venda_5*.json"))) == 1


def test_mesma_venda_em_arquivo_com_outro_nome_e_duplicada(pastas, repo):
    itens = [{"produto_id": 1, "quantidade": 2}]
    processar_arquivo(escrever_venda(pastas, "a.json", 6, itens), repo, pastas)
    quantidade = repo.produtos[1].quantidade

    # mesmo venda_id, conteúdo diferente (ex.: item extra) e nome diferente
    outro = escrever_venda(pastas, "b.json", 6, itens + [{"produto_id": 2, "quantidade": 1}])
    resultado = processar_arquivo(outro, repo, pastas)

    assert resultado.status is Status.DUPLICADO
    assert repo.produtos[1].quantidade == quantidade


def test_duplicidade_sobrevive_a_reinicio(pastas, repo):
    itens = [{"produto_id": 1, "quantidade": 2}]
    processar_arquivo(escrever_venda(pastas, "a.json", 8, itens), repo, pastas)

    repo_novo = RepositorioEstoque(pastas.arquivo_estoque)  # "reabre" o sistema
    resultado = processar_arquivo(escrever_venda(pastas, "a.json", 8, itens), repo_novo, pastas)

    assert resultado.status is Status.DUPLICADO


def test_erro_em_um_arquivo_nao_interrompe_os_demais(pastas, repo):
    (pastas.entrada / "1_ruim.json").write_text("nada de json", encoding="utf-8")
    escrever_venda(pastas, "2_boa.json", 9, [{"produto_id": 1, "quantidade": 1}])

    resultados = processar_pendentes(repo, pastas)

    assert [r.status for r in resultados] == [Status.ERRO, Status.PROCESSADO]


def test_ignora_arquivos_que_nao_sao_json(pastas, repo):
    (pastas.entrada / "anotacoes.txt").write_text("oi", encoding="utf-8")

    assert processar_pendentes(repo, pastas) == []
    assert (pastas.entrada / "anotacoes.txt").exists()
