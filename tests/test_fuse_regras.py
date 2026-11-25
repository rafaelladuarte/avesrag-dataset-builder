"""Testes para as regras de fusão (fuse/regras.py) e a montagem da ficha (fuse/species.py).

Casos do aceite A1 do Marco 5: taxonomia da Rhea americana toda do CBRO; pombas
-> generalista; papagaios -> quebrador; gaviões -> raptorial.
"""

import copy

import pytest

from avesrag_builder.core.models import Prov
from avesrag_builder.core.regras_fusao import regras_fusao_padrao
from avesrag_builder.core.regras_midia import regras_midia_padrao
from avesrag_builder.core.vocabulario import regras_bico_padrao, vocabulario_padrao
from avesrag_builder.fuse import regras as r
from avesrag_builder.fuse.species import montar
from avesrag_builder.validate.regras import campos_preenchidos


@pytest.fixture(scope="module")
def vocab():
    return vocabulario_padrao()


@pytest.fixture(scope="module")
def bico():
    return regras_bico_padrao()


@pytest.fixture(scope="module")
def regras():
    return regras_fusao_padrao()


def extracao(prompt, saida, nao_encontradas=(), ok=True, versao="2.0"):
    return {
        "prompt": prompt,
        "versao": versao,
        "saida": saida,
        "validacao": {"ok": ok, "evidencias_nao_encontradas": list(nao_encontradas)},
    }


def b01(**campos):
    saida = dict.fromkeys(["comprimento_cm", "cores", "cores_por_parte", "marcas", "cauda"])
    saida.update(campos)
    return saida


def b02(**campos):
    saida = dict.fromkeys(["ambiente", "onde_estava", "o_que_fazia", "grupo", "atividade"])
    saida.update(campos)
    return saida


def item(valor, evidencia=None):
    return {"valor": valor, "evidencia": evidencia or f"texto com {valor}"}


def bem_te_vi(**sobrescrever):
    dados = r.DadosEspecie(
        species_id="sp_pitangus_sulphuratus",
        nome_cientifico="Pitangus sulphuratus",
        nome_comum="bem-te-vi",
        wikiaves={
            "lista": {"nome_comum": "bem-te-vi", "url": "/wiki/bem-te-vi"},
            "pagina": {
                "classificacao_cientifica": {"Ordem": "Passeriformes", "Família": "Tyrannidae"},
                "nome_ingles": "Great Kiskadee (WikiAves)",
                "estado_de_conservacao": "Pouco Preocupante",
                "foto_mais_indicada": "https://exemplo/foto.jpg",
                "url": "https://www.wikiaves.com.br/wiki/bem-te-vi",
            },
        },
        cbro={
            "Ordem": "Passeriformes",
            "Família": "Tyrannidae",
            "Gênero": "Pitangus",
            "English Name": "Great Kiskadee",
            "Status": "BR",
        },
        avonet={
            "Habitat": "Human Modified",
            "Trophic.Niche": "Omnivore",
            "Primary.Lifestyle": "Insessorial",
            "Mass": 62.85,
        },
        birdbase={
            "2024 IUCN Red List category": "LC",
            "Average Mass": 61.5,
            "Primary Diet": "Omnivore",
            "Social_3": 1.0,
            "Social_4": 1.0,
        },
        extracoes={
            r.B01: extracao(
                r.B01,
                b01(
                    comprimento_cm={"min": 20.5, "max": 25, "evidencia": "entre 20,5 e 25 cm"},
                    cores=[item("amarelo"), item("preto")],
                    cores_por_parte=[
                        {"parte": "barriga", "cor": "amarelo", "evidencia": "barriga amarela"},
                        {"parte": "cabeca", "cor": "preto", "evidencia": "cabeça preta"},
                        {"parte": "garganta", "cor": "branco", "evidencia": "garganta branca"},
                    ],
                    marcas=[item("sobrancelha")],
                ),
            ),
            r.B02: extracao(
                r.B02,
                b02(
                    ambiente=[item("beira_de_agua")],
                    o_que_fazia=[item("pousada"), item("cacando_em_voo")],
                    atividade=[item("diurna")],
                ),
            ),
        },
        ocorrencia={"biomas": ["Cerrado"], "n_municipios": 1},
    )
    for campo, valor in sobrescrever.items():
        setattr(dados, campo, valor)
    return dados


class TestTaxonomia:
    def test_rhea_americana_toda_do_cbro(self):
        d = r.DadosEspecie(
            species_id="sp_rhea_americana",
            nome_cientifico="Rhea americana",
            wikiaves={"pagina": {"classificacao_cientifica": {"Ordem": "Struthioniformes"}}},
            cbro={"Ordem": "Rheiformes", "Família": "Rheidae", "Gênero": "Rhea"},
        )
        campo = r.taxonomia(d)
        assert campo.valor == {"ordem": "Rheiformes", "familia": "Rheidae", "genero": "Rhea"}
        assert campo.prov.fonte == "cbro"

    def test_cbro_incompleto_usa_o_wikiaves_inteiro(self):
        d = bem_te_vi(cbro={"Ordem": "Passeriformes", "Família": None, "Gênero": "Pitangus"})
        campo = r.taxonomia(d)
        assert campo.valor == {
            "ordem": "Passeriformes",
            "familia": "Tyrannidae",
            "genero": "Pitangus",
        }
        assert (campo.prov.fonte, campo.prov.metodo) == ("wikiaves", "reserva")

    def test_sem_fonte_completa(self):
        d = bem_te_vi(cbro=None, wikiaves={"pagina": {"classificacao_cientifica": {}}})
        assert r.taxonomia(d) is None


class TestIdentidade:
    def test_nomes(self):
        d = bem_te_vi()
        assert r.nomes_pt(d).valor == ["bem-te-vi"]
        assert r.nomes_en(d).valor == ["Great Kiskadee"]

    def test_nome_em_ingles_do_wikiaves_como_reserva(self):
        campo = r.nomes_en(bem_te_vi(cbro=None))
        assert campo.valor == ["Great Kiskadee (WikiAves)"]
        assert campo.prov.metodo == "reserva"

    def test_iucn_do_birdbase_com_sufixo(self, vocab):
        d = bem_te_vi(birdbase={"2024 IUCN Red List category": "CR (PE)"})
        assert r.iucn(d, vocab).valor == "CR"

    def test_iucn_do_wikiaves_como_reserva(self, vocab):
        campo = r.iucn(bem_te_vi(birdbase=None), vocab)
        assert (campo.valor, campo.prov.fonte) == ("LC", "wikiaves")

    def test_midia_so_com_o_link_do_wikiaves(self):
        # A foto do WikiAves não entra na ficha (Termo de Uso, B8).
        assert r.midia(bem_te_vi()).valor == {
            "url_wikiaves": "https://www.wikiaves.com.br/wiki/bem-te-vi",
        }


class TestBico:
    @pytest.mark.parametrize(
        "familia, tipo",
        [
            ("Columbidae", "generalista"),  # pombas
            ("Psittacidae", "quebrador"),  # papagaios
            ("Accipitridae", "raptorial"),  # gaviões
        ],
    )
    def test_regra_por_familia_vence_a_dieta(self, bico, familia, tipo):
        d = bem_te_vi(avonet={"Trophic.Niche": "Frugivore"})
        campo = r.bico_tipo(d, familia, bico)
        assert (campo.valor, campo.prov.fonte) == (tipo, "regra_familia")

    def test_nicho_do_avonet(self, bico):
        campo = r.bico_tipo(bem_te_vi(), "Tyrannidae", bico)
        assert (campo.valor, campo.prov.fonte) == ("generalista", "dieta_avonet")

    def test_dieta_do_birdbase_sem_nicho(self, bico):
        d = bem_te_vi(avonet={}, birdbase={"Primary Diet": "Invertebrate"})
        campo = r.bico_tipo(d, "Troglodytidae", bico)
        assert (campo.valor, campo.prov.fonte) == ("insetivoro", "dieta_birdbase")

    def test_sem_correspondencia(self, bico):
        d = bem_te_vi(avonet={}, birdbase={"Primary Diet": "No Information"})
        assert r.bico_tipo(d, "Tyrannidae", bico) is None


class TestTamanho:
    def test_comprimento_e_a_media_arredondada(self, regras):
        campo = r.comprimento_cm(bem_te_vi(), regras, r.Descartes())
        assert campo.valor == 23.0  # (20,5 + 25) / 2 = 22,75 -> 23
        assert campo.prov.ref == "b01_aparencia@2.0"

    def test_tamanho_pelo_comprimento(self, regras, vocab):
        d = bem_te_vi()
        comp = r.comprimento_cm(d, regras, r.Descartes())
        campo = r.tamanho(d, comp, regras, vocab)
        assert campo.valor == ["medio"]
        assert campo.prov.metodo == "comprimento"

    def test_comprimento_com_evidencia_nao_encontrada_cai(self, regras):
        d = bem_te_vi()
        d.extracoes[r.B01]["validacao"]["evidencias_nao_encontradas"] = ["entre 20,5 e 25 cm"]
        descartes = r.Descartes()
        assert r.comprimento_cm(d, regras, descartes) is None
        assert descartes.por_prompt == {r.B01: 1}

    def test_reserva_pela_massa_do_birdbase(self, regras, vocab):
        campo = r.tamanho(bem_te_vi(), None, regras, vocab)
        assert campo.valor == ["pequeno", "medio"]  # 61,5 g, a 30% de 50 g
        assert (campo.prov.fonte, campo.prov.metodo) == ("birdbase", "massa")

    def test_reserva_pela_massa_do_avonet(self, regras, vocab):
        campo = r.tamanho(bem_te_vi(birdbase={"Average Mass": None}), None, regras, vocab)
        assert campo.prov.fonte == "avonet"

    def test_sem_comprimento_nem_massa(self, regras, vocab):
        assert r.tamanho(bem_te_vi(birdbase=None, avonet=None), None, regras, vocab) is None


class TestAparencia:
    def test_cores_incluem_as_de_cores_por_parte(self, vocab):
        d = bem_te_vi()
        por_parte = r.cores_por_parte(d, vocab, r.Descartes())
        campo = r.cores(d, por_parte, vocab, r.Descartes())
        assert campo.valor == ["preto", "branco", "amarelo"]  # ordem do vocabulário

    def test_cores_por_parte_na_ordem_do_vocabulario(self, vocab):
        campo = r.cores_por_parte(bem_te_vi(), vocab, r.Descartes())
        assert [i["parte"] for i in campo.valor] == ["cabeca", "garganta", "barriga"]

    def test_item_com_evidencia_nao_encontrada_cai(self, vocab):
        d = bem_te_vi()
        d.extracoes[r.B01]["validacao"]["evidencias_nao_encontradas"] = ["texto com preto"]
        descartes = r.Descartes()
        campo = r.cores(d, None, vocab, descartes)
        assert campo.valor == ["amarelo"]
        assert descartes.total == 1

    def test_extracao_invalida_nao_contribui(self, vocab):
        d = bem_te_vi()
        d.extracoes[r.B01]["validacao"]["ok"] = False
        assert r.cores(d, None, vocab, r.Descartes()) is None
        assert r.lista_llm(d, r.B01, "marcas", vocab, r.Descartes()) is None

    def test_repetidos_caem(self, vocab):
        d = bem_te_vi()
        d.extracoes[r.B01]["saida"]["marcas"] = [item("sobrancelha"), item("sobrancelha", "outra")]
        assert r.lista_llm(d, r.B01, "marcas", vocab, r.Descartes()).valor == ["sobrancelha"]


class TestComportamento:
    def test_ambiente_une_avonet_e_b02(self, vocab):
        campo = r.ambiente(bem_te_vi(), vocab, r.Descartes())
        assert campo.valor == ["area_urbana", "parque_jardim", "beira_de_agua", "pasto_plantacao"]
        assert (campo.prov.fonte, campo.prov.metodo) == ("avonet+wikiaves", "uniao")

    def test_ambiente_so_do_avonet(self, vocab):
        d = bem_te_vi(extracoes={})
        campo = r.ambiente(d, vocab, r.Descartes())
        assert (campo.prov.fonte, campo.prov.metodo) == ("avonet", "mapeamento")

    def test_onde_estava_pela_locomocao_do_avonet(self, vocab):
        campo = r.onde_estava(bem_te_vi(), vocab, r.Descartes())
        assert campo.valor == ["meio_da_arvore", "copa"]
        assert campo.prov.metodo == "reserva"

    def test_grupo_pelas_colunas_sociais_do_birdbase(self, vocab):
        campo = r.grupo(bem_te_vi(), vocab, r.Descartes())
        assert campo.valor == ["sozinha", "casal", "bando"]  # Social_3 + Social_4
        assert (campo.prov.fonte, campo.prov.metodo) == ("birdbase", "reserva")

    def test_grupo_do_b02_vence_a_reserva(self, vocab):
        d = bem_te_vi()
        d.extracoes[r.B02]["saida"]["grupo"] = [item("casal")]
        assert r.grupo(d, vocab, r.Descartes()).valor == ["casal"]


class TestMontar:
    def test_ficha_completa_e_prov_de_todo_campo(self, vocab, bico, regras):
        ficha = montar(bem_te_vi(), vocab, bico, regras)
        doc = ficha.species.to_mongo()
        assert doc["taxonomia"]["familia"] == "Tyrannidae"
        assert doc["atributos"]["bico_tipo"] == "generalista"
        assert doc["atributos"]["tamanho"] == ["medio"]
        assert doc["ocorrencia"] == {"biomas": ["Cerrado"], "n_municipios": 1}
        assert set(doc["_prov"]) == campos_preenchidos(doc)
        assert "dq_status" not in doc["_meta"]

    def test_campo_sem_valor_fica_de_fora(self, vocab, bico, regras):
        doc = montar(bem_te_vi(), vocab, bico, regras).species.to_mongo()
        assert "cauda" not in doc["atributos"]
        assert "atributos.cauda" not in doc["_prov"]

    def test_mesma_entrada_mesma_ficha(self, vocab, bico, regras):
        d1 = bem_te_vi()
        d2 = copy.deepcopy(d1)
        d2.extracoes[r.B01]["saida"]["cores"].reverse()
        d2.extracoes[r.B02]["saida"]["o_que_fazia"].reverse()
        f1 = montar(d1, vocab, bico, regras).species.to_mongo()
        f2 = montar(d2, vocab, bico, regras).species.to_mongo()
        f1.pop("_meta"), f2.pop("_meta")
        assert f1 == f2

    def test_especie_so_com_planilhas(self, vocab, bico, regras):
        doc = montar(bem_te_vi(extracoes={}), vocab, bico, regras).species.to_mongo()
        assert "cores" not in doc["atributos"]
        assert doc["_prov"]["atributos.tamanho"]["metodo"] == "massa"


ALBUM = {
    "id": "Pitangus_sulphuratus",
    "scientific_name": "Pitangus sulphuratus",
    "ebird": "grekis",
    "sticker_file": "stickers/Passeriformes/Tyrannidae/Pitangus_sulphuratus.webp",
    "sticker_license": "CC-BY-4.0",
    "meets_quality_bar": "True",
    "reference_type": "photo",
}
REPO, REF = "dono/repo", "abc123"


class TestIlustracao:
    def test_ilustracao_com_credito_e_commit_fixo(self):
        campo = r.ilustracao(bem_te_vi(birdalbum=ALBUM, birdalbum_por="ebird"), REPO, REF)
        assert campo.valor == {
            "url": "https://raw.githubusercontent.com/dono/repo/abc123/"
            "stickers/Passeriformes/Tyrannidae/Pitangus_sulphuratus.webp",
            "credito": "Bird stickers: huashu-bird-sticker by Huashu, CC BY 4.0",
            "licenca": "CC BY 4.0",
            "link": "https://github.com/dono/repo",
            "gerada_por_ia": True,
            "referencia": "foto",
        }
        assert (campo.prov.fonte, campo.prov.metodo) == ("birdalbum", "ebird")

    @pytest.mark.parametrize(
        "mudar, referencia",
        [({"reference_type": "reference-board"}, "quadro"), ({"reference_type": ""}, "descricao")],
    )
    def test_referencia(self, mudar, referencia):
        d = bem_te_vi(birdalbum={**ALBUM, **mudar})
        assert r.ilustracao(d, REPO, REF).valor["referencia"] == referencia

    @pytest.mark.parametrize(
        "mudar",
        [
            {"sticker_file": ""},
            {"sticker_license": "PolyForm-Shield-1.0.0"},
            {"meets_quality_bar": "False"},
            {"reference_type": "desconhecido"},
        ],
    )
    def test_sem_ilustracao(self, mudar):
        assert r.ilustracao(bem_te_vi(birdalbum={**ALBUM, **mudar}), REPO, REF) is None

    def test_sem_registro_no_bird_album(self):
        assert r.ilustracao(bem_te_vi(), REPO, REF) is None

    def test_ficha_com_ilustracao_tem_prov_separado(self, vocab, bico, regras):
        d = bem_te_vi(birdalbum=ALBUM, birdalbum_por="nome")
        doc = montar(d, vocab, bico, regras, birdalbum=(REPO, REF)).species.to_mongo()
        assert doc["midia"]["ilustracao"]["referencia"] == "foto"
        assert "foto" not in doc["midia"]
        assert doc["_prov"]["midia.ilustracao"] == {"fonte": "birdalbum", "metodo": "nome"}
        assert doc["_prov"]["midia"] == {"fonte": "wikiaves"}
        assert set(doc["_prov"]) == campos_preenchidos(doc)

    def test_ficha_so_com_a_ilustracao(self, vocab, bico, regras):
        d = bem_te_vi(
            birdalbum=ALBUM, birdalbum_por="ebird", wikiaves={"lista": {"nome_comum": "x"}}
        )
        doc = montar(d, vocab, bico, regras, birdalbum=(REPO, REF)).species.to_mongo()
        assert set(doc["midia"]) == {"ilustracao"}
        assert "midia" not in doc["_prov"]
        assert set(doc["_prov"]) == campos_preenchidos(doc)


# ---------------------------------------------------------------------------
# Foto principal (midia.foto): iNaturalist do Brasil -> Commons P18 -> iNaturalist de fora
# ---------------------------------------------------------------------------


def foto_inat(id_=1, licenca="cc-by", autor="Fulano", login="fulano", local="Uberlândia, MG"):
    return {
        "id": id_,
        "url": f"https://inaturalist-open-data.s3.amazonaws.com/photos/{id_}/square.jpeg",
        "licenca": licenca,
        "atribuicao": f"(c) {autor or login}",
        "autor": autor,
        "login": login,
        "observacao_id": id_ * 10,
        "local": local,
        "data": "2024-01-02",
    }


def inat(brasil=(), mundo=()):
    return {
        "taxon": {"id": 16956, "nome": "Pitangus sulphuratus", "rank": "species"},
        "nomes": ["Pitangus sulphuratus"],
        "fotos_brasil": list(brasil),
        "fotos_mundo": list(mundo),
    }


COMMONS = {
    "qid": "Q1",
    "nomes": ["Pitangus sulphuratus"],
    "arquivo": "Bem-te-vi.jpg",
    "url": "https://upload.wikimedia.org/thumb/Bem-te-vi.jpg/960px-Bem-te-vi.jpg",
    "url_original": "https://upload.wikimedia.org/Bem-te-vi.jpg",
    "pagina": "https://commons.wikimedia.org/wiki/File:Bem-te-vi.jpg",
    "licenca": "CC BY-SA 4.0",
    "licenca_url": "https://creativecommons.org/licenses/by-sa/4.0",
    "artista": '<a href="//commons.wikimedia.org/wiki/User:Bel" title="User:Bel">Beltrano &amp; Cia</a>',
    "credito": "Obra do próprio",
    "categorias": ["Category:Pitangus sulphuratus"],
}


@pytest.fixture(scope="module")
def midia_regras():
    return regras_midia_padrao()


class TestFoto:
    def test_brasil_vence_e_monta_o_credito(self, midia_regras):
        d = bem_te_vi(
            inaturalist=inat(brasil=[foto_inat(7)], mundo=[foto_inat(8)]), commons=COMMONS
        )
        campo = r.foto(d, midia_regras)
        assert campo.valor == {
            "url": "https://inaturalist-open-data.s3.amazonaws.com/photos/7/medium.jpeg",
            "autor": "Fulano",
            "licenca": "CC BY 4.0",
            "licenca_url": "https://creativecommons.org/licenses/by/4.0/",
            "fonte": "inaturalist",
            "link": "https://www.inaturalist.org/photos/7",
            "credito": "Foto: Fulano · CC BY 4.0 · iNaturalist",
            "local": "Uberlândia, MG",
        }
        assert campo.prov == Prov(fonte="inaturalist", metodo="brasil", ref="regras_midia@1.1")

    def test_sem_brasil_vale_o_commons(self, midia_regras):
        d = bem_te_vi(inaturalist=inat(mundo=[foto_inat(8)]), commons=COMMONS)
        campo = r.foto(d, midia_regras)
        assert (campo.prov.fonte, campo.prov.metodo) == ("commons", "p18")
        assert campo.valor == {
            "url": COMMONS["url"],
            "autor": "Beltrano & Cia",
            "licenca": "CC BY-SA 4.0",
            "licenca_url": "https://creativecommons.org/licenses/by-sa/4.0",
            "fonte": "commons",
            "link": COMMONS["pagina"],
            "credito": "Foto: Beltrano & Cia · CC BY-SA 4.0 · Wikimedia Commons",
        }

    def test_sem_brasil_nem_commons_vale_a_de_fora(self, midia_regras):
        d = bem_te_vi(inaturalist=inat(mundo=[foto_inat(8)]))
        campo = r.foto(d, midia_regras)
        assert (campo.prov.metodo, campo.valor["link"]) == (
            "mundo",
            "https://www.inaturalist.org/photos/8",
        )

    def test_sem_nenhuma_fonte(self, midia_regras):
        assert r.foto(bem_te_vi(), midia_regras) is None
        assert r.foto(bem_te_vi(inaturalist=inat()), midia_regras) is None

    def test_vale_a_primeira_foto_valida_da_lista(self, midia_regras):
        d = bem_te_vi(inaturalist=inat(brasil=[foto_inat(1, licenca="cc-by-nc"), foto_inat(2)]))
        assert r.foto(d, midia_regras).valor["link"].endswith("/photos/2")

    def test_sem_nome_o_autor_e_o_login(self, midia_regras):
        d = bem_te_vi(inaturalist=inat(brasil=[foto_inat(autor=None)]))
        assert r.foto(d, midia_regras).valor["credito"] == "Foto: fulano · CC BY 4.0 · iNaturalist"

    def test_sem_local_nao_grava_o_campo(self, midia_regras):
        d = bem_te_vi(inaturalist=inat(brasil=[foto_inat(local=None)]))
        assert "local" not in r.foto(d, midia_regras).valor

    @pytest.mark.parametrize(
        "mudar",
        [
            {"categorias": ["Category:Birds illustrations"]},
            {"artista": "Joseph Smit"},
            {"licenca": "GFDL 1.2"},
            {"artista": "No machine-readable author provided"},
            {"artista": ""},
            {"url": "http://upload.wikimedia.org/x.jpg"},
        ],
    )
    def test_commons_recusado_passa_para_a_de_fora(self, midia_regras, mudar):
        d = bem_te_vi(inaturalist=inat(mundo=[foto_inat(8)]), commons={**COMMONS, **mudar})
        assert r.foto(d, midia_regras).prov.metodo == "mundo"

    def test_licenca_url_http_do_commons_cai_na_do_arquivo(self, midia_regras):
        c = {**COMMONS, "licenca_url": "http://creativecommons.org/licenses/by-sa/4.0"}
        valor = r.foto(bem_te_vi(commons=c), midia_regras).valor
        assert valor["licenca_url"] == "https://creativecommons.org/licenses/by-sa/4.0/"

    def test_ficha_com_foto_e_ilustracao_tem_provs_separados(
        self, vocab, bico, regras, midia_regras
    ):
        d = bem_te_vi(
            inaturalist=inat(brasil=[foto_inat(7)]), birdalbum=ALBUM, birdalbum_por="ebird"
        )
        ficha = montar(d, vocab, bico, regras, birdalbum=(REPO, REF), midia_regras=midia_regras)
        doc = ficha.species.to_mongo()
        assert set(doc["midia"]) == {"foto", "url_wikiaves", "ilustracao"}
        assert doc["midia"]["foto"]["fonte"] == "inaturalist"
        assert doc["_prov"]["midia.foto"] == {
            "fonte": "inaturalist",
            "metodo": "brasil",
            "ref": "regras_midia@1.1",
        }
        assert doc["_prov"]["midia"] == {"fonte": "wikiaves"}
        assert set(doc["_prov"]) == campos_preenchidos(doc)


# ---------------------------------------------------------------------------
# Perfil (massa e dieta) e galeria de fotos
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def ficha_regras():
    from avesrag_builder.core.regras_ficha import regras_ficha_padrao

    return regras_ficha_padrao()


class TestPerfil:
    def test_massa_do_birdbase_com_a_origem(self):
        campo = r.massa(bem_te_vi())
        assert campo.valor == 61.5
        assert (campo.prov.fonte, campo.prov.metodo) == ("birdbase", "massa")

    def test_sem_birdbase_vale_o_avonet(self):
        campo = r.massa(bem_te_vi(birdbase={"Primary Diet": "Omnivore"}))
        assert (campo.valor, campo.prov.fonte) == (62.9, "avonet")  # 62,85 arredondado

    def test_sem_massa_nao_ha_campo(self):
        assert r.massa(bem_te_vi(avonet={}, birdbase={})) is None

    def test_dieta_do_avonet_vence(self, ficha_regras):
        campo = r.dieta(bem_te_vi(), ficha_regras)
        assert campo.valor == "onívora"
        assert (campo.prov.fonte, campo.prov.metodo) == ("avonet", "dieta")
        assert campo.prov.ref == "regras_ficha@1.0"

    def test_sem_avonet_vale_o_birdbase(self, ficha_regras):
        d = bem_te_vi(avonet={}, birdbase={"Primary Diet": "Fruit"})
        campo = r.dieta(d, ficha_regras)
        assert (campo.valor, campo.prov.fonte) == ("frugívora", "birdbase")

    @pytest.mark.parametrize("categoria", ["No Information", "Beeswax", "Desconhecida", None])
    def test_categoria_sem_texto_nao_vira_campo(self, ficha_regras, categoria):
        d = bem_te_vi(avonet={}, birdbase={"Primary Diet": categoria})
        assert r.dieta(d, ficha_regras) is None

    def test_a_ficha_leva_o_perfil_e_o_prov(self, vocab, bico, regras):
        doc = montar(bem_te_vi(), vocab, bico, regras).species.to_mongo()
        assert doc["perfil"] == {"massa_g": 61.5, "dieta": "onívora"}
        assert {"perfil.massa_g", "perfil.dieta"} <= set(doc["_prov"])
        assert set(doc["_prov"]) == campos_preenchidos(doc)

    def test_sem_massa_nem_dieta_a_ficha_fica_sem_perfil(self, vocab, bico, regras):
        d = bem_te_vi(avonet={}, birdbase={})
        doc = montar(d, vocab, bico, regras).species.to_mongo()
        assert "perfil" not in doc


class TestGaleria:
    def test_principal_e_as_outras_do_brasil_sem_repetir(self, midia_regras):
        d = bem_te_vi(inaturalist=inat(brasil=[foto_inat(7), foto_inat(8), foto_inat(9)]))
        principal = r.foto(d, midia_regras).valor
        campo = r.galeria(d, principal, midia_regras)
        assert [f["link"].rsplit("/", 1)[1] for f in campo.valor] == ["7", "8", "9"]
        assert campo.prov == Prov(fonte="inaturalist", metodo="galeria", ref="regras_midia@1.1")

    def test_para_no_limite_da_galeria(self, midia_regras):
        d = bem_te_vi(inaturalist=inat(brasil=[foto_inat(i) for i in range(1, 9)]))
        principal = r.foto(d, midia_regras).valor
        assert len(r.galeria(d, principal, midia_regras).valor) == midia_regras.galeria == 4

    def test_pula_a_foto_de_licenca_recusada(self, midia_regras):
        ruim = {**foto_inat(8), "licenca": "cc-by-nc"}
        d = bem_te_vi(inaturalist=inat(brasil=[foto_inat(7), ruim, foto_inat(9)]))
        principal = r.foto(d, midia_regras).valor
        links = [f["link"].rsplit("/", 1)[1] for f in r.galeria(d, principal, midia_regras).valor]
        assert links == ["7", "9"]

    def test_so_com_a_principal_nao_ha_galeria(self, midia_regras):
        d = bem_te_vi(inaturalist=inat(brasil=[foto_inat(7)]))
        assert r.galeria(d, r.foto(d, midia_regras).valor, midia_regras) is None

    def test_sem_principal_nao_ha_galeria(self, midia_regras):
        assert r.galeria(bem_te_vi(), None, midia_regras) is None

    def test_a_principal_do_commons_vem_primeiro(self, midia_regras):
        d = bem_te_vi(
            inaturalist=inat(mundo=[foto_inat(8)]) | {"fotos_brasil": []}, commons=COMMONS
        )
        assert r.galeria(d, r.foto(d, midia_regras).valor, midia_regras) is None  # sem outras

    def test_a_ficha_guarda_fotos_com_prov(self, vocab, bico, regras):
        d = bem_te_vi(inaturalist=inat(brasil=[foto_inat(7), foto_inat(8)]))
        doc = montar(d, vocab, bico, regras).species.to_mongo()
        assert [f["link"][-1] for f in doc["midia"]["fotos"]] == ["7", "8"]
        assert doc["midia"]["foto"] == doc["midia"]["fotos"][0]
        assert doc["_prov"]["midia.fotos"]["metodo"] == "galeria"
        assert set(doc["_prov"]) == campos_preenchidos(doc)
