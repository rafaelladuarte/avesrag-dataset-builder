"""Testes para scr.fusion.canonical_specie — funções get_size e get_weight."""
import pytest
from scr.fusion.canonical_specie import get_size, get_weight


class TestGetSize:
    def test_valor_simples(self):
        assert get_size("Mede 23,5 centímetros de comprimento") == {"min": 23.5, "max": 23.5}

    def test_valor_inteiro(self):
        assert get_size("Mede 30 centímetros") == {"min": 30.0, "max": 30.0}

    def test_virgula_decimal(self):
        assert get_size("Mede 8,6 centímetros de comprimento") == {"min": 8.6, "max": 8.6}

    def test_texto_sem_medida(self):
        assert get_size("Ave de grande porte") == {"min": None, "max": None}

    def test_texto_vazio(self):
        assert get_size("") == {"min": None, "max": None}

    def test_none(self):
        assert get_size(None) == {"min": None, "max": None}

    def test_texto_com_medida_parcial(self):
        """'cent' parcial deve casar com 'centímetros'."""
        assert get_size("Mede 15 cent de comprimento") == {"min": 15.0, "max": 15.0}


class TestGetWeight:
    def test_faixa_peso(self):
        assert get_weight("pesa de 52 a 68 gramas") == {"min": 52.0, "max": 68.0}

    def test_faixa_decimal(self):
        assert get_weight("pesa de 1,8 a 2,2 gramas") == {"min": 1.8, "max": 2.2}

    def test_case_insensitive(self):
        assert get_weight("Pesa de 100 a 150 gramas") == {"min": 100.0, "max": 150.0}

    def test_sem_peso(self):
        assert get_weight("Ave de porte médio") == {"min": None, "max": None}

    def test_vazio(self):
        assert get_weight("") == {"min": None, "max": None}

    def test_none(self):
        assert get_weight(None) == {"min": None, "max": None}
