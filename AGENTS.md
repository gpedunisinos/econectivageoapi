# AGENTS.md — Task Flow (SPO)

1. Criar branches no formato `<JIRA>-<slug>` a partir de `main` atualizada.
2. Manter o contrato OpenAPI, catálogo e fontes versionadas ao alterar indicadores ou camadas.
3. Não versionar rasters, vetores brutos, credenciais ou tokens.
4. Executar `ruff check .` e `pytest --cov=app` antes da publicação.
5. Commits devem mencionar a tarefa Jira e usar as seções `Added`, `Changed` ou `Fixed`.
6. Publicar a branch e mover a tarefa para Review; não marcar Done sem validação humana.
