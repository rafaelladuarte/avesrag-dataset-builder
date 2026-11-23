"""Testes para a ingestão do iNaturalist (ingest/inaturalist.py), sem rede e sem Mongo.

As respostas em `fixtures/inaturalist_respostas.json` são reais (23/11/2026),
reduzidas aos campos usados: *Pitangus sulphuratus* (táxon 16956) e a busca por
"Suiriri suiriri", que também traz espécies cujo nome popular é "suiriri".
"""

import json
from pathlib import Path

from avesrag_builder.core.regras_midia import regras_midia_padrao
from avesrag_builder.ingest import inaturalist as inat

RESPOSTAS = json.loads(
    (Path(__file__).parent / "fixtures" / "inaturalist_respostas.json").read_text("utf-8")
)
CODIGOS = ["cc0", "cc-by", "cc-by-sa"]


def taxon(id_, nome, matched_term=None, rank="species"):
    return {"id": id_, "name": nome, "rank": rank, "matched_term": matched_term or nome}


def observacao(id_, votos, licencas, nome="Fulano", login="fulano"):
    return {
        "id": id_,
        "cached_votes_total": votos,
        "faves_count": votos,
        "observed_on": "2024-01-02",
        "place_guess": "Uberlândia, MG, Brasil",
        "user": {"login": login, "name": nome},
        "photos": [
            {
                "id": id_ * 10 + i,
                "license_code": lic,
                "url": f"https://inaturalist-open-data.s3.amazonaws.com/photos/{id_ * 10 + i}/square.jpg",
                "attribution": f"(c) {nome}",
            }
            for i, lic in enumerate(licencas)
        ],
    }


def test_codigos_vem_do_regras_midia():
    assert regras_midia_padrao().codigos_inaturalist() == CODIGOS


class TestTaxon:
    def test_nome_exato(self):
        t = inat.escolher_taxon(RESPOSTAS["taxa_pitangus"], "Pitangus sulphuratus")
        assert t == {"id": 16956, "nome": "Pitangus sulphuratus", "rank": "species"}

    def test_ignora_quem_casa_so_pelo_nome_popular(self):
        t = inat.escolher_taxon(RESPOSTAS["taxa_suiriri"], "Suiriri suiriri")
        assert t["id"] == 17197

    def test_maiusculas_e_espacos(self):
        t = inat.escolher_taxon(RESPOSTAS["taxa_pitangus"], "  pitangus   SULPHURATUS ")
        assert t["id"] == 16956

    def test_sinonimo_pelo_matched_term(self):
        resposta = {"results": [taxon(1, "Astur bicolor", "Accipiter bicolor")]}
        assert inat.escolher_taxon(resposta, "Accipiter bicolor")["nome"] == "Astur bicolor"

    def test_nome_exato_vence_sinonimo(self):
        resposta = {"results": [taxon(1, "Outra especie", "Aa bb"), taxon(2, "Aa bb")]}
        assert inat.escolher_taxon(resposta, "Aa bb")["id"] == 2

    def test_dois_taxons_ambiguos(self):
        resposta = {"results": [taxon(1, "X y", "Aa bb"), taxon(2, "Z w", "Aa bb")]}
        assert inat.escolher_taxon(resposta, "Aa bb") is None

    def test_so_especie(self):
        resposta = {"results": [taxon(1, "Aa bb", rank="subspecies")]}
        assert inat.escolher_taxon(resposta, "Aa bb") is None

    def test_sem_resultado(self):
        assert inat.escolher_taxon({"total_results": 0, "results": []}, "Aa bb") is None


class TestFotos:
    def test_resposta_real_do_brasil(self):
        fotos = inat.ler_fotos(RESPOSTAS["observacoes_brasil"], CODIGOS)
        assert len(fotos) == 5
        assert fotos[0]["observacao_id"] == 18185926  # a mais votada (2 votos)
        # empate de 1 voto: menor id primeiro
        assert [f["observacao_id"] for f in fotos[1:]] == sorted(
            f["observacao_id"] for f in fotos[1:]
        )
        assert all(f["licenca"] in CODIGOS for f in fotos)
        assert all(f["url"].startswith("https://") for f in fotos)

    def test_campos_gravados_sem_votos(self):
        foto = inat.ler_fotos({"results": [observacao(7, 3, ["cc-by"])]}, CODIGOS)[0]
        assert foto == {
            "id": 70,
            "url": "https://inaturalist-open-data.s3.amazonaws.com/photos/70/square.jpg",
            "licenca": "cc-by",
            "atribuicao": "(c) Fulano",
            "autor": "Fulano",
            "login": "fulano",
            "observacao_id": 7,
            "local": "Uberlândia, MG, Brasil",
            "data": "2024-01-02",
        }

    def test_primeira_foto_com_licenca_aceita(self):
        foto = inat.ler_fotos({"results": [observacao(7, 0, ["cc-by-nc", "cc-by-sa"])]}, CODIGOS)[0]
        assert (foto["id"], foto["licenca"]) == (71, "cc-by-sa")

    def test_observacao_sem_foto_aceita_fica_de_fora(self):
        resposta = {"results": [observacao(7, 9, ["cc-by-nc", None]), observacao(8, 0, ["cc0"])]}
        assert [f["observacao_id"] for f in inat.ler_fotos(resposta, CODIGOS)] == [8]

    def test_corta_em_cinco_uma_por_observacao(self):
        resposta = {"results": [observacao(i, 0, ["cc-by", "cc-by"]) for i in range(1, 9)]}
        fotos = inat.ler_fotos(resposta, CODIGOS)
        assert [f["observacao_id"] for f in fotos] == [1, 2, 3, 4, 5]

    def test_ordem_nao_depende_da_ordem_da_resposta(self):
        obs = [observacao(3, 1, ["cc0"]), observacao(1, 1, ["cc0"]), observacao(2, 4, ["cc0"])]
        ida = inat.ler_fotos({"results": obs}, CODIGOS)
        volta = inat.ler_fotos({"results": obs[::-1]}, CODIGOS)
        assert ida == volta
        assert [f["observacao_id"] for f in ida] == [2, 1, 3]

    def test_autor_sem_nome_fica_com_o_login(self):
        foto = inat.ler_fotos({"results": [observacao(7, 0, ["cc0"], nome="  ")]}, CODIGOS)[0]
        assert foto["autor"] is None and foto["login"] == "fulano"


class TestParametros:
    def test_brasil(self):
        p = inat.params_observacoes(16956, CODIGOS, brasil=True)
        assert p["place_id"] == 6878 and "not_in_place" not in p
        assert p["photo_license"] == "cc0,cc-by,cc-by-sa"
        assert p["quality_grade"] == "research" and p["order_by"] == "votes"

    def test_fora_do_brasil(self):
        p = inat.params_observacoes(16956, CODIGOS, brasil=False)
        assert p["not_in_place"] == 6878 and "place_id" not in p
