"""Integração: gravação idempotente no envelope raw_* (pytest -m integration)."""

import datetime as dt

import pytest

from avesrag_builder.core.models import compute_source_hash
from avesrag_builder.ingest.base import IdDuplicado, gravar_envelopes

pytestmark = pytest.mark.integration

T0 = dt.datetime(2026, 11, 20, tzinfo=dt.UTC)
T1 = dt.datetime(2026, 11, 21, tzinfo=dt.UTC)


def test_insere_pula_e_atualiza(db_temporario):
    col = db_temporario.raw_teste
    registros = [("1", {"nome": "ema"}), ("2", {"nome": "bem-te-vi", "Beak.Length": 3.1})]

    r1 = gravar_envelopes(col, registros, "teste", agora=T0)
    assert (r1.inseridos, r1.atualizados, r1.inalterados) == (2, 0, 0)

    r2 = gravar_envelopes(col, registros, "teste", agora=T1)
    assert (r2.inseridos, r2.atualizados, r2.inalterados) == (0, 0, 2)
    assert col.find_one({"_id": "1"})["ingerido_em"].replace(tzinfo=dt.UTC) == T0

    r3 = gravar_envelopes(col, [("1", {"nome": "ema-comum"})], "teste", agora=T1)
    assert (r3.inseridos, r3.atualizados, r3.inalterados) == (0, 1, 0)
    doc = col.find_one({"_id": "1"})
    assert doc["dados"] == {"nome": "ema-comum"}
    assert doc["source_hash"] == compute_source_hash({"nome": "ema-comum"})
    assert doc["ingerido_em"].replace(tzinfo=dt.UTC) == T1


def test_chaves_com_ponto_sao_preservadas(db_temporario):
    col = db_temporario.raw_teste
    gravar_envelopes(col, [("x", {"Beak.Length_Culmen": 29.3})], "teste")
    assert col.find_one({"_id": "x"})["dados"]["Beak.Length_Culmen"] == 29.3


def test_conta_ausentes_na_fonte_sem_apagar(db_temporario):
    col = db_temporario.raw_teste
    gravar_envelopes(col, [("a:1", {}), ("a:2", {}), ("b:1", {})], "teste")
    r = gravar_envelopes(col, [("a:1", {})], "teste", completo=True, prefixo_completo="a:")
    assert r.ausentes_na_fonte == 1
    assert col.count_documents({}) == 3


def test_id_duplicado_nao_grava_nada(db_temporario):
    col = db_temporario.raw_teste
    with pytest.raises(IdDuplicado):
        gravar_envelopes(col, [("1", {}), ("1", {"x": 1})], "teste")
    assert col.count_documents({}) == 0


def test_mais_de_um_lote(db_temporario):
    col = db_temporario.raw_teste
    registros = [(str(i), {"i": i}) for i in range(1203)]
    assert gravar_envelopes(col, registros, "teste").inseridos == 1203
    assert gravar_envelopes(col, registros, "teste").inalterados == 1203
