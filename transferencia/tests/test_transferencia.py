from src.transferencia import transferir


def test_move_json_da_saida_para_entrada(tmp_path):
    saida, entrada = tmp_path / "saida", tmp_path / "entrada"
    saida.mkdir()
    (saida / "venda_000001.json").write_text("{}", encoding="utf-8")

    movidos = transferir(saida, entrada)

    assert [p.name for p in movidos] == ["venda_000001.json"]
    assert (entrada / "venda_000001.json").exists()
    assert not (saida / "venda_000001.json").exists()


def test_ignora_arquivo_temporario(tmp_path):
    saida, entrada = tmp_path / "saida", tmp_path / "entrada"
    saida.mkdir()
    (saida / "venda_000002.tmp").write_text("{", encoding="utf-8")

    assert transferir(saida, entrada) == []
    assert (saida / "venda_000002.tmp").exists()


def test_nao_sobrescreve_arquivo_no_destino(tmp_path):
    saida, entrada = tmp_path / "saida", tmp_path / "entrada"
    saida.mkdir()
    entrada.mkdir()
    (entrada / "venda_000003.json").write_text("antigo", encoding="utf-8")
    (saida / "venda_000003.json").write_text("novo", encoding="utf-8")

    transferir(saida, entrada)

    assert (entrada / "venda_000003.json").read_text(encoding="utf-8") == "antigo"
    assert len(list(entrada.glob("venda_000003_*.json"))) == 1
