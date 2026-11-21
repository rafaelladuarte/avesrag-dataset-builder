"""Testes unitários de avesrag_builder.ingest.base (sem MongoDB)."""

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from avesrag_builder.ingest.avonet import registros_crosswalk
from avesrag_builder.ingest.base import (
    IdDuplicado,
    ResultadoIngestao,
    _checar_duplicados,
    id_texto,
    para_bson,
    registros_de_dataframe,
)
from avesrag_builder.ingest.birdbase import desfazer_datas


class TestParaBson:
    @pytest.mark.parametrize("valor", [None, float("nan"), np.nan, pd.NA, pd.NaT])
    def test_vazios_viram_none(self, valor):
        assert para_bson(valor) is None

    def test_numpy_vira_nativo(self):
        assert type(para_bson(np.int64(3))) is int
        assert type(para_bson(np.float64(2.5))) is float
        assert type(para_bson(np.bool_(True))) is bool

    def test_datas(self):
        assert para_bson(pd.Timestamp("2026-11-20")) == dt.datetime(2026, 11, 20)
        assert para_bson(dt.date(2026, 11, 20)) == dt.datetime(2026, 11, 20)
        assert para_bson(dt.time(13, 5)) == "13:05:00"

    def test_recursivo(self):
        assert para_bson({"a": [np.int64(1), np.nan], 2: {"b": np.float64(1.5)}}) == {
            "a": [1, None],
            "2": {"b": 1.5},
        }

    def test_strings_ficam(self):
        assert para_bson("  NA ") == "  NA "


class TestIdTexto:
    @pytest.mark.parametrize(
        "valor, esperado",
        [
            (3170206, "3170206"),
            (3170206.0, "3170206"),
            (np.int64(8), "8"),
            (" CBRO#0004 ", "CBRO#0004"),
        ],
    )
    def test_casos(self, valor, esperado):
        assert id_texto(valor) == esperado

    @pytest.mark.parametrize("valor", [None, float("nan"), "  "])
    def test_vazio(self, valor):
        with pytest.raises(ValueError, match="id vazio"):
            id_texto(valor)


def test_registros_de_dataframe():
    df = pd.DataFrame({"Geocódigo": [3170206, 5200050], "Bioma": ["Cerrado", np.nan]})
    registros = list(registros_de_dataframe(df, "Geocódigo", prefixo="m:"))
    assert registros == [
        ("m:3170206", {"Geocódigo": 3170206, "Bioma": "Cerrado"}),
        ("m:5200050", {"Geocódigo": 5200050, "Bioma": None}),
    ]


def test_checar_duplicados():
    _checar_duplicados([("a", {}), ("b", {})])
    with pytest.raises(IdDuplicado, match="1 ids repetidos"):
        _checar_duplicados([("a", {}), ("b", {}), ("a", {})])


def test_crosswalk_aceita_um_lado_vazio_e_pula_os_dois_vazios():
    df = pd.DataFrame(
        {
            "Species1": ["A a", "B b", np.nan, np.nan],
            "Species2": ["A a", np.nan, "C c", np.nan],
            "Match.type": ["1BL to 1eBird", "x", "y", "z"],
            "Unnamed: 6": [np.nan] * 4,
        }
    )
    ids = [id_ for id_, _ in registros_crosswalk(df)]
    assert ids == ["crosswalk:A a|A a", "crosswalk:B b|", "crosswalk:|C c"]
    assert "Unnamed: 6" not in registros_crosswalk(df)[0][1]


@pytest.mark.parametrize(
    "valor, esperado",
    [
        (dt.time(0, 0), 0),
        (dt.datetime(1900, 1, 1), 1),
        (dt.datetime(1900, 3, 4), 64),
        (5, 5),
        ("x", "x"),
    ],
)
def test_birdbase_desfaz_celulas_numericas_lidas_como_data(valor, esperado):
    assert desfazer_datas(valor) == esperado


def test_resumo():
    r = ResultadoIngestao("cbro", "raw_cbro", inseridos=2, inalterados=5, ausentes_na_fonte=1)
    assert r.lidos == 7
    assert r.resumo() == (
        "cbro -> raw_cbro: 7 lidos, 2 inseridos, 0 atualizados, 5 inalterados, "
        "1 na collection mas fora da fonte"
    )
