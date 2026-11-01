# MarginMiner
MarginMiner for screening and portfolio control

# Minha carteira — base inicial

Aplicativo local em Python, Streamlit, pandas e SQLite. Um único banco guarda usuários, ativos, lançamentos e cotações. Sem dados pessoais ou senhas predefinidas no pacote.

## Preparar no Arch Linux / VS Code

Extraia este ZIP e abra **a pasta carteira** no VS Code.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python init_db.py
python -m streamlit run app.py --server.address 127.0.0.1
```

Se aparecer erro de módulo sqlite3 no seu Python, verifique a instalação do Python/SQLite no sistema. O aplicativo cria automaticamente `data/carteira.sqlite3`, inclusive se você não executar init_db.py. A localização independe da pasta atual do terminal. Opcional: variável `CARTEIRA_DB` com outro caminho.

No Windows: use `py -m venv .venv`, depois `.venv\Scripts\activate`. No VS Code, escolha `.venv\Scripts\python.exe` como interpretador.

Instale as extensões **Python** e **Python Debugger**, da Microsoft. Execute **Python: Select Interpreter**, escolha `.venv`, abra app.py e pressione **F5** com a configuração “Carteira: Streamlit”. Coloque breakpoints em app.py ou core.py; interaja no navegador para executar o trecho. A configuração fornecida inicia o servidor em localhost:8501. Não inicie dois servidores na mesma porta. Atualizações no código provocam recarregamento pelo Streamlit; não é preciso abrir outra aba.

No primeiro acesso, crie login, nome e senha (10+ caracteres). Depois use o login. A senha usa scrypt com salt individual, não texto puro. Atualizar a página pode exigir entrar novamente. Usuários adicionais são criados pelo terminal:

```bash
python create_user.py
```

Cada usuário tem seus próprios ativos, lançamentos e cotações. Não há cadastro público depois do primeiro usuário, recuperação de senha ou perfis administrativos nesta versão. Não publique esta versão na internet sem preparar HTTPS, proteção contra tentativas repetidas e revisar autenticação e implantação.

## Primeiro uso

1. Cadastre um ativo em BRL.
2. Lance o aporte inicial no caixa.
3. Lance a compra (quantidade, preço e taxas).
4. Cadastre/importe cotações desde a primeira posição.
5. Veja a série diária e o valor da cota em Resumo.

Há validação de saldo e posições negativos. Inclua todo o histórico desde o início; posições antigas não podem aparecer sem compras e aportes correspondentes. Dentro de cada data, a ordem deve ser positiva e única. Lançamentos retroativos e exclusões revalidam os movimentos posteriores e são revertidos se deixarem o histórico inválido. Para corrigir um lançamento, exclua e recadastre; se houver dependências, pode ser necessário corrigir do mais recente para o mais antigo. Edição direta fica para a próxima versão.

## Eventos implementados

| Tipo | Efeito | Campos |
|---|---|---|
| APORTE / RETIRADA | Entrada / saída externa de caixa | valor total |
| COMPRA / VENDA | Altera posição e caixa | quantidade, preco e taxas |
| DIVIDENDO / JCP | Receita interna em caixa | valor total líquido recebido |
| TAXA | Despesa interna em caixa | valor total |
| DESDOBRAMENTO | Multiplica quantidade pelo fator > 1 | fator; exemplo 2 |
| GRUPAMENTO | Multiplica quantidade pelo fator entre 0 e 1 | fator; exemplo 0,1 |
| BONIFICACAO | Soma ações recebidas à posição | quantidade adicional |
| AMORTIZACAO | Credita caixa, mantendo a quantidade | valor total recebido |
| LIQUIDACAO | Zera toda a posição e credita caixa | valor total recebido |

Quantidade e valores são positivos; o tipo determina o sinal. Campos não aplicáveis devem ficar em zero (fator = 1). Não há custo fiscal, imposto, custo médio, custo atribuído a bonificações, frações vendidas em leilão ou liquidação parcial. Incorporações, cisões e conversões entre ativos **não são implementadas**, e não devem ser substituídas por vendas fictícias: exigem regras próprias. Amortização aqui só trata caixa, sem ajuste fiscal de custo.

## Cotização

O sistema começa com valor de cota 1. Aportes emitem cotas e retiradas resgatam cotas. Compras, vendas, taxas e dividendos são internos; não emitem cotas. Dividendos ficam no caixa até compra/retirada explícita. O patrimônio é saldo mais quantidade multiplicada pelo preço de fechamento.

**Convenção diária:** todos os fluxos externos são considerados no começo do dia, pelo valor da cota anterior. É uma cotização com convenção de início do dia, não TWR intradiário exato. Não usamos horários nem valores da carteira imediatamente antes de cada fluxo. Não atribua precisão intradiária ao resultado. Variação da primeira cota também entra no retorno acumulado. Ao encerrar todas as posições e retirar todo o saldo, mantém-se o último valor da cota; novos aportes retomam essa mesma série.

Dias sem cotação usam o último preço conhecido. Ausência de qualquer preço anterior para uma posição bloqueia a série; preços com mais de 7 dias geram alerta. Isso não substitui validar se todos os pregões estão presentes. Na data de um desdobramento/grupamento sem cotação nova, o preço anterior é ajustado pelo fator para evitar ganho fictício. Bonificações precisam de atenção à cotação na data do evento.

As cotações devem ser em BRL e **historicamente não ajustadas por dividendos nem por desdobramentos**, porque ambos são tratados em lançamentos. O campo “Close” de uma fonte nem sempre atende essa definição; verifique antes de importar. Coleta automática Yahoo ainda não está implementada. Multimoeda, Tesouro com regras de cotação específicas, accrual e câmbio não estão implementados.

TWR com avaliação em cada fluxo, XIRR/TIR com datas, CAGR, drawdown, análise de empresas e valuation são próximas etapas; não há resultados simulados desses métodos na interface. XIRR é a modalidade de TIR que considera datas irregulares.

## Importação / exportação

A interface exporta:
- JSON com todos os dados financeiros do usuário, sem credenciais.
- CSV dos lançamentos e das cotações.
- CSV da série de cotização calculada.

Restaure JSON somente em usuário sem ativos e lançamentos; todo o lote é transacional. Isso evita sobrescrever carteiras existentes. Não transfere a conta nem a senha. Para backup completo, pare o aplicativo e copie `data/carteira.sqlite3`, que inclui todas as contas e hashes de senha.

CSV usa UTF-8 e separador ponto e vírgula. Datas em AAAA-MM-DD. Decimais aceitam ponto ou vírgula, sem separador de milhar. Cadastre os ativos antes. Use os cabeçalhos exportados. IDs vazios são criados automaticamente; reimportar linhas sem ID **duplica** lançamentos. Preserve IDs exportados para reimportação idempotente. Mesmo ID e dados diferentes rejeitam todo o lote; a importação não edita registros existentes. A ordem no dia não pode repetir. Cotações repetidas para mesmo usuário/ativo/data são atualizadas explicitamente; as demais datas são mantidas. Exemplos sintéticos em `examples/`.

## Organização técnica e testes

- `core.py`: acesso SQLite, validações, movimentações, importação/exportação e cotização.
- `app.py`: interface e login.
- `schema.sql`: esquema consultável; `init_db.py` inicializa o banco.
- `.vscode/`: configuração de depuração.
- `tests/`: testes do domínio e persistência, sem usar dados reais.

```bash
python -m unittest discover -s tests -v
```

Valores são persistidos como texto decimal e calculados com `Decimal`; float é usado somente na apresentação da série/gráfico. O acesso ao SQLite fica centralizado em Store. Não usamos SQLAlchemy nesta base: uma migração para MariaDB exigirá adaptar Store, DDL, UPSERTs e transferir os dados. A interface e as regras de cálculo ficam separadas dessa troca. Não troque apenas a conexão esperando migração automática.

Esta é uma base de desenvolvimento funcional, ainda sem certificação contábil ou fiscal.

Validação desta entrega: 9 testes passaram (8 de domínio/persistência e 1 de interface cobrindo criação de conta, login e navegação). Executado com Python 3.12, Streamlit 1.66.1 e pandas 2.2.3. O ambiente virtual precisa ser criado na sua máquina; não é distribuído no ZIP.
