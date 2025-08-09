def formatted_resume_prompt(
    taxonomia: str, specie: str,
    feature: str, food: str,
    geo: str, habitat: str, rep: str
):
    prompt = f"""
    Você é um especialista em aves e está atuando como redator científico em
    língua portuguesa. Abaixo estão informações descritivas sobre uma espécie
    de ave, incluindo suas características físicas, alimentação, reprodução,
    hábitos, distribuição geográfica e habitat.

    Sua tarefa é gerar um **resumo objetivo, claro e informativo em um único parágrafo**,
    capturando os principais pontos da espécie de forma natural e impessoal.
    **Não copie trechos do texto original** e **responda exclusivamente em português**,
    mesmo que o modelo tenha sido treinado em outra língua. Seja direto,
    mas mantenha um tom científico.

    ## Texto:
    Taxonomia: {taxonomia}
    Espécie: {specie}
    Característica: {feature}
    Alimentação: {food}
    Distribuição Geográfica: {geo}
    Habitat: {habitat}
    Reprodução: {rep}
    """
    return prompt
