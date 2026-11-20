from pathlib import Path

import yaml


class PromptManager:
    def __init__(self, prompts_dir: str = "data/prompts"):
        self.prompts_dir = Path(prompts_dir)

    def get_prompt(self, prompt_id: str) -> dict:
        """Carrega e retorna o conteúdo do prompt a partir do YAML."""
        prompt_path = self.prompts_dir / f"{prompt_id}.yaml"
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt '{prompt_id}' não encontrado em {prompt_path}")

        with open(prompt_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return {
            "name": data.get("name", prompt_id),
            "version": data.get("version", "unknown"),
            "model": data.get("model", "gemini-1.5-flash"),
            "system_prompt": data.get("system_prompt", ""),
        }
