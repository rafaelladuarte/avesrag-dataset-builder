"""Leitura das planilhas reais de data/raw/ (lento: pytest -m slow)."""

import pytest

from avesrag_builder.core.settings import get_settings
from avesrag_builder.ingest import avonet, birdbase, cbro, ibge

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def s():
    return get_settings()


def test_cbro_tem_as_1971_especies(s):
    registros = dict(cbro.ler(s.CBRO_XLSX))
    assert len(registros) == 1971
    rhea = registros["CBRO#0004"]
    assert rhea["Nome do táxon (sem autoria)"] == "Rhea americana"
    assert rhea["Ordem"] == "Rheiformes"
    assert {r["Categoria"] for r in registros.values()} == {"Espécie"}


def test_ibge_tem_uberlandia(s):
    registros = dict(ibge.ler(s.IBGE_XLSX))
    assert len(registros) == 5572
    assert registros["3170206"]["Nome do município"] == "Uberlândia"
    assert registros["3170206"]["Bioma predominante"] == "Cerrado"


def test_birdbase_sem_datas_falsas(s):
    import datetime as dt

    registros = birdbase.ler(s.BIRDBASE_XLSX)
    assert len(registros) == 11589
    for _, dados in registros:
        assert not any(isinstance(v, (dt.datetime, dt.time)) for v in dados.values())


def test_avonet_tres_abas(s):
    registros = avonet.ler(s.AVONET_XLSX)
    prefixos = {}
    for id_, _ in registros:
        prefixo = id_.split(":", 1)[0]
        prefixos[prefixo] = prefixos.get(prefixo, 0) + 1
    assert prefixos == {"birdlife": 11009, "ebird": 10661, "crosswalk": 11352}
    pitangus = dict(registros)["birdlife:Pitangus sulphuratus"]
    assert pitangus["Family1"] == "Tyrannidae"
    assert "Beak.Length_Culmen" in pitangus
