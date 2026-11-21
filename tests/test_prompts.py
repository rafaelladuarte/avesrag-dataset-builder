"""Leitor dos prompts do builder (config/prompts/*.yaml)."""

import pytest
import yaml

from avesrag_builder.core.settings import get_settings
from avesrag_builder.core.vocabulario import vocabulario_padrao
from avesrag_builder.extract.contratos import SCHEMAS
from avesrag_builder.llm.prompts import (
    PROMPTS_DO_BUILDER,
    PromptInvalido,
    carregar_prompt,
    carregar_prompts,
)


@pytest.fixture(scope="module")
def voc():
    return vocabulario_padrao()


@pytest.fixture
def base():
    return {
        "id": "b01_aparencia",
        "versao": "2.0",
        "modelo": "gpt-6-luna",
        "temperatura": None,
        "schema": "B01Aparencia",
        "vocabulario": ["cores"],
        "campos": ["caracteristicas"],
        "system": "Valores:\n{vocabulario}\n",
        "entrada": "<texto_fonte>{caracteristicas}</texto_fonte>",
    }


def _gravar(tmp_path, dados, nome="b01_aparencia"):
    caminho = tmp_path / f"{nome}.yaml"
    caminho.write_text(yaml.safe_dump(dados, allow_unicode=True), encoding="utf-8")
    return caminho


def test_prompts_do_repositorio_carregam(voc):
    prompts = carregar_prompts(get_settings().CONFIG_DIR / "prompts", voc, SCHEMAS)
    assert [p.id for p in prompts] == list(PROMPTS_DO_BUILDER)
    for p in prompts:
        system = p.render_system(voc)
        assert "{vocabulario}" not in system
        entrada = p.render_entrada({c: f"TEXTO_{c}" for c in p.campos})
        for c in p.campos:
            assert f"TEXTO_{c}" in entrada


def test_vocabulario_injetado_no_system(voc, tmp_path, base):
    p = carregar_prompt(_gravar(tmp_path, base), voc, SCHEMAS)
    assert "amarelo" in p.render_system(voc)


def test_texto_com_chaves_nao_quebra_a_entrada(voc, tmp_path, base):
    p = carregar_prompt(_gravar(tmp_path, base), voc, SCHEMAS)
    assert "{x}" in p.render_entrada({"caracteristicas": "texto com {x}"})


@pytest.mark.parametrize(
    "mudanca, erro",
    [
        ({"schema": "B09Inexistente"}, "schema"),
        ({"vocabulario": ["cor_do_bico"]}, "cor_do_bico"),
        ({"campos": ["distribuicao"], "entrada": "{distribuicao}"}, "distribuicao"),
        ({"entrada": "<texto_fonte></texto_fonte>"}, "entrada"),
        ({"system": "sem placeholder"}, "system"),
        ({"temperatura": "zero"}, "temperatura"),
        ({"extra": 1}, "extra"),
    ],
)
def test_prompt_invalido(voc, tmp_path, base, mudanca, erro):
    with pytest.raises(PromptInvalido, match=erro):
        carregar_prompt(_gravar(tmp_path, {**base, **mudanca}), voc, SCHEMAS)


def test_id_igual_ao_nome_do_arquivo(voc, tmp_path, base):
    with pytest.raises(PromptInvalido, match="nome do arquivo"):
        carregar_prompt(_gravar(tmp_path, base, nome="outro"), voc, SCHEMAS)


def test_falta_arquivo(voc, tmp_path, base):
    _gravar(tmp_path, base)
    with pytest.raises(PromptInvalido, match="b02_comportamento.yaml"):
        carregar_prompts(tmp_path, voc, SCHEMAS)
