import json
import logging
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .aplicacao import Aplicacao, ErroRepositorio
from .autenticacao import Autenticacao, COOKIE_SESSAO, DURACAO_SESSAO, ErroAcesso

ARQUIVOS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/estilos.css": ("estilos.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/acesso.js": ("acesso.js", "text/javascript; charset=utf-8"),
    "/favicon.svg": ("favicon.svg", "image/svg+xml"),
    "/marca.svg": ("marca.svg", "image/svg+xml"),
}


def criar_servidor(raiz: Path, porta: int = 8000) -> HTTPServer:
    aplicacao = Aplicacao(raiz)
    autenticacao = Autenticacao(raiz / "dados" / "acesso.json")
    estaticos = Path(__file__).parent / "static"

    class Handler(BaseHTTPRequestHandler):
        def responder(self, status: int, conteudo: bytes, tipo: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(conteudo)))
            self.send_header("Cache-Control", "no-store")
            if getattr(self, "cookie_sessao", None):
                self.send_header("Set-Cookie", self.cookie_sessao)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
            )
            self.end_headers()
            self.wfile.write(conteudo)

        def json(self, status: int, dados: dict) -> None:
            self.responder(
                status,
                json.dumps(dados, ensure_ascii=False, allow_nan=False).encode("utf-8"),
                "application/json; charset=utf-8",
            )

        def host_valido(self) -> bool:
            return self.headers.get("Host") in {
                f"127.0.0.1:{self.server.server_port}",
                f"localhost:{self.server.server_port}",
            }

        def token_sessao(self) -> str:
            cookies = SimpleCookie()
            try:
                cookies.load(self.headers.get("Cookie", ""))
                return cookies[COOKIE_SESSAO].value if COOKIE_SESSAO in cookies else ""
            except CookieError:
                return ""

        def definir_cookie(self, token: str, duracao: int = DURACAO_SESSAO) -> None:
            self.cookie_sessao = f"{COOKIE_SESSAO}={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={duracao}"

        def exigir_acesso(self) -> None:
            if autenticacao.consultar(self.token_sessao()) is None:
                raise ErroAcesso("Entre na sua conta para continuar.")

        def do_GET(self) -> None:
            if not self.host_valido():
                self.json(
                    403, {"erro": "Acesso permitido somente pelo endereço local."}
                )
                return
            caminho = urlsplit(self.path).path
            try:
                if caminho == "/api/sessao":
                    usuario = autenticacao.consultar(self.token_sessao())
                    self.json(
                        200,
                        {"configurada": autenticacao.configurada, "usuario": usuario},
                    )
                elif caminho == "/api/estado":
                    self.exigir_acesso()
                    self.json(200, aplicacao.estado())
                elif caminho in ARQUIVOS:
                    nome, tipo = ARQUIVOS[caminho]
                    self.responder(200, (estaticos / nome).read_bytes(), tipo)
                else:
                    self.json(404, {"erro": "Página não encontrada."})
            except ErroAcesso as erro:
                self.json(erro.status, {"erro": str(erro)})
            except (OSError, ValueError, ErroRepositorio):
                logging.exception("Falha ao carregar os dados")
                self.json(
                    500,
                    {
                        "erro": "Não foi possível ler os dados locais. Confira o terminal e os arquivos de dados."
                    },
                )

        def do_POST(self) -> None:
            origem = self.headers.get("Origin")
            if not self.host_valido() or (
                origem and origem != f"http://{self.headers.get('Host')}"
            ):
                self.json(403, {"erro": "Origem não permitida."})
                return
            try:
                caminho = urlsplit(self.path).path
                if caminho not in {
                    "/api/acesso/configurar",
                    "/api/acesso/cadastrar",
                    "/api/acesso/entrar",
                    "/api/acesso/sair",
                }:
                    self.exigir_acesso()
                tamanho = int(self.headers.get("Content-Length", "0"))
                if tamanho <= 0 or tamanho > 100_000:
                    raise ValueError("Tamanho de requisição inválido.")
                if self.headers.get_content_type() != "application/json":
                    raise ValueError("Envie os dados em JSON.")
                dados = json.loads(self.rfile.read(tamanho))
                if not isinstance(dados, dict):
                    raise ValueError("Envie um objeto JSON.")
                if caminho in {
                    "/api/acesso/configurar",
                    "/api/acesso/cadastrar",
                    "/api/acesso/entrar",
                }:
                    if caminho.endswith("configurar"):
                        token, usuario = autenticacao.configurar(
                            dados.get("nome"), dados.get("usuario"), dados.get("senha")
                        )
                    elif caminho.endswith("cadastrar"):
                        token, usuario = autenticacao.cadastrar(
                            dados.get("nome"), dados.get("usuario"), dados.get("senha")
                        )
                    else:
                        token, usuario = autenticacao.entrar(
                            dados.get("usuario"), dados.get("senha")
                        )
                    self.definir_cookie(token)
                    self.json(200, {"usuario": usuario})
                    return
                if caminho == "/api/acesso/sair":
                    autenticacao.sair(self.token_sessao())
                    self.definir_cookie("", 0)
                    self.json(200, {"mensagem": "Sessão encerrada."})
                    return
                resultado = aplicacao.executar(caminho, dados)
                self.json(200, resultado)
            except ErroAcesso as erro:
                self.json(erro.status, {"erro": str(erro)})
            except (ValueError, ErroRepositorio) as erro:
                self.json(400, {"erro": str(erro)})
            except LookupError:
                self.json(404, {"erro": "Operação não encontrada."})
            except OSError:
                logging.exception("Falha ao gravar os dados")
                self.json(
                    500,
                    {
                        "erro": "Falha ao gravar os arquivos. Atualize a tela antes de tentar novamente; se a venda já estiver no histórico, use Sincronizar vendas."
                    },
                )

    # Um único servidor serializa as alterações nos arquivos JSON.
    return HTTPServer(("127.0.0.1", porta), Handler)
