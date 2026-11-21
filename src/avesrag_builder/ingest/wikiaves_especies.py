"""Parser da tabela de espécies do WikiAves (especies.php)."""

import re

from bs4 import BeautifulSoup

from avesrag_builder.core.logging import get_logger

logger = get_logger(__name__)

URL = "https://www.wikiaves.com.br/especies.php?t=t"


def extrair_especies(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_="wa-table-sp")

    if not table or not table.tbody:
        raise RuntimeError(
            "Tabela de espécies não encontrada. A página pode não ter carregado corretamente."
        )

    rows = table.tbody.find_all("tr")
    especies = []
    familia_atual = ""

    for row in rows:
        if "wa-linha-familia" in row.get("class", []):
            continue

        cols = row.find_all("td")
        if len(cols) < 5:
            continue

        fam_text = cols[0].get_text(strip=True)
        if fam_text and fam_text != "\xa0":
            familia_atual = fam_text

        nome_cientifico_tag = cols[1].find("i")
        nome_cientifico = nome_cientifico_tag.get_text(strip=True) if nome_cientifico_tag else ""
        especie_link = cols[1].find("a")
        url_especie = especie_link["href"] if especie_link else ""

        nome_comum = cols[2].get_text(strip=True)

        sons_link = cols[3].find("a")
        sons = sons_link.get_text(strip=True) if sons_link else "0"
        url_sons = sons_link["href"] if sons_link else ""

        fotos_link = cols[4].find("a")
        fotos = fotos_link.get_text(strip=True) if fotos_link else "0"
        url_fotos = fotos_link["href"] if fotos_link else ""

        # O id vem do link de sons; espécies sem som (93 em 2026) só têm o de fotos.
        id_match = re.search(r"s=(\d+)", url_sons) or re.search(r"s=(\d+)", url_fotos)
        id_especie = id_match.group(1) if id_match else ""

        if nome_cientifico:
            especies.append(
                {
                    "id": id_especie,
                    "familia": familia_atual,
                    "nome_cientifico": nome_cientifico,
                    "nome_comum": nome_comum,
                    "sons": sons,
                    "fotos": fotos,
                    "url": url_especie,
                    "url_sons": url_sons,
                    "url_fotos": url_fotos,
                }
            )

    return especies
