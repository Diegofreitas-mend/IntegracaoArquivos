# IntegracaoArquivos

Trabalho de Técnicas de Integração de Sistemas: integração por **troca de arquivos**
entre um Sistema de Vendas e um Sistema de Estoque.

```
Sistema de Vendas  --grava-->  integracao/saida/
Transferência      --move--->  integracao/entrada/
Sistema de Estoque --lê------> integracao/entrada/  --> processados/ ou erros/
```

| Componente | Pasta | Persistência |
|---|---|---|
| Sistema de Vendas | [sistema-vendas/](sistema-vendas/) | SQLite (`sistema-vendas/data/vendas.db`) |
| Transferência | [transferencia/](transferencia/) | nenhuma, só move os arquivos |
| Sistema de Estoque | [sistema-estoque/](sistema-estoque/README.md) | JSON (`sistema-estoque/data/estoque.json`) |

Só usa a biblioteca padrão do Python (3.10+). O `pytest` é necessário apenas para os testes.

## Formato do arquivo trocado

```json
{
  "venda_id": 1,
  "data_hora": "2026-10-20T10:30:00",
  "itens": [
    { "produto_id": 1, "quantidade": 2 },
    { "produto_id": 2, "quantidade": 1 }
  ]
}
```

Os IDs de produto são os mesmos nos dois sistemas (1-Mouse, 2-Teclado, 3-Monitor).

## Como demonstrar

Abra três terminais na raiz do repositório:

```bash
# Terminal 1 - Estoque: opção 3 (monitorar entrada)
cd sistema-estoque && python -m src.main

# Terminal 2 - Transferência em modo contínuo
cd transferencia && python -m src.transferencia --monitorar

# Terminal 3 - Vendas: opção 2 (registrar venda)
cd sistema-vendas && python -m src.main
```

1. No Estoque, opção 1 mostra o saldo inicial; depois, opção 3 para monitorar.
2. No Vendas, registre uma venda (ex.: produto 1, quantidade 2; ID 0 encerra).
   O arquivo é gravado em `integracao/saida/`.
3. A Transferência move o arquivo para `integracao/entrada/`.
4. O Estoque valida, dá baixa e move o arquivo para `integracao/processados/`.
5. Casos de erro: copie os arquivos de [sistema-estoque/exemplos/](sistema-estoque/exemplos/)
   para `integracao/entrada/` e veja-os irem para `integracao/erros/` com o motivo no log.
   Copiar de novo um arquivo já processado demonstra a recusa por duplicidade.

Para recomeçar do zero, apague `sistema-vendas/data/`, `sistema-estoque/data/`,
`sistema-estoque/logs/` e os `.json` dentro de `integracao/`. Apague **os dois**
bancos juntos: o Vendas recomeça os IDs em 1, e o Estoque recusaria essas vendas
como duplicadas.

## Testes

```bash
pip install pytest
(cd sistema-vendas && pytest)
(cd transferencia && pytest)
(cd sistema-estoque && pytest)
```
