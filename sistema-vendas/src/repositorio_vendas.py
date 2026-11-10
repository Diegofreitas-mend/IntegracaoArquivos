import json
import os
from pathlib import Path


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
    def __init__(self, pasta_dados: Path, pasta_saida: Path):
        self.pasta_dados = pasta_dados
        self.pasta_saida = pasta_saida

    def listar(self) -> list[dict]:
        return sorted(
            (
                json.loads(p.read_text(encoding="utf-8"))
                for p in self.pasta_dados.glob("venda_*.json")
            ),
            key=lambda venda: venda["venda_id"],
            reverse=True,
        )

    def salvar(self, venda: dict) -> None:
        nome = f"venda_{venda['venda_id']}.json"
        # O histórico é a fonte durável. Se a exportação falhar, sincronizar
        # pode tentar novamente usando exatamente a mesma venda e o mesmo ID.
        gravar_json(self.pasta_dados / nome, venda)
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
