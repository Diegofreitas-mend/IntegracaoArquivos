import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from src.item_venda import ItemVenda
from src.produto import Produto
from src.venda import Venda

# sistema-vendas/src/banco_dados.py -> parents[1] é a pasta sistema-vendas
CAMINHO_PADRAO = Path(__file__).resolve().parents[1] / "data" / "vendas.db"

# Mesmos IDs do Sistema de Estoque, para que as vendas geradas sejam aceitas lá.
PRODUTOS_INICIAIS = [
    Produto(1, "Mouse", 79.90),
    Produto(2, "Teclado", 149.90),
    Produto(3, "Monitor", 899.00),
]

ESQUEMA = """
CREATE TABLE IF NOT EXISTS produtos (
    produto_id INTEGER PRIMARY KEY,
    nome       TEXT    NOT NULL,
    preco      REAL    NOT NULL CHECK (preco >= 0)
);

CREATE TABLE IF NOT EXISTS vendas (
    venda_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    data_hora TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS itens_venda (
    venda_id       INTEGER NOT NULL REFERENCES vendas (venda_id),
    produto_id     INTEGER NOT NULL REFERENCES produtos (produto_id),
    quantidade     INTEGER NOT NULL CHECK (quantidade > 0),
    preco_unitario REAL    NOT NULL,
    PRIMARY KEY (venda_id, produto_id)
);
"""


class ErroBancoDados(Exception):
    """Operação inválida ou falha ao acessar o banco de vendas."""


class BancoVendas:
    """Persiste produtos e vendas do Sistema de Vendas em SQLite.

    O preço de cada item é gravado no momento da venda (preco_unitario), então
    alterar o preço de um produto depois não muda o total de vendas antigas.
    """

    def __init__(self, caminho: Path = CAMINHO_PADRAO):
        self.caminho = Path(caminho)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        with self._conectar() as conexao:
            conexao.executescript(ESQUEMA)
            vazio = conexao.execute("SELECT COUNT(*) FROM produtos").fetchone()[0] == 0
            if vazio:
                conexao.executemany(
                    "INSERT INTO produtos (produto_id, nome, preco) VALUES (?, ?, ?)",
                    [(p.produto_id, p.nome, p.preco) for p in PRODUTOS_INICIAIS],
                )

    @contextmanager
    def _conectar(self):
        """Abre uma conexão, confirma tudo no fim (ou desfaz se der erro) e fecha."""
        conexao = sqlite3.connect(self.caminho)
        conexao.execute("PRAGMA foreign_keys = ON")
        try:
            with conexao:  # commit / rollback automático
                yield conexao
        except sqlite3.Error as erro:
            raise ErroBancoDados(f"erro no banco de vendas: {erro}") from erro
        finally:
            conexao.close()

    # ---------- produtos ----------

    def listar_produtos(self) -> list[Produto]:
        with self._conectar() as conexao:
            linhas = conexao.execute(
                "SELECT produto_id, nome, preco FROM produtos ORDER BY produto_id"
            ).fetchall()
        return [Produto(*linha) for linha in linhas]

    def buscar_produto(self, produto_id: int) -> Produto | None:
        with self._conectar() as conexao:
            linha = conexao.execute(
                "SELECT produto_id, nome, preco FROM produtos WHERE produto_id = ?",
                (produto_id,),
            ).fetchone()
        return Produto(*linha) if linha else None

    def cadastrar_produto(self, produto_id: int, nome: str, preco: float) -> Produto:
        if not nome.strip():
            raise ErroBancoDados("nome não pode ser vazio")
        if preco < 0:
            raise ErroBancoDados("preço não pode ser negativo")
        if self.buscar_produto(produto_id) is not None:
            raise ErroBancoDados(f"produto {produto_id} já existe")
        with self._conectar() as conexao:
            conexao.execute(
                "INSERT INTO produtos (produto_id, nome, preco) VALUES (?, ?, ?)",
                (produto_id, nome.strip(), preco),
            )
        return Produto(produto_id, nome.strip(), preco)

    # ---------- vendas ----------

    def registrar_venda(self, itens: list[tuple[int, int]]) -> Venda:
        """Grava uma venda a partir de pares (produto_id, quantidade).

        Venda e itens são gravados na mesma transação: ou entra tudo, ou nada.
        """
        if not itens:
            raise ErroBancoDados("a venda precisa ter pelo menos um item")

        quantidades: dict[int, int] = {}
        for produto_id, quantidade in itens:
            if quantidade <= 0:
                raise ErroBancoDados(f"quantidade inválida para o produto {produto_id}")
            # o mesmo produto informado duas vezes vira um único item
            quantidades[produto_id] = quantidades.get(produto_id, 0) + quantidade

        data_hora = datetime.now().replace(microsecond=0)
        with self._conectar() as conexao:
            itens_venda = []
            for produto_id, quantidade in quantidades.items():
                linha = conexao.execute(
                    "SELECT produto_id, nome, preco FROM produtos WHERE produto_id = ?",
                    (produto_id,),
                ).fetchone()
                if linha is None:
                    raise ErroBancoDados(f"produto {produto_id} não existe")
                itens_venda.append(ItemVenda(Produto(*linha), quantidade))

            cursor = conexao.execute(
                "INSERT INTO vendas (data_hora) VALUES (?)", (data_hora.isoformat(),)
            )
            venda_id = cursor.lastrowid
            conexao.executemany(
                "INSERT INTO itens_venda (venda_id, produto_id, quantidade, preco_unitario) "
                "VALUES (?, ?, ?, ?)",
                [(venda_id, i.produto.produto_id, i.qnt, i.produto.preco) for i in itens_venda],
            )
        return Venda(venda_id, itens_venda, data_hora)

    def buscar_venda(self, venda_id: int) -> Venda | None:
        with self._conectar() as conexao:
            return self._montar_venda(conexao, venda_id)

    def listar_vendas(self) -> list[Venda]:
        with self._conectar() as conexao:
            ids = conexao.execute("SELECT venda_id FROM vendas ORDER BY venda_id").fetchall()
            return [self._montar_venda(conexao, venda_id) for (venda_id,) in ids]

    def _montar_venda(self, conexao: sqlite3.Connection, venda_id: int) -> Venda | None:
        linha = conexao.execute(
            "SELECT data_hora FROM vendas WHERE venda_id = ?", (venda_id,)
        ).fetchone()
        if linha is None:
            return None
        itens = conexao.execute(
            "SELECT p.produto_id, p.nome, i.preco_unitario, i.quantidade "
            "FROM itens_venda i JOIN produtos p ON p.produto_id = i.produto_id "
            "WHERE i.venda_id = ? ORDER BY p.produto_id",
            (venda_id,),
        ).fetchall()
        return Venda(
            venda_id,
            [ItemVenda(Produto(pid, nome, preco), qnt) for pid, nome, preco, qnt in itens],
            datetime.fromisoformat(linha[0]),
        )
