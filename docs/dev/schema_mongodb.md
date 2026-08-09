# Estrutura do Banco de Dados MongoDB - `avesrag`

Este documento fornece um resumo detalhado e estruturado do esquema (schema) das collections utilizadas no banco de dados MongoDB `avesrag`. Com base no código-fonte, mapeamos três collections principais responsáveis pela ingestão de dados brutos (`avonet`, `wikiaves`, `ebird`) e uma collection para consolidação (`especies`).

## Resumo das Collections

### 1. Collection: `avonet`
Armazena dados morfológicos, ecológicos e geográficos das espécies, oriundos do dataset AVONET.
- `nome_cientifico`: String (Identificador principal)
- `familia`: String
- `ordem`: String
- `bico_comprimento_culmen_mm`: Float
- `bico_comprimento_nares_mm`: Float
- `bico_largura_mm`: Float
- `bico_profundidade_mm`: Float
- `tarso_comprimento_mm`: Float
- `asa_comprimento_mm`: Float
- `kipps_distancia_mm`: Float
- `secundaria1_mm`: Float
- `indice_asa_mao`: Float
- `cauda_comprimento_mm`: Float
- `massa_corporal_g`: Float
- `habitat_avonet`: String
- `nivel_trofico`: String
- `nicho_trofico`: String
- `estilo_vida_primario`: String
- `migracao`: String
- `area_distribuicao_km2`: Float
- `fontes`: Array de Strings (Ex: `["avonet"]`)
- `atualizado_em`: Date


#### Exemplo documento
```
{
  "_id": {
    "$oid": "6a3fd6edfdd104ff0ef3a193"
  },
  "nome_cientifico": "Rhea americana",
  "area_distribuicao_km2": 6537549.66,
  "asa_comprimento_mm": 604.5,
  "atualizado_em": {
    "$date": "2026-08-08T15:48:27.491Z"
  },
  "bico_comprimento_culmen_mm": 86.5,
  "bico_comprimento_nares_mm": 35.6,
  "bico_largura_mm": 27.2,
  "bico_profundidade_mm": 17.2,
  "cauda_comprimento_mm": 62,
  "estilo_vida_primario": "Terrestrial",
  "familia": "Rheidae",
  "fontes": [
    "avonet"
  ],
  "habitat_avonet": "Grassland",
  "indice_asa_mao": 0.1,
  "kipps_distancia_mm": 0.3,
  "massa_corporal_g": 23000,
  "migracao": 1,
  "nicho_trofico": "Omnivore",
  "nivel_trofico": "Omnivore",
  "ordem": "Struthioniformes",
  "secundaria1_mm": 604.2,
  "tarso_comprimento_mm": 308
}
```

### 2. Collection: `wikiaves`
Armazena informações descritivas, taxonômicas, metadados de mídia e características comportamentais extraídas da WikiAves.
- `nome_cientifico`: String (ou Objeto contendo `nome` e `autoridade`)
- `meta_id`: String
- `meta_nome_comum`: String
- `classificacao_cientifica`: Objeto (Chave-Valor com a taxonomia)
- `nome_ingles`: String
- `estado_de_conservacao`: String
- `foto_mais_indicada`: String (URL)
- `caracteristicas`: String
- `alimentacao`: String
- `reproducao`: String
- `habitos`: String
- `distribuicao_geografica`: String
- `galeria_fotos_primeiras_2`: Array de Strings (URLs)
- `fontes`: Array de Strings (Ex: `["wikiaves"]`)
- `atualizado_em`: Date
- `_pipeline_processed`: Boolean (True após o enriquecimento no fluxo do pipeline)

**Campos Adicionais pós-processamento (_pipeline_processed: true):**
- `canonical_species`: Objeto
  - `identificacao`: String
  - `descricao_curta`: String
  - `caracteristicas_diagnosticas`: Array de Strings
  - `_audit`: Objeto
- `species_normalized`: Objeto
  - `semantica`: Objeto contendo múltiplos Arrays de Strings (Ex: `cores`, `partes_corpo`, `comportamento_alimentar`) e `_audit`.
  - `medidas`: Objeto contendo Array de Objetos em `measurements` (cada um com `value`, `min_value`, `max_value`, `unit`) e `_audit`.
  - `taxonomia`: Objeto contendo campos taxonômicos (`reino`, `filo`, etc.) e `_audit`.
- `species_raw`: Objeto
  - `morfologia`: Objeto contendo múltiplos Arrays de Strings brutos (Ex: `colors_raw`, `body_parts_raw`) e `_audit`.
  - `alimentacao`: Objeto contendo múltiplos Arrays de Strings brutos e `_audit`.
  - `habitos`: Objeto contendo múltiplos Arrays de Strings brutos e `_audit`.
  - `reproducao`: Objeto contendo múltiplos Arrays de Strings brutos e `_audit`.

#### Exemplo documento

```
{
  "_id": {
    "$oid": "6a3fea1efdd104ff0ef3aa48"
  },
  "nome_cientifico": {
    "nome": "Rhea americana",
    "autoridade": "(Linnaeus, 1758)"
  },
  "alimentacao": "É onívora, comendo folhas, inclusive as espinhosas e ardidas, frutas, sementes, insetos, principalmente gafanhotos, ..."
  "atualizado_em": {
    "$date": "2026-06-27T11:29:51.299Z"
  },
  "caracteristicas": "134 – 170 cm de altura, dependendo da postura adotada; o macho atinge 34,4 kg e a fêmea 32 kg. É a maior e mais pesada ave brasileira. Tem cor predominantemente cinza, sendo o macho um pouco mais escuro, e tem a base do pescoço, peito anterior e parte ...",
  "classificacao_cientifica": {
    "Reino": "Animalia",
    "Filo": "Chordata",
    "Classe": "Aves",
    "Ordem": "Rheiformes",
    "Família": "Rheidae",
    "Espécie": "R. americana"
  },
  "distribuicao_geografica": "R (Comitê Brasileiro de Registros Ornitológicos) No Brasil, ocorre no Centro-Oeste, Sul e Nordeste, muito comum em áreas de Cerrado e Pampa...",
  "estado_de_conservacao": "Quase Ameaçada",
  "fontes": [
    "wikiaves"
  ],
  "foto_mais_indicada": "https://s3.amazonaws.com/media.wikiaves.com.br/images/8002/2008255_3d89225e3d49a3d0283b1dec851fe204.jpg",
  "galeria_fotos_primeiras_2": [
    "https://www.wikiaves.com.br/169660&t=s&s=10001",
    "https://www.wikiaves.com.br/427364&t=s&s=10001"
  ],
  "habitos": "A ema é uma ave corredora que ocorre em paisagens abertas da América do Sul, do Brasil até o sul da Argentina. Vive em campos naturais, cerrados e áreas de uso agropecuário ...",
  "meta_id": "10001",
  "meta_nome_comum": "ema",
  "nome_ingles": "Greater Rhea",
  "reproducao": "A ema só vocaliza na época do acasalamento, quando o macho produz um som profundo e potente, ouvido de longe, quase como o mugido de um grande mamífero...",
  "_pipeline_processed": true,
  "canonical_species": {
    "identificacao": "Rhea americana",
    "descricao_curta": "Maior e mais pesada ave brasileira, não voadora, de hábitos gregários e adaptada a paisagens abertas.",
    "caracteristicas_diagnosticas": [
      "cor predominantemente cinza",
      "está entre as poucas aves que não possuem glândulas uropigianas",
      "separação de fezes e urina, ao contrário das outras aves",
      "três dedos, adaptados a sua vida terrestre",
      "Não possui quilha, como as restantes aves, estando o esterno transformado numa placa óssea achatada",
      "Falta inteiramente a cauda e o pigostilo"
    ],
    "_audit": {
      "prompt_name": "P08_Estrutura_Canonica",
      "prompt_version": "1.0",
      "model_name": "gemini-3.5-flash-lite",
      "timestamp": "2026-08-09T18:23:10.663535+00:00"
    }
  },
  "species_normalized": {
    "semantica": {
      "cores": [
        "cinza",
        "negros",
        "cinza-pardacento",
        "cinzentas",
        "preto",
        "branco",
        "marrom",
        "castanho-amarelado",
        "marrom-acinzentada",
        "marrom-escuras",
        "pretas",
        "esbranquiçado",
        "esbranquiçadas",
        "quase totalmente pretos",
        "amarelo-claros",
        "fuliginosa",
        "acinzentada",
        "marrom-escuro",
        "amarelo-claro",
        "marrom-escura",
        "laranja-canela"
      ],
      "partes_corpo": [
        "pescoço",
        "peito anterior",
        "dorso anterior",
        "cabeça",
        "penas laterais",
        "dorso",
        "corpo",
        "traseiro",
        "cauda",
        "pigostilo",
        "glândulas uropigianas",
        "cloaca",
        "pênis",
        "pele facial",
        "íris",
        "dedos",
        "Tarso",
        "dedos dos pés",
        "esterno",
        "ratis",
        "pernas",
        "alula",
        "partes superiores",
        "coroa",
        "nuca",
        "costas",
        "partes inferiores",
        "região interescapular",
        "barriga"
      ],
      "descricao_bico": [
        "bico chato e castanho-amarelado, semelhante ao dos patos"
      ],
      "descricao_asas": [
        "macias e cinzentas penas das asas (incluindo as “plumas”, que correspondem às rêmiges nas outra aves) se dirigem obliquamente de cima para baixo, formando um manto que se eleva em uma corcova dorsal",
        "garra substancial nas asas (formada pela ponta da alula, que é cornificada)"
      ],
      "descricao_cauda": [
        "Falta inteiramente a cauda e o pigostilo"
      ],
      "descricao_tamanho": [
        "134 – 170 cm de altura",
        "maior e mais pesada ave brasileira",
        "cabeça pequena",
        "muito grande",
        "pescoço e tarsos longos",
        "menor que o macho"
      ],
      "medidas": [
        "134 – 170 cm de altura",
        "34,4 kg",
        "32 kg"
      ],
      "dimorfismo_sexual": [
        "o macho atinge 34,4 kg e a fêmea 32 kg",
        "macho um pouco mais escuro",
        "O macho adulto possui um grande pênis",
        "O macho, além de ser mais robusto, tiene a cabeça mais perfilada e tem o pescoço e as pernas mais grossos",
        "Fêmea: menor que o macho e menos escuro, mas os sexos são muito semelhantes"
      ],
      "descricao_juvenil": [],
      "descricao_plumagem": [
        "cor predominantemente cinza",
        "base do pescoço recoberta por um tufo de penas laterais cinzentas",
        "curtas penas piliformes",
        "mancha escura",
        "todo o comprimento do tarso é recoberto com escamas transversais",
        "A plumagem das partes superiores é geralmente cinza ou marrom-acinzentada",
        "A coroa, nuca, base do pescoço e parte superior das costas são geralmente marrom-escuras ou pretas",
        "o pescoço às vezes é extensamente esbranquiçado e aparece inchado em machos reprodutores",
        "Indivíduos inteiramente brancos não são incomuns"
      ],
      "caracteristicas_distintivas": [
        "está entre as poucas aves que não possuem glândulas uropigianas",
        "separação de fezes e urina, ao contrário das outras aves",
        "três dedos, adaptados a sua vida terrestre",
        "Não possui quilha, como as restantes aves, estando o esterno transformado numa placa óssea achatada"
      ],
      "itens_alimentares": [
        "folhas",
        "inclusive as espinhosas e ardidas",
        "frutos",
        "sementes",
        "insetos",
        "principalmente gafanhotos",
        "moluscos",
        "carne em putrefação",
        "pequenos animais",
        "lagartixas",
        "pequenos roedores",
        "rãs",
        "cobras",
        "coquinhos caídos",
        "animais moribundos",
        "pedrinhas",
        "qualquer coisa que a auxilie na trituração dos alimentos"
      ],
      "comportamento_alimentar": [
        "caça moscas procurando-as",
        "ingere pedrinhas ou qualquer coisa que a auxilie na trituração dos alimentos",
        "Forrageia caminhando lentamente, mantendo a cabeça abaixo de 50 cm do solo, interrompida por ocasionais ataques de vigilância em que levanta a cabeça e esquadrinha a área",
        "Com o pescoço curvado em U, move-se lentamente, explorando para cima e para baixo, ou de um lado para o outro, com pequenos movimentos da cabeça",
        "pega-o com a ponta de seu bico, joga a cabeça alguns centímetros para trás, joga o alimento no ar e pega-o na parte de trás da boca com um impulso para a frente da abertura do bico",
        "ema se alimentando"
      ],
      "locais_alimentacao": [
        "perto de carne em putrefação",
        "ao seu alcance",
        "queimadas"
      ],
      "habitats": [
        "paisagens abertas da América do Sul, do Brasil até o sul da Argentina",
        "campos naturais",
        "cerrados",
        "áreas de uso agropecuário",
        "campos",
        "pampas",
        "plantações",
        "savanas de cupins",
        "varjões com buritirana no sudeste do Pará",
        "próximo da orla marítima nos campos litorâneos",
        "brejos"
      ],
      "atividade": [
        "passa o dia dormindo e sai à noite para alimentar-se",
        "Quando faz muito calor, ofega de bico meio aberto",
        "gosta de tomar banho entrando nos brejos e atravessando rios a nado"
      ],
      "comportamento_social": [
        "Vive em bandos e procura a companhia de ovelhas, vacas e veados campeiros",
        "sedentária e gregária",
        "não se forme bandos numerosos, de várias famílias",
        "podem formar-se grupos de 20 a 30 animais, ou mesmo 100 indivíduos",
        "Um macho pode lutar com outro macho para tomar-lhe as suas fêmeas e até mesmo suas crias"
      ],
      "comportamento_voo": [
        "Ela não voa, e usa suas grandes asas para equilibrar-se e mudar de direção ao correr",
        "afasta-se de repente num ziguezague ligeiro, erguendo as asas e inflando a plumagem",
        "foge a grande velocidade dando passos de um metro e meio, podendo atingir mais de 60 km por hora",
        "Corre executando ziguezagues controlados pelas asas, que são abaixadas e levantadas alternadamente",
        "Andando tranquilamente, movimenta as asas ritmicamente"
      ],
      "vocalizacao": [
        "A ema só vocaliza na época do acasalamento",
        "o macho emite um urro forte, produzindo um som profundo e potente, ouvido de longe, ventríloquo, bissilábco: “bu-úp” (“nan-dú”), lembrando o bramido de um boi",
        "Urra até mesmo à noite",
        "Alarme: grasnido rouco",
        "Os filhotes extraviados emitem assobios melodiosos, lembrando o canto do inhambu-relógio (Crypturellus strigulosus), que o pai responde com leve estalo de bico"
      ],
      "ninho": [
        "faz o ninho",
        "É o macho que constrói o ninho, escavando uma depressão pouco profunda, revestida por vegetação seca e geralmente abrigada na vegetação."
      ],
      "cortejo": [
        "Na época do acasalamento, o macho abre as asas e dá os seus passos de dança.",
        "Na disputa entre os machos destacam-se as vocalizações, os saltos, as exibições das asas e do pescoço, ataques e expulsões.",
        "Fazem a corte à fêmea esticando as asas horizontalmente; correm fazendo roda, abrindo e agitando as asas, executando uma exibição arrebatadora que chega a confundir o espectador pela exuberância das plumas macias eriçadas que a mais leve brisa faz tremular."
      ],
      "ninhada": [
        "Cada ninho conta com geralmente 20 a 30 ovos, postos por várias fêmeas diferentes, que botam em cada ninho de 4 a 5 ovos."
      ],
      "incubacao": [
        "O choco é de responsabilidade do macho",
        "A incubação começa 5 a 8 dias após as fêmeas terem iniciado a postura (o que implica em períodos de incubação com até 12 dias de diferença) e pode durar de 27 a 41 dias."
      ],
      "periodo_filhotes": [
        "Com 6 meses de vida, os filhotes já estão fortes e quase do tamanho de uma fêmea.",
        "As crias são nidífugas, isto é, abandonam o ninho precocemente, neste caso, com poucos dias de idade.",
        "Com duas semanas de idade, as eminhas alcançam meio metro de altura, sem contar o pescoço."
      ],
      "_audit": {
        "prompt_name": "P05_Normalizacao_Semantica",
        "prompt_version": "2.0",
        "model_name": "gemini-3.5-flash-lite",
        "timestamp": "2026-08-09T18:22:49.062225+00:00"
      }
    },
    "medidas": {
      "measurements": [
        {
          "value": null,
          "min_value": 134,
          "max_value": 170,
          "unit": "cm"
        },
        {
          "value": 34.4,
          "min_value": null,
          "max_value": null,
          "unit": "kg"
        },
        {
          "value": 32,
          "min_value": null,
          "max_value": null,
          "unit": "kg"
        }
      ],
      "_audit": {
        "prompt_name": "P06_Padronizacao_Medidas",
        "prompt_version": "1.0",
        "model_name": "gemini-3.5-flash-lite",
        "timestamp": "2026-08-09T18:22:56.124776+00:00"
      }
    },
    "taxonomia": {
      "reino": "Animalia",
      "filo": "Chordata",
      "classe": "Aves",
      "ordem": "Rheiformes",
      "familia": "Rheidae",
      "genero": "Rhea",
      "especie": "Rhea americana",
      "_audit": {
        "prompt_name": "P07_Padronizacao_Taxonomica",
        "prompt_version": "1.0",
        "model_name": "gemini-3.5-flash-lite",
        "timestamp": "2026-08-09T18:23:03.085277+00:00"
      }
    }
  },
  "species_raw": {
    "morfologia": {
      "colors_raw": [
        "cinza",
        "negros",
        "cinza-pardacento",
        "cinzentas",
        "preto",
        "branco",
        "marrom",
        "castanho-amarelado",
        "marrom-acinzentada",
        "marrom-escuras",
        "pretas",
        "esbranquiçado",
        "esbranquiçadas",
        "quase totalmente pretos",
        "amarelo-claros",
        "fuliginosa",
        "acinzentada",
        "marrom-escuro",
        "amarelo-claro",
        "marrom-escura",
        "laranja-canela"
      ],
      "body_parts_raw": [
        "pescoço",
        "peito anterior",
        "dorso anterior",
        "cabeça",
        "penas laterais",
        "dorso",
        "corpo",
        "traseiro",
        "cauda",
        "pigostilo",
        "glândulas uropigianas",
        "cloaca",
        "pênis",
        "pele facial",
        "íris",
        "dedos",
        "Tarso",
        "dedos dos pés",
        "esterno",
        "ratis",
        "pernas",
        "alula",
        "partes superiores",
        "coroa",
        "nuca",
        "costas",
        "partes inferiores",
        "região interescapular",
        "barriga"
      ],
      "bill_description_raw": [
        "bico chato e castanho-amarelado, semelhante ao dos patos"
      ],
      "wing_description_raw": [
        "macias e cinzentas penas das asas (incluindo as “plumas”, que correspondem às rêmiges nas outra aves) se dirigem obliquamente de cima para baixo, formando um manto que se eleva em uma corcova dorsal",
        "garra substancial nas asas (formada pela ponta da alula, que é cornificada)"
      ],
      "tail_description_raw": [
        "Falta inteiramente a cauda e o pigostilo"
      ],
      "size_description_raw": [
        "134 – 170 cm de altura",
        "maior e mais pesada ave brasileira",
        "cabeça pequena",
        "muito grande",
        "pescoço e tarsos longos",
        "menor que o macho"
      ],
      "measurements_raw": [
        "134 – 170 cm de altura",
        "34,4 kg",
        "32 kg"
      ],
      "sexual_dimorphism_raw": [
        "o macho atinge 34,4 kg e a fêmea 32 kg",
        "macho um pouco mais escuro",
        "O macho adulto possui um grande pênis",
        "O macho, além de ser mais robusto, tiene a cabeça mais perfilada e tem o pescoço e as pernas mais grossos",
        "Fêmea: menor que o macho e menos escuro, mas os sexos são muito semelhantes"
      ],
      "juvenile_description_raw": [],
      "plumage_description_raw": [
        "cor predominantemente cinza",
        "base do pescoço recoberta por um tufo de penas laterais cinzentas",
        "curtas penas piliformes",
        "mancha escura",
        "todo o comprimento do tarso é recoberto com escamas transversais",
        "A plumagem das partes superiores é geralmente cinza ou marrom-acinzentada",
        "A coroa, nuca, base do pescoço e parte superior das costas são geralmente marrom-escuras ou pretas",
        "o pescoço às vezes é extensamente esbranquiçado e aparece inchado em machos reprodutores",
        "Indivíduos inteiramente brancos não são incomuns"
      ],
      "distinctive_features_raw": [
        "está entre as poucas aves que não possuem glândulas uropigianas",
        "separação de fezes e urina, ao contrário das outras aves",
        "três dedos, adaptados a sua vida terrestre",
        "Não possui quilha, como as restantes aves, estando o esterno transformado numa placa óssea achatada"
      ],
      "_audit": {
        "prompt_name": "P01_Morfologia",
        "prompt_version": "1.0",
        "model_name": "gemini-3.5-flash-lite",
        "timestamp": "2026-08-09T18:21:33.556225+00:00"
      }
    },
    "alimentacao": {
      "food_items_raw": [
        "folhas",
        "inclusive as espinhosas e ardidas",
        "frutas",
        "sementes",
        "insetos",
        "principalmente gafanhotos",
        "moluscos",
        "carne em putrefação",
        "pequeno animal",
        "lagartixas",
        "pequenos roedores",
        "rãs",
        "cobras",
        "coquinhos caídos",
        "animais moribundos",
        "pedrinhas",
        "qualquer coisa que a auxilie na trituração dos alimentos"
      ],
      "feeding_behavior_raw": [
        "caça moscas procurando-as",
        "ingere pedrinhas ou qualquer coisa que a auxilie na trituração dos alimentos",
        "Forrageia caminhando lentamente, mantendo a cabeça abaixo de 50 cm do solo, interrompida por ocasionais ataques de vigilância em que levanta a cabeça e esquadrinha a área",
        "Com o pescoço curvado em U, move-se lentamente, explorando para cima e para baixo, ou de um lado para o outro, com pequenos movimentos da cabeça",
        "pega-o com a ponta de seu bico, joga a cabeça alguns centímetros para trás, joga o alimento no ar e pega-o na parte de trás da boca com um impulso para a frente da abertura do bico",
        "ema se alimentando"
      ],
      "feeding_locations_raw": [
        "perto de carne em putrefação",
        "ao seu alcance",
        "queimadas"
      ],
      "_audit": {
        "prompt_name": "P02_Alimentacao",
        "prompt_version": "1.0",
        "model_name": "gemini-3.5-flash-lite",
        "timestamp": "2026-08-09T18:21:54.837277+00:00"
      }
    },
    "habitos": {
      "habitats_raw": [
        "paisagens abertas da América do Sul, do Brasil até o sul da Argentina",
        "campos naturais",
        "cerrados",
        "áreas de uso agropecuário",
        "campos",
        "pampas",
        "plantações",
        "savanas de cupins",
        "varjões com buritirana no sudeste do Pará",
        "próximo da orla marítima nos campos litorâneos",
        "brejos"
      ],
      "activity_raw": [
        "passa o dia dormindo e sai à noite para alimentar-se",
        "Quando faz muito calor, ofega de bico meio aberto",
        "gosta de tomar banho entrando nos brejos e atravessando rios a nado"
      ],
      "social_behavior_raw": [
        "Vive em bandos e procura a companhia de ovelhas, vacas e veados campeiros",
        "sedentária e gregária",
        "não se forme bandos numerosos, de várias famílias",
        "podem formar-se grupos de 20 a 30 animais, ou mesmo 100 indivíduos",
        "Um macho pode lutar com outro macho para tomar-lhe as suas fêmeas e até mesmo suas crias"
      ],
      "flight_behavior_raw": [
        "Ela não voa, e usa suas grandes asas para equilibrar-se e mudar de direção ao correr",
        "afasta-se de repente num ziguezague ligeiro, erguendo as asas e inflando a plumagem",
        "foge a grande velocidade dando passos de um metro e meio, podendo atingir mais de 60 km por hora",
        "Corre executando ziguezagues controlados pelas asas, que são abaixadas e levantadas alternadamente",
        "Andando tranquilamente, movimenta as asas ritmicamente"
      ],
      "vocalization_raw": [
        "A ema só vocaliza na época do acasalamento",
        "o macho emite um urro forte, produzindo um som profundo e potente, ouvido de longe, ventríloquo, bissilábco: “bu-úp” (“nan-dú”), lembrando o bramido de um boi",
        "Urra até mesmo à noite",
        "Alarme: grasnido rouco",
        "Os filhotes extraviados emitem assobios melodiosos, lembrando o canto do inhambu-relógio (Crypturellus strigulosus), que o pai responde com leve estalo de bico"
      ],
      "_audit": {
        "prompt_name": "P03_Habitos",
        "prompt_version": "1.0",
        "model_name": "gemini-3.5-flash-lite",
        "timestamp": "2026-08-09T18:22:03.085688+00:00"
      }
    },
    "reproducao": {
      "nest_raw": [
        "faz o ninho",
        "É o macho que constrói o ninho, escavando uma depressão pouco profunda, revestida por vegetação seca e geralmente abrigada na vegetação."
      ],
      "courtship_raw": [
        "Na época do acasalamento, o macho abre as asas e dá os seus passos de dança.",
        "Na disputa entre os machos destacam-se as vocalizações, os saltos, as exibições das asas e do pescoço, ataques e expulsões.",
        "Fazem a corte à fêmea esticando as asas horizontalmente; correm fazendo roda, abrindo e agitando as asas, executando uma exibição arrebatadora que chega a confundir o espectador pela exuberância das plumas macias eriçadas que a mais leve brisa faz tremular."
      ],
      "clutch_raw": [
        "Cada ninho conta com geralmente 20 a 30 ovos, postos por várias fêmeas diferentes, que botam em cada ninho de 4 a 5 ovos."
      ],
      "incubation_raw": [
        "O choco é de responsabilidade do macho",
        "A incubação começa 5 a 8 dias após as fêmeas terem iniciado a postura (o que implica em períodos de incubação com até 12 dias de diferença) e pode durar de 27 a 41 dias."
      ],
      "fledging_raw": [
        "Com 6 meses de vida, os filhotes já estão fortes e quase do tamanho de uma fêmea.",
        "As crias são nidífugas, isto é, abandonam o ninho precocemente, neste caso, com poucos dias de idade.",
        "Com duas semanas de idade, as eminhas alcançam meio metro de altura, sem contar o pescoço."
      ],
      "_audit": {
        "prompt_name": "P04_Reproducao",
        "prompt_version": "1.0",
        "model_name": "gemini-3.5-flash-lite",
        "timestamp": "2026-08-09T18:22:10.861552+00:00"
      }
    }
  }
}
```

### 3. Collection: `ebird` (Municípios e Espécies)
Armazena a relação entre municípios brasileiros (com base no IBGE) e as listas de espécies presentes nesses municípios, oriundas da API do eBird.
- `geocodigo`: String (Identificador único IBGE)
- `nome`: String (Nome do município)
- `uf`: String
- `bioma`: String
- `ebird_code`: String
- `ebird_name`: String
- `match_type`: String (Ex: "exact", "fuzzy:90", "no_match")
- `total_especies`: Integer
- `especies`: Array de Objetos (Espécies eBird associadas)
  - `speciesCode`: String
  - `comName`: String
  - `sciName`: String
  - `order`: String
  - `familyComName`: String
  - `familySciName`: String
  - `category`: String

#### Exemplo documento
```
{
  "_id": {
    "$oid": "6a4048621955e836a0a464dc"
  },
  "geocodigo": "2103554",
  "bioma": "Amazônia",
  "ebird_code": "BR-MA-062",
  "ebird_name": "Conceição do Lago-Açu",
  "especies": [
    {
      "speciesCode": "yecspi2",
      "comName": "Yellow-chinned Spinetail",
      "sciName": "Certhiaxis cinnamomeus",
      "order": "Passeriformes",
      "familyComName": "Ovenbirds and Woodcreepers",
      "familySciName": "Furnariidae",
      "category": "species"
    },
    {
      "speciesCode": "mawtyr1",
      "comName": "Masked Water-Tyrant",
      "sciName": "Fluvicola nengeta",
      "order": "Passeriformes",
      "familyComName": "Tyrant Flycatchers",
      "familySciName": "Tyrannidae",
      "category": "species"
    },
    {
      "speciesCode": "houspa",
      "comName": "House Sparrow",
      "sciName": "Passer domesticus",
      "order": "Passeriformes",
      "familyComName": "Old World Sparrows",
      "familySciName": "Passeridae",
      "category": "species"
    }
  ],
  "match_type": "exact",
  "nome": "Conceição do Lago-Açu",
  "total_especies": 3,
  "uf": "MA"
}
```

### 4. Collection: `ocorrencias_especies`

#### Exemplo documento
```
{
  "_id": {
    "$oid": "6a418f22f5cda2bedaf0b094"
  },
  "nome_cientifico": "Rhea americana",
  "biomas": [
    "Amazônia",
    "Cerrado",
    "Caatinga",
    "Mata Atlântica",
    "Pampa",
    "Pantanal"
  ],
  "contagem_ocorrencias": 534,
  "estados": [
    "PA",
    "TO",
    "MA",
    "PI",
    "CE",
    "RN",
    "PB",
    "BA",
    "MG",
    "SP",
    "PR",
    "RS",
    "MS",
    "MT",
    "GO",
    "DF"
  ],
  "municipios": [
    {
      "geocodigo": "1500602",
      "nome": "Altamira",
      "uf": "PA"
    },
    {
      "geocodigo": "1502103",
      "nome": "Cametá",
      "uf": "PA"
    },
    {
      "geocodigo": "1502707",
      "nome": "Conceição do Araguaia",
      "uf": "PA"
    },...
  ],
  "paises": [
    "Brasil"
  ]
}
```

### 4. Collection: `canonical_species`

#### Exemplo documento
```
{
  "_id": {
    "$oid": "6a402738fdd104ff0ef40a72"
  },
  "species_id": "3550d103-333a-4eb2-92c7-603fe208fe45",
  "scientific_name": "Rhea americana",
  "authority": "(Linnaeus, 1758)",
  "common_names": {
    "pt": [
      "ema"
    ],
    "en": [
      "Greater Rhea"
    ]
  },
  "taxonomy": {
    "kingdom": "Animalia",
    "phylum": "Chordata",
    "class": "Aves",
    "order": "Struthioniformes",
    "family": "Rheidae",
    "genus": "Rhea",
    "species": "Rhea americana"
  },
  "morphology": {
    "size_cm": {
      "min": null,
      "max": null
    },
    "weight_g": {
      "min": null,
      "max": null,
      "mean": 23000
    },
    "colors": [],
    "beak": {
      "shape": "",
      "culmen_mm": 86.5,
      "nares_mm": 35.6,
      "width_mm": 27.2,
      "depth_mm": 17.2
    },
    "wing": {
      "shape": "",
      "length_mm": 604.5,
      "hand_wing_index": 0.1,
      "kipps_distance_mm": 0.3
    },
    "tail": {
      "shape": "",
      "length_mm": 62
    },
    "tarsus_mm": 308,
    "sexual_dimorphism": "",
    "juvenile_description": "",
    "distinctive_features": []
  },
  "description": {
    "short": "",
    "detailed": "134 – 170 cm de altura, dependendo da postura adotada; o macho atinge 34,4 kg e a fêmea 32 kg. É a maior e mais pesada ave brasileira. Tem cor predominantemente cinza...",
    "behavior": [],
    "identification": ""
  },
  "diet": {
    "guilds": [
      "Omnivore"
    ],
    "food_items": []
  },
  "habitat": {
    "primary": [
      "Grassland"
    ],
    "secondary": [],
    "altitude_range_m": {
      "min": null,
      "max": null
    }
  },
  "occurrence": {
    "countries": [],
    "states": [],
    "municipalities": [],
    "biomes": [],
    "range_area_km2": 6537549.66,
    "endemism": "",
    "range_type": ""
  },
  "ecology": {
    "activity_pattern": "",
    "social_structure": "",
    "migration": 1,
    "primary_lifestyle": "Terrestrial",
    "trophic_level": "Omnivore",
    "trophic_niche": "Omnivore",
    "reproduction": ""
  },
  "conservation": {
    "iucn_status": "Quase Ameaçada",
    "population_trend": "",
    "cites": ""
  },
  "external_ids": {
    "wikiaves": "10001",
    "gbif": null,
    "ebird": null,
    "iucn": null,
    "birdlife": null
  },
  "data_quality": {
    "confidence_score": null,
    "sources": [
      "AVONET",
      "WikiAves"
    ],
    "schema_version": "1.0",
    "pipeline_version": "1.0",
    "last_updated": {
      "$date": "2026-06-27T19:40:40.029Z"
    }
  }
}
```
