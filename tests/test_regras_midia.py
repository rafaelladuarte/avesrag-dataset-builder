"""Testes para config/regras_midia.yaml e avesrag_builder.core.regras_midia."""

import textwrap

import pytest

from avesrag_builder.core.regras_midia import carregar_regras_midia, regras_midia_padrao
from avesrag_builder.core.settings import get_settings
from avesrag_builder.core.vocabulario import VocabularioInvalido


@pytest.fixture(scope="module")
def regras():
    return regras_midia_padrao()


def _yaml_real() -> str:
    return (get_settings().CONFIG_DIR / "regras_midia.yaml").read_text(encoding="utf-8")


def _erros(tmp_path, conteudo: str) -> str:
    path = tmp_path / "regras_midia.yaml"
    path.write_text(textwrap.dedent(conteudo), encoding="utf-8")
    with pytest.raises(VocabularioInvalido) as exc:
        carregar_regras_midia(path)
    return str(exc.value)


class TestOrdemECredito:
    def test_ordem_aprovada(self, regras):
        assert regras.ordem == [
            ("inaturalist", "brasil"),
            ("commons", "p18"),
            ("inaturalist", "mundo"),
        ]

    def test_credito(self, regras):
        assert (
            regras.credito(" Fulano de Tal ", "CC BY 4.0", "inaturalist")
            == "Foto: Fulano de Tal · CC BY 4.0 · iNaturalist"
        )
        assert regras.credito("Beltrano", "CC0 1.0", "commons").endswith("Wikimedia Commons")


class TestLicencas:
    @pytest.mark.parametrize(
        "codigo, nome",
        [
            ("cc-by", "CC BY 4.0"),
            ("cc-by-sa", "CC BY-SA 4.0"),
            ("cc0", "CC0 1.0"),
            ("CC-BY", "CC BY 4.0"),
        ],
    )
    def test_inaturalist_aceitas(self, regras, codigo, nome):
        assert regras.licenca_inaturalist(codigo).nome == nome

    @pytest.mark.parametrize(
        "codigo", ["cc-by-nc", "cc-by-nc-sa", "cc-by-nc-nd", "cc-by-nd", None, "", "desconhecida"]
    )
    def test_inaturalist_recusadas(self, regras, codigo):
        assert regras.licenca_inaturalist(codigo) is None

    # Os valores de LicenseShortName medidos no piloto em 22/11 (plano_fotos.md §2).
    @pytest.mark.parametrize(
        "nome, esperado",
        [
            ("CC BY-SA 4.0", "CC BY-SA 4.0"),
            ("CC BY-SA 2.0", "CC BY-SA 2.0"),
            ("CC BY-SA 3.0", "CC BY-SA 3.0"),
            ("CC BY 2.0", "CC BY 2.0"),
            ("Public domain", "Domínio público"),
            ("CC BY 4.0", "CC BY 4.0"),
            ("CC BY 3.0", "CC BY 3.0"),
            ("CC0", "CC0 1.0"),
            ("CC BY 2.5", "CC BY 2.5"),
            ("CC BY-SA 2.5", "CC BY-SA 2.5"),
            ("CC BY-SA 2.5 ar", "CC BY-SA 2.5"),  # portada
            ("  cc  by-sa 4.0 ", "CC BY-SA 4.0"),
        ],
    )
    def test_commons_aceitas(self, regras, nome, esperado):
        assert regras.licenca_commons(nome).nome == esperado

    @pytest.mark.parametrize(
        "nome", ["GFDL 1.2", "CC BY-NC 4.0", "CC BY-ND 2.0", "CC BY-NC-SA 2.0", "Copyrighted", None]
    )
    def test_commons_recusadas(self, regras, nome):
        assert regras.licenca_commons(nome) is None

    def test_portada_desligada(self, tmp_path):
        path = tmp_path / "regras_midia.yaml"
        path.write_text(_yaml_real().replace("aceitar_portadas: true", "aceitar_portadas: false"))
        assert carregar_regras_midia(path).licenca_commons("CC BY-SA 2.5 ar") is None

    def test_toda_licenca_tem_url_https(self, regras):
        assert all(lic.url.startswith("https://") for lic in regras.arquivo.licencas)


class TestCommons:
    @pytest.mark.parametrize(
        "categorias, artista",
        [
            (["Category:Bird illustrations by Joseph Smit"], "Joseph Smit"),
            (["Category:Gallinago undulata (illustrations)"], None),
            (["Category:Apodidae illustrations"], "Joseph Wolf"),
            ([], "Joseph Smit, cropped by User:Kersti Nebelsiek"),
            ([], "J G Keulemans"),
            ([], "George Robert Gray / David William Mitchell / Joseph Wolf"),
            (["Category:Bird specimens in the Naturalis Biodiversity Center"], "Fulano"),
        ],
    )
    def test_nao_e_foto(self, regras, categorias, artista):
        assert regras.nao_e_foto_commons(categorias, artista)

    @pytest.mark.parametrize(
        "categorias, artista",
        [
            # "Naturalis" dentro de "INaturalist" e "plate" dentro de "template" não contam.
            (["Category:INaturalist images reviewed by iNaturalistReviewBot"], "Agustín Zarco"),
            (["Category:Files with Assessments template missing SDC"], "Fulano"),
            ([], 'Gregory "Slobirdr" Smith'),  # Smith não é Smit
            (["Category:Cistothorus platensis"], None),
        ],
    )
    def test_e_foto(self, regras, categorias, artista):
        assert not regras.nao_e_foto_commons(categorias, artista)

    @pytest.mark.parametrize(
        "autor",
        [
            None,
            "",
            "   ",
            "No machine-readable author provided. Factumquintus assumed (based on copyright claims).",
            "Unknown",
        ],
    )
    def test_autor_invalido(self, regras, autor):
        assert not regras.autor_valido(autor)

    @pytest.mark.parametrize("autor", ["Gabriel Mello", "ALAN SCHMIERER", "Unknown photographer X"])
    def test_autor_valido(self, regras, autor):
        assert regras.autor_valido(autor)


class TestValidacao:
    def test_metodo_inexistente(self, tmp_path):
        conteudo = _yaml_real().replace(
            "{ fonte: commons, metodo: p18 }", "{ fonte: commons, metodo: brasil }"
        )
        assert "ordem[1]: commons não tem o método 'brasil'" in _erros(tmp_path, conteudo)

    def test_fonte_inexistente(self, tmp_path):
        conteudo = _yaml_real().replace(
            "{ fonte: commons, metodo: p18 }", "{ fonte: wikiaves, metodo: p18 }"
        )
        assert "ordem.1.fonte" in _erros(tmp_path, conteudo)

    def test_ordem_repetida(self, tmp_path):
        conteudo = _yaml_real().replace(
            "{ fonte: inaturalist, metodo: mundo }", "{ fonte: inaturalist, metodo: brasil }"
        )
        assert "ordem[2]: inaturalist/brasil repetido" in _erros(tmp_path, conteudo)

    def test_credito_sem_autor(self, tmp_path):
        conteudo = _yaml_real().replace(
            '"Foto: {autor} · {licenca} · {fonte}"', '"Foto: {licenca}"'
        )
        assert "credito: o modelo precisa citar {autor}" in _erros(tmp_path, conteudo)

    def test_credito_com_campo_desconhecido(self, tmp_path):
        conteudo = _yaml_real().replace("· {fonte}", "· {ano}")
        assert "credito: {ano} não existe" in _erros(tmp_path, conteudo)

    def test_licenca_nc_recusada(self, tmp_path):
        conteudo = _yaml_real().replace("inaturalist: [cc-by]", "inaturalist: [cc-by, cc-by-nc]")
        assert "'cc-by-nc' é NC, ND ou GFDL" in _erros(tmp_path, conteudo)

    def test_gfdl_recusada(self, tmp_path):
        conteudo = _yaml_real().replace("commons: [CC BY 2.0]", "commons: [CC BY 2.0, GFDL 1.2]")
        assert "'GFDL 1.2' é NC, ND ou GFDL" in _erros(tmp_path, conteudo)

    def test_apelido_em_duas_licencas(self, tmp_path):
        conteudo = _yaml_real().replace("commons: [CC BY 2.5]", "commons: [CC BY 2.5, cc by 2.0]")
        assert "commons 'cc by 2.0' já é de 'CC BY 2.0'" in _erros(tmp_path, conteudo)

    def test_url_sem_https(self, tmp_path):
        conteudo = _yaml_real().replace(
            "https://creativecommons.org/licenses/by/2.0/",
            "http://creativecommons.org/licenses/by/2.0/",
        )
        assert "licencas[2] (CC BY 2.0): a URL deve começar com https://" in _erros(
            tmp_path, conteudo
        )

    def test_expressao_invalida(self, tmp_path):
        conteudo = _yaml_real().replace("'\\bJoseph Smit\\b'", "'\\bJoseph (Smit'")
        assert "commons.nao_foto.artistas[0]: expressão inválida" in _erros(tmp_path, conteudo)

    def test_chave_desconhecida(self, tmp_path):
        assert "extra" in _erros(tmp_path, _yaml_real() + "extra: 1\n")
