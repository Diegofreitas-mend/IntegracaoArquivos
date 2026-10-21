from dataclasses import dataclass


@dataclass(frozen=True)
class ItemRecebido:
    produto_id: int
    quantidade: int


@dataclass(frozen=True)
class VendaRecebida:
    """Venda já validada, lida de um arquivo JSON vindo do Sistema de Vendas."""

    venda_id: int | str
    data_hora: str | None
    itens: tuple[ItemRecebido, ...]
