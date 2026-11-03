import json
import os
from pathlib import Path

from src.venda import Venda

# sistema-vendas/src/exportador.py -> parents[2] é a raiz do repositório
PASTA_SAIDA = Path(__file__).resolve().parents[2] / "integracao" / "saida"


def venda_para_dict(venda: Venda) -> dict:
    """Monta o JSON combinado com o Sistema de Estoque."""
    return {
        "venda_id": venda.venda_id,
        "data_hora": venda.data_hora.isoformat(),
        "itens": [
            {"produto_id": item.produto.produto_id, "quantidade": item.qnt}
            for item in venda.itens
        ],
    }


def exportar_venda(venda: Venda, pasta: Path = PASTA_SAIDA) -> Path:
    """Grava a venda em `pasta` como venda_<id>.json (RF01).

    Escreve primeiro num .tmp e depois renomeia, para que a Transferência
    (que só olha *.json) nunca pegue um arquivo pela metade.
    """
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f"venda_{venda.venda_id:06d}.json"
    temporario = destino.with_suffix(".tmp")
    temporario.write_text(
        json.dumps(venda_para_dict(venda), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    os.replace(temporario, destino)
    return destino
