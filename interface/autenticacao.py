"""Conta local e sessões de acesso. Não depende de serviços externos."""

import hashlib
import hmac
import json
import os
import re
import secrets
import time
from pathlib import Path

COOKIE_SESSAO = "ve_sessao"
DURACAO_SESSAO = 8 * 60 * 60
ITERACOES_SENHA = 600_000


class ErroAcesso(Exception):
    def __init__(self, mensagem: str, status: int = 401):
        super().__init__(mensagem)
        self.status = status


class Autenticacao:
    def __init__(self, arquivo: Path):
        self.arquivo = arquivo
        self.sessoes: dict[str, tuple[dict, float]] = {}
        self.falhas = 0
        self.bloqueado_ate = 0.0

    @property
    def configurada(self) -> bool:
        return self.arquivo.exists()

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

    def _carregar_contas(self) -> list[dict]:
        if not self.arquivo.exists():
            return []
        dados = json.loads(self.arquivo.read_text(encoding="utf-8"))
        # Preserva a conta criada na versão de acesso único, incluindo seu hash.
        if isinstance(dados, dict) and "usuario" in dados:
            return [dados]
        if not isinstance(dados, dict) or not isinstance(dados.get("usuarios"), list):
            raise ValueError("O arquivo de contas é inválido.")
        return dados["usuarios"]

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
        contas = self._carregar_contas()
        if any(conta["usuario"] == usuario.casefold() for conta in contas):
            raise ErroAcesso(
                "Este usuário já está cadastrado. Escolha outro ou entre na sua conta.",
                409,
            )
        salt = secrets.token_hex(16)
        conta = {
            "nome": nome.strip(),
            "usuario": usuario.casefold(),
            "salt": salt,
            "iteracoes": ITERACOES_SENHA,
            "senha_hash": self._hash(senha, salt),
        }
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        temporario = self.arquivo.with_suffix(".tmp")
        temporario.write_text(
            json.dumps({"usuarios": contas + [conta]}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temporario, self.arquivo)
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
        conta = next(
            (
                conta
                for conta in self._carregar_contas()
                if conta["usuario"] == usuario.strip().casefold()
            ),
            None,
        )
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
