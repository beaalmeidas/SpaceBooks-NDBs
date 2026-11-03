# Modelagem dos dados do SpaceBooks

Os modelos em `src/domain/models.py` definem contratos antes da implementação dos bancos. São entidades imutáveis: alterações criam novas instâncias. As projeções retornam dicionários; não fazem persistência nem garantem integridade entre bancos.

## Identificadores e valores

O ISBN-13 é uma string e identifica o livro nos três bancos. O `user_id` do CSV identifica o cliente. IDs de pedidos serão fornecidos pelo serviço de checkout, preferencialmente como UUIDs.

Valores monetários são inteiros em centavos, em BRL. Quantidades são inteiros positivos; estoque pode ser zero. Avaliações individuais usam notas inteiras de 1 a 5. A média agregada do catálogo pode ter casas decimais e não identifica avaliações de clientes.

Cadastros importados mantêm a precisão de dia (`YYYY-MM-DD`). Pedidos e avaliações exigem horários com fuso e são exportados em UTC, no formato ISO 8601. Os futuros adaptadores MongoDB poderão convertê-los para BSON Date.

## Livros e clientes no MongoDB

`Book.to_document()` produz documentos de `books` com `_id` igual ao ISBN, título, autores e categorias em listas, preço, estoque, moeda e metadados bibliográficos. ISBN-10 permanece string para preservar zeros à esquerda. Subtítulos vazios tornam-se `null`. Campos numéricos como `247.0` páginas são convertidos para inteiros sem arredondamento silencioso.

Na importação, páginas iguais a zero tornam-se `null` (quantidade desconhecida), preservando o livro. Valores negativos ou fracionários são rejeitados.

`Customer.to_document()` produz documentos de `customers`, com `_id`, nome, e-mail, categorias e autores favoritos e data de criação. Preferências são listas, não strings contendo JSON. O modelo não implementa autenticação. Quando o login for implementado, senhas deverão ter hashes e tokens temporários ficarão no Redis.

Índices planejados: `_id` único em livros e clientes; índice único de e-mail após definição de sua normalização; índices de busca por título, autores e categorias conforme as consultas da interface.

## Pedidos e checkout

`Order.from_cart()` recebe um carrinho e o catálogo atual, valida a existência dos livros e o estoque informado, e copia título e preço para cada `OrderItem`. O total é calculado pela soma de quantidade × preço unitário. Não é aceito um total fornecido pelo cliente. Pedidos vazios ou com livros repetidos são rejeitados.

`Order.to_document()` produz `_id`, cliente, itens, total, moeda, data e status para `orders`. Os status previstos são `confirmed` e `cancelled`. Alterar o catálogo não modifica o histórico já criado. O construtor de `Order` permite reconstruir pedidos históricos sem consultar o preço atual.

O método não reserva estoque, não limpa o carrinho e não confirma pagamento. O futuro checkout deve validar o cliente e efetuar a baixa condicional do estoque junto à persistência do pedido. Sincronização com Neo4j e limpeza do Redis precisam de tratamento de falhas e repetição idempotente.

Índices planejados: `_id` único e índice composto de `customer_id` e `created_at` para histórico.

## Carrinho no Redis

`Cart` representa uma chave `cart:{customer_id}`, com Hash de ISBN → quantidade. `to_redis_hash()` retorna o mapeamento para `HSET`. O TTL padrão é 86.400 segundos (24 horas); o futuro adaptador deve executar `EXPIRE` ao salvar ou atualizar o carrinho. O modelo valida o TTL, mas não inicia temporizadores.

O carrinho não armazena preços; o checkout utiliza o catálogo atual. Um carrinho vazio é válido para navegação, mas não gera pedido. A aplicação deve remover a chave Redis quando o último item for excluído.

Sessões (`session:{token}`) e cache (`product:{isbn}`) terão TTLs próprios, definidos nos respectivos serviços quando implementados.

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

O carregador futuro deverá criar constraints únicas para `id` em cada tipo de nó e usar Cypher parametrizado. O JSONL do grafo é um formato interno para esse carregador, não um dump nativo do Neo4j.

## Preparação e limites

`python -m src.prepare_data` lê os CSVs sem alterá-los e gera documentos JSONL e manifesto em `data/prepared/`. Preços de R$ 19,90 a R$ 149,90 e estoques de 5 a 50 unidades são fictícios, calculados pelo SHA-256 do ISBN. A regra e os hashes das entradas ficam no manifesto. Identificadores duplicados ou preferências fora do catálogo interrompem a preparação antes de substituir os arquivos existentes.

Não há conexões, índices efetivamente criados, autenticação, telas Streamlit ou recomendação Cypher executável. Esta etapa fornece os contratos e os dados preparados para essas funcionalidades.
