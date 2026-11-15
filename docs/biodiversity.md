# Fauna observada no entorno — UU-105

Piloto de leitura do iNaturalist; não importa o acervo nem cria pistas ou vínculos.

## Contrato

Ambos os endpoints exigem o Bearer privado da Geo API, enviado somente pela API do app:

- `GET /biodiversity/nearby?latitude=-29.794&longitude=-51.151&radius_m=1000`
  - Latitude [-90,90], longitude [-180,180], valores finitos; raios 500/1000/5000 m.
  - Até 12 táxons distintos identificados em nível de espécie ou inferior.
- `GET /biodiversity/observations?north=-29.78&south=-29.81&east=-51.13&west=-51.17`
  - Retângulo positivo com até 3 graus por eixo, sem cruzar o antimeridiano.
  - Até 100 observações, sem agrupar por espécie.

Resposta: `source`, `fetched_at`, `cached`, `radius_m`, `limit`, `sampled_records`,
`total_matching_observations`, `limited` e `observations`.
Cada observação inclui ID/link de origem, táxon, nomes, data, coordenada pública,
aproximação/precisão, URL da foto, crédito, licença e distância (somente no entorno).
O OpenAPI disponível em `/openapi.json` descreve o contrato tipado.

## Fontes e limites

- Provedor: https://api.inaturalist.org/v1/docs/
- Práticas: https://www.inaturalist.org/pages/api+recommended+practices
- Fonte/versão: API iNaturalist v1, observações públicas; sem dados privados/OAuth.
- Animalia (`taxon_id=1`), `verifiable=true`, `photos=true`, locale `pt-BR`.
- Uma página de até 200 observações recentes por data do avistamento.
- Fotos CC0, CC BY e CC BY-SA apenas; cada foto é validada novamente antes de exibir.
- Crédito e licença acompanham a foto. As imagens são carregadas por URL, sem cópia no S3 próprio.
- O banco guarda somente campos públicos usados pela interface. Perfis completos, comentários,
  campos privados e demais dados do JSON original não são persistidos.
- Localizações obscurecidas permanecem as coordenadas públicas; não se tenta recuperar a real.
- Não é um inventário completo nem uma evidência de presença atual ou ausência de animais.

## Operação

Nenhuma credencial adicional do iNaturalist é necessária. Cache SQLite em
`BIODIVERSITY_CACHE_PATH` (padrão `/data/biodiversity/cache.sqlite3`), com TTL de
`BIODIVERSITY_CACHE_SECONDS=21600` (6 h), compartilhado pelos processos da instância.
Montar `/data` persistente e gravável; o arquivo deve ser local, não NFS.
Não versionar o banco nem as imagens. Não há migração de PostGIS.

Reserva transacional em SQLite limita as tentativas de consulta a no máximo uma a cada
1,1 s e `BIODIVERSITY_DAILY_LIMIT=9000` por dia UTC (configuração limitada a 10000).
Um 429 impõe pausa compartilhada de 60 s. Cache hits não consomem quota.
Consultas concorrentes acima da quota retornam 503, sem repetir automaticamente.
Cache expirado não é servido em caso de falha: a interface mostra indisponibilidade opcional.
O TTL limita a defasagem de atualizações de licença/conteúdo; não se trata de espelho permanente.

Usar uma única réplica da Geo API com esse arquivo compartilhado entre seus workers.
Antes de escalar para várias réplicas/servidores, mover cache e quota para banco/Redis comum,
para manter uma saída/IP e orçamento únicos. Timeout externo 15 s; resposta externa limitada
em 8 MiB. A API do app limita a resposta a 2 MiB e usa timeout 20 s.

Ordem de implantação após revisão: Geo API → API principal → app. Produção não é alterada
por esta branch. O catálogo de tiles permanece intacto: fauna é uma camada dinâmica de pontos,
não um raster, e usa endpoints próprios documentados.
