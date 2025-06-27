def formatted_behavior_prompt(
        order: str = None, family: str = None,
        genre: str = None, specie: str = None,
        feature: str = None, habit: str = None
) -> str:

    example_output = {
        "locomocao": "...",
        "sociabilidade": "...",
        "atividade": ["..."]
    }
    prompt = f"""
        [INSTRUÇÃO]
        Você é um ornitólogo especializado em morfologia de aves. Sua tarefa é
        extrair características sobre o comportamento da ave a partir de um
        texto descritivo, preenchendo os campos abaixo com base nas categorias
        pré-definidas.

        ⚠️ IMPORTANTE: Todas as classificações devem ser escolhidas
        **exclusivamente entre os tipos listados abaixo**.
        Se a informação não estiver presente ou não puder ser inferida com
        base no texto e na taxonomia da ave, retorne uma **string vazia `""`**.

        ### Categorias disponíveis:

        * **locomocao** (escolha um):
        - *voadora*
        - *corredora*
        - *nadadora*
        - *trepadora*

        * **sociabilidade** (escolha um):
        - *solitária*
        - *gregária*
        - *territorial*

        * **atividade** (lista):
        - *diurna*
        - *noturna*
        - *crepuscular*

        ### Formato da resposta (JSON obrigatório):
        ```json
        {str(example_output)}
        ````
        [CONTEXTO]
        Ordem: {order}
        Família: {family}
        Gênero: {genre}
        Espécie: {specie}

        Texto descritivo:
        {feature}
        {habit}

        [SAÍDA ESPERADA]
        ⚠️ A resposta deve ser exclusivamente no formato JSON abaixo,
        sem nenhum texto adicional antes ou depois:
        ```json
        {str(example_output)}
        ```
    """
    return prompt
