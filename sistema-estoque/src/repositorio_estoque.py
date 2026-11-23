from datetime import datetime

from banco import MAIOR_ID, Banco, ErroIntegridade

from .produto_estoque import ProdutoEstoque
from .venda_recebida import VendaRecebida

PRODUTOS_INICIAIS = [
    ProdutoEstoque(1, "Mouse", 50),
    ProdutoEstoque(2, "Teclado", 30),
    ProdutoEstoque(3, "Monitor", 20),
]

TABELAS = {
    "estoque_produtos": (
        "produto_id INTEGER PRIMARY KEY, "
        "nome TEXT NOT NULL, "
        "quantidade INTEGER NOT NULL CHECK (quantidade >= 0)"
    ),
    # RF05: venda_id e hash são únicos, então o próprio banco recusa uma
    # segunda baixa da mesma venda, mesmo vinda de outro processo.
    "estoque_processados": (
        "venda_id INTEGER PRIMARY KEY, "
        "arquivo TEXT NOT NULL, "
        "hash TEXT NOT NULL UNIQUE, "
        "processado_em TEXT NOT NULL"
    ),
}


class ErroRepositorio(Exception):
    """Operação de estoque inválida."""


class RepositorioEstoque:
    """Guarda produtos e o controle de arquivos já processados no banco de dados.

    A baixa do estoque e o registro do arquivo acontecem na MESMA transação.
    Assim, é impossível o estoque ser atualizado sem o arquivo ser marcado como
    processado (ou o contrário) se o programa cair no meio, o que protege
    contra baixa em dobro (RF05).
    """

    def __init__(self, banco: Banco):
        self.banco = banco
        if banco.preparar(TABELAS):
            with banco.transacao() as t:
                if t.um("SELECT COUNT(*) FROM estoque_produtos")[0] == 0:
                    t.varios(
                        "INSERT INTO estoque_produtos (produto_id, nome, quantidade) VALUES (?, ?, ?)",
                        [(p.produto_id, p.nome, p.quantidade) for p in PRODUTOS_INICIAIS],
                    )

    # ---------- consultas ----------

    def listar(self) -> list[ProdutoEstoque]:
        with self.banco.transacao() as t:
            linhas = t.todos(
                "SELECT produto_id, nome, quantidade FROM estoque_produtos ORDER BY produto_id"
            )
        return [ProdutoEstoque(*linha) for linha in linhas]

    @property
    def produtos(self) -> dict[int, ProdutoEstoque]:
        return {p.produto_id: p for p in self.listar()}

    @property
    def processados(self) -> list[dict]:
        with self.banco.transacao() as t:
            linhas = t.todos(
                "SELECT arquivo, hash, venda_id, processado_em FROM estoque_processados "
                "ORDER BY processado_em, venda_id"
            )
        return [
            {"arquivo": arquivo, "hash": hash_, "venda_id": venda_id, "processado_em": quando}
            for arquivo, hash_, venda_id, quando in linhas
        ]

    def motivo_duplicidade(self, hash_arquivo: str, venda_id: int | None = None) -> str | None:
        """Retorna o motivo se o arquivo/venda já foi processado, senão None."""
        with self.banco.transacao() as t:
            registro = t.um(
                "SELECT arquivo, processado_em FROM estoque_processados WHERE hash = ?",
                (hash_arquivo,),
            )
            if registro:
                return (
                    f"conteúdo idêntico ao arquivo '{registro[0]}' "
                    f"já processado em {registro[1]}"
                )
            # Um ID fora da faixa do banco nunca pode ter sido gravado.
            if venda_id is not None and 0 < venda_id <= MAIOR_ID:
                registro = t.um(
                    "SELECT arquivo FROM estoque_processados WHERE venda_id = ?",
                    (venda_id,),
                )
                if registro:
                    return f"venda {venda_id} já foi processada (arquivo '{registro[0]}')"
        return None

    # ---------- alterações ----------

    def aplicar_venda(self, venda: VendaRecebida, nome_arquivo: str, hash_arquivo: str) -> None:
        """Baixa o estoque de todos os itens e registra o arquivo, numa transação só."""
        try:
            with self.banco.transacao() as t:
                for item in venda.itens:
                    # A condição no WHERE impede saldo negativo mesmo que outro
                    # processo baixe o mesmo produto ao mesmo tempo.
                    alteradas = t.executar(
                        "UPDATE estoque_produtos SET quantidade = quantidade - ? "
                        "WHERE produto_id = ? AND quantidade >= ?",
                        (item.quantidade, item.produto_id, item.quantidade),
                    )
                    if alteradas == 0:
                        raise ErroRepositorio(
                            f"estoque negativo para o produto {item.produto_id}"
                        )
                t.executar(
                    "INSERT INTO estoque_processados (venda_id, arquivo, hash, processado_em) "
                    "VALUES (?, ?, ?, ?)",
                    (
                        venda.venda_id,
                        nome_arquivo,
                        hash_arquivo,
                        datetime.now().isoformat(timespec="seconds"),
                    ),
                )
        except ErroIntegridade as erro:
            raise ErroRepositorio(f"venda {venda.venda_id} já foi processada") from erro

    def cadastrar_produto(self, produto_id: int, nome: str, quantidade: int = 0) -> None:
        if type(produto_id) is not int or not 0 < produto_id <= MAIOR_ID:
            raise ErroRepositorio("ID deve ser um inteiro positivo")
        if not isinstance(nome, str):
            raise ErroRepositorio("nome deve ser um texto")
        if type(quantidade) is not int:
            raise ErroRepositorio("quantidade deve ser um inteiro")
        if not nome.strip():
            raise ErroRepositorio("nome não pode ser vazio")
        if not 0 <= quantidade <= MAIOR_ID:
            raise ErroRepositorio("quantidade inicial não pode ser negativa")
        try:
            with self.banco.transacao() as t:
                t.executar(
                    "INSERT INTO estoque_produtos (produto_id, nome, quantidade) VALUES (?, ?, ?)",
                    (produto_id, nome.strip(), quantidade),
                )
        except ErroIntegridade as erro:
            raise ErroRepositorio(f"produto {produto_id} já existe") from erro

    def repor(self, produto_id: int, quantidade: int) -> None:
        if type(produto_id) is not int or type(quantidade) is not int:
            raise ErroRepositorio("ID e quantidade devem ser inteiros")
        if not 0 < quantidade <= MAIOR_ID:
            raise ErroRepositorio("quantidade de reposição deve ser maior que zero")
        if not 0 < produto_id <= MAIOR_ID:
            raise ErroRepositorio(f"produto {produto_id} não existe")
        with self.banco.transacao() as t:
            alteradas = t.executar(
                "UPDATE estoque_produtos SET quantidade = quantidade + ? WHERE produto_id = ?",
                (quantidade, produto_id),
            )
            if alteradas == 0:
                raise ErroRepositorio(f"produto {produto_id} não existe")
