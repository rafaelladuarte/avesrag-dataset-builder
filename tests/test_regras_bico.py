"""Testes para config/regras_bico.yaml e avesrag_builder.core.vocabulario.RegrasBico."""

import textwrap

import pandas as pd
import pytest

from avesrag_builder.core.settings import get_settings
from avesrag_builder.core.vocabulario import (
    VocabularioInvalido,
    carregar_regras_bico,
    regras_bico_padrao,
    vocabulario_padrao,
)


@pytest.fixture(scope="module")
def regras():
    return regras_bico_padrao()


def _yaml_real() -> str:
    return (get_settings().CONFIG_DIR / "regras_bico.yaml").read_text(encoding="utf-8")


def _erros(tmp_path, conteudo: str) -> str:
    path = tmp_path / "regras_bico.yaml"
    path.write_text(textwrap.dedent(conteudo), encoding="utf-8")
    with pytest.raises(VocabularioInvalido) as exc:
        carregar_regras_bico(path, vocabulario_padrao())
    return str(exc.value)


class TestArquivoReal:
    def test_carrega(self, regras):
        assert regras.versao

    def test_todo_tipo_tem_perfil(self, regras):
        tipos = set(vocabulario_padrao().valores("bico_tipo"))
        assert set(regras.arquivo.perfil_visual) == tipos

    @pytest.mark.parametrize(
        "familia, tipo",
        [
            ("Columbidae", "generalista"),  # pombas
            ("Psittacidae", "quebrador"),  # papagaios
            ("Accipitridae", "raptorial"),  # gaviões
            ("Trochilidae", "nectarivoro"),
            ("Picidae", "insetos_em_troncos"),
            ("Ramphastidae", "frugivoro"),
            ("Cathartidae", "carniceiro"),
            ("Anatidae", "filtrador"),
        ],
    )
    def test_regra_por_familia(self, regras, familia, tipo):
        assert regras.tipo_por_familia(familia) == tipo

    def test_familia_sem_regra(self, regras):
        assert regras.tipo_por_familia("Tyrannidae") is None

    @pytest.mark.parametrize(
        "nicho, tipo",
        [
            ("Nectarivore", "nectarivoro"),
            ("Vertivore", "raptorial"),
            ("Scavenger", "carniceiro"),
            ("Granivore", "granivoro"),
            ("Frugivore", "frugivoro"),
            ("Invertivore", "insetivoro"),
            ("Omnivore", "generalista"),
            ("Herbivore aquatic", "filtrador"),
        ],
    )
    def test_dieta_da_especificacao(self, regras, nicho, tipo):
        assert regras.tipo_por_dieta("avonet.trophic_niche", nicho) == tipo

    def test_perfil(self, regras):
        perfil = regras.perfil("quebrador")
        assert perfil.curvatura == ["gancho"]
        assert perfil.espessura == ["muito_grosso"]


class TestValidacao:
    def test_familia_com_tipo_inexistente(self, tmp_path):
        conteudo = _yaml_real().replace("Psittacidae: quebrador", "Psittacidae: papagaio")
        assert "por_familia.Psittacidae: 'papagaio' não é valor de bico_tipo" in _erros(
            tmp_path, conteudo
        )

    def test_dieta_com_tipo_inexistente(self, tmp_path):
        conteudo = _yaml_real().replace("Granivore: granivoro", "Granivore: sementes")
        assert "por_dieta.avonet.trophic_niche.Granivore" in _erros(tmp_path, conteudo)

    def test_tipo_sem_perfil(self, tmp_path):
        linhas = _yaml_real().splitlines()
        i = linhas.index("  insetivoro:")
        del linhas[i : i + 2]
        assert "falta o perfil de 'insetivoro'" in _erros(tmp_path, "\n".join(linhas))

    def test_perfil_de_tipo_inexistente(self, tmp_path):
        conteudo = (
            _yaml_real()
            + "  martelo:\n    { comprimento: [curto], espessura: [fino], curvatura: [reto] }\n"
        )
        assert "perfil_visual.martelo: não é valor de bico_tipo" in _erros(tmp_path, conteudo)

    def test_dimensao_com_valor_inexistente(self, tmp_path):
        conteudo = _yaml_real().replace("espessura: [muito_grosso]", "espessura: [enorme]")
        assert "perfil_visual.quebrador.espessura: 'enorme'" in _erros(tmp_path, conteudo)


@pytest.mark.slow
def test_todo_nicho_trofico_do_avonet_esta_no_yaml(regras):
    avonet = pd.read_excel(
        get_settings().AVONET_XLSX, sheet_name="AVONET1_BirdLife", usecols=["Trophic.Niche"]
    )
    na_fonte = set(avonet["Trophic.Niche"].dropna().unique())
    no_yaml = set(regras.arquivo.por_dieta["avonet.trophic_niche"].valores)
    assert na_fonte <= no_yaml, f"faltam no YAML: {sorted(na_fonte - no_yaml)}"
