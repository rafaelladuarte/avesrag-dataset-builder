import csv
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from pymongo import UpdateOne
from pymongo.errors import BulkWriteError

from scr.database.connection import DatabaseConnection

# ═══════════════════════════════════════════════════════════════
# Funções de Evasão e Resiliência
# ═══════════════════════════════════════════════════════════════

USER_AGENTS = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]


def criar_browser_stealth(playwright):
    """Lança o browser com configurações que minimizam assinaturas de automação."""
    browser = playwright.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ],
    )

    context = browser.new_context(
        user_agent=random.choice(USER_AGENTS),
        viewport={"width": random.randint(1280, 1920), "height": random.randint(800, 1080)},
        locale="pt-BR",
        timezone_id="America/Sao_Paulo",
        extra_http_headers={
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "sec-ch-ua": '"Chromium";v="125", "Not.A/Brand";v="24"',
            "sec-ch-ua-platform": '"Linux"',
            "sec-ch-ua-mobile": "?0",
            "DNT": "1",
        },
    )

    context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
        window.chrome = { runtime: {} };
    """)

    return browser, context


def espera_humana(min_s: float = 2.5, max_s: float = 6.0):
    """Pausa com jitter aleatório para simular tempo de leitura humano."""
    time.sleep(random.uniform(min_s, max_s))


def scroll_suave(page):
    """Simula scroll humano para disparar lazy-loading e parecer orgânico."""
    page.evaluate("window.scrollTo({ top: document.body.scrollHeight / 2, behavior: 'smooth' })")
    time.sleep(random.uniform(0.5, 1.5))
    page.evaluate("window.scrollTo({ top: 0, behavior: 'smooth' })")


def navegar_com_retry(page, url: str, max_tentativas: int = 3) -> str | None:
    """Navega para a URL com backoff exponencial em caso de falha ou bloqueio HTTP."""
    for tentativa in range(1, max_tentativas + 1):
        try:
            response = page.goto(url, wait_until="domcontentloaded", timeout=30_000)

            if response and response.status in (429, 403):
                backoff = (2**tentativa) + random.uniform(0, 2)
                print(
                    f"  -> HTTP {response.status}. Aguardando {backoff:.1f}s antes de tentar novamente..."
                )
                time.sleep(backoff)
                continue

            scroll_suave(page)
            return page.content()

        except Exception as e:  # noqa: BLE001
            backoff = (2**tentativa) + random.uniform(0, 2)
            print(
                f"  -> Tentativa {tentativa}/{max_tentativas} falhou: {e}. Aguardando {backoff:.1f}s..."
            )
            time.sleep(backoff)

    return None


def extrair_classificacao_cientifica(soup: BeautifulSoup) -> dict:
    """Extrai a tabela de classificação científica (taxonomia)."""
    tabela = soup.find("table", id="taxonomia")
    classificacao = {}
    if not tabela:
        return classificacao

    for row in tabela.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) == 2:
            chave = cells[0].get_text(strip=True).rstrip(":")
            valor = cells[1].get_text(strip=True)
            if chave:
                classificacao[chave] = valor

    return classificacao


def extrair_nome_cientifico(soup: BeautifulSoup) -> dict:
    """Extrai o nome científico e a autoridade/ano."""
    h2_list = soup.find_all("h2")
    for h2 in h2_list:
        if "Nome Científico" in h2.get_text():
            nome = None
            autoridade = None
            for sib in h2.next_siblings:
                tag = getattr(sib, "name", None)
                if tag == "h2":
                    break
                if tag == "i" and not nome:
                    nome = sib.get_text(strip=True)
                if tag == "sup" and not autoridade:
                    autoridade = sib.get_text(strip=True)
                if tag in ("br", None):
                    continue
            if nome:
                return {"nome": nome, "autoridade": autoridade}

    titulo = soup.find("title")
    if titulo:
        m = re.search(r"\(([^)]+)\)", titulo.get_text())
        if m:
            return {"nome": m.group(1), "autoridade": None}
    return {}


def extrair_nome_ingles(soup: BeautifulSoup) -> str | None:
    """Extrai o nome em inglês a partir do painel lateral."""
    for h2 in soup.find_all("h2"):
        if "Nome em Inglês" in h2.get_text():
            for sib in h2.next_siblings:
                if getattr(sib, "name", None) == "h2":
                    break
                texto = sib.get_text(strip=True) if hasattr(sib, "get_text") else str(sib).strip()
                if texto:
                    return texto
    return None


def extrair_estado_conservacao(soup: BeautifulSoup) -> str | None:
    """Extrai o estado de conservação (IUCN)."""
    for h2 in soup.find_all("h2"):
        if "Estado de Conservação" in h2.get_text():
            for sib in h2.next_siblings:
                tag = getattr(sib, "name", None)
                if tag == "h2":
                    break
                if tag == "a":
                    texto = sib.get_text(strip=True)
                    if texto:
                        return texto
                if tag and sib.find("b"):
                    return sib.find("b").get_text(strip=True)
    return None


def extrair_foto_indicada(soup: BeautifulSoup) -> str | None:
    """Extrai o link da foto mais indicada pela comunidade."""
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        return og["content"]

    twitter = soup.find("meta", attrs={"name": "twitter:image"})
    if twitter and twitter.get("content"):
        return twitter["content"]

    return None


def get_section_text(soup: BeautifulSoup, section_id: str) -> str | None:
    """Retorna o texto de uma seção identificada pelo id do <h2>."""
    h2 = soup.find("h2", id=section_id)
    if not h2:
        return None

    partes = []
    for sib in h2.next_siblings:
        if getattr(sib, "name", None) == "h2":
            break
        if hasattr(sib, "get_text"):
            texto = sib.get_text(separator=" ", strip=True)
            if texto:
                partes.append(texto)

    texto_completo = " ".join(partes).strip()
    return re.sub(r"\s{2,}", " ", texto_completo) if texto_completo else None


def extrair_galeria(soup: BeautifulSoup, n: int = 2) -> list[str]:
    """Extrai os primeiros N links da galeria de fotos."""
    galeria_div = soup.find("div", class_="wa-galeria")
    if not galeria_div:
        return []

    links = []
    for a in galeria_div.find_all("a", class_="wa-wikifoto"):
        href = a.get("href")
        if href:
            if href.startswith("http"):
                links.append(href)
            else:
                links.append("https://www.wikiaves.com.br/" + href.lstrip("/"))
        if len(links) >= n:
            break

    return links


def extrair_dados_html(html: str) -> dict:
    """Função principal que orquestra toda a extração a partir do HTML em string."""
    soup = BeautifulSoup(html, "html.parser")

    return {
        "classificacao_cientifica": extrair_classificacao_cientifica(soup),
        "nome_cientifico": extrair_nome_cientifico(soup),
        "nome_ingles": extrair_nome_ingles(soup),
        "estado_de_conservacao": extrair_estado_conservacao(soup),
        "foto_mais_indicada": extrair_foto_indicada(soup),
        "caracteristicas": get_section_text(soup, "caracteristicas"),
        "alimentacao": get_section_text(soup, "alimentacao"),
        "reproducao": get_section_text(soup, "reproducao"),
        "habitos": get_section_text(soup, "habitos"),
        "distribuicao_geografica": get_section_text(soup, "distribuicao_geografica"),
        "galeria_fotos_primeiras_2": extrair_galeria(soup, n=2),
    }


def main():
    csv_path = "data/raw/wikiaves_especies.csv"
    from scr.core.config import settings

    MAX_ESPECIES = settings.MAX_ESPECIES or None  # 0 ou ausente = sem limite

    if not Path(csv_path).exists():
        print(f"Erro: Arquivo '{csv_path}' não encontrado.")
        sys.exit(1)

    print("Conectando ao MongoDB para recuperar espécies já extraídas...")
    db_connection = DatabaseConnection()
    db_avesrag = db_connection.get_mongo_db()

    especies_existentes = set()
    for doc in db_avesrag.wikiaves.find({}, {"nome_cientifico": 1}):
        nc = doc.get("nome_cientifico")
        if isinstance(nc, dict):
            especies_existentes.add(nc.get("nome"))
        elif isinstance(nc, str):
            especies_existentes.add(nc)

    print(f"Encontradas {len(especies_existentes)} espécies já cadastradas na base.")

    resultados = []

    limite_str = f"as primeiras {MAX_ESPECIES}" if MAX_ESPECIES else "todas as"
    print(f"Iniciando extração dinâmica via Playwright para {limite_str} espécies...")

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        with sync_playwright() as p:
            browser, context = criar_browser_stealth(p)
            page = context.new_page()

            for i, row in enumerate(reader):
                if MAX_ESPECIES is not None and i >= MAX_ESPECIES:
                    break

                nome = row.get("nome_cientifico", f"Espécie {i+1}")

                if nome in especies_existentes:
                    print(
                        f"[{i+1}/{MAX_ESPECIES}] Espécie '{nome}' já existe no MongoDB. Pulando..."
                    )
                    continue

                url_path = row.get("url", "")

                if not url_path:
                    print(f"URL ausente para {nome}, pulando...")
                    continue

                full_url = "https://www.wikiaves.com.br" + (
                    url_path if url_path.startswith("/") else "/" + url_path
                )

                print(f"[{i+1}/{MAX_ESPECIES}] Acessando {nome}: {full_url}")

                html = navegar_com_retry(page, full_url)
                if html is None:
                    print(f"  -> Desistindo de {nome} após todas as tentativas.")
                    continue

                dados_extraidos = extrair_dados_html(html)
                dados_extraidos["meta_id"] = row.get("id")
                dados_extraidos["meta_nome_comum"] = row.get("nome_comum")
                dados_extraidos["fontes"] = ["wikiaves"]
                dados_extraidos["atualizado_em"] = datetime.now(timezone.utc)
                resultados.append(dados_extraidos)

                espera_humana()

            browser.close()

    if not resultados:
        print("Nenhum resultado para inserir no MongoDB.")
        return

    print("Conectando ao MongoDB para inserção (BulkWrite)...")
    # A conexão já foi estabelecida acima
    ops = []
    for doc in resultados:
        nome_cientifico = doc.get("nome_cientifico", {}).get("nome")
        if not nome_cientifico:
            # Caso fallback para nome_cientifico seja diferente
            nome_cientifico = row.get("nome_cientifico")

        if nome_cientifico:
            # Reestrutura chave para bater com o padrão de busca, se preferir salvar string
            ops.append(
                UpdateOne(
                    {"nome_cientifico": nome_cientifico},
                    {"$set": doc},
                    upsert=True,
                )
            )
        else:
            print(f"Documento sem nome científico, ignorando: {doc}")

    if ops:
        try:
            db_avesrag.wikiaves.bulk_write(ops, ordered=False)
            print(
                f"Extração finalizada com sucesso! {len(ops)} espécies carregadas na collection 'wikiaves' do MongoDB (banco 'avesrag')."
            )
        except BulkWriteError as e:
            print(f"Erro de bulk_write no MongoDB: {e.details}")


if __name__ == "__main__":
    main()
