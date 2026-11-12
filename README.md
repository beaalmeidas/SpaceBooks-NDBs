# SpaceBooks-NDBs
E-commerce de livros e sistema de recomendação. Projeto final da disciplina de Implementação e Gestão de Bancos de Dados NoSQL, Ciência da Computação 26.2.

O projeto possui modelos de domínio, preparação do catálogo, conexões com MongoDB, Redis e Neo4j, carga inicial idempotente, catálogo Streamlit com cache Redis, identificação demonstrativa, carrinhos, checkout transacional e avaliações/recomendações personalizadas com Neo4j.

## Instalação a partir de um clone limpo

Pré-requisitos: Git, Docker Desktop com containers Linux e Docker Compose v2 ou superior. Para os comandos locais, prefira Python 3.12 (a versão da imagem Docker); a aplicação requer Python 3.10 ou superior. Os exemplos usam PowerShell, na raiz do repositório. No Linux/macOS, use `python3` no lugar de `py -3` e `.venv/bin/python` no lugar de `.venv\Scripts\python.exe`.

### 1. Obter o projeto e gerar a configuração

Clone o repositório pela URL fornecida na entrega e entre em `SpaceBooks-NDBs`. Em seguida:

```powershell
py -3 -m src.configure_env
```

O comando usa somente a biblioteca padrão e gera `.env` com senhas aleatórias, preservando um arquivo existente. Não use os placeholders `CHANGE_ME_*` como credenciais reais. Confira as portas no `.env` antes de subir os bancos; o padrão MongoDB é `27017`. Não é necessário copiar arquivos da máquina dos autores.

### 2. Iniciar os bancos e carregar os dados

```powershell
docker compose up -d mongodb redis neo4j mongo-init
docker compose --profile tools run --rm --build tools python -m src.bootstrap --prepare --check-idempotence
```

Aguarde o segundo comando terminar com sucesso. Ele prepara os CSVs, cria índices/constraints, carrega os dados e repete a carga para verificar idempotência e preservação de preço/estoque. A primeira inicialização pode levar alguns minutos. Em redes que exigem certificado próprio, siga a seção de certificados abaixo antes do build.

### 3. Executar e demonstrar

```powershell
docker compose --profile app up -d --build catalog
docker compose exec -T catalog python -m src.check_connections
# Opcional: perfis com compras e avaliações fictícias
docker compose exec -T catalog python -m src.seed_recommendation_demo
```

Abra **http://localhost:8501**. Na identificação demonstrativa, busque `DEMO`, selecione um perfil, navegue pelo catálogo, adicione um livro, revise e confirme a compra. O número do pedido permite consultar sua confirmação e retomar integrações pendentes. Não há cobrança financeira. As seções seguintes detalham as telas e os perfis.

### 4. Executar os testes

Com a preparação/carga concluída e o container `catalog` iniciado:

```powershell
# Gerar os JSONL também dentro do container usado pelos testes de carga
docker compose exec -T catalog python -m src.prepare_data
# Sem integrações; os casos que exigem bancos são ignorados
docker compose exec -T catalog python -m unittest discover -s tests -v
# Suíte completa: bancos reais e interface AppTest
docker compose exec -T -e SPACEBOOKS_INTEGRATION=1 catalog python -m unittest discover -s tests -v
# Somente o fluxo completo e cenários de falha
docker compose exec -T -e SPACEBOOKS_INTEGRATION=1 catalog python -m unittest tests.test_system_flow -v
```

Na instalação local, instale `requirements.txt` em um ambiente virtual e substitua `docker compose exec -T catalog python` por esse Python. No PowerShell, habilite integrações com `$env:SPACEBOOKS_INTEGRATION = "1"` e remova a variável com `Remove-Item Env:SPACEBOOKS_INTEGRATION` ao terminar. A suíte completa também repete a carga regular; execute-a em um ambiente de desenvolvimento/demonstração. Os demais cenários criam dados temporários e fazem sua limpeza.

Os três testes da auditoria de entrega exigem Git e são ignorados na imagem da aplicação, que não inclui esse executável. Execute-os no computador com `py -3 -m unittest tests.test_delivery -v`; eles usam somente a biblioteca padrão e repositórios temporários.

Para diagnóstico: `docker compose ps`, `docker compose logs --tail 100 catalog mongo-init` e `docker compose --profile tools run --rm tools python -m src.bootstrap --verify-only`. Para parar mantendo os dados: `docker compose down`. A opção `down -v` apaga os volumes e não é necessária para executar o projeto.

## Dependências da aplicação e do notebook

| Arquivo | Finalidade |
| --- | --- |
| `requirements.txt` | Instalação padrão; inclui `requirements-app.txt` |
| `requirements-app.txt` | Streamlit e clientes dos bancos; imagem da aplicação |
| `requirements-db.txt` | PyMongo, Redis, Neo4j e dotenv; imagem de preparação/carga |
| `requirements-notebook.txt` | Pandas, NumPy, Matplotlib, Pillow, Requests e Jupyter; opcional |

O antigo congelamento de um ambiente com pacotes sem uso foi substituído pelas dependências do projeto. Os arquivos declaram faixas de versões; não há lock de todas as dependências transitivas. O notebook não é necessário para executar a aplicação.

Para manter a exploração separada:

```powershell
py -3.12 -m venv .venv-notebook
.\.venv-notebook\Scripts\python.exe -m pip install -r requirements-notebook.txt
.\.venv-notebook\Scripts\python.exe -m jupyterlab
```

Abra `src/notebooks/books-exploration.ipynb`. O notebook registra a exploração original; downloads de capas por URL exigem internet e podem não estar disponíveis. Os CSVs necessários à aplicação já acompanham o projeto.

## Limitações e dados fictícios

- A identificação é demonstrativa, sem senha; selecionar um cadastro não comprova a identidade da pessoa.
- Os cadastros demonstrativos usam e-mails `example.com`; preços e estoques iniciais são fictícios e determinísticos. Os perfis `DEMO_REC_*` possuem compras/avaliações simuladas identificadas. Compras simuladas no grafo não representam pedidos MongoDB. Lucas Espindola também é um cadastro para demonstração. Médias importadas são separadas das avaliações individuais.
- Checkout não inclui pagamento, frete ou reserva de estoque no carrinho. O estoque é validado e baixado na confirmação, preservando os preços históricos do pedido.
- MongoDB usa replica set de um nó para transações. Não há transação distribuída entre os três bancos. Pendências após a compra ficam no MongoDB e são retomadas por consulta, repetição da tentativa ou `python -m src.retry_checkout`; não há trabalhador automático.
- Edições externas pelo Compass exigem invalidação do cache ou expiração do TTL. Sem Redis, o catálogo público continua disponível, mas sessões e carrinhos ficam indisponíveis. Recomendações exigem conferir o histórico Neo4j antes de aplicar a alternativa por preferências.
- Portas são publicadas em `127.0.0.1`. Autenticação real, publicação externa, TLS de aplicação, backups e monitoramento não fazem parte desta entrega local.

## Conferência dos arquivos de entrega

```powershell
py -3 -m src.check_delivery --history
py -3 -m unittest tests.test_delivery -v
git status --short
```

A auditoria examina arquivos rastreados e novos não ignorados, padrões de credenciais e correspondências com senhas locais. Com `--history`, também examina os blobs alcançáveis do histórico Git. Não imprime os valores encontrados. É uma verificação de escopo conhecido, não uma garantia de detecção de qualquer segredo.

`.env`, variantes locais, ambientes virtuais, certificados/chaves, `.local/`, saídas `data/prepared/` e configurações de editores/agentes devem ficar fora do Git. Entregue apenas `.env.example` com placeholders. O `.dockerignore` também exclui arquivos privados do contexto de build. Não inclua volumes Docker ou saídas geradas: os comandos de instalação reconstroem o ambiente.

Arquivos novos precisam integrar o commit final para aparecerem em outro clone. Consulte o [registro da validação de entrega](docs/delivery.md).

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

O serviço `catalog` aguarda o MongoDB e seu inicializador de replica set e usa `requirements-app.txt`. O catálogo público pode consultar somente MongoDB; identificação e carrinho exigem Redis, e o checkout usa também Neo4j com recuperação de pendências. O Python local lê o `.env`; o Compose usa os endereços internos dos serviços. `STREAMLIT_PORT` permite trocar a porta publicada.

## Navegação e validação do fluxo completo

O seletor **Navegar** reúne **Visão geral**, **Catálogo**, **Carrinho**, **Checkout** e **Recomendações**. A visão geral mantém os painéis na mesma página; as demais opções abrem cada etapa diretamente. A identificação fica no cabeçalho e é preservada ao mudar de tela. Carrinho, checkout e recomendações exigem um cliente identificado. Sair, trocar de cliente ou expirar a sessão descarta os dados locais anteriores.

Nas telas dedicadas, adicionar um livro no catálogo ou nas recomendações abre o carrinho. Use **Salvar quantidade** para confirmar alterações e **Ir para checkout** para revisar a compra. **Editar carrinho** permite corrigir os itens e **Voltar ao catálogo** retoma a navegação. O UUID e a revisão de uma tentativa de compra permanecem ao alternar as telas, permitindo consultar ou repetir a mesma tentativa após uma resposta perdida.

Erros de serviço são apresentados de forma uniforme; sessão expirada limpa a identidade e solicita nova identificação. Uma compra persistida com integração pendente continua mostrando confirmação e número do pedido. O resumo anterior do carrinho é substituído pelo estado de limpeza confirmado ou por uma orientação para consultar/atualizar, evitando apresentar os itens antigos como se ainda precisassem ser comprados.

Os cenários de aceitação executam ações de interface pelo Streamlit AppTest, conectados aos três bancos reais com banco MongoDB, chaves Redis e IDs Neo4j temporários. Incluem compra completa, navegação com identidade preservada, estoque insuficiente, repetição da confirmação, sessão expirada, carrinhos independentes, atualização das recomendações e invalidação de cache. Falhas de Redis e Neo4j são injetadas nos clientes dos testes; não é necessário desligar os serviços compartilhados.

```powershell
$env:SPACEBOOKS_INTEGRATION = "1"
.\.venv\Scripts\python.exe -m unittest tests.test_system_flow -v
# Regressão completa:
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
Remove-Item Env:SPACEBOOKS_INTEGRATION
```

O teste principal confere pedido/preços históricos e estoque no MongoDB, limpeza/revisão no Redis, `COMPROU` sem duplicação no Neo4j e atualização do cache/recomendações. Consulte o registro da etapa 9 em [modelagem e validações](docs/data-model.md#integração-da-navegação-e-validação-do-fluxo-completo).

## Identificação de clientes e sessões

Com MongoDB e Redis iniciados e a carga inicial concluída, abra `http://localhost:8501`:

1. Marque **Identificação demonstrativa**.
2. Informe um nome ou ID e clique em **Buscar clientes**. Uma busca vazia mostra os primeiros 50 clientes; refine a busca para localizar os demais.
3. Selecione o cliente cadastrado e clique em **Entrar na demonstração**.
4. Use **Trocar cliente** para encerrar a sessão anterior e escolher outro, ou **Sair** para encerrar a identificação.

É uma demonstração acadêmica sem senha: selecionar um cadastro não comprova a identidade de uma pessoa. Cada sessão de navegador recebe um token aleatório de 256 bits, guardado apenas no estado privado do Streamlit. No Redis, `session:{sha256_do_token}` contém JSON com cliente e datas UTC, com validade fixa de 8 horas, sem renovação ao consultar. O token não aparece na URL ou na interface. Fechar/recarregar a página pode perder o estado do Streamlit; a sessão Redis restante expira normalmente.

Redis é obrigatório para identificar clientes, mas continua opcional para navegar no catálogo público. Falhas não autorizam acesso usando um ID local. `REDIS_SESSION_TIMEOUT_SECONDS` configura o timeout (padrão 1 s, maior que zero e até 5 s), independentemente do cache; `REDIS_URL` tem prioridade sobre senha/porta. A validade de 8 horas é fixa. Reinicie o processo para aplicar configurações novas.

Sair ou trocar de cliente limpa todo o estado local daquele navegador, incluindo rascunhos de quantidade/avaliação, opções de recomendações e dados de pedidos, sem apagar carrinhos persistidos. Logout revoga apenas o token atual; outras sessões continuam válidas. Se o Redis falhar ao sair, a tela limpa a identificação local e informa que a revogação remota não foi confirmada; a chave remanescente expira em até 8 horas.

`RedisSessionService` (`src/services/sessions.py`) implementa busca limitada de clientes, criação, resolução e logout. `current_customer()` em `src/session_ui.py` retorna o `Customer` validado para outras telas, ou `None` para visitante. Trate `ServiceError` nas telas protegidas. Os serviços de carrinho, checkout e avaliações/recomendações recebem o token (`TOKEN_KEY` no estado Streamlit) e chamam `SessionService.resolve()` em cada operação; um ID ou DTO previamente exibido não substitui essa validação. Os clientes de conexão são compartilhados, as identidades não.

Para verificar duas sessões isoladas, expiração real, troca e logout com os bancos locais:

```powershell
$env:SPACEBOOKS_INTEGRATION = "1"
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_sessions*.py" -v
Remove-Item Env:SPACEBOOKS_INTEGRATION
```

Os testes usam coleções e chaves temporárias, sem alterar os clientes cadastrados. Incluem dois navegadores simulados pelo AppTest, com MongoDB e Redis reais, e falhas simuladas das dependências.

## Carrinho no Redis

Depois de identificar um cliente, clique em **Adicionar ao carrinho** em um livro. O painel **Meu carrinho** abre automaticamente; também pode ser aberto pela opção com esse nome. Altere a quantidade e clique em **Salvar quantidade**, ou use **Remover**. **Atualizar carrinho** relê os preços diretamente do MongoDB, mesmo quando o catálogo está em cache. Use **Revisar compra** para iniciar o checkout descrito a seguir.

Cada cliente tem um Hash `cart:{customer_id}` contendo apenas ISBN → quantidade, além de `cart:meta:{customer_id}` com a revisão UUID. Clientes diferentes mantêm carrinhos independentes; sessões do mesmo cliente compartilham o carrinho. Sair ou trocar de cliente preserva os itens no Redis e descarta os rascunhos locais de quantidade. A sessão de identificação dura até 8 horas; o carrinho tem TTL próprio de 24 horas após a última alteração efetiva. Leituras e operações sem mudança não renovam esse prazo. Excluir o último item remove ambas as chaves.

`RedisCartService` (`src/services/cart.py`) valida a sessão em cada operação. Adicionar incrementa a quantidade; salvar define um valor absoluto e exige item existente. Quantidades precisam ser inteiros de 1 até 2.147.483.647 e respeitar o estoque atual. Zero não remove um item. Atualizações usam `WATCH`/`MULTI`/`EXEC` para alterar itens, revisão e TTL juntos, com até cinco tentativas em caso de concorrência. Preços, subtotais e total são calculados em centavos a partir do MongoDB, sem cache e sem reservar ou baixar estoque.

Se o estoque cair depois da inclusão, o painel avisa sem reduzir quantidades silenciosamente. Se um livro for excluído do MongoDB, o erro informa o ISBN e o formulário **Remover por ISBN** permite excluí-lo do carrinho. Redis indisponível não gera carrinho local alternativo. Uma falha de rede após escrita pode deixar a alteração concluída no servidor: atualize o carrinho antes de repetir uma adição. A configuração usa a mesma URL e o timeout `REDIS_SESSION_TIMEOUT_SECONDS` das sessões, independentemente do cache.

Para testar serviço, TTL real, concorrência e dois clientes na interface:

```powershell
$env:SPACEBOOKS_INTEGRATION = "1"
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_cart*.py" -v
Remove-Item Env:SPACEBOOKS_INTEGRATION
```

Os testes usam clientes, sessões, coleções MongoDB e chaves Redis temporários e removem esses dados ao terminar.

## Avaliações e recomendações no Neo4j

Depois de identificar um cliente, abra **Ver detalhes** em um livro e marque **Minha avaliação**. Escolha uma nota inteira de 1 a 5 e clique em **Salvar avaliação**. A mesma opção permite alterar a nota depois; a tela mostra a nota atual e a data UTC da última gravação. Não é necessário ter comprado o livro. Cada cliente tem uma única relação `AVALIOU` por livro, atualizada com nota e data. A média importada do CSV continua separada das avaliações individuais.

Marque **Recomendações para você** para abrir o painel. Ele procura outros clientes que compraram ou avaliaram positivamente (4 ou 5) algum livro em comum com você. Sugere os livros comprados ou bem avaliados por esses clientes, contando cada cliente semelhante uma única vez por candidato. Primeiro aparecem as sugestões por similaridade; se faltarem resultados, o sistema completa pelas suas categorias e autores favoritos. Dentro de cada grupo, ordena por pontuação decrescente e ISBN crescente.

Livros já comprados ou avaliados por você, removidos do catálogo ou sem estoque são excluídos. Compras confirmadas no MongoDB também são consideradas, mesmo que a projeção no Neo4j esteja pendente. Preço, estoque e dados dos candidatos vêm diretamente do MongoDB a cada consulta, sem usar o cache comercial do catálogo. **Atualizar recomendações** relê esses dados, e os botões do painel permitem adicionar um livro ao carrinho.

Se a consulta de clientes semelhantes falhar depois de o histórico ser conhecido, o serviço pode usar somente preferências. Se não conseguir conferir o histórico de compras, apresenta erro e não inventa recomendações que poderiam incluir um livro já comprado. O catálogo e as outras telas continuam disponíveis conforme seus próprios bancos. Sessões e notas em edição são isoladas por navegador e descartadas ao trocar de cliente ou sair.

### Perfis fictícios para demonstração

Com a carga inicial executada, carregue os dados identificados em `data/recommendation-demo.json`:

```powershell
.\.venv\Scripts\python.exe -m src.seed_recommendation_demo
# Aplicação em Docker:
docker compose exec -T catalog python -m src.seed_recommendation_demo
```

O comando cria cinco cadastros MongoDB com IDs `DEMO_REC_*`, nomes iniciados por `DEMO` e `demo_dataset="recommendations-v1"`. Compras simuladas no grafo usam `pedido_id` iniciado por `DEMO-REC-`; essas relações e as avaliações recebem o mesmo marcador do conjunto. Não cria pedidos MongoDB nem baixa estoque. Repetir o comando não duplica cadastros ou relações, mas reaplica as avaliações fictícias originais. Esses perfis e sinais fazem parte do conjunto demonstrativo usado pelo algoritmo.

| Cliente para selecionar | Histórico inicial | Resultado esperado, quando disponível |
| --- | --- | --- |
| `DEMO_REC_TECH` | Compra simulada de *Incident Response & Computer Forensics* | *C++ Programmer's Notebook* e *Java* por cliente semelhante |
| `DEMO_REC_FICTION` | Nota 5 para *Gilead* | *Rage of angels* e *Warhost of Vastmark* por cliente semelhante |
| `DEMO_REC_COLD` | Sem compras ou avaliações | Livros de `Computers`/`Fiction`, com preferência adicional por Walter J. Savitch |

Os outros dois cadastros, `DEMO_REC_TECH_PEER` e `DEMO_REC_FICTION_PEER`, representam os leitores semelhantes desses cenários. Busque por `DEMO` na identificação para localizá-los. Os cadastros demonstrativos ficam separados do CSV original; a carga inicial regular preserva esses registros adicionais.

Para executar os testes dos serviços e da interface com dados temporários:

```powershell
$env:SPACEBOOKS_INTEGRATION = "1"
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_recommendations*.py" -v
Remove-Item Env:SPACEBOOKS_INTEGRATION
```

Os testes cobrem perfis sem histórico, compras e avaliações semelhantes, edição e concorrência de notas, empates, preferência por autor, indisponibilidade, exclusões, preços atuais e compras cuja projeção ainda está pendente. Usam banco MongoDB, chaves Redis e IDs Neo4j temporários, removidos ao terminar. As dependências existentes são suficientes.

## Checkout e registro das compras

No painel **Meu carrinho**, clique em **Revisar compra**, confira os itens e o total e clique em **Confirmar compra**. A demonstração registra a compra sem cobrança ou pagamento externo. O número do pedido é o UUID da tentativa. Mudanças de preço ou de revisão do carrinho exigem uma nova revisão explícita. Repetir uma confirmação ou consultar uma tentativa usa o mesmo identificador e não baixa estoque outra vez.

O MongoDB local agora usa um replica set de um nó, `rs0`, necessário para transações. Os volumes existentes são preservados; `mongo-init` configura o conjunto e aguarda o primário. A chave de autenticação entre membros é gerada dentro do volume `mongo_config`, sem entrar no Git. Inicie o ambiente com:

```powershell
docker compose up -d mongodb redis neo4j mongo-init
docker compose --profile app up -d --build catalog
```

No ambiente com bundle de certificados local, mantenha a opção `-f compose.yaml -f compose.build-ca.yaml` no comando de build. A aplicação aguarda a conclusão de `mongo-init`; a preparação/carga inicial continua necessária em bancos novos. Conexões Python locais geradas pelo projeto usam `directConnection=true`, pois o nome anunciado pelo replica set é interno ao Docker. Quem configurou `MONGO_URI` manualmente deve incluir essa opção quando conectar pelo endereço publicado. O serviço de checkout exige MongoDB com suporte a transações; não há alternativa com escritas independentes em standalone.

`MongoCheckoutService` (`src/services/checkout.py`) registra a revisão em `checkout_attempts`, com preços aprovados e TTL de dois dias para esse rascunho. O pedido confirmado não expira. Na confirmação, relê o carrinho, valida o cliente e consulta os livros dentro de uma transação MongoDB. Baixas condicionais de estoque, pedido com preços históricos e marcadores de integração são confirmados juntos, com write concern `majority`. O `_id` do pedido impede repetir uma tentativa; o índice único de cliente + revisão impede comprar novamente o mesmo carrinho usando outro UUID.

Depois da confirmação, a aplicação registra `COMPROU` no Neo4j, limpa o carrinho somente se a revisão corresponder à comprada e invalida o cache. Uma revisão nova é preservada e a tela informa isso. O Neo4j usa `MERGE` por cliente, produto e pedido, com trava de escrita no cliente para serializar projeções concorrentes. Quantidades são atribuídas, sem acumular novamente durante retomadas.

Se Redis ou Neo4j falharem depois da transação, a compra continua confirmada e as pendências ficam no MongoDB. Use **Consultar esta tentativa** ou **Consultar pedido** para recuperar a confirmação do próprio cliente e tentar suas integrações. Uma resposta perdida exige consultar ou repetir o mesmo identificador; não crie outra compra para compensar uma falha de comunicação. Um operador também pode regularizar pendências de qualquer cliente pelo comando interno:

```powershell
.\.venv\Scripts\python.exe -m src.retry_checkout --limit 100
# Aplicação em Docker:
docker compose exec -T catalog python -m src.retry_checkout --limit 100
```

Esse comando pode ser repetido e não requer sessões de clientes. Não há trabalhador agendado nesta etapa; as retomadas ocorrem por consulta do pedido, repetição da mesma tentativa ou execução desse comando. Pedidos e marcadores persistem no MongoDB mesmo após a sessão expirar.

Testes de checkout com os bancos reais:

```powershell
$env:SPACEBOOKS_INTEGRATION = "1"
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_checkout*.py" -v
Remove-Item Env:SPACEBOOKS_INTEGRATION
```

Os testes usam um banco MongoDB temporário, chaves Redis e IDs Neo4j exclusivos, removidos ao terminar. Incluem concorrência, rollback de estoque, preços históricos, alteração de preço, resposta perdida e recuperação após falhas das integrações.

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

Com a interface em Docker, o equivalente é `docker compose exec -T catalog python -m src.invalidate_catalog_cache`. Uma falha Redis mantém a intenção no MongoDB, na coleção `catalog_cache_state`. A retomada acontece em uma ausência de cache, após recuperação percebida pelo mesmo serviço ou pelo comando acima. Uma instância que não percebeu a falha pode servir entradas antigas até o TTL. Novos serviços que alterarem preço, estoque ou metadados devem usar a invalidação comum; o checkout registra a intenção na própria transação de estoque/pedido e tenta concluí-la depois da confirmação.

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
docker compose up -d mongodb redis neo4j mongo-init
docker compose --profile tools run --rm --build tools python -m src.bootstrap --prepare --check-idempotence
```

O primeiro comando gera `.env` com senhas aleatórias e preserva o arquivo caso ele já exista. Não publique esse arquivo. `.env.example` documenta as variáveis; valores do ambiente têm prioridade sobre `.env` no Python. Em caso de conflito de portas, ajuste `MONGO_PORT`, `REDIS_PORT`, `NEO4J_HTTP_PORT` e `NEO4J_BOLT_PORT` antes de iniciar os serviços.

`DB_TIMEOUT_SECONDS` limita a espera por conexões e operações de rede (10 segundos por padrão). `DB_QUERY_TIMEOUT_SECONDS` define o limite de execução das consultas e a janela de repetição de transações do Neo4j (60 segundos), permitindo a carga inicial com índices ainda frios. Cada limite pode ser configurado até 120 segundos.

Os três bancos têm volumes persistentes e portas publicadas apenas em `127.0.0.1`. O serviço `tools` executa os comandos Python dentro do Compose e monta `data/prepared/` para salvar os arquivos gerados no computador. `requirements-db.txt` contém somente os clientes dos bancos; a interface usa `requirements-app.txt`, e a exploração opcional usa `requirements-notebook.txt`.

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

O teste de saúde Neo4j autentica com `cypher-shell` e tem prazo de 30 segundos: a inicialização da JVM desse comando pode ultrapassar 10 segundos sob carga. Se aparecer `unhealthy`, confira `docker compose logs --tail 100 neo4j` e execute `src.check_connections`; não interprete apenas o status como prova de perda dos dados.

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
| `src/catalogo.py` | Entrada Streamlit, identidade visual e roteamento das telas |
| `src/catalog_ui.py` | Catálogo com busca, filtros e preço/estoque atuais |
| `src/navigation_ui.py` e `src/ui_feedback.py` | Navegação, mensagens e descarte de sessão |
| `src/services/sessions.py` e `src/services/cart.py` | Sessões e carrinhos Redis |
| `src/services/checkout.py` e `src/retry_checkout.py` | Checkout transacional e recuperação de pendências |
| `src/services/recommendations.py` | Avaliações e recomendações Neo4j |
| `src/check_delivery.py` | Auditoria local dos arquivos publicáveis e do histórico |
| `src/database/` | Configuração, conexões, índices, carga e verificação |
| `src/bootstrap.py` | Inicialização e validação dos bancos |
| `src/check_connections.py` | Diagnóstico das conexões e TTL do Redis |
| `src/notebooks/books-exploration.ipynb` | Exploração e limpeza original |
| `tests/` | Testes unitários, integração dos bancos e interface AppTest |
| `docs/data-model.md` | Contratos dos dados e dos bancos |

Consulte [a modelagem e os contratos compartilhados](docs/data-model.md) para os campos, identificadores, chaves Redis, TTLs, sessões, checkout, recomendações e responsabilidades de cada banco. As interfaces Python em `src/domain/contracts.py` possuem implementações para catálogo, sessões, carrinho, checkout e avaliações/recomendações.
