"""Testes para a ingestão do Bird Album (ingest/birdalbum.py), sem rede."""

from avesrag_builder.ingest.birdalbum import ler, link_repositorio, url_raw

CSV = (
    "id,scientific_name,ebird,sticker_file,sticker_license,meets_quality_bar,reference_type\n"
    "Pitangus_sulphuratus,Pitangus sulphuratus,grekis,stickers/a.webp,CC-BY-4.0,True,photo\n"
    "Ardea_ibis,Ardea ibis,categr,stickers/b.webp,CC-BY-4.0,True,\n"
)


def test_id_da_fonte_e_dados_como_vieram():
    registros = ler(CSV)
    assert [i for i, _ in registros] == ["Pitangus_sulphuratus", "Ardea_ibis"]
    assert registros[1][1]["reference_type"] == ""
    assert registros[0][1]["ebird"] == "grekis"


def test_urls_no_commit_fixo():
    assert url_raw("dono/repo", "abc", "data/species.csv") == (
        "https://raw.githubusercontent.com/dono/repo/abc/data/species.csv"
    )
    assert link_repositorio("dono/repo") == "https://github.com/dono/repo"
