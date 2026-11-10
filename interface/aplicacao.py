from importlib import import_module
from pathlib import Path

# Os diretórios originais possuem hífen e ambos usam um pacote chamado src.
# Importar pelo caminho completo mantém os dois sistemas isolados e preserva o CLI.
ServicoEstoque = import_module("sistema-estoque.src.servico").ServicoEstoque
ServicoVendas = import_module("sistema-vendas.src.servico").ServicoVendas
ErroRepositorio = import_module(
    "sistema-estoque.src.repositorio_estoque"
).ErroRepositorio
ErroExportacao = import_module(
    "sistema-vendas.src.repositorio_vendas"
).ErroExportacao


class Aplicacao:
    def __init__(self, raiz: Path):
        self.estoque = ServicoEstoque(raiz)
        self.vendas = ServicoVendas(raiz)

    def estado(self) -> dict:
        repo = self.estoque.repositorio()
        processados = {p["venda_id"] for p in repo.processados}
        rejeitados = self.estoque.rejeitados()
        arquivos = self.estoque.arquivos()
        pendentes = set(arquivos["saida"]) | set(arquivos["entrada"])
        vendas = self.vendas.repositorio.listar()
        historico = []
        for venda in vendas:
            pid = venda["venda_id"]
            nome = f"venda_{pid}.json"
            if pid in processados:
                status = "processado"
            elif nome in pendentes:
                status = "pendente"
            elif pid in rejeitados:
                status = "erro"
            else:
                status = "exportacao_pendente"
            historico.append(dict(venda, status=status))
        return {
            "produtos": self.vendas.catalogo(
                [vars(p) for p in repo.listar()], vendas, processados | rejeitados
            ),
            "vendas": historico,
            "arquivos": arquivos,
            "movimentacoes": list(reversed(repo.processados)),
        }

    def executar(self, caminho: str, dados: dict) -> dict:
        if caminho == "/api/vendas":
            estado = self.estado()
            ids = {
                p["venda_id"] for p in estado["movimentacoes"]
            } | self.estoque.rejeitados()
            try:
                venda = self.vendas.criar(dados.get("itens"), estado["produtos"], ids)
            except ErroExportacao as erro:
                return {"mensagem": str(erro), "venda": erro.venda, "aviso": True}
            return {
                "mensagem": f"Venda #{venda['venda_id']} registrada e enviada para integração.",
                "venda": venda,
            }
        if caminho == "/api/sincronizar":
            # Recupera vendas salvas cujo arquivo não chegou a ser exportado.
            for venda in self.estado()["vendas"]:
                if venda["status"] == "exportacao_pendente":
                    original = {k: v for k, v in venda.items() if k != "status"}
                    self.vendas.repositorio.exportar(original)
            resultados = self.estoque.sincronizar()
            return {
                "mensagem": (
                    "Sincronização concluída."
                    if resultados
                    else "Tudo em dia. Nenhuma venda pendente."
                ),
                "resultados": resultados,
            }
        if caminho == "/api/processar":
            resultados = self.estoque.processar()
            return {
                "mensagem": (
                    "Processamento concluído."
                    if resultados
                    else "Nenhum arquivo na entrada."
                ),
                "resultados": resultados,
            }
        if caminho == "/api/produtos":
            self.estoque.repositorio().cadastrar_produto(
                dados.get("produto_id"), dados.get("nome"), dados.get("quantidade", 0)
            )
            return {
                "mensagem": "Produto cadastrado. Defina o preço no catálogo de vendas para começar a vender."
            }
        if caminho == "/api/reposicoes":
            self.estoque.repositorio().repor(
                dados.get("produto_id"), dados.get("quantidade")
            )
            return {"mensagem": "Reposição registrada com sucesso."}
        if caminho == "/api/precos":
            pid = dados.get("produto_id")
            produtos = self.estoque.repositorio().produtos
            produto = produtos.get(pid) if type(pid) is int else None
            if produto is None:
                raise ValueError("Produto não encontrado.")
            self.vendas.definir_preco(vars(produto), dados.get("preco"))
            return {"mensagem": "Preço atualizado."}
        raise LookupError("Operação não encontrada.")
