import json
import os
from datetime import datetime
from pathlib import Path

from src.produto_estoque import ProdutoEstoque
from src.venda_recebida import VendaRecebida

PRODUTOS_INICIAIS = [
    ProdutoEstoque(1, "Mouse", 50),
    ProdutoEstoque(2, "Teclado", 30),
    ProdutoEstoque(3, "Monitor", 20),
]


class ErroRepositorio(Exception):
    """Problema ao ler ou gravar o arquivo de estoque."""


class RepositorioEstoque:
    """Guarda produtos e o controle de arquivos já processados num único JSON.

    Produtos e registro de processados ficam no MESMO arquivo e são gravados de
    uma vez só (escrita atômica). Assim, é impossível o estoque ser atualizado
    sem o arquivo ser marcado como processado (ou o contrário) se o programa
    cair no meio, o que protege contra baixa em dobro (RF05).
    """

    def __init__(self, caminho: Path):
        self.caminho = Path(caminho)
        self.produtos: dict[int, ProdutoEstoque] = {}
        self.processados: list[dict] = []
        if self.caminho.exists():
            self._carregar()
        else:
            self.produtos = {p.produto_id: ProdutoEstoque(**vars(p)) for p in PRODUTOS_INICIAIS}
            self._gravar(self.produtos, self.processados)

    # ---------- persistência ----------

    def _carregar(self) -> None:
        try:
            dados = json.loads(self.caminho.read_text(encoding="utf-8"))
            self.produtos = {
                p["produto_id"]: ProdutoEstoque(p["produto_id"], p["nome"], p["quantidade"])
                for p in dados["produtos"]
            }
            self.processados = list(dados.get("arquivos_processados", []))
        except (ValueError, KeyError, TypeError) as erro:
            raise ErroRepositorio(
                f"arquivo de estoque corrompido ({self.caminho}): {erro}"
            ) from erro

    def _gravar(self, produtos: dict[int, ProdutoEstoque], processados: list[dict]) -> None:
        conteudo = {
            "produtos": [vars(p) for p in sorted(produtos.values(), key=lambda p: p.produto_id)],
            "arquivos_processados": processados,
        }
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        temporario = self.caminho.with_suffix(".tmp")
        temporario.write_text(json.dumps(conteudo, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(temporario, self.caminho)  # troca atômica

    # ---------- consultas ----------

    def listar(self) -> list[ProdutoEstoque]:
        return sorted(self.produtos.values(), key=lambda p: p.produto_id)

    def motivo_duplicidade(self, hash_arquivo: str, venda_id: int | None = None) -> str | None:
        """Retorna o motivo se o arquivo/venda já foi processado, senão None."""
        for registro in self.processados:
            if registro["hash"] == hash_arquivo:
                return (
                    f"conteúdo idêntico ao arquivo '{registro['arquivo']}' "
                    f"já processado em {registro['processado_em']}"
                )
            if venda_id is not None and registro["venda_id"] == venda_id:
                return (
                    f"venda {venda_id} já foi processada "
                    f"(arquivo '{registro['arquivo']}')"
                )
        return None

    # ---------- alterações ----------

    def aplicar_venda(self, venda: VendaRecebida, nome_arquivo: str, hash_arquivo: str) -> None:
        """Baixa o estoque de todos os itens e registra o arquivo, numa gravação só."""
        novos = {pid: ProdutoEstoque(**vars(p)) for pid, p in self.produtos.items()}
        for item in venda.itens:
            novos[item.produto_id].quantidade -= item.quantidade
            if novos[item.produto_id].quantidade < 0:
                raise ErroRepositorio(f"estoque negativo para o produto {item.produto_id}")

        registros = self.processados + [
            {
                "arquivo": nome_arquivo,
                "hash": hash_arquivo,
                "venda_id": venda.venda_id,
                "processado_em": datetime.now().isoformat(timespec="seconds"),
            }
        ]
        self._gravar(novos, registros)  # se falhar, nada muda em memória
        self.produtos, self.processados = novos, registros

    def cadastrar_produto(self, produto_id: int, nome: str, quantidade: int = 0) -> None:
        if produto_id in self.produtos:
            raise ErroRepositorio(f"produto {produto_id} já existe")
        if not nome.strip():
            raise ErroRepositorio("nome não pode ser vazio")
        if quantidade < 0:
            raise ErroRepositorio("quantidade inicial não pode ser negativa")
        novos = dict(self.produtos)
        novos[produto_id] = ProdutoEstoque(produto_id, nome.strip(), quantidade)
        self._gravar(novos, self.processados)
        self.produtos = novos

    def repor(self, produto_id: int, quantidade: int) -> None:
        if produto_id not in self.produtos:
            raise ErroRepositorio(f"produto {produto_id} não existe")
        if quantidade <= 0:
            raise ErroRepositorio("quantidade de reposição deve ser maior que zero")
        novos = {pid: ProdutoEstoque(**vars(p)) for pid, p in self.produtos.items()}
        novos[produto_id].quantidade += quantidade
        self._gravar(novos, self.processados)
        self.produtos = novos
