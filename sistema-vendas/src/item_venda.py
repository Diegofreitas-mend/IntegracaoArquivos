from decimal import Decimal, ROUND_HALF_UP

from .produto import Produto


class ItemVenda:
    def __init__(self, produto: Produto, qnt: int):
        if type(qnt) is not int or qnt <= 0:
            raise ValueError("A quantidade deve ser um inteiro maior que zero.")
        self.produto = produto
        self.qnt = qnt

    def calcular_subtotal(self) -> float:
        valor = Decimal(str(self.produto.preco)) * self.qnt
        return float(valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
