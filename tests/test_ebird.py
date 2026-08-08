"""Testes para scr.ingestion.ebird — função normalize."""

from scr.ingestion.ebird import normalize


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
