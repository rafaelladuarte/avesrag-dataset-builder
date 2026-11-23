"""Integração: ingest inaturalist com o MongoDB real e a API simulada."""

import pytest
import requests

from avesrag_builder.core.settings import Settings
from avesrag_builder.ingest import inaturalist as inat

pytestmark = pytest.mark.integration

TAXONS = {
    # nome consultado -> resultados da busca de táxons
    "Astur bicolor": [{"id": 1, "name": "Astur bicolor", "rank": "species"}],
    "Pitangus sulphuratus": [{"id": 2, "name": "Pitangus sulphuratus", "rank": "species"}],
    # sinônimo que o iNaturalist juntou ao bem-te-vi (lump)
    "Pitangus lumpado": [
        {
            "id": 2,
            "name": "Pitangus sulphuratus",
            "rank": "species",
            "matched_term": "Pitangus lumpado",
        }
    ],
}


def foto(obs_id, licenca="cc-by"):
    return {
        "id": obs_id,
        "cached_votes_total": 0,
        "observed_on": "2024-01-02",
        "place_guess": "Brasil",
        "user": {"login": "fulano", "name": "Fulano"},
        "photos": [
            {
                "id": obs_id * 10,
                "license_code": licenca,
                "url": f"https://inaturalist-open-data.s3.amazonaws.com/photos/{obs_id}/square.jpg",
                "attribution": "(c) Fulano",
            }
        ],
    }


class ApiFalsa:
    """Responde como a API v1 e conta as chamadas; `falhar_em` derruba uma chamada."""

    def __init__(self):
        self.chamadas: list[tuple[str, object]] = []
        self.observacoes = {
            (1, True): [foto(10)],
            (1, False): [],
            (2, True): [],
            (2, False): [foto(20)],
        }
        self.falhar_em: set[tuple[str, object]] = set()

    def get(self, url, params=None):
        if url.endswith("/taxa"):
            chave = ("taxa", params["q"])
            resposta = {"results": TAXONS.get(params["q"], [])}
        else:
            brasil = "place_id" in params
            chave = ("observacoes", (params["taxon_id"], brasil))
            resposta = {"results": self.observacoes[(params["taxon_id"], brasil)]}
        self.chamadas.append(chave)
        if chave in self.falhar_em:
            raise requests.ConnectionError("rota perdida")
        return resposta

    def observacoes_chamadas(self):
        return [c for c in self.chamadas if c[0] == "observacoes"]


@pytest.fixture
def db(db_temporario):
    registry = [
        ("sp_accipiter_bicolor", "Accipiter bicolor", "bichaw1"),
        ("sp_pitangus_sulphuratus", "Pitangus sulphuratus", "grekis"),
        ("sp_pitangus_lumpado", "Pitangus lumpado", None),
        ("sp_sem_taxon", "Nada encontrado", None),
    ]
    db_temporario.species_registry.insert_many(
        [
            {"species_id": s, "nome_cientifico": n, "chaves": {"ebird": c} if c else {}}
            for s, n, c in registry
        ]
    )
    db_temporario.raw_ebird.insert_many(
        [
            {"_id": "taxon:bichaw1", "dados": {"sciName": "Astur bicolor"}},
            {"_id": "taxon:grekis", "dados": {"sciName": "Pitangus sulphuratus"}},
        ]
    )
    return db_temporario


@pytest.fixture
def settings():
    return Settings(_env_file=None, PILOTO_MUNICIPIO_IBGE="3170206")


def ingerir(db, api, settings, **kw):
    (resultado,) = inat.ingerir(db, settings=settings, cliente=api, **kw)
    return resultado


def test_grava_e_segunda_execucao_nao_chama_nem_grava(db, settings):
    api = ApiFalsa()
    r = ingerir(db, api, settings)
    assert (r.inseridos, r.atualizados, r.erros) == (2, 0, [])

    gaviao = db.raw_inaturalist.find_one({"_id": "taxon:1"})["dados"]
    assert gaviao["taxon"] == {"id": 1, "nome": "Astur bicolor", "rank": "species"}
    assert gaviao["nomes"] == ["Astur bicolor"]  # o nome do eBird casou primeiro
    assert [f["observacao_id"] for f in gaviao["fotos_brasil"]] == [10]
    assert gaviao["fotos_mundo"] == []

    # lump: um registro só, com os nomes das duas espécies; fotos buscadas uma vez
    bentevi = db.raw_inaturalist.find_one({"_id": "taxon:2"})["dados"]
    assert bentevi["nomes"] == ["Pitangus lumpado", "Pitangus sulphuratus"]
    assert api.observacoes_chamadas().count(("observacoes", (2, True))) == 1

    segunda = ApiFalsa()
    r2 = ingerir(db, segunda, settings)
    assert (r2.inseridos, r2.atualizados, r2.inalterados) == (0, 0, 0)
    assert segunda.observacoes_chamadas() == []
    # só a espécie sem táxon é consultada de novo
    assert segunda.chamadas == [("taxa", "Nada encontrado")]


def test_falha_nao_grava_e_a_proxima_execucao_retoma(db, settings):
    api = ApiFalsa()
    api.falhar_em = {("observacoes", (1, False))}
    r = ingerir(db, api, settings)
    assert len(r.erros) == 1 and "sp_accipiter_bicolor" in r.erros[0]
    assert db.raw_inaturalist.find_one({"_id": "taxon:1"}) is None
    assert db.raw_inaturalist.find_one({"_id": "taxon:2"}) is not None

    retomada = ApiFalsa()
    r2 = ingerir(db, retomada, settings)
    assert (r2.inseridos, r2.erros) == (1, [])
    assert {c[1][0] for c in retomada.observacoes_chamadas()} == {1}


def test_refazer_sem_mudanca_fica_inalterado_e_com_foto_nova_atualiza(db, settings):
    ingerir(db, ApiFalsa(), settings)

    r = ingerir(db, ApiFalsa(), settings, refazer=True)
    assert (r.inseridos, r.atualizados, r.inalterados) == (0, 0, 2)

    api = ApiFalsa()
    api.observacoes[(2, True)] = [foto(30)]
    r2 = ingerir(db, api, settings, refazer=True)
    assert (r2.atualizados, r2.inalterados) == (1, 1)
    bentevi = db.raw_inaturalist.find_one({"_id": "taxon:2"})["dados"]
    assert [f["observacao_id"] for f in bentevi["fotos_brasil"]] == [30]
