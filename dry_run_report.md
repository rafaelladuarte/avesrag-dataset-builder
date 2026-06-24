# 🦜 Dry Run Report — avesrag-dataset-builder
**Função:** Engenheiro de Dados de Testes  
**Escopo:** `src/extractors/` e `src/database/conexoes.py`  
**Tipo:** Análise Estática + Simulação Lógica de Execução  

---

## 1. Arquitetura de Fluxo (Rastreio Global)

```
base.py (BaseExtractor)
  └── run(db_connection)
        ├── extract(*args, **kwargs)   ← entrada de dados brutos
        ├── transform(raw_data)        ← normalização / filtragem
        └── load(clean, db_connection) ← escrita em PostGIS ou MongoDB
```

### Mapeamento por Extrator

| Extrator | Entrada | Destino Final | Usa `run()` Base? |
|---|---|---|---|
| `GBIFExtractor` | API GBIF (REST, sem auth) | PostGIS `ocorrencias` | ❌ usa `run_for_species()` |
| `AvonetExtractor` | CSV local `AVONET_CSV` | MongoDB `especies` | ✅ com `run()` sobrescrito |
| `EbirdExtractor` | API eBird (`EBIRD_TOKEN`) | MongoDB `especies` | ✅ usa `run()` base |
| `SibbrExtractor` | API GBIF com `datasetKey` fixo | PostGIS `ocorrencias` | ❌ usa `run_for_species()` |
| `IUCNExtractor` | API IUCN (`IUCN_TOKEN`) | MongoDB `especies` | ❌ usa `run_for_species()` |
| `WorldclimExtractor` | .tif local + PostGIS (leitura) | MongoDB `especies` | ❌ usa `run_for_species()` |

---

## 2. Validação de Conexões (`conexoes.py`)

### 2.1 Variáveis de Ambiente Necessárias vs. Disponíveis

| Variável | Requerida por | Status no `.env` atual |
|---|---|---|
| `POSTGRES_URI` | `DatabaseConnection`, `WorldclimExtractor` | ❌ **AUSENTE** (usa fallback `localhost`) |
| `MONGODB_URI` | `DatabaseConnection` | ❌ **AUSENTE** (usa fallback `localhost`) |
| `IUCN_TOKEN` | `IUCNExtractor` | ❌ **AUSENTE** |
| `EBIRD_TOKEN` | `EbirdExtractor` | ❌ **AUSENTE** |
| `AVONET_CSV` | `AvonetExtractor` | ❌ **AUSENTE** (usa fallback `dados/AVONET_BirdLife.csv`) |
| `WORLDCLIM_DIR` | `WorldclimExtractor` | ❌ **AUSENTE** (usa fallback `dados/worldclim/`) |
| `GROQ_API_KEY` | (não encontrado nos extratores) | ✅ presente, mas **PONTO CEGO** — não é consumida por nenhum extrator analisado |

> **Avaliação:** O `.env` atual serve exclusivamente ao serviço de IA (GROQ). Nenhuma variável de banco ou de API de biodiversidade está configurada para execução local. Os fallbacks embutidos (`localhost`) só funcionariam se os contêineres Docker estivessem ativos e acessíveis na rede local.

### 2.2 Context Manager (`get_pg_connection`)

Implementação **correta**. O uso de `@contextmanager` garante fechamento automático via `finally`. Sem vazamentos de conexão detectados.

### 2.3 Singleton MongoDB (`_mongo_client`)

Implementação **funcional**, mas com **risco**: `_mongo_client` é uma variável de classe (`ClassVar`). Em execuções paralelas via Airflow com múltiplos workers, todas as instâncias de `DatabaseConnection` compartilharão o mesmo cliente Mongo. Isso pode ser intencional (pool único) ou problemático se os workers forem em processos separados (o singleton não é compartilhado entre processos).

---

## 3. Diagnóstico Detalhado por Extrator

---

### 🟢 GBIFExtractor — `gbif.py`

**Status: FUNCIONARIA hoje, com ressalvas**

**Parâmetros de busca (método `buscar_especies_brasil`):**
```python
{
  "classKey": 212,          # taxonKey para Aves
  "country": "BR",
  "hasCoordinate": "true",
  "hasGeospatialIssue": "false",
  "limit": 300,
  "offset": 0              # incrementado na paginação
}
```

**Parâmetros de busca (método `extract`):**
```python
{
  "scientificName": nome_cientifico,  # ex: "Ara ararauna"
  "country": "BR",
  "hasCoordinate": "true",
  "hasGeospatialIssue": "false",
  "limit": 200
}
```

**Output esperado antes do PostGIS:**
```python
[{
  "nome_cientifico": "Ara ararauna",
  "fonte": "gbif",
  "fonte_id": "123456789",
  "data_observacao": "2024-03-15",
  "municipio": "Uberlândia",
  "estado": "MG",         # ← fatia [:2] de "Minas Gerais"
  "altitude_m": 850.0,
  "instituicao": "INPA",
  "latitude": -18.91,
  "longitude": -48.27
}]
```

**⚠️ Pontos de Quebra:**
1. **`import pandas as pd` (linha 7) — PANDAS IMPORTADO, NÃO UTILIZADO.** Nenhum método do `GBIFExtractor` usa `pd`. Isso não quebra, mas é um import supérfluo que aumenta o tempo de carregamento do módulo.
2. **Assinatura de `transform` vs. `run()` base:** O método `transform` aceita `(self, raw_data, nome_cientifico=None)`, mas o `BaseExtractor.run()` chama `self.transform(raw_data)` — sem passar `nome_cientifico`. Isso significa que se alguém chamar `GBIFExtractor().run(db_conn, "Ara ararauna")`, o campo `nome_cientifico` ficará `None` e o dado gravado no PostGIS terá `nome_cientifico = "Unknown"`.
3. **Carga (PostGIS):** Se o Docker não estiver up, `pg_insert_ocorrencias` levantará `psycopg2.OperationalError` sem retry automático.

---

### 🟡 AvonetExtractor — `avonet.py`

**Status: NÃO FUNCIONARIA hoje (arquivo CSV ausente)**

**Parâmetros de entrada:**
- Caminho: `os.environ.get("AVONET_CSV", "dados/AVONET_BirdLife.csv")`
- O arquivo `dados/AVONET_BirdLife.csv` **não existe** no repositório (verificado na estrutura de diretórios).

**Simulação de execução:**
```
INFO     AvonetExtractor: Iniciando processo de Extração AVONET...
ERROR    AvonetExtractor: AVONET CSV não encontrado: dados/AVONET_BirdLife.csv
# → extract() retorna pd.DataFrame() vazio
# → transform() detecta df.empty e retorna []
# → load() recebe [] e retorna set() sem gravar nada
# PIPELINE TERMINA SEM ERRO EXPLÍCITO, MAS SEM DADOS
```

**Output esperado (quando o CSV existir):**
```python
# Documento MongoDB (por espécie)
{
  "nome_cientifico": "Ara ararauna",
  "familia": "Psittacidae",
  "ordem": "Psittaciformes",
  "bico_comprimento_culmen_mm": 38.2,
  "asa_comprimento_mm": 267.0,
  "massa_corporal_g": 1100.0,
  "nivel_trofico": "Herbivore",
  "migracao": 1,
  "fontes": ["avonet"],
  "atualizado_em": datetime(...),
  "wikiaves_url": "https://www.wikiaves.com.br/wiki/ara-ararauna"
}
```

**⚠️ Pontos de Quebra:**
1. **CSV ausente** — falha silenciosa (retorna `set()` vazio). O pipeline Airflow não levantaria erro, apenas logaria 0 espécies carregadas.
2. **Colunas ausentes no CSV:** O `rename` e depois `df[list(COLUNAS.values())]` levantará `KeyError` se o CSV não contiver todas as 20 colunas mapeadas em `COLUNAS`.

---

### 🔴 EbirdExtractor — `ebird.py`

**Status: NÃO FUNCIONARIA hoje (token ausente)**

**Simulação de execução:**
```
WARNING  EbirdExtractor: EBIRD_TOKEN não configurado.
# → extract() retorna {}
# → transform({}) retorna []
# → load([]) retorna None sem gravar
# PIPELINE TERMINA SILENCIOSAMENTE
```

**⚠️ Pontos de Quebra:**
1. **`EBIRD_TOKEN` ausente** — extrator é neutralizado. A verificação do token está corretamente no `extract()`, portanto há degradação segura (graceful degradation).
2. **PROBLEMA CRÍTICO DE DESIGN — API chamada dentro do `transform`:** O método `transform` faz **chamadas HTTP adicionais** para resolver os códigos eBird em nomes científicos. Isso viola o princípio de separação de responsabilidades do padrão ETL: `transform` deveria ser uma operação pura de dados, sem I/O. Isso causa:
   - Impossibilidade de testar o `transform` unitariamente sem mockar HTTP.
   - Timeout de rede mascarado dentro da fase de transformação.
3. **Dados SEM `upsert` explícito:** O `load` usa `update_one` sem `upsert=True`. Se a espécie ainda não existe no MongoDB (ex: eBird está rodando antes do AVONET), o `update_one` não cria o documento — os dados do eBird são perdidos silenciosamente.

---

### 🟢 SibbrExtractor — `sibbr.py`

**Status: FUNCIONARIA hoje (sem autenticação necessária)**

**Parâmetros de busca:**
```python
{
  "scientificName": nome_cientifico,
  "datasetKey": "4fa7b334-ce0d-4e88-aaae-2e0c138d049e",  # dataset SiBBr no GBIF
  "country": "BR",
  "hasCoordinate": "true",
  "limit": 100
}
```

**Output esperado antes do PostGIS:** Idêntico ao `GBIFExtractor`, com `"fonte": "sibbr"`.

**⚠️ Pontos de Quebra:**
1. **`nome_cientifico=None` no transform:** Se `run_for_species` for chamado sem `nome_cientifico`, `transform` receberá `None` para preencher o campo — e o PostGIS pode recusar o `INSERT` (coluna `NOT NULL`). Porém, o método exige o argumento, então isso só ocorreria via bug de chamada.
2. **Dependência do Docker (PostGIS):** Mesma restrição do GBIF — sem o contêiner ativo, falha na fase `load`.

---

### 🔴 IUCNExtractor — `iucn.py`

**Status: NÃO FUNCIONARIA hoje (token ausente)**

**Simulação de execução:**
```
WARNING  IUCNExtractor: IUCN_TOKEN não configurado.
# → extract() retorna None
# → transform(None) retorna None
# → load(None) retorna sem gravar
```

**⚠️ Pontos de Quebra:**
1. **`IUCN_TOKEN` ausente** — degradação segura, mesma situação do eBird.
2. **PROBLEMA CRÍTICO — `.pop()` em `load` mutando o dict original:**
   ```python
   # iucn.py linha 53
   nome_cientifico = transformed_data.pop("nome_cientifico")
   ```
   O `dict.pop()` **modifica o dicionário in-place**. Se o mesmo dicionário for referenciado em outro lugar (improvável aqui, mas é uma má prática), ele terá `nome_cientifico` removido. Prefira `transformed_data.get(...)` + construção de novo dict para o `$set`.
3. **Espécie precisa já existir no MongoDB:** Mesmo problema do eBird — `update_one` sem `upsert=True`. Se a espécie não foi previamente criada pelo AVONET, o enriquecimento IUCN é descartado.

---

### 🟡 WorldclimExtractor — `worldclim.py`

**Status: NÃO FUNCIONARIA hoje (arquivos .tif ausentes + Docker necessário)**

**Simulação de execução:**
```
WARNING  WorldclimExtractor: Diretório WorldClim não encontrado: dados/worldclim/
# → extract() retorna []
# → transform([]) retorna {}
# → load({}, ...) verifica `not transformed_data` → retorna sem gravar
```

**⚠️ Pontos de Quebra:**
1. **Arquivos `.tif` ausentes** — o diretório `dados/worldclim/` não existe localmente. Falha silenciosa.
2. **`rasterio` é importado de forma lazy (dentro do `transform`)** — correto para evitar `ImportError` em ambientes sem o pacote, mas o Poetry já instalou `rasterio`, então isso não seria um problema no ambiente atual.
3. **`extract` recebe `db_connection`** — única assinatura que diverge do padrão `BaseExtractor.extract(*args, **kwargs)`. O `run()` base **não funcionaria** para este extrator porque chama `self.extract(*args, **kwargs)` sem injetar `db_connection`. Por isso ele tem `run_for_species` próprio. **Arquitetura ok, mas a herança da interface não é 100% compatível.**

---

## 4. Status Report Consolidado

| Extrator | Executa Hoje? | Motivo Principal |
|---|---|---|
| **GBIF** | ✅ **SIM** (parcialmente) | API pública, sem autenticação. Requer Docker up para Load. |
| **SiBBr** | ✅ **SIM** (parcialmente) | Usa a API pública do GBIF com `datasetKey` fixo. Requer Docker up para Load. |
| **AVONET** | ❌ **NÃO** | CSV `AVONET_BirdLife.csv` não encontrado. Falha silenciosa. |
| **eBird** | ❌ **NÃO** | `EBIRD_TOKEN` ausente no `.env`. Falha silenciosa com warning. |
| **IUCN** | ❌ **NÃO** | `IUCN_TOKEN` ausente no `.env`. Falha silenciosa com warning. |
| **WorldClim** | ❌ **NÃO** | Arquivos `.tif` e diretório ausentes. Falha silenciosa com warning. |

---

## 5. Pontos Cegos (Blind Spots)

| # | Descrição |
|---|---|
| **PC-01** | `GROQ_API_KEY` presente no `.env` — nenhum módulo em `src/extractors` a consome. Provavelmente faz parte de um módulo RAG ainda não exposto para análise. |
| **PC-02** | A tabela `ocorrencias` e suas colunas no PostGIS não foram analisadas (`init_postgis.sql`). Se o schema não coincidir com os campos usados no `INSERT`, haverá erro de coluna desconhecida. |
| **PC-03** | Não há tratamento de retry em nenhum extrator HTTP. Uma falha de rede transitória aborta silenciosamente o registro específico. |
| **PC-04** | O `src/pipeline/` está vazio. Não há jobs centralizadores além da DAG. |

---

## 6. Bugs Confirmados (sem sugestão de correção)

| ID | Arquivo | Linha | Descrição |
|---|---|---|---|
| **BUG-01** | `gbif.py` | 7 | `import pandas as pd` não utilizado |
| **BUG-02** | `gbif.py` | 75 | `transform(raw_data, nome_cientifico=None)` ignorado pelo `run()` base → campo `nome_cientifico = "Unknown"` no PostGIS |
| **BUG-03** | `ebird.py` | 51-63 | Chamadas HTTP dentro de `transform()` violando separação ETL |
| **BUG-04** | `ebird.py` | 72 | `update_one` sem `upsert=True` — dados descartados se espécie não existe no Mongo |
| **BUG-05** | `iucn.py` | 53 | `dict.pop()` mutando o dicionário transformado in-place |
| **BUG-06** | `iucn.py` | 55 | `update_one` sem `upsert=True` — mesmo risco do eBird |
