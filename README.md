# SpaceBooks-NDBs
E-commerce de livros e sistema de recomendação. Projeto final da disciplina de Implementação e Gestão de Bancos de Dados NoSQL, Ciência da Computação 26.2.

O projeto possui modelos de domínio, preparação do catálogo, conexões com MongoDB, Redis e Neo4j, carga inicial idempotente e catálogo Streamlit integrado ao MongoDB com cache Redis. Sessões, carrinho, recomendações e checkout ainda serão implementados.

## Catálogo com MongoDB

Com a carga inicial já executada, instale as dependências da interface e inicie o catálogo na raiz do repositório:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-app.txt
.\.venv\Scripts\python.exe -m streamlit run src/catalogo.py
```

Abra `http://localhost:8501`. A tela usa `CachedCatalogService` para busca literal por título ou autor, filtro por categoria, ordenação por título/preço e páginas de 24 livros. Em um acerto de cache, a resposta vem do Redis; em ausência, expiração ou falha do Redis, `MongoCatalogService` consulta `books`. Preço e estoque têm origem nos documentos cadastrados. Clique em **Atualizar catálogo** após editar um livro no Compass para invalidar imediatamente o cache. Sem invalidação, as entradas expiram pelo TTL. `st.cache_resource` compartilha apenas clientes/serviços; os resultados são armazenados no Redis.

Também é possível executar a interface no Docker:

```powershell
docker compose --profile app up -d --build catalog
```

Em redes com o erro TLS de build já descrito neste README, use o bundle exportado:

```powershell
docker compose -f compose.yaml -f compose.build-ca.yaml --profile app up -d --build catalog
```

O serviço `catalog` depende apenas do MongoDB e usa `requirements-app.txt`. O Python local lê as variáveis MongoDB do `.env` sem exigir credenciais Redis/Neo4j; o Compose usa o endereço interno do serviço. `STREAMLIT_PORT` permite trocar a porta publicada.

## Cache do catálogo no Redis

Inicie o Redis para habilitar o cache; ele continua sendo opcional para a navegação:

```powershell
docker compose up -d --wait mongodb redis
```

As buscas paginadas, detalhes dos livros e categorias usam JSON com TTL padrão de 60 segundos. Configure `CATALOG_CACHE_TTL_SECONDS` (1–3600 s) e `REDIS_CACHE_TIMEOUT_SECONDS` (0–5 s, maior que zero; padrão 0,25 s) no `.env` e reinicie o catálogo para aplicar. O cliente de cache não faz tentativas automáticas após falhas, permitindo consultar o MongoDB rapidamente. `REDIS_URL` tem prioridade sobre `REDIS_PASSWORD` e `REDIS_PORT`; sem configuração Redis válida, o catálogo usa somente MongoDB.

Chaves: `catalog:v1:generation`, `catalog:v1:{generation}:search:{digest}`, `catalog:v1:{generation}:categories` e `product:v1:{generation}:{isbn}`. O digest considera pesquisa normalizada, categoria, ordenação, página e tamanho da página. Cada ambiente/conjunto de dados deve usar seu próprio banco lógico Redis (`REDIS_URL`), evitando compartilhar essas chaves entre catálogos diferentes.

A invalidação troca a geração, sem apagar sessões/carrinhos ou executar `FLUSHDB`. A carga inicial invalida automaticamente, inclusive quando termina com erro parcial. O botão **Atualizar catálogo** usa a mesma rotina. Para edições externas pelo Compass, também é possível invalidar pela linha de comando:

```powershell
.\.venv\Scripts\python.exe -m src.invalidate_catalog_cache
# Retomar uma invalidação pendente depois de restabelecer o Redis:
.\.venv\Scripts\python.exe -m src.invalidate_catalog_cache --retry-only
```

Com a interface em Docker, o equivalente é `docker compose exec -T catalog python -m src.invalidate_catalog_cache`. Uma falha Redis mantém a intenção no MongoDB, na coleção `catalog_cache_state`. A retomada acontece em uma ausência de cache, após recuperação percebida pelo mesmo serviço ou pelo comando acima. Uma instância que não percebeu a falha pode servir entradas antigas até o TTL. Novos serviços que alterarem preço, estoque ou metadados devem chamar `CatalogInvalidator.invalidate()` após persistir a alteração; o checkout ainda será implementado.

Para executar os testes de cache com os bancos reais:

```powershell
$env:SPACEBOOKS_INTEGRATION = "1"
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_catalog_cache*.py" -v
Remove-Item Env:SPACEBOOKS_INTEGRATION
```

Os testes cobrem acertos, ausência de cache, expiração real, invalidação, dados corrompidos, recuperação após indisponibilidade e concorrência. Usam coleções e chaves temporárias próprias. No RedisInsight, explore `catalog:v1:*` e `product:v1:*` e consulte `TTL <chave>`; a leitura não renova a expiração.

Testes da interface e do serviço (instale `requirements-app.txt` primeiro):

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
$env:SPACEBOOKS_INTEGRATION = "1"
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_catalog*.py" -v
Remove-Item Env:SPACEBOOKS_INTEGRATION
```

Os testes de integração do catálogo criam uma coleção temporária própria e a removem ao terminar. Eles verificam busca, paginação, filtros e atualização de preço/estoque na interface sem alterar os livros da aplicação. Veja [o registro das mudanças do catálogo](docs/data-model.md#integração-do-catálogo-com-mongodb).

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

`--verify-only` também inspeciona as coleções, as definições dos índices MongoDB e as constraints de unicidade do Neo4j, sem recriá-los. `--check-idempotence` compara as contagens e os valores de preço, estoque e moeda antes/depois da repetição; também confere que a primeira carga preservou os valores comerciais já existentes.

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
| `src/services/catalog.py` | Consulta paginada ao MongoDB, independente da interface |
| `src/services/cached_catalog.py` | Cache de buscas, detalhes e categorias com fallback MongoDB |
| `src/services/catalog_cache.py` | Primitivas Redis e invalidação compartilhada |
| `src/invalidate_catalog_cache.py` | Invalidação manual e retomada de pendências |
| `src/catalogo.py` | Catálogo Streamlit com busca, filtros e preço/estoque atuais |
| `src/database/` | Configuração, conexões, índices, carga e verificação |
| `src/bootstrap.py` | Inicialização e validação dos bancos |
| `src/check_connections.py` | Diagnóstico das conexões e TTL do Redis |
| `src/notebooks/books-exploration.ipynb` | Exploração e limpeza original |
| `tests/` | Testes de domínio e preparação |
| `docs/data-model.md` | Contratos dos dados e dos bancos |

Consulte [a modelagem e os contratos compartilhados](docs/data-model.md) para os campos, identificadores, chaves Redis, TTLs, sessões, regras do checkout e responsabilidades de cada banco. As interfaces Python dos futuros serviços estão em `src/domain/contracts.py`; são contratos, sem implementação dos serviços.
