# 🦜 AvesRAG Dataset Builder

Pipeline que monta a base de espécies do [AvesRAG](https://github.com/rafaelladuarte/avesrag-assistant), um assistente open source que identifica aves brasileiras a partir de uma descrição em texto livre.

**O que ele entrega:** para cada espécie, uma ficha validada (`species`) e três documentos de busca com embedding (`species_retrieval_docs`).

**O que você precisa:** Docker, Python 3.13, uma chave da OpenAI e uma do eBird.

## Estado

A v2 está em construção.

| Marco | Etapa | Situação |
| --- | --- | --- |
| 1 | Fundação: CLI, settings, modelos, MongoDB com busca vetorial | ✅ pronto |
| 2 | Ingestão das seis fontes | ✅ pronto |
| 3 | Registry de espécies | ✅ pronto |
| 4 | Extração por LLM | ✅ pronto |
| 5 | Fusão e validação | ✅ pronto |
| 6 | Documentos de busca e índices | ⏳ pendente |
| 7 | Reprodutibilidade | ⏳ pendente |

---

## Início rápido

```bash
git clone https://github.com/rafaelladuarte/avesrag-dataset-builder.git
cd avesrag-dataset-builder

poetry install
poetry run playwright install chromium        # usado no scraping do WikiAves

cp .env.example .env                          # preencha OPENAI_API_KEY e EBIRD_API_KEY
docker compose up -d                          # sobe o MongoDB
poetry run avesrag-builder index --verificar  # deve terminar com "OK"
```

O `index --verificar` cria uma collection temporária, testa o `$vectorSearch` e o `$search` e apaga tudo. Se aparecer `OK`, o ambiente está pronto.

---

## Como funciona

```text
fontes ──ingest──► raw_* ──resolve──► species_registry ──extract (LLM)──► species_extractions
                                                                                 │
              species_retrieval_docs ◄──docs── species (validada) ◄──fuse/validate┘
```

O pipeline é uma sequência de comandos. Três regras valem para todos:

- **Cada etapa lê só das anteriores** e pode ser rodada sozinha.
- **Rodar de novo é seguro:** se nada mudou na fonte, nada é gravado.
- **O LLM aparece só no `extract`.** O resto é determinístico e vem dos arquivos de `config/`.

| Comando | O que faz | Grava em | Situação |
| --- | --- | --- | --- |
| `ingest <fonte>` | baixa ou lê cada fonte | `raw_<fonte>` | ✅ |
| `resolve` | casa as espécies entre as fontes | `species_registry` | ✅ |
| `extract` | extrai atributos dos textos com LLM | `species_extractions` | ✅ |
| `fuse` | junta tudo numa ficha por espécie | `species`, `species_occurrence` | ✅ |
| `validate` | confere a qualidade das fichas | `_meta.dq_status` | ✅ |
| `docs` | gera os documentos de busca | `species_retrieval_docs` | Marco 6 |
| `index` | cria os índices de busca | — | Marco 6 (`--verificar` já funciona) |
| `run [--piloto]` | roda do `resolve` ao `index` | — | Marco 6 |

O **piloto** limita o trabalho às espécies registradas no eBird em Uberlândia (MG), cerca de 440. É o escopo usado no desenvolvimento.

---

## Passo a passo

### 1. Ingestão

```bash
# Planilhas de data/raw/: sem rede, ~1 min no total
poetry run avesrag-builder ingest cbro
poetry run avesrag-builder ingest ibge
poetry run avesrag-builder ingest birdbase
poetry run avesrag-builder ingest avonet

# APIs e sites
poetry run avesrag-builder ingest ebird --piloto      # 3 chamadas à API
poetry run avesrag-builder ingest wikiaves --piloto   # ~1 h (~7 s por página)
```

**Rode o `wikiaves` por último:** ele usa o eBird para escolher as páginas e o BIRDBASE e o AVONET para casar os nomes.

<details>
<summary>Mais detalhes</summary>

- Cada fonte vira uma collection `raw_<fonte>` no formato `{_id, dados, ingerido_em, source_hash}`. O `_id` é a chave na fonte e `dados` é o registro como chegou. Um documento só é regravado quando o `source_hash` muda.
- O que cada fonte traz: CBRO, 1.971 espécies (id = #CBRO); IBGE, 5.572 municípios (id = geocódigo); BIRDBASE, 11.589 espécies (id = IOC 15.1); AVONET, as abas BirdLife e eBird e a correspondência entre elas.
- Sem `--piloto`, o `ebird` percorre todos os municípios (~1 a 2 h) e o `wikiaves` baixa as 1.975 páginas (~4 h).
- O `ebird` e o `wikiaves` retomam de onde pararam. Use `--refazer` para baixar tudo de novo e `--limite N` (só no `wikiaves`) para parar depois de N páginas.

</details>

### 2. Registry

```bash
poetry run avesrag-builder resolve   # ~2 s, sem rede
```

Cria um documento por espécie do WikiAves (1.975) e anota, para cada fonte, qual registro corresponde a ela.

<details>
<summary>Mais detalhes</summary>

- O `species_id` é o slug do nome científico, com índice único. O `_id` é o ObjectId do Mongo.
- Tipos de casamento: `exato`; `ponte`, pela correspondência do AVONET; `genero`, com o mesmo epíteto e a mesma família, mas outro gênero; e `sem_match`.
- Espécies que saem do WikiAves não são apagadas.
- Relatórios em `reports/`:
  - `resolve_sem_match.tsv`: espécies sem casamento, por fonte;
  - `resolve_piloto.tsv`: espécies do piloto fora do registry ou casadas por aproximação;
  - `resolve_orfaos.txt`.

</details>

### 3. Extração (LLM)

```bash
poetry run avesrag-builder extract --piloto --limite 5 --sincrono   # teste: 5 espécies, chamadas diretas
poetry run avesrag-builder extract --piloto                          # piloto inteiro, pela API de batch
poetry run avesrag-builder extract --piloto --sem-esperar            # só envia ou coleta o lote e sai
```

Para cada espécie, três prompts leem os textos do WikiAves:

| Prompt | Lê | Extrai |
| --- | --- | --- |
| `b01_aparencia` | Características | cores, marcas, cauda e tamanho |
| `b02_comportamento` | Hábitos, Alimentação | ambiente, onde estava, o que fazia, grupo e atividade |
| `b03_textos_busca` | os quatro textos | três textos curtos para a busca |

A resposta segue um JSON Schema estrito, gerado do `config/vocabulario.yaml`. Cada valor vem com um trecho de evidência, e o builder confere esse trecho no texto original. O piloto inteiro custa cerca de US$ 0,30 em batch.

**Pode interromper o script.** O lote roda na OpenAI e fica registrado em `llm_batches`. Na próxima execução, o `extract` coleta o lote em vez de enviar de novo.

<details>
<summary>Mais detalhes</summary>

- **Cache:** um par espécie × prompt só vai ao LLM se o `input_hash` (modelo + prompt + entrada + schema) ou a `versao` do prompt mudou.
- **Atenção:** se você mudar os prompts, o vocabulário ou o modelo com um lote em andamento, as respostas desse lote são descartadas e os pedidos são enviados de novo.
- **Falhas:** uma resposta inválida é refeita uma vez, por chamada direta. Se falhar de novo, fica gravada com `validacao.erro` e é tentada de novo na próxima execução. Espécie sem texto vira `sem_texto`, sem chamada ao LLM.
- **Relatório:** `reports/extract.tsv`, com uma linha por par. O terminal mostra um resumo com a taxa de respostas válidas, as evidências não encontradas, os tokens e o custo.
- O texto do WikiAves é tratado como dado, nunca como instrução: ele vai delimitado no prompt.

</details>

---

## Configuração

### Variáveis de ambiente

Só as chaves de API são obrigatórias, e cada uma só é cobrada pelo comando que a usa. O `--help` e os testes rodam sem `.env`.

| Variável | Para quê |
| --- | --- |
| `OPENAI_API_KEY` | `extract` e `docs` |
| `EBIRD_API_KEY` | `ingest ebird` |

<details>
<summary>Todas as variáveis</summary>

| Variável | Padrão | Uso |
| --- | --- | --- |
| `MONGODB_URI` | `mongodb://localhost:27017/?directConnection=true` | conexão |
| `MONGODB_DATABASE` | `avesrag` | banco |
| `MONGODB_PORT` | `27017` | porta publicada pelo `docker-compose` |
| `LLM_PROVIDER` | `openai` | fornecedor do LLM |
| `LLM_MODEL` | `gpt-6-luna` | modelo do `extract` (o `modelo` do YAML do prompt tem prioridade) |
| `LLM_PRECO_ENTRADA`, `LLM_PRECO_SAIDA` | `0.05`, `0.25` | US$ por milhão de tokens em batch, para a estimativa de custo |
| `EMBEDDING_MODEL` | `text-embedding-3-large` | modelo dos embeddings |
| `PILOTO_MUNICIPIO_IBGE` | `3170206` (Uberlândia, MG) | município do `--piloto` |
| `WIKIAVES_MAX_ESPECIES` | `0` (sem limite) | limite do scraping |
| `AVESRAG_LOG_FILE` | — | grava o log também neste arquivo |

</details>

### MongoDB

A imagem `mongodb/mongodb-atlas-local:8.3.17` traz o `mongod` e o `mongot` (o processo que atende `$vectorSearch` e `$search`). Ela roda como replica set de um nó, por isso a URI leva `?directConnection=true`.

- **Desligar:** use `docker compose stop`, não `docker stop`. A imagem ignora o SIGTERM, e é o `pre_stop` do compose que faz o desligamento limpo.
- **Porta ocupada:** rode `MONGODB_PORT=27018 docker compose up -d` e, no `.env`, use `MONGODB_URI=mongodb://localhost:27018/?directConnection=true`.
- **Ver os dados:** conecte o [MongoDB Compass](https://www.mongodb.com/products/tools/compass) na mesma URI.

### Vocabulário e regras

- `config/vocabulario.yaml` define os valores aceitos, os sinônimos e os mapeamentos AVONET/BIRDBASE → vocabulário.
- `config/regras_bico.yaml` define família → tipo de bico, dieta → tipo de bico e o perfil visual de cada tipo.
- `config/regras_fusao.yaml` define os cortes de tamanho (por comprimento e, na falta dele, por massa) e o que uma ficha precisa ter para ser `apta`.

Os três se validam ao carregar. Um valor inexistente, um sinônimo ambíguo ou um tipo de bico sem perfil faz o carregamento falhar, indicando onde está o erro.

---

## Testes

```bash
poetry run pytest                    # unitários: sem .env, sem rede
poetry run pytest -m slow            # conferem os mapeamentos contra as planilhas de data/raw/
poetry run pytest -m integration     # precisam do MongoDB de pé
poetry run ruff check src tests && poetry run ruff format --check src tests
```

---

## Estrutura

<details>
<summary>Ver a árvore de pastas</summary>

```text
config/
├── vocabulario.yaml      # valores aceitos, sinônimos e mapeamentos
├── regras_bico.yaml      # tipo de bico e perfil visual
├── regras_fusao.yaml     # cortes de tamanho e critérios de apta
└── prompts/              # b01_aparencia, b02_comportamento, b03_textos_busca
src/avesrag_builder/
├── cli.py                # comando avesrag-builder
├── core/                 # settings, logging, modelos Pydantic, vocabulário e regras
├── db/                   # conexão, nomes das collections, verificação da busca
├── ingest/               # uma ingestão por fonte
├── resolve/              # species_registry
├── llm/                  # interface de fornecedor, adaptador OpenAI e leitor dos prompts
├── extract/              # contratos, evidências e pipeline do extract
├── fuse/                 # regras por campo, species e species_occurrence
└── validate/             # validações, dq_status e relatório
data/raw/                 # planilhas AVONET, BIRDBASE, CBRO, IBGE e lista do WikiAves
reports/                  # relatórios gerados (fora do git)
tests/
docs/legado/              # documentação e dados tratados da v1
```

</details>

---

## Fontes de dados

| Fonte | Para quê |
| --- | --- |
| [WikiAves](https://www.wikiaves.com.br/) | define o universo de espécies; textos em português, nome comum e foto |
| [CBRO 2021](https://doi.org/10.1007/s43388-021-00058-x) | lista e taxonomia oficiais das aves do Brasil (1.971 espécies) |
| [AVONET](https://doi.org/10.1111/ele.13898) | medidas morfológicas, habitat, dieta e locomoção |
| BIRDBASE v2025.1 | nomes em 4 taxonomias (ponte para o eBird), IUCN 2024 e ecologia |
| [eBird](https://ebird.org/) | taxonomia (`speciesCode`) e espécies registradas por município |
| [IBGE](https://www.ibge.gov.br/) | bioma predominante de cada município |

A base gerada não é publicada. Cada pessoa a reconstrói com as próprias chaves, porque a redistribuição depende dos termos de cada fonte.

---

## Dados da v1

<details>
<summary>Backup e restauração</summary>

A v1 rodava em `mongo:7.0`. Em 20/11/2026, o banco inteiro foi exportado com `mongodump` (`v1_avesrag_mongo7_20261120.archive.gz`, guardado fora do repositório) e o volume antigo foi apagado.

As collections mais caras de coletar de novo foram restauradas como `legado_wikiaves` (1.925 espécies) e `legado_ebird` (5.572 municípios). Elas servem só de reserva: a v2 coleta tudo das fontes pelo `ingest`.

Para restaurar a partir do arquivo:

```bash
docker cp v1_avesrag_mongo7_20261120.archive.gz avesrag-mongodb:/tmp/v1.archive.gz
docker exec avesrag-mongodb mongorestore --gzip --archive=/tmp/v1.archive.gz \
  --nsInclude 'avesrag.wikiaves' --nsInclude 'avesrag.ebird' \
  --nsFrom 'avesrag.$c$' --nsTo 'avesrag.legado_$c$'
```

</details>

---

## Licença

[MIT](LICENSE).
