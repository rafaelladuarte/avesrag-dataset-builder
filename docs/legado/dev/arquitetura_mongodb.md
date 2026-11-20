# Arquitetura das Collections do MongoDB

## Sistema de Construção da Base Canônica de Espécies para RAG de Identificação de Aves Brasileiras

---

# 1. Objetivo

A arquitetura do banco de dados foi projetada seguindo os princípios de Engenharia de Dados para separar claramente:

* dados brutos provenientes das fontes originais;
* dados derivados obtidos por transformações determinísticas;
* dados canônicos enriquecidos por Inteligência Artificial;
* dados utilizados pelo sistema RAG.

Essa separação reduz acoplamento, facilita manutenção, aumenta a rastreabilidade do pipeline e permite reprocessamentos parciais quando novas versões das fontes ou dos prompts forem disponibilizadas.

---

# 2. Princípios da Arquitetura

O projeto segue cinco princípios fundamentais.

## 2.1 Fonte Única da Verdade (Single Source of Truth)

Cada collection possui responsabilidade única.

Nenhuma informação deve possuir duas fontes primárias.

Exemplos:

* medidas biométricas pertencem ao AVONET;
* descrições textuais pertencem ao WikiAves;
* distribuição geográfica pertence ao eBird.

A collection `canonical_species` nunca substitui essas bases.

Ela representa apenas a integração das informações.

---

## 2.2 Preservação dos Dados Originais

As collections de origem armazenam os dados exatamente como foram extraídos.

Não ocorre limpeza semântica durante a ingestão.

Isso permite:

* auditoria;
* reprocessamento;
* atualização das regras de transformação;
* reprodução do pipeline.

---

## 2.3 Transformações Determinísticas Sempre que Possível

Informações estruturadas não utilizam modelos de IA.

Exemplo:

AVONET

↓

massa corporal

↓

canonical_species.weight.mean

Esse processo ocorre por ETL convencional.

A utilização de LLM fica restrita à interpretação de texto livre.

---

## 2.4 IA Apenas para Extração Semântica

O modelo de linguagem não é utilizado para gerar conhecimento novo.

Sua função consiste em:

* interpretar textos;
* extrair informações;
* normalizar conceitos;
* estruturar os dados.

Assim, reduz-se significativamente o risco de alucinações.

---

## 2.5 Separação entre Conhecimento Estruturado e Conhecimento Semântico

A base canônica possui duas representações complementares.

Dados estruturados

* utilizados para consultas;
* filtros;
* inferências.

Texto canônico

* utilizado exclusivamente para geração dos embeddings.

---

# 3. Visão Geral da Arquitetura

```
                  FONTES

        WikiAves
        AVONET
        eBird
            │
            ▼

      Collections RAW
            │
            ▼

  Transformações Determinísticas
            │
            ▼

   Collections Derivadas
            │
            ▼

     Pipeline de Prompts
            │
            ▼

   canonical_species
            │
            ▼

      Texto Canônico
            │
            ▼

        Embeddings
            │
            ▼

        Sistema RAG
```

---

# 4. Collections do Sistema

## 4.1 wikiaves

### Responsabilidade

Armazenar os dados textuais extraídos do WikiAves sem modificações semânticas.

### Tipo

Raw Collection

### Origem

Crawler/Scraper

### Principais informações

* características
* alimentação
* hábitos
* reprodução
* classificação científica
* distribuição
* conservação
* nomes populares
* imagens
* metadados

### Utilização

Serve como principal fonte para os prompts responsáveis pela extração de conhecimento.

Nunca deve ser utilizada diretamente pelo sistema RAG.

### Exemplo

```json
{
  "_id": {
    "$oid": "6a3fea1efdd104ff0ef3aa4b"
  },
  "nome_cientifico": {
    "nome": "Tinamus major",
    "autoridade": "(Gmelin, 1789)"
  },
  "alimentacao": "Alimenta-se de vermes, insetos, sementes, brotos e frutos. inhambu-serra se alimentando",
  "atualizado_em": {
    "$date": "2026-06-27T11:30:08.953Z"
  },
  "caracteristicas": "Mede cerca de 41 centímetros e pesa 1,05 quilo. É ave cinegética (caçada). Muito arisca e sua plumagem apresenta excelente coloração de camuflagem. Na Região Norte do Brasil, divide seu hábitat com outras espécies do gênero Tinamus, como a azulona ( Tinamus tao ) e o macuquinho ou inhambu-galinha ( Tinamus guttatus ), o menor representante do gênero, sendo de maior ocorrência, nessa região, a subespécie Tinamus major olivascens . inhambu-serra adulto inhambu-serra jovem",
  "classificacao_cientifica": {
    "Reino": "Animalia",
    "Filo": "Chordata",
    "Classe": "Aves",
    "Ordem": "Tinamiformes",
    "Família": "Tinamidae",
    "Espécie": "T. major"
  },
  "distribuicao_geografica": "Amazonas, Pará e norte do Mato Grosso. Ocorre também do México à Bolívia. Ocorrências registradas no WikiAves",
  "estado_de_conservacao": "Quase Ameaçada",
  "fontes": [
    "wikiaves"
  ],
  "foto_mais_indicada": "https://s3.amazonaws.com/media.wikiaves.com.br/images/6781/1876087_191a674a79a538b59f322b7d307864b1.jpg",
  "galeria_fotos_primeiras_2": [
    "https://www.wikiaves.com.br/640317&t=s&s=10004",
    "https://www.wikiaves.com.br/236009&t=s&s=10004"
  ],
  "habitos": "É uma ave tinamiforme florestal, terrícola. Habita as matas de terra firme e várzeas.",
  "meta_id": "10004",
  "meta_nome_comum": "inhambu-serra",
  "nome_ingles": "Great Tinamou",
  "reproducao": "A espécie pratica a poligiandria, ou seja, um grupo de machos tem uma relação exclusiva com um grupo de fêmeas, e qualquer macho do grupo pode se acasalar com qualquer fêmea do grupo.\nUma vez fertilizada, a fêmea põe cerca de três ovos (arredondados de cor azul) em cinco ou seis dias. Os ovos são depositados sobre folhas ou entre raízes , sem proteção alguma, e a responsabilidade de chocá-los é transferida para o macho, que passa os próximos 17 dias chocando e tentando protegê-los. Casal de inhambu-serra Ninho de inhambu-serra Ovo de inhambu-serra Filhote de inhambu-serra"
}

```

---

## 4.2 avonet

### Responsabilidade

Armazenar atributos biométricos e ecológicos estruturados.

### Tipo

Raw Collection

### Principais informações

* massa corporal
* medidas do bico
* medidas da asa
* medidas da cauda
* tarso
* hand wing index
* kipps distance
* nicho trófico
* nível trófico
* estilo de vida
* migração
* habitat funcional

### Utilização

Esses dados são copiados diretamente para a base canônica por meio de transformações determinísticas.

Nenhum prompt de IA é utilizado para interpretar essas informações.

### Exemplo

```json
{
  "_id": {
    "$oid": "6a3fd6e7fdd104ff0ef39a56"
  },
  "nome_cientifico": "Pitangus sulphuratus",
  "area_distribuicao_km2": 16133982.75,
  "asa_comprimento_mm": 111.9,
  "atualizado_em": {
    "$date": "2026-06-27T10:57:47.518Z"
  },
  "bico_comprimento_culmen_mm": 29.3,
  "bico_comprimento_nares_mm": 21.1,
  "bico_largura_mm": 10.1,
  "bico_profundidade_mm": 9.1,
  "cauda_comprimento_mm": 84.8,
  "estilo_vida_primario": "Insessorial",
  "familia": "Tyrannidae",
  "fontes": [
    "avonet"
  ],
  "habitat_avonet": "Human Modified",
  "indice_asa_mao": 18.1,
  "kipps_distancia_mm": 20.6,
  "massa_corporal_g": 62.85,
  "migracao": 1,
  "nicho_trofico": "Omnivore",
  "nivel_trofico": "Carnivore",
  "ordem": "Passeriformes",
  "secundaria1_mm": 92.5,
  "tarso_comprimento_mm": 25.8
}
```

---

## 4.3 ebird

### Responsabilidade

Armazenar a ocorrência das espécies por localidade.

### Tipo

Raw Collection

### Organização

Cada documento representa uma região geográfica contendo todas as espécies registradas naquela localidade.

### Principais informações

* município
* estado
* bioma
* código eBird
* lista de espécies

### Utilização

Essa collection não alimenta diretamente a canonical_species.

Ela é utilizada para construir uma coleção derivada de ocorrência.

### Exemplo

```json
{
  "_id": {
    "$oid": "6a40285dfdd104ff0ef429f1"
  },
  "geocodigo": "1200385",
  "bioma": "Amazônia",
  "ebird_code": "BR-AC-013",
  "ebird_name": "Plácido de Castro",
  "especies": [
    {
      "speciesCode": "undtin1",
      "comName": "Undulated Tinamou",
      "sciName": "Crypturellus undulatus",
      "order": "Tinamiformes",
      "familyComName": "Tinamous",
      "familySciName": "Tinamidae",
      "category": "species"
    },
    {
      "speciesCode": "categr1",
      "comName": "Western Cattle-Egret",
      "sciName": "Ardea ibis",
      "order": "Pelecaniformes",
      "familyComName": "Herons, Egrets, and Bitterns",
      "familySciName": "Ardeidae",
      "category": "species"
    },
    {
      "speciesCode": "blkvul",
      "comName": "Black Vulture",
      "sciName": "Coragyps atratus",
      "order": "Cathartiformes",
      "familyComName": "New World Vultures",
      "familySciName": "Cathartidae",
      "category": "species"
    },
    {
      "speciesCode": "roahaw",
      "comName": "Roadside Hawk",
      "sciName": "Rupornis magnirostris",
      "order": "Accipitriformes",
      "familyComName": "Hawks, Eagles, and Kites",
      "familySciName": "Accipitridae",
      "category": "species"
    },
    {
      "speciesCode": "fepowl",
      "comName": "Ferruginous Pygmy-Owl",
      "sciName": "Glaucidium brasilianum",
      "order": "Strigiformes",
      "familyComName": "Owls",
      "familySciName": "Strigidae",
      "category": "species"
    },
    {
      "speciesCode": "cheara1",
      "comName": "Chestnut-eared Aracari",
      "sciName": "Pteroglossus castanotis",
      "order": "Piciformes",
      "familyComName": "Toucans",
      "familySciName": "Ramphastidae",
      "category": "species"
    },
    {
      "speciesCode": "blhpar1",
      "comName": "Blue-headed Parrot",
      "sciName": "Pionus menstruus",
      "order": "Psittaciformes",
      "familyComName": "New World and African Parrots",
      "familySciName": "Psittacidae",
      "category": "species"
    },
    {
      "speciesCode": "trokin",
      "comName": "Tropical Kingbird",
      "sciName": "Tyrannus melancholicus",
      "order": "Passeriformes",
      "familyComName": "Tyrant Flycatchers",
      "familySciName": "Tyrannidae",
      "category": "species"
    },
    {
      "speciesCode": "brcmar1",
      "comName": "Brown-chested Martin",
      "sciName": "Progne tapera",
      "order": "Passeriformes",
      "familyComName": "Swallows",
      "familySciName": "Hirundinidae",
      "category": "species"
    },
    {
      "speciesCode": "puteup1",
      "comName": "Purple-throated Euphonia",
      "sciName": "Euphonia chlorotica",
      "order": "Passeriformes",
      "familyComName": "Finches, Euphonias, and Allies",
      "familySciName": "Fringillidae",
      "category": "species"
    },
    {
      "speciesCode": "yebspa1",
      "comName": "Yellow-browed Sparrow",
      "sciName": "Ammodramus aurifrons",
      "order": "Passeriformes",
      "familyComName": "New World Sparrows",
      "familySciName": "Passerellidae",
      "category": "species"
    },
    {
      "speciesCode": "sibtan2",
      "comName": "Silver-beaked Tanager",
      "sciName": "Ramphocelus carbo",
      "order": "Passeriformes",
      "familyComName": "Tanagers and Allies",
      "familySciName": "Thraupidae",
      "category": "species"
    },
    {
      "speciesCode": "blbgra1",
      "comName": "Blue-black Grassquit",
      "sciName": "Volatinia jacarina",
      "order": "Passeriformes",
      "familyComName": "Tanagers and Allies",
      "familySciName": "Thraupidae",
      "category": "species"
    }
  ],
  "match_type": "exact",
  "nome": "Plácido de Castro",
  "total_especies": 13,
  "uf": "AC"
}
```

---

## 4.4 ocorrencias_especies

### Responsabilidade

Inverter a estrutura do eBird.

Enquanto o eBird responde:

> Quais espécies existem neste município?

A collection species_occurrence responde:

> Em quais localidades ocorre esta espécie?

### Tipo

Derived Collection

### Construção

ETL determinístico.

Sem utilização de LLM.

### Informações

* estados
* municípios
* países
* biomas
* regiões eBird
* estatísticas de ocorrência

Essa collection simplifica o merge com a canonical_species.

### Exemplo

```json
{
  "nome_cientifico": "Pitangus sulphuratus",
  "paises": ["Brasil"],
  "estados": ["AC", "AM", "SP"],
  "municipios": [
    { "geocodigo": "1200385", "nome": "Plácido de Castro", "uf": "AC" }
  ],
  "biomas": ["Amazônia", "Mata Atlântica"],
  "contagem_ocorrencias": 1842
}

```

---

## 4.5 canonical_species

### Responsabilidade

Representar o documento canônico de cada espécie.

Essa collection constitui a principal fonte de conhecimento utilizada pelo sistema.

### Tipo

Canonical Collection

### Origem

Merge entre:

* WikiAves
* AVONET
* species_occurrence

Mais informações inferidas e normalizadas pelos prompts.

### Características

* informações estruturadas;
* dados normalizados;
* rastreabilidade das fontes;
* textos canônicos para RAG.

Essa collection representa a Single Source of Truth do sistema.

---

# 5. Relacionamento entre Collections

```
                 WikiAves
                      │
                      │
                      ▼

                 canonical_species

                      ▲
                      │

                 AVONET

                      ▲
                      │

           species_occurrence

                      ▲
                      │

                   eBird
```

Não existem relacionamentos físicos entre documentos.

Todos os relacionamentos são realizados pelo campo:

```
scientific_name
```

---

# 6. Fluxo de Dados

## Etapa 1

Extração das fontes.

↓

Collections RAW.

---

## Etapa 2

Transformações determinísticas.

* AVONET → canonical
* eBird → species_occurrence

---

## Etapa 3

Pipeline de IA.

Os textos do WikiAves passam por uma sequência de prompts especializados responsáveis por:

* morfologia;
* alimentação;
* comportamento;
* reprodução;
* habitat;
* identificação;
* texto canônico.

---

## Etapa 4

Merge final.

Todas as informações produzidas são consolidadas na canonical_species.

---

## Etapa 5

Construção do RAG.

A partir da canonical_species são gerados:

* texto canônico;
* embedding;
* índices vetoriais.

---

# 7. Estratégia de Atualização

Cada collection pode ser atualizada independentemente.

Exemplos:

* nova versão do AVONET;
* atualização do WikiAves;
* novos registros do eBird;
* melhoria em um prompt específico.

O pipeline permite reprocessar apenas a etapa afetada, preservando as demais informações.

---

# 8. Benefícios da Arquitetura

A arquitetura proposta apresenta diversas vantagens.

## Modularidade

Cada collection possui responsabilidade única.

---

## Escalabilidade

Novas fontes podem ser incorporadas sem alterar a estrutura existente.

---

## Rastreabilidade

Toda informação possui origem conhecida.

---

## Reprodutibilidade

O pipeline pode ser executado novamente produzindo os mesmos resultados.

---

## Baixo Acoplamento

Alterações em uma fonte não impactam diretamente as demais.

---

## Eficiência

A utilização de IA fica restrita apenas às tarefas que realmente exigem interpretação semântica.

Transformações estruturadas continuam sendo realizadas por ETL determinístico, reduzindo custo computacional e aumentando a confiabilidade do processo.
