"""Contas de acesso (no banco de dados) e sessões (em memória)."""

import hashlib
import hmac
import re
import secrets
import time

from banco import Banco, ErroIntegridade

COOKIE_SESSAO = "ve_sessao"
DURACAO_SESSAO = 8 * 60 * 60
ITERACOES_SENHA = 600_000

# A senha nunca é gravada: só o salt e o hash PBKDF2.
TABELAS = {
    "usuarios": (
        "usuario TEXT PRIMARY KEY, "
        "nome TEXT NOT NULL, "
        "salt TEXT NOT NULL, "
        "iteracoes INTEGER NOT NULL, "
        "senha_hash TEXT NOT NULL"
    ),
}


class ErroAcesso(Exception):
    def __init__(self, mensagem: str, status: int = 401):
        super().__init__(mensagem)
        self.status = status


class Autenticacao:
    def __init__(self, banco: Banco):
        self.banco = banco
        banco.preparar(TABELAS)
        self.sessoes: dict[str, tuple[dict, float]] = {}
        self.falhas = 0
        self.bloqueado_ate = 0.0

    @property
    def configurada(self) -> bool:
        with self.banco.transacao() as t:
            return t.um("SELECT COUNT(*) FROM usuarios")[0] > 0

    @staticmethod
    def _hash(senha: str, salt: str, iteracoes: int = ITERACOES_SENHA) -> str:
        return hashlib.pbkdf2_hmac(
            "sha256", senha.encode("utf-8"), bytes.fromhex(salt), iteracoes
        ).hex()

    def _criar_sessao(self, conta: dict) -> tuple[str, dict]:
        agora = time.monotonic()
        self.sessoes = {
            token: valor for token, valor in self.sessoes.items() if valor[1] > agora
        }
        token = secrets.token_urlsafe(32)
        usuario = {"nome": conta["nome"], "usuario": conta["usuario"]}
        self.sessoes[token] = (usuario, agora + DURACAO_SESSAO)
        return token, usuario

    def configurar(self, nome, usuario, senha) -> tuple[str, dict]:
        if self.configurada:
            raise ErroAcesso("O acesso já foi configurado. Entre com sua conta.", 409)
        return self.cadastrar(nome, usuario, senha)

    def _buscar(self, usuario: str) -> dict | None:
        with self.banco.transacao() as t:
            linha = t.um(
                "SELECT nome, usuario, salt, iteracoes, senha_hash FROM usuarios WHERE usuario = ?",
                (usuario,),
            )
        if linha is None:
            return None
        return dict(zip(("nome", "usuario", "salt", "iteracoes", "senha_hash"), linha))

    def cadastrar(self, nome, usuario, senha) -> tuple[str, dict]:
        if not isinstance(nome, str) or not 1 <= len(nome.strip()) <= 80:
            raise ValueError("Informe seu nome, com até 80 caracteres.")
        if not isinstance(usuario, str) or not re.fullmatch(
            r"[a-zA-Z0-9._-]{3,40}", usuario
        ):
            raise ValueError(
                "Use de 3 a 40 letras, números, pontos, traços ou sublinhados no usuário."
            )
        if not isinstance(senha, str) or not 8 <= len(senha) <= 128:
            raise ValueError("A senha deve ter entre 8 e 128 caracteres.")
        salt = secrets.token_hex(16)
        conta = {
            "nome": nome.strip(),
            "usuario": usuario.casefold(),
            "salt": salt,
            "iteracoes": ITERACOES_SENHA,
            "senha_hash": self._hash(senha, salt),
        }
        try:
            with self.banco.transacao() as t:
                t.executar(
                    "INSERT INTO usuarios (usuario, nome, salt, iteracoes, senha_hash) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (conta["usuario"], conta["nome"], salt, ITERACOES_SENHA, conta["senha_hash"]),
                )
        except ErroIntegridade as erro:
            raise ErroAcesso(
                "Este usuário já está cadastrado. Escolha outro ou entre na sua conta.",
                409,
            ) from erro
        return self._criar_sessao(conta)

    def entrar(self, usuario, senha) -> tuple[str, dict]:
        if time.monotonic() < self.bloqueado_ate:
            raise ErroAcesso(
                "Muitas tentativas. Aguarde um minuto e tente novamente.", 429
            )
        if (
            not isinstance(usuario, str)
            or not isinstance(senha, str)
            or len(senha) > 128
        ):
            self._registrar_falha()
        conta = self._buscar(usuario.strip().casefold())
        # Mantém o custo de verificação quando o usuário não existe.
        salt = conta["salt"] if conta else "0" * 32
        iteracoes = conta["iteracoes"] if conta else ITERACOES_SENHA
        senha_correta = hmac.compare_digest(
            self._hash(senha, salt, iteracoes),
            conta["senha_hash"] if conta else "0" * 64,
        )
        if conta is None or not senha_correta:
            self._registrar_falha()
        self.falhas = 0
        return self._criar_sessao(conta)

    def _registrar_falha(self) -> None:
        self.falhas += 1
        if self.falhas >= 5:
            self.bloqueado_ate = time.monotonic() + 60
            self.falhas = 0
        raise ErroAcesso("Usuário ou senha incorretos.")

    def consultar(self, token: str) -> dict | None:
        sessao = self.sessoes.get(token)
        if sessao is None:
            return None
        if sessao[1] <= time.monotonic():
            self.sessoes.pop(token, None)
            return None
        return sessao[0].copy()

    def sair(self, token: str) -> None:
        self.sessoes.pop(token, None)
