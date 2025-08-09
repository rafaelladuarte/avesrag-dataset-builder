from prompts.resume import formatted_resume_prompt

from time import sleep

import requests
import json
import os
import re


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
    model = "deepseek-r1-distill-llama-70b"

    with open(path_json) as file:
        list_birds = json.load(file)

    j = 0
    n = len(list_birds)
    should_stop = False
    for i, bird in enumerate(list_birds):
        try:
            tax = bird.get("taxonomia")
            order = bird.get("ordem")
            fami = bird.get("familia")
            genre = bird.get("genero")
            specie = bird.get("especie")
            feature = bird.get("caracteristicas")
            food = bird.get("alimentacao")
            geo = bird.get("dist_geo")
            habit = bird.get("habitos")
            rep = bird.get("reproducao")

            print(f"{i+1}/{n} - {tax}")

            if bird.get("resumo_llm", None) is None:

                prompt_mor = formatted_resume_prompt(
                    tax,
                    specie, feature, food, geo,
                    habit, rep
                )

                return_llm = get_info_llm(model, prompt_mor)

                match = re.search(r'</think>(.*)', return_llm, re.DOTALL)
                group = match.group(0)
                if group:
                    resume = group.replace('\n', '').strip()
                    resume = resume.replace('</think>', '')
                    bird["resumo_llm"] = resume
                    print("- Get information resume for bird")

                sleep(25)
            else:
                print("- Information resume for bird is exists")

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
