from time import sleep

import requests
import json
import os


def save_resut(path_json, data):
    with open(
        path_json,
        "w",
        encoding="utf-8"
    ) as jsonfile:
        json.dump(data, jsonfile, ensure_ascii=False, indent=2)


def formatted_prompt(
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
    **exclusivamente entre os tipos listados abaixo**.
    Se a informação não estiver presente ou não puder ser inferida com base no
    texto e na taxonomia da ave, retorne uma **string vazia `""`**.

    ### Categorias disponíveis:

    * **bico** (escolha apenas um):
    - *Generalista*: bico versátil, para dieta variada.
    - *Insetívoro*: fino, para capturar insetos.
    - *Granívoro*: grosso e curto, para sementes.
    - *Nectarívoro*: longo e fino, para sugar néctar.
    - *Frugívoro*: adaptado para comer frutos.
    - *Insetos em troncos*: rígido e pontiagudo, para perfurar madeira.
    - *Rede de Pesca*: com ramificações para coar água.
    - *Pescador de superfície*: reto, para capturar presas na água.
    - *Limícola*: longo e reto ou curvado, para explorar lama.
    - *Sondador*: longo e fino, para sondar o solo.
    - *Filtrador*: adaptado para filtrar pequenos organismos.
    - *Pescador*: forte, reto ou com gancho, para capturar peixes.
    - *Mergulhador*: adaptado para pescar em mergulho.
    - *Carniceiro*: forte e encurvado, para rasgar carne.
    - *Raptorial*: curvo e afiado, típico de aves de rapina.

    * **asa** (escolha apenas uma):
    - *Planeio ascendente dinâmico*:
        asas longas e estreitas para voos longos sobre o mar.
    - *Elíptica*:
        asas curtas e arredondadas, ideal para manobras.
    - *Alto coeficiente de proporcionalidade*:
        asas longas, ideais para voo sustentado.
    - *Grande sustentação*:
        asas largas, para planar com eficiência.

    * **pata** (escolha apenas uma):
    - *Anizodáctilo*: 3 dedos voltados para frente e 1 para trás.
    - *Zigodáctilo*: 2 dedos para frente e 2 para trás (ex: pica-paus).
    - *Pernalta*: pernas longas, adaptadas a ambientes aquáticos rasos.
    - *Palmada*: com membranas para nadar.

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


RPM = 30
RPD = 14400
TPM = 15000
TPD = 500000

if __name__ == "__main__":
    path_json = "result_llm_wikiaves_udi.json"
    model = "gemma2-9b-it"

    with open(path_json) as file:
        list_birds = json.load(file)

    j = 0
    n = len(list_birds)
    for i, bird in enumerate(list_birds):
        tax = bird.get("taxonomia")
        print(f"{i}/{n} - {tax}")

        if bird.get("morfologia_llm", None) is None:

            prompt = formatted_prompt(
                order=bird.get("ordem"),
                family=bird.get("familia"),
                genre=bird.get("genero"),
                specie=bird.get("especie"),
                feature=bird.get("caracteristicas"),
                food=bird.get("alimentacao")
            )

            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {os.getenv("GROQ_API_KEY")}",
                "Content-Type": "application/json"
            }
            data = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}]
            }

            response = requests.post(url, headers=headers, json=data)

            if response.status_code == 200:
                bird["morfologia_llm"] = response.json()[
                    "choices"
                ][0]["message"]["content"]
            else:
                with open(
                    path_json,
                    "w",
                    encoding="utf-8"
                ) as jsonfile:
                    json.dump(
                        list_birds, jsonfile, ensure_ascii=False, indent=2
                    )
                raise

            j += 1
            print("Get information for bird")

            # # TPM
            # rate_token = response.headers.get("x-ratelimit-remaining-tokens")
            # print(rate_token)
            # # RPD
            # rate_requests = response.headers.get(
            #     "x-ratelimit-remaining-requests"
            # )
            # print(rate_requests)
            # # RPD
            # rate_reset_requests = response.headers.get(
            #     "x-ratelimit-reset-requests"
            # )
            # print(rate_reset_requests)
            # # TPM
            # rate_reset_tokens = response.headers.get(
            #     "x-ratelimit-reset-tokens"
            # )
            # print(rate_reset_tokens)
            # retry_after = response.headers.get("retry-after")
            # print(retry_after)

            sleep(20)

        else:
            print("Information for bird is exists")

        if j == 30:
            with open(
                path_json,
                "w",
                encoding="utf-8"
            ) as jsonfile:
                json.dump(list_birds, jsonfile, ensure_ascii=False, indent=2)
            j = 0

    with open(
        path_json,
        "w",
        encoding="utf-8"
    ) as jsonfile:
        json.dump(list_birds, jsonfile, ensure_ascii=False, indent=2)
