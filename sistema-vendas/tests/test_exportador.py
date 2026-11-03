import json
from datetime import datetime

from src.exportador import exportar_venda
from src.item_venda import ItemVenda
from src.produto import Produto
from src.venda import Venda


def test_exporta_venda_no_formato_combinado(tmp_path):
    venda = Venda(
        7,
        [ItemVenda(Produto(1, "Mouse", 79.90), 2), ItemVenda(Produto(2, "Teclado", 149.90), 1)],
        datetime(2026, 10, 20, 10, 30),
    )

    arquivo = exportar_venda(venda, tmp_path)

    assert arquivo.name == "venda_000007.json"
    assert json.loads(arquivo.read_text(encoding="utf-8")) == {
        "venda_id": 7,
        "data_hora": "2026-10-20T10:30:00",
        "itens": [
            {"produto_id": 1, "quantidade": 2},
            {"produto_id": 2, "quantidade": 1},
        ],
    }
    # não sobra arquivo temporário na pasta de saída
    assert [p.name for p in tmp_path.iterdir()] == ["venda_000007.json"]
