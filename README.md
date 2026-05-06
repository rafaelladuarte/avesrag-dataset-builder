# 🐦 Extração e Tratamento de Dados de Aves Brasileiras

Este repositório contém scripts Python desenvolvidos para realizar a extração, tratamento e enriquecimento de dados sobre aves brasileiras, com foco na construção de um dataset estruturado com informações taxonômicas, morfológicas e ecológicas. O dataset resultante é utilizado como base para o projeto **AvesRAG**, desenvolvido como projeto final do curso **LLM Zoomcamp** da DataTalks Club.

## 📌 Objetivo

Criar um dataset consolidado e enriquecido com dados de diversas fontes confiáveis, permitindo a aplicação de técnicas de Recuperação de Informação com LLMs (RAG) para identificação de espécies de aves com base em descrições fornecidas por usuários.


## 🗂️ Fontes de Dados

### 1. Lista comentada das aves do Brasil pelo Comitê Brasileiro de Registros Ornitológicos (CBRO) (2021)

* **Conteúdo**: Lista taxonómica actualizada das aves do Brasil com status de ocorrência, subespécies presentes e notas explicativas para cada espécie; cobre 1 971 espécies na “Lista Primária” no país.
* **Característica principal**: Uma referência oficial e abrangente para a avifauna brasileira, útil para base taxonômica, harmonização de listas e identificação de quais espécies viveram ou vivem no país.
* **Link**: https://zenodo.org/records/5138368


### 2. AVONET: morphological, ecological and geographical data for all birds (2022)

* **Conteúdo**: Dados de traços funcionais de aves ao nível global,  inclui aproxuimadamente 11.000 espécies vivas, com aproximadamanete 90.000 indivíduos medidos em 181 países. Contém 11 variáveis contínuas morfológicas (por ex., medidas de bico, asa, cauda, tarso), com mais de 6 variáveis ecológicas e distribuição geográfica e tamanho da faixa. 
* **Característica principal**: Um dos conjuntos de dados mais completos de traços de aves vivas para macroecologia e macroevolução, que permite integração com filogenias globais, mapas de distribuição, listas da IUCN etc.
* **Link**: https://onlinelibrary.wiley.com/doi/10.1111/ele.13898

### 3. BIRDBASE: A Global Dataset of Avian Biogeography, Conservation, Ecology and Life History Traits (2025)

* **Conteúdo**: Dataset global de traços ecológicos e de história de vida para aproximadamente 11.000 espécies de aves (em 254 famílias) cobrindo 78 variáveis (morfologia, habitat, dieta, reprodução, mobilidade etc). 
* **CCaracterística principal**: A base mais atual e abrangente que cobre todas as espécies reconhecidas por cinco taxonomias principais de aves, com amplo escopo para aplicações em conservação, macroecologia e biogeografia.
* **Link**: https://springernature.figshare.com/articles/dataset/BIRDBASE_A_Global_Database_of_Avian_Biogeography_Conservation_Ecology_and_Life_History_Traits/27051040

### 4. WikiAves – A Enciclopédia das Aves do Brasil

* **Conteúdo**: Plataforma colaborativa que reúne registros fotográficos e sonoros de aves que ocorrem no Brasil (aproximadamente 1.970 espécies), com informações taxonômicas, mapas de ocorrência, busca por estado/município, além de ferramentas de identificação e interação entre observadores. 
* **Característica principal**: Ciência cidadã aplicada à ornitologia brasileira — permite que usuários contribuam com fotos/sons, editem páginas wiki para espécies, e consultem dados de distribuição e diversidade da avifauna nacional, tornando-se uma base dinâmica e comunitária.
* **Link**: https://www.wikiaves.com.br/

## 🔧 Etapas do Pipeline

1. **Extração Taxonômica**: Leitura, parsing e organização da lista oficial de espécies brasileiras.

2. **Web Scraping (WikiAves)**: Scripts automatizados para coleta de descrições por espécie diretamente do site WikiAves.

3. **Merge e Tratamento Inicial**: Consolidação entre as bases (CBRO + WikiAves) com tratamento de duplicatas e limpeza textual.

4. **Extração de Atributos com LLM**: Uso de modelo de linguagem (Gemma 2 9B - via API da [GROQ](https://groq.com)) para identificar e extrair automaticamente as seguintes características a partir das descrições:

   * Tipo de bico
   * Formato da asa
   * Tipo de alimentação
   * Hábitat
   * Forma de locomoção
   * Atividade (diurna/noturna/etc.)
   * Entre outros atributos morfoecológicos

5. **Parametrização, Normalização e Validação**

   * Padronização das categorias retornadas pela LLM
   * Validação manual e semiautomática (em progresso) dos dados gerados

## ⚠️ Observações Importantes

* A **validação dos dados extraídos via LLM** está sendo feita de forma **gradual**, com foco em garantir consistência e aplicabilidade ao projeto AvesRAG.

## 🧪 Aplicação: Projeto AvesRAG

O dataset gerado por este pipeline será utilizado no **AvesRAG**, um sistema baseado em LLM + RAG (Retrieval-Augmented Generation) para auxiliar usuários a identificar espécies de aves brasileiras com base em descrições textuais. Este projeto faz parte da entrega final do curso **LLM Zoomcamp: A Free Course on Real-Life Applications of LLMs**, curso promovido pela comunidade **DataTalks Club**.



## 📁 Estrutura do Repositório

```bash
├── data/
│   ├── raw/                   
│   ├── treat/                  
│   └── oficial/                
├── scripts/                    
├── docs/
├── notebooks/      
├── README.md
└── requirements.txt
```
