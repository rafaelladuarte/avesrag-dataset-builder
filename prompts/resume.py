def formatted_resume_prompt(
    taxonomia: str, specie: str,
    feature: str, food: str,
    geo: str, habitat: str, rep: str
):
    # prompt = f"""
    # Você é um especialista em aves e está atuando como redator científico em
    # língua portuguesa. Abaixo estão informações descritivas sobre uma espécie
    # de ave, incluindo suas características físicas, alimentação, reprodução,
    # hábitos, distribuição geográfica e habitat.

    # Sua tarefa é gerar um **resumo objetivo, claro e informativo em um único parágrafo**,
    # capturando os principais pontos da espécie de forma natural e impessoal.
    # **Não copie trechos do texto original** e **responda exclusivamente em português**,
    # mesmo que o modelo tenha sido treinado em outra língua. Seja direto,
    # mas mantenha um tom científico.

    # ## Texto:
    # Taxonomia: {taxonomia}
    # Espécie: {specie}
    # Característica: {feature}
    # Alimentação: {food}
    # Distribuição Geográfica: {geo}
    # Habitat: {habitat}
    # Reprodução: {rep}
    # """

    prompt = f"""
    Você é um ornitólogo especializado em redação científica em português brasileiro.
    Sua tarefa é resumir as informações abaixo sobre uma ave **em um único parágrafo objetivo,
    com linguagem clara e impessoal**, seguindo rigorosamente estas regras:

    1. **Idioma**: Responda EXCLUSIVAMENTE em português brasileiro.
    - Proibido incluir caracteres ou palavras em chinês, inglês ou outros idiomas.

    2. **Estilo**: 
    - Mantenha tom científico (evite primeira pessoa e linguagem coloquial).
    - Não copie frases do texto original; paraphraseie com suas próprias palavras.
    - Seja direto, mas inclua todos os aspectos relevantes (habitat, alimentação, reprodução, etc.).

    3. **Formato**:
    - Apenas UM parágrafo (3 a 5 frases).
    - Exemplo de estrutura:
        *"A [Espécie], [breve descrição física], habita [regiões/habitat]. Alimenta-se de [dieta] e reproduz-se [detalhes reprodutivos]. Distribui-se [área geográfica]."*

    ## Dados para resumo:
    Taxonomia: {taxonomia}
    Espécie: {specie}
    Características físicas: {feature}
    Alimentação: {food}
    Distribuição geográfica: {geo}
    Habitat: {habitat}
    Reprodução: {rep}

    **Comece imediatamente com o resumo, sem introduções.**
    """

    return prompt
