# Roteiro com clientes já cadastrados

Depois da carga inicial, prepare os cenários:

```powershell
docker compose exec -T catalog python -m src.seed_presentation
```

Se a imagem ainda não contiver o comando, reconstrua a aplicação com `docker compose --profile app up -d --build catalog`. Na rede com certificado local, use a opção de build descrita no README.

| Cliente existente | Papel na apresentação |
| --- | --- |
| Lucas Espindola — `U3501` | Computação e ficção: compras simuladas de *Incident Response & Computer Forensics* e *Gilead*, notas positivas para *Gilead* e *Gold*, nota 2 para *Robot Visions* |
| Eduarda Carvalho — `U0503` | Tem computação em comum com Lucas; comprou *C++ Programmer's Notebook* e *Java*; avaliou *Rage of angels* com nota 2 |
| Felipe Pinto — `U0585` | Tem computação e *Gold* em comum com Lucas; avaliou *Java* e *The Robots of Dawn* positivamente |
| Clara Rodrigues — `U0357` | Perfil de ficção: *Gilead*, *Warhost of Vastmark*, *Rage of angels* e *The Caves of Steel* |
| Giovana Macedo — `U0829` | Continua sem compras ou avaliações; recebe sugestões pela preferência já cadastrada por `Computers` e pelos autores Aldous Huxley e Michael F. Roizen |

A carga acrescenta **dez compras simuladas e dezesseis avaliações** quando não há colisões com avaliações existentes. Ela usa os cadastros MongoDB e nós Neo4j existentes. Não altera nomes, preferências, preços, estoque, pedidos ou carrinhos. Os cinco perfis antigos `DEMO_REC_*` continuam disponíveis e também participam normalmente do algoritmo.

As relações novas têm `demo_dataset="presentation-existing-v1"`, `simulated=true` e data UTC. Compras fictícias usam `pedido_id` iniciado por `DEMO-PRESENTATION-`; não correspondem a pedidos MongoDB. As notas de 1 a 5 e as datas usam o mesmo formato consumido pela aplicação. Cadastros e produtos devem existir nos dois bancos antes da carga.

O comando grava as relações em uma transação Neo4j. Repetir não duplica compras e preserva notas/datas já existentes, inclusive avaliações feitas pela interface. O histórico anterior de Lucas é mantido. Se Giovana já tiver comprado ou avaliado algo, a carga recusa o cenário sem histórico e não apaga suas relações. Não há reset automático de demonstração.

## Demonstração na aplicação

1. Abra <http://localhost:8501>, identifique **Lucas Espindola** e acesse **Recomendações**.
2. Mostre as sugestões por clientes semelhantes. *Java* e *C++ Programmer's Notebook* têm sinais positivos dos outros clientes; candidatos já comprados ou avaliados por Lucas ficam excluídos. O motivo é o histórico compartilhado, não apenas a categoria favorita.
3. Abra a avaliação de *Robot Visions*: a nota 2 não é sinal positivo, e o livro já avaliado não aparece como sugestão para Lucas.
4. Troque para **Clara Rodrigues** e compare os resultados com os de Lucas. Perfis mistos podem conectar gêneros; similaridade não restringe sugestões à categoria favorita.
5. Troque para **Giovana Macedo** e mostre a alternativa por preferências sem histórico.
6. Volte para Lucas, adicione uma sugestão ao carrinho e conclua **uma compra real da demonstração**. Mostre o pedido UUID no MongoDB, o carrinho limpo no Redis e a relação `COMPROU` no Neo4j. Atualize recomendações: o livro comprado deve desaparecer.

Os títulos e a ordem das sugestões dependem de estoque, avaliações e compras posteriores. Relações de demonstração preservam o histórico: repetir o comando não desfaz uma compra feita durante o ensaio.

### Exemplos observados após a carga

| Cliente | Sugestões observadas | Explicação |
| --- | --- | --- |
| Lucas Espindola | *Java*, *Rage of angels*, *Warhost of Vastmark*, *C++ Programmer's Notebook*, *The Robots of Dawn* e *The Caves of Steel* | Clientes com compras ou avaliações positivas em comum fornecem os candidatos |
| Eduarda Carvalho | *Gilead*, *Robot Visions* e *The Robots of Dawn*, entre outros | Os sinais positivos de Lucas e Felipe conectam seus históricos; a nota baixa de Lucas para *Robot Visions* não anula a compra positiva de Felipe |
| Felipe Pinto | *C++ Programmer's Notebook* e *Gilead*, entre outros | Livros dos clientes semelhantes que Felipe ainda não comprou ou avaliou |
| Clara Rodrigues | *Gold* e *Incident Response & Computer Forensics*, entre outros | O perfil misto de Lucas conecta ficção a computação; o algoritmo não limita similaridade ao gênero favorito |
| Giovana Macedo | *Island*, *The Perennial Philosophy* e *Brave New World*, entre outros | Preferência pelo autor Aldous Huxley; categorias e autores contribuem para a pontuação, com desempate por ISBN |

São exemplos da validação inicial, não uma lista fixa. Os perfis opcionais `DEMO_REC_*` também podem contribuir para a similaridade. Se *Java* deixar de aparecer para Lucas após a compra ao vivo, esse é o comportamento esperado.

## Consultas no Neo4j Browser

Somente as compras e avaliações acrescentadas por esta carga:

```cypher
MATCH (c:Cliente)-[r:COMPROU|AVALIOU]->(p:Produto)
WHERE r.demo_dataset = 'presentation-existing-v1'
RETURN c, r, p
```

Os cinco clientes, incluindo as preferências da cliente sem histórico:

```cypher
MATCH (c:Cliente)
WHERE c.id IN ['U3501', 'U0503', 'U0585', 'U0357', 'U0829']
OPTIONAL MATCH (c)-[r:COMPROU|AVALIOU|PREFERE]->(n)
RETURN c, r, n
```

Conferir notas e identificação dos dados fictícios:

```cypher
MATCH (c:Cliente)-[r:AVALIOU]->(p:Produto)
WHERE r.demo_dataset = 'presentation-existing-v1'
RETURN c.nome AS cliente, p.titulo AS livro, r.nota AS nota,
       r.created_at AS data, r.simulated AS ficticia
ORDER BY cliente, livro
```

Mostrar a nota baixa de Lucas, preservando o livro fora de suas sugestões:

```cypher
MATCH (c:Cliente {id: 'U3501'})-[r:AVALIOU]->(p:Produto {id: '9780451450647'})
RETURN c.nome AS cliente, p.titulo AS livro, r.nota AS nota
```

Conferir as quantidades simuladas da apresentação:

```cypher
MATCH ()-[r:COMPROU|AVALIOU]->()
WHERE r.demo_dataset = 'presentation-existing-v1'
RETURN type(r) AS relacionamento, count(r) AS quantidade
```

Sem conflitos com avaliações preexistentes, o resultado é `COMPROU: 10` e `AVALIOU: 16`. Esses números contam somente as relações marcadas por esta carga.

Após comprar pela aplicação, mostrar as compras de Lucas que não são simulações da carga:

```cypher
MATCH (c:Cliente {id: 'U3501'})-[r:COMPROU]->(p:Produto)
WHERE r.demo_dataset IS NULL
RETURN c, r, p
```

## Exemplos no MongoDB Compass

Na coleção `customers`, filtre o cadastro escolhido para a apresentação:

```json
{"_id": "U3501"}
```

Na coleção `orders`, mostre os pedidos confirmados de Lucas e ordene por `created_at: -1`:

```json
{"customer_id": "U3501", "status": "confirmed"}
```

Confira `_id`, `items`, `total_cents` e os estados em `integration`. O `_id` deve ser o número exibido pela interface. As dez compras simuladas não criam documentos nessa coleção; o checkout ao vivo cria um pedido.

Na coleção `books`, localize *Java* pelo ISBN:

```json
{"_id": "9780131492028"}
```

Se esse for o livro comprado, compare `stock` antes e depois. O estoque cai pela quantidade comprada, e o preço unitário fica registrado em `items.unit_price_cents` no pedido.

## Exemplos no RedisInsight

Com Lucas identificado, adicione um livro ao carrinho antes de executar:

```redis
HGETALL cart:U3501
HGETALL cart:meta:U3501
TTL cart:U3501
```

O primeiro Hash contém ISBN e quantidade; o segundo contém a revisão do carrinho. Preços e totais vêm do MongoDB. Após confirmar a compra, confira:

```redis
EXISTS cart:U3501 cart:meta:U3501
```

O resultado esperado é `0` quando a limpeza foi concluída e não houve novas alterações no carrinho. Um `TTL` de `-2` indica que a chave não existe.

Para comparar clientes, abra um segundo navegador e identifique Eduarda. Adicione um item e consulte `HGETALL cart:U0503`; seu carrinho deve ser independente de `cart:U3501`. Giovana deve continuar sem compras e avaliações para preservar seu cenário inicial.

## Verificação automatizada

```powershell
$env:SPACEBOOKS_INTEGRATION = "1"
.\.venv\Scripts\python.exe -m unittest tests.test_presentation -v
Remove-Item Env:SPACEBOOKS_INTEGRATION
```

Os testes usam dados temporários e verificam repetição, preservação de avaliações reais, cadastros/valores comerciais/pedidos, recomendações por similaridade e preferências, referências inválidas e rollback. Não reutilizam os clientes da apresentação.
