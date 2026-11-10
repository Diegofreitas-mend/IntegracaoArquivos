import json
import os
import subprocess
import sys
import tempfile
import unittest
from importlib import import_module
from pathlib import Path

ServicoVendas = import_module("sistema-vendas.src.servico").ServicoVendas
RAIZ = Path(__file__).resolve().parents[1]


class TerminalVendasTest(unittest.TestCase):
    def setUp(self):
        self.temporario = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporario.cleanup)
        self.dados = Path(self.temporario.name)

    def executar(self, entradas):
        resultado = subprocess.run(
            [sys.executable, "vendas.py", "--dados", str(self.dados)],
            input=entradas,
            text=True,
            encoding="utf-8",
            capture_output=True,
            cwd=RAIZ,
            timeout=15,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        return resultado.stdout

    def arquivos(self):
        return list((self.dados / "integracao" / "saida").glob("*.json"))

    def test_registra_pelo_terminal_e_gera_json_compativel(self):
        saida = self.executar("1\n1\n2\n\ns\n0\n")
        self.assertIn("Venda #1001 registrada", saida)
        self.assertIn("159,80", saida)
        venda = json.loads(self.arquivos()[0].read_text(encoding="utf-8"))
        self.assertEqual(venda["itens"][0]["produto_id"], 1)
        self.assertEqual(venda["itens"][0]["quantidade"], 2)
        self.assertEqual(venda["total"], 159.80)
        self.assertIn("data_hora", venda)
        # O produtor não criou, leu ou atualizou o arquivo do estoque.
        self.assertFalse((self.dados / "sistema-estoque").exists())

    def test_soma_itens_repetidos_e_mantem_ids_apos_reinicio(self):
        self.executar("1\n1\n1\n1\n2\n\ns\n0\n")
        self.executar("1\n2\n1\n\ns\n3\n0\n")
        vendas = ServicoVendas(self.dados).repositorio.listar()
        self.assertEqual([v["venda_id"] for v in vendas], [1002, 1001])
        self.assertEqual(vendas[1]["itens"][0]["quantidade"], 3)
        self.assertEqual(len(self.arquivos()), 2)

    def test_quantidade_e_produto_invalidos_nao_geram_venda(self):
        saida = self.executar("1\n999\n1\n0\n1\nabc\n\n0\n")
        self.assertIn("Produto não encontrado", saida)
        self.assertIn("Pedido vazio", saida)
        self.assertEqual(self.arquivos(), [])

    def test_cancelamento_e_fim_de_entrada_nao_salvam_pedido(self):
        self.executar("1\n1\n2\n\nn\n0\n")
        self.executar("1\n1\n2\n0\n0\n")
        self.executar("1\n1\n")
        self.assertEqual(self.arquivos(), [])

    def test_saldo_e_validado_pelo_consumidor_nao_pelo_produtor(self):
        self.executar("1\n1\n60\n\ns\n0\n")
        venda = json.loads(self.arquivos()[0].read_text(encoding="utf-8"))
        self.assertEqual(venda["itens"][0]["quantidade"], 60)
        self.assertIn("venda_id", venda)

    def test_nova_venda_nao_sobrescreve_arquivo_presente_na_saida(self):
        pasta = self.dados / "integracao" / "saida"
        pasta.mkdir(parents=True)
        existente = pasta / "venda_1001.json"
        existente.write_text('{"arquivo": "preservar"}', encoding="utf-8")
        self.executar("1\n1\n1\n\ns\n0\n")
        self.assertEqual(
            existente.read_text(encoding="utf-8"), '{"arquivo": "preservar"}'
        )
        self.assertTrue((pasta / "venda_1002.json").exists())

    def test_reexportacao_identica_e_idempotente_e_diferente_e_bloqueada(self):
        servico = ServicoVendas(self.dados)
        venda = servico.criar(
            [{"produto_id": 1, "quantidade": 1}], servico.catalogo_terminal()
        )
        caminho = self.arquivos()[0]
        conteudo = caminho.read_bytes()
        servico.repositorio.exportar(venda)
        self.assertEqual(caminho.read_bytes(), conteudo)
        with self.assertRaises(FileExistsError):
            servico.repositorio.exportar(dict(venda, total=1))
        self.assertEqual(caminho.read_bytes(), conteudo)

    def test_terminal_do_estoque_consume_json_em_outro_processo(self):
        self.executar("1\n1\n2\n\ns\n0\n")
        origem = self.arquivos()[0]
        entrada = self.dados / "integracao" / "entrada"
        entrada.mkdir(parents=True)
        origem.rename(entrada / origem.name)
        resultado = subprocess.run(
            [sys.executable, "estoque.py", "--dados", str(self.dados)],
            input="2\n1\n0\n",
            text=True,
            encoding="utf-8",
            capture_output=True,
            cwd=RAIZ,
            timeout=15,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        persistido = json.loads(
            (self.dados / "sistema-estoque" / "data" / "estoque.json").read_text(
                encoding="utf-8"
            )
        )
        mouse = next(p for p in persistido["produtos"] if p["produto_id"] == 1)
        self.assertEqual(mouse["quantidade"], 48)
        self.assertTrue(
            (self.dados / "integracao" / "processados" / origem.name).exists()
        )
        self.assertIn("PROCESSADO", resultado.stdout)


if __name__ == "__main__":
    unittest.main()
