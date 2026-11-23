"""Testes para o próximo passo do `status` (avesrag_builder.status)."""

import dataclasses

import pytest

from avesrag_builder.status import Estado, linhas, proximo_passo

COMPLETO = Estado(
    piloto=True,
    raw={
        "cbro": 1971,
        "ibge": 5572,
        "birdbase": 11589,
        "avonet": 33022,
        "wikiaves": 1975,
        "birdalbum": 11011,
        "commons": 431,
        "inaturalist": 432,
    },
    ebird_municipios=1,
    wikiaves_paginas=437,
    registry=1975,
    piloto_codigos=445,
    escopo=433,
    escopo_com_pagina=433,
    pares=1299,
    pares_validos=1293,
    pares_sem_texto=6,
    fichas=433,
    dq={"apta": 387, "incompleta": 46},
    documentos=1156,
    especies_com_documento=387,
    indices={"vetor_especies": "READY", "texto_especies": "READY"},
)


def com(**mudar):
    return dataclasses.replace(COMPLETO, **mudar)


@pytest.mark.parametrize(
    "estado, passo",
    [
        (com(raw={}), "ingest cbro"),
        (com(raw={**COMPLETO.raw, "avonet": 0}), "ingest avonet"),
        (com(ebird_municipios=0), "ingest ebird --piloto"),
        (com(wikiaves_paginas=0), "ingest wikiaves --piloto"),
        (com(raw={**COMPLETO.raw, "birdalbum": 0}), "ingest birdalbum"),
        (com(registry=0), "resolve"),
        (com(escopo_com_pagina=400), "ingest wikiaves --piloto (faltam páginas"),
        (com(raw={**COMPLETO.raw, "commons": 0}), "ingest commons --piloto"),
        (com(raw={**COMPLETO.raw, "inaturalist": 0}), "ingest inaturalist --piloto"),
        (com(lotes_abertos=1), "extract --piloto --sem-esperar"),
        (com(pares=15), "extract --piloto"),
        (com(fichas=0, dq={}), "fuse --piloto"),
        (com(sem_dq=433), "validate --piloto"),
        (com(documentos=0, especies_com_documento=0, indices={}), "docs --piloto"),
        (com(indices={"vetor_especies": "READY"}), "index"),
        (com(indices={"vetor_especies": "BUILDING", "texto_especies": "READY"}), "index"),
    ],
)
def test_proximo_passo(estado, passo):
    assert proximo_passo(estado).startswith(passo)


def test_completo():
    assert proximo_passo(COMPLETO) is None
    assert linhas(COMPLETO)[-1] == "próximo passo: nenhum, o escopo está completo"


def test_sem_piloto_nao_leva_a_flag():
    assert proximo_passo(com(piloto=False, pares=0)) == "extract"


def test_linhas_resumem_cada_etapa():
    texto = "\n".join(linhas(COMPLETO))
    assert "piloto 433 de 445 do eBird (97.3%)" in texto
    assert "apta 387 (89.4%)" in texto
    assert "1156 documentos de 387 espécies" in texto
