from src.item_venda import ItemVenda


class Venda:
    def __init__(self, venda_id: int, itens: list[ItemVenda]):
        self.venda_id = venda_id
        self.itens = itens

    def calcular_total(self) -> float:
        return sum(item.calcular_subtotal() for item in self.itens)
