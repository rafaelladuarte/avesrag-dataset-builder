"""Montagem das tarefas, interpretação das respostas e adaptador OpenAI (sem rede)."""

import json

import pytest

from avesrag_builder.core.settings import Settings, get_settings
from avesrag_builder.core.vocabulario import vocabulario_padrao
from avesrag_builder.extract.contratos import SCHEMAS
from avesrag_builder.extract.pipeline import (
    SEM_TEXTO,
    extracao_sem_texto,
    interpretar,
    montar_tarefa,
)
from avesrag_builder.llm.base import Resposta
from avesrag_builder.llm.openai import corpo, linha_de_resultado
from avesrag_builder.llm.prompts import carregar_prompts

TEXTOS = {
    "caracteristicas": "Mede 13 centímetros. O macho é azul e negro, com as pernas rosadas.",
    "habitos": "Vive aos pares.",
    "alimentacao": "",
    "reproducao": "",
}


@pytest.fixture(scope="module")
def voc():
    return vocabulario_padrao()


@pytest.fixture(scope="module")
def prompts(voc):
    return {p.id: p for p in carregar_prompts(get_settings().CONFIG_DIR / "prompts", voc, SCHEMAS)}


@pytest.fixture
def settings():
    return Settings(_env_file=None)


def _b01(**campos):
    base = dict.fromkeys(["comprimento_cm", "cores", "cores_por_parte", "marcas", "cauda"])
    return json.dumps({**base, **campos})


class TestMontarTarefa:
    def test_pedido(self, prompts, voc, settings):
        t = montar_tarefa("sp_dacnis_cayana", TEXTOS, prompts["b01_aparencia"], voc, settings)
        assert t.extraction_id == "sp_dacnis_cayana:b01_aparencia"
        assert t.pedido.id == f"sp_dacnis_cayana:b01_aparencia:{t.input_hash[:12]}"
        assert t.modelo == "gpt-6-luna" and t.pedido.temperatura is None
        assert TEXTOS["caracteristicas"] in t.pedido.entrada
        assert "Vive aos pares" not in t.pedido.entrada  # b01 só lê as características
        assert t.pedido.schema["name"] == "B01Aparencia"
        assert not t.sem_texto

    def test_hash_estavel_e_sensivel_a_entrada_e_modelo(self, prompts, voc, settings):
        p = prompts["b01_aparencia"]
        h = montar_tarefa("sp_x", TEXTOS, p, voc, settings).input_hash
        assert montar_tarefa("sp_x", dict(TEXTOS), p, voc, settings).input_hash == h
        outro_texto = {**TEXTOS, "caracteristicas": "Mede 14 centímetros."}
        assert montar_tarefa("sp_x", outro_texto, p, voc, settings).input_hash != h
        outro_modelo = Settings(_env_file=None, LLM_MODEL="outro")
        sem_modelo = p.model_copy(update={"modelo": None})
        assert montar_tarefa("sp_x", TEXTOS, sem_modelo, voc, outro_modelo).input_hash != h

    def test_hash_muda_com_o_system(self, prompts, voc, settings):
        p = prompts["b02_comportamento"]
        h = montar_tarefa("sp_x", TEXTOS, p, voc, settings).input_hash
        mudado = p.model_copy(update={"system": p.system + "\nRegra nova."})
        assert montar_tarefa("sp_x", TEXTOS, mudado, voc, settings).input_hash != h

    def test_sem_texto(self, prompts, voc, settings):
        vazio = {**TEXTOS, "caracteristicas": "  "}
        t = montar_tarefa("sp_x", vazio, prompts["b01_aparencia"], voc, settings)
        assert t.sem_texto
        e = extracao_sem_texto(t)
        assert e.validacao.erro == SEM_TEXTO and not e.validacao.ok and e.saida == {}

    def test_b02_com_um_dos_textos_basta(self, prompts, voc, settings):
        t = montar_tarefa("sp_x", TEXTOS, prompts["b02_comportamento"], voc, settings)
        assert not t.sem_texto


class TestInterpretar:
    @pytest.fixture
    def tarefa(self, prompts, voc, settings):
        return montar_tarefa("sp_x", TEXTOS, prompts["b01_aparencia"], voc, settings)

    def test_valida_com_evidencia(self, tarefa):
        conteudo = _b01(
            comprimento_cm={"min": 13, "max": 13, "evidencia": "Mede 13 centímetros"},
            cores=[
                {"valor": "azul", "evidencia": "o macho é azul e negro"},
                {"valor": "azul", "evidencia": "azul"},
                {"valor": "rosa", "evidencia": "pernas rosadas no ninho"},
            ],
            marcas=[],
        )
        e, erro = interpretar(tarefa, Resposta(id="x", conteudo=conteudo))
        assert erro is None and e.validacao.ok
        assert [c["valor"] for c in e.saida["cores"]] == ["azul", "rosa"]
        assert e.saida["marcas"] is None
        assert e.validacao.evidencias_nao_encontradas == ["pernas rosadas no ninho"]

    @pytest.mark.parametrize(
        "resposta, motivo",
        [
            (Resposta(id="x", erro="erro_api: HTTP 500"), "erro_api"),
            (Resposta(id="x", erro="recusa: não"), "erro_api"),
            (Resposta(id="x", conteudo="{nao e json"), "invalido"),
            (Resposta(id="x", conteudo="[]"), "invalido"),
            (
                Resposta(id="x", conteudo=_b01(cores=[{"valor": "dourado", "evidencia": "a"}])),
                "invalido",
            ),
        ],
    )
    def test_falhas(self, tarefa, resposta, motivo):
        e, erro = interpretar(tarefa, resposta)
        assert e is None and erro.startswith(motivo)


class TestOpenAI:
    def test_corpo_sem_temperature_quando_null(self, prompts, voc, settings):
        t = montar_tarefa("sp_x", TEXTOS, prompts["b03_textos_busca"], voc, settings)
        body = corpo(t.pedido)
        assert "temperature" not in body
        assert body["response_format"]["json_schema"]["strict"] is True
        assert [m["role"] for m in body["messages"]] == ["system", "user"]

    def test_linha_do_lote_ok(self):
        linha = {
            "custom_id": "sp_x:b01:abc",
            "response": {
                "status_code": 200,
                "body": {
                    "choices": [{"message": {"content": "{}"}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 3},
                },
            },
            "error": None,
        }
        r = linha_de_resultado(linha)
        assert (r.id, r.conteudo, r.erro, r.tokens_entrada, r.tokens_saida) == (
            "sp_x:b01:abc",
            "{}",
            None,
            10,
            3,
        )

    def test_linha_do_lote_com_erro(self):
        assert linha_de_resultado(
            {"custom_id": "a", "response": {"status_code": 400, "body": {}}, "error": None}
        ).erro.startswith("erro_api")
        assert linha_de_resultado({"custom_id": "a", "error": {"code": "x"}}).erro.startswith(
            "erro_api"
        )
