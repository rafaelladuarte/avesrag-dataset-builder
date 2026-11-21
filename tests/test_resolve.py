"""Testes do casamento de nomes do `resolve` (fontes em memória, sem Mongo)."""

from datetime import UTC, datetime

import pytest

from avesrag_builder.resolve.registry import (
    COLUNAS_BIRDBASE,
    Fontes,
    Taxon,
    resolver_todas,
)

AGORA = datetime(2026, 11, 21, tzinfo=UTC)
BL, IOC, EB = COLUNAS_BIRDBASE


def _taxa(*itens: tuple[str, str, str]) -> dict[str, Taxon]:
    return {nome: Taxon(codigo, nome, familia) for codigo, nome, familia in itens}


def _fontes(**kw) -> Fontes:
    base = {"birdbase": {BL: {}, IOC: {}, EB: {}}}
    base.update(kw)
    return Fontes(**base)


def _especie(id_: str, nome: str, familia: str = "Tyrannidae", comum: str = "x") -> dict:
    return {"id": id_, "nome_cientifico": nome, "familia": familia, "nome_comum": comum}


def _por_nome(registros):
    return {r.nome_cientifico: r for r in registros}


class TestFontesExatas:
    def test_casamento_exato_em_todas(self):
        f = _fontes(
            cbro={"Pitangus sulphuratus": "CBRO#1234"},
            avonet_birdlife={"Pitangus sulphuratus"},
            birdbase={BL: {"Pitangus sulphuratus": "10"}, IOC: {}, EB: {}},
            birdbase_ebird={"10": "Pitangus sulphuratus"},
            taxa=_taxa(("grekis", "Pitangus sulphuratus", "Tyrannidae")),
        )
        (r,) = resolver_todas(
            [_especie("11450", "Pitangus sulphuratus", comum="bem-te-vi")], f, AGORA
        )
        assert r.species_id == "sp_pitangus_sulphuratus"
        assert r.nome_comum == "bem-te-vi"
        assert r.chaves.model_dump() == {
            "wikiaves": "11450",
            "cbro": "CBRO#1234",
            "avonet": "birdlife:Pitangus sulphuratus",
            "birdbase": "10",
            "ebird": "grekis",
        }
        assert set(r.match.values()) == {"exato"}

    def test_sem_match_guarda_null(self):
        (r,) = resolver_todas([_especie("1", "Avis inexistens")], _fontes(), AGORA)
        assert r.chaves.cbro is r.chaves.avonet is r.chaves.birdbase is r.chaves.ebird is None
        assert set(r.match.values()) == {"sem_match"}

    def test_avonet_cai_para_aba_ebird(self):
        f = _fontes(avonet_ebird={"Pitangus sulphuratus"})
        (r,) = resolver_todas([_especie("1", "Pitangus sulphuratus")], f, AGORA)
        assert r.chaves.avonet == "ebird:Pitangus sulphuratus"

    def test_birdbase_prefere_birdlife_depois_ioc(self):
        f = _fontes(birdbase={BL: {}, IOC: {"Avis a": "20"}, EB: {"Avis a": "30"}})
        (r,) = resolver_todas([_especie("1", "Avis a")], f, AGORA)
        assert r.chaves.birdbase == "20"


class TestEbird:
    def test_via_nome_ebird_do_birdbase(self):
        f = _fontes(
            birdbase={BL: {"Nengetus cinereus": "40"}, IOC: {}, EB: {}},
            birdbase_ebird={"40": "Xolmis cinereus"},
            taxa=_taxa(("gramon1", "Xolmis cinereus", "Tyrannidae")),
        )
        (r,) = resolver_todas([_especie("1", "Nengetus cinereus")], f, AGORA)
        assert (r.chaves.ebird, r.match["ebird"]) == ("gramon1", "exato")

    def test_nome_direto_sem_birdbase(self):
        f = _fontes(taxa=_taxa(("grekis", "Pitangus sulphuratus", "Tyrannidae")))
        (r,) = resolver_todas([_especie("1", "Pitangus sulphuratus")], f, AGORA)
        assert (r.chaves.ebird, r.match["ebird"]) == ("grekis", "exato")

    def test_ponte_avonet(self):
        f = _fontes(
            crosswalk={"Aphantochroa cirrochloris": {"Eupetomena cirrochloris"}},
            taxa=_taxa(("sombhu1", "Eupetomena cirrochloris", "Trochilidae")),
        )
        (r,) = resolver_todas([_especie("1", "Aphantochroa cirrochloris", "Trochilidae")], f, AGORA)
        assert (r.chaves.ebird, r.match["ebird"]) == ("sombhu1", "ponte")

    def _genero(self, *taxa_extra, familia_wikiaves="Accipitridae"):
        # Uma espécie casada exata ensina que Accipitridae (WikiAves) = Accipitridae (eBird).
        taxa = _taxa(
            ("roahaw", "Rupornis magnirostris", "Accipitridae"),
            ("grbhaw1", "Buteogallus urubitinga", "Accipitridae"),
            *taxa_extra,
        )
        especies = [
            _especie("1", "Rupornis magnirostris", "Accipitridae"),
            _especie("2", "Urubitinga urubitinga", familia_wikiaves),
        ]
        return _por_nome(resolver_todas(especies, _fontes(taxa=taxa), AGORA))

    def test_troca_de_genero(self):
        r = self._genero()["Urubitinga urubitinga"]
        assert (r.chaves.ebird, r.match["ebird"]) == ("grbhaw1", "genero")

    def test_troca_de_genero_rejeita_familia_diferente(self):
        # Caso Elaenia sordida (Tyrannidae) x Thlypopsis sordida (Thraupidae).
        r = self._genero(familia_wikiaves="Thraupidae")["Urubitinga urubitinga"]
        assert r.match["ebird"] == "sem_match"

    def test_troca_de_genero_rejeita_dois_candidatos(self):
        r = self._genero(("xxx1", "Outro urubitinga", "Accipitridae"))["Urubitinga urubitinga"]
        assert r.match["ebird"] == "sem_match"

    def test_familia_equivalente_aprendida_dos_exatos(self):
        taxa = _taxa(
            ("yeofly1", "Tolmomyias sulphurescens", "Tyrannidae"),
            ("novo1", "Genus velhus", "Tyrannidae"),
        )
        especies = [
            _especie("1", "Tolmomyias sulphurescens", "Rhynchocyclidae"),
            _especie("2", "Novogenus velhus", "Rhynchocyclidae"),
        ]
        r = _por_nome(resolver_todas(especies, _fontes(taxa=taxa), AGORA))["Novogenus velhus"]
        assert (r.chaves.ebird, r.match["ebird"]) == ("novo1", "genero")

    def test_aproximado_nao_reusa_codigo_de_exato(self):
        taxa = _taxa(
            ("thlsor1", "Thlypopsis sordida", "Thraupidae"),
        )
        especies = [
            _especie("1", "Thlypopsis sordida", "Thraupidae"),
            _especie("2", "Outragenus sordida", "Thraupidae"),
        ]
        r = _por_nome(resolver_todas(especies, _fontes(taxa=taxa), AGORA))
        assert r["Thlypopsis sordida"].chaves.ebird == "thlsor1"
        assert r["Outragenus sordida"].match["ebird"] == "sem_match"


@pytest.mark.parametrize("nome", ["Hydrobates gr. castro", "Lophornis cf. delattrei"])
def test_nomes_fora_do_padrao_viram_slug(nome):
    (r,) = resolver_todas([_especie("1", nome)], _fontes(), AGORA)
    assert r.species_id.startswith("sp_") and " " not in r.species_id


def test_species_id_estavel_entre_execucoes():
    especies = [
        _especie(str(i), n) for i, n in enumerate(["Avis a", "Avis b", "Pitangus sulphuratus"])
    ]
    a = [r.species_id for r in resolver_todas(especies, _fontes(), AGORA)]
    b = [r.species_id for r in resolver_todas(list(reversed(especies)), _fontes(), AGORA)]
    assert sorted(a) == sorted(b)
