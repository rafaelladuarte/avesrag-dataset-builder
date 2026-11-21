"""Testes de avesrag_builder.ingest.wikiaves (sem rede nem MongoDB)."""

from avesrag_builder.ingest.wikiaves import registro, selecionar_piloto, url_pagina
from avesrag_builder.ingest.wikiaves_especies import extrair_especies

WIKIAVES = {
    "Pitangus sulphuratus",
    "Nannochordeiles pusillus",
    "Aphantochroa cirrochloris",
    "Urubitinga coronata",
    "Heterospizias meridionalis",
    "Chaetura meridionalis",
}


def test_ordem_das_pontes():
    escolhidas, sem = selecionar_piloto(
        [
            "Pitangus sulphuratus",  # exato
            "Buteogallus coronatus",  # ponte BIRDBASE
            "Eupetomena cirrochloris",  # ponte AVONET
            "Chordeiles pusillus",  # epíteto
            "Gallus gallus",  # nada
        ],
        WIKIAVES,
        [
            ("birdbase", {"Buteogallus coronatus": {"Urubitinga coronata"}}),
            ("avonet", {"Eupetomena cirrochloris": {"Aphantochroa cirrochloris"}}),
        ],
    )
    assert escolhidas == {
        "Pitangus sulphuratus": "exato",
        "Urubitinga coronata": "birdbase:Buteogallus coronatus",
        "Aphantochroa cirrochloris": "avonet:Eupetomena cirrochloris",
        "Nannochordeiles pusillus": "epiteto:Chordeiles pusillus",
    }
    assert sem == ["Gallus gallus"]


def test_ponte_tem_prioridade_sobre_epiteto():
    escolhidas, _ = selecionar_piloto(
        ["Buteogallus coronatus"],
        WIKIAVES | {"Platyrinchus coronatus"},
        [("birdbase", {"Buteogallus coronatus": {"Urubitinga coronata"}})],
    )
    assert escolhidas == {"Urubitinga coronata": "birdbase:Buteogallus coronatus"}


def test_epiteto_pode_trazer_mais_de_uma_pagina():
    escolhidas, _ = selecionar_piloto(["Buteogallus meridionalis"], WIKIAVES, [])
    assert set(escolhidas) == {"Heterospizias meridionalis", "Chaetura meridionalis"}


def test_ponte_para_nome_fora_do_wikiaves_segue_para_o_epiteto():
    escolhidas, _ = selecionar_piloto(
        ["Chordeiles pusillus"], WIKIAVES, [("birdbase", {"Chordeiles pusillus": {"Outro nome"}})]
    )
    assert escolhidas == {"Nannochordeiles pusillus": "epiteto:Chordeiles pusillus"}


def test_registro_e_url():
    linha = {"id": "10001", "nome_cientifico": "Rhea americana", "url": "/wiki/ema"}
    assert url_pagina(linha) == "https://www.wikiaves.com.br/wiki/ema"
    assert url_pagina({"url": "wiki/ema"}) == "https://www.wikiaves.com.br/wiki/ema"
    assert registro(linha, None) == ("10001", {"lista": linha})
    assert registro(linha, {"habitos": "x"}) == (
        "10001",
        {"lista": linha, "pagina": {"habitos": "x"}},
    )


def test_id_da_lista_cai_no_link_de_fotos_sem_sons():
    html = """
    <table class="wa-table-sp"><tbody><tr>
      <td>Cracidae</td><td><a href="/wiki/mutum"><i>Pauxi mitu</i></a></td><td>mutum</td>
      <td></td><td><a href="midias.php?tm=f&t=s&s=10069">2</a></td>
    </tr></tbody></table>
    """
    especie = extrair_especies(html)[0]
    assert especie["id"] == "10069"
    assert especie["sons"] == "0"
