from dataclasses import dataclass
from pathlib import Path

# sistema-estoque/src/config.py -> parents[2] é a raiz do repositório
RAIZ_REPOSITORIO = Path(__file__).resolve().parents[2]
RAIZ_ESTOQUE = RAIZ_REPOSITORIO / "sistema-estoque"


@dataclass(frozen=True)
class Pastas:
    """Pastas usadas pelo Sistema de Estoque.

    As pastas de integração ficam na raiz do repositório (integracao/) e são
    compartilhadas com o Sistema de Vendas e o componente de Transferência.
    """

    entrada: Path
    processados: Path
    erros: Path
    arquivo_estoque: Path
    arquivo_log: Path

    @classmethod
    def padrao(cls) -> "Pastas":
        return cls.no_projeto(RAIZ_REPOSITORIO)

    @classmethod
    def no_projeto(cls, raiz: Path) -> "Pastas":
        raiz = Path(raiz)
        integracao = raiz / "integracao"
        return cls(
            entrada=integracao / "entrada",
            processados=integracao / "processados",
            erros=integracao / "erros",
            arquivo_estoque=raiz / "sistema-estoque" / "data" / "estoque.json",
            arquivo_log=raiz / "sistema-estoque" / "logs" / "estoque.log",
        )

    @classmethod
    def dentro_de(cls, base: Path) -> "Pastas":
        """Cria a estrutura toda dentro de `base` (útil para testes)."""
        return cls(
            entrada=base / "entrada",
            processados=base / "processados",
            erros=base / "erros",
            arquivo_estoque=base / "data" / "estoque.json",
            arquivo_log=base / "logs" / "estoque.log",
        )

    def criar(self) -> None:
        for pasta in (self.entrada, self.processados, self.erros):
            pasta.mkdir(parents=True, exist_ok=True)
        self.arquivo_estoque.parent.mkdir(parents=True, exist_ok=True)
        self.arquivo_log.parent.mkdir(parents=True, exist_ok=True)
