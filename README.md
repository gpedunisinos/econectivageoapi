# Educação OnLIFE — API Geo

Serviço geoespacial da plataforma **Educação OnLIFE**, desenvolvido em **Python**, com **FastAPI**, **PostgreSQL/PostGIS** e processamento de rasters em formato COG. Fornece contexto socioambiental para coordenadas e camadas para os mapas da plataforma.

**[Plataforma](https://educacaoonlife.gpedu.com.br)** · **[Aplicativo](https://github.com/gpedunisinos/educacaoonlifeapp)** · **[API principal](https://github.com/gpedunisinos/econectivaapi)** · **[Financiamento](#financiamento)**

O serviço utiliza versões identificadas das bases territoriais para:

1. enriquecer automaticamente uma Pista Viva a partir de sua coordenada;
2. disponibilizar camadas ativáveis no mapa por tiles.

## Endpoints

| Método | Endpoint | Uso |
|---|---|---|
| `GET` | `/health` | Saúde e camadas configuradas |
| `POST` | `/context` | Contexto socioambiental da coordenada |
| `GET` | `/layers` | Catálogo, fontes, estilos e legendas |
| `GET` | `/tiles/{layer}/{z}/{x}/{y}.png` | Tiles raster transparentes |
| `GET` | `/tiles/satellite/{z}/{x}/{y}.jpg` | Mapa-base Esri World Imagery |
| `GET` | `/vector-tiles/{layer}/{z}/{x}/{y}.pbf` | Vector tiles PostGIS |
| `GET` | `/docs` | OpenAPI interativo |

Exceto `/health`, `/docs` e `/openapi.json`, os endpoints exigem `Authorization: Bearer <API_TOKEN>`.

### Consulta de contexto

No terminal, defina `API_TOKEN` com o mesmo valor configurado no serviço antes de executar a consulta.

```bash
curl -X POST http://localhost:8000/context \
  -H "Authorization: Bearer ${API_TOKEN}" \
  -H 'Content-Type: application/json' \
  -d '{"latitude":-29.9442,"longitude":-51.1847}'
```

Exemplo ilustrativo de resposta (os valores dependem das fontes disponíveis):

```json
{
  "biome": "Mata Atlântica",
  "land_cover": "Área urbanizada",
  "vegetation_percent": 18.2,
  "water_distance_m": 240,
  "altitude_m": 732,
  "slope_percent": 8.4,
  "built_up_percent": 61,
  "population_density_km2": 4270,
  "sources": {
    "land_cover": {
      "layer_id": "land-cover",
      "dataset": "MapBiomas Brasil 10 m",
      "version": "collection-4-2025",
      "radius_m": 250
    }
  },
  "generated_at": "2026-08-29T15:00:00Z",
  "warnings": []
}
```

Falhas de uma fonte são isoladas: os outros valores continuam sendo retornados e o campo
`warnings` explica a indisponibilidade. A API Go armazena o resultado como snapshot.

## Fontes previstas

| Indicador/camada | Fonte | Armazenamento |
|---|---|---|
| Bioma | IBGE, escala 1:250.000 | PostGIS |
| Cobertura, vegetação e ocupação construída | MapBiomas 10 m, Coleção 4/2025 | COG |
| Altitude e declividade | TOPODATA/INPE | COG |
| Hidrografia | ANA BHO Multiescalas 6 | PostGIS |
| Densidade populacional | IBGE, Censo 2022 por setor | PostGIS |

Os dados não são incluídos na imagem Docker nem no Git. Isso mantém as versões auditáveis e
evita imagens com dezenas de gigabytes.

## Instalação e execução local

### Pré-requisitos

- Docker com Compose para executar a API e o PostGIS.
- Python **3.12 ou superior** para desenvolvimento fora do contêiner.
- Fontes geográficas oficiais para habilitar as camadas que dependem de dados importados.
- Credencial do provedor de mapas-base, caso essa integração seja utilizada.

```bash
git clone git@github.com:gpedunisinos/econectivageoapi.git
cd econectivageoapi
cp .env.example .env
```

Edite o `.env`, defina um `API_TOKEN` próprio e ajuste as configurações do ambiente. O token, as credenciais do banco e os dados geográficos não devem ser publicados no Git.

```bash
docker compose up --build
```

O PostGIS fica disponível na porta local `5433` e a API em `8000`.
Antes de iniciar a API, o contêiner executa automaticamente `alembic upgrade head`.

Sem dados importados, a aplicação inicia normalmente. O catálogo marca os rasters como
indisponíveis e o `/context` retorna resultados parciais com avisos.

### Mapa-base de satélite

Crie uma credencial no ArcGIS Location Platform com acesso a mapas-base e configure:

```dotenv
ESRI_BASEMAP_ENABLED=true
ESRI_BASEMAP_TOKEN=token-da-aplicacao
```

Sem essas duas configurações, `satellite` permanece visível no catálogo como indisponível. O
token é utilizado somente pelo Geo API e nunca é devolvido ao app. A atribuição Esri fornecida
pelo catálogo deve permanecer visível enquanto esse mapa-base estiver selecionado.

## Preparação dos rasters

Baixe as versões oficiais e transforme os GeoTIFFs em COGs:

```bash
./scripts/prepare_cog.sh \
  data/raw/brazil_coverage-col4_10m_2025.tif \
  data/processed/mapbiomas_coverage_2025.tif

./scripts/prepare_cog.sh \
  data/processed/topodata_elevation.vrt \
  data/processed/topodata_elevation.tif \
  bilinear

# Recomendado para os tiles: preserva o VRT nativo para consultas pontuais e
# produz um COG visual a 90 m, muito menor e mais rápido.
./scripts/prepare_topodata_tile_cog.sh \
  data/processed/topodata_elevation.vrt \
  data/processed/topodata_elevation_tiles_90m.tif
```

O script cria overviews, compressão e checksum SHA-256. Para altitude e declividade do
TOPODATA, primeiro é necessário montar o mosaico nacional das folhas e então executar o mesmo
script com reamostragem `bilinear`. A reamostragem categórica do MapBiomas permanece `nearest`.
O serviço mantém um cache persistente de tiles em `RASTER_TILE_CACHE_DIR`; incremente
`RASTER_TILE_CACHE_VERSION` sempre que uma fonte ou estilo for atualizado.
Configure o COG visual em `ELEVATION_TILE_COG_URL`. `ELEVATION_COG_URL` pode continuar
apontando para o mosaico nativo usado na consulta pontual de contexto. O mesmo padrão se aplica
a `SLOPE_TILE_COG_URL` e `SLOPE_COG_URL`.

Também é possível apontar as variáveis `*_COG_URL` para URLs HTTPS/S3 que aceitem requisições
HTTP Range; o serviço não precisa baixar o arquivo inteiro.

## Importação dos vetores

O schema é versionado por Alembic em `migrations/versions`. Para importar um arquivo oficial:

```bash
python scripts/import_vector.py biomes data/raw/biomas.gpkg \
  --database-url 'host=localhost port=5433 dbname=geo user=geo password=geo'

psql 'postgresql://geo:geo@localhost:5433/geo' \
  -f scripts/normalize_biomes.sql
```

Fluxos equivalentes estão disponíveis para `hydrography` e `population`. Como nomes de campos
podem mudar entre edições das fontes, revise o SQL de normalização contra o dicionário da versão
baixada antes da execução. Depois da validação, habilite a camada correspondente no `.env`:

```dotenv
BIOMES_ENABLED=true
HYDROGRAPHY_ENABLED=true
POPULATION_ENABLED=true
```

Registre versão, URL e checksum na tabela `dataset_imports` a cada carga.

## Cálculos

- Bioma: polígono que cobre a coordenada.
- Cobertura predominante: moda das classes do MapBiomas em raio configurável de 250 m.
- Vegetação: percentual das classes vegetadas dentro do mesmo raio.
- Ocupação construída: percentual da classe Área urbanizada.
- Altitude: valor do MDE na coordenada.
- Declividade: média em raio configurável de 100 m.
- Hidrografia: distância geodésica até a drenagem mais próxima em até 50 km.
- Densidade: população dividida pela área geodésica do setor censitário.

## Integração com a plataforma

A API principal consulta este serviço para enriquecer pistas e intermediar o acesso ao catálogo e aos tiles. A credencial permanente da API Geo permanece no backend; não deve ser distribuída no aplicativo Flutter.

As sete camadas do catálogo possuem representação PNG para uso uniforme pelo mapa. Biomas, hidrografia e densidade populacional são rasterizados sob demanda a partir do PostGIS; os endpoints PBF também estão disponíveis para clientes vetoriais.

## Desenvolvimento

```bash
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/alembic upgrade head
```

Para criar uma nova migração, use `make migration message="descricao_da_alteracao"`. Toda
alteração estrutural deve possuir `upgrade` e `downgrade`; o arquivo `sql/001_schema.sql` é
mantido apenas como referência do schema-base e não é executado pelo Docker Compose.

## Decisões de segurança

- O token permanente deve existir somente entre a API Go e esta Geo API.
- O aplicativo deve acessar os serviços geográficos pela API principal; não incorporar o token permanente da API Geo no frontend.
- Não registre segredos, URLs assinadas ou credenciais de buckets no catálogo.
- Os identificadores de tabelas são definidos exclusivamente por configuração administrativa e
  interpolados com identificadores seguros do Psycopg.

## Estrutura do projeto

```text
app/          Aplicação FastAPI, serviços e provedores geográficos
migrations/   Evolução do schema PostGIS com Alembic
scripts/      Preparação e importação das bases geográficas
sql/          Referência do schema-base
data/         Diretórios locais de dados, sem as bases versionadas
```

## Documentação e contribuições

- A documentação interativa fica em `/docs` na instância da API.
- A especificação OpenAPI fica em `/openapi.json`.
- [Origem desta publicação no GitHub](docs/publicacao-github.md).
- Sugestões e problemas podem ser registrados nas [issues do projeto](https://github.com/gpedunisinos/econectivageoapi/issues). Envie alterações por pull request, descrevendo os impactos sobre os endpoints, as camadas e as fontes de dados.

## Financiamento

Esta API integra a plataforma Educação OnLIFE, cujo desenvolvimento conta com financiamento da **Fundação de Amparo à Pesquisa do Estado do Rio Grande do Sul (FAPERGS)** e da **Fundação de Amparo à Pesquisa do Estado de São Paulo (FAPESP)**.

<p>
  <a href="https://fapergs.rs.gov.br/"><img src="docs/assets/financiamento/fapergs.jpg" alt="FAPERGS — Fundação de Amparo à Pesquisa do Estado do Rio Grande do Sul" width="280"></a>
  &nbsp;&nbsp;
  <a href="https://fapesp.br/"><img src="docs/assets/financiamento/fapesp.svg" alt="FAPESP — Fundação de Amparo à Pesquisa do Estado de São Paulo" width="260"></a>
</p>

Logos de origem institucional: [FAPERGS](https://fapergs.rs.gov.br/identidade-visual) e [FAPESP](https://fapesp.br/). As marcas pertencem às respectivas instituições; o logo branco original da FAPESP é apresentado proporcionalmente sobre fundo azul para manter a legibilidade.

## Fauna observada no entorno

O piloto iNaturalist adiciona consultas de fauna por raio ou área visível, com cache persistente e quota compartilhada. Consulte o [contrato, fontes, limites e operação](docs/biodiversity.md).

## Avisos DETER Amazônia — TerraBrasilis

A integração `/deter/nearby?latitude=...&longitude=...&radius_m=1000` consulta um
snapshot local dos últimos **365 dias** de avisos públicos em áreas de floresta na
Amazônia. Raios aceitos: 500, 1000 e 5000 metros. Retorna cobertura, período,
classes, quantidade, data de sincronização e indicação de dados desatualizados.
Ausência de avisos não comprova ausência de alterações ambientais. Os avisos
DETER não equivalem à taxa anual de desmatamento do PRODES.

A camada opcional `deter-amazonia` está disponível no catálogo após a primeira
importação e é exibida entre os zooms 10 e 18, com cache limitado a 256 tiles.
A versão do cache acompanha a sincronização. Credenciais permanecem no backend.

Primeira carga, após `alembic upgrade head`:

```bash
python -c 'from app.services.deter import sync_snapshot; print(sync_snapshot(force=True))'
```

O processo usa o ZIP oficial do INPE com GDAL `/vsizip`, sem extrair o acervo todo.
Limites: ZIP 512 MiB, conteúdo descompactado declarado 2 GiB, seleção 256 MiB,
100 mil registros, conversão 180 segundos e margem livre mínima de 2 GiB.
A troca do snapshot é transacional, protegida por advisory lock; falhas preservam
a carga anterior. Geometrias inválidas são reparadas, vazias são rejeitadas e
identificadores repetidos da fonte não são usados sozinhos como chave.
Arquivos temporários são removidos. Cada instância verifica a necessidade de
atualização a cada hora; após a primeira carga a atualização ocorre, no máximo,
uma vez por dia. Não são necessários cron, novos serviços ou alterações de `.env`.

Fonte: <https://terrabrasilis.dpi.inpe.br/downloads/>.
A implantação inicial inclui somente DETER Amazônia; não inclui PRODES, DETER
Cerrado ou avisos em áreas de Não Floresta. Indicação de cobertura refere-se ao
bioma; o produto é restrito às áreas de floresta monitoradas pelo DETER Amazônia.
