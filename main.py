import asyncio
from playwright.sync_api import sync_playwright

def extrair_textos_wikiaves(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=60000)

        page.wait_for_selector("div.wrapper.group")
        textos = page.eval_on_selector_all(
            "div.wrapper.group p, div.wrapper.group h2",
            "elements => elements.map(e => e.textContent.trim()).filter(Boolean)"
        )

        browser.close()
        return textos

url = "https://www.wikiaves.com.br/wiki/ema"
textos_extraidos = extrair_textos_wikiaves(url)

for texto in textos_extraidos:
    print(texto)