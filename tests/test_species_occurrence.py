"""Testes para scr.fusion.species_occurrence."""
import pytest
from unittest.mock import MagicMock
from scr.fusion.species_occurrence import _add_unique, extrair_e_transformar


class TestAddUnique:
    def test_adiciona_novo(self):
        lst = ["a", "b"]
        _add_unique(lst, "c")
        assert lst == ["a", "b", "c"]

    def test_nao_duplica(self):
        lst = ["a", "b"]
        _add_unique(lst, "a")
        assert lst == ["a", "b"]

    def test_ignora_vazio(self):
        lst = ["a"]
        _add_unique(lst, "")
        assert lst == ["a"]

    def test_ignora_none(self):
        lst = ["a"]
        _add_unique(lst, None)
        assert lst == ["a"]

    def test_lista_vazia(self):
        lst = []
        _add_unique(lst, "x")
        assert lst == ["x"]


class TestExtrairETransformar:
    def _make_mock_collection(self, docs):
        """Cria mock de collection MongoDB com cursor encadeável."""
        col = MagicMock()
        col.count_documents.return_value = len(docs)

        cursor = MagicMock()
        cursor.sort.return_value = iter(docs)

        col.find.return_value = cursor
        return col

    def test_documento_unico_uma_especie(self):
        docs = [{
            "geocodigo": "3550308",
            "nome": "São Paulo",
            "uf": "SP",
            "bioma": "Mata Atlântica",
            "especies": [
                {"speciesCode": "grkis1", "sciName": "Pitangus sulphuratus"}
            ],
        }]
        col = self._make_mock_collection(docs)
        result = extrair_e_transformar(col)

        assert "grkis1" in result
        sp = result["grkis1"]
        assert sp["nome_cientifico"] == "Pitangus sulphuratus"
        assert sp["estados"] == ["SP"]
        assert sp["biomas"] == ["Mata Atlântica"]
        assert sp["contagem_ocorrencias"] == 1

    def test_mesma_especie_dois_municipios(self):
        docs = [
            {
                "geocodigo": "3550308", "nome": "São Paulo", "uf": "SP",
                "bioma": "Mata Atlântica",
                "especies": [{"speciesCode": "grkis1", "sciName": "Pitangus sulphuratus"}],
            },
            {
                "geocodigo": "3304557", "nome": "Rio de Janeiro", "uf": "RJ",
                "bioma": "Mata Atlântica",
                "especies": [{"speciesCode": "grkis1", "sciName": "Pitangus sulphuratus"}],
            },
        ]
        col = self._make_mock_collection(docs)
        result = extrair_e_transformar(col)

        sp = result["grkis1"]
        assert sp["contagem_ocorrencias"] == 2
        assert sp["estados"] == ["SP", "RJ"]
        assert len(sp["municipios"]) == 2
        # Bioma não duplica
        assert sp["biomas"] == ["Mata Atlântica"]

    def test_collection_vazia(self):
        col = self._make_mock_collection([])
        result = extrair_e_transformar(col)
        assert result == {}
