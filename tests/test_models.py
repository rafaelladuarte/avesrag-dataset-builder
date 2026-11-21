"""Testes para avesrag_builder.core.models.

Os exemplos vêm do documento "Modelo de Dados", com duas correções:
`_prov.ref` aponta para o prompt b01 (o exemplo cita o antigo p05) e o
embedding é curto, com a dimensão passada no contexto da validação.
"""

import copy
import csv

import pytest
from pydantic import ValidationError

from avesrag_builder.core.models import (
    Extraction,
    RawEnvelope,
    RetrievalDoc,
    Species,
    SpeciesRegistry,
    compute_source_hash,
    slug_species_id,
)
from avesrag_builder.core.settings import get_settings

REGISTRY = {
    "_id": "sp_pitangus_sulphuratus",
    "nome_cientifico": "Pitangus sulphuratus",
    "nome_comum": "bem-te-vi",
    "chaves": {
        "wikiaves": "11450",
        "cbro": "CBRO#1234",
        "avonet": "Pitangus sulphuratus",
        "birdbase": "Pitangus sulphuratus",
        "ebird": "grekis",
    },
    "match": {"avonet": "exato", "birdbase": "exato", "ebird": "exato"},
    "criado_em": "2026-11-20T00:00:00Z",
}

SPECIES = {
    "_id": "sp_pitangus_sulphuratus",
    "nome_cientifico": "Pitangus sulphuratus",
    "nomes": {"pt": ["bem-te-vi"], "en": ["Great Kiskadee"]},
    "taxonomia": {"ordem": "Passeriformes", "familia": "Tyrannidae", "genero": "Pitangus"},
    "status_ocorrencia": "BR",
    "iucn": "LC",
    "atributos": {
        "tamanho": ["medio"],
        "comprimento_cm": 23,
        "cores": ["amarelo", "preto", "branco", "marrom"],
        "cores_por_parte": [
            {"parte": "barriga", "cor": "amarelo"},
            {"parte": "cabeca", "cor": "preto"},
        ],
        "marcas": ["mascara", "sobrancelha"],
        "bico_tipo": "generalista",
        "cauda": ["curta"],
        "ambiente": ["area_urbana", "parque_jardim", "borda_de_mata", "beira_de_agua"],
        "onde_estava": ["meio_da_arvore", "copa"],
        "o_que_fazia": ["pousada", "cacando_em_voo"],
        "grupo": ["sozinha", "casal"],
        "atividade": ["diurna"],
    },
    "ocorrencia": {"biomas": ["Cerrado", "Mata Atlântica"], "n_municipios": 4210},
    "midia": {"foto": "https://...", "url_wikiaves": "/wiki/bem-te-vi"},
    "_prov": {
        "atributos.bico_tipo": {"fonte": "regra_familia"},
        "atributos.cores": {"fonte": "wikiaves", "metodo": "llm", "ref": "b01_aparencia@2.0"},
    },
    "_meta": {"schema_version": "2.0", "built_at": "2026-11-20T00:00:00Z", "dq_status": "apta"},
}

EXTRACTION = {
    "_id": "sp_pitangus_sulphuratus:b01_aparencia",
    "species_id": "sp_pitangus_sulphuratus",
    "prompt": "b01_aparencia",
    "versao": "2.0",
    "modelo": "gpt-6-luna",
    "input_hash": "9f3c",
    "saida": {"comprimento_cm": {"min": 22, "max": 25, "evidencia": "Mede de 22 a 25 cm"}},
    "validacao": {"ok": True, "evidencias_nao_encontradas": []},
    "criado_em": "2026-11-20T00:00:00Z",
}

RETRIEVAL = {
    "_id": "sp_pitangus_sulphuratus:aparencia",
    "species_id": "sp_pitangus_sulphuratus",
    "dominio": "aparencia",
    "texto": "Bem-te-vi. Ave de tamanho médio, barriga amarela, cabeça preta...",
    "embedding": [0.012, -0.034, 0.5],
    "filtros": {"tamanho": ["medio"], "cores": ["amarelo", "preto"], "bico_tipo": "generalista"},
    "built_at": "2026-11-20T00:00:00Z",
}


class TestSlug:
    @pytest.mark.parametrize(
        "nome, esperado",
        [
            ("Pitangus sulphuratus", "sp_pitangus_sulphuratus"),
            ("Hydrobates gr. castro", "sp_hydrobates_gr_castro"),
            ("Lophornis cf. delattrei", "sp_lophornis_cf_delattrei"),
            ("  Rhea   americana ", "sp_rhea_americana"),
        ],
    )
    def test_casos(self, nome, esperado):
        assert slug_species_id(nome) == esperado

    def test_vazio(self):
        with pytest.raises(ValueError):
            slug_species_id(" . ")

    def test_todas_as_especies_do_wikiaves_geram_slugs_unicos(self):
        with open(get_settings().WIKIAVES_CSV, encoding="utf-8") as f:
            nomes = [row["nome_cientifico"] for row in csv.DictReader(f)]
        assert len(nomes) == 1975
        assert len({slug_species_id(n) for n in nomes}) == 1975


class TestRawEnvelope:
    def test_hash_independe_da_ordem(self):
        assert compute_source_hash({"a": 1, "b": [1, 2]}) == compute_source_hash(
            {"b": [1, 2], "a": 1}
        )

    def test_hash_muda_com_o_dado(self):
        assert compute_source_hash({"a": 1}) != compute_source_hash({"a": 2})

    def test_build_e_to_mongo(self):
        env = RawEnvelope.build("10001", {"nome": "ema"})
        doc = env.to_mongo()
        assert doc["_id"] == "10001"
        assert doc["dados"] == {"nome": "ema"}
        assert doc["source_hash"] == compute_source_hash({"nome": "ema"})
        assert doc["ingerido_em"].tzinfo is not None

    def test_id_vazio(self):
        with pytest.raises(ValidationError):
            RawEnvelope.build("", {})


class TestSpeciesRegistry:
    def test_exemplo_do_modelo(self):
        reg = SpeciesRegistry.model_validate(REGISTRY)
        assert reg.to_mongo()["_id"] == "sp_pitangus_sulphuratus"

    def test_sem_match_guarda_null(self):
        data = copy.deepcopy(REGISTRY)
        data["chaves"]["avonet"] = None
        data["match"]["avonet"] = "sem_match"
        doc = SpeciesRegistry.model_validate(data).to_mongo()
        assert doc["chaves"]["avonet"] is None

    def test_chave_nula_com_match_exato(self):
        data = copy.deepcopy(REGISTRY)
        data["chaves"]["ebird"] = None
        with pytest.raises(ValidationError, match="incoerente"):
            SpeciesRegistry.model_validate(data)

    def test_id_diferente_do_slug(self):
        data = copy.deepcopy(REGISTRY)
        data["_id"] = "sp_pitangus"
        with pytest.raises(ValidationError, match="slug"):
            SpeciesRegistry.model_validate(data)

    def test_id_fora_do_padrao(self):
        data = copy.deepcopy(REGISTRY)
        data["_id"] = "Pitangus sulphuratus"
        with pytest.raises(ValidationError):
            SpeciesRegistry.model_validate(data)


class TestSpecies:
    def test_exemplo_do_modelo(self):
        sp = Species.model_validate(SPECIES)
        doc = sp.to_mongo()
        assert doc["_prov"]["atributos.cores"]["ref"] == "b01_aparencia@2.0"
        assert doc["_meta"]["dq_status"] == "apta"

    def test_campos_sem_valor_ficam_de_fora(self):
        data = copy.deepcopy(SPECIES)
        del data["iucn"]
        del data["atributos"]["grupo"]
        doc = Species.model_validate(data).to_mongo()
        assert "iucn" not in doc
        assert "grupo" not in doc["atributos"]
        assert "en" in doc["nomes"]

    @pytest.mark.parametrize(
        "caminho, valor",
        [
            (("iucn",), ""),
            (("atributos", "cores"), []),
            (("atributos", "bico_tipo"), "  "),
            (("ocorrencia", "biomas"), []),
        ],
    )
    def test_rejeita_vazios(self, caminho, valor):
        data = copy.deepcopy(SPECIES)
        alvo = data
        for chave in caminho[:-1]:
            alvo = alvo[chave]
        alvo[caminho[-1]] = valor
        with pytest.raises(ValidationError, match="vazia"):
            Species.model_validate(data)

    def test_rejeita_campo_desconhecido(self):
        data = copy.deepcopy(SPECIES)
        data["atributos"]["cor_favorita"] = ["azul"]
        with pytest.raises(ValidationError):
            Species.model_validate(data)

    def test_taxonomia_incompleta_e_aceita(self):
        # A ficha é gravada e o `validate` a marca como bloqueada.
        data = copy.deepcopy(SPECIES)
        data["taxonomia"] = {"genero": "Pitangus"}
        Species.model_validate(data)


class TestExtraction:
    def test_exemplo_do_modelo(self):
        Extraction.model_validate(EXTRACTION)

    def test_id_incoerente(self):
        data = dict(EXTRACTION, prompt="b02_comportamento")
        with pytest.raises(ValidationError, match="_id deve ser"):
            Extraction.model_validate(data)


class TestRetrievalDoc:
    def test_exemplo_do_modelo(self):
        RetrievalDoc.model_validate(RETRIEVAL, context={"embedding_dim": 3})

    def test_dimensao_padrao_3072(self):
        with pytest.raises(ValidationError, match="esperado 3072"):
            RetrievalDoc.model_validate(RETRIEVAL)
        RetrievalDoc.model_validate(dict(RETRIEVAL, embedding=[0.0] * 3072))

    def test_dominio_invalido(self):
        data = dict(RETRIEVAL, _id="sp_pitangus_sulphuratus:canto", dominio="canto")
        with pytest.raises(ValidationError):
            RetrievalDoc.model_validate(data, context={"embedding_dim": 3})

    def test_id_incoerente(self):
        data = dict(RETRIEVAL, _id="sp_pitangus_sulphuratus:voz_habitos")
        with pytest.raises(ValidationError, match="_id deve ser"):
            RetrievalDoc.model_validate(data, context={"embedding_dim": 3})
