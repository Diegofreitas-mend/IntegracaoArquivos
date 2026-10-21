# Sistema de Estoque

Parte do trabalho de Técnicas de Integração de Sistemas. Consome os arquivos JSON
gerados pelo Sistema de Vendas, valida, atualiza as quantidades em estoque e organiza
os arquivos em `processados/` ou `erros/`.

## Como executar

```bash
cd sistema-estoque
pip install -r requirements.txt   # só o pytest
python -m src.main                # menu no terminal
pytest                            # testes automatizados
```

Menu: ver estoque · processar arquivos da entrada · monitorar entrada (automático,
a cada 3 s) · cadastrar produto · repor estoque.

Na primeira execução é criado `data/estoque.json` com 3 produtos de exemplo
(1-Mouse, 2-Teclado, 3-Monitor).

## Pastas (compartilhadas com Vendas e Transferência)

```
integracao/
  saida/        <- Vendas grava aqui
  entrada/      <- Transferência move para cá; Estoque lê daqui
  processados/  <- arquivos aceitos
  erros/        <- arquivos rejeitados (motivo no log)
sistema-estoque/
  data/estoque.json   <- produtos + controle de arquivos já processados
  logs/estoque.log
```

## Formato do arquivo de venda

```json
{
  "venda_id": 1001,
  "data_hora": "2026-10-20T10:30:00",
  "itens": [
    { "produto_id": 1, "quantidade": 2 },
    { "produto_id": 2, "quantidade": 1 }
  ]
}
```

## Regras de validação (RF03)

- JSON bem formado (UTF-8) e conteúdo é um objeto;
- `venda_id` presente; `itens` é uma lista não vazia;
- cada item tem `produto_id` existente no cadastro;
- `quantidade` é inteiro maior que zero;
- há saldo suficiente (itens repetidos do mesmo produto são somados).

A atualização é "tudo ou nada": se qualquer item for inválido, nenhum é baixado.

## Prevenção de duplicidade (RF05)

Cada arquivo processado é registrado com **hash SHA-256 do conteúdo**, nome e
`venda_id`. Um arquivo é recusado como duplicado se o hash OU o `venda_id` já foram
processados. O registro fica no mesmo `estoque.json` e é gravado junto com a baixa
(escrita atômica), então sobrevive a reinicializações e não há baixa em dobro se o
programa cair no meio.

## Arquivos de exemplo

`exemplos/` tem uma venda válida e três inválidas (JSON malformado, produto
inexistente, quantidade inválida) para copiar para `integracao/entrada/` e demonstrar.

## Mapa do código

| Arquivo | Responsabilidade |
|---|---|
| `src/main.py` | menu no terminal e modo monitor |
| `src/processador.py` | fluxo por arquivo: duplicidade → JSON → validação → baixa → mover |
| `src/validador.py` | regras de validação (RF03) |
| `src/repositorio_estoque.py` | leitura/gravação atômica do estoque e do controle de duplicidade |
| `src/log_config.py` | logs em arquivo e terminal |
| `src/config.py` | caminhos das pastas |
