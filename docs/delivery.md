# Validação da entrega

## Procedimento reproduzível

Siga, em ordem, a seção **Instalação a partir de um clone limpo** do README: gerar `.env`, iniciar bancos, preparar/carregar com `--check-idempotence`, construir a aplicação, conferir conexões, carregar opcionalmente os perfis fictícios e executar os testes.

A instalação padrão usa `requirements.txt` → `requirements-app.txt` → `requirements-db.txt`. O notebook usa exclusivamente `requirements-notebook.txt`, em outro ambiente. As saídas do notebook foram removidas; suas células de instalação agora remetem ao arquivo de dependências. Os caminhos relativos originais do notebook consideram o diretório `src/notebooks` como diretório de trabalho do kernel.

## Arquivos privados

`python -m src.check_delivery --history` verifica arquivos publicáveis, arquivos locais rastreados indevidamente, padrões de chaves privadas/tokens e correspondências com valores longos de credenciais presentes no `.env` local. O modo de histórico inclui blobs alcançáveis, inclusive arquivos já removidos. O relatório exibe apenas caminhos e motivos. Não substitui revisão humana ou detecta todos os formatos de segredo.

As regras Git e Docker excluem variantes locais de `.env`, ambientes virtuais, certificados/chaves, `.local/`, saídas preparadas e configurações de editores/agentes. `.env.example` contém apenas placeholders. Os dados persistentes ficam em volumes Docker, fora do repositório.

## Escopo do clone de validação

Como há mudanças de implementação ainda não commitadas no repositório de trabalho, a conferência usa um snapshot dos arquivos rastreados e novos não ignorados. Esse snapshot é registrado somente em um repositório temporário local e clonado para outro diretório vazio. O histórico e o índice do repositório de trabalho não são modificados. Assim, a validação exercita o conteúdo previsto para entrega; o clone remoto só terá esse conteúdo após o commit final.

O ambiente de validação usa projeto Compose, rede, credenciais e volumes novos, sem acessar os bancos principais. As portas do ambiente temporário não são publicadas. O certificado público de confiança exigido pela rede local é fornecido externamente como segredo de build, sem entrar no clone. Esse ajuste de infraestrutura não substitui arquivos da aplicação.

## Resultado da validação em 11 de novembro de 2026

- Clone local limpo do snapshot de 79 arquivos publicáveis, sem `.env`, saídas preparadas, ambientes virtuais ou certificados locais. A atualização das instruções de testes também foi registrada no repositório temporário e recebida por `pull --ff-only`, mantendo o clone limpo.
- Construção de `tools` e `catalog` com instalação das dependências declaradas: sucesso. Ambiente da imagem: Python 3.12, Streamlit 1.67.0, PyMongo 4.19.0, redis-py 6.4.0 e driver Neo4j 5.28.8. `pip check`: nenhuma dependência incompatível.
- Primeira inicialização em quatro volumes novos: MongoDB replica set `rs0`, Redis e Neo4j acessíveis. O Compose base passou em `config --quiet`; o inicializador MongoDB passou em `bash -n` e terminou com código zero.
- Preparação/carga: 6.215 livros, 3.501 clientes, 488 categorias, 6.215 relações `PERTENCE_A` e 7.045 `PREFERE`. Índices e constraints validados. Segunda carga sem duplicações ou restauração dos valores comerciais; expiração Redis verificada.
- Auditoria dos arquivos previstos e de 101 blobs do histórico original: nenhum dos padrões ou valores locais verificados foi encontrado. A auditoria do clone também passou, incluindo seu histórico temporário. Os três testes da auditoria passaram no host, cobrindo arquivo privado rastreado à força, vazamento em arquivo novo e segredo removido do histórico, sem exibir valores.
- Notebook: resolução das dependências com `pip --dry-run --ignore-installed`, sintaxe das células e ausência de saídas salvas verificadas. A exploração inteira e downloads externos de capas não foram executados; não são pré-requisitos da aplicação.

- Suíte completa no container do clone: `Ran 138 tests in 857.438s — OK (skipped=3)`. Foram executados com sucesso os 135 testes de domínio, serviços, persistência e interface. Os três casos ignorados exigem Git, ausente na imagem da aplicação, e passaram separadamente no host. As falhas Redis/Neo4j dos cenários de aceitação são injetadas nos drivers; os bancos e as demais operações são reais.

- Conferência adicional sem redirecionar as fábricas de serviços: carga dos cinco perfis fictícios, HTTP 200, identificação de `DEMO_REC_COLD`, inclusão pelo catálogo, navegação, revisão e confirmação via AppTest. Conferidos um pedido MongoDB, preço histórico, baixa de uma unidade, carrinho Redis vazio, uma relação `COMPROU` e todos os marcadores de integração concluídos. Recomendações e logout funcionaram. `src.retry_checkout --limit 100` retornou zero pedidos a regularizar.

Os containers, a rede, os quatro volumes e as duas imagens do projeto temporário foram removidos após os testes. A compra de validação não usou os bancos ou dados principais. O índice e o histórico do repositório de trabalho foram preservados; o commit final dos arquivos da entrega continua a cargo dos responsáveis pelo repositório.

Na conferência final, o Neo4j principal apresentou `unhealthy` por repetidas execuções de `cypher-shell` que ultrapassaram o prazo de 10 segundos durante a carga de testes. `src.check_connections` confirmou os três bancos acessíveis, incluindo autenticação/consulta Neo4j. O Compose passou a permitir 30 segundos para o mesmo teste autenticado, sem mudar as operações de negócio ou os dados. Esse ajuste de infraestrutura foi realizado após a suíte completa e recebe validação específica de configuração e do comando de saúde.

Validação específica concluída: `docker compose config --quiet` passou; somente o container Neo4j principal foi recriado, preservando o volume existente, e `docker compose up --wait --no-deps neo4j` confirmou **Healthy** com o prazo de 30 segundos. Uma nova execução de `src.check_connections` confirmou MongoDB, Redis e Neo4j acessíveis e a expiração Redis funcionando. Não foi necessário repetir a suíte de negócio para essa mudança exclusiva do teste de saúde.
