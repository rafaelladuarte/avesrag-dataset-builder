"""Integração: escopo das fontes de foto e ingest commons com a API simulada."""

import pytest

from avesrag_builder.core.settings import Settings
from avesrag_builder.ingest import commons
from avesrag_builder.ingest.escopo import RegistryVazio, especies_com_nomes

pytestmark = pytest.mark.integration


@pytest.fixture
def db(db_temporario):
    db_temporario.species_registry.insert_many(
        [
            {
                "species_id": "sp_accipiter_bicolor",
                "nome_cientifico": "Accipiter bicolor",
                "chaves": {"ebird": "bichaw1"},
            },
            {
                "species_id": "sp_pitangus_sulphuratus",
                "nome_cientifico": "Pitangus sulphuratus",
                "chaves": {"ebird": "grekis"},
            },
            {"species_id": "sp_fora_do_piloto", "nome_cientifico": "Fora piloto", "chaves": {}},
        ]
    )
    db_temporario.raw_ebird.insert_many(
        [
            {"_id": "taxon:bichaw1", "dados": {"sciName": "Astur bicolor"}},
            {"_id": "taxon:grekis", "dados": {"sciName": "Pitangus sulphuratus"}},
            {"_id": "municipio:3170206", "dados": {"especies": ["bichaw1", "grekis"]}},
        ]
    )
    return db_temporario


@pytest.fixture
def settings():
    return Settings(_env_file=None, PILOTO_MUNICIPIO_IBGE="3170206")


class TestEscopo:
    def test_piloto_com_nome_do_ebird_primeiro(self, db):
        especies = especies_com_nomes(db, piloto=True, geocodigo="3170206")
        assert [(e.species_id, e.nomes) for e in especies] == [
            ("sp_accipiter_bicolor", ("Astur bicolor", "Accipiter bicolor")),
            ("sp_pitangus_sulphuratus", ("Pitangus sulphuratus",)),
        ]

    def test_sem_piloto_todas_do_registry(self, db):
        por_id = {e.species_id: e.nomes for e in especies_com_nomes(db)}
        assert len(por_id) == 3
        assert por_id["sp_fora_do_piloto"] == ("Fora piloto",)

    def test_registry_vazio(self, db_temporario):
        with pytest.raises(RegistryVazio, match="resolve"):
            especies_com_nomes(db_temporario)


@pytest.fixture
def api_falsa(monkeypatch):
    chamadas = []

    def p18(cliente, nomes):
        chamadas.append(("p18", tuple(nomes)))
        return [
            {
                "item": {"value": "http://www.wikidata.org/entity/Q100"},
                "nome": {"value": "Astur bicolor"},
                "img": {"value": "http://commons.wikimedia.org/wiki/Special:FilePath/Gaviao.jpg"},
            }
        ]

    def imageinfo(cliente, arquivos):
        chamadas.append(("imageinfo", tuple(arquivos)))
        return {
            "query": {
                "pages": [
                    {
                        "title": "File:Gaviao.jpg",
                        "imageinfo": [
                            {
                                "thumburl": "https://upload.wikimedia.org/640px-Gaviao.jpg",
                                "url": "https://upload.wikimedia.org/Gaviao.jpg",
                                "descriptionurl": "https://commons.wikimedia.org/wiki/File:Gaviao.jpg",
                                "extmetadata": {"LicenseShortName": {"value": "CC BY 4.0"}},
                            }
                        ],
                    }
                ]
            }
        }

    def categorias(cliente, arquivos):
        return [{"query": {"pages": [{"title": "File:Gaviao.jpg", "categories": []}]}}]

    monkeypatch.setattr(commons, "baixar_p18", p18)
    monkeypatch.setattr(commons, "baixar_imageinfo", imageinfo)
    monkeypatch.setattr(commons, "baixar_categorias", categorias)
    return chamadas


def test_piloto_grava_e_segunda_execucao_nao_grava(db, api_falsa, settings):
    (resultado,) = commons.ingerir(db, piloto=True, settings=settings)
    assert (resultado.inseridos, resultado.erros) == (1, [])
    assert api_falsa[0] == ("p18", ("Accipiter bicolor", "Astur bicolor", "Pitangus sulphuratus"))

    doc = db.raw_commons.find_one({"_id": "wikidata:Q100"})
    assert doc["dados"]["nomes"] == ["Astur bicolor"]
    assert doc["dados"]["licenca"] == "CC BY 4.0"
    assert doc["dados"]["categorias"] == []

    (segunda,) = commons.ingerir(db, piloto=True, settings=settings)
    assert (segunda.inseridos, segunda.atualizados, segunda.inalterados) == (0, 0, 1)
