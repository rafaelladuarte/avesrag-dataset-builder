"""Testes para extractors do WikiAves (wikiaves_info + wikiaves_especies)."""

import pytest
from bs4 import BeautifulSoup

from scr.ingestion.wikiaves_especies import extrair_especies
from scr.ingestion.wikiaves_info import (
    extrair_classificacao_cientifica,
    extrair_dados_html,
    extrair_estado_conservacao,
    extrair_foto_indicada,
    extrair_galeria,
    extrair_nome_cientifico,
    extrair_nome_ingles,
    get_section_text,
)


class TestExtrairClassificacao:
    def test_extrai_taxonomia(self, wikiaves_species_html):
        soup = BeautifulSoup(wikiaves_species_html, "html.parser")
        result = extrair_classificacao_cientifica(soup)
        assert result["Reino"] == "Animalia"
        assert result["Classe"] == "Aves"
        assert result["Ordem"] == "Passeriformes"

    def test_sem_tabela(self):
        soup = BeautifulSoup("<html><body></body></html>", "html.parser")
        assert extrair_classificacao_cientifica(soup) == {}


class TestExtrairNomeCientifico:
    def test_extrai_nome_e_autoridade(self, wikiaves_species_html):
        soup = BeautifulSoup(wikiaves_species_html, "html.parser")
        result = extrair_nome_cientifico(soup)
        assert result["nome"] == "Pitangus sulphuratus"
        assert result["autoridade"] == "(Linnaeus, 1766)"

    def test_fallback_titulo(self):
        html = (
            "<html><head><title>WikiAves - (Turdus rufiventris)</title></head><body></body></html>"
        )
        soup = BeautifulSoup(html, "html.parser")
        result = extrair_nome_cientifico(soup)
        assert result["nome"] == "Turdus rufiventris"
        assert result["autoridade"] is None

    def test_sem_dados(self):
        soup = BeautifulSoup("<html><body></body></html>", "html.parser")
        assert extrair_nome_cientifico(soup) == {}


class TestExtrairNomeIngles:
    def test_extrai_nome(self, wikiaves_species_html):
        soup = BeautifulSoup(wikiaves_species_html, "html.parser")
        assert extrair_nome_ingles(soup) == "Great Kiskadee"

    def test_sem_nome(self):
        soup = BeautifulSoup("<html><body></body></html>", "html.parser")
        assert extrair_nome_ingles(soup) is None


class TestExtrairEstadoConservacao:
    def test_extrai_status(self, wikiaves_species_html):
        soup = BeautifulSoup(wikiaves_species_html, "html.parser")
        assert extrair_estado_conservacao(soup) == "Pouco Preocupante"


class TestExtrairFotoIndicada:
    def test_og_image(self, wikiaves_species_html):
        soup = BeautifulSoup(wikiaves_species_html, "html.parser")
        assert extrair_foto_indicada(soup) == "https://www.wikiaves.com.br/img/bemtevi.jpg"

    def test_sem_meta(self):
        soup = BeautifulSoup("<html><head></head><body></body></html>", "html.parser")
        assert extrair_foto_indicada(soup) is None


class TestGetSectionText:
    def test_extrai_texto_secao(self, wikiaves_species_html):
        soup = BeautifulSoup(wikiaves_species_html, "html.parser")
        text = get_section_text(soup, "alimentacao")
        assert "Onívoro" in text
        assert "insetos" in text

    def test_secao_inexistente(self, wikiaves_species_html):
        soup = BeautifulSoup(wikiaves_species_html, "html.parser")
        assert get_section_text(soup, "inexistente") is None


class TestExtrairGaleria:
    def test_extrai_links(self, wikiaves_species_html):
        soup = BeautifulSoup(wikiaves_species_html, "html.parser")
        links = extrair_galeria(soup, n=2)
        assert len(links) == 2
        assert links[0] == "https://www.wikiaves.com.br/foto/12345"
        assert links[1] == "https://www.wikiaves.com.br/foto/67890"

    def test_sem_galeria(self):
        soup = BeautifulSoup("<html><body></body></html>", "html.parser")
        assert extrair_galeria(soup) == []


class TestExtrairDadosHtml:
    def test_integracao_completa(self, wikiaves_species_html):
        """Testa a orquestração completa de extração."""
        result = extrair_dados_html(wikiaves_species_html)

        assert result["nome_cientifico"]["nome"] == "Pitangus sulphuratus"
        assert result["classificacao_cientifica"]["Reino"] == "Animalia"
        assert result["nome_ingles"] == "Great Kiskadee"
        assert result["estado_de_conservacao"] == "Pouco Preocupante"
        assert "centímetros" in result["caracteristicas"]
        assert result["foto_mais_indicada"] is not None
        assert len(result["galeria_fotos_primeiras_2"]) == 2


class TestExtrairEspeciesTabela:
    def test_extrai_lista(self, wikiaves_table_html):
        especies = extrair_especies(wikiaves_table_html)
        assert len(especies) == 2

        assert especies[0]["nome_cientifico"] == "Pitangus sulphuratus"
        assert especies[0]["nome_comum"] == "Bem-te-vi"
        assert especies[0]["familia"] == "Tyrannidae"

        assert especies[1]["nome_cientifico"] == "Tyrannus melancholicus"

    def test_html_sem_tabela(self):
        with pytest.raises(RuntimeError, match="Tabela de espécies não encontrada"):
            extrair_especies("<html><body></body></html>")
