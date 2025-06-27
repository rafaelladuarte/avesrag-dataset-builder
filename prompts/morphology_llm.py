def formatted_morphology_prompt(
        order: str = None, family: str = None,
        genre: str = None, specie: str = None,
        feature: str = None, food: str = None
) -> str:

    example_output = {
        "bico": "",
        "asa": "",
        "pata": "",
        "cores": [],
        "tamanho": ""
    }
    prompt = f"""
        [INSTRUÇÃO]
        Você é um ornitólogo especializado em morfologia de aves. Sua tarefa é
        extrair características morfológicas a partir de um texto descritivo,
        preenchendo os campos abaixo com base nas categorias pré-definidas.

        ⚠️ IMPORTANTE: Todas as classificações devem ser escolhidas
        **exclusivamente entre os tipos listados abaixo**. Se a informação não
        estiver presente ou não puder ser inferida com base no texto e na
        taxonomia da ave, retorne uma **string vazia `""`**.

        ### Categorias disponíveis:

        * **bico** (escolha apenas um):
        - *Generalista*:
            bico de forma intermediária, versátil e adaptado para uma dieta
            variada (frutas, insetos, sementes). Comum em aves oportunistas.
        - *Insetívoro*:
            fino, reto ou levemente curvo, ideal para capturar pequenos
            insetos com precisão, seja no ar, vegetação ou solo.
        - *Granívoro*:
            grosso, forte e geralmente curto, ideal para quebrar
            cascas duras de sementes e grãos.
        - *Nectarívoro*:
            longo, fino e geralmente curvado, especializado em alcançar o
            néctar de flores profundas.
        - *Frugívoro*:
            robusto e adaptado para manipular, esmagar ou engolir frutos
            inteiros ou pedaços de polpa.
        - *Insetos em troncos*:
            rígido, reto e pontiagudo, usado para perfurar cascas e extrair
            insetos escondidos na madeira.
        - *Rede de Pesca*:
            largo e com ramificações ou serrilhas internas, serve para
            pequenos organismos da água, como plâncton.
        - *Pescador de superfície*:
            longo, reto e afilado, eficiente para capturar peixes e pequenos
            animais aquáticos sem mergulho.
        - *Limícola*:
            longo e sensível, geralmente reto ou levemente curvado, usado para
            sondar lama e areia em busca de invertebrados.
        - *Sondador*:
            fino, comprido e sensível ao toque, especializado em encontrar
            presas escondidas sob o solo ou vegetação rala.
        - *Filtrador*:
            adaptado com estruturas como lamelas ou placas para filtrar
            alimento da água ou lama.
        - *Pescador*:
            forte e afiado, reto ou ligeiramente curvo, ideal para capturar e
            segurar peixes escorregadios.
        - *Mergulhador*:
            resistente e afilado, funciona bem embaixo d’água, usado por aves
            que capturam presas durante o mergulho.
        - *Carniceiro*:
            largo, forte e curvado na ponta, usado para rasgar carne em
            carcaças de animais.
        - *Raptorial*:
            curvo, afiado e muito resistente, projetado para capturar e rasgar
            carne de presas vivas.


        * **asa** (escolha apenas uma):
        - *Planeio ascendente dinâmico*:
            asas extremamente longas, estreitas e pontiagudas, com baixa
            curvatura, adaptadas ao voo de longa duração sobre o mar com
            poucos batimentos.
        - *Elíptica*:
            asas curtas, largas e arredondadas, com extremidades digitadas;
            ideais para manobras rápidas em ambientes fechados como florestas
            densas.
        - *Alto coeficiente de proporcionalidade*:
            asas longas e estreitas com alta razão comprimento/largura;
            favorecem voos sustentados e eficientes em planadores terrestres.
        - *Grande sustentação*:
            asas largas e com separação visível entre penas primárias;
            proporcionam voo lento e planar aproveitando correntes térmicas
            ascendentes.


        * **pata** (escolha apenas uma):
        - *Anizodáctilo*:
            três dedos voltados para frente e um para trás, arranjo mais comum
            entre as aves, ideal para empoleiramento e locomoção em solo firme.
        - *Zigodáctilo*:
            dois dedos voltados para frente e dois para trás, formando uma
            pinça; ideal para agarrar superfícies verticais como troncos e
            galhos.
        - *Pernalta*:
            pernas longas e finas, adaptadas para caminhar ou caçar em águas
            rasas; comum em aves aquáticas de ambientes alagados.
        - *Palmada*:
            dedos unidos por membranas interdigitais (pés palmados), próprias
            para natação eficiente em ambientes aquáticos.


        * **cores** (lista):
        Liste todas as cores mencionadas diretamente ou inferíveis da plumagem.
        Exemplo: ["preto", "branco", "cinza"]

        * **tamanho** (escolha apenas um):
        Classifique com base no comprimento médio observado:
        - *Pequeno*: até 30 cm
        - *Médio*: 31 a 90 cm
        - *Grande*: acima de 90 cm

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
