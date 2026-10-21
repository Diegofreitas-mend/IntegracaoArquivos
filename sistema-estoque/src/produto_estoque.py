from dataclasses import dataclass


@dataclass
class ProdutoEstoque:
    produto_id: int
    nome: str
    quantidade: int
