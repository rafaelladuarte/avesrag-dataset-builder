def formatted_habitat_prompt(
        order: str = None, family: str = None,
        genre: str = None, specie: str = None,
        geo: str = None, habit: str = None
) -> str:

    example_output = {
        "habitat": []
    }
    prompt = f"""
        [INSTRUÇÃO]
        Você é um ornitólogo especializado em morfologia de aves. Sua tarefa é
        extrair características sobre o habitat da ave a partir de um texto
        descritivo, preenchendo os campos abaixo com base nas categorias
        pré-definidas.

        ⚠️ IMPORTANTE: Todas as classificações devem ser escolhidas
        **exclusivamente entre os tipos listados abaixo**.
        Se a informação não estiver presente ou não puder ser inferida com
        base no texto e na taxonomia da ave, retorne uma **string vazia `""`**.

        ### Categorias disponíveis:

        * **bico** (escolha apenas um):
        - *cerrado*
        - *pampa*
        - *campo natural*
        - *plantação*
        - *floresta aberta*
        - *mata ciliar*
        - *área urbana*
        - *área alagada*
        - *brejo*
        - *savana*
        - *pantanal*
        - *caatinga*

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
        {habit}
        {geo}

        [SAÍDA ESPERADA]
        ⚠️ A resposta deve ser exclusivamente no formato JSON abaixo,
        sem nenhum texto adicional antes ou depois:
        ```json
        {str(example_output)}
        ```
    """

    return prompt
