"""Testes para avesrag_builder.fuse.species_occurrence (raw_ebird + raw_ibge -> species_occurrence)."""

from datetime import UTC, datetime

from avesrag_builder.fuse.species_occurrence import agrupar

AGORA = datetime(2026, 11, 22, tzinfo=UTC)

MUNICIPIOS = [
    {"geocodigo": "3170206", "nome": "Uberlândia", "uf": "MG", "especies": ["grekis", "xxxx1"]},
    {"geocodigo": "3106200", "nome": "Belo Horizonte", "uf": "MG", "especies": ["grekis"]},
]
IBGE = {
    "3170206": {
        "Nome do município": "Uberlândia",
        "Sigla da UF": "MG",
        "Bioma predominante": "Cerrado",
    },
    "3106200": {
        "Nome do município": "Belo Horizonte",
        "Sigla da UF": "MG",
        "Bioma predominante": "Mata Atlântica",
    },
}
CODIGOS = {"grekis": "sp_pitangus_sulphuratus"}


def test_agrupa_por_especie_com_bioma_do_ibge():
    res = agrupar(MUNICIPIOS, IBGE, CODIGOS, AGORA)
    occ = res.por_especie["sp_pitangus_sulphuratus"]
    assert occ.n_municipios == 2
    assert [m.geocodigo for m in occ.municipios] == ["3106200", "3170206"]  # por geocódigo
    assert occ.biomas == ["Cerrado", "Mata Atlântica"]
    assert res.municipios == 2


def test_codigo_sem_especie_no_registry_e_contado():
    res = agrupar(MUNICIPIOS, IBGE, CODIGOS, AGORA)
    assert res.codigos_sem_especie == {"xxxx1"}
    assert set(res.por_especie) == {"sp_pitangus_sulphuratus"}


def test_municipio_sem_ibge_fica_sem_bioma():
    res = agrupar(MUNICIPIOS[:1], {}, CODIGOS, AGORA)
    occ = res.por_especie["sp_pitangus_sulphuratus"]
    assert occ.municipios[0].nome == "Uberlândia"  # do eBird
    assert occ.municipios[0].bioma is None
    assert occ.biomas == []


def test_municipio_repetido_conta_uma_vez():
    res = agrupar([MUNICIPIOS[0], MUNICIPIOS[0]], IBGE, CODIGOS, AGORA)
    assert res.por_especie["sp_pitangus_sulphuratus"].n_municipios == 1


def test_deterministico():
    a = agrupar(MUNICIPIOS, IBGE, CODIGOS, AGORA)
    b = agrupar(list(reversed(MUNICIPIOS)), IBGE, CODIGOS, AGORA)
    assert a.por_especie["sp_pitangus_sulphuratus"] == b.por_especie["sp_pitangus_sulphuratus"]
