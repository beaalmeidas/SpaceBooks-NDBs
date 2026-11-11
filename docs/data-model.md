# Modelagem dos dados do SpaceBooks

Os modelos em `src/domain/models.py` são entidades imutáveis: alterações criam novas instâncias. Suas projeções retornam dicionários. As conexões e a carga inicial estão em `src/database/`; o catálogo consulta MongoDB por `src/services/catalog.py`. Ainda não há serviços de checkout ou sincronização de compras entre bancos.

## Identificadores e valores

O ISBN-13 é uma string e identifica o livro nos três bancos. O `user_id` do CSV identifica o cliente. IDs de pedidos serão fornecidos pelo serviço de checkout, preferencialmente como UUIDs.

Valores monetários são inteiros em centavos, em BRL. Quantidades são inteiros positivos; estoque pode ser zero. Avaliações individuais usam notas inteiras de 1 a 5. A média agregada do catálogo pode ter casas decimais e não identifica avaliações de clientes.

Cadastros importados mantêm a precisão de dia (`YYYY-MM-DD`). Pedidos e avaliações exigem horários com fuso e são exportados em UTC, no formato ISO 8601. Os futuros adaptadores MongoDB poderão convertê-los para BSON Date.

## Livros e clientes no MongoDB

`Book.to_document()` produz documentos de `books` com `_id` igual ao ISBN, título, autores e categorias em listas, preço, estoque, moeda e metadados bibliográficos. ISBN-10 permanece string para preservar zeros à esquerda. Subtítulos vazios tornam-se `null`. Campos numéricos como `247.0` páginas são convertidos para inteiros sem arredondamento silencioso.

Na importação, páginas iguais a zero tornam-se `null` (quantidade desconhecida), preservando o livro. Valores negativos ou fracionários são rejeitados.

`Customer.to_document()` produz documentos de `customers`, com `_id`, nome, e-mail, categorias e autores favoritos e data de criação. Preferências são listas, não strings contendo JSON. O modelo não implementa autenticação. Quando o login for implementado, senhas deverão ter hashes e tokens temporários ficarão no Redis.

Índices criados pela carga: `_id` único em livros e clientes (nativo do MongoDB); e-mail único normalizado; índice textual de título e autores; índices individuais de autores e categorias. A interface poderá ajustar os índices conforme suas consultas.

## Pedidos e checkout

`Order.from_cart()` recebe um carrinho e o catálogo atual, valida a existência dos livros e o estoque informado, e copia título e preço para cada `OrderItem`. O total é calculado pela soma de quantidade × preço unitário. Não é aceito um total fornecido pelo cliente. Pedidos vazios ou com livros repetidos são rejeitados.

`Order.to_document()` produz `_id`, cliente, itens, total, moeda, data e status para `orders`. Os status previstos são `confirmed` e `cancelled`. Alterar o catálogo não modifica o histórico já criado. O construtor de `Order` permite reconstruir pedidos históricos sem consultar o preço atual.

O método não reserva estoque, não limpa o carrinho e não confirma pagamento. O futuro checkout deve validar o cliente e efetuar a baixa condicional do estoque junto à persistência do pedido. Sincronização com Neo4j e limpeza do Redis precisam de tratamento de falhas e repetição idempotente.

Índices criados pela carga: `_id` único (nativo do MongoDB) e índice composto de `customer_id` e `created_at` para histórico.

## Carrinho no Redis

`Cart` representa uma chave `cart:{customer_id}`, com Hash de ISBN → quantidade. `to_redis_hash()` retorna o mapeamento para `HSET`. O TTL padrão é 86.400 segundos (24 horas); o futuro adaptador deve executar `EXPIRE` ao salvar ou atualizar o carrinho. O modelo valida o TTL, mas não inicia temporizadores.

O carrinho não armazena preços; o checkout utiliza o catálogo atual. Um carrinho vazio é válido para navegação, mas não gera pedido. A aplicação deve remover a chave Redis quando o último item for excluído.

Os contratos de sessões e cache estão definidos nas seções seguintes. O cache do catálogo está implementado; sessões e carrinhos persistidos ainda não.

## Grafo no Neo4j

| Nó | Identificador | Propriedades iniciais |
| --- | --- | --- |
| `Cliente` | `id` = ID do cliente | `nome` |
| `Produto` | `id` = ISBN-13 | `titulo` |
| `Categoria` | `id` = nome da categoria | `nome` |

| Relacionamento | Origem → destino | Propriedades |
| --- | --- | --- |
| `PERTENCE_A` | Produto → Categoria | Nenhuma |
| `PREFERE` | Cliente → Categoria | Nenhuma |
| `COMPROU` | Cliente → Produto | `pedido_id`, `quantidade`, `unit_price_cents`, `created_at` |
| `AVALIOU` | Cliente → Produto | `nota`, `created_at` |

A preparação exporta apenas os nós, `PERTENCE_A` e `PREFERE` derivados dos CSVs. Não inventa compras ou avaliações. Autores favoritos permanecem no documento do cliente; nós de autores não fazem parte do grafo inicial.

`Order.to_graph_records()` projeta compras confirmadas, uma relação por pedido e produto. A carga futura deverá usar cliente, produto e `pedido_id` na identidade da relação para evitar duplicação em tentativas repetidas. Pedidos cancelados retornam lista vazia; isso não remove compras previamente persistidas. O serviço de cancelamento deverá realizar essa atualização.

`Review.to_graph_record()` projeta uma avaliação. A regra proposta é uma avaliação atual por par cliente/livro: a futura escrita deve atualizar a relação existente. A existência dos clientes e livros precisa ser validada pelo serviço.

O carregador cria constraints únicas para `id` em cada tipo de nó e usa Cypher parametrizado. Apenas os tipos de nós e relacionamentos iniciais definidos acima são aceitos na carga; os identificadores dos produtos e clientes devem coincidir com os documentos MongoDB. O JSONL do grafo é um formato interno, não um dump nativo do Neo4j.

## Preparação e limites

`python -m src.prepare_data` lê os CSVs sem alterá-los e gera documentos JSONL e manifesto em `data/prepared/`. Preços de R$ 19,90 a R$ 149,90 e estoques de 5 a 50 unidades são fictícios, calculados pelo SHA-256 do ISBN. A regra e os hashes das entradas ficam no manifesto. Identificadores duplicados ou preferências fora do catálogo interrompem a preparação antes de substituir os arquivos existentes.

`python -m src.bootstrap --prepare --check-idempotence` prepara e carrega os dados, cria índices/constraints, testa as conexões e o TTL do Redis e repete a carga para verificar contagens estáveis. Preço, estoque e moeda são definidos apenas na inserção; os demais metadados bibliográficos podem ser atualizados. Clientes existentes não são sobrescritos. O e-mail de clientes novos é normalizado com `strip().lower()` e possui índice único. Pedidos não são importados pela carga inicial.

A verificação confere todos os IDs preparados no MongoDB e Neo4j, assim como cada relação esperada no grafo. Também inspeciona as coleções, as chaves e opções dos índices MongoDB (incluindo unicidade do e-mail e campos do índice textual) e as constraints únicas de `id` para os três tipos de nó Neo4j. `--verify-only` faz essa inspeção sem recriar índices ou carregar registros; o diagnóstico Redis continua usando sua chave temporária com expiração.

Com `--check-idempotence`, o script compara contagens e todos os valores existentes de preço, estoque e moeda antes/depois da carga e de sua repetição. Registros adicionais da aplicação são permitidos. A carga não remove dados ausentes da nova entrada e não executa uma transação distribuída. Uma carga interrompida pode ser repetida. Mudanças futuras de preferências deverão ser tratadas pelo serviço da aplicação.

Ainda não há identificação de clientes por sessão, serviços de carrinho/checkout ou recomendação Cypher. `src/catalogo.py` usa cache Redis e consultas MongoDB pelos serviços de catálogo, conforme os registros de mudanças abaixo. As credenciais existentes são para conexão técnica com os bancos.

## Contratos compartilhados dos serviços

Esta é a referência para implementar os módulos. `src/domain/contracts.py` declara os DTOs (dados de entrada e saída), erros e interfaces `Protocol` correspondentes. Os protocolos não implementam serviços, conexões ou validação em tempo de execução. As regras abaixo devem ser aplicadas pelas futuras implementações. O uso de dataclasses não dispensa validar entradas vindas da interface ou dos bancos.

### Identificadores e representação

| Conceito | Contrato |
| --- | --- |
| Livro | `Book.isbn`, documento `books._id`, campo `book_id` e `Produto.id` representam a mesma string ISBN-13 |
| Cliente | `Customer.customer_id`, documento `customers._id`, `user_id` do CSV e `Cliente.id` representam o mesmo ID |
| Categoria | String original, sem conversão para minúsculas; mesma identidade em MongoDB e Neo4j |
| Pedido e tentativa | UUID criado pela interface uma vez por tentativa; `request_id` é também `Order.order_id`, `orders._id` e `COMPROU.pedido_id` |
| Dinheiro | Inteiro em centavos, moeda `BRL`; não aceitar preço ou total calculado pelo navegador como autoridade |
| Datas de eventos | `datetime` com fuso no Python; ISO 8601 UTC com `Z` nas projeções atuais; manter esse formato ao persistir esta versão |
| Listas | Tuplas nos DTOs imutáveis; listas nos documentos JSON/MongoDB |

Não substituir as strings ISBN por números e não gerar IDs diferentes para o mesmo registro em cada banco. As diferenças de nomes acima são mapeamentos explícitos, não novas identidades. IDs de pedido já existentes nos testes continuam válidos no modelo; a geração de UUID é obrigação do futuro serviço/interface.

### Catálogo

`CatalogService.search(CatalogQuery) -> CatalogPage` recebe pesquisa, categoria, página, tamanho e ordenação. A pesquisa é uma substring literal por título **ou** autor, sem diferenciar maiúsculas e minúsculas. Não interpretar a entrada como expressão regular. A implementação poderá mudar a estratégia de busca depois, mas deverá tratar essa alteração como mudança de contrato.

Normalizar a pesquisa com `strip().casefold()` e preservar os espaços internos. Categoria `None` significa todas; a interface deve converter a opção visual “Todas” para `None`. Uma categoria informada deve ser não vazia e corresponder ao valor armazenado. Página começa em 1; tamanho padrão 24 e permitido entre 1 e 100. Ordenações: `title_asc`, `price_asc`, `price_desc`, sempre com ISBN crescente como desempate. O título usa a mesma comparação de strings definida pela consulta MongoDB em todas as páginas. Valores inválidos geram `ValidationError`, sem correção silenciosa.

`CatalogPage` contém `items`, `total` de resultados antes da paginação, `page` e `page_size`. Página além do fim retorna itens vazios e o total correto. Nenhum resultado também é uma resposta válida. `get_book(book_id)` retorna `Book` ou lança `NotFoundError`. `list_categories()` retorna categorias distintas em ordem crescente. Preço e estoque vêm do MongoDB ou de cache válido desse documento, nunca de `demo_commerce()` durante a navegação.

### Cache do catálogo

Consultas elegíveis: busca paginada, detalhes de livro e lista de categorias. TTL padrão de 60 segundos, configurável por `CATALOG_CACHE_TTL_SECONDS` entre 1 e 3600 segundos, sem renovação na leitura. Falha do Redis faz a consulta seguir diretamente para o MongoDB; falha do MongoDB sem resultado de cache válido gera `ServiceUnavailableError`. `st.cache_data` não substitui esse contrato e não deve adicionar outra camada de dados comerciais sem a mesma invalidação.

| Chave Redis | Tipo | Conteúdo e validade |
| --- | --- | --- |
| `catalog:v1:generation` | String | UUID da geração atual, sem TTL; se ausente, inicializar um UUID novo de forma atômica |
| `catalog:v1:{generation}:search:{digest}` | String JSON | Página de livros, total, página e tamanho; TTL 60 s |
| `catalog:v1:{generation}:categories` | String JSON | Lista de categorias; TTL 60 s |
| `product:v1:{generation}:{isbn}` | String JSON | Documento de livro; TTL 60 s |

`digest` é SHA-256 do JSON dos campos normalizados `search`, `category`, `page`, `page_size`, `sort`, serializado com chaves ordenadas, `ensure_ascii=False` e separadores `(',', ':')`. Os livros no cache usam o formato de `Book.to_document()`. O adaptador reconstrói `Book` e `CatalogPage` ao ler; nenhum objeto Python serializado com pickle.

`CatalogService.invalidate_cache()` troca a geração por outro UUID. Isso torna as entradas antigas inacessíveis; elas expiram pelo TTL, sem `FLUSHDB`, `KEYS` ou limpeza de dados de outros módulos. A consulta deve capturar a geração antes de ler o MongoDB e gravar nessa mesma geração, evitando republicar resultados antigos após uma invalidação concorrente.

Invalidar depois de compra confirmada, alteração de preço/estoque e alteração de metadados/categorias. Toda rotina que alterar esses dados deve chamar a invalidação ou registrar uma pendência durável quando o Redis falhar. A carga bibliográfica e o botão de atualização já usam essa rotina. Durante uma pendência, uma resposta antiga pode permanecer visível até o TTL; o futuro checkout deverá ignorar cache e revalidar no MongoDB.

### Identificação e sessões

Para a primeira versão acadêmica, a decisão é **identificação demonstrativa por seleção de cliente cadastrado**, sem senha. A interface deve informar que é uma demonstração, pois selecionar um ID não comprova a identidade de uma pessoa. Login com senha é uma extensão futura e não deve ser presumido pelos outros módulos.

`SessionService.create_demo_session(customer_id)` valida o cliente no MongoDB e retorna `Session` com token aleatório de pelo menos 256 bits, cliente e datas UTC. Validade fixa de 8 horas, sem renovação automática. O token fica apenas no estado privado da sessão Streamlit; não deve aparecer na URL, mensagens, logs ou MongoDB.

Persistir `session:{sha256_do_token}` como String JSON com `customer_id`, `created_at` e `expires_at`, com TTL de 28.800 segundos. Não guardar o token original no Redis. `resolve(token)` valida existência/expiração e retorna o cliente; falha de identificação gera `SessionExpiredError`. Cliente removido também invalida a sessão. Falha do Redis gera `ServiceUnavailableError`, não autoriza acesso por um ID enviado pela tela.

`logout(token)` remove apenas essa sessão e limpa o estado privado correspondente na interface. É idempotente para token já inexistente e não apaga o carrinho persistido. Trocar de cliente exige encerrar a sessão anterior e criar outra. Várias sessões do mesmo cliente compartilham o carrinho por decisão desta versão.

### Carrinho

Todos os métodos de `CartService` recebem token e resolvem o cliente por `SessionService`; a tela não escolhe um `customer_id` independente para ler ou alterar carrinhos.

| Chave Redis | Tipo | Conteúdo e validade |
| --- | --- | --- |
| `cart:{customer_id}` | Hash | ISBN → quantidade inteira representada como string; TTL 24 h |
| `cart:meta:{customer_id}` | Hash | `revision` UUID; mesmo TTL do carrinho |

Atualizar itens, revisão e expiração de forma atômica. Cada mutação efetiva gera outra revisão; leitura não renova o TTL. Carrinho vazio não mantém as duas chaves e retorna `CartView(revision=None, items=(), total_cents=0)`. Revisão nova não pode reutilizar contador antigo após expiração; usar UUID evita esse conflito.

`add_item(token, book_id, quantity)` incrementa a quantidade existente. `set_quantity(...)` define a quantidade absoluta, exige item existente e quantidade positiva; zero não significa remoção. `remove_item(...)` remove o item e é idempotente se ele já não existir. Adição/alteração valida livro e quantidade resultante contra o estoque atual. Isso não reserva unidades: o checkout precisa revalidar.

`get_cart(...)` retorna `CartView` com linhas `CartLine(book, quantity, subtotal_cents)` e total calculados a partir dos preços atuais no MongoDB, sem confiar em preços enviados pela interface. Estoque insuficiente pode aparecer na revisão do carrinho; não reduzir a quantidade silenciosamente. Se um livro tiver sido excluído, retornar `NotFoundError` e permitir removê-lo por ISBN sem precisar carregá-lo. Os dados brutos do carrinho não guardam preço nem total.

### Checkout e recuperação

`CheckoutService.checkout(token, request_id, expected_revision)` confirma exclusivamente o carrinho/revisão exibidos na tela. Na primeira chamada, validar sessão, cliente, UUID, revisão, itens e estoque. A interface mantém o mesmo `request_id` durante duplo clique, repetição ou resposta perdida; cria outro somente ao iniciar uma nova tentativa. A mesma tentativa não pode gerar dois pedidos ou duas baixas de estoque.

Antes de conferir novamente o carrinho, procurar um pedido já confirmado para `request_id`. Se pertencer ao mesmo cliente, retornar seu resultado persistido, mesmo que o carrinho já tenha sido limpo. Se pertencer a outro cliente, responder `NotFoundError`. Para tentativa ainda não confirmada, revisão diferente gera `ConflictError` e exige revisão da compra na interface.

O pedido guarda os campos já definidos por `Order.to_document()`. A implementação deverá acrescentar metadados de integração, mantendo o status comercial separado:

```json
{
  "cart_revision": "UUID da revisão confirmada",
  "integration": {
    "graph_status": "pending",
    "cart_status": "pending",
    "cache_status": "pending"
  }
}
```

Esses são campos reservados para o checkout, ainda não adicionados ao modelo nem à persistência. `CheckoutResult` retorna o pedido e os três estados `pending`/`done`. Pedido confirmado com integração pendente continua confirmado; a interface deve informar a pendência e apresentar o mesmo número de pedido, sem solicitar outra compra.

Baixa de estoque, pedido e pendências devem ser persistidos de forma consistente no MongoDB. A decisão para a implementação é usar transação MongoDB, com baixa condicional de cada estoque e `_id` único do pedido. **Antes de implementar essa operação, o ambiente local deverá ser configurado como replica set**; o Compose atual é standalone. Não considerar várias escritas independentes como transação. Esta etapa de contratos não altera a infraestrutura.

Depois da confirmação MongoDB, registrar `COMPROU`, limpar o carrinho confirmado e invalidar cache, marcando cada etapa como concluída somente após sucesso. Comparar e limpar carrinho/revisão atomicamente. Se o cliente tiver modificado o carrinho depois da confirmação, preservar o carrinho atual, marcar a limpeza como resolvida e informar que ele não foi limpo por ter alterações novas. Não remover indiscriminadamente itens de uma revisão diferente.

`retry_pending(limit=100)` é operação interna, sem botão público ou token de cliente; tenta concluir integrações de pedidos confirmados e retorna a quantidade de pedidos totalmente regularizados nessa execução. Só executar com configuração de serviço. Todas as operações precisam ser idempotentes, inclusive a atualização dos estados após uma queda. Pendências ficam no MongoDB; não dependem exclusivamente do Redis. `get_order(token, order_id)` permite recuperar confirmação e pendências apenas do próprio cliente.

Cancelamento e pagamento externo não integram o fluxo inicial. `cancelled` permanece como status aceito pelo modelo, mas nenhum serviço de cancelamento é prometido nesta etapa.

### Recomendações e avaliações

`RecommendationService.recommend(token, limit=10)` resolve o cliente e retorna até 50 recomendações, validando limite entre 1 e 50. Cada `Recommendation` contém `book`, pontuação finita não negativa e motivo `similar_customers` ou `preferences`. Ordenar por pontuação decrescente e ISBN crescente no desempate; não retornar livros duplicados, já comprados, excluídos ou sem estoque.

Usar histórico de compras e avaliações positivas (notas 4 ou 5) para localizar clientes semelhantes no Neo4j. Priorizar livros por quantidade de clientes semelhantes distintos que os compraram ou avaliaram positivamente, contando cada cliente uma vez por candidato. Essa contagem é a pontuação de similaridade. Se não houver candidatos suficientes, completar por categorias/autores favoritos: pontuar por número de categorias mais número de autores favoritos distintos que coincidam com o livro. Não incluir candidatos com pontuação zero. Preferências de autores continuam disponíveis no MongoDB, sem exigir novos nós no grafo.

Consultar MongoDB para obter os dados comerciais atuais dos candidatos. Nenhuma recomendação é um resultado válido. Neo4j indisponível pode usar a alternativa por preferências, mas deve retornar `ServiceUnavailableError` se não for possível determinar o histórico necessário para excluir livros comprados; não fingir que houve personalização por similaridade.

`submit_review(token, book_id, rating)` valida sessão, livro e nota inteira de 1 a 5; retorna `Review`. Uma avaliação atual por cliente/livro: nova submissão atualiza nota e data. Não exigir compra prévia nesta versão. Avaliações individuais não sobrescrevem a média agregada importada do catálogo.

No grafo, preservar as propriedades existentes. Identidade de `COMPROU`: cliente + produto + `pedido_id`; identidade de `AVALIOU`: cliente + produto. Repetir o registro de compra usa a quantidade original do pedido, sem incrementar novamente. Não criar novas grafias como `COMPROU_LIVRO` ou `AVALIACAO`.

### Erros e fronteiras entre módulos

| Erro em `contracts.py` | Uso |
| --- | --- |
| `ValidationError` | Entrada inválida ou carrinho vazio na confirmação |
| `NotFoundError` | Livro/cliente/pedido inexistente ou pedido inacessível |
| `SessionExpiredError` | Sessão ausente, inválida, expirada ou revogada |
| `StockUnavailableError` | Quantidade solicitada indisponível |
| `ConflictError` | Revisão do carrinho incompatível com a tentativa |
| `ServiceUnavailableError` | Banco necessário indisponível, sem alternativa válida |

Todos derivam de `ServiceError`. Os adaptadores traduzem exceções dos drivers e o `DatabaseError` existente para erros do serviço. A interface trata esses erros e mostra mensagens sem credenciais. Serviços não chamam Streamlit, não retornam cursores/drivers/DataFrames e não importam a tela. Os DTOs retornados usam `Book`, `Customer`, `Order` e `Review` existentes, com as projeções definidas neste documento.

### Critério de conclusão dos contratos

Cada implementação deve respeitar as assinaturas de `src/domain/contracts.py`, os nomes/formatos aqui definidos e testar suas regras de autorização, expiração, invalidação e repetição. Alterar assinatura, chave, identidade ou semântica exige atualizar este documento e todos os consumidores afetados no mesmo trabalho. O catálogo MongoDB já implementa a interface; os demais serviços continuam como contratos.

## Integração do catálogo com MongoDB

Mudança implementada em 11 de novembro de 2026. A tela manteve sua identidade visual e deixou de ler `books-processed.csv`, filtrar DataFrames e recalcular valores com `demo_commerce()`. O CSV continua sendo uma entrada da preparação/carga; não é uma alternativa automática quando MongoDB estiver indisponível.

`MongoCatalogService` em `src/services/catalog.py` recebe uma coleção MongoDB e devolve `Book`, `CatalogPage` e tuplas de categorias. `search()` normaliza e valida `CatalogQuery`, combina pesquisa por título/autor e categoria, conta os resultados e usa `sort`, `skip` e `limit` no servidor. O cursor materializa no máximo a página solicitada. A ordenação é por título crescente ou preço crescente/decrescente, com `_id` (ISBN) crescente no desempate. Consultas têm limite de tempo. A busca usa substring literal com caracteres de regex escapados, sem interpretar operadores enviados pelo usuário. O índice textual existente não é utilizado para essa semântica de substring.

`get_book()` consulta por ISBN; `list_categories()` consulta os valores distintos. As projeções incluem apenas os campos de `Book`. Documentos inválidos geram erro de serviço, em vez de exibir preços calculados ou estoque inventado. Erros de configuração, conexão e consulta são apresentados sem a mensagem original do driver e sem credenciais. Nenhum resultado é uma resposta normal; a tela exibe uma orientação e desabilita a próxima página.

Na implementação original da etapa 3, `MongoSettings` separou a configuração MongoDB das credenciais dos demais bancos, a conexão passou a ser compartilhada com `st.cache_resource` e os resultados eram relidos a cada execução. A etapa 4, descrita a seguir, acrescenta uma camada Redis. `MongoCatalogService` continua sendo o backend sem cache, para consultas diretas e futuras revalidações de checkout.

A interface inclui ordenação e o botão **Atualizar catálogo**. Mudar pesquisa/categoria/ordenação reinicia a página; se exclusões reduzirem o total, a página é ajustada e consultada novamente. Contagem e leitura da página são operações separadas, sem promessa de snapshot transacional durante alterações concorrentes.

`requirements-app.txt` reúne dependências da interface e referencia `requirements-db.txt`, preservando o arquivo de dependências de desenvolvimento existente. O Dockerfile aceita a escolha das dependências; o perfil Compose `app` acrescenta o serviço `catalog`, disponível em `localhost:8501` por padrão. `compose.build-ca.yaml` também atende ao build da interface quando for necessário usar o bundle de CAs confiáveis local.

Os testes do catálogo cobrem entradas inválidas, busca literal, tratamento seguro de falhas, consultas reais por título/autor/categoria, desempate e paginação. Os testes da tela usam [Streamlit AppTest](https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest), com uma coleção MongoDB temporária própria, para comprovar que alterações de preço e estoque aparecem após atualizar, que a navegação funciona e que a página se ajusta quando a coleção diminui. A coleção temporária é removida ao terminar, sem modificar o catálogo carregado.

Para conferir manualmente o critério de conclusão: abrir um livro no MongoDB Compass, alterar seu `price_cents` ou `stock`, salvar e clicar em **Atualizar catálogo** na tela. O cartão correspondente deve mostrar os valores persistidos; pesquisar seu título facilita localizá-lo.

Validação desta mudança: 33 testes passaram com `SPACEBOOKS_INTEGRATION=1`, incluindo os testes reais de serviço e tela. A instalação local de `requirements-app.txt` também passou em `pip check`.

## Cache Redis do catálogo

`CachedCatalogService` implementa o mesmo contrato do catálogo e envolve `MongoCatalogService`. Consultas válidas procuram primeiro a geração e o JSON no Redis. Um acerto é reconstruído em `Book`, `CatalogPage` ou tupla de categorias, sem executar a consulta MongoDB correspondente. Ausências, expiração, JSON inválido ou Redis indisponível seguem para o backend. O resultado é escrito com expiração somente na criação/substituição da entrada. Nenhum resultado antigo é republicado na nova geração se a invalidação ocorrer durante a leitura MongoDB.

`RedisCatalogCache` usa os nomes de chaves da tabela anterior. A geração é inicializada com `SET NX`, não expira e é sempre um UUID novo quando invalidada. Entradas antigas ficam inacessíveis e expiram normalmente. Não há remoção global de chaves. Os resultados usam JSON, sem pickle. O cliente do cache usa timeout padrão de 0,25 segundo e nenhuma repetição automática, preservando a navegação pelo MongoDB durante indisponibilidade Redis. A configuração não exige credenciais Neo4j. O catálogo mantém clientes compartilhados, mas não usa `st.cache_data` para duplicar resultados comerciais.

`CatalogInvalidator` centraliza o procedimento para carga, atualização manual e futuros escritores. Na coleção MongoDB `catalog_cache_state`, o documento `_id: "catalog"` contém `revision` (UUID) e `pending` (booleano). A marcação é persistida antes de tentar trocar a geração Redis. A conclusão usa filtro pela mesma revisão, evitando apagar a pendência de outra alteração concorrente. Cada tentativa de troca de geração cria um UUID novo, inclusive durante retomadas.

A carga marca intenção antes de escrever e a renova no bloco `finally`, após a última escrita, antes de tentar invalidar. Assim, uma retomada por um leitor durante a carga não consome sua invalidação final. Falhas parciais também acionam esse bloco. Se não for possível registrar a intenção no MongoDB, a carga falha explicitamente. A rotina não transforma a carga em transação distribuída nem oferece snapshot entre os três bancos.

Uma falha Redis deixa a intenção pendente. O serviço tenta retomá-la em ausências de cache e após perceber recuperação da conexão. `python -m src.invalidate_catalog_cache --retry-only` permite uma tentativa explícita. Acertos de cache não consultam o MongoDB para sondar pendências; por isso, outro processo que não percebeu a falha pode servir a entrada antiga até o TTL. Não há trabalhador em segundo plano nesta etapa. Edições diretas por Compass não emitem eventos para o aplicativo: usar o botão **Atualizar catálogo**, o comando de invalidação ou aguardar a expiração.

No Streamlit, o botão de atualização invalida antes de carregar categorias e resultados. O Compose transmite a URL Redis e as opções de TTL/timeout ao catálogo, mantendo Redis como dependência opcional de execução. Os testes de interface agora usam cache Redis real, com namespace próprio por teste, e comprovam atualização de preços/estoque e ajuste de página após invalidar.

Testes unitários e de integração cobrem chaves por todos os parâmetros, consultas sem cache, acertos, TTL sem renovação, expiração real, invalidação de buscas/detalhes/categorias, falhas de leitura/escrita Redis, JSON/metadados inválidos, retomada de pendência e invalidações concorrentes. Coleções e chaves de teste são isoladas e removidas ao terminar. As dependências já existentes em `requirements-db.txt` são suficientes para esta etapa.

Validação final da etapa 4: 50 testes passaram com `SPACEBOOKS_INTEGRATION=1`, incluindo os testes da interface com Redis real.
