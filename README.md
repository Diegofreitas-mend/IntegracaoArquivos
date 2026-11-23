# Arvendro Gestão

Aplicação de vendas e estoque, integrada por arquivos JSON. Inclui cadastro
e login, carrinho, histórico, catálogo com preços, reposição e processamento de
arquivos. Os dados de cada sistema ficam em um banco de dados (Supabase). A
[identidade visual](docs/identidade/README.md) reúne a logo e suas regras.

## Executar

Requer **Python 3.11 ou superior**. Na pasta `IntegracaoArquivos`:

```powershell
python -m pip install -r requirements.txt
python app.py
```

Abra **http://127.0.0.1:8000**, crie uma conta ou entre. Encerre com `Ctrl+C`.
Ao iniciar, o terminal mostra qual banco está em uso.
Para alterar a porta e usar dados separados:

```powershell
python app.py --porta 8001 --dados CAMINHO
```

Os terminais independentes também aceitam `--dados CAMINHO`:

```powershell
python vendas.py
python estoque.py
```

Use a mesma raiz de dados nos terminais e transfira os JSONs da saída para a
entrada. O monitor do estoque processa somente os arquivos recebidos na entrada;
a transferência entre as pastas é manual.

## Banco de dados (Supabase)

1. Crie um projeto em [supabase.com](https://supabase.com) e guarde a senha do banco.
2. Em **Project Settings > Database > Connection string**, copie a URL do
   **Session pooler** (funciona em redes IPv4).
3. Copie `.env.example` para `.env` e cole a URL em `DATABASE_URL`, trocando
   `[YOUR-PASSWORD]` pela senha.

As tabelas são criadas automaticamente na primeira execução, com o estoque e os
preços iniciais. Elas aparecem no **Table Editor** do Supabase:

| Sistema | Tabela | Conteúdo |
|---|---|---|
| Vendas | `vendas`, `vendas_itens` | histórico de pedidos, com nome e preço de cada item no momento da venda |
| Vendas | `vendas_precos` | catálogo de preços |
| Estoque | `estoque_produtos` | produtos e saldo (nunca negativo) |
| Estoque | `estoque_processados` | arquivos já processados: `venda_id` e hash únicos (RF05) |
| Interface | `usuarios` | contas de acesso (salt e hash da senha, nunca a senha) |

Cada sistema acessa somente as próprias tabelas; vendas e estoque continuam se
comunicando apenas pelos arquivos JSON de `integracao/`. As tabelas têm RLS
ativado e nenhuma política, então a API pública do Supabase não as lê: só a
aplicação, conectada pela `DATABASE_URL`.

O `.env` contém a senha do banco e **não vai para o Git**. Compartilhe a URL com
a equipe por um canal privado.

**Sem `.env`**, ou com `--dados CAMINHO`, cada sistema usa um arquivo SQLite local
(`sistema-vendas/data/vendas.db`, `sistema-estoque/data/estoque.db` e
`dados/acesso.db`). Os testes usam sempre esse modo, então nunca alteram o
Supabase. A variável de ambiente `DATABASE_URL` é ignorada de propósito: só o
`.env` da raiz liga o banco real.

A baixa do estoque e o registro do arquivo processado acontecem na mesma
transação, e as chaves únicas do banco recusam uma segunda baixa da mesma venda.
Por isso o terminal e a web podem ser usados ao mesmo tempo sobre o mesmo
estoque. Se o banco ficar fora do ar, os arquivos permanecem na entrada e são
processados na próxima tentativa.

## Fluxo de uso

1. Em **Nova venda**, adicione produtos e registre o pedido.
2. Use **Atualizar estoque agora** ou **Sincronizar vendas** para confirmar a baixa.
3. Consulte o histórico e a integração para verificar pedidos e arquivos rejeitados.

O estoque inicial contém Mouse (50), Teclado (30) e Monitor (20), com preços de
R$ 79,90, R$ 149,90 e R$ 899,90. Novos produtos precisam de preço no catálogo antes
da venda. O terminal de vendas usa um catálogo inicial próprio; o consumidor
valida o saldo ao receber o JSON.

Pedidos pendentes reservam o saldo. O processamento ou a rejeição libera a reserva.
Preços alterados não modificam vendas anteriores. O carrinho permanece na aba ao
navegar ou recarregar e é limpo ao registrar a venda ou sair.

## Integração por arquivos

```text
integracao/
  saida/                      # vendas exportadas
  entrada/                    # arquivos recebidos pelo estoque
  processados/                # arquivos aceitos
  erros/                      # arquivos rejeitados ou duplicados
sistema-estoque/logs/         # motivos de rejeição e processamento
```

**Sincronizar vendas** transfere os arquivos e processa a fila. **Processar entrada**
consome somente o que já foi recebido. A venda é salva no banco antes da exportação;
se o envio falhar, o pedido é confirmado com um aviso e a sincronização reenvia
a mesma venda. ID e hash persistidos impedem outra baixa em reenvios.

Todas as contas compartilham os dados do sistema. Senhas usam salt e PBKDF2-SHA256
(600 mil iterações); sessões duram até 8 horas e terminam ao sair ou reiniciar o
servidor. O cookie é HttpOnly/SameSite. Após cinco tentativas incorretas, o login
bloqueia por um minuto. O servidor aceita somente acesso local.

## Organização

- `banco/`: conexão com o Supabase (PostgreSQL) ou SQLite e transações.
- `interface/`: servidor HTTP, autenticação, coordenação dos serviços e telas.
- `sistema-vendas/src/`: entidades, preços, registro e exportação de vendas.
- `sistema-estoque/src/`: validação, processamento, persistência e terminal.
- `tests/`: banco, autenticação, servidor, fluxo integrado e terminais.

As regras ficam nos serviços Python; a interface apresenta os dados e envia ações.
Clientes, pagamentos e emissão fiscal ficam fora do escopo atual.

## Testes

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/python -m unittest discover -s tests -v
cd sistema-vendas;  ../.venv/Scripts/python -m pytest -q; cd ..
cd sistema-estoque; ../.venv/Scripts/python -m pytest -q; cd ..
```

Execute as suítes originais separadamente, de dentro de cada pasta: ambas usam o
nome de pacote `src`.
