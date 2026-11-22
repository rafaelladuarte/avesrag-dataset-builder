"""Integração: `docs` e `index` em banco temporário (pytest -m integration).

Cobre o aceite do Marco 6 com um embedder falso (vetores one-hot determinísticos
de 3.072 posições): documentos só das aptas (A2), segunda execução sem chamadas
(A3), remoção quando a espécie deixa de ser apta e índices criados, consultáveis
e não recriados (A4).
"""

import hashlib

import pytest

from avesrag_builder.core.models import EMBEDDING_DIM
from avesrag_builder.core.settings import get_settings
from avesrag_builder.db.collections import (
    RAW_EBIRD,
    SPECIES,
    SPECIES_EXTRACTIONS,
    SPECIES_REGISTRY,
    SPECIES_RETRIEVAL_DOCS,
)
from avesrag_builder.docs import indices
from avesrag_builder.docs.busca import buscar_especies
from avesrag_builder.docs.pipeline import executar
from avesrag_builder.llm.base import Embeddings

pytestmark = pytest.mark.integration

PILOTO = "3170206"


def vetor(texto: str) -> list[float]:
    v = [0.0] * EMBEDDING_DIM
    v[int(hashlib.sha256(texto.encode()).hexdigest(), 16) % EMBEDDING_DIM] = 1.0
    return v


class Falso:
    nome = "falso"

    def __init__(self):
        self.textos: list[str] = []

    def embeddings(self, textos, modelo):
        self.textos += textos
        return Embeddings(vetores=[vetor(t) for t in textos], tokens=len(textos) * 5)


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("REPORTS_DIR", str(tmp_path))
    monkeypatch.setenv("PILOTO_MUNICIPIO_IBGE", PILOTO)
    get_settings.cache_clear()
    return get_settings()


ESPECIES = {
    # species_id: (dq_status, textos do b03)
    "sp_pitangus_sulphuratus": ("apta", ("Barriga amarela.", "Pousa em fios.", "Canta bem-te-vi.")),
    "sp_ramphastos_toco": ("apta", ("Bico enorme e laranja.", "Vive em bandos.", None)),
    "sp_volatinia_jacarina": ("incompleta", ("Todo preto.", "Pula no capim.", "Canto curto.")),
}


@pytest.fixture
def db(db_temporario):
    db = db_temporario
    codigos = []
    for i, (sid, (status, textos)) in enumerate(ESPECIES.items()):
        codigo = f"cod{i}"
        codigos.append(codigo)
        db[SPECIES_REGISTRY].insert_one(
            {"species_id": sid, "nome_cientifico": sid, "chaves": {"ebird": codigo}}
        )
        db[SPECIES].insert_one(
            {
                "species_id": sid,
                "nome_cientifico": sid.removeprefix("sp_").replace("_", " ").capitalize(),
                "nomes": {"pt": [sid.split("_")[1]]},
                "taxonomia": {"familia": "Familia"},
                "atributos": {"cores": ["preto", "amarelo"], "tamanho": ["medio"]},
                "_meta": {"dq_status": status},
            }
        )
        aparencia, comportamento, voz = textos
        db[SPECIES_EXTRACTIONS].insert_one(
            {
                "_id": f"{sid}:b03_textos_busca",
                "species_id": sid,
                "prompt": "b03_textos_busca",
                "saida": {
                    "aparencia": aparencia,
                    "comportamento_ambiente": comportamento,
                    "voz_habitos": voz,
                },
                "validacao": {"ok": True},
            }
        )
    db[RAW_EBIRD].insert_one({"_id": f"municipio:{PILOTO}", "dados": {"especies": codigos}})
    return db


def test_docs_so_das_aptas_e_segunda_execucao_sem_chamadas(db, settings):
    falso = Falso()
    r1 = executar(db, lambda: falso, piloto=True, settings=settings)
    ids = sorted(d["_id"] for d in db[SPECIES_RETRIEVAL_DOCS].find())
    assert ids == [
        "sp_pitangus_sulphuratus:aparencia",
        "sp_pitangus_sulphuratus:comportamento_ambiente",
        "sp_pitangus_sulphuratus:voz_habitos",
        "sp_ramphastos_toco:aparencia",
        "sp_ramphastos_toco:comportamento_ambiente",
    ]
    assert r1.aptas == 2 and r1.embeddings == 5
    doc = db[SPECIES_RETRIEVAL_DOCS].find_one({"_id": "sp_ramphastos_toco:aparencia"})
    assert doc["texto"] == "Bico enorme e laranja."
    assert doc["nomes"] == ["ramphastos", "Ramphastos toco"]
    assert doc["filtros"] == {
        "tamanho": ["medio"],
        "cores": ["preto", "amarelo"],
        "familia": "Familia",
    }
    assert doc["modelo"] == settings.EMBEDDING_MODEL
    assert (settings.REPORTS_DIR / "docs.tsv").exists()

    def sem_embedder():
        raise AssertionError("não deveria criar o embedder")

    r2 = executar(db, sem_embedder, piloto=True, settings=settings)  # A3
    assert r2.embeddings == 0
    assert r2.status["inalterado"] == 5


def test_filtro_mudou_reaproveita_e_deixou_de_ser_apta_sai(db, settings):
    executar(db, Falso, piloto=True, settings=settings)
    db[SPECIES].update_one(
        {"species_id": "sp_pitangus_sulphuratus"}, {"$set": {"atributos.cores": ["amarelo"]}}
    )
    db[SPECIES].update_one(
        {"species_id": "sp_ramphastos_toco"}, {"$set": {"_meta.dq_status": "incompleta"}}
    )
    falso = Falso()
    r = executar(db, lambda: falso, piloto=True, settings=settings)
    assert falso.textos == []  # só filtros: o embedding é reaproveitado
    assert r.status["so_filtros"] == 3
    assert r.status["removido"] == 2
    restantes = {d["species_id"] for d in db[SPECIES_RETRIEVAL_DOCS].find()}
    assert restantes == {"sp_pitangus_sulphuratus"}
    doc = db[SPECIES_RETRIEVAL_DOCS].find_one({"_id": "sp_pitangus_sulphuratus:aparencia"})
    assert doc["filtros"]["cores"] == ["amarelo"]
    assert doc["embedding"] == vetor("Barriga amarela.")


def test_indices_criados_consultaveis_e_nao_recriados(db, settings):
    executar(db, Falso, piloto=True, settings=settings)
    r1 = indices.garantir(db, timeout_s=180)
    assert r1.acoes == {indices.INDICE_VETOR: "criado", indices.INDICE_TEXTO: "criado"}
    assert r1.documentos == 5

    cands = buscar_especies(db, vetor("Bico enorme e laranja."), k=10)
    assert cands[0].species_id == "sp_ramphastos_toco"
    filtrado = buscar_especies(
        db, vetor("Bico enorme e laranja."), filtro={"dominio": "voz_habitos"}
    )
    assert {c.species_id for c in filtrado} == {"sp_pitangus_sulphuratus"}

    texto = list(
        db[SPECIES_RETRIEVAL_DOCS].aggregate(
            [
                {
                    "$search": {
                        "index": indices.INDICE_TEXTO,
                        "text": {"query": "amarelas", "path": "texto"},  # radical em português
                    }
                },
                {"$project": {"_id": 1}},
            ]
        )
    )
    assert [d["_id"] for d in texto] == ["sp_pitangus_sulphuratus:aparencia"]

    r2 = indices.garantir(db, timeout_s=180)  # A4
    assert set(r2.acoes.values()) == {"inalterado"}
