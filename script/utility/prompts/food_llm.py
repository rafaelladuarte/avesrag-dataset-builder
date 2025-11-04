def formatted_food_prompt(
        order: str = None, family: str = None,
        genre: str = None, specie: str = None,
        feature: str = None, food: str = None
) -> str:

    example_output = {
        "tipo": "...",
        "itens": ["...", "..."]
        }

    prompt = f"""
        [INSTRUÇÃO]
        Você é um ornitólogo especializado em ecologia alimentar de aves.
        Sua tarefa é extrair o tipo de alimentação da ave a partir de um texto
        descritivo, preenchendo os campos abaixo com base nas categorias
        pré-definidas.

        ⚠️ IMPORTANTE: Todas as classificações devem ser escolhidas
        **exclusivamente entre os tipos listados abaixo**.
        Se a informação não estiver presente ou não puder ser inferida com
        base no texto e na taxonomia da ave, retorne uma **string vazia `""`**.

        ### Categorias válidas:

        * **tipo** (escolha apenas um):
        - *herbívoro*:
            Alimenta-se principalmente de partes vegetais como folhas, brotos,
            flores e caules.
        - *frugívoro*:
            Tem dieta baseada em frutas. Pode engolir frutos inteiros ou
            apenas partes moles.
        - *granívoro*:
            Especializado em sementes e grãos. Possui bico adaptado para
            quebrá-las.
        - *insetívoro*:
            Come principalmente insetos e outros artrópodes.
            Frequentemente caçam em voo, troncos ou solo.
        - *carnívoro*:
            Preda animais vertebrados como roedores, répteis,
            anfíbios ou outras aves.
        - *onívoro*:
            Dieta variada, inclui itens de origem vegetal e animal.
            Grande flexibilidade alimentar.

        * **itens** (lista curta com substantivos simples):
        Exemplo: ["frutas", "sementes", "insetos", "roedores"]

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
        {food}

        [SAÍDA ESPERADA]
        ⚠️ A resposta deve ser exclusivamente no formato JSON abaixo,
        sem nenhum texto adicional antes ou depois:
        ```json
        {str(example_output)}
        ```
    """

    return prompt
