from pathlib import Path

from banco import Banco

from .item_venda import ItemVenda
from .produto import Produto
from .repositorio_vendas import RepositorioVendas
from .venda import Venda

CATALOGO_INICIAL = ((1, "Mouse", 79.90), (2, "Teclado", 149.90), (3, "Monitor", 899.90))
PRECOS_INICIAIS = {pid: preco for pid, _, preco in CATALOGO_INICIAL}


class ServicoVendas:
    def __init__(self, raiz: Path):
        self.banco = Banco.do_projeto(raiz, raiz / "sistema-vendas" / "data" / "vendas.db")
        self.repositorio = RepositorioVendas(
            self.banco, raiz / "integracao" / "saida", PRECOS_INICIAIS
        )

    def carregar_precos(self) -> dict[int, float]:
        return self.repositorio.precos()

    def definir_preco(self, produto: dict, preco) -> None:
        validado = Produto(produto["produto_id"], produto["nome"], preco)
        self.repositorio.definir_preco(validado.produto_id, validado.preco)

    def catalogo_terminal(self) -> list[dict]:
        """Catálogo local de demonstração, sem importar ou consultar o estoque.

        A disponibilidade é validada pelo consumidor do JSON. Na interface web,
        o catálogo recebido por criar() inclui o saldo e permite a pré-validação.
        """
        precos = self.carregar_precos()
        return [
            {"produto_id": pid, "nome": nome, "preco": precos.get(pid, preco)}
            for pid, nome, preco in CATALOGO_INICIAL
        ]

    def catalogo(
        self, produtos: list[dict], vendas: list[dict], finalizadas: set[int]
    ) -> list[dict]:
        reservas: dict[int, int] = {}
        for venda in vendas:
            if venda["venda_id"] in finalizadas:
                continue
            for item in venda["itens"]:
                pid = item["produto_id"]
                reservas[pid] = reservas.get(pid, 0) + item["quantidade"]
        precos = self.carregar_precos()
        return [
            dict(
                p,
                preco=precos.get(p["produto_id"]),
                reservado=reservas.get(p["produto_id"], 0),
                disponivel=max(0, p["quantidade"] - reservas.get(p["produto_id"], 0)),
            )
            for p in produtos
        ]

    def criar(
        self, itens, catalogo: list[dict], ids_existentes: set[int] | None = None
    ) -> dict:
        if not isinstance(itens, list) or not itens:
            raise ValueError("Adicione ao menos um produto à venda.")
        produtos = {p["produto_id"]: p for p in catalogo}
        quantidades: dict[int, int] = {}
        for item in itens:
            if not isinstance(item, dict):
                raise ValueError("Item de venda inválido.")
            pid, quantidade = item.get("produto_id"), item.get("quantidade")
            if type(pid) is not int or pid not in produtos:
                raise ValueError("Produto não encontrado no catálogo.")
            if type(quantidade) is not int or quantidade <= 0:
                raise ValueError("A quantidade deve ser um inteiro maior que zero.")
            quantidades[pid] = quantidades.get(pid, 0) + quantidade

        itens_venda = []
        for pid, quantidade in quantidades.items():
            produto = produtos[pid]
            disponivel = produto.get("disponivel")
            if disponivel is not None and quantidade > disponivel:
                raise ValueError(
                    f"Saldo insuficiente para {produto['nome']}. Disponível: {disponivel}."
                )
            if produto["preco"] is None:
                raise ValueError(
                    f"Defina o preço de {produto['nome']} antes de vender."
                )
            itens_venda.append(
                ItemVenda(Produto(pid, produto["nome"], produto["preco"]), quantidade)
            )

        historico = self.repositorio.listar()
        ids = (
            {v["venda_id"] for v in historico}
            | self.repositorio.ids_na_saida()
            | (ids_existentes or set())
        )
        proximo_id = max(ids | {1000}) + 1
        venda = Venda(proximo_id, itens_venda).para_dict()
        self.repositorio.salvar(venda)
        return venda
