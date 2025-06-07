from playwright.sync_api import sync_playwright
from time import sleep

import random
import json
import csv


def scraper_wikiaves(url):
    titles = {
        "Características",
        "Alimentação",
        "Reprodução",
        "Hábitos",
        "Distribuição Geográfica"
    }

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
                locale="pt-BR",
                # proxy={"server": "http://exyon.flow2go.com.br:8888"}
            )

            page = context.new_page()

            page.set_extra_http_headers({
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "pt-BR,pt;q=0.9",
                "Referer": "https://www.wikiaves.com.br/especies.php?t=t",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-User": "?1",
                "Sec-CH-UA": '"Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
                "Sec-CH-UA-Platform": '"Windows"',
                "Sec-CH-UA-Mobile": "?0"
            })

            page.goto(url)
            page.wait_for_load_state("networkidle")

            elementos = page.query_selector_all("div.wrapper.group h2, div.wrapper.group p")

            sleep(random.uniform(1, 5))

            result = {}
            chave_atual = None

            for el in elementos:
                tag = el.evaluate("el => el.tagName")
                text = el.evaluate("el => el.textContent.trim()")

                if tag == "H2" and text in titles:
                    chave_atual = text
                elif tag == "P" and chave_atual:
                    result[chave_atual] = text
                    chave_atual = None

            browser.close()

            return result
    except Exception as e:
        print(e)
        sleep(random.uniform(5, 20))
        return {}
    

if __name__ == "__main__":
    path_json = "result_scraper_wikiaves_udi.json"

    with open(path_json) as file:
        data = json.load(file)

    j = 0
    n = len(data)
    for i, d in enumerate(data):
        url = d["url_wikiaves"]
        tax = d["taxonomia"]
        
        print(f"{i}/{n} - {tax}")
        if d["caracteristicas"] is None:

            increment_dataset = scraper_wikiaves(url)

            d["caracteristicas"] = increment_dataset.get("Características", None)
            d["alimentacao"] = increment_dataset.get("Alimentação", None)
            d["reproducao"] = increment_dataset.get("Reprodução", None)
            d["habitos"] = increment_dataset.get("Hábitos", None)
            d["dist_geo"] = increment_dataset.get("Distribuição Geográfica", None)
             
            sleep(random.uniform(1, 5))

            j += 1

            print("Get information for bird")
        else:
            print("Information for bird is exists")


        if j == 20:
            with open(
                path_json,
                "w", 
                encoding="utf-8"
            ) as jsonfile:
                json.dump(data, jsonfile, ensure_ascii=False, indent=2)
            
            sleep(random.uniform(5, 20))
            j = 0
    
    with open(
        path_json,
        "w", 
        encoding="utf-8"
    ) as jsonfile:
        json.dump(data, jsonfile, ensure_ascii=False, indent=2)
