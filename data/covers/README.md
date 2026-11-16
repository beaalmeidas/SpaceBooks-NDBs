# Capas originais

Cadastre arquivos de capa por ISBN: `data/covers/9780310243564.jpg` (também PNG, JPEG ou WebP).
Use imagens reais da edição, com pelo menos 300 pixels de largura; 600 pixels ou mais são recomendados.
Esses arquivos têm prioridade sobre fontes externas no catálogo e nos detalhes. Reconstrua o container após incluí-los.

O Google Books pode retornar imagens de erro com HTTP 200. O resolvedor rejeita as imagens de indisponibilidade identificadas, imagens corrompidas e proporções inválidas. Nas páginas visualizadas, tenta também a Open Library pelo ISBN, com cache e limite de consultas. Não faz varredura em massa da API.

Quando só existe uma miniatura, ela é apresentada no tamanho original, sem ampliação artificial. A existência de URL no CSV não garante uma capa real em alta resolução. Para garantir cobertura total, é necessário cadastrar os originais das edições ausentes; não são inventadas capas nem usadas imagens de outros livros.
