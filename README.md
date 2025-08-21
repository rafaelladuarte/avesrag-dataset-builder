
# 🐦 Extração e Tratamento de Dados de Aves Brasileiras

Este repositório contém scripts Python desenvolvidos para realizar a extração, tratamento e enriquecimento de dados sobre aves brasileiras, com foco na construção de um dataset estruturado com informações taxonômicas, morfológicas e ecológicas. O dataset resultante é utilizado como base para o projeto **AvesRAG**, desenvolvido como projeto final do curso **LLM Zoomcamp** da DataTalks Club.

## 📌 Objetivo

Criar um dataset consolidado e enriquecido com dados de diversas fontes confiáveis, permitindo a aplicação de técnicas de Recuperação de Informação com LLMs (RAG) para identificação de espécies de aves com base em descrições fornecidas por usuários.

---

## 🗂️ Fontes de Dados

### 1. Taxonomia - Lista Comentada das Aves do Brasil (CBRO - 2ª edição)

* Fonte: Zenodo / Ornithology Research
* DOI: [10.1007/s43388-021-00058-x](https://doi.org/10.1007/s43388-021-00058-x)
* Citação recomendada:

  > Pacheco, J.F. et al. (2021). Annotated checklist of the birds of Brazil by the Brazilian Ornithological Records Committee – second edition. *Ornithology Research*, 29(2).

Essa lista foi utilizada para obter a base taxonômica das espécies de aves reconhecidas oficialmente no Brasil.

---

### 2. Descrições - WikiAves

* Site: [https://www.wikiaves.com.br](https://www.wikiaves.com.br)
* Técnica: Web Scraping
* Conteúdo extraído: descrições morfológicas, comportamentais e ecológicas de espécies selecionadas.

---

## 🔧 Etapas do Pipeline

1. **Extração Taxonômica (CBRO)**
   Leitura, parsing e organização da lista oficial de espécies brasileiras.

2. **Web Scraping (WikiAves)**
   Scripts automatizados para coleta de descrições por espécie diretamente do site WikiAves.

3. **Merge e Tratamento Inicial**
   Consolidação entre as bases (CBRO + WikiAves) com tratamento de duplicatas e limpeza textual.

4. **Extração de Atributos com LLM**
   Uso de modelo de linguagem (Gemma 2 9B - via API da [GROQ](https://groq.com)) para identificar e extrair automaticamente as seguintes características a partir das descrições:

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

---

## ⚠️ Observações Importantes

* **AVONET**: foi testada como possível fonte de atributos morfológicos, mas descartada por conter apenas registros de espécies extintas ou fósseis.
* A **validação dos dados extraídos via LLM** está sendo feita de forma **gradual**, com foco em garantir consistência e aplicabilidade ao projeto AVESrag.

---

## 🧪 Aplicação: Projeto AVESrag

O dataset gerado por este pipeline será utilizado no **AvesRAG**, um sistema baseado em LLM + RAG (Retrieval-Augmented Generation) para auxiliar usuários a identificar espécies de aves brasileiras com base em descrições textuais. Este projeto faz parte da entrega final do curso **LLM Zoomcamp: A Free Course on Real-Life Applications of LLMs**, curso promovido pela comunidade **DataTalks Club**.

---

## 📁 Estrutura do Repositório

```bash
├── data/
│   ├── raw/                    # Dados brutos (CBRO, HTMLs do WikiAves, etc)
│   ├── treat/                  # Dados tratados e enriquecidos
│   ├── oficial/                # Dados normalizados e validados
├── scripts/                    # Scripts e Notebooks de extração, tratamento e validação dos dados.
├── README.md
└── requirements.txt
```
