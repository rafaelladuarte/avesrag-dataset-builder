"""Testes para scr.ingestion.avonet — método transform."""
import pytest
import pandas as pd
from unittest.mock import patch
from scr.ingestion.avonet import AvonetIngestion, COLUNAS


class TestAvonetTransform:
    @pytest.fixture
    def extractor(self):
        """AvonetIngestion com DatabaseConnection mockada."""
        with patch("scr.ingestion.avonet.DatabaseConnection"):
            return AvonetIngestion()

    def _make_df(self, rows: list[dict]) -> pd.DataFrame:
        """Cria DataFrame com colunas originais do AVONET."""
        return pd.DataFrame(rows)

    def _make_full_row(self, species_name: str = "Pitangus sulphuratus") -> dict:
        """Cria uma linha completa com todas as colunas do AVONET."""
        return {
            "Species1": species_name,
            "Family1": "Tyrannidae",
            "Order1": "Passeriformes",
            "Beak.Length_Culmen": 30.5,
            "Beak.Length_Nares": 20.0,
            "Beak.Width": 12.0,
            "Beak.Depth": 10.0,
            "Tarsus.Length": 25.0,
            "Wing.Length": 120.0,
            "Kipps.Distance": 15.0,
            "Secondary1": 80.0,
            "Hand-Wing.Index": 20.5,
            "Tail.Length": 85.0,
            "Mass": 63.0,
            "Habitat": "Forest",
            "Trophic.Level": "Omnivore",
            "Trophic.Niche": "Omnivore",
            "Primary.Lifestyle": "Insessorial",
            "Migration": 1,
            "Range.Size": 15000000,
        }

    def test_transform_basico(self, extractor):
        df = self._make_df([self._make_full_row()])
        result = extractor.transform(df)

        assert len(result) == 1
        doc = result[0]
        assert doc["nome_cientifico"] == "Pitangus sulphuratus"
        assert doc["familia"] == "Tyrannidae"
        assert doc["massa_corporal_g"] == 63.0
        assert doc["fontes"] == ["avonet"]
        assert "atualizado_em" in doc

    def test_transform_vazio(self, extractor):
        df = pd.DataFrame()
        result = extractor.transform(df)
        assert result == []

    def test_transform_filtra_especies_alvo(self, extractor):
        df = self._make_df([
            self._make_full_row("Especie A"),
            self._make_full_row("Especie B"),
        ])
        result = extractor.transform(df, especies_alvo={"Especie A"})
        assert len(result) == 1
        assert result[0]["nome_cientifico"] == "Especie A"

    def test_transform_remove_nan(self, extractor):
        """Colunas NaN devem ser removidas do documento."""
        row = {k: None for k in COLUNAS.keys()}
        row["Species1"] = "Teste"
        row["Family1"] = "Familia"
        df = self._make_df([row])
        result = extractor.transform(df)

        assert len(result) == 1
        doc = result[0]
        assert "massa_corporal_g" not in doc  # era None, removido por dropna
        assert doc["nome_cientifico"] == "Teste"

    def test_transform_multiplas_especies(self, extractor):
        df = self._make_df([
            self._make_full_row("Especie A"),
            self._make_full_row("Especie B"),
            self._make_full_row("Especie C"),
        ])
        result = extractor.transform(df)
        assert len(result) == 3
        nomes = {doc["nome_cientifico"] for doc in result}
        assert nomes == {"Especie A", "Especie B", "Especie C"}
