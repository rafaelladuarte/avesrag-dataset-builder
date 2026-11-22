"""Testes para as validações e a classificação do `validate` (validate/regras.py)."""

import pytest

from avesrag_builder.core.regras_fusao import regras_fusao_padrao
from avesrag_builder.core.vocabulario import regras_bico_padrao, vocabulario_padrao
from avesrag_builder.fuse.species import montar
from avesrag_builder.validate import regras as v
from tests.test_fuse_regras import bem_te_vi

REGISTRADOS = {"sp_pitangus_sulphuratus"}


@pytest.fixture(scope="module")
def vocab():
    return vocabulario_padrao()


@pytest.fixture(scope="module")
def regras():
    return regras_fusao_padrao()


@pytest.fixture
def doc(vocab, regras):
    return montar(bem_te_vi(), vocab, regras_bico_padrao(), regras).species.to_mongo()


def _erros(doc, vocab, regras):
    return v.erros(doc, vocab, regras, REGISTRADOS)


class TestErros:
    def test_ficha_montada_passa(self, doc, vocab, regras):
        assert _erros(doc, vocab, regras) == []

    def test_1_valor_fora_do_vocabulario(self, doc, vocab, regras):
        doc["atributos"]["cores"].append("dourado")
        assert "atributos.cores: 'dourado' não está no vocabulário" in _erros(doc, vocab, regras)

    def test_1_parte_fora_do_vocabulario(self, doc, vocab, regras):
        doc["atributos"]["cores_por_parte"].append({"parte": "crista", "cor": "preto"})
        assert any("parte 'crista'" in e for e in _erros(doc, vocab, regras))

    def test_1_iucn_fora_do_vocabulario(self, doc, vocab, regras):
        doc["iucn"] = "XX"
        assert "iucn: 'XX' não está no vocabulário" in _erros(doc, vocab, regras)

    def test_2_comprimento_fora_da_faixa(self, doc, vocab, regras):
        doc["atributos"]["comprimento_cm"] = 230
        assert "atributos.comprimento_cm: 230 fora de 5–200 cm" in _erros(doc, vocab, regras)

    def test_3_campo_sem_prov(self, doc, vocab, regras):
        del doc["_prov"]["atributos.marcas"]
        assert "_prov: falta a entrada de atributos.marcas" in _erros(doc, vocab, regras)

    def test_3_prov_de_campo_inexistente(self, doc, vocab, regras):
        doc["_prov"]["atributos.cauda"] = {"fonte": "wikiaves"}
        assert "_prov.atributos.cauda: aponta para um campo vazio ou inexistente" in _erros(
            doc, vocab, regras
        )

    def test_4_lista_vazia(self, doc, vocab, regras):
        doc["atributos"]["marcas"] = []
        erros = _erros(doc, vocab, regras)
        assert any("lista vazia" in e for e in erros)

    def test_5_taxonomia_incompleta(self, doc, vocab, regras):
        del doc["taxonomia"]["genero"]
        assert "taxonomia: falta genero" in _erros(doc, vocab, regras)

    def test_5_taxonomia_de_duas_fontes(self, doc, vocab, regras):
        doc["_prov"]["taxonomia"] = {"fonte": "cbro+wikiaves"}
        assert "taxonomia: mais de uma fonte (cbro+wikiaves)" in _erros(doc, vocab, regras)

    def test_6_species_id_fora_do_registry(self, doc, vocab, regras):
        assert any("não está no registry" in e for e in v.erros(doc, vocab, regras, set()))


class TestFaltasEClassificacao:
    def test_apta(self, doc, regras):
        assert v.faltas(doc, regras, {"aparencia"}) == []
        assert v.classificar([], []) == "apta"

    def test_incompleta_com_o_que_falta(self, doc, regras):
        doc["atributos"]["cores"] = ["amarelo"]
        del doc["atributos"]["bico_tipo"]
        faltas = v.faltas(doc, regras, set())
        assert faltas == ["cores (1 de 2)", "bico_tipo", "b03.aparencia"]
        assert v.classificar([], faltas) == "incompleta"

    def test_bloqueada_vence_incompleta(self):
        assert v.classificar(["taxonomia: falta genero"], ["cores (1 de 2)"]) == "bloqueada"


def test_3_ilustracao_sem_prov(doc, vocab, regras):
    doc["midia"]["ilustracao"] = {
        "url": "u",
        "credito": "c",
        "licenca": "l",
        "link": "k",
        "gerada_por_ia": True,
        "referencia": "foto",
    }
    assert "_prov: falta a entrada de midia.ilustracao" in _erros(doc, vocab, regras)
