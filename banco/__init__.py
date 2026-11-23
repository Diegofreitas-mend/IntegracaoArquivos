"""Conexão com o banco de dados dos três componentes (vendas, estoque e contas).

Com DATABASE_URL no arquivo .env da raiz, todos usam o PostgreSQL do Supabase.
Sem ele (testes e raízes de demonstração criadas com --dados), cada componente
usa um arquivo SQLite próprio. As consultas usam apenas SQL comum aos dois.

Os componentes continuam independentes: cada um cria e acessa somente as
próprias tabelas. A integração entre vendas e estoque segue por arquivos JSON.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

# Faixa do tipo INTEGER do PostgreSQL, usado nos IDs.
MAIOR_ID = 2_147_483_647


class ErroBanco(OSError):
    """O banco está indisponível ou recusou a operação."""


class ErroIntegridade(ErroBanco):
    """Uma restrição do banco foi violada, por exemplo uma chave repetida."""


def ler_url(raiz: Path) -> str | None:
    """Lê DATABASE_URL do .env da raiz. Variáveis de ambiente não são usadas,
    para que testes e raízes de demonstração nunca gravem no banco real."""
    arquivo = Path(raiz) / ".env"
    if not arquivo.is_file():
        return None
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        chave, separador, valor = linha.partition("=")
        if separador and chave.strip() == "DATABASE_URL":
            url = valor.strip().strip("\"'")
            if url and not url.startswith(("postgres://", "postgresql://")):
                raise ErroBanco(
                    "DATABASE_URL no .env deve começar com postgresql://. Use a "
                    "connection string do Supabase (botão Connect > Session pooler), "
                    "não a Project URL https://...supabase.co."
                )
            if ":[" in url and "]@" in url:
                raise ErroBanco(
                    "A senha na DATABASE_URL está entre colchetes. Troque "
                    "[YOUR-PASSWORD] pela senha, sem os colchetes."
                )
            return url or None
    return None


def _psycopg():
    try:
        import psycopg
    except ImportError as erro:
        raise ErroBanco(
            "DATABASE_URL está configurada, mas o driver do PostgreSQL não foi "
            "instalado. Execute: pip install -r requirements.txt"
        ) from erro
    return psycopg


class Transacao:
    """Executa comandos dentro de uma transação aberta por Banco.transacao()."""

    def __init__(self, conexao, postgres: bool):
        self._conexao = conexao
        self._postgres = postgres

    def _sql(self, sql: str) -> str:
        # sqlite3 usa ? como marcador de parâmetro; o psycopg usa %s e, por
        # isso, exige %% para um % literal (ex.: LIKE 'a%').
        if not self._postgres:
            return sql
        return sql.replace("%", "%%").replace("?", "%s")

    def executar(self, sql: str, parametros=()) -> int:
        """Executa um comando e retorna quantas linhas ele alterou."""
        return self._conexao.execute(self._sql(sql), parametros).rowcount

    def varios(self, sql: str, linhas) -> None:
        self._conexao.cursor().executemany(self._sql(sql), list(linhas))

    def todos(self, sql: str, parametros=()) -> list[tuple]:
        return self._conexao.execute(self._sql(sql), parametros).fetchall()

    def um(self, sql: str, parametros=()) -> tuple | None:
        return self._conexao.execute(self._sql(sql), parametros).fetchone()


class Banco:
    def __init__(self, destino: str | Path):
        destino = str(destino)
        self.postgres = destino.startswith(("postgres://", "postgresql://"))
        self._destino = destino
        self._conexao = None  # reaproveitada no PostgreSQL (conexão de rede)
        self._preparados: set[tuple[str, ...]] = set()

    @classmethod
    def do_projeto(cls, raiz: Path, arquivo_local: Path) -> "Banco":
        """Supabase se a raiz tiver DATABASE_URL no .env; senão SQLite local."""
        return cls(ler_url(raiz) or arquivo_local)

    @property
    def descricao(self) -> str:
        # Não exibe a URL: ela contém a senha do banco.
        return "Supabase (PostgreSQL)" if self.postgres else f"SQLite local ({self._destino})"

    def preparar(self, tabelas: dict[str, str]) -> bool:
        """Cria as tabelas que faltam. Retorna True na primeira chamada desta execução."""
        chave = tuple(tabelas)
        if chave in self._preparados:
            return False
        with self.transacao() as t:
            for nome, colunas in tabelas.items():
                t.executar(f"CREATE TABLE IF NOT EXISTS {nome} ({colunas})")
                if self.postgres:
                    # Sem políticas, a API pública do Supabase não lê nem grava a
                    # tabela. A aplicação conecta como dona e não é afetada.
                    t.executar(f"ALTER TABLE {nome} ENABLE ROW LEVEL SECURITY")
        self._preparados.add(chave)
        return True

    @contextmanager
    def transacao(self):
        """Confirma tudo ao final do bloco ou desfaz tudo se houver erro."""
        conexao = self._abrir()
        try:
            yield Transacao(conexao, self.postgres)
            conexao.commit()
        except Exception as erro:
            self._desfazer(conexao)
            traduzido = self._traduzir(erro)
            if traduzido is None:
                raise
            raise traduzido from erro
        finally:
            if not self.postgres:
                conexao.close()

    def fechar(self) -> None:
        if self._conexao is not None:
            self._conexao.close()
            self._conexao = None

    def _abrir(self):
        if not self.postgres:
            try:
                Path(self._destino).parent.mkdir(parents=True, exist_ok=True)
                conexao = sqlite3.connect(self._destino, timeout=10)
                conexao.execute("PRAGMA foreign_keys = ON")
            except (OSError, sqlite3.Error) as erro:
                raise ErroBanco(f"não foi possível abrir o banco local: {erro}") from erro
            return conexao
        if self._conexao is None or self._conexao.closed or self._conexao.broken:
            psycopg = _psycopg()
            try:
                # prepare_threshold=None: o pooler do Supabase não aceita
                # comandos preparados no modo de transação.
                self._conexao = psycopg.connect(
                    self._destino, connect_timeout=10, prepare_threshold=None
                )
            except psycopg.Error as erro:
                raise ErroBanco(
                    f"não foi possível conectar ao Supabase; confira DATABASE_URL no .env: {erro}"
                ) from erro
        return self._conexao

    def _desfazer(self, conexao) -> None:
        try:
            conexao.rollback()
        except Exception:  # noqa: BLE001 - conexão perdida: abre outra na próxima vez
            if self.postgres:
                self.fechar()

    def _traduzir(self, erro: Exception) -> ErroBanco | None:
        if self.postgres:
            psycopg = _psycopg()
            integridade, geral = psycopg.IntegrityError, psycopg.Error
            if isinstance(erro, psycopg.OperationalError):
                self.fechar()  # conexão caiu; a próxima operação reconecta
        else:
            integridade, geral = sqlite3.IntegrityError, sqlite3.Error
        if isinstance(erro, integridade):
            return ErroIntegridade(f"restrição do banco violada: {erro}")
        if isinstance(erro, geral):
            return ErroBanco(f"erro no banco de dados: {erro}")
        return None
