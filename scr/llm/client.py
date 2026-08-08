import json
from datetime import datetime, timezone

from google import genai
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

from scr.core.config import settings
from scr.llm.prompt_manager import PromptManager


class GeminiClient:
    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.prompt_manager = PromptManager()

    @retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
    def extract_structured(self, prompt_id: str, text: str, schema: type[BaseModel]) -> dict:
        """
        Gera uma saída estruturada e injeta o bloco de _audit.
        """
        # Carregar configuração do prompt
        prompt_config = self.prompt_manager.get_prompt(prompt_id)
        model_name = prompt_config["model"]

        # Construir o conteúdo final
        full_prompt = f"{prompt_config['system_prompt']}\n\nTexto para análise:\n{text}"

        # Chamar Gemini com schema estruturado
        response = self.client.models.generate_content(
            model=model_name,
            contents=full_prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": schema,
            },
        )

        # Parsear a resposta
        try:
            parsed_data = schema.model_validate_json(response.text)
            data_dict = parsed_data.model_dump()
        except Exception as e:
            # Fallback/Log em caso de falha bizarra
            print(f"Falha ao fazer parse da resposta do Gemini: {e}")
            data_dict = json.loads(response.text) if response.text else {}

        # Injetar bloco de auditoria
        data_dict["_audit"] = {
            "prompt_name": prompt_config["name"],
            "prompt_version": prompt_config["version"],
            "model_name": model_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        return data_dict
