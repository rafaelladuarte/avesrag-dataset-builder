# 🦜 AvesRAG Dataset Builder

Pipeline que monta a base de espécies do [AvesRAG](https://github.com/rafaelladuarte/avesrag-assistant), um assistente open source que identifica aves brasileiras a partir de uma descrição em texto livre.

**O que ele entrega:** para cada espécie, uma ficha validada (`species`) e até três documentos de busca com embedding (`species_retrieval_docs`), num MongoDB com busca vetorial.

**O que você precisa:**
- Docker, Python 3.13 e [Poetry](https://python-poetry.org/) 2.x;
- uma chave da [OpenAI](https://platform.openai.com/) (paga) e uma do [eBird](https://ebird.org/api/keygen) (gratuita);
- para o piloto: cerca de **US$ 0,35** e **até 1 dia**, quase todo de espera pelo lote da OpenAI. Você só digita uns 15 comandos.

---

## Início rápido

```bash
git clone https://github.com/rafaelladuarte/avesrag-dataset-builder.git
cd avesrag-dataset-builder

poetry install
poetry run playwright install chromium              # navegador do scraping do WikiAves

cp .env.example .env                                 # preencha OPENAI_API_KEY e EBIRD_API_KEY
docker compose up -d                                 # sobe o MongoDB (leva ~1 min na primeira vez)
poetry run avesrag-builder index --verificar         # deve terminar com "OK"
```

O `index --verificar` cria uma collection temporária, testa o `$vectorSearch` e o `$search` e apaga tudo. Se aparecer `OK`, o ambiente está pronto.

---

## Reconstruir o piloto do zero

O **piloto** são as espécies com registro no eBird em Uberlândia (MG): cerca de 440. Os comandos abaixo, nesta ordem, vão do banco vazio à busca pronta. Todos podem ser interrompidos e rodados de novo: cada etapa retoma de onde parou e não refaz o que já está pronto.

```bash
# 1. Planilhas de data/raw/ (sem rede)
poetry run avesrag-builder ingest cbro
poetry run avesrag-builder ingest ibge
poetry run avesrag-builder ingest birdbase
poetry run avesrag-builder ingest avonet

# 2. APIs e sites (o wikiaves por último: ele usa as três fontes anteriores)
poetry run avesrag-builder ingest birdalbum
poetry run avesrag-builder ingest ebird --piloto
poetry run avesrag-builder ingest wikiaves --piloto

# 3. Casamento das espécies entre as fontes
poetry run avesrag-builder resolve

# 4. Extração por LLM: envia um lote à OpenAI e espera o resultado
poetry run avesrag-builder extract --piloto

# 5. Ficha de cada espécie, data quality, documentos de busca e índices
poetry run avesrag-builder fuse --piloto
poetry run avesrag-builder validate --piloto
poetry run avesrag-builder docs --piloto
poetry run avesrag-builder index

# 6. Conferência
poetry run avesrag-builder status --piloto
poetry run avesrag-builder index --fumaca
```

Os passos 3 a 5 também rodam juntos com `poetry run avesrag-builder run --piloto`.

### Tempo e custo

| Etapa | Tempo | Custo |
| --- | --- | --- |
| `ingest` das 4 planilhas | ~1 min | — |
| `ingest birdalbum` | segundos (um CSV de 3,6 MB do GitHub) | — |
| `ingest ebird --piloto` | segundos | — |
| `ingest wikiaves --piloto` | ~50 min (437 páginas, ~7 s cada) | — |
| `resolve` | ~2 s | — |
| `extract --piloto` | **até 24 h** de espera do lote (9 h 40 min no desenvolvimento) | ~US$ 0,30 |
| `fuse`, `validate` | segundos | — |
| `docs --piloto` | ~1 min | ~US$ 0,01 |
| `index`, `index --fumaca` | ~1 min | < US$ 0,001 |

Os custos são da OpenAI: o `extract` usa o `gpt-6-luna` pela API de batch (metade do preço normal), e o `docs` usa o `text-embedding-3-large`. Cada comando que chama a API mostra no fim os tokens e o custo estimado.

### Enquanto o lote do `extract` roda

O `extract` envia ~1.300 pedidos num lote só e fica esperando, consultando a OpenAI a cada minuto. **Você pode fechar o terminal:** o lote continua na OpenAI e fica registrado no banco (`llm_batches`). Para ver se terminou, sem esperar:

```bash
poetry run avesrag-builder extract --piloto --sem-esperar   # coleta se estiver pronto; senão, só informa
poetry run avesrag-builder status --piloto                  # mostra "lote em andamento" no próximo passo
```

O lote nunca é enviado duas vezes. Não altere `config/prompts/`, `config/vocabulario.yaml` nem o `LLM_MODEL` enquanto ele roda: as respostas seriam descartadas e os pedidos, enviados (e pagos) de novo.

---

## Como saber se deu certo

O `status` mostra o estado de cada etapa e qual comando rodar em seguida. Ele só lê o banco e não precisa de chave de API.

```text
$ poetry run avesrag-builder status --piloto
raw_*: cbro 1971 · ibge 5572 · birdbase 11589 · avonet 33022 · ebird 1 município(s) · wikiaves 1975 (437 páginas)
species_registry: 1975 espécies; piloto 433 de 445 do eBird (97.3%)
species_extractions: 1299 de 1299 pares; 1293 válidas, 6 sem texto; 0 lote(s) aberto(s)
species: 433 fichas; apta 387 (89.4%), incompleta 46, bloqueada 0
species_retrieval_docs: 1156 documentos de 387 espécies; vetor_especies READY, texto_especies READY
próximo passo: nenhum, o escopo está completo
```

**Seus números não vão ser iguais a esses**, e isso é esperado: a lista do eBird de Uberlândia ganha registros novos, as páginas do WikiAves são editadas e as respostas do LLM variam um pouco entre execuções. O resultado está certo se cair nestas faixas:

| Item | No desenvolvimento (22/11/2026) | Esperado |
| --- | --- | --- |
| Espécies do piloto no registry | 433 de 445 (97,3%) | acima de 95% das espécies do eBird |
| Respostas válidas do LLM | 100% | ≥ 95% |
| Fichas `apta` | 89,4% | ≥ 80% |
| Fichas `bloqueada` | 0 | 0 |
| Documentos de busca | 1.156 | cerca de 3 por espécie apta |
| `index --fumaca` | 5 de 5 | 5 de 5 no top 10 |

O `index --fumaca` roda 5 descrições de teste ("bico enorme e colorido" → tucano, "ave enorme que corre no campo e não voa" → ema…) e diz em que posição a espécie esperada ficou. Se as faixas acima estiverem atendidas e uma consulta de fumaça falhar, o motivo é a variação do LLM nos textos de busca; o top 10 de cada consulta está em `reports/fumaca.tsv`.

---

## Como funciona

```text
fontes ──ingest──► raw_* ──resolve──► species_registry ──extract (LLM)──► species_extractions
                                                                                 │
   índices ◄──index── species_retrieval_docs ◄──docs── species ◄──fuse/validate──┘
```

O pipeline é uma sequência de comandos. Três regras valem para todos:

- **Cada etapa lê só das anteriores** e pode ser rodada sozinha.
- **Rodar de novo é seguro:** se nada mudou na fonte, nada é gravado e nada é pago de novo.
- **O LLM aparece só no `extract`.** O resto é determinístico e vem dos arquivos de `config/` (o `docs` só gera embeddings).

| Comando | O que faz | Grava em |
| --- | --- | --- |
| `ingest <fonte>` | baixa ou lê cada fonte | `raw_<fonte>` |
| `resolve` | casa as espécies entre as fontes | `species_registry` |
| `extract` | extrai atributos dos textos com LLM | `species_extractions` |
| `fuse` | junta tudo numa ficha por espécie | `species`, `species_occurrence` |
| `validate` | classifica as fichas em apta, incompleta ou bloqueada | `_meta.dq_status` |
| `docs` | gera os documentos de busca das espécies aptas | `species_retrieval_docs` |
| `index` | cria os índices de busca (`--fumaca` roda as consultas de teste) | índices do MongoDB |
| `status` | mostra o estado de cada etapa e o próximo passo | — |
| `run [--piloto]` | roda do `resolve` ao `index` | — |

Sem `--piloto`, as etapas cobrem as 1.975 espécies do WikiAves; o scraping completo leva ~4 h, e o `ebird` sem `--piloto` percorre todos os municípios (~1 a 2 h).

---

## Passo a passo por etapa

### 1. Ingestão

```bash
# Planilhas de data/raw/: sem rede, ~1 min no total
poetry run avesrag-builder ingest cbro
poetry run avesrag-builder ingest ibge
poetry run avesrag-builder ingest birdbase
poetry run avesrag-builder ingest avonet

# APIs e sites
poetry run avesrag-builder ingest birdalbum           # lista das ilustrações (1 download do GitHub)
poetry run avesrag-builder ingest ebird --piloto      # 3 chamadas à API
poetry run avesrag-builder ingest wikiaves --piloto   # ~50 min (~7 s por página)
```

**Rode o `wikiaves` por último:** ele usa o eBird para escolher as páginas e o BIRDBASE e o AVONET para casar os nomes.

<details>
<summary>Mais detalhes</summary>

- Cada fonte vira uma collection `raw_<fonte>` no formato `{_id, dados, ingerido_em, source_hash}`. O `_id` é a chave na fonte e `dados` é o registro como chegou. Um documento só é regravado quando o `source_hash` muda.
- O que cada fonte traz: CBRO, 1.971 espécies (id = #CBRO); IBGE, 5.572 municípios (id = geocódigo); BIRDBASE, 11.589 espécies (id = IOC 15.1); AVONET, as abas BirdLife e eBird e a correspondência entre elas; Bird Album, 11.011 espécies com ilustração (id = nome científico da AviList, num commit fixo do repositório: `BIRDALBUM_REF`).
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

A resposta segue um JSON Schema estrito, gerado do `config/vocabulario.yaml`. Cada valor vem com um trecho de evidência, e o builder confere esse trecho no texto original.

<details>
<summary>Mais detalhes</summary>

- **Cache:** um par espécie × prompt só vai ao LLM se o `input_hash` (modelo + prompt + entrada + schema) ou a `versao` do prompt mudou.
- **Falhas:** uma resposta inválida é refeita uma vez, por chamada direta. Se falhar de novo, fica gravada com `validacao.erro` e é tentada de novo na próxima execução. Espécie sem texto vira `sem_texto`, sem chamada ao LLM.
- **Relatório:** `reports/extract.tsv`, com uma linha por par. O terminal mostra um resumo com a taxa de respostas válidas, as evidências não encontradas, os tokens e o custo.
- O texto do WikiAves é tratado como dado, nunca como instrução: ele vai delimitado no prompt.

</details>

### 4. Fusão e validação

```bash
poetry run avesrag-builder fuse --piloto       # segundos, sem rede
poetry run avesrag-builder validate --piloto
```

O `fuse` monta uma ficha por espécie em `species`: cada campo vem de uma fonte definida (taxonomia do CBRO, IUCN do BIRDBASE, cores e marcas do `b01`, ambiente do AVONET + `b02`…), e a origem de cada campo fica em `_prov`. O `validate` classifica cada ficha:

- **`apta`:** tem tamanho, pelo menos 2 cores, tipo de bico, pelo menos 1 ambiente e o texto de aparência. Só as aptas viram documentos de busca.
- **`incompleta`:** falta algum desses itens (quase sempre cor, quando o texto do WikiAves é curto).
- **`bloqueada`:** falhou numa validação (valor fora do vocabulário, comprimento implausível, taxonomia incompleta…).

<details>
<summary>Mais detalhes</summary>

- Valores do `b01`/`b02` cuja evidência não foi encontrada no texto são descartados aqui.
- Reservas: sem comprimento, o tamanho sai da massa (BIRDBASE, depois AVONET); sem família na regra de bico, a dieta do AVONET e depois a do BIRDBASE; `onde_estava` e `grupo` sem valor no `b02` usam o AVONET e o BIRDBASE.
- `species_occurrence` guarda os municípios e biomas com registro de cada espécie no eBird.
- **Mídia:** `midia.foto` é a foto indicada do WikiAves; `midia.ilustracao` é uma ilustração do Bird Album, **gerada por IA**, com crédito e licença (CC BY 4.0). Ela é mídia secundária: serve de ilustração, nunca de confirmação da espécie, e o app deve exibi-la sempre com o rótulo de IA. O casamento é pelo código do eBird e, na falta dele, pelo nome científico.
- Rodar de novo não grava nada. Uma ficha que muda perde o `dq_status` até o próximo `validate`.
- Relatórios: `reports/fuse.tsv` (de onde veio cada campo) e `reports/validate.tsv` (o que falta em cada incompleta).

</details>

### 5. Documentos de busca e índices

```bash
poetry run avesrag-builder docs --piloto    # ~1 min, ~US$ 0,01 de embeddings
poetry run avesrag-builder index            # cria os índices e espera ficarem prontos
poetry run avesrag-builder index --fumaca   # 5 consultas de teste (centésimos de centavo)
```

Cada espécie apta ganha até três documentos (`aparencia`, `comportamento_ambiente`, `voz_habitos`) com o texto do `b03`, os filtros da ficha (cores, tamanho, bico, ambiente…) e o embedding. O `index` cria um índice vetorial (`vetor_especies`) e um de palavras-chave em português (`texto_especies`).

<details>
<summary>Mais detalhes</summary>

- O embedding só é gerado para texto novo ou alterado. Se só os filtros mudaram, ele é reaproveitado.
- Uma espécie que deixa de ser apta perde os documentos: a busca nunca devolve uma espécie que não passou na data quality.
- O texto não leva o nome da espécie, que fica num campo à parte (`nomes`), indexado só pelo `$search`.
- Na busca, cada espécie vale pela maior nota entre os seus documentos.
- As consultas de fumaça ficam em `config/consultas_fumaca.yaml`; o resultado vai para `reports/fumaca.tsv`.

</details>

---

## Problemas comuns

| Sintoma | O que fazer |
| --- | --- |
| `docker compose up` falha com porta em uso | outra aplicação usa a 27017: no `.env`, troque `MONGODB_PORT` e a porta do `MONGODB_URI` (ex.: 27018) e rode de novo |
| `index --verificar` falha ou demora | o MongoDB ainda está subindo: espere `docker compose ps` mostrar `healthy` |
| O MongoDB não volta depois de desligar | desligue sempre com `docker compose stop`, nunca `docker stop` (a imagem ignora o SIGTERM, e é o compose que faz o desligamento limpo) |
| `extract` parado em "em andamento" | normal: o lote leva até 24 h. Pode fechar o terminal e usar `extract --piloto --sem-esperar` depois |
| `playwright install` ou o `ingest wikiaves` reclamam de biblioteca do sistema | no Linux, rode `poetry run playwright install --with-deps chromium` (instala as dependências com `sudo`) |
| `ingest wikiaves` com erros ou bloqueio | rode de novo: ele retoma de onde parou. Se persistir, espere algumas horas |
| `Falhou: Defina OPENAI_API_KEY…` | a chave não está no `.env`; só os comandos que chamam a OpenAI cobram a chave |
| Parou no meio e não sei o que falta | `poetry run avesrag-builder status --piloto` mostra o próximo passo |

---

## Configuração

### Variáveis de ambiente

Só as chaves de API são obrigatórias, e cada uma só é cobrada pelo comando que a usa. O `--help`, o `status` e os testes rodam sem chave.

| Variável | Para quê |
| --- | --- |
| `OPENAI_API_KEY` | `extract`, `docs` (só quando há embedding a gerar) e `index --fumaca` |
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
| `EMBEDDING_PRECO` | `0.13` | US$ por milhão de tokens de embedding, para a estimativa de custo |
| `PILOTO_MUNICIPIO_IBGE` | `3170206` (Uberlândia, MG) | município do `--piloto` |
| `WIKIAVES_MAX_ESPECIES` | `0` (sem limite) | limite do scraping |
| `BIRDALBUM_REPO`, `BIRDALBUM_REF` | `alchaincyf/huashu-bird-sticker`, commit `fb4463b…` | repositório e commit fixo das ilustrações |
| `AVESRAG_LOG_FILE` | — | grava o log também neste arquivo |

</details>

### MongoDB

A imagem `mongodb/mongodb-atlas-local:8.3.17` traz o `mongod` e o `mongot` (o processo que atende `$vectorSearch` e `$search`). Ela roda como replica set de um nó, por isso a URI leva `?directConnection=true`. Para ver os dados, conecte o [MongoDB Compass](https://www.mongodb.com/products/tools/compass) na mesma URI.

### Vocabulário e regras

- `config/vocabulario.yaml` define os valores aceitos, os sinônimos e os mapeamentos AVONET/BIRDBASE → vocabulário.
- `config/regras_bico.yaml` define família → tipo de bico, dieta → tipo de bico e o perfil visual de cada tipo.
- `config/regras_fusao.yaml` define os cortes de tamanho (por comprimento e, na falta dele, por massa) e o que uma ficha precisa ter para ser `apta`.
- `config/regras_midia.yaml` define a foto de cada espécie: a ordem das fontes (iNaturalist do Brasil, Commons, iNaturalist de fora), as licenças aceitas (CC0, domínio público, CC BY e CC BY-SA; nada NC, ND ou GFDL), o modelo do crédito e como reconhecer, no Commons, uma ilustração ou um autor sem nome.

Os quatro se validam ao carregar. Um valor inexistente, um sinônimo ambíguo ou um tipo de bico sem perfil faz o carregamento falhar, indicando onde está o erro.

---

## Testes

```bash
poetry run pytest                    # unitários: sem .env, sem rede, sem MongoDB (também rodam no GitHub Actions)
poetry run pytest -m slow            # conferem os mapeamentos contra as planilhas de data/raw/
poetry run pytest -m integration     # precisam do MongoDB de pé (docker compose up -d)
poetry run ruff check src tests && poetry run ruff format --check src tests
```

Nenhum teste chama a OpenAI nem o eBird: os de integração usam fornecedores falsos num banco temporário.

---

## Estrutura

<details>
<summary>Ver a árvore de pastas</summary>

```text
config/
├── vocabulario.yaml      # valores aceitos, sinônimos e mapeamentos
├── regras_bico.yaml      # tipo de bico e perfil visual
├── regras_fusao.yaml     # cortes de tamanho e critérios de apta
├── regras_midia.yaml     # fontes, licenças e crédito da foto
├── consultas_fumaca.yaml # consultas de teste da busca (index --fumaca)
└── prompts/              # b01_aparencia, b02_comportamento, b03_textos_busca
src/avesrag_builder/
├── cli.py                # comando avesrag-builder
├── status.py             # estado de cada etapa e próximo passo
├── core/                 # settings, logging, modelos Pydantic, vocabulário e regras
├── db/                   # conexão, nomes das collections, verificação da busca
├── ingest/               # uma ingestão por fonte
├── resolve/              # species_registry
├── llm/                  # interface de fornecedor, adaptador OpenAI (chat, batch, embeddings) e prompts
├── extract/              # contratos, evidências e pipeline do extract
├── fuse/                 # regras por campo, species e species_occurrence
├── validate/             # validações, dq_status e relatório
└── docs/                 # documentos de busca, índices e consultas de fumaça
data/raw/                 # planilhas AVONET, BIRDBASE, CBRO, IBGE e lista do WikiAves
reports/                  # relatórios gerados (fora do git)
tests/
docs/legado/              # documentação e dados tratados da v1
```

</details>

---

## Fontes e licenças

| Fonte | Para quê | Arquivo em `data/raw/` | Licença |
| --- | --- | --- | --- |
| [WikiAves](https://www.wikiaves.com.br/) | universo de espécies; textos em português, nome comum e foto | `wikiaves_especies.csv` (lista de espécies) | termos do site; as páginas raspadas ficam só no seu MongoDB e não são redistribuídas |
| [CBRO 2021](https://doi.org/10.5281/zenodo.5138368) | lista e taxonomia oficiais das aves do Brasil (1.971 espécies) | `2021.07.26 CBRO 2021 Zenodo Release.xlsx` | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| [AVONET](https://doi.org/10.6084/m9.figshare.16586228) | medidas morfológicas, habitat, dieta e locomoção | `AVONET Supplementary dataset 1.xlsx` | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| [BIRDBASE v2025.1](https://doi.org/10.6084/m9.figshare.27051040) | nomes em 4 taxonomias (ponte para o eBird), IUCN 2024 e ecologia | `BIRDBASEv2025.1.xlsx` (no Figshare: `BIRDBASE v2025.1 Sekercioglu et al. Final.xlsx`) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| [IBGE](https://www.ibge.gov.br/geociencias/informacoes-ambientais/vegetacao/15842-biomas.html) | bioma predominante de cada município (2024) | `Bioma_Predominante_por_Municipio_2024.xlsx` | dados abertos ([Decreto nº 8.777/2016](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2016/decreto/d8777.htm)): uso livre, inclusive comercial, citando a fonte |
| [eBird](https://ebird.org/) | taxonomia (`speciesCode`) e espécies registradas por município | — (API, com a sua chave) | termos de uso da API do eBird |
| [Bird Album](https://birdalbum.com/) ([repositório](https://github.com/alchaincyf/huashu-bird-sticker)) | ilustração de cada espécie, **gerada por IA** (mídia secundária) | — (baixado do GitHub num commit fixo) | ilustrações [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); dados MIT |

**Citações** (exigidas pela CC BY):
- Pacheco, J. F. et al. (2021). Annotated checklist of the birds of Brazil by the Brazilian Ornithological Records Committee — second edition. *Ornithology Research* 29. Dados: [10.5281/zenodo.5138368](https://doi.org/10.5281/zenodo.5138368).
- Tobias, J. A. et al. (2022). AVONET: morphological, ecological and geographical data for all birds. *Ecology Letters* 25. Dados: [10.6084/m9.figshare.16586228](https://doi.org/10.6084/m9.figshare.16586228).
- Şekercioğlu, Ç. H. et al. (2025). BIRDBASE: a global dataset of avian biogeography, conservation, ecology and life history traits. *Scientific Data*. Dados: [10.6084/m9.figshare.27051040](https://doi.org/10.6084/m9.figshare.27051040).
- IBGE (2024). Bioma Predominante por Município para Fins Estatísticos. Os biomas de cada espécie em `species_occurrence` são elaboração própria a partir desses dados, cruzados com os registros do eBird.
- Ilustrações: "Bird stickers: huashu-bird-sticker by Huashu, CC BY 4.0", <https://github.com/alchaincyf/huashu-bird-sticker>. O crédito vai em cada ficha (`midia.ilustracao.credito` e `.link`).

A base gerada não é publicada: cada pessoa a reconstrói com as próprias chaves, porque ela contém trechos dos textos do WikiAves.

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

Código: [MIT](LICENSE). Os dados de `data/raw/` seguem as licenças das fontes (acima).
