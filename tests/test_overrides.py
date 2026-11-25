"""Correções manuais da ficha: validação, aplicação e o efeito no `montar`."""

from datetime import UTC, datetime

import pytest

from avesrag_builder.core.models import Prov
from avesrag_builder.core.regras_fusao import regras_fusao_padrao
from avesrag_builder.core.vocabulario import regras_bico_padrao, vocabulario_padrao
from avesrag_builder.fuse import overrides as ov
from avesrag_builder.fuse.species import montar
from avesrag_builder.validate.regras import campos_preenchidos
from tests.test_fuse_regras import bem_te_vi

EM = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def vocab():
    return vocabulario_padrao()


def entrada(valor):
    return {"valor": valor, "por": "ana", "em": EM}


class TestValidar:
    def test_lista_vai_para_a_ordem_do_vocabulario_sem_repetir(self, vocab):
        assert ov.validar_valor("atributos.cores", ["azul", "preto", "azul"], vocab) == [
            "preto",
            "azul",
        ]

    @pytest.mark.parametrize(
        ("caminho", "valor"),
        [
            ("atributos.cores", []),
            ("atributos.cores", ["fucsia"]),
            ("atributos.cores", "azul"),
            ("atributos.comprimento_cm", 20),
            ("nomes.pt", ["x"]),
            ("atributos.bico_tipo", "colher"),
            (
                "atributos.cores_por_parte",
                [{"parte": "asas", "cor": "azul"}, {"parte": "asas", "cor": "preto"}],
            ),
            ("atributos.cores_por_parte", [{"parte": "nariz", "cor": "azul"}]),
            ("atributos.cores_por_parte", [{"parte": "asas"}]),
            ("perfil.massa_g", 0),
            ("perfil.massa_g", True),
            ("perfil.massa_g", 500_000),
            ("perfil.dieta", "  "),
            ("perfil.dieta", "x" * 41),
            ("descricao", ""),
            ("descricao", "x" * 1501),
        ],
    )
    def test_recusa_o_que_nao_vale(self, vocab, caminho, valor):
        with pytest.raises(ov.OverrideInvalido):
            ov.validar_valor(caminho, valor, vocab)

    def test_valores_validos(self, vocab):
        pares = ov.validar_valor(
            "atributos.cores_por_parte",
            [{"parte": "asas", "cor": "azul"}, {"parte": "cabeca", "cor": "preto"}],
            vocab,
        )
        assert [p["parte"] for p in pares] == ["cabeca", "asas"]  # ordem das partes no vocabulário
        assert ov.validar_valor("atributos.bico_tipo", "frugivoro", vocab) == "frugivoro"
        assert ov.validar_valor("perfil.massa_g", 62.84, vocab) == 62.8
        assert ov.validar_valor("perfil.dieta", " onívora   estrita ", vocab) == "onívora estrita"
        assert ov.validar_valor("descricao", "  Ave comum.  ", vocab) == "Ave comum."

    def test_none_remove_o_campo(self, vocab):
        assert ov.validar_valor("atributos.marcas", None, vocab) is None
        with pytest.raises(ov.OverrideInvalido):
            ov.validar_valor("nomes.pt", None, vocab)  # mesmo para remover, o caminho tem de valer


class TestAplicar:
    def test_define_e_marca_a_origem_manual(self, vocab):
        doc = {"atributos": {"cores": ["preto"]}, "perfil": {"dieta": "onívora"}}
        prov = {"atributos.cores": Prov(fonte="wikiaves", metodo="llm")}
        res = ov.aplicar(
            doc,
            prov,
            {"atributos.cores": entrada(["amarelo"]), "descricao": entrada("Texto.")},
            vocab,
        )
        assert doc["atributos"]["cores"] == ["amarelo"] and doc["descricao"] == "Texto."
        assert prov["atributos.cores"] == Prov(
            fonte="manual", metodo="curadoria", ref="override@2026-11-25"
        )
        assert prov["descricao"].fonte == "manual"
        assert res.aplicados == ["atributos.cores", "descricao"] and res.erros == []

    def test_remove_campo_e_prov(self, vocab):
        doc = {"atributos": {"marcas": ["mascara"]}, "perfil": {"dieta": "x"}}
        prov = {"atributos.marcas": Prov(fonte="wikiaves"), "perfil.dieta": Prov(fonte="avonet")}
        ov.aplicar(
            doc, prov, {"atributos.marcas": entrada(None), "perfil.dieta": entrada(None)}, vocab
        )
        assert "marcas" not in doc["atributos"] and doc["perfil"] is None
        assert prov == {}

    def test_cria_o_bloco_que_nao_existia(self, vocab):
        doc = {"atributos": {}, "perfil": None}
        ov.aplicar(doc, {}, {"perfil.massa_g": entrada(70)}, vocab)
        assert doc["perfil"] == {"massa_g": 70.0}

    def test_correcao_invalida_e_ignorada_e_relatada(self, vocab):
        doc = {"atributos": {"cores": ["preto"]}}
        res = ov.aplicar(doc, {}, {"atributos.cores": entrada(["fucsia"])}, vocab)
        assert doc["atributos"]["cores"] == ["preto"] and res.aplicados == []
        assert res.erros[0][0] == "atributos.cores"


class TestMontar:
    def montar(self, vocab, **overrides):
        d = bem_te_vi()
        d.overrides = overrides
        return montar(d, vocab, regras_bico_padrao(), regras_fusao_padrao())

    def test_a_correcao_vence_a_fonte_e_a_ficha_passa_na_conferencia_do_prov(self, vocab):
        ficha = self.montar(
            vocab,
            **{
                "atributos.cores": entrada(["azul"]),
                "atributos.bico_tipo": entrada("frugivoro"),
                "perfil.massa_g": entrada(80),
                "descricao": entrada("Ave comum em fios."),
            },
        )
        doc = ficha.species.to_mongo()
        assert (
            doc["atributos"]["cores"] == ["azul"] and doc["atributos"]["bico_tipo"] == "frugivoro"
        )
        assert doc["perfil"]["massa_g"] == 80.0 and doc["perfil"]["dieta"] == "onívora"
        assert doc["descricao"] == "Ave comum em fios."
        for caminho in ("atributos.cores", "atributos.bico_tipo", "perfil.massa_g", "descricao"):
            assert doc["_prov"][caminho]["fonte"] == "manual"
        assert doc["_prov"]["perfil.dieta"]["fonte"] == "avonet"  # o que não foi corrigido segue
        assert set(doc["_prov"]) == campos_preenchidos(doc)

    def test_remover_um_campo_tira_o_prov(self, vocab):
        doc = self.montar(vocab, **{"atributos.cores": entrada(None)}).species.to_mongo()
        assert "cores" not in doc["atributos"] and "atributos.cores" not in doc["_prov"]
        assert set(doc["_prov"]) == campos_preenchidos(doc)

    def test_correcao_invalida_nao_derruba_a_ficha(self, vocab):
        ficha = self.montar(vocab, **{"atributos.cores": entrada(["fucsia"])})
        assert ficha.species.to_mongo()["atributos"]["cores"] != ["fucsia"]
        assert ficha.descartes.por_prompt.get("overrides") == 1

    def test_sem_correcao_a_ficha_e_a_de_antes(self, vocab):
        antes = montar(bem_te_vi(), vocab, regras_bico_padrao(), regras_fusao_padrao())
        assert (
            self.montar(vocab).species.to_mongo()["atributos"]
            == antes.species.to_mongo()["atributos"]
        )
        assert "descricao" not in antes.species.to_mongo()


# ---------------------------------------------------------------------------
# Textos e fotos
# ---------------------------------------------------------------------------


def _foto(n, **mudar):
    return {
        "url": f"https://exemplo.org/{n}.jpg",
        "autor": "Beltrana",
        "licenca": "CC BY 4.0",
        "fonte": "manual",
        "link": f"https://exemplo.org/foto/{n}",
        "credito": "Foto: Beltrana · CC BY 4.0",
        **mudar,
    }


class TestTextos:
    @pytest.mark.parametrize("caminho", ["descricao", "comportamento", "voz"])
    def test_os_tres_textos_sao_editaveis(self, vocab, caminho):
        assert ov.EDITAVEIS[caminho] == "texto_longo"
        assert ov.validar_valor(caminho, "  Texto.  ", vocab) == "Texto."
        with pytest.raises(ov.OverrideInvalido):
            ov.validar_valor(caminho, "x" * 1501, vocab)

    def test_a_ficha_leva_os_textos_com_prov_manual(self, vocab):
        d = bem_te_vi()
        d.overrides = {"comportamento": entrada("Vive em áreas urbanas."), "voz": entrada("Canta.")}
        doc = montar(d, vocab, regras_bico_padrao(), regras_fusao_padrao()).species.to_mongo()
        assert doc["comportamento"] == "Vive em áreas urbanas." and doc["voz"] == "Canta."
        assert doc["_prov"]["voz"]["fonte"] == "manual"
        assert set(doc["_prov"]) == campos_preenchidos(doc)


class TestFotos:
    def test_valida_e_poe_a_url_da_licenca_do_arquivo(self, vocab):
        r = ov.validar_valor("midia.fotos", [_foto(1, licenca_url="https://falsa.example/")], vocab)
        assert r[0]["licenca_url"] == "https://creativecommons.org/licenses/by/4.0/"
        assert r[0]["fonte"] == "manual"

    @pytest.mark.parametrize(
        "valor",
        [
            [],
            None,
            "foto.jpg",
            [_foto(1, licenca="CC BY-NC 4.0")],
            [_foto(1, licenca="Todos os direitos reservados")],
            [_foto(1, url="http://sem-https.example/a.jpg")],
            [_foto(1, autor="")],
            [_foto(1, fonte="flickr")],
            [_foto(1, extra="x")],
            [_foto(1), _foto(1)],
            [_foto(n) for n in range(7)],
        ],
    )
    def test_recusa_o_que_nao_vale(self, vocab, valor):
        with pytest.raises(ov.OverrideInvalido):
            ov.validar_valor("midia.fotos", valor, vocab)

    def test_a_primeira_vira_a_principal_e_a_galeria_so_com_duas(self, vocab):
        doc = {"midia": {"foto": {"x": 1}, "url_wikiaves": "https://w"}}
        prov = {}
        ov.aplicar(doc, prov, {"midia.fotos": entrada([_foto(1), _foto(2)])}, vocab)
        assert doc["midia"]["foto"]["link"].endswith("/1") and len(doc["midia"]["fotos"]) == 2
        assert doc["midia"]["url_wikiaves"] == "https://w"
        assert prov["midia.foto"].fonte == prov["midia.fotos"].fonte == "manual"

        doc = {"midia": {"foto": {"x": 1}, "fotos": [{"x": 1}, {"x": 2}]}}
        prov = {"midia.fotos": Prov(fonte="inaturalist")}
        ov.aplicar(doc, prov, {"midia.fotos": entrada([_foto(9)])}, vocab)
        assert doc["midia"]["foto"]["link"].endswith("/9") and "fotos" not in doc["midia"]
        assert "midia.fotos" not in prov and prov["midia.foto"].fonte == "manual"

    def test_a_ficha_montada_passa_na_conferencia_do_prov(self, vocab):
        d = bem_te_vi()
        d.overrides = {"midia.fotos": entrada([_foto(1), _foto(2)])}
        doc = montar(d, vocab, regras_bico_padrao(), regras_fusao_padrao()).species.to_mongo()
        assert doc["midia"]["foto"]["fonte"] == "manual"
        assert [f["link"][-1] for f in doc["midia"]["fotos"]] == ["1", "2"]
        assert set(doc["_prov"]) == campos_preenchidos(doc)

    def test_candidatas_sem_repetir_e_na_ordem_das_regras(self):
        from avesrag_builder.core.regras_midia import regras_midia_padrao
        from avesrag_builder.fuse import regras as r
        from tests.test_fuse_regras import COMMONS, foto_inat, inat

        d = bem_te_vi(
            inaturalist=inat(
                brasil=[foto_inat(7), foto_inat(8)], mundo=[foto_inat(8), foto_inat(9)]
            ),
            commons=COMMONS,
        )
        achadas = r.fotos_candidatas(d, regras_midia_padrao())
        assert [(o, f["link"].rsplit("/", 1)[-1]) for o, f in achadas][:2] == [
            ("brasil", "7"),
            ("brasil", "8"),
        ]
        assert [o for o, _ in achadas] == ["brasil", "brasil", "p18", "mundo"]  # o 8 não repete
