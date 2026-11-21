"""Contratos de saída dos prompts e JSON Schema estrito."""

import pytest
from pydantic import ValidationError

from avesrag_builder.core.vocabulario import vocabulario_padrao
from avesrag_builder.extract.contratos import (
    B03TextosBusca,
    contrato,
    normalizar_saida,
    schema_estrito,
)

B01_ATRIBUTOS = ["cores", "cores_por_parte", "marcas", "cauda"]
B02_ATRIBUTOS = ["ambiente", "onde_estava", "o_que_fazia", "grupo", "atividade"]


@pytest.fixture(scope="module")
def voc():
    return vocabulario_padrao()


@pytest.fixture(scope="module")
def b01(voc):
    return contrato("B01Aparencia", B01_ATRIBUTOS, voc)


@pytest.fixture(scope="module")
def b02(voc):
    return contrato("B02Comportamento", B02_ATRIBUTOS, voc)


def _b01(**campos):
    base = dict.fromkeys(["comprimento_cm", *B01_ATRIBUTOS])
    return {**base, **campos}


def _objetos(no):
    if isinstance(no, dict):
        if "properties" in no:
            yield no
        for v in no.values():
            yield from _objetos(v)
    elif isinstance(no, list):
        for v in no:
            yield from _objetos(v)


class TestSchemaEstrito:
    def test_todo_objeto_fechado_e_com_tudo_obrigatorio(self, b01, b02):
        for modelo in (b01, b02, B03TextosBusca):
            sch = schema_estrito(modelo)
            assert sch["strict"] is True and sch["name"] == modelo.__name__
            objetos = list(_objetos(sch["schema"]))
            assert objetos
            for obj in objetos:
                assert obj["additionalProperties"] is False
                assert obj["required"] == list(obj["properties"])

    def test_sem_palavras_fora_do_modo_estrito(self, b01):
        texto = str(schema_estrito(b01))
        for chave in ("'default'", "'minLength'", "'title'"):
            assert chave not in texto

    def test_valores_do_vocabulario_como_enum(self, b01, voc):
        defs = schema_estrito(b01)["schema"]["$defs"]
        assert defs["ItemCores"]["properties"]["valor"]["enum"] == voc.valores("cores")
        assert defs["ItemCoresPorParte"]["properties"]["parte"]["enum"] == voc.partes()
        assert list(defs["ItemMarcas"]["properties"]) == ["valor", "evidencia"]

    def test_campos_aceitam_null(self, b02):
        props = schema_estrito(b02)["schema"]["properties"]
        assert set(props) == set(B02_ATRIBUTOS)
        for campo in props.values():
            assert {"type": "null"} in campo["anyOf"]


class TestValidacao:
    def test_saida_valida(self, b01):
        saida = _b01(
            comprimento_cm={"min": 20.5, "max": 25, "evidencia": "mede entre 20,5 e 25 cm"},
            cores=[{"valor": "amarelo", "evidencia": "barriga amarela"}],
            cores_por_parte=[
                {"parte": "barriga", "cor": "amarelo", "evidencia": "barriga amarela"}
            ],
        )
        assert b01.model_validate(saida).model_dump()["cores"][0]["valor"] == "amarelo"

    def test_valor_fora_do_vocabulario(self, b01):
        with pytest.raises(ValidationError):
            b01.model_validate(_b01(cores=[{"valor": "dourado", "evidencia": "x"}]))

    def test_campo_faltando_ou_extra(self, b01):
        with pytest.raises(ValidationError):
            b01.model_validate({"cores": None})
        with pytest.raises(ValidationError):
            b01.model_validate(_b01(bico=None))

    def test_lista_vazia_rejeitada(self, b01):
        with pytest.raises(ValidationError, match="lista vazia"):
            b01.model_validate(_b01(marcas=[]))

    def test_evidencia_vazia(self, b01):
        with pytest.raises(ValidationError):
            b01.model_validate(_b01(cauda=[{"valor": "longa", "evidencia": " "}]))

    def test_comprimento_invertido(self, b01):
        with pytest.raises(ValidationError, match="maior que max"):
            b01.model_validate(_b01(comprimento_cm={"min": 30, "max": 20, "evidencia": "x"}))

    def test_b03(self):
        B03TextosBusca.model_validate(
            {"aparencia": "Mede 13 cm.", "comportamento_ambiente": None, "voz_habitos": None}
        )
        with pytest.raises(ValidationError, match="limite"):
            B03TextosBusca.model_validate(
                {"aparencia": "a" * 701, "comportamento_ambiente": None, "voz_habitos": None}
            )


class TestNormalizar:
    def test_tira_repetidos_mantendo_a_primeira_evidencia(self):
        saida = normalizar_saida(
            {
                "ambiente": [
                    {"valor": "borda_de_mata", "evidencia": "bordas de florestas"},
                    {"valor": "borda_de_mata", "evidencia": "capoeiras"},
                    {"valor": "mata", "evidencia": "matas"},
                ]
            }
        )
        assert [i["evidencia"] for i in saida["ambiente"]] == ["bordas de florestas", "matas"]

    def test_cores_por_parte_repetidas_pela_parte_e_cor(self):
        itens = [
            {"parte": "pernas", "cor": "rosa", "evidencia": "a"},
            {"parte": "pernas", "cor": "laranja", "evidencia": "b"},
            {"parte": "pernas", "cor": "rosa", "evidencia": "c"},
        ]
        assert len(normalizar_saida({"cores_por_parte": itens})["cores_por_parte"]) == 2

    def test_vazios_viram_null(self):
        saida = normalizar_saida({"marcas": [], "aparencia": "  ", "cauda": None})
        assert saida == {"marcas": None, "aparencia": None, "cauda": None}
