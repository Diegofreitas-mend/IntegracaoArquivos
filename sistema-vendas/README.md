# Sistema de Vendas

Primeiro recorte funcional: catálogo, carrinho, total, histórico e exportação de vendas para o estoque. A interface usa o mesmo padrão visual do Sistema de Estoque.

Na raiz do repositório:

```bash
python app.py
```

Abra http://127.0.0.1:8000.

## Terminal (RF01)

Na raiz, execute `python vendas.py`. Dentro desta pasta, o comando equivalente
é `python -m src.main`. O menu permite registrar vendas, consultar o catálogo
de demonstração e listar o histórico. O JSON é gerado ao confirmar o pedido.

Para usar dados separados, execute `python vendas.py --dados CAMINHO` a partir
da raiz. O terminal usa Mouse, Teclado e Monitor como catálogo local inicial e
não consulta o estoque; o saldo é validado pelo consumidor do arquivo.

O histórico fica em `data/vendas/`, os preços em `data/precos.json` e os arquivos exportados em `../integracao/saida/`. Use **Sincronizar vendas** para transferir e processar os pedidos no estoque.

As vendas pendentes reservam o saldo disponível. Pedidos processados e rejeitados deixam de reservar saldo. Os valores de cada pedido são preservados no histórico mesmo depois de editar os preços do catálogo.

Clientes, pagamentos, descontos, cancelamentos e emissão fiscal ficam fora desta etapa. Consulte o [README principal](../README.md) para o fluxo de demonstração, arquitetura e testes.
