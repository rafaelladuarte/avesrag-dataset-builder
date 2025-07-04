from prompts.food_llm import formatted_food_prompt
from prompts.behavior import formatted_behavior_prompt
from prompts.habitat_llm import formatted_habitat_prompt
from prompts.morphology_llm import formatted_morphology_prompt

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
    path_json = "result_llm_wikiaves_udi.json"
    model = "gemma2-9b-it"

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

            if bird.get("morfologia_llm", None) is None:

                prompt_mor = formatted_morphology_prompt(
                    order, family, genre,
                    specie, feature, food
                )

                return_mor_llm = get_info_llm(model, prompt_mor)
                bird["morfologia_llm"] = return_mor_llm

                print("- Get information morphology for bird")

                sleep(25)
            else:
                print("- Information morphology for bird is exists")

            if bird.get("food_llm", None) is None:

                prompt_food = formatted_food_prompt(
                    order, family, genre,
                    specie, feature, food
                )

                return_food_llm = get_info_llm(model, prompt_food)
                bird["food_llm"] = return_food_llm

                print("- Get information food for bird")

                sleep(25)
            else:
                print("- Information food for bird is exists")

            if bird.get("habitat_llm", None) is None:

                prompt_hab = formatted_habitat_prompt(
                    order, family, genre,
                    specie, geo, habit
                )

                return_hab_llm = get_info_llm(model, prompt_hab)
                bird["habitat_llm"] = return_hab_llm

                print("- Get information habitat for bird")

                sleep(25)
            else:
                print("- Information habitat for bird is exists")

            if bird.get("behavior_llm", None) is None:

                prompt_beh = formatted_behavior_prompt(
                    order, family, genre,
                    specie, feature, habit
                )

                return_beh_llm = get_info_llm(model, prompt_beh)
                bird["behavior_llm"] = return_beh_llm

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
