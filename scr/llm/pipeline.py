from scr.llm.client import GeminiClient
from scr.llm.schemas import P01Morfologia, P02Alimentacao, P03Habitos, P04Reproducao


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

    def process_species(self, wikiaves_doc: dict) -> dict:
        """
        Roda todas as etapas do pipeline para uma espécie.
        """
        # Textos crus do WikiAves
        txt_caracteristicas = wikiaves_doc.get("caracteristicas", "")
        txt_alimentacao = wikiaves_doc.get("alimentacao", "")
        txt_habitos = wikiaves_doc.get("habitos", "")
        txt_reproducao = wikiaves_doc.get("reproducao", "")

        # Etapa 1: Extração (Raw)
        morfologia = (
            self.step_1_extract_morfologia(txt_caracteristicas) if txt_caracteristicas else {}
        )
        alimentacao = self.step_1_extract_alimentacao(txt_alimentacao) if txt_alimentacao else {}
        habitos = self.step_1_extract_habitos(txt_habitos) if txt_habitos else {}
        reproducao = self.step_1_extract_reproducao(txt_reproducao) if txt_reproducao else {}

        # Retorno consolidado (SpeciesRaw)
        return {
            "morfologia": morfologia,
            "alimentacao": alimentacao,
            "habitos": habitos,
            "reproducao": reproducao,
        }
