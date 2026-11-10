"""Testes do fluxo completo. Executar: python -m unittest discover -s tests -v."""

import json
import logging
import tempfile
import threading
import unittest
from importlib import import_module
from http.cookiejar import CookieJar
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen

from interface.aplicacao import Aplicacao, ErroRepositorio
from interface.servidor import criar_servidor

repositorio_vendas = import_module("sistema-vendas.src.repositorio_vendas")


class FluxoTest(unittest.TestCase):
    def setUp(self):
        self.temporario = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporario.cleanup)
        self.raiz = Path(self.temporario.name)
        self.app = Aplicacao(self.raiz)
        # Os handlers precisam ser fechados antes de remover a pasta no Windows.
        logger = logging.getLogger("estoque")
        self.addCleanup(lambda: [handler.close() for handler in logger.handlers])

    def vender(self, quantidade=2):
        return self.app.executar(
            "/api/vendas", {"itens": [{"produto_id": 1, "quantidade": quantidade}]}
        )["venda"]

    def test_venda_exporta_json_compativel_e_persiste_historico(self):
        venda = self.vender()
        arquivo = self.raiz / "integracao" / "saida" / "venda_1001.json"
        self.assertEqual(json.loads(arquivo.read_text(encoding="utf-8")), venda)
        self.assertEqual(venda["total"], 159.80)
        self.assertEqual(self.app.estado()["vendas"][0]["status"], "pendente")
        self.assertEqual(Aplicacao(self.raiz).estado()["vendas"][0]["venda_id"], 1001)

    def test_reserva_impede_vender_saldo_duas_vezes(self):
        self.vender(49)
        produto = self.app.estado()["produtos"][0]
        self.assertEqual(
            (produto["quantidade"], produto["disponivel"], produto["reservado"]),
            (50, 1, 49),
        )
        with self.assertRaisesRegex(ValueError, "Saldo insuficiente"):
            self.vender(2)
        self.assertEqual(len(self.app.estado()["vendas"]), 1)

    def test_sincronizacao_baixa_uma_vez_e_remove_reserva(self):
        self.vender()
        resultado = self.app.executar("/api/sincronizar", {})
        self.assertEqual(resultado["resultados"][0]["status"], "processado")
        estado = self.app.estado()
        self.assertEqual(estado["produtos"][0]["quantidade"], 48)
        self.assertEqual(estado["produtos"][0]["disponivel"], 48)
        self.assertEqual(estado["produtos"][0]["reservado"], 0)
        self.assertEqual(estado["vendas"][0]["status"], "processado")
        self.assertEqual(self.app.executar("/api/sincronizar", {})["resultados"], [])

    def test_duplicidade_nao_baixa_novamente_apos_reinicio(self):
        venda = self.vender()
        self.app.executar("/api/sincronizar", {})
        self.app = Aplicacao(self.raiz)
        self.app.vendas.repositorio.exportar(venda)
        resultado = self.app.executar("/api/sincronizar", {})
        self.assertEqual(resultado["resultados"][0]["status"], "duplicado")
        self.assertEqual(self.app.estado()["produtos"][0]["quantidade"], 48)

    def test_itens_repetidos_somados_antes_da_validacao(self):
        with self.assertRaisesRegex(ValueError, "Saldo insuficiente"):
            self.app.executar(
                "/api/vendas", {"itens": [{"produto_id": 1, "quantidade": 30}] * 2}
            )
        self.assertEqual(self.app.estado()["vendas"], [])

    def test_quantidades_invalidas_e_carrinho_vazio_nao_salvam(self):
        for quantidade in (0, -1, 1.5, True, "2", None):
            with self.subTest(quantidade=quantidade), self.assertRaises(ValueError):
                self.vender(quantidade)
        for itens in (
            [],
            None,
            "invalido",
            [None],
            [{"produto_id": 999, "quantidade": 1}],
        ):
            with self.subTest(itens=itens), self.assertRaises(ValueError):
                self.app.executar("/api/vendas", {"itens": itens})
        self.assertEqual(self.app.estado()["vendas"], [])

    def test_falha_exportacao_recuperada_sem_criar_outra_venda(self):
        with patch.object(
            self.app.vendas.repositorio,
            "exportar",
            side_effect=OSError("disco indisponível"),
        ):
            resultado = self.app.executar(
                "/api/vendas", {"itens": [{"produto_id": 1, "quantidade": 2}]}
            )
        self.assertTrue(resultado["aviso"])
        self.assertEqual(resultado["venda"]["venda_id"], 1001)
        self.assertIn("salva", resultado["mensagem"])
        self.assertEqual(
            self.app.estado()["vendas"][0]["status"], "exportacao_pendente"
        )
        self.app.executar("/api/sincronizar", {})
        self.assertEqual(len(self.app.estado()["vendas"]), 1)
        self.assertEqual(self.app.estado()["produtos"][0]["quantidade"], 48)

    def test_falha_ao_salvar_historico_nao_confirma_nem_exporta(self):
        with patch.object(
            repositorio_vendas, "gravar_json",
            side_effect=OSError("disco indisponível"),
        ), self.assertRaises(OSError):
            self.vender()
        self.assertEqual(self.app.estado()["vendas"], [])
        self.assertEqual(self.app.estado()["arquivos"]["saida"], [])

    def test_novo_produto_preco_reposicao_e_venda(self):
        self.app.executar(
            "/api/produtos", {"produto_id": 4, "nome": "Webcam", "quantidade": 5}
        )
        self.app.executar("/api/precos", {"produto_id": 4, "preco": 99.90})
        self.app.executar("/api/reposicoes", {"produto_id": 4, "quantidade": 3})
        venda = self.app.executar(
            "/api/vendas", {"itens": [{"produto_id": 4, "quantidade": 2}]}
        )["venda"]
        self.assertEqual(venda["total"], 199.80)
        self.app.executar("/api/sincronizar", {})
        self.assertEqual(self.app.estado()["produtos"][3]["quantidade"], 6)

    def test_edicao_preco_preserva_vendas_anteriores_e_centavos(self):
        self.app.executar("/api/precos", {"produto_id": 1, "preco": 0.10})
        venda = self.vender(3)
        self.app.executar("/api/precos", {"produto_id": 1, "preco": 99.90})
        self.assertEqual(venda["total"], 0.30)
        self.assertEqual(self.app.estado()["vendas"][0]["total"], 0.30)

    def test_precos_invalidos_nao_persistem(self):
        for preco in (
            0,
            -1,
            True,
            None,
            "abc",
            1.234,
            float("inf"),
            float("nan"),
            1e100,
        ):
            with self.subTest(preco=preco), self.assertRaises(ValueError):
                self.app.executar("/api/precos", {"produto_id": 1, "preco": preco})
        self.assertEqual(self.app.estado()["produtos"][0]["preco"], 79.90)

    def test_cadastro_e_reposicao_rejeitam_tipos_invalidos(self):
        for dados in (
            {},
            {"produto_id": True, "nome": "X"},
            {"produto_id": 4, "nome": None},
            {"produto_id": 4, "nome": "X", "quantidade": 1.5},
        ):
            with self.subTest(dados=dados), self.assertRaises(ErroRepositorio):
                self.app.executar("/api/produtos", dados)
        with self.assertRaises(ErroRepositorio):
            self.app.executar("/api/reposicoes", {"produto_id": 1, "quantidade": True})

    def test_arquivo_invalido_nao_impede_venda_valida(self):
        (self.app.estoque.pastas.entrada / "invalido.json").write_text(
            "{", encoding="utf-8"
        )
        self.vender()
        resultados = self.app.executar("/api/sincronizar", {})["resultados"]
        self.assertEqual([r["status"] for r in resultados], ["erro", "processado"])
        self.assertEqual(self.app.estado()["produtos"][0]["quantidade"], 48)

    def test_venda_rejeitada_libera_reserva(self):
        self.vender(50)
        # Simula uma alteração de saldo feita no sistema de estoque antes da integração.
        repo = self.app.estoque.repositorio()
        repo.produtos[1].quantidade = 10
        repo._gravar(repo.produtos, repo.processados)
        self.app.executar("/api/sincronizar", {})
        estado = self.app.estado()
        self.assertEqual(estado["vendas"][0]["status"], "erro")
        self.assertEqual(estado["produtos"][0]["disponivel"], 10)

    def test_ids_nao_colidem_com_vendas_externas_processadas(self):
        dados = {
            "venda_id": 1001,
            "data_hora": "2026-10-20T10:00:00",
            "itens": [{"produto_id": 1, "quantidade": 1}],
        }
        (self.app.estoque.pastas.entrada / "externa.json").write_text(
            json.dumps(dados), encoding="utf-8"
        )
        self.app.executar("/api/processar", {})
        self.assertEqual(self.vender()["venda_id"], 1002)


class ServidorTest(unittest.TestCase):
    def setUp(self):
        self.temporario = tempfile.TemporaryDirectory()
        self.servidor = criar_servidor(Path(self.temporario.name), 0)
        self.thread = threading.Thread(target=self.servidor.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.servidor.server_port}"
        self.cookies = CookieJar()
        self.client = build_opener(HTTPCookieProcessor(self.cookies))
        with self.client.open(
            self.requisicao(
                "/api/acesso/configurar",
                {
                    "nome": "Operador de teste",
                    "usuario": "operador",
                    "senha": "SenhaTeste123!",
                },
            )
        ) as resposta:
            self.cookie_header = resposta.headers["Set-Cookie"]

    def requisicao(self, caminho, dados, **headers):
        return Request(
            self.url + caminho,
            data=json.dumps(dados).encode(),
            headers={"Content-Type": "application/json", "Origin": self.url, **headers},
        )

    def tearDown(self):
        self.servidor.shutdown()
        self.servidor.server_close()
        self.thread.join()
        for handler in logging.getLogger("estoque").handlers:
            handler.close()
        self.temporario.cleanup()

    def test_estaticos_e_estado_acessiveis(self):
        for caminho in (
            "/",
            "/estilos.css",
            "/app.js",
            "/acesso.js",
            "/favicon.svg",
            "/marca.svg",
            "/api/estado",
        ):
            with self.subTest(caminho=caminho), self.client.open(
                self.url + caminho
            ) as response:
                self.assertEqual(response.status, 200)
                self.assertGreater(len(response.read()), 0)
        with self.assertRaises(HTTPError) as erro:
            urlopen(self.url + "/../app.py")
        self.assertEqual(erro.exception.code, 404)
        erro.exception.close()

    def test_post_valida_dados_e_origem(self):
        for dados, origem, esperado in (
            ({}, self.url, 400),
            ({}, "https://externo.example", 403),
            ({"itens": [{"produto_id": 1, "quantidade": 1}]}, self.url, 200),
        ):
            requisicao = Request(
                self.url + "/api/vendas",
                data=json.dumps(dados).encode(),
                headers={"Content-Type": "application/json", "Origin": origem},
            )
            if esperado == 200:
                with self.client.open(requisicao) as resposta:
                    self.assertEqual(resposta.status, esperado)
            else:
                with self.assertRaises(HTTPError) as erro:
                    self.client.open(requisicao)
                self.assertEqual(erro.exception.code, esperado)
                erro.exception.close()

    def test_api_confirma_venda_salva_quando_exportacao_falha(self):
        with patch.object(
            repositorio_vendas.RepositorioVendas, "exportar",
            side_effect=OSError("saída indisponível"),
        ), self.client.open(self.requisicao(
            "/api/vendas", {"itens": [{"produto_id": 1, "quantidade": 2}]}
        )) as resposta:
            resultado = json.load(resposta)
            self.assertEqual(resposta.status, 200)
            self.assertTrue(resultado["aviso"])
            self.assertEqual(resultado["venda"]["venda_id"], 1001)
        with self.client.open(self.requisicao("/api/sincronizar", {})):
            pass
        with self.client.open(self.url + "/api/estado") as resposta:
            estado = json.load(resposta)
        self.assertEqual(len(estado["vendas"]), 1)
        self.assertEqual(estado["produtos"][0]["quantidade"], 48)

    def test_operacoes_exigem_login(self):
        requisicoes = [Request(self.url + "/api/estado")]
        requisicoes.extend(
            self.requisicao(caminho, {})
            for caminho in (
                "/api/vendas",
                "/api/sincronizar",
                "/api/processar",
                "/api/produtos",
                "/api/reposicoes",
                "/api/precos",
            )
        )
        for requisicao in requisicoes:
            with self.subTest(url=requisicao.full_url), self.assertRaises(
                HTTPError
            ) as erro:
                urlopen(requisicao)
            self.assertEqual(erro.exception.code, 401)
            erro.exception.close()

    def test_sessao_cookie_logout_e_replay(self):
        self.assertIn("HttpOnly", self.cookie_header)
        self.assertIn("SameSite=Strict", self.cookie_header)
        with self.client.open(self.url + "/api/sessao") as resposta:
            sessao = json.load(resposta)
        self.assertEqual(sessao["usuario"]["usuario"], "operador")
        cookie_antigo = "; ".join(
            f"{cookie.name}={cookie.value}" for cookie in self.cookies
        )
        with self.client.open(self.requisicao("/api/acesso/sair", {})) as resposta:
            self.assertIn("Max-Age=0", resposta.headers["Set-Cookie"])
        with self.assertRaises(HTTPError) as erro:
            urlopen(
                Request(self.url + "/api/estado", headers={"Cookie": cookie_antigo})
            )
        self.assertEqual(erro.exception.code, 401)
        erro.exception.close()

    def test_login_invalido_e_novo_login(self):
        with self.assertRaises(HTTPError) as erro:
            urlopen(
                self.requisicao(
                    "/api/acesso/entrar", {"usuario": "operador", "senha": "incorreta"}
                )
            )
        self.assertEqual(erro.exception.code, 401)
        erro.exception.close()
        outro_cliente = build_opener(HTTPCookieProcessor(CookieJar()))
        with outro_cliente.open(
            self.requisicao(
                "/api/acesso/entrar", {"usuario": "operador", "senha": "SenhaTeste123!"}
            )
        ) as resposta:
            self.assertEqual(
                json.load(resposta)["usuario"]["nome"], "Operador de teste"
            )
        with outro_cliente.open(self.url + "/api/estado") as resposta:
            self.assertEqual(len(json.load(resposta)["produtos"]), 3)

    def test_configuracao_nao_sobrescreve_conta_e_sessao_publica_nao_expoe_dados(self):
        with self.assertRaises(HTTPError) as erro:
            urlopen(
                self.requisicao(
                    "/api/acesso/configurar",
                    {"nome": "Outro", "usuario": "outro", "senha": "OutraSenha123!"},
                )
            )
        self.assertEqual(erro.exception.code, 409)
        erro.exception.close()
        with urlopen(self.url + "/api/sessao") as resposta:
            self.assertEqual(
                json.load(resposta), {"configurada": True, "usuario": None}
            )

    def test_cadastro_disponivel_depois_da_primeira_conta(self):
        outro_cliente = build_opener(HTTPCookieProcessor(CookieJar()))
        cadastro = {
            "nome": "Segunda pessoa",
            "usuario": "segundo",
            "senha": "OutraSenha123!",
        }
        with outro_cliente.open(
            self.requisicao("/api/acesso/cadastrar", cadastro)
        ) as resposta:
            self.assertEqual(json.load(resposta)["usuario"]["usuario"], "segundo")
        with outro_cliente.open(self.url + "/api/estado") as resposta:
            self.assertEqual(len(json.load(resposta)["produtos"]), 3)
        with outro_cliente.open(self.requisicao("/api/acesso/sair", {})):
            pass
        with outro_cliente.open(
            self.requisicao(
                "/api/acesso/entrar", {"usuario": "operador", "senha": "SenhaTeste123!"}
            )
        ) as resposta:
            self.assertEqual(json.load(resposta)["usuario"]["usuario"], "operador")
        with self.assertRaises(HTTPError) as erro:
            urlopen(self.requisicao("/api/acesso/cadastrar", cadastro))
        self.assertEqual(erro.exception.code, 409)
        erro.exception.close()


if __name__ == "__main__":
    unittest.main()
