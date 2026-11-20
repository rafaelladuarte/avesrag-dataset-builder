# Plano de Sprints — AVESRAG

## 1. Estado atual do projeto

### 1.1. O que já está pronto

A base MongoDB já possui collections para diferentes responsabilidades:

- `avonet`: dados morfológicos, ecológicos e geográficos do AVONET.
- `wikiaves`: dados descritivos, taxonômicos, comportamentais e metadados de mídia da WikiAves.
- `ebird`: relação entre municípios brasileiros e espécies observadas via eBird.
- `ocorrencias_especies`: ocorrência agregada por espécie, incluindo biomas, estados e municípios.
- `canonical_species`: tentativa atual de Golden Record consolidado por espécie.

A collection `wikiaves` também contém uma etapa de processamento semântico com:

- `species_raw`;
- `species_normalized`;
- `canonical_species`;
- `_audit` contendo prompt, versão, modelo e timestamp das transformações.

A estrutura atual, portanto, já apresenta uma separação importante entre dados de origem, dados normalizados e dados destinados à consolidação. A documentação disponível mostra, porém, que a consolidação final ainda não está completa. Há campos vazios no `canonical_species`, identificadores externos ainda não resolvidos e informações existentes em collections de origem que ainda não chegaram ao Golden Record.

### 1.2. O que está parcialmente pronto

- Entity Resolution entre as diferentes fontes.
- Consolidação taxonômica.
- Fusão dos atributos de AVONET e WikiAves.
- Integração da ocorrência do eBird ao registro canônico.
- Preenchimento dos `external_ids`.
- Definição de regras de prioridade entre fontes.
- Curadoria da camada `species_normalized`.
- Data Quality formal da camada canônica.
- Proveniência em nível de campo.
- Validação do Golden Record como base estável para RAG.

### 1.3. O que ainda está pendente

Antes da arquitetura de embeddings, a base precisa chegar a um estado em que cada espécie tenha identidade resolvida, dados fusionados, proveniência e qualidade verificadas.

A documentação atual também revela uma lacuna taxonômica que precisa ser explicitamente tratada: o exemplo de `Rhea americana` apresenta `Struthioniformes` em AVONET e `Rheiformes` na WikiAves. A documentação não estabelece qual tratamento taxonômico deve prevalecer. Isso deve ser decidido como parte da consolidação, não assumido antecipadamente.

Da mesma forma, a documentação não fecha:

- qual fonte é autoridade para cada domínio;
- qual vector database será usado;
- qual modelo de embedding será usado;
- como o texto semântico será construído;
- qual estratégia de chunking será adotada;
- se haverá retrieval vetorial, híbrido ou outra estratégia.

Essas decisões devem ser adiadas até que os dados e as métricas necessárias estejam disponíveis.

---

## 2. Estratégia geral de execução

O plano segue uma estratégia de dependências progressivas:

```text
Estado atual
    ↓
Identidade das espécies
    ↓
Contrato de fusão
    ↓
Consolidação do Golden Record
    ↓
Curadoria semântica
    ↓
Data Quality + cobertura
    ↓
Preparação da representação para retrieval
    ↓
Experimentação de embeddings / retrieval
    ↓
Avaliação
    ↓
Otimização
    ↓
Arquitetura consolidada
```

A prioridade é estabilizar a camada de dados antes de introduzir uma arquitetura vetorial definitiva.

A razão é direta: embeddings produzidos sobre registros ainda inconsistentes criariam retrabalho e poderiam mascarar problemas de qualidade da base. Primeiro deve existir uma representação canônica confiável; depois deve ser definido como essa representação será transformada em unidades semânticas para recuperação.

As sprints foram separadas em duas grandes fases:

### Fase A — Consolidação da base

Sprints 1 a 5:

1. Inventário e contrato de identidade.
2. Entity Resolution e registro de espécies.
3. Contrato de Data Fusion.
4. Golden Record.
5. Curadoria e Data Quality.

### Fase B — Preparação e experimentação do retrieval

Sprints 6 a 9:

6. Dataset de avaliação e representação semântica.
7. Baseline de retrieval.
8. Experimentação de embeddings e estratégia de retrieval.
9. Avaliação e decisão arquitetural.

A arquitetura definitiva de embeddings não deve ser decidida antes das métricas produzidas pelas sprints de experimentação.

---

## 3. Roadmap das Sprints

| Sprint | Objetivo | Prioridade | Complexidade | Dependências | Resultado principal |
|---|---|---|---|---|---|
| 1 | Fechar identidade e contrato de espécie | Alta | Média | Estado atual | `species_registry` e regras de identidade |
| 2 | Resolver entidades entre fontes | Alta | Alta | Sprint 1 | Mapeamento fonte → `species_id` |
| 3 | Definir contrato de fusão | Alta | Alta | Sprint 2 | Mapping + regras de prioridade/conflito |
| 4 | Construir Golden Record consolidado | Alta | Alta | Sprint 3 | `canonical_species` completo e reproduzível |
| 5 | Curadoria + Data Quality | Alta | Alta | Sprint 4 | Base validada, métricas e quarantine |
| 6 | Preparar representação semântica e dataset de avaliação | Alta | Média | Sprint 5 | Dataset de avaliação + textos candidatos |
| 7 | Criar baseline de retrieval | Alta | Média | Sprint 6 | Baseline mensurável sem arquitetura definitiva |
| 8 | Experimentar embeddings e retrieval | Alta | Alta | Sprint 7 | Resultados comparativos |
| 9 | Avaliar e consolidar arquitetura | Alta | Alta | Sprint 8 | Decisão arquitetural documentada |

---

## Sprint 1 — Contrato de Identidade das Espécies

**Prioridade:** Alta
**Complexidade:** Média
**Dependências:** estado atual da base
**Risco principal:** criar identificadores inconsistentes ou permitir que nomes científicos funcionem como identidade permanente.
**Ponto de decisão:** definição formal da identidade interna da espécie.

**Objetivo:**

Definir a identidade canônica de uma espécie no projeto e criar o contrato que permitirá relacionar todas as fontes ao mesmo registro.

**Justificativa:**

As collections atuais utilizam `nome_cientifico`/`scientific_name` em diferentes contextos, enquanto `canonical_species` já possui `species_id`. Sem uma identidade interna clara, a fusão entre fontes fica dependente de strings e dificulta auditoria, versionamento e futuras mudanças taxonômicas.

Esta sprint deve acontecer antes de qualquer fusão porque todas as etapas seguintes precisam saber exatamente a qual espécie um dado pertence.

**Pré-requisitos:**

- Collections atuais disponíveis.
- Schema atual documentado.
- `canonical_species.species_id` existente identificado.

**Tarefas:**

1. **Inventariar os identificadores atuais.**
   - Mapear `nome_cientifico`, `scientific_name`, `meta_id`, `speciesCode`, IDs eventualmente presentes em outras fontes e o `species_id`.
   - Validar quantidade de registros e duplicidades por identificador.

2. **Definir `species_id` como identificador interno.**
   - Documentar que o identificador interno representa a entidade da espécie dentro do AVESRAG.
   - Não substituir os identificadores externos.

3. **Projetar `species_registry`.**
   - Criar uma collection dedicada ao relacionamento entre `species_id`, nome científico, autoridade e IDs externos.
   - Definir estados de resolução, como `matched`, `pending` e `not_found`, somente se forem necessários para representar o processo.

4. **Criar regras de identidade.**
   - Definir quais campos podem participar do matching.
   - Registrar separadamente matches exatos, fuzzy e não resolvidos.

5. **Criar testes de unicidade.**
   - Garantir que um `species_id` não represente duas entidades diferentes.
   - Detectar múltiplos registros conflitantes para a mesma identidade.

**Como fazer:**

A implementação deve ser simples e reproduzível em Python, utilizando as collections MongoDB existentes. O resultado da resolução deve ser persistido, e não depender de uma comparação feita novamente a cada pipeline.

Não introduzir ainda embeddings ou vector database.

**Resultado esperado:**

Uma definição única de identidade de espécie e uma collection `species_registry` pronta para receber o mapeamento entre fontes.

**Critérios de conclusão (Definition of Done):**

- [ ] `species_id` está formalmente definido como chave interna.
- [ ] Identificadores externos foram inventariados.
- [ ] `species_registry` possui schema documentado.
- [ ] Regras de identidade estão documentadas.
- [ ] Duplicidades de identidade foram identificadas.
- [ ] Testes de unicidade executam sem inconsistências não explicadas.

**Entregáveis:**

- `species_registry`.
- Schema documentado.
- Script de criação/população inicial.
- Testes de identidade.
- Relatório de duplicidades.
- Documentação das regras.

**Dependências para a próxima sprint:**

A Sprint 2 utilizará `species_registry` como chave de relacionamento entre as fontes.

---

## Sprint 2 — Entity Resolution entre as Fontes

**Prioridade:** Alta
**Complexidade:** Alta
**Dependências:** Sprint 1
**Risco principal:** falsos matches ou espécies diferentes sendo associadas ao mesmo `species_id`.
**Ponto de decisão:** limiar e política para matches fuzzy.

**Objetivo:**

Resolver as correspondências entre AVONET, WikiAves, eBird e ocorrência, vinculando os registros à mesma identidade interna.

**Justificativa:**

A consolidação depende de saber quais registros representam a mesma espécie. A collection `ebird` já possui `match_type`, demonstrando que matching é uma etapa existente, mas a estratégia precisa ser integrada ao registro canônico.

Executar a fusão antes dessa etapa poderia misturar informações de espécies diferentes.

**Pré-requisitos:**

- `species_registry`.
- Campos de identificação de todas as collections.
- Regras de identidade da Sprint 1.

**Tarefas:**

1. **Criar candidatos de correspondência.**
   - Usar nome científico e identificadores disponíveis.
   - Separar matches exatos de fuzzy.

2. **Resolver WikiAves ↔ AVONET.**
   - Priorizar correspondências científicas exatas.
   - Registrar casos ambíguos para revisão.

3. **Resolver eBird ↔ registro canônico.**
   - Aproveitar `speciesCode`, `sciName` e `match_type`.
   - Não converter automaticamente `no_match` em correspondência.

4. **Integrar ocorrência ↔ `species_id`.**
   - Relacionar `ocorrencias_especies.nome_cientifico` ao registro de identidade.

5. **Gerar relatório de resolução.**
   - Percentual de match exato.
   - Percentual de fuzzy.
   - Quantidade de `no_match`.
   - Casos ambíguos.

6. **Persistir o resultado.**
   - Atualizar `species_registry` com os IDs externos resolvidos.

**Como fazer:**

Separar o matching determinístico do fuzzy. Matches fuzzy não devem ser tratados como verdade sem uma regra de aceitação documentada.

Todos os casos não resolvidos devem permanecer identificáveis. Não apagar registros das fontes.

**Resultado esperado:**

Cada registro que puder ser relacionado com segurança possui um `species_id`; casos ambíguos e não resolvidos são explicitamente conhecidos.

**Definition of Done:**

- [ ] AVONET possui correspondência documentada.
- [ ] WikiAves possui correspondência documentada.
- [ ] eBird possui correspondência documentada.
- [ ] Ocorrência possui correspondência documentada.
- [ ] `no_match` não é silenciosamente descartado.
- [ ] Matches fuzzy são auditáveis.
- [ ] Relatório de cobertura foi produzido.
- [ ] Casos ambíguos foram separados.

**Entregáveis:**

- `species_registry` enriquecido.
- Scripts de Entity Resolution.
- Relatório de matching.
- Testes.
- Documentação dos critérios.

**Dependências para a próxima sprint:**

A Sprint 3 utilizará o mapeamento resolvido para saber quais valores pertencem à mesma espécie.

---

## Sprint 3 — Contrato de Data Fusion

**Prioridade:** Alta
**Complexidade:** Alta
**Dependências:** Sprint 2
**Risco principal:** conflitos silenciosos entre fontes.
**Ponto de decisão:** fonte prioritária por domínio/atributo.

**Objetivo:**

Definir formalmente como os dados das fontes serão transformados e combinados no Golden Record.

**Justificativa:**

O `canonical_species` atual já combina AVONET e WikiAves, mas ainda contém campos vazios e não existe, na documentação disponível, uma matriz formal de origem e prioridade para cada atributo.

Sem esse contrato, a consolidação fica dependente de decisões implícitas no código.

**Pré-requisitos:**

- Entity Resolution concluído.
- Schemas atuais.
- Lista de campos do `canonical_species`.

**Tarefas:**

1. **Criar matriz de mapeamento de campos.**
   - Para cada campo canônico, indicar fonte, campo de origem e transformação.

2. **Definir prioridade por domínio.**
   - Taxonomia.
   - Morfologia.
   - Descrição.
   - Dieta.
   - Habitat.
   - Ocorrência.
   - Conservação.
   - IDs externos.

3. **Definir regras de conflito.**
   - Valor único.
   - Múltiplos valores.
   - Intervalo.
   - Fonte prioritária.
   - Conflito não resolvido.

4. **Definir tratamento de valores ausentes.**
   - Ausência real.
   - Não encontrado.
   - Não aplicável.
   - Pendente de resolução.

5. **Definir regras de transformação.**
   - Unidades.
   - nomes;
   - listas;
   - taxonomia;
   - agregações de ocorrência.

6. **Documentar casos de conflito conhecidos.**
   - Especialmente a divergência taxonômica observada para `Rhea americana`.

**Como fazer:**

O contrato deve ser escrito antes da implementação do consolidator. Cada campo deve ter uma regra verificável.

Não escolher uma autoridade taxonômica por conveniência. A documentação atual não fecha essa decisão; ela deve ser explicitamente tomada nesta sprint com base nas fontes adotadas pelo projeto.

**Resultado esperado:**

Um contrato de fusão que permita a outro agente implementar a consolidação sem inferir regras.

**Definition of Done:**

- [ ] Todos os campos do Golden Record possuem origem definida ou estão explicitamente marcados como pendentes.
- [ ] Prioridades por domínio estão documentadas.
- [ ] Conflitos possuem tratamento definido.
- [ ] Ausência possui semântica definida.
- [ ] Transformações possuem regra documentada.
- [ ] Divergências taxonômicas conhecidas estão registradas.
- [ ] O contrato foi revisado antes da implementação.

**Entregáveis:**

- `data_fusion_mapping.md`.
- Regras de prioridade.
- Regras de conflito.
- Regras de transformação.
- Casos de teste de fusão.

**Dependências para a próxima sprint:**

A Sprint 4 implementará exatamente o contrato definido aqui.

---

## Sprint 4 — Construção do Golden Record

**Prioridade:** Alta
**Complexidade:** Alta
**Dependências:** Sprint 3
**Risco principal:** consolidar dados incorretamente ou perder proveniência.
**Ponto de decisão:** nenhum novo desenho arquitetural deve ser introduzido sem necessidade; a sprint implementa o contrato.

**Objetivo:**

Construir uma versão reproduzível da `canonical_species`, preenchendo os dados disponíveis nas fontes e mantendo a origem das informações.

**Justificativa:**

A `canonical_species` atual ainda apresenta campos vazios apesar de os dados existirem em outras collections. Ela precisa deixar de ser uma coleção parcialmente consolidada e passar a representar efetivamente o Golden Record.

**Pré-requisitos:**

- Entity Resolution.
- Contrato de Data Fusion.
- Schema da `canonical_species`.

**Tarefas:**

1. **Implementar o consolidator.**
   - Ler as collections de origem.
   - Relacionar por `species_id`.
   - Aplicar as regras do contrato.

2. **Consolidar taxonomia.**
   - Aplicar a autoridade definida no contrato.
   - Preservar informação de origem.

3. **Consolidar morfologia.**
   - Integrar valores de AVONET e WikiAves.
   - Padronizar unidades.

4. **Consolidar descrição, dieta, habitat e ecologia.**
   - Aplicar prioridade e regras de combinação.

5. **Consolidar ocorrência.**
   - Integrar estados, municípios, biomas e países disponíveis.
   - Manter a origem dos dados.

6. **Consolidar conservação.**
   - Integrar dados disponíveis da fonte correspondente quando essa integração estiver implementada.

7. **Completar `external_ids`.**
   - Preencher identificadores resolvidos.
   - Representar explicitamente os que não foram encontrados.

8. **Adicionar provenance.**
   - Registrar origem dos dados consolidados.
   - Não confundir proveniência da fonte com auditoria das transformações por LLM.

9. **Versionar o processo.**
   - Registrar `schema_version` e `pipeline_version`.

**Como fazer:**

A consolidação deve ser determinística sempre que possível. Transformações semânticas feitas por LLM devem continuar identificáveis por `_audit`.

Não sobrescrever os dados RAW.

A saída deve ser regenerável a partir das collections de origem e do contrato de fusão.

**Resultado esperado:**

Uma `canonical_species` completa, reproduzível e rastreável.

**Definition of Done:**

- [ ] Todas as espécies resolvidas possuem Golden Record.
- [ ] Campos disponíveis nas fontes foram incorporados conforme o contrato.
- [ ] Valores conflitantes seguem regras documentadas.
- [ ] Proveniência está preservada.
- [ ] `external_ids` foram preenchidos quando disponíveis.
- [ ] Ocorrência foi integrada quando disponível.
- [ ] Pipeline pode ser executado novamente sem depender de edição manual.
- [ ] Nenhum RAW foi sobrescrito.

**Entregáveis:**

- Código do consolidator.
- Nova versão da `canonical_species`.
- Testes de fusão.
- Relatório de cobertura.
- Documentação de provenance.
- Versão do pipeline/schema.

**Dependências para a próxima sprint:**

A Sprint 5 validará e fará a curadoria do Golden Record produzido aqui.

---

## Sprint 5 — Curadoria Semântica e Data Quality

**Prioridade:** Alta
**Complexidade:** Alta
**Dependências:** Sprint 4
**Risco principal:** levar ruído, duplicidades e valores semanticamente inconsistentes para a representação usada pelo retrieval.
**Ponto de decisão:** critérios de qualidade mínimos para considerar uma espécie apta para experimentação.

**Objetivo:**

Validar a qualidade do Golden Record e corrigir problemas de normalização semântica antes de construir qualquer índice vetorial.

**Justificativa:**

A estrutura `species_normalized` atual demonstra extração semântica, mas contém exemplos de duplicidades, flexões, frases e ruído. Embeddings sobre esse conteúdo poderiam incorporar essas inconsistências.

**Pré-requisitos:**

- Golden Record reproduzível.
- Dados de origem preservados.

**Tarefas:**

1. **Auditar `species_normalized`.**
   - Identificar duplicidades.
   - Identificar frases completas em campos que deveriam representar conceitos.
   - Identificar categorias com conteúdo inadequado.

2. **Definir o que é normalização e o que é extração.**
   - Não transformar toda informação textual em vocabulário artificialmente fechado.
   - Preservar fatos quando a normalização não for segura.

3. **Criar regras de curadoria.**
   - Deduplicação.
   - Padronização de unidades.
   - Padronização de termos.
   - Remoção de ruído evidente.

4. **Criar validações automáticas.**
   - Tipos.
   - Ranges.
   - Campos obrigatórios.
   - Taxonomia.
   - Identidade.
   - Proveniência.

5. **Criar quarantine.**
   - Registros que falharem em regras críticas não devem desaparecer.
   - Devem ser isolados para revisão.

6. **Produzir métricas de qualidade.**
   - Cobertura por campo.
   - Cobertura por fonte.
   - Percentual de espécies aptas.
   - Quantidade de conflitos.
   - Quantidade de registros incompletos.

**Como fazer:**

Preferir regras determinísticas para Data Quality. LLM pode continuar sendo usado onde já foi adotado para normalização, mas sua saída deve permanecer auditável.

Não tentar resolver todos os problemas linguísticos nesta sprint; o objetivo é eliminar problemas que comprometam a representação semântica e a confiabilidade do Golden Record.

**Resultado esperado:**

Uma base canônica com métricas objetivas de qualidade e um conjunto claramente identificado de espécies aptas para experimentação.

**Definition of Done:**

- [ ] Validações automatizadas executam.
- [ ] Cobertura por campo foi medida.
- [ ] Duplicidades críticas foram tratadas.
- [ ] Problemas de unidade foram identificados/corrigidos.
- [ ] Conflitos taxonômicos estão resolvidos ou explicitamente pendentes.
- [ ] Quarantine existe para falhas críticas.
- [ ] Proveniência está preservada.
- [ ] Existe um relatório de Data Quality.
- [ ] Existe uma definição objetiva de "espécie apta".

**Entregáveis:**

- Testes de Data Quality.
- Regras de validação.
- Quarantine.
- Relatório de qualidade.
- Versão validada do Golden Record.
- Documentação de problemas conhecidos.

**Dependências para a próxima sprint:**

A Sprint 6 utilizará somente registros que atendam aos critérios de qualidade definidos aqui.

---

## Sprint 6 — Representação Semântica e Dataset de Avaliação

**Prioridade:** Alta
**Complexidade:** Média
**Dependências:** Sprint 5
**Risco principal:** definir a representação do documento de retrieval sem dados de avaliação suficientes.
**Ponto de decisão:** quais campos devem participar da representação semântica.

**Objetivo:**

Preparar uma representação textual/semântica do Golden Record e criar um conjunto de consultas de avaliação antes de escolher uma arquitetura definitiva de embeddings.

**Justificativa:**

Ainda não está definido quais campos serão embutidos, como serão agrupados nem qual estratégia de chunking será necessária. Essas decisões devem ser orientadas pelo comportamento do retrieval.

**Pré-requisitos:**

- Golden Record validado.
- Métricas de Data Quality.
- Espécies aptas para experimentação.

**Tarefas:**

1. **Definir campos candidatos à representação semântica.**
   - Identificação.
   - Morfologia.
   - Características diagnósticas.
   - Habitat.
   - Alimentação.
   - Comportamento.
   - Ocorrência.
   - Outros campos relevantes já existentes.

2. **Criar representações experimentais.**
   - Uma representação integrada.
   - Representações separadas por domínio quando necessário.

3. **Criar dataset de avaliação.**
   - Consultas sintéticas e/ou exemplos reais disponíveis.
   - Cada consulta deve possuir espécie-alvo conhecida.

4. **Definir métricas.**
   - Recall@K.
   - Precision@K quando aplicável.
   - MRR ou métrica equivalente para ranking.
   - Cobertura de candidatos.

5. **Criar conjunto de casos difíceis.**
   - Espécies semelhantes.
   - Descrições incompletas.
   - Descrições focadas em habitat.
   - Descrições focadas em comportamento.
   - Descrições morfológicas.

**Como fazer:**

Não escolher ainda o modelo final de embeddings nem o vector database como decisão definitiva. O objetivo é construir um ambiente experimental comparável.

**Resultado esperado:**

Um dataset de avaliação reproduzível e representações candidatas que permitam comparar estratégias.

**Definition of Done:**

- [ ] Campos candidatos estão documentados.
- [ ] Representações experimentais são geradas de forma reproduzível.
- [ ] Dataset de avaliação possui espécie-alvo.
- [ ] Métricas estão definidas.
- [ ] Casos difíceis estão representados.
- [ ] Processo de avaliação pode ser executado automaticamente.

**Entregáveis:**

- Dataset de avaliação.
- Gerador de representação semântica.
- Scripts de avaliação.
- Métricas documentadas.
- Relatório inicial dos casos de teste.

**Dependências para a próxima sprint:**

A Sprint 7 usará o dataset e as representações para estabelecer um baseline.

---

## Sprint 7 — Baseline de Retrieval

**Prioridade:** Alta
**Complexidade:** Média
**Dependências:** Sprint 6
**Risco principal:** comparar arquiteturas complexas sem possuir uma referência simples.
**Ponto de decisão:** baseline mínimo contra o qual os embeddings serão comparados.

**Objetivo:**

Criar uma estratégia simples de recuperação que permita medir o quanto as representações atuais já conseguem recuperar espécies relevantes.

**Justificativa:**

Sem baseline, não existe forma objetiva de afirmar que uma arquitetura vetorial melhorou o sistema.

**Pré-requisitos:**

- Dataset de avaliação.
- Representações semânticas.
- Golden Record validado.

**Tarefas:**

1. **Implementar recuperação lexical simples.**
   - Usar os campos mais relevantes.
   - Registrar ranking produzido.

2. **Executar o dataset de avaliação.**

3. **Calcular métricas.**
   - Recall@K.
   - MRR ou equivalente.
   - Analisar erros.

4. **Classificar erros.**
   - Falha de identidade.
   - Falha de representação.
   - Falha de cobertura.
   - Ambiguidade real.
   - Limitação da recuperação lexical.

5. **Documentar baseline.**

**Como fazer:**

Manter o baseline simples. Ele não deve ser tratado como arquitetura final.

**Resultado esperado:**

Um ponto de comparação quantitativo para as experiências vetoriais.

**Definition of Done:**

- [ ] Baseline executável.
- [ ] Dataset completo foi processado.
- [ ] Métricas calculadas.
- [ ] Erros classificados.
- [ ] Resultado versionado.
- [ ] Baseline documentado.

**Entregáveis:**

- Implementação do baseline.
- Métricas.
- Relatório de erros.
- Dataset de resultados.

**Dependências para a próxima sprint:**

A Sprint 8 deverá superar ou justificar diferenças em relação ao baseline.

---

## Sprint 8 — Experimentação de Embeddings e Retrieval

**Prioridade:** Alta
**Complexidade:** Alta
**Dependências:** Sprint 7
**Risco principal:** escolher modelo, chunking ou vector store com base em preferência e não em evidência.
**Ponto de decisão:** estratégia de embeddings e retrieval.

**Objetivo:**

Experimentar alternativas de representação vetorial e recuperação utilizando o dataset de avaliação criado anteriormente.

**Justificativa:**

Somente agora existem os dados necessários para decidir a arquitetura: Golden Record validado, representação semântica, dataset de avaliação e baseline.

**Pré-requisitos:**

- Sprint 7 concluída.
- Dataset de avaliação.
- Baseline.
- Representações experimentais.

**Tarefas:**

1. **Definir conjunto limitado de candidatos a embedding.**
   - Somente modelos compatíveis com os requisitos do projeto.
   - Registrar dimensão, idioma, custo e restrições.

2. **Testar estratégias de representação.**
   - Documento integrado.
   - Separação por domínio.
   - Chunking quando houver justificativa.

3. **Testar retrieval.**
   - Comparar resultados com o baseline.
   - Medir Recall@K e ranking.

4. **Avaliar casos difíceis.**
   - Morfologia.
   - Habitat.
   - Dieta.
   - Comportamento.
   - Descrições ambíguas.

5. **Avaliar vector store apenas no nível necessário.**
   - Não otimizar infraestrutura antes de validar a qualidade da recuperação.

6. **Registrar custo e desempenho.**
   - Tempo de indexação.
   - Latência.
   - Dimensionalidade.
   - Custo de geração.
   - Qualidade.

**Como fazer:**

A experimentação deve alterar uma variável por vez sempre que possível. O objetivo é atribuir diferenças de qualidade à mudança realmente testada.

Não escolher a arquitetura definitiva por popularidade da tecnologia.

**Resultado esperado:**

Uma matriz comparativa de estratégias e evidências suficientes para uma decisão arquitetural.

**Definition of Done:**

- [ ] Candidatos foram testados com o mesmo dataset.
- [ ] Métricas são comparáveis.
- [ ] Baseline foi incluído.
- [ ] Casos difíceis foram analisados.
- [ ] Custos/latência foram registrados quando mensuráveis.
- [ ] Resultados estão versionados.
- [ ] Nenhuma escolha definitiva foi feita sem evidência.

**Entregáveis:**

- Experimentos de embeddings.
- Índices experimentais.
- Matriz comparativa.
- Relatório de resultados.
- Análise de erros.

**Dependências para a próxima sprint:**

A Sprint 9 utilizará os resultados para formalizar a arquitetura de retrieval.

---

## Sprint 9 — Avaliação e Consolidação da Arquitetura

**Prioridade:** Alta
**Complexidade:** Alta
**Dependências:** Sprint 8
**Risco principal:** transformar um resultado experimental em arquitetura sem considerar operação, manutenção e qualidade.
**Ponto de decisão:** arquitetura de embeddings/retrieval adotada.

**Objetivo:**

Transformar os resultados experimentais em uma decisão arquitetural documentada e reproduzível.

**Justificativa:**

A arquitetura definitiva deve ser consequência dos resultados obtidos, não uma premissa anterior aos testes.

**Pré-requisitos:**

- Resultados da Sprint 8.
- Baseline.
- Métricas.
- Relatório de Data Quality.

**Tarefas:**

1. **Comparar estratégias por qualidade.**
2. **Comparar por custo e complexidade.**
3. **Avaliar impacto de atualização dos dados.**
4. **Definir estratégia de reindexação.**
5. **Definir representação final dos documentos.**
6. **Definir chunking, se necessário.**
7. **Definir vector store, se necessário.**
8. **Documentar arquitetura final.**
9. **Definir critérios de monitoramento.**
10. **Registrar decisões rejeitadas e motivos.**

**Como fazer:**

Escolher a alternativa que satisfaça os requisitos do projeto com menor complexidade necessária. Não adicionar componentes cuja necessidade não tenha sido demonstrada.

**Resultado esperado:**

Uma arquitetura de embeddings/retrieval formalmente documentada, apoiada por métricas e pronta para implementação produtiva.

**Definition of Done:**

- [ ] Estratégia de representação escolhida.
- [ ] Modelo de embedding escolhido.
- [ ] Estratégia de chunking definida ou explicitamente considerada desnecessária.
- [ ] Vector store escolhido ou decisão documentada de não utilizá-lo ainda.
- [ ] Métricas de qualidade registradas.
- [ ] Custos/latência avaliados.
- [ ] Estratégia de atualização/reindexação definida.
- [ ] Arquitetura documentada.
- [ ] Alternativas rejeitadas possuem justificativa.

**Entregáveis:**

- Documento de arquitetura.
- Matriz de decisão.
- Configuração da estratégia escolhida.
- Métricas finais.
- Plano de implementação da próxima fase.

**Dependências para a próxima fase:**

A implementação definitiva do índice e do pipeline de retrieval só deve começar após esta sprint.

---

## 4. Decisões que devem ser adiadas

As seguintes decisões não devem ser fechadas agora:

### Modelo definitivo de embeddings

Depende dos resultados de qualidade da representação semântica e do baseline.

### Chunking definitivo

A necessidade de chunking depende do tamanho, estrutura e comportamento dos documentos na avaliação.

### Vector database definitivo

A documentação atual cita alternativas, mas não estabelece uma escolha definitiva. A escolha deve considerar qualidade, latência, operação e complexidade após os experimentos.

### Retrieval híbrido

Não deve ser adotado automaticamente. Primeiro deve ser medido se a recuperação vetorial é suficiente e onde o baseline falha.

### Estratégia final de RAG

A forma como o LLM receberá os candidatos deve ser definida depois que a qualidade do retrieval for conhecida.

### Otimização de infraestrutura

Escalabilidade, particionamento e otimizações prematuras devem ficar para depois da validação da qualidade.

---

## 5. Riscos e pontos de atenção

### 5.1. Identidade baseada em nome científico

Nomes podem sofrer alterações taxonômicas. O `species_id` deve permanecer a identidade interna.

### 5.2. Falsos matches

Um fuzzy match incorreto é potencialmente mais prejudicial que um registro não resolvido, pois contamina o Golden Record.

### 5.3. Conflitos taxonômicos

A divergência observada entre AVONET e WikiAves para `Rhea americana` demonstra que a taxonomia precisa de uma política explícita.

### 5.4. Ruído da normalização semântica

A camada atual contém conceitos duplicados, flexões e frases. Esse conteúdo não deve ser diretamente tratado como vocabulário semântico final.

### 5.5. Proveniência insuficiente

`_audit` registra a transformação por LLM, mas a consolidação precisa também registrar a origem dos dados utilizados.

### 5.6. Campos vazios no Golden Record

Campos vazios apesar da existência do dado em outra collection são sinal de consolidação incompleta.

### 5.7. Embedding de dados ruins

Um embedding não corrige problemas de qualidade. Ele pode apenas representar semanticamente o ruído.

### 5.8. Avaliação insuficiente

Sem dataset de avaliação e métricas, a escolha de embeddings e retrieval seria essencialmente subjetiva.

---

## 6. Critério para avançar entre fases

### Fase atual → Fase de Retrieval

A base só deve avançar para experimentação de retrieval quando:

- [ ] identidade das espécies estiver resolvida;
- [ ] Entity Resolution estiver mensurado;
- [ ] contrato de Data Fusion estiver documentado;
- [ ] Golden Record puder ser regenerado;
- [ ] ocorrência estiver integrada quando disponível;
- [ ] identificadores externos estiverem resolvidos ou classificados;
- [ ] conflitos taxonômicos estiverem resolvidos ou explicitamente marcados;
- [ ] provenance estiver disponível;
- [ ] Data Quality possuir métricas;
- [ ] registros inadequados estiverem separados;
- [ ] existir um conjunto de espécies aptas para experimentação.

### Fase de Retrieval → Arquitetura definitiva

Só avançar quando:

- [ ] existir dataset de avaliação;
- [ ] baseline estiver mensurado;
- [ ] representações alternativas tiverem sido testadas;
- [ ] embeddings tiverem resultados comparáveis;
- [ ] casos difíceis tiverem sido analisados;
- [ ] custo e latência tiverem sido considerados;
- [ ] decisão de chunking estiver fundamentada;
- [ ] escolha do vector store estiver fundamentada;
- [ ] estratégia final estiver documentada.

---

# Próxima ação concreta

A execução deve começar pela **Sprint 1 — Contrato de Identidade das Espécies**.

O primeiro trabalho concreto não é alterar a `canonical_species`. É:

1. inventariar os identificadores existentes em `avonet`, `wikiaves`, `ebird`, `ocorrencias_especies` e `canonical_species`;
2. medir duplicidades e inconsistências;
3. definir o schema de `species_registry`;
4. documentar as regras de identidade;
5. gerar o primeiro relatório de cobertura.

Somente depois desse resultado deve-se iniciar o Entity Resolution entre as fontes.
