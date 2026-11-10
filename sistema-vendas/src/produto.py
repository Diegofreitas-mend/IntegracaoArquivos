from decimal import Decimal, InvalidOperation


class Produto:
    def __init__(self, produto_id: int, nome: str, preco: float):
        if type(produto_id) is not int or produto_id <= 0:
            raise ValueError("O ID do produto deve ser um inteiro positivo.")
        if not isinstance(nome, str) or not nome.strip():
            raise ValueError("Informe o nome do produto.")
        try:
            valor = Decimal(str(preco))
        except InvalidOperation as erro:
            raise ValueError("Informe um preço válido.") from erro
        if (
            not valor.is_finite()
            or not 0 < valor <= Decimal("9999999.99")
            or valor != valor.quantize(Decimal("0.01"))
        ):
            raise ValueError("O preço deve ser positivo e ter até duas casas decimais.")
        self.produto_id = produto_id
        self.nome = nome.strip()
        self.preco = float(valor)
