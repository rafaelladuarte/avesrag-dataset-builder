"""Testes para avesrag_builder.ingest.ebird — função normalize."""

from avesrag_builder.ingest.ebird import normalize


class TestNormalize:
    def test_lowercase(self):
        assert normalize("São Paulo") == "sao paulo"

    def test_remove_acentos(self):
        assert normalize("Água Fria") == "agua fria"

    def test_remove_apostrofos(self):
        assert normalize("Pingo d'Água") == "pingo dagua"

    def test_remove_backtick(self):
        assert normalize("Pingo d`Água") == "pingo dagua"

    def test_strip_whitespace(self):
        assert normalize("  São Paulo  ") == "sao paulo"

    def test_cedilha(self):
        assert normalize("Açaí") == "acai"

    def test_texto_simples(self):
        assert normalize("Brasilia") == "brasilia"

    def test_til(self):
        assert normalize("São João") == "sao joao"


# ---------------------------------------------------------------------------
# Casamento IBGE <-> eBird e montagem dos registros (sem API)
# ---------------------------------------------------------------------------

from avesrag_builder.ingest.ebird import (  # noqa: E402
    casar_municipio,
    registro_municipio,
    registros_taxonomia,
)

REGIOES_MG = [
    {"code": "BR-MG-825", "name": "Uberlândia"},
    {"code": "BR-MG-111", "name": "Pingo-d'Água"},
    {"code": "BR-MG-222", "name": "São João del Rei"},
]


class TestCasarMunicipio:
    def test_exato_ignorando_acento(self):
        r = casar_municipio({"nome": "Uberlandia"}, REGIOES_MG)
        assert r == {"ebird_code": "BR-MG-825", "ebird_name": "Uberlândia", "match_type": "exato"}

    def test_hifen_e_apostrofo(self):
        # IBGE "Pingo d'Água" x eBird "Pingo-d'Água": ficou sem match na v1
        assert casar_municipio({"nome": "Pingo d'Água"}, REGIOES_MG)["match_type"] == "exato"
        assert casar_municipio({"nome": "São João del-Rei"}, REGIOES_MG)["match_type"] == "exato"

    def test_fuzzy(self):
        r = casar_municipio({"nome": "São João del Rey"}, REGIOES_MG)
        assert r["ebird_code"] == "BR-MG-222"
        assert r["match_type"].startswith("fuzzy:")

    def test_sem_match(self):
        r = casar_municipio({"nome": "Abadia de Goiás"}, REGIOES_MG)
        assert r == {"ebird_code": None, "ebird_name": None, "match_type": "sem_match"}

    def test_uf_sem_regioes(self):
        assert casar_municipio({"nome": "Uberlândia"}, [])["match_type"] == "sem_match"


def test_registros_taxonomia_usa_species_code():
    taxa = [{"speciesCode": "grekis", "sciName": "Pitangus sulphuratus"}]
    assert registros_taxonomia(taxa) == [("taxon:grekis", taxa[0])]


def test_registro_municipio():
    municipio = {"geocodigo": "3170206", "nome": "Uberlândia", "uf": "MG"}
    casamento = {"ebird_code": "BR-MG-825", "ebird_name": "Uberlândia", "match_type": "exato"}
    id_, dados = registro_municipio(municipio, casamento, ["grekis"])
    assert id_ == "municipio:3170206"
    assert dados["especies"] == ["grekis"]
    assert dados["ebird_code"] == "BR-MG-825"
