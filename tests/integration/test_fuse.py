"""Integração: `fuse` e `validate` em banco temporário (pytest -m integration).

Cobre o aceite do Marco 5: uma ficha por espécie do escopo (A3), segunda execução
sem gravação (A4), `species_occurrence` chaveada por `species_id` (A5) e o
`dq_status` mantido quando a ficha não muda e zerado quando muda.
"""

import pytest

from avesrag_builder.core.models import Species
from avesrag_builder.core.settings import get_settings
from avesrag_builder.db.collections import (
    RAW_AVONET,
    RAW_BIRDALBUM,
    RAW_BIRDBASE,
    RAW_CBRO,
    RAW_EBIRD,
    RAW_IBGE,
    RAW_WIKIAVES,
    SPECIES,
    SPECIES_EXTRACTIONS,
    SPECIES_OCCURRENCE,
    SPECIES_REGISTRY,
)
from avesrag_builder.fuse import species as fuse
from avesrag_builder.validate import pipeline as validate

pytestmark = pytest.mark.integration

PILOTO = "3170206"


def _raw(db, collection, _id, dados):
    db[collection].insert_one({"_id": _id, "dados": dados, "source_hash": "x"})


def _extracao(db, sid, prompt, saida, ok=True):
    db[SPECIES_EXTRACTIONS].insert_one(
        {
            "_id": f"{sid}:{prompt}",
            "species_id": sid,
            "prompt": prompt,
            "versao": "2.0",
            "saida": saida,
            "validacao": {"ok": ok, "evidencias_nao_encontradas": [], "erro": None},
        }
    )


def _item(valor):
    return {"valor": valor, "evidencia": f"texto com {valor}"}


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("REPORTS_DIR", str(tmp_path))
    monkeypatch.setenv("PILOTO_MUNICIPIO_IBGE", PILOTO)
    get_settings.cache_clear()
    return get_settings()


@pytest.fixture
def db(db_temporario):
    db = db_temporario
    # bem-te-vi: completo (apta); tiziu: sem extrações (incompleta);
    # sanhaço: fora do piloto (não tem registro no eBird do município).
    especies = [
        ("sp_pitangus_sulphuratus", "Pitangus sulphuratus", "bem-te-vi", "1", "grekis"),
        ("sp_volatinia_jacarina", "Volatinia jacarina", "tiziu", "2", "blbgra1"),
        ("sp_thraupis_sayaca", "Thraupis sayaca", "sanhaço-cinzento", "3", "sayta1"),
    ]
    for sid, nome, comum, wid, ebird in especies:
        db[SPECIES_REGISTRY].insert_one(
            {
                "species_id": sid,
                "nome_cientifico": nome,
                "nome_comum": comum,
                "chaves": {
                    "wikiaves": wid,
                    "cbro": f"CBRO#{wid}",
                    "avonet": f"birdlife:{nome}",
                    "birdbase": wid,
                    "ebird": ebird,
                },
                "match": dict.fromkeys(["cbro", "avonet", "birdbase", "ebird"], "exato"),
            }
        )
        genero = nome.split()[0]
        _raw(db, RAW_WIKIAVES, wid, {"lista": {"nome_comum": comum}, "pagina": {}})
        _raw(
            db,
            RAW_CBRO,
            f"CBRO#{wid}",
            {"Ordem": "Passeriformes", "Família": "Thraupidae", "Gênero": genero, "Status": "BR"},
        )
        _raw(
            db,
            RAW_AVONET,
            f"birdlife:{nome}",
            {"Habitat": "Woodland", "Trophic.Niche": "Granivore", "Mass": 10.0},
        )
        _raw(db, RAW_BIRDBASE, wid, {"2024 IUCN Red List category": "LC"})
    _raw(
        db,
        RAW_EBIRD,
        f"municipio:{PILOTO}",
        {"geocodigo": PILOTO, "nome": "Uberlândia", "uf": "MG", "especies": ["grekis", "blbgra1"]},
    )
    _raw(
        db,
        RAW_IBGE,
        PILOTO,
        {"Nome do município": "Uberlândia", "Sigla da UF": "MG", "Bioma predominante": "Cerrado"},
    )
    album = {"sticker_license": "CC-BY-4.0", "meets_quality_bar": "True", "reference_type": "photo"}
    # bem-te-vi casa pelo código do eBird (nome diferente na AviList); tiziu, pelo nome.
    _raw(
        db,
        RAW_BIRDALBUM,
        "Pitangus_outro",
        {
            **album,
            "scientific_name": "Pitangus outro",
            "ebird": "grekis",
            "sticker_file": "s/a.webp",
        },
    )
    _raw(
        db,
        RAW_BIRDALBUM,
        "Volatinia_jacarina",
        {**album, "scientific_name": "Volatinia jacarina", "ebird": "", "sticker_file": "s/b.webp"},
    )
    sid = "sp_pitangus_sulphuratus"
    b01 = dict.fromkeys(["comprimento_cm", "cores", "cores_por_parte", "marcas", "cauda"])
    b01 |= {
        "comprimento_cm": {"min": 22, "max": 24, "evidencia": "mede 23 cm"},
        "cores": [_item("amarelo"), _item("preto")],
    }
    _extracao(db, sid, "b01_aparencia", b01)
    b02 = dict.fromkeys(["ambiente", "onde_estava", "o_que_fazia", "grupo", "atividade"])
    _extracao(db, sid, "b02_comportamento", b02 | {"ambiente": [_item("area_urbana")]})
    _extracao(
        db,
        sid,
        "b03_textos_busca",
        {"aparencia": "Barriga amarela.", "comportamento_ambiente": None, "voz_habitos": None},
    )
    return db


def test_fuse_e_validate_do_piloto(db, settings):
    r1 = fuse.executar(db, piloto=True, settings=settings)
    assert r1.escopo == 2
    assert r1.species.inseridos == 2
    assert r1.erros == []
    fichas = {d["species_id"]: d for d in db[SPECIES].find()}
    assert set(fichas) == {"sp_pitangus_sulphuratus", "sp_volatinia_jacarina"}
    for doc in fichas.values():
        Species.from_mongo(doc)  # A3: válida no modelo
    bem_te_vi = fichas["sp_pitangus_sulphuratus"]
    assert bem_te_vi["atributos"]["tamanho"] == ["medio"]
    assert bem_te_vi["atributos"]["bico_tipo"] == "granivoro"
    assert bem_te_vi["ocorrencia"] == {"biomas": ["Cerrado"], "n_municipios": 1}
    assert bem_te_vi["midia"]["ilustracao"]["url"].endswith("/s/a.webp")
    assert bem_te_vi["_prov"]["midia.ilustracao"] == {"fonte": "birdalbum", "metodo": "ebird"}
    tiziu = fichas["sp_volatinia_jacarina"]
    assert tiziu["_prov"]["midia.ilustracao"] == {"fonte": "birdalbum", "metodo": "nome"}
    assert (settings.REPORTS_DIR / "fuse.tsv").exists()

    # A5: species_occurrence por species_id (o sanhaço não tem registro)
    occ = {d["species_id"] for d in db[SPECIES_OCCURRENCE].find()}
    assert occ == {"sp_pitangus_sulphuratus", "sp_volatinia_jacarina"}

    v1 = validate.executar(db, piloto=True, settings=settings)
    assert v1.status == {"apta": 1, "incompleta": 1}
    assert v1.gravados == 2
    status = {d["species_id"]: d["_meta"]["dq_status"] for d in db[SPECIES].find()}
    assert status == {"sp_pitangus_sulphuratus": "apta", "sp_volatinia_jacarina": "incompleta"}
    tsv = (settings.REPORTS_DIR / "validate.tsv").read_text()
    assert "sp_volatinia_jacarina\tincompleta\tcores (0 de 2); b03.aparencia" in tsv


def test_segunda_execucao_nao_grava(db, settings):
    fuse.executar(db, piloto=True, settings=settings)
    validate.executar(db, piloto=True, settings=settings)
    antes = {d["species_id"]: d["_meta"]["built_at"] for d in db[SPECIES].find()}

    r2 = fuse.executar(db, piloto=True, settings=settings)
    assert (r2.species.gravados, r2.species.inalterados) == (0, 2)
    assert (r2.ocorrencia.gravados, r2.ocorrencia.inalterados) == (0, 2)
    v2 = validate.executar(db, piloto=True, settings=settings)
    assert (v2.gravados, v2.inalterados) == (0, 2)

    depois = {d["species_id"]: d["_meta"] for d in db[SPECIES].find()}
    assert {k: m["built_at"] for k, m in depois.items()} == antes
    assert depois["sp_pitangus_sulphuratus"]["dq_status"] == "apta"  # mantido


def test_ficha_que_muda_perde_o_dq_status(db, settings):
    fuse.executar(db, piloto=True, settings=settings)
    validate.executar(db, piloto=True, settings=settings)
    _id_antes = db[SPECIES].find_one({"species_id": "sp_pitangus_sulphuratus"})["_id"]

    db[RAW_BIRDBASE].update_one({"_id": "1"}, {"$set": {"dados.2024 IUCN Red List category": "NT"}})
    r = fuse.executar(db, piloto=True, settings=settings)
    assert (r.species.atualizados, r.species.inalterados) == (1, 1)

    doc = db[SPECIES].find_one({"species_id": "sp_pitangus_sulphuratus"})
    assert doc["_id"] == _id_antes  # o ObjectId é mantido
    assert doc["iucn"] == "NT"
    assert "dq_status" not in doc["_meta"]
    v = validate.executar(db, piloto=True, settings=settings)
    assert (v.gravados, v.inalterados) == (1, 1)


def test_sem_piloto_usa_todo_o_registry(db, settings):
    r = fuse.executar(db, piloto=False, settings=settings)
    assert r.escopo == 3
    sanhaco = db[SPECIES].find_one({"species_id": "sp_thraupis_sayaca"})
    assert "ocorrencia" not in sanhaco
    assert sanhaco["_prov"]["atributos.tamanho"] == {"fonte": "avonet", "metodo": "massa"}


def test_validate_avisa_especie_sem_ficha(db, settings):
    v = validate.executar(db, piloto=True, settings=settings)
    assert v.sem_ficha == ["sp_pitangus_sulphuratus", "sp_volatinia_jacarina"]
    assert v.avaliadas == 0
