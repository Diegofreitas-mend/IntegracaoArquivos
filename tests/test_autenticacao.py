import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from banco import Banco
from interface.autenticacao import Autenticacao, DURACAO_SESSAO, ErroAcesso


class AutenticacaoTest(unittest.TestCase):
    def setUp(self):
        self.temporario = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporario.cleanup)
        self.arquivo = Path(self.temporario.name) / "acesso.db"
        self.auth = Autenticacao(Banco(self.arquivo))

    def configurar(self):
        return self.auth.configurar("Operador", "operador", "SenhaTeste123!")

    def contas(self) -> list[tuple]:
        with Banco(self.arquivo).transacao() as t:
            return t.todos("SELECT * FROM usuarios ORDER BY usuario")

    def test_primeiro_acesso_persiste_hash_e_retorna_apenas_perfil_publico(self):
        self.assertFalse(self.auth.configurada)
        token, usuario = self.configurar()
        self.assertTrue(self.auth.configurada)
        self.assertEqual(usuario, {"nome": "Operador", "usuario": "operador"})
        self.assertEqual(self.auth.consultar(token), usuario)
        (conta,) = self.contas()
        self.assertNotIn("SenhaTeste123!", [str(valor) for valor in conta])
        with Banco(self.arquivo).transacao() as t:
            self.assertGreaterEqual(t.um("SELECT iteracoes FROM usuarios")[0], 600_000)

    def test_cadastra_contas_diferentes_e_cada_uma_usa_sua_senha(self):
        primeiro, _ = self.auth.cadastrar("Ana", "ana", "SenhaDaAna123!")
        segundo, _ = self.auth.cadastrar("Bruno", "bruno", "SenhaDoBruno123!")
        self.assertEqual(self.auth.consultar(primeiro)["nome"], "Ana")
        self.assertEqual(self.auth.consultar(segundo)["nome"], "Bruno")
        reaberta = Autenticacao(Banco(self.arquivo))
        for usuario, senha in (
            ("ana", "SenhaDaAna123!"),
            ("bruno", "SenhaDoBruno123!"),
        ):
            token, perfil = reaberta.entrar(usuario, senha)
            self.assertEqual(reaberta.consultar(token)["usuario"], usuario)
        with self.assertRaises(ErroAcesso):
            reaberta.entrar("ana", "SenhaDoBruno123!")

    def test_cadastro_repetido_nao_sobrescreve_conta(self):
        self.configurar()
        antes = self.contas()
        with self.assertRaises(ErroAcesso) as erro:
            self.auth.cadastrar("Outra pessoa", "OPERADOR", "OutraSenha123!")
        self.assertEqual(erro.exception.status, 409)
        self.assertEqual(self.contas(), antes)

    def test_validacao_de_cadastro_nao_cria_conta(self):
        for nome, usuario, senha in (
            ("", "operador", "12345678"),
            ("Nome", "a", "12345678"),
            ("Nome", "com espaço", "12345678"),
            ("Nome", "usuario", "curta"),
            (None, "operador", "12345678"),
        ):
            with self.subTest(usuario=usuario), self.assertRaises(ValueError):
                self.auth.configurar(nome, usuario, senha)
        self.assertFalse(self.auth.configurada)

    def test_conta_existente_nao_pode_ser_substituida(self):
        self.configurar()
        antes = self.contas()
        with self.assertRaises(ErroAcesso) as erro:
            self.auth.configurar("Outro", "outro", "OutraSenha123!")
        self.assertEqual(erro.exception.status, 409)
        self.assertEqual(self.contas(), antes)

    def test_login_valida_senha_e_normaliza_usuario(self):
        self.configurar()
        token, usuario = self.auth.entrar(" OPERADOR ", "SenhaTeste123!")
        self.assertEqual(self.auth.consultar(token), usuario)
        for login, senha in (
            ("inexistente", "SenhaTeste123!"),
            ("operador", "incorreta"),
        ):
            with self.subTest(login=login), self.assertRaisesRegex(
                ErroAcesso, "Usuário ou senha incorretos"
            ):
                self.auth.entrar(login, senha)

    def test_sessao_expira(self):
        with patch("interface.autenticacao.time.monotonic", return_value=100):
            token, _ = self.configurar()
        with patch(
            "interface.autenticacao.time.monotonic", return_value=101 + DURACAO_SESSAO
        ):
            self.assertIsNone(self.auth.consultar(token))
        self.assertIsNone(self.auth.consultar("token-inexistente"))

    def test_logout_invalida_apenas_a_sessao_atual(self):
        primeiro, _ = self.configurar()
        segundo, _ = self.auth.entrar("operador", "SenhaTeste123!")
        self.auth.sair(primeiro)
        self.assertIsNone(self.auth.consultar(primeiro))
        self.assertIsNotNone(self.auth.consultar(segundo))

    def test_reinicio_preserva_conta_mas_encerra_sessoes(self):
        token, _ = self.configurar()
        reaberta = Autenticacao(Banco(self.arquivo))
        self.assertIsNone(reaberta.consultar(token))
        novo_token, usuario = reaberta.entrar("operador", "SenhaTeste123!")
        self.assertEqual(reaberta.consultar(novo_token), usuario)

    def test_limite_de_tentativas_temporario(self):
        self.configurar()
        for _ in range(5):
            with self.assertRaises(ErroAcesso):
                self.auth.entrar("operador", "incorreta")
        with self.assertRaises(ErroAcesso) as erro:
            self.auth.entrar("operador", "SenhaTeste123!")
        self.assertEqual(erro.exception.status, 429)
        with patch(
            "interface.autenticacao.time.monotonic",
            return_value=self.auth.bloqueado_ate + 1,
        ):
            token, _ = self.auth.entrar("operador", "SenhaTeste123!")
            self.assertIsNotNone(self.auth.consultar(token))


if __name__ == "__main__":
    unittest.main()
