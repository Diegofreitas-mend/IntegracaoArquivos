from datetime import datetime

from src.item_venda import ItemVenda


class Venda:
    def __init__(self, venda_id: int, itens: list[ItemVenda], data_hora: datetime | None = None):
        self.venda_id = venda_id
        self.itens = itens
        self.data_hora = data_hora or datetime.now().replace(microsecond=0)

    def calcular_total(self) -> float:
        return sum(item.calcular_subtotal() for item in self.itens)
