| Campo no documento                | Tipo de dado               | Fonte primária           | Fontes secundárias   | Estratégia de enriquecimento                   |
| --------------------------------- | -------------------------- | ------------------------ | -------------------- | ---------------------------------------------- |
| `scientific_name`                 | taxon                      | AVONET                   | GBIF, eBird          | AVONET como autoridade (golden source)         |
| `common_name_pt`                  | nome comum                 | WikiAves                 | eBird                | LLM + scraping + normalização linguística      |
| `common_name_en`                  | nome comum                 | eBird                    | GBIF                 | cross-reference + LLM alignment                |
| `taxonomy`                        | hierarquia biológica       | AVONET                   | GBIF                 | AVONET (principal), fallback GBIF              |
| `morphology.size_cm`              | morfologia                 | AVONET                   | —                    | direto AVONET                                  |
| `morphology.weight_g`             | morfologia                 | AVONET                   | —                    | direto AVONET                                  |
| `morphology.beak_type`            | morfologia funcional       | AVONET                   | LLM enrichment       | AVONET + classificação derivada por LLM        |
| `morphology.colors`               | visual                     | AVONET (parcial)         | WikiAves             | LLM + visão descritiva (scraping + inferência) |
| `morphology.distinctive_features` | descrição visual           | WikiAves                 | eBird                | LLM sintetiza observações humanas              |
| `description.short`               | texto semântico            | LLM                      | eBird                | LLM baseado em múltiplas fontes                |
| `description.detailed`            | texto rico                 | WikiAves                 | eBird + GBIF notes   | scraping + LLM synthesis                       |
| `description.behavior`            | comportamento              | eBird                    | WikiAves             | agregação + LLM normalization                  |
| `description.diet`                | ecologia alimentar         | eBird                    | AVONET               | AVONET + LLM inferência controlada             |
| `habitat.primary`                 | habitat ecológico          | eBird                    | GBIF                 | consenso multi-fonte                           |
| `habitat.secondary`               | habitat expandido          | GBIF                     | eBird                | inferência espacial + registros                |
| `habitat.altitude_range_m`        | ecologia espacial          | GBIF                     | WorldClim (se usado) | derivação estatística                          |
| `occurrence.countries`            | distribuição               | GBIF                     | eBird                | GBIF como base global                          |
| `occurrence.biomes`               | bioma                      | GBIF + WWF biome mapping | eBird                | geospatial join + enrichment                   |
| `occurrence.range_type`           | classificação distribuição | LLM                      | GBIF                 | inferência (broad, endemic, restricted)        |
| `ecology.activity_pattern`        | comportamento              | eBird                    | WikiAves             | LLM normalization                              |
| `ecology.social_structure`        | comportamento social       | eBird                    | WikiAves             | LLM inference                                  |
| `ecology.migration`               | migração                   | eBird                    | GBIF                 | eBird checklist temporal                       |
| `rag.embedding_text`              | texto para embedding       | TODOS os campos acima    | —                    | pipeline determinístico de concatenação        |
| `rag.keywords`                    | indexação híbrida          | LLM                      | —                    | extração semântica controlada                  |
| `data_quality.confidence_score`   | score                      | LLM + regras             | —                    | scoring baseado em cobertura de fontes         |
| `data_quality.sources`            | lineage                    | pipeline                 | —                    | tracking automático de proveniência            |
| `status.conservation`             | risco extinção             | IUCN                     | —                    | fonte única oficial                            |
| `status.population_trend`         | tendência populacional     | IUCN                     | —                    | direto IUCN                                    |
