from scr.llm.client import GeminiClient
from scr.llm.schemas import P01Morfologia


class EnrichmentPipeline:
    def __init__(self):
        self.client = GeminiClient()

    def step_1_extract_morphology(self, raw_text: str) -> dict:
        """
        Etapa 1: Extração (P01)
        """
        return self.client.extract_structured(
            prompt_id="p01_morfologia", text=raw_text, schema=P01Morfologia
        )

    def process_species(self, wikiaves_doc: dict) -> dict:
        """
        Roda todas as etapas do pipeline para uma espécie.
        """
        # 1. Extração
        caracteristicas = wikiaves_doc.get("caracteristicas", "")
        morfologia = self.step_1_extract_morphology(caracteristicas) if caracteristicas else {}

        # TODO: Implementar P02 (Alimentação), P03 (Hábitos), etc.
        # ...

        # Retorno consolidado
        return {
            "morfologia": morfologia,
            # "alimentacao": ...
        }
