# SpaceBooks-NDBs
E-commerce de livros e sistema de recomendação. Projeto final da disciplina de Implementação e Gestão de Bancos de Dados NoSQL, Ciência da Computação 26.2.

O projeto possui preparação do catálogo e modelos de domínio para livros, clientes, pedidos, avaliações e carrinhos. As conexões com MongoDB, Redis e Neo4j e a interface Streamlit ainda serão implementadas.

## Executar

Requer Python 3.10 ou superior. Modelos, preparação e testes usam apenas a biblioteca padrão. O notebook exploratório tem dependências próprias.

Na raiz do repositório:

```powershell
py -3 -m src.prepare_data
py -3 -m unittest discover -s tests -v
```

Em sistemas que usam `python`, substitua `py -3` por `python`.

A preparação lê `data/books-processed.csv` e `data/users.csv`, preserva os CSVs originais e gera em `data/prepared/`:

| Arquivo | Conteúdo |
| --- | --- |
| `books.jsonl` | Livros com preços em centavos e estoque fictícios |
| `customers.jsonl` | Clientes com preferências convertidas em listas |
| `graph.jsonl` | Nós e relacionamentos para um futuro carregador Neo4j |
| `manifest.json` | Quantidades, regras de geração e hashes SHA-256 das entradas |

As saídas são reproduzíveis e estão no `.gitignore`. O comando não se conecta aos bancos. O JSONL do grafo é um formato interno, não um dump nativo do Neo4j.

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
| `src/notebooks/books-exploration.ipynb` | Exploração e limpeza original |
| `tests/` | Testes de domínio e preparação |
| `docs/data-model.md` | Contratos dos dados e dos bancos |

Consulte [a modelagem dos dados](docs/data-model.md) para os campos, identificadores, regras do checkout e responsabilidades de cada banco.
