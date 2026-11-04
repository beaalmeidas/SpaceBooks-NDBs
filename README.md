# SpaceBooks-NDBs
E-commerce de livros e sistema de recomendação. Projeto final da disciplina de Implementação e Gestão de Bancos de Dados NoSQL, Ciência da Computação 26.2.

O projeto possui modelos de domínio, preparação do catálogo, conexões com MongoDB, Redis e Neo4j e carga inicial idempotente. A interface Streamlit e os serviços de catálogo, carrinho e checkout ainda serão implementados.

## Bancos locais com Docker

Requer Docker Desktop com containers Linux e Python 3.10 ou superior para gerar a configuração local. Na raiz do repositório:

```powershell
py -3 -m src.configure_env
docker compose up -d --wait
docker compose --profile tools run --rm --build tools python -m src.bootstrap --prepare --check-idempotence
```

O primeiro comando gera `.env` com senhas aleatórias e preserva o arquivo caso ele já exista. Não publique esse arquivo. `.env.example` documenta as variáveis; valores do ambiente têm prioridade sobre `.env` no Python. Em caso de conflito de portas, ajuste `MONGO_PORT`, `REDIS_PORT`, `NEO4J_HTTP_PORT` e `NEO4J_BOLT_PORT` antes de iniciar os serviços.

`DB_TIMEOUT_SECONDS` limita a espera por conexões e operações de rede (10 segundos por padrão). `DB_QUERY_TIMEOUT_SECONDS` define o limite de execução das consultas e a janela de repetição de transações do Neo4j (60 segundos), permitindo a carga inicial com índices ainda frios. Cada limite pode ser configurado até 120 segundos.

Os três bancos têm volumes persistentes e portas publicadas apenas em `127.0.0.1`. O serviço `tools` executa os comandos Python dentro do Compose e monta `data/prepared/` para salvar os arquivos gerados no computador. O arquivo `requirements-db.txt` contém as dependências dessa etapa, separado do ambiente de desenvolvimento já registrado em `requirements.txt`.

A carga cria índices no MongoDB, incluindo e-mail único normalizado, busca textual de livros e histórico de pedidos; cria constraints únicas no Neo4j; carrega livros, clientes, categorias e preferências em lotes; verifica as referências e repete a carga para comparar as contagens. O Redis é testado com uma chave temporária que expira de verdade. Não são criados carrinhos, sessões, compras ou avaliações fictícias.

Executar a carga novamente atualiza metadados bibliográficos, mas **preserva preço, estoque e moeda existentes**. Clientes existentes também são preservados. Os relacionamentos iniciais usam `MERGE`: repetir a carga não cria duplicatas. A carga é aditiva, não remove registros ou preferências antigos e não é uma transação distribuída. Em caso de interrupção entre bancos, corrija a causa e execute novamente.

Para verificar sem carregar dados ou apenas testar conexões:

```powershell
docker compose --profile tools run --rm tools python -m src.bootstrap --verify-only
docker compose --profile tools run --rm tools python -m src.check_connections
docker compose ps
```

Abra o Neo4j Browser em `http://localhost:7474`, usuário `neo4j`, com a senha de `NEO4J_PASSWORD` no `.env`. Para parar os containers mantendo os dados:

```powershell
docker compose down
```

As credenciais configuram bancos novos. Editar `.env` após a criação dos volumes não altera automaticamente as senhas armazenadas nos bancos.

Se o build falhar com `CERTIFICATE_VERIFY_FAILED` em uma rede com certificado local confiável, exporte as autoridades certificadoras públicas do computador e forneça-as apenas durante o build:

```powershell
py -3 -m src.export_build_ca
docker compose -f compose.yaml -f compose.build-ca.yaml --profile tools build tools
docker compose --profile tools run --rm tools python -m src.bootstrap --prepare --check-idempotence
```

O bundle fica em `.local/`, ignorado pelo Git, e é montado como [segredo de build do Docker](https://docs.docker.com/build/building/secrets/). A verificação TLS permanece ativa. Em outro sistema, também é possível fornecer um bundle PEM confiável através de `PIP_CA_FILE` com o arquivo `compose.build-ca.yaml`.

## Executar Python no computador

Como alternativa ao serviço `tools`, com os bancos já iniciados:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-db.txt
.\.venv\Scripts\python.exe -m src.bootstrap --prepare --check-idempotence
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Para incluir testes com os bancos reais (repetem a carga e verificam a preservação de preço/estoque usando um documento temporário):

```powershell
$env:SPACEBOOKS_INTEGRATION = "1"
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_database_integration.py -v
Remove-Item Env:SPACEBOOKS_INTEGRATION
```

## Executar

Requer Python 3.10 ou superior. Modelos e preparação usam apenas a biblioteca padrão; os testes de integração e de configuração exigem `requirements-db.txt`. O notebook exploratório tem dependências próprias.

Na raiz do repositório:

```powershell
py -3 -m src.prepare_data
```

Em sistemas que usam `python`, substitua `py -3` por `python`.

A preparação lê `data/books-processed.csv` e `data/users.csv`, preserva os CSVs originais e gera em `data/prepared/`:

| Arquivo | Conteúdo |
| --- | --- |
| `books.jsonl` | Livros com preços em centavos e estoque fictícios |
| `customers.jsonl` | Clientes com preferências convertidas em listas |
| `graph.jsonl` | Nós e relacionamentos para o carregador Neo4j |
| `manifest.json` | Quantidades, regras de geração e hashes SHA-256 das entradas |

As saídas são reproduzíveis e estão no `.gitignore`. O comando de preparação não se conecta aos bancos. O JSONL do grafo é um formato interno consumido por `src.bootstrap`, não um dump nativo do Neo4j.

Para escolher outros caminhos:

```powershell
py -3 -m src.prepare_data --books data/books-processed.csv --users data/users.csv --output data/prepared
```

Preços de R$ 19,90 a R$ 149,90 e estoques de 5 a 50 unidades são gerados a partir do SHA-256 do ISBN. São valores exclusivos de demonstração, estáveis entre execuções. Os dados são validados antes de substituir as saídas. Identificadores duplicados e preferências sem correspondência no catálogo interrompem a preparação com erro.

## Organização

| Caminho | Responsabilidade |
| --- | --- |
| `src/domain/models.py` | Modelos e regras de domínio |
| `src/prepare_data.py` | Conversão e validação dos CSVs |
| `src/database/` | Configuração, conexões, índices, carga e verificação |
| `src/bootstrap.py` | Inicialização e validação dos bancos |
| `src/check_connections.py` | Diagnóstico das conexões e TTL do Redis |
| `src/notebooks/books-exploration.ipynb` | Exploração e limpeza original |
| `tests/` | Testes de domínio e preparação |
| `docs/data-model.md` | Contratos dos dados e dos bancos |

Consulte [a modelagem dos dados](docs/data-model.md) para os campos, identificadores, regras do checkout e responsabilidades de cada banco.
