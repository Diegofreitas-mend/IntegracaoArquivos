import json
import os
from pathlib import Path

from banco import Banco, ErroIntegridade

TABELAS = {
    "vendas_precos": "produto_id INTEGER PRIMARY KEY, preco NUMERIC NOT NULL CHECK (preco > 0)",
    "vendas": "venda_id INTEGER PRIMARY KEY, data_hora TEXT NOT NULL, total NUMERIC NOT NULL",
    # Nome e preço ficam copiados no item: alterar o catálogo depois não muda
    # vendas antigas. A posição preserva a ordem do pedido no JSON exportado.
    "vendas_itens": (
        "venda_id INTEGER NOT NULL REFERENCES vendas (venda_id), "
        "posicao INTEGER NOT NULL, "
        "produto_id INTEGER NOT NULL, "
        "nome TEXT NOT NULL, "
        "preco NUMERIC NOT NULL, "
        "quantidade INTEGER NOT NULL CHECK (quantidade > 0), "
        "subtotal NUMERIC NOT NULL, "
        "PRIMARY KEY (venda_id, posicao), "
        "UNIQUE (venda_id, produto_id)"
    ),
}


def gravar_json(caminho: Path, dados) -> None:
    """Publica somente arquivos completos, inclusive na pasta de integração."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(".tmp")
    temporario.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    os.replace(temporario, caminho)


class ErroExportacao(OSError):
    """A venda está salva; somente o envio do JSON precisa ser repetido."""

    def __init__(self, venda: dict):
        super().__init__(
            f"Venda #{venda['venda_id']} salva. A exportação está pendente; "
            "use Sincronizar vendas para reenviar sem registrar outro pedido."
        )
        self.venda = venda


class RepositorioVendas:
    def __init__(self, banco: Banco, pasta_saida: Path, precos_iniciais: dict[int, float]):
        self.banco = banco
        self.pasta_saida = pasta_saida
        if banco.preparar(TABELAS):
            with banco.transacao() as t:
                if t.um("SELECT COUNT(*) FROM vendas_precos")[0] == 0:
                    t.varios(
                        "INSERT INTO vendas_precos (produto_id, preco) VALUES (?, ?)",
                        precos_iniciais.items(),
                    )

    # ---------- preços ----------

    def precos(self) -> dict[int, float]:
        with self.banco.transacao() as t:
            linhas = t.todos("SELECT produto_id, preco FROM vendas_precos")
        return {pid: float(preco) for pid, preco in linhas}

    def definir_preco(self, produto_id: int, preco: float) -> None:
        with self.banco.transacao() as t:
            t.executar(
                "INSERT INTO vendas_precos (produto_id, preco) VALUES (?, ?) "
                "ON CONFLICT (produto_id) DO UPDATE SET preco = excluded.preco",
                (produto_id, preco),
            )

    # ---------- vendas ----------

    def listar(self) -> list[dict]:
        with self.banco.transacao() as t:
            vendas = t.todos("SELECT venda_id, data_hora, total FROM vendas ORDER BY venda_id DESC")
            itens = t.todos(
                "SELECT venda_id, produto_id, nome, preco, quantidade, subtotal "
                "FROM vendas_itens ORDER BY venda_id, posicao"
            )
        por_venda: dict[int, list[dict]] = {}
        for venda_id, produto_id, nome, preco, quantidade, subtotal in itens:
            por_venda.setdefault(venda_id, []).append(
                {
                    "produto_id": produto_id,
                    "nome": nome,
                    "preco": float(preco),
                    "quantidade": quantidade,
                    "subtotal": float(subtotal),
                }
            )
        # Mesmo formato de Venda.para_dict(), usado também na exportação.
        return [
            {
                "venda_id": venda_id,
                "data_hora": data_hora,
                "itens": por_venda.get(venda_id, []),
                "total": float(total),
            }
            for venda_id, data_hora, total in vendas
        ]

    def salvar(self, venda: dict) -> None:
        # O histórico no banco é a fonte durável. Se a exportação falhar,
        # sincronizar pode tentar novamente usando a mesma venda e o mesmo ID.
        try:
            with self.banco.transacao() as t:
                t.executar(
                    "INSERT INTO vendas (venda_id, data_hora, total) VALUES (?, ?, ?)",
                    (venda["venda_id"], venda["data_hora"], venda["total"]),
                )
                t.varios(
                    "INSERT INTO vendas_itens "
                    "(venda_id, posicao, produto_id, nome, preco, quantidade, subtotal) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    [
                        (
                            venda["venda_id"],
                            posicao,
                            item["produto_id"],
                            item["nome"],
                            item["preco"],
                            item["quantidade"],
                            item["subtotal"],
                        )
                        for posicao, item in enumerate(venda["itens"], start=1)
                    ],
                )
        except ErroIntegridade as erro:
            # Outro terminal registrou uma venda com o mesmo número ao mesmo tempo.
            raise ValueError(
                f"O número de venda #{venda['venda_id']} acabou de ser usado. "
                "Registre o pedido novamente."
            ) from erro
        try:
            self.exportar(venda)
        except (OSError, ValueError) as erro:
            raise ErroExportacao(venda) from erro

    def ids_na_saida(self) -> set[int]:
        ids = set()
        for arquivo in self.pasta_saida.glob("venda_*.json"):
            try:
                ids.add(int(arquivo.stem.removeprefix("venda_")))
            except ValueError:
                continue
        return ids

    def exportar(self, venda: dict) -> None:
        caminho = self.pasta_saida / f"venda_{venda['venda_id']}.json"
        if caminho.exists():
            if json.loads(caminho.read_text(encoding="utf-8")) == venda:
                return
            raise FileExistsError(
                f"Já existe um arquivo diferente com o nome {caminho.name}; nenhum arquivo foi sobrescrito."
            )
        gravar_json(caminho, venda)
