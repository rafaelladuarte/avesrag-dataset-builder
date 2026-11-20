# Arquitetura do Pipeline de Prompts para Construção da Base Canônica de Espécies (PT-BR)

## Visão Geral

Este pipeline define uma arquitetura modular baseada em LLMs para construção de uma base canônica de espécies de aves a partir de textos descritivos (principalmente WikiAves), todos originalmente em português.

O objetivo é transformar dados textuais não estruturados em uma base estruturada, consistente e consultável, mantendo rastreabilidade completa das transformações.

A arquitetura é organizada como uma **DAG de enriquecimento semântico**, onde cada etapa produz um artefato intermediário persistente.

---

# Princípios da Arquitetura

* **Separação de responsabilidades por etapa**
* **Extração sem inferência na primeira camada**
* **Normalização antes de classificação**
* **Inferência baseada em múltiplas evidências**
* **Saída final totalmente padronizada em português**
* **Rastreabilidade completa dos dados**
* **Reprocessamento parcial do pipeline quando necessário**
* **Vocabulário controlado e consistente na base final**

---

# Visão Geral do Pipeline

```text id="ppl0v1"
ETAPA 1 — Extração (PT-BR)
        ↓
species_raw
        ↓
ETAPA 2 — Normalização (PT-BR)
        ↓
species_normalized
        ↓
ETAPA 3 — Classificação
        ↓
species_classified
        ↓
ETAPA 4 — Inferência
        ↓
species_inferred
        ↓
ETAPA 5 — Síntese
        ↓
canonical_species
        ↓
ETAPA 6 — Validação
```

---

# ETAPA 1 — Extração (PT-BR)

## Objetivo

Extrair informações explicitamente presentes nos textos de origem, sem qualquer interpretação, tradução ou normalização.

Esta etapa opera exclusivamente como um **extrator literal de fatos**.

---

## Entradas

Textos em português provenientes de fontes como:

* Seção de Características
* Seção de Alimentação
* Seção de Hábitos
* Seção de Reprodução

---

## Prompts

### P01 — Morfologia

## Entrada

Texto da seção de características da espécie.

## Saída

```json id="p01"
{
  "colors_raw": [],
  "body_parts_raw": [],
  "bill_description_raw": [],
  "wing_description_raw": [],
  "tail_description_raw": [],
  "size_description_raw": [],
  "measurements_raw": [],
  "sexual_dimorphism_raw": [],
  "juvenile_description_raw": [],
  "plumage_description_raw": [],
  "distinctive_features_raw": []
}
```

## Objetivo

Extrair descrições morfológicas explícitas sem inferência.

---

### P02 — Alimentação

## Entrada

Texto da seção de alimentação.

## Saída

```json id="p02"
{
  "food_items_raw": [],
  "feeding_behavior_raw": [],
  "feeding_locations_raw": []
}
```

## Objetivo

Extrair informações explícitas sobre dieta e comportamento alimentar.

---

### P03 — Hábitos

## Entrada

Texto da seção de hábitos/ecologia.

## Saída

```json id="p03"
{
  "habitats_raw": [],
  "activity_raw": [],
  "social_behavior_raw": [],
  "flight_behavior_raw": [],
  "vocalization_raw": []
}
```

## Objetivo

Extrair comportamento, habitat e ecologia sem interpretação.

---

### P04 — Reprodução

## Entrada

Texto da seção de reprodução.

## Saída

```json id="p04"
{
  "nest_raw": [],
  "courtship_raw": [],
  "clutch_raw": [],
  "incubation_raw": [],
  "fledging_raw": []
}
```

## Objetivo

Extrair dados reprodutivos explícitos.

---

## Artefato gerado

```text id="raw"
species_raw
```

### Características

* Dados literais
* Sem padronização
* Sem inferência
* Preserva ambiguidade original

---

# ETAPA 2 — Normalização (PT-BR)

## Objetivo

Padronizar linguagem, corrigir variações lexicais e estruturar os dados em formato consistente.

Nenhuma inferência é realizada.

---

## Prompts

### P05 — Normalização semântica

## Objetivo

Unificar sinônimos e expressões equivalentes em português.

## Exemplos

| Entrada            | Saída                    |
| ------------------ | ------------------------ |
| “pequenos insetos” | “invertebrados pequenos” |
| “frutinhos”        | “frutos”                 |
| “mata”             | “floresta”               |

---

### P06 — Padronização de medidas

## Objetivo

Padronizar medidas em formato estruturado.

## Exemplos

```json id="p06"
"11 cm" → {"value": 11, "unit": "cm"}

"10–12 cm" → {"min": 10, "max": 12, "unit": "cm"}
```

---

### P07 — Padronização taxonômica

## Objetivo

Garantir consistência em nomes científicos e categorias biológicas.

Exemplo:

* *Passeriformes*
* *Thraupidae*

---

### P08 — Estrutura canônica (PT-BR)

## Objetivo

Organizar os dados em uma estrutura padronizada da base final, já em português.

## Exemplos de normalização conceitual:

| Entrada     | Saída       |
| ----------- | ----------- |
| insectivore | insetívoro  |
| nectarivore | nectarívoro |
| forest      | floresta    |
| grassland   | campo       |

---

## Artefato gerado

```text id="norm"
species_normalized
```

### Características

* Linguagem padronizada (PT-BR)
* Estrutura consistente
* Sem inferência
* Base preparada para classificação

---

# ETAPA 3 — Classificação

## Objetivo

Associar atributos a categorias ecológicas pré-definidas.

Nesta etapa ocorre categorização estruturada.

---

## Saída

```text id="class"
species_classified
```

---

## Classificações

### Guilda alimentar

* insetívoro
* frugívoro
* nectarívoro
* onívoro

---

### Habitat

* floresta
* cerrado
* campo
* área úmida

---

### Estratégia de forrageamento

* catação
* captura em voo
* forrageamento no solo

---

### Padrão de atividade

* diurno
* noturno
* crepuscular

---

### Estrutura social

* solitário
* pares
* bandos

---

## Objetivo técnico

Transformar dados livres em categorias controladas.

---

# ETAPA 4 — Inferência

## Objetivo

Gerar atributos derivados a partir da combinação de múltiplas evidências.

Esta é a etapa mais dependente de raciocínio do modelo.

---

## Submódulos

### Bico

Inferência baseada em:

* dieta
* descrição morfológica
* medidas

---

### Asa

Inferência baseada em:

* envergadura
* tipo de voo
* comportamento

---

### Cauda

Inferência baseada em proporções e função.

---

### Coloração

Organização de padrões visuais.

---

### Características diagnósticas parciais

Atributos relevantes para diferenciação.

---

## Artefato gerado

```text id="inf"
species_inferred
```

---

# ETAPA 5 — Síntese

## Objetivo

Consolidar todos os dados em uma representação final coerente e utilizável.

---

## Saída

```text id="canon"
canonical_species
```

---

## Componentes

### Identificação

Descrição objetiva para uso em campo ou sistemas de busca.

---

### Descrição curta

Resumo da espécie em linguagem natural.

---

### Características diagnósticas finais

Atributos mais relevantes para diferenciação entre espécies similares.

---

## Objetivo técnico

Produzir a camada final consumível por sistemas de RAG e aplicações.

---

# ETAPA 6 — Validação

## Objetivo

Garantir consistência, coerência e qualidade dos dados gerados.

Esta etapa não gera novos dados, apenas analisa.

---

## Verificações

### Consistência lógica

Exemplo:

* dieta incompatível com guilda

---

### Campos ausentes

Identificação de lacunas importantes.

---

### Conflitos

Detecção de inconsistências entre atributos.

---

### Score de confiança

Estimativa de confiabilidade dos dados inferidos.

---

## Resultado

* Relatório de qualidade da espécie
* Lista de inconsistências
* Pontuação de confiança

---

# Resultado Final

Ao final do pipeline, cada espécie possui:

* `species_raw` (dados literais)
* `species_normalized` (dados padronizados em PT-BR)
* `species_classified` (categorias ecológicas)
* `species_inferred` (atributos derivados)
* `canonical_species` (representação final)
* relatório de validação

---

# Benefícios da Arquitetura

* Alta modularidade
* Baixa complexidade por prompt
* Reprocessamento parcial eficiente
* Forte consistência semântica
* Total padronização em português
* Escalabilidade para novas fontes
* Facilidade de debug e auditoria
* Independência de modelo LLM

---

# Conclusão

Esta arquitetura transforma o problema de extração e enriquecimento de espécies em um pipeline estruturado de engenharia de dados baseado em LLMs.

O uso de etapas isoladas reduz ambiguidade, melhora precisão e garante uma base canônica consistente, pronta para aplicações de RAG, identificação automática e análise ecológica.
