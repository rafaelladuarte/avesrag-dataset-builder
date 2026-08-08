import json

from scr.llm.client import GeminiClient
from scr.llm.schemas import (
    P01Morfologia,
    P02Alimentacao,
    P03Habitos,
    P04Reproducao,
    P05NormalizacaoSemantica,
    P06PadronizacaoMedidas,
    P07PadronizacaoTaxonomica,
    P08EstruturaCanonica,
)


class EnrichmentPipeline:
    def __init__(self):
        self.client = GeminiClient()

    def step_1_extract_morfologia(self, raw_text: str) -> dict:
        return self.client.extract_structured(
            prompt_id="p01_morfologia", text=raw_text, schema=P01Morfologia
        )

    def step_1_extract_alimentacao(self, raw_text: str) -> dict:
        return self.client.extract_structured(
            prompt_id="p02_alimentacao", text=raw_text, schema=P02Alimentacao
        )

    def step_1_extract_habitos(self, raw_text: str) -> dict:
        return self.client.extract_structured(
            prompt_id="p03_habitos", text=raw_text, schema=P03Habitos
        )

    def step_1_extract_reproducao(self, raw_text: str) -> dict:
        return self.client.extract_structured(
            prompt_id="p04_reproducao", text=raw_text, schema=P04Reproducao
        )

    def step_2_normalize_semantic(self, raw_data_str: str) -> dict:
        return self.client.extract_structured(
            prompt_id="p05_normalizacao_semantica",
            text=raw_data_str,
            schema=P05NormalizacaoSemantica,
        )

    def step_2_normalize_measurements(self, text_with_measures: str) -> dict:
        return self.client.extract_structured(
            prompt_id="p06_padronizacao_medidas",
            text=text_with_measures,
            schema=P06PadronizacaoMedidas,
        )

    def step_2_normalize_taxonomy(self, raw_taxonomy: str) -> dict:
        return self.client.extract_structured(
            prompt_id="p07_padronizacao_taxonomica",
            text=raw_taxonomy,
            schema=P07PadronizacaoTaxonomica,
        )

    def step_5_canonical_structure(self, combined_data_str: str) -> dict:
        return self.client.extract_structured(
            prompt_id="p08_estrutura_canonica", text=combined_data_str, schema=P08EstruturaCanonica
        )

    def process_species(self, wikiaves_doc: dict) -> dict:
        """
        Roda todas as etapas do pipeline para uma espécie.
        """
        # Textos crus do WikiAves
        txt_caracteristicas = wikiaves_doc.get("caracteristicas", "")
        txt_alimentacao = wikiaves_doc.get("alimentacao", "")
        txt_habitos = wikiaves_doc.get("habitos", "")
        txt_reproducao = wikiaves_doc.get("reproducao", "")
        classificacao_cient = wikiaves_doc.get("classificacao_cientifica", {})

        # Etapa 1: Extração (Raw)
        morfologia = (
            self.step_1_extract_morfologia(txt_caracteristicas) if txt_caracteristicas else {}
        )
        alimentacao = self.step_1_extract_alimentacao(txt_alimentacao) if txt_alimentacao else {}
        habitos = self.step_1_extract_habitos(txt_habitos) if txt_habitos else {}
        reproducao = self.step_1_extract_reproducao(txt_reproducao) if txt_reproducao else {}

        species_raw = {
            "morfologia": morfologia,
            "alimentacao": alimentacao,
            "habitos": habitos,
            "reproducao": reproducao,
        }

        # Etapa 2: Normalização
        # Semântica
        semantic_normalized = self.step_2_normalize_semantic(
            json.dumps(species_raw, ensure_ascii=False)
        )

        # Medidas
        measurements_normalized = (
            self.step_2_normalize_measurements(txt_caracteristicas) if txt_caracteristicas else {}
        )

        # Taxonomia
        taxonomy_normalized = (
            self.step_2_normalize_taxonomy(json.dumps(classificacao_cient, ensure_ascii=False))
            if classificacao_cient
            else {}
        )

        species_normalized = {
            "semantica": semantic_normalized,
            "medidas": measurements_normalized,
            "taxonomia": taxonomy_normalized,
        }

        # Etapa 5: Síntese Canônica (P08)
        # Passamos a união do Raw com o Normalized
        combined_data = {"raw": species_raw, "normalized": species_normalized}
        canonical = self.step_5_canonical_structure(json.dumps(combined_data, ensure_ascii=False))

        # Retorno consolidado com todas as camadas
        return {
            "species_raw": species_raw,
            "species_normalized": species_normalized,
            "canonical_species": canonical,
        }
