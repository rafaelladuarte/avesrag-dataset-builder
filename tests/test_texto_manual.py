"""Testes da divisão e da mescla dos textos do WikiAves colados à mão, sem banco."""

from avesrag_builder.extract.pipeline import mesclar_textos
from avesrag_builder.ingest.texto_manual import dividir

ARAPACU = """Arapaçu-escamoso
O arapaçu-escamoso é uma ave passeriforme da família Dendrocolaptidae.

Nome Científico
Seu nome científico significa: do grego lepis = com marcações.

Características
Mede 19 centímetros de comprimento. Assemelha-se ao arapacu-escamoso-do-sul.

ESPÉCIE SEM DIMORFISMO SEXUALSubespécies
Não possui subespécies.

Espécies Similares
**Ajuda para a diferenciação**

Alimentação
Hábitos alimentares…

arapaçu-escamoso se alimentando
Predando insetoHábitos
Ocorre em matas úmidas. Solitário ou aos pares.Distribuição Geográfica
Ocorre nas Regiões Nordeste e Sudeste do Brasil.
"""


def test_divide_titulos_grudados_e_nao_confunde_frase_com_titulo():
    p = dividir(ARAPACU)
    assert p["caracteristicas"].startswith("Mede 19 centímetros")
    assert "ESPÉCIE SEM DIMORFISMO SEXUAL" in p["caracteristicas"]
    # "Hábitos alimentares…" é frase da seção Alimentação, não o título Hábitos
    assert p["alimentacao"].startswith("Hábitos alimentares…")
    assert p["alimentacao"].endswith("Predando inseto")
    assert p["habitos"] == "Ocorre em matas úmidas. Solitário ou aos pares."
    assert p["reproducao"] == ""
    assert "Distribuição Geográfica: Ocorre nas Regiões" in p["outros"]
    assert p["outros"].startswith("Arapaçu-escamoso")


def test_titulos_no_estilo_wiki_e_secoes_desconhecidas():
    texto = (
        "Curió\nIntro com cor preta.\n\nNome Científico\nSeu nome significa algo. "
        "=====Ameaças===== Caça. ===== Características ===== Mede 12 cm, macho negro.\n"
        "===== Subespécies ===== Duas. ===== Alimentação ===== Sementes.\n"
        "==== Reprodução ===== Ninho em xícara.===== Hábitos ===== Vive aos pares. "
        "===== Distribuição Geográfica ===== Brasil."
    )
    p = dividir(texto)
    assert p["caracteristicas"] == "Mede 12 cm, macho negro."
    assert p["alimentacao"] == "Sementes."
    assert p["reproducao"] == "Ninho em xícara."
    assert p["habitos"] == "Vive aos pares."
    assert "Ameaças: Caça." in p["outros"]
    assert "Intro com cor preta." in p["outros"]


def test_voz_vai_para_habitos():
    p = dividir(
        "Hábitos\nAve de campo aberto.\nVoz\nCanta ao amanhecer.\nReprodução\nNinho no chão.\n"
    )
    assert p["habitos"] == "Ave de campo aberto. Canta ao amanhecer."
    assert p["reproducao"] == "Ninho no chão."


def test_sem_titulo_nao_reconhece_nada():
    p = dividir("Texto solto sem seções nenhumas.")
    assert p["titulos"] == []
    assert not any(p[c] for c in ("caracteristicas", "alimentacao", "habitos", "reproducao"))


def test_mescla_campo_a_campo():
    pagina = {
        "caracteristicas": "da página",
        "alimentacao": "da página",
        "habitos": "",
        "reproducao": "da página",
    }
    manual = {"caracteristicas": " colado ", "alimentacao": "", "habitos": "colado h"}
    r = mesclar_textos(pagina, manual)
    assert r == {
        "caracteristicas": "colado",
        "alimentacao": "da página",
        "habitos": "colado h",
        "reproducao": "da página",
    }
    assert mesclar_textos(pagina, {}) == pagina
