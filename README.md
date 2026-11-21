# 🦜 AvesRAG Dataset Builder

Pipeline que monta a base de espécies do [AvesRAG](https://github.com/rafaelladuarte/avesrag-assistant), um assistente open source que identifica aves brasileiras a partir de uma descrição em texto livre.

Para cada espécie, o builder entrega uma ficha canônica validada (`species`) e três documentos de busca com embedding (`species_retrieval_docs`). A base é reconstruída do zero com um comando, uma chave da OpenAI e uma do eBird.

> **Estado:** v2 em construção. O Marco 1 (fundação) está pronto: estrutura, CLI, settings, modelos, vocabulário e MongoDB com busca vetorial. As etapas do pipeline chegam nos marcos seguintes (tabela abaixo). Os scripts da v1 continuam em `src/avesrag_builder/ingest/` até o Marco 2.

## Como funciona

```text
fontes ──ingest──► raw_* ──resolve──► species_registry ──extract (LLM)──► species_extractions
                                                                                 │
              species_retrieval_docs ◄──docs── species (validada) ◄──fuse/validate┘
```

| # | Comando | Lê | Escreve | Marco |
| --- | --- | --- | --- | --- |
| 1 | `ingest <fonte>` | sites, APIs e planilhas | `raw_wikiaves`, `raw_avonet`, `raw_birdbase`, `raw_cbro`, `raw_ebird`, `raw_ibge` | 2 |
| 2 | `resolve` | `raw_*` | `species_registry` | 3 |
| 3 | `extract` | `raw_wikiaves`, `species_registry` | `species_extractions` | 4 |
| 4 | `fuse` | registry, extractions, `raw_*` | `species`, `species_occurrence` | 5 |
| 5 | `validate` | `species` | `_meta.dq_status` + relatório em `reports/` | 5 |
| 6 | `docs` | `species` aptas | `species_retrieval_docs` | 6 |
| 7 | `index` | — | índices `$vectorSearch` e `$search` | 6 (`--verificar` já funciona) |
| — | `run [--piloto]` | — | etapas 2 a 7 | 6 |

Cada etapa lê só das anteriores, pode ser rodada sozinha e é idempotente. O LLM aparece só no `extract`; o resto é determinístico, guiado pelos arquivos de `config/`.

## Pré-requisitos

- Python 3.13+ e [Poetry](https://python-poetry.org/docs/#installation)
- Docker com Docker Compose
- Chaves de API: [OpenAI](https://platform.openai.com/) (`extract`, `docs`) e [eBird](https://ebird.org/api/keygen) (`ingest ebird`)

## Instalação

```bash
git clone https://github.com/rafaelladuarte/avesrag-dataset-builder.git
cd avesrag-dataset-builder

poetry install
poetry run playwright install chromium   # scraping do WikiAves

cp .env.example .env                     # preencha as chaves
docker compose up -d                     # MongoDB com busca vetorial
poetry run avesrag-builder index --verificar
```

O último comando cria uma collection temporária com um índice `$vectorSearch` e um `$search`, consulta os dois e apaga tudo. Se ele disser `OK`, o MongoDB está pronto.

### MongoDB local

O `docker-compose.yml` usa a imagem `mongodb/mongodb-atlas-local:8.3.17`, que traz o `mongod` e o `mongot` (o processo que atende `$vectorSearch` e `$search`). Ela roda como replica set de um nó, por isso a URI tem `?directConnection=true`.

Se a porta 27017 já estiver em uso, escolha outra:

```bash
MONGODB_PORT=27018 docker compose up -d
# e no .env: MONGODB_URI=mongodb://localhost:27018/?directConnection=true
```

Para inspecionar os dados, conecte o [MongoDB Compass](https://www.mongodb.com/products/tools/compass) na mesma URI.

## Variáveis de ambiente

| Variável | Padrão | Uso |
| --- | --- | --- |
| `OPENAI_API_KEY` | — | obrigatória para `extract` e `docs` |
| `EBIRD_API_KEY` | — | obrigatória para `ingest ebird` |
| `MONGODB_URI` | `mongodb://localhost:27017/?directConnection=true` | conexão |
| `MONGODB_DATABASE` | `avesrag` | banco |
| `MONGODB_PORT` | `27017` | porta publicada pelo `docker-compose` |
| `LLM_PROVIDER` | `openai` | fornecedor do LLM |
| `LLM_MODEL` | `gpt-6-luna` | modelo do `extract` |
| `EMBEDDING_MODEL` | `text-embedding-3-large` | modelo dos embeddings |
| `PILOTO_MUNICIPIO_IBGE` | `3170206` (Uberlândia, MG) | município do `--piloto` |
| `WIKIAVES_MAX_ESPECIES` | `0` (sem limite) | limite do scraping |
| `AVESRAG_LOG_FILE` | — | grava o log também neste arquivo |

As chaves só são cobradas pelo comando que as usa: `--help` e os testes funcionam sem `.env`.

## Estrutura

```text
config/
├── vocabulario.yaml      # valores aceitos, sinônimos e mapeamentos AVONET/BIRDBASE → vocabulário
├── regras_bico.yaml      # família → tipo de bico, dieta → tipo, perfil visual de cada tipo
└── prompts/              # b01–b03 (Marco 4)
src/avesrag_builder/
├── cli.py                # avesrag-builder
├── core/                 # settings, logging, modelos Pydantic, vocabulário
├── db/                   # conexão, nomes das collections, verificação de busca
├── ingest/               # fontes (scripts da v1 até o Marco 2)
├── resolve/ llm/ extract/ fuse/ validate/ docs/
data/raw/                 # planilhas AVONET, BIRDBASE, CBRO, IBGE e lista do WikiAves
reports/                  # relatórios gerados (fora do git)
tests/
docs/legado/              # documentação e dados tratados da v1
```

O vocabulário e as regras se validam ao carregar: um valor inexistente num mapeamento, um sinônimo que aponta para dois valores ou um tipo de bico sem perfil faz o carregamento falhar com o caminho do erro. Entradas marcadas `PROPOSTA` nos YAMLs ainda precisam de revisão.

## Testes

```bash
poetry run pytest                    # unitários (não precisam de .env nem de rede)
poetry run pytest -m slow            # conferem os mapeamentos contra as planilhas de data/raw/
poetry run pytest -m integration     # precisam do MongoDB de pé (docker compose up -d)
poetry run ruff check src tests && poetry run ruff format --check src tests
```

## Migrando dados da v1 (MongoDB 7.0)

A v1 usava a imagem `mongo:7.0` com o volume `avesrag-dataset-builder_mongodb_data`. O compose novo usa outro nome de projeto (`avesrag-builder`) e outros volumes, então **o volume antigo não é tocado** por `docker compose up` ou `down -v`. Os arquivos de dados do 7.0 não devem ser abertos direto pelo 8.x: a migração é por dump e restore.

As collections que valem migrar são as caras de recoletar: `wikiaves` (scraping) e `ebird` (milhares de chamadas à API). As demais são regeneradas pelo pipeline. A conversão para o formato `raw_*` é feita pelo `ingest` no Marco 2; aqui elas entram como `legado_*`.

```bash
# 1. subir o MongoDB antigo (precisa da porta 27017 livre)
docker start mongodb_avesrag

# 2. exportar (use as credenciais do .env da v1)
docker exec mongodb_avesrag mongodump -u admin -p '<senha>' --authenticationDatabase admin \
  --db avesrag --archive=/tmp/v1.archive
docker cp mongodb_avesrag:/tmp/v1.archive ./v1.archive
docker stop mongodb_avesrag

# 3. importar só wikiaves e ebird no atlas-local, com prefixo legado_
docker compose up -d
docker cp ./v1.archive avesrag-mongodb:/tmp/v1.archive
docker exec avesrag-mongodb mongorestore --archive=/tmp/v1.archive \
  --nsInclude 'avesrag.wikiaves' --nsInclude 'avesrag.ebird' \
  --nsFrom 'avesrag.$c$' --nsTo 'avesrag.legado_$c$'
```

O arquivo `v1.archive` tem o banco inteiro da v1: guarde-o como backup.

Confira as contagens (`db.legado_wikiaves.countDocuments()`) antes de apagar qualquer coisa da v1.

## Fontes de dados

- **[WikiAves](https://www.wikiaves.com.br/)**: define o universo de espécies; textos em português, nome comum e foto de referência.
- **[CBRO 2021](https://doi.org/10.1007/s43388-021-00058-x)**: lista e taxonomia oficiais das aves do Brasil (1.971 espécies).
- **[AVONET](https://doi.org/10.1111/ele.13898)**: medidas morfológicas e categorias de habitat, dieta e locomoção.
- **BIRDBASE v2025.1**: nomes em 4 taxonomias (ponte para o eBird), IUCN 2024 e ecologia.
- **[eBird](https://ebird.org/)**: taxonomia (`speciesCode`) e espécies registradas por município.
- **[IBGE](https://www.ibge.gov.br/)**: bioma predominante por município.

A base gerada não é publicada: cada pessoa a reconstrói com as próprias chaves, porque a redistribuição depende dos termos de cada fonte.

## Licença

[MIT](LICENSE).
