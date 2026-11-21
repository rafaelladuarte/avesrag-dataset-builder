# 🦜 AvesRAG Dataset Builder

Pipeline que monta a base de espécies do [AvesRAG](https://github.com/rafaelladuarte/avesrag-assistant), um assistente open source que identifica aves brasileiras a partir de uma descrição em texto livre.

Para cada espécie, o builder entrega uma ficha canônica validada (`species`) e três documentos de busca com embedding (`species_retrieval_docs`). A base é reconstruída do zero com um comando, uma chave da OpenAI e uma do eBird.

> **Estado:** v2 em construção. Prontos: o Marco 1 (estrutura, CLI, settings, modelos, vocabulário e MongoDB com busca vetorial) e o Marco 2 (ingestão das seis fontes). As demais etapas chegam nos marcos seguintes (tabela abaixo).

## Como funciona

```text
fontes ──ingest──► raw_* ──resolve──► species_registry ──extract (LLM)──► species_extractions
                                                                                 │
              species_retrieval_docs ◄──docs── species (validada) ◄──fuse/validate┘
```

| # | Comando | Lê | Escreve | Marco |
| --- | --- | --- | --- | --- |
| 1 | `ingest <fonte>` | sites, APIs e planilhas | `raw_wikiaves`, `raw_avonet`, `raw_birdbase`, `raw_cbro`, `raw_ebird`, `raw_ibge` | pronto |
| 2 | `resolve` | `raw_*` | `species_registry` | pronto |
| 3 | `extract` | `raw_wikiaves`, `species_registry` | `species_extractions` | 4 |
| 4 | `fuse` | registry, extractions, `raw_*` | `species`, `species_occurrence` | 5 |
| 5 | `validate` | `species` | `_meta.dq_status` + relatório em `reports/` | 5 |
| 6 | `docs` | `species` aptas | `species_retrieval_docs` | 6 |
| 7 | `index` | — | índices `$vectorSearch` e `$search` | 6 (`--verificar` já funciona) |
| — | `run [--piloto]` | — | etapas 2 a 7 | 6 |

Cada etapa lê só das anteriores, pode ser rodada sozinha e é idempotente. O LLM aparece só no `extract`; o resto é determinístico, guiado pelos arquivos de `config/`.

### Ingestão

Cada fonte vira uma collection `raw_<fonte>` com o formato `{_id, dados, ingerido_em, source_hash}`: `_id` é a chave na fonte e `dados` é o registro como veio. Um documento só é regravado quando o `source_hash` muda, então rodar de novo sem mudança na fonte não grava nada.

```bash
# planilhas de data/raw/ (sem rede, ~1 min no total)
poetry run avesrag-builder ingest cbro       # 1.971 espécies (id #CBRO)
poetry run avesrag-builder ingest ibge       # 5.572 municípios (id = geocódigo)
poetry run avesrag-builder ingest birdbase   # 11.589 espécies (id = IOC 15.1)
poetry run avesrag-builder ingest avonet     # abas BirdLife e eBird + correspondência entre elas

# eBird: taxonomia (pt_BR) + espécies registradas no município do piloto (3 chamadas)
poetry run avesrag-builder ingest ebird --piloto

# WikiAves: lista completa + páginas das espécies do piloto (~1 h, ~7 s por página)
poetry run avesrag-builder ingest wikiaves --piloto
```

A ordem importa só no fim: o `wikiaves --piloto` escolhe as páginas a partir de `raw_ebird` e usa as pontes de nomes do `raw_birdbase` e do `raw_avonet`. Sem `--piloto`, o `ebird` percorre todos os municípios (~1 a 2 h) e o `wikiaves`, todas as 1.975 páginas (~4 h). Os dois retomam de onde pararam; `--refazer` baixa tudo de novo e `--limite N` (wikiaves) para depois de N páginas.

### Registry

```bash
poetry run avesrag-builder resolve   # 1.975 espécies, ~2 s, sem rede
```

Um documento por espécie do WikiAves em `species_registry`, com `species_id` = slug do nome científico (índice único; o `_id` é o ObjectId do Mongo). Cada fonte guarda a chave do seu `raw_*` (`_id` do doc, ou o `speciesCode` no eBird) e o tipo de casamento: `exato`, `ponte` (correspondência do AVONET), `genero` (mesmo epíteto e família, gênero trocado) ou `sem_match`. Rodar de novo só grava o que mudou; espécies que saem do WikiAves não são apagadas. Relatórios em `reports/`: `resolve_sem_match.tsv` (por fonte), `resolve_piloto.tsv` (espécies do eBird do município do piloto fora do registry ou casadas por aproximação) e `resolve_orfaos.txt`.

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

Para desligar, use `docker compose stop`: o `pre_stop` do compose pede ao mongod um desligamento limpo (a imagem ignora o SIGTERM). Evite `docker stop` direto no container.

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

## Dados da v1

A v1 rodava em `mongo:7.0`. Em 20/11/2026 o banco inteiro foi exportado com `mongodump` (`v1_avesrag_mongo7_20261120.archive.gz`, guardado fora do repositório) e o volume antigo foi apagado. As collections caras de recoletar foram restauradas no MongoDB novo como `legado_wikiaves` (1.925 espécies) e `legado_ebird` (5.572 municípios). Elas servem só de reserva: a v2 coleta das fontes pelo `ingest`.

Para restaurar de novo a partir do arquivo:

```bash
docker cp v1_avesrag_mongo7_20261120.archive.gz avesrag-mongodb:/tmp/v1.archive.gz
docker exec avesrag-mongodb mongorestore --gzip --archive=/tmp/v1.archive.gz \
  --nsInclude 'avesrag.wikiaves' --nsInclude 'avesrag.ebird' \
  --nsFrom 'avesrag.$c$' --nsTo 'avesrag.legado_$c$'
```

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
