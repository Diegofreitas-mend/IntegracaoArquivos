# Arvendro Gest?o

Aplica??o local de vendas e estoque, integrada por arquivos JSON. Inclui cadastro
e login, carrinho, hist?rico, cat?logo com pre?os, reposi??o e processamento de
arquivos. A [identidade visual](docs/identidade/README.md) re?ne a logo e suas regras.

## Executar

Requer **Python 3.11 ou superior**, sem depend?ncias para executar a aplica??o.
Na pasta `IntegracaoArquivos`:

```powershell
python app.py
```

Abra **http://127.0.0.1:8000**, crie uma conta ou entre. Encerre com `Ctrl+C`.
Para alterar a porta e usar dados separados:

```powershell
python app.py --porta 8001 --dados CAMINHO
```

Os terminais independentes tamb?m aceitam `--dados CAMINHO`:

```powershell
python vendas.py
python estoque.py
```

Use a mesma raiz de dados nos terminais e transfira os JSONs da sa?da para a
entrada. O monitor do estoque processa somente os arquivos recebidos na entrada;
a transfer?ncia entre as pastas ? manual.

**Execute uma inst?ncia por pasta de dados.** Evite alterar o mesmo estoque pelo
terminal e pela web simultaneamente. A escrita at?mica impede arquivos parciais,
mas n?o coordena processos concorrentes.

## Fluxo de uso

1. Em **Nova venda**, adicione produtos e registre o pedido.
2. Use **Atualizar estoque agora** ou **Sincronizar vendas** para confirmar a baixa.
3. Consulte o hist?rico e a integra??o para verificar pedidos e arquivos rejeitados.

O estoque inicial cont?m Mouse (50), Teclado (30) e Monitor (20), com pre?os de
R$ 79,90, R$ 149,90 e R$ 899,90. Novos produtos precisam de pre?o no cat?logo antes
da venda. O terminal de vendas usa um cat?logo inicial pr?prio; o consumidor
valida o saldo ao receber o JSON.

Pedidos pendentes reservam o saldo. O processamento ou a rejei??o libera a reserva.
Pre?os alterados n?o modificam vendas anteriores. O carrinho permanece na aba ao
navegar ou recarregar e ? limpo ao registrar a venda ou sair.

## Dados e integra??o

```text
dados/acesso.json              # contas locais
sistema-vendas/data/           # pre?os e hist?rico de vendas
sistema-estoque/data/          # estoque e controle de duplicidade
sistema-estoque/logs/          # motivos de rejei??o e processamento
integracao/
  saida/                      # vendas exportadas
  entrada/                    # arquivos recebidos pelo estoque
  processados/                # arquivos aceitos
  erros/                      # arquivos rejeitados ou duplicados
```

**Sincronizar vendas** transfere os arquivos e processa a fila. **Processar entrada**
consome somente o que j? foi recebido. O hist?rico ? salvo antes da exporta??o;
se o envio falhar, o pedido ? confirmado com um aviso e a sincroniza??o reenvia
a mesma venda. ID e hash persistidos impedem outra baixa em reenvios.

Os dados gerados ficam fora do Git. Todas as contas compartilham os dados do
sistema. Senhas usam salt e PBKDF2-SHA256 (600 mil itera??es); sess?es duram at?
8 horas e terminam ao sair ou reiniciar o servidor. O cookie ? HttpOnly/SameSite.
Ap?s cinco tentativas incorretas, o login bloqueia por um minuto. O servidor aceita
somente acesso local.

## Organiza??o

- `interface/`: servidor HTTP, autentica??o, coordena??o dos servi?os e telas.
- `sistema-vendas/src/`: entidades, pre?os, registro e exporta??o de vendas.
- `sistema-estoque/src/`: valida??o, processamento, persist?ncia e terminal.
- `tests/`: autentica??o, servidor, fluxo integrado e terminais.

As regras ficam nos servi?os Python; a interface apresenta os dados e envia a??es.
Clientes, pagamentos e emiss?o fiscal ficam fora do escopo atual.

## Testes

```powershell
python -m unittest discover -s tests -v
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/python -m pytest -q sistema-vendas
.venv/Scripts/python -m pytest -q sistema-estoque
```

Execute as su?tes originais separadamente: ambas usam o nome de pacote `src`.
