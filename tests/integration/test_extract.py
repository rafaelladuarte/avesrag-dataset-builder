"""Integração: `extract` com fornecedor falso em banco temporário (pytest -m integration).

Cobre o aceite do Marco 4: todos os pares processados (A1), segunda execução sem
chamadas ao LLM (A3) e retomada de lote aberto sem reenvio (A5).
"""

import itertools
import json

import pytest

from avesrag_builder.core.settings import get_settings
from avesrag_builder.db.collections import (
    LLM_BATCHES,
    RAW_WIKIAVES,
    SPECIES_EXTRACTIONS,
    SPECIES_REGISTRY,
)
from avesrag_builder.extract.pipeline import SEM_TEXTO, Extrator
from avesrag_builder.llm.base import Pedido, Resposta, SituacaoLote

pytestmark = pytest.mark.integration

PAGINAS = {
    # espécie completa: os 3 prompts têm texto
    "1": {
        "caracteristicas": "Mede 13 centímetros. O macho é azul e negro.",
        "habitos": "Vive aos pares na borda da mata.",
        "alimentacao": "Come frutas.",
        "reproducao": "Ninho em taça.",
    },
    # sem características nem hábitos/alimentação: b01 e b02 ficam sem_texto
    "2": {"reproducao": "Põe dois ovos."},
}


def saida_valida(pedido: Pedido) -> str:
    nome = pedido.schema["name"]
    if nome == "B01Aparencia":
        return json.dumps(
            {
                "comprimento_cm": {"min": 13, "max": 13, "evidencia": "Mede 13 centímetros"},
                "cores": [{"valor": "azul", "evidencia": "o macho é azul"}],
                "cores_por_parte": None,
                "marcas": None,
                "cauda": None,
            }
        )
    if nome == "B02Comportamento":
        campos = ["ambiente", "onde_estava", "o_que_fazia", "grupo", "atividade"]
        return json.dumps(
            {**dict.fromkeys(campos), "grupo": [{"valor": "casal", "evidencia": "aos pares"}]}
        )
    return json.dumps(
        {"aparencia": "Ave azul.", "comportamento_ambiente": None, "voz_habitos": None}
    )


_IDS_DE_LOTE = itertools.count(1)


class Falso:
    """Fornecedor em memória que registra as chamadas (ids de lote únicos no processo)."""

    nome = "falso"

    def __init__(
        self, conteudo=saida_valida, conteudo_sincrono=None, andamentos=0, status="concluido"
    ):
        self.conteudo = conteudo
        self.conteudo_sincrono = conteudo_sincrono or conteudo
        self.andamentos = andamentos  # vezes que o lote responde "em_andamento"
        self.status = status
        self.lotes: dict[str, list[Pedido]] = {}
        self.sincronos: list[str] = []
        self.consultas = 0

    def gerar(self, pedido):
        self.sincronos.append(pedido.id)
        return Resposta(id=pedido.id, conteudo=self.conteudo_sincrono(pedido), tokens_entrada=100)

    def enviar_lote(self, pedidos):
        lote_id = f"lote_{next(_IDS_DE_LOTE)}"
        self.lotes[lote_id] = list(pedidos)
        return lote_id

    def situacao_lote(self, lote_id):
        self.consultas += 1
        if self.andamentos > 0:
            self.andamentos -= 1
            return SituacaoLote("em_andamento", "validating")
        return SituacaoLote(self.status)

    def resultados_lote(self, lote_id):
        return [
            Resposta(id=p.id, conteudo=self.conteudo(p), tokens_entrada=100, tokens_saida=10)
            for p in self.lotes[lote_id]
        ]


@pytest.fixture
def db(db_temporario):
    for wid, pagina in PAGINAS.items():
        sid = f"sp_especie_{wid}"
        db_temporario[RAW_WIKIAVES].insert_one({"_id": wid, "dados": {"pagina": pagina}})
        db_temporario[SPECIES_REGISTRY].insert_one(
            {"species_id": sid, "nome_cientifico": f"Especie {wid}", "chaves": {"wikiaves": wid}}
        )
    return db_temporario


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("REPORTS_DIR", str(tmp_path))
    get_settings.cache_clear()
    return get_settings()


def extrair(db, fornecedor, settings, **opcoes):
    extrator = Extrator(db, fornecedor, settings, intervalo_s=0, dormir=lambda _: None)
    return extrator.executar(**opcoes)


def _extracoes(db):
    return {d["_id"]: d for d in db[SPECIES_EXTRACTIONS].find()}


def test_lote_completo_e_segunda_execucao_sem_chamadas(db, settings):
    llm = Falso(andamentos=2)
    r1 = extrair(db, llm, settings)
    assert (r1.pares, r1.sem_texto, r1.enviados) == (6, 2, 4)
    assert len(llm.lotes) == 1 and llm.consultas == 3 and llm.sincronos == []

    ext = _extracoes(db)
    assert len(ext) == 6  # A1
    assert ext["sp_especie_2:b01_aparencia"]["validacao"]["erro"] == SEM_TEXTO
    assert ext["sp_especie_2:b03_textos_busca"]["validacao"]["ok"] is True
    b01 = ext["sp_especie_1:b01_aparencia"]
    assert b01["validacao"] == {"ok": True, "evidencias_nao_encontradas": [], "erro": None}
    assert b01["saida"]["cores"] == [{"valor": "azul", "evidencia": "o macho é azul"}]
    assert db[LLM_BATCHES].find_one()["status"] == "coletado"
    assert (settings.REPORTS_DIR / "extract.tsv").read_text().count("\n") == 7

    llm2 = Falso()
    r2 = extrair(db, llm2, settings)
    assert (r2.cache, r2.enviados, r2.sem_texto) == (6, 0, 0)  # A3
    assert llm2.lotes == {} and llm2.sincronos == [] and llm2.consultas == 0


def test_retomada_de_lote_sem_reenvio(db, settings):
    llm = Falso()
    r1 = extrair(db, llm, settings, esperar=False)
    (lote_id,) = r1.lotes_enviados
    assert r1.em_lote == 4
    assert db[LLM_BATCHES].find_one()["status"] == "enviado"
    assert len(_extracoes(db)) == 2  # só as sem_texto

    # O processo "caiu": outra execução encontra o lote aberto e só coleta (A5).
    r2 = extrair(db, llm, settings)
    assert len(llm.lotes) == 1 and r2.enviados == 0 and r2.lotes_coletados == [lote_id]
    assert all(
        d["validacao"]["ok"] or d["validacao"]["erro"] == SEM_TEXTO for d in _extracoes(db).values()
    )


def test_lote_em_andamento_nao_e_reenviado(db, settings):
    llm = Falso(andamentos=10)
    extrair(db, llm, settings, esperar=False)
    r2 = extrair(db, llm, settings, esperar=False)
    assert len(llm.lotes) == 1 and r2.enviados == 0 and r2.em_lote == 4
    assert r2.lotes_em_andamento == list(llm.lotes)


def test_resposta_invalida_refeita_uma_vez(db, settings):
    def b01_invalida(p):
        if p.schema["name"] == "B01Aparencia":
            return json.dumps({"cores": [{"valor": "dourado", "evidencia": "x"}]})
        return saida_valida(p)

    llm = Falso(conteudo=b01_invalida, conteudo_sincrono=saida_valida)
    r = extrair(db, llm, settings)
    (pedidos,) = llm.lotes.values()
    assert r.retentativas == 1 and llm.sincronos == [p.id for p in pedidos if "b01" in p.id]
    assert _extracoes(db)["sp_especie_1:b01_aparencia"]["validacao"]["ok"] is True


def test_falha_dupla_grava_erro_e_volta_na_proxima(db, settings):
    llm = Falso(conteudo=lambda p: "{quebrado")
    extrair(db, llm, settings)
    b01 = _extracoes(db)["sp_especie_1:b01_aparencia"]
    assert b01["validacao"]["ok"] is False and b01["validacao"]["erro"].startswith("invalido")
    assert b01["saida"] == {}

    llm2 = Falso()
    r2 = extrair(db, llm2, settings)
    assert r2.enviados == 4 and r2.cache == 2  # só as sem_texto ficam em cache


def test_texto_mudou_depois_do_envio(db, settings):
    llm = Falso()
    extrair(db, llm, settings, esperar=False)
    db[RAW_WIKIAVES].update_one(
        {"_id": "1"}, {"$set": {"dados.pagina.caracteristicas": "Mede 14 centímetros."}}
    )
    r2 = extrair(db, llm, settings)
    # b01 e b03 leem as características: as respostas antigas não valem mais.
    assert r2.descartados == 2
    assert len(llm.lotes) == 2
    segundo = list(llm.lotes.values())[1]
    assert sorted(p.id.split(":")[1] for p in segundo) == ["b01_aparencia", "b03_textos_busca"]


def test_lote_que_falhou_volta_a_pendente(db, settings):
    llm = Falso(status="falhou")
    extrair(db, llm, settings)
    assert db[LLM_BATCHES].find_one()["status"] == "falhou"
    r2 = extrair(db, Falso(), settings)
    assert r2.enviados == 4


def test_sincrono_e_limite(db, settings):
    llm = Falso()
    r = extrair(db, llm, settings, sincrono=True, limite=1)
    assert r.pares == 3 and len(llm.sincronos) == 3 and llm.lotes == {}
    assert set(_extracoes(db)) == {
        f"sp_especie_1:{p}" for p in ("b01_aparencia", "b02_comportamento", "b03_textos_busca")
    }
