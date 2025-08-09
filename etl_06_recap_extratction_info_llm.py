from prompts.food_llm import formatted_food_prompt
from prompts.behavior import formatted_behavior_prompt
from prompts.habitat_llm import formatted_habitat_prompt
from prompts.morphology_llm import formatted_morphology_prompt

from time import sleep

import requests
import json
import os
import re
import ast


def string_to_dict(string_input):
    try:
        if 'json' in string_input:
            match = re.search(
                r'```json\s*(.*?)\s*```', string_input, re.DOTALL
            )
            content = match.group(1)

            string_clean = re.sub(r'^```json\n|\n```$', '', content.strip())
            string_clean = string_clean.replace('\\', ' ')
            string_clean = string_clean.replace('...', '')
        else:
            string_clean = string_input.replace('\\', ' ')
            string_clean = string_clean.replace('...', '')

        try:
            string_json = json.loads(string_clean)
        except json.JSONDecodeError:
            string_json = ast.literal_eval(string_clean)
        return string_json
    except Exception as e:
        print(e)
        return {}


def save_resut(path_json, data):
    with open(
        path_json,
        "w",
        encoding="utf-8"
    ) as jsonfile:
        json.dump(data, jsonfile, ensure_ascii=False, indent=2)


def get_info_llm(model, prompt):
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
    response.raise_for_status()

    return response.json()["choices"][0]["message"]["content"]


def verify_rate_limit_llm(response):
    # TPM
    rate_token = response.headers.get("x-ratelimit-remaining-tokens")
    print(rate_token)
    # RPD
    rate_requests = response.headers.get(
        "x-ratelimit-remaining-requests"
    )
    print(rate_requests)
    # RPD
    rate_reset_requests = response.headers.get(
        "x-ratelimit-reset-requests"
    )
    print(rate_reset_requests)
    # TPM
    rate_reset_tokens = response.headers.get(
        "x-ratelimit-reset-tokens"
    )
    print(rate_reset_tokens)
    retry_after = response.headers.get("retry-after")
    print(retry_after)


RPM = 30
RPD = 14400
TPM = 15000
TPD = 500000

if __name__ == "__main__":
    path_json = "data/treat/dedup2_result_scraper_wikiaves_udi.json"
    model = "llama-3.1-8b-instant"

    with open(path_json) as file:
        list_birds = json.load(file)

    j = 0
    n = len(list_birds)
    should_stop = False
    for i, bird in enumerate(list_birds):
        try:
            tax = bird.get("taxonomia")
            order = bird.get("ordem")
            family = bird.get("familia")
            genre = bird.get("genero")
            specie = bird.get("especie")
            feature = bird.get("caracteristicas")
            food = bird.get("alimentacao")
            geo = bird.get("dist_geo")
            habit = bird.get("habitos")

            print(f"{i+1}/{n} - {tax}")

            if all(
                [
                    bird.get("bico", None) is None,
                    bird.get("asa", None) is None,
                    bird.get("pata", None) is None,
                    bird.get("cores", None) is None,
                    bird.get("tamanho", None) is None
                ]
            ):

                prompt_mor = formatted_morphology_prompt(
                    order, family, genre,
                    specie, feature, food
                )

                return_mor_llm = get_info_llm(model, prompt_mor)
                morfolofia = string_to_dict(return_mor_llm)

                bird["bico"] = morfolofia.get("bico", None)
                bird["asa"] = morfolofia.get("asa", None)
                bird["pata"] = morfolofia.get("pata", None)
                bird["cores"] = morfolofia.get("cores", None)
                bird["tamanho"] = morfolofia.get("tamanho", None)

                print("- Get information morphology for bird")

                sleep(25)
            else:
                print("- Information morphology for bird is exists")

            if all(
                [
                    bird.get("dieta_principal", None) is None,
                ]
            ):

                prompt_food = formatted_food_prompt(
                    order, family, genre,
                    specie, feature, food
                )

                return_food_llm = get_info_llm(model, prompt_food)
                food_llm = string_to_dict(return_food_llm)

                bird["tipo"] = food_llm.get("tipo", None)
                bird["dieta_principal"] = food_llm.get("itens", None)

                print("- Get information food for bird")

                sleep(25)
            else:
                print("- Information food for bird is exists")

            if bird.get("habitat", None) is None:

                prompt_hab = formatted_habitat_prompt(
                    order, family, genre,
                    specie, geo, habit
                )

                return_hab_llm = get_info_llm(model, prompt_hab)
                habitat_llm = string_to_dict(return_hab_llm)
                bird["habitat"] = habitat_llm.get("habitat", None)

                print("- Get information habitat for bird")

                sleep(25)
            else:
                print("- Information habitat for bird is exists")

            if all(
                [
                    bird.get("locomocao", None) is None,
                    bird.get("sociabilidade", None) is None,
                    bird.get("atividade", None) is None
                ]
            ):

                prompt_beh = formatted_behavior_prompt(
                    order, family, genre,
                    specie, feature, habit
                )

                return_beh_llm = get_info_llm(model, prompt_beh)
                behavior_llm = string_to_dict(return_beh_llm)

                bird["locomocao"] = behavior_llm.get("locomocao", None)
                bird["sociabilidade"] = behavior_llm.get("sociabilidade", None)
                bird["atividade"] = behavior_llm.get("atividade", None)

                print("- Get information behavior for bird")

                sleep(10)

                j += 1
            else:
                print("- Information behavior for bird is exists")

            if j == 100:
                should_stop = True

        except requests.exceptions.HTTPError as err:
            print(f"HTTP Error: {err}")
            print(f"Status code: {err.response.status_code}")
            print(f"Response text: {err.response.text}")
            should_stop = True
        except requests.exceptions.RequestException as err:
            print(f"Other Request Error: {str(err)}")
            should_stop = True
        except Exception as err:
            print(f"Other Error: {str(err)}")
            should_stop = True
        finally:
            save_resut(path_json, list_birds)

        if should_stop:
            break
