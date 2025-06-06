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

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
            locale="pt-BR"
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
    

if __name__ == "__main__":
    path_csv = r"data\treat_data\merge_cbro_wikiaves_uberlandia.csv"

    with open(path_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        data = list(reader)

    dataset = []
    for d in data:
        url = d["url_wikiaves"]

        increment_dataset = scraper_wikiaves(url)

        dataset.append(
            {   
                **d,
                "caracteristicas": increment_dataset.get("Características"),
                "alimentacao": increment_dataset.get("Alimentação"),
                "reproducao": increment_dataset.get("Reprodução"),
                "habitos": increment_dataset.get("Hábitos"),
                "dist_geo": increment_dataset.get("Distribuição Geográfica")
            }
        )

        sleep(random.uniform(1, 5))

    
        with open(
            r"data\treat_data\result_scraper_wikiaves_udi.json", 
            "w", 
            encoding="utf-8"
        ) as jsonfile:
            json.dump(dataset, jsonfile, ensure_ascii=False, indent=2)
