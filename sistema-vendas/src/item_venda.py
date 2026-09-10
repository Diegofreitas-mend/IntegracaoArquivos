from src.produto import Produto


class ItemVenda:
    def __init__(self, produto: Produto, qnt: int):
        self.produto = produto
        self.qnt = qnt

    def calcular_subtotal(self) -> float:
        return self.qnt * self.produto.preco
