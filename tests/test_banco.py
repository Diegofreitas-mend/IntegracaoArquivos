import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from banco import Banco, ErroBanco, ler_url


class BancoTest(unittest.TestCase):
    def setUp(self):
        self.temporario = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporario.cleanup)
        self.raiz = Path(self.temporario.name)

    def test_le_url_do_env_ignorando_comentarios_e_aspas(self):
        (self.raiz / ".env").write_text(
            '# DATABASE_URL=postgresql://comentario\nDATABASE_URL="postgresql://u:s@h/db"\n',
            encoding="utf-8",
        )
        self.assertEqual(ler_url(self.raiz), "postgresql://u:s@h/db")
        self.assertTrue(Banco.do_projeto(self.raiz, self.raiz / "x.db").postgres)

    def test_url_que_nao_e_do_postgres_tem_erro_claro(self):
        (self.raiz / ".env").write_text(
            "DATABASE_URL=https://abc.supabase.co\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(ErroBanco, "postgresql://"):
            ler_url(self.raiz)

    def test_senha_entre_colchetes_tem_erro_claro(self):
        (self.raiz / ".env").write_text(
            "DATABASE_URL=postgresql://postgres.ref:[minhasenha]@host:5432/postgres\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ErroBanco, "colchetes"):
            ler_url(self.raiz)

    def test_sem_env_usa_sqlite_mesmo_com_variavel_de_ambiente(self):
        # Garante que testes e raízes de demonstração nunca gravem no Supabase.
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://u:s@h/db"}):
            banco = Banco.do_projeto(self.raiz, self.raiz / "local.db")
        self.assertFalse(banco.postgres)
        self.assertNotIn("postgresql", banco.descricao)

    def test_descricao_nao_expoe_senha(self):
        self.assertNotIn("senha", Banco("postgresql://u:senha@h/db").descricao)

    def test_transacao_desfaz_tudo_em_caso_de_erro(self):
        banco = Banco(self.raiz / "t.db")
        banco.preparar({"t": "id INTEGER PRIMARY KEY"})
        with self.assertRaises(ErroBanco), banco.transacao() as t:
            t.executar("INSERT INTO t (id) VALUES (1)")
            t.executar("INSERT INTO t (id) VALUES (1)")  # chave repetida
        with banco.transacao() as t:
            self.assertEqual(t.um("SELECT COUNT(*) FROM t")[0], 0)


if __name__ == "__main__":
    unittest.main()
