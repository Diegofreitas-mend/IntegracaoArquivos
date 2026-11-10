from datetime import datetime
from decimal import Decimal

from .item_venda import ItemVenda


class Venda:
    def __init__(self, venda_id: int, itens: list[ItemVenda]):
        if type(venda_id) is not int or venda_id <= 0:
            raise ValueError("O ID da venda deve ser um inteiro positivo.")
        if not itens:
            raise ValueError("Adicione ao menos um produto à venda.")
        self.venda_id = venda_id
        self.itens = itens
        self.data_hora = datetime.now().astimezone().isoformat(timespec="seconds")

    def calcular_total(self) -> float:
        return float(
            sum(
                (Decimal(str(item.calcular_subtotal())) for item in self.itens),
                Decimal(0),
            )
        )

    def para_dict(self) -> dict:
        """O estoque consome IDs e quantidades; os demais campos compõem o histórico."""
        return {
            "venda_id": self.venda_id,
            "data_hora": self.data_hora,
            "itens": [
                {
                    "produto_id": item.produto.produto_id,
                    "nome": item.produto.nome,
                    "preco": item.produto.preco,
                    "quantidade": item.qnt,
                    "subtotal": item.calcular_subtotal(),
                }
                for item in self.itens
            ],
            "total": self.calcular_total(),
        }
