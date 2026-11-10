import json
from pathlib import Path

from .config import Pastas
from .log_config import configurar_logging
from .processador import processar_pendentes
from .repositorio_estoque import RepositorioEstoque


class ServicoEstoque:
    """Adapta as operações existentes para a interface, sem duplicar as regras."""

    def __init__(self, raiz: Path):
        integracao = raiz / "integracao"
        self.saida = integracao / "saida"
        self.saida.mkdir(parents=True, exist_ok=True)
        self.pastas = Pastas.no_projeto(raiz)
        self.pastas.criar()
        configurar_logging(self.pastas.arquivo_log, console=False)

    def repositorio(self) -> RepositorioEstoque:
        return RepositorioEstoque(self.pastas.arquivo_estoque)

    def arquivos(self) -> dict[str, list[str]]:
        return {
            nome: sorted(p.name for p in pasta.glob("*.json") if p.is_file())
            for nome, pasta in (
                ("saida", self.saida),
                ("entrada", self.pastas.entrada),
                ("processados", self.pastas.processados),
                ("erros", self.pastas.erros),
            )
        }

    def rejeitados(self) -> set[int]:
        ids = set()
        for arquivo in self.pastas.erros.glob("*.json"):
            try:
                dados = json.loads(arquivo.read_text(encoding="utf-8"))
                if isinstance(dados, dict) and type(dados.get("venda_id")) is int:
                    ids.add(dados["venda_id"])
            except (ValueError, OSError):
                continue
        return ids

    def sincronizar(self) -> list[dict]:
        for arquivo in sorted(self.saida.glob("*.json")):
            if not arquivo.is_file():
                continue
            destino = self.pastas.entrada / arquivo.name
            if destino.exists():
                raise ValueError(
                    f"Já existe {arquivo.name} na entrada. Processe a entrada antes de sincronizar."
                )
            arquivo.rename(destino)
        return self.processar()

    def processar(self) -> list[dict]:
        return [
            dict(arquivo=r.arquivo, status=r.status.value, motivo=r.motivo)
            for r in processar_pendentes(self.repositorio(), self.pastas)
        ]
