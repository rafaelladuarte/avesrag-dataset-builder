"""Testes para config/regras_fusao.yaml e avesrag_builder.core.regras_fusao."""

import textwrap

import pytest

from avesrag_builder.core.regras_fusao import carregar_regras_fusao, regras_fusao_padrao
from avesrag_builder.core.settings import get_settings
from avesrag_builder.core.vocabulario import VocabularioInvalido, vocabulario_padrao


@pytest.fixture(scope="module")
def regras():
    return regras_fusao_padrao()


def _yaml_real() -> str:
    return (get_settings().CONFIG_DIR / "regras_fusao.yaml").read_text(encoding="utf-8")


def _erros(tmp_path, conteudo: str) -> str:
    path = tmp_path / "regras_fusao.yaml"
    path.write_text(textwrap.dedent(conteudo), encoding="utf-8")
    with pytest.raises(VocabularioInvalido) as exc:
        carregar_regras_fusao(path, vocabulario_padrao())
    return str(exc.value)


class TestTamanho:
    @pytest.mark.parametrize(
        "cm, faixas",
        [
            (12, ["pequeno"]),
            (17.5, ["pequeno"]),
            (18, ["pequeno", "medio"]),  # a 10% do corte de 20 cm
            (20, ["pequeno", "medio"]),
            (22, ["pequeno", "medio"]),
            (23, ["medio"]),
            (62, ["medio"]),
            (63, ["medio", "grande"]),
            (77, ["medio", "grande"]),
            (80, ["grande"]),
        ],
    )
    def test_por_comprimento(self, regras, cm, faixas):
        assert regras.tamanho_por_comprimento(cm) == faixas

    @pytest.mark.parametrize(
        "g, faixas",
        [
            (10, ["pequeno"]),
            (35, ["pequeno", "medio"]),
            (65, ["pequeno", "medio"]),
            (66, ["medio"]),
            (839, ["medio"]),
            (840, ["medio", "grande"]),
            (1560, ["medio", "grande"]),
            (25250, ["grande"]),  # ema
        ],
    )
    def test_por_massa(self, regras, g, faixas):
        assert regras.tamanho_por_massa(g) == faixas

    def test_arredonda_a_meio_centimetro(self, regras):
        assert regras.arredondar_comprimento(22.75) == 23.0
        assert regras.arredondar_comprimento(22.7) == 22.5
        assert regras.arredondar_comprimento(13) == 13.0

    def test_limites_do_comprimento(self, regras):
        assert regras.comprimento_valido(5)
        assert regras.comprimento_valido(200)
        assert not regras.comprimento_valido(4.9)
        assert not regras.comprimento_valido(250)


class TestApta:
    def test_criterios_da_especificacao(self, regras):
        assert regras.minimos == {"tamanho": 1, "cores": 2, "bico_tipo": 1, "ambiente": 1}
        assert regras.textos_b03 == ["aparencia"]


class TestValidacao:
    def test_faixa_fora_do_vocabulario(self, tmp_path):
        conteudo = _yaml_real().replace("[pequeno, medio, grande]", "[pequeno, medio, gigante]")
        assert "'gigante' não é valor de tamanho" in _erros(tmp_path, conteudo)

    def test_numero_de_cortes(self, tmp_path):
        conteudo = _yaml_real().replace("cortes: [20, 70]", "cortes: [20]")
        assert "tamanho.comprimento_cm.cortes: 3 faixas pedem 2 cortes" in _erros(
            tmp_path, conteudo
        )

    def test_cortes_decrescentes(self, tmp_path):
        conteudo = _yaml_real().replace("cortes: [50, 1200]", "cortes: [1200, 50]")
        assert "tamanho.massa_g.cortes: use valores positivos e crescentes" in _erros(
            tmp_path, conteudo
        )

    def test_minimo_de_atributo_inexistente(self, tmp_path):
        conteudo = _yaml_real().replace("bico_tipo: 1,", "bico: 1,")
        assert "apta.minimos.bico: não é atributo do vocabulário" in _erros(tmp_path, conteudo)

    def test_texto_b03_inexistente(self, tmp_path):
        conteudo = _yaml_real().replace("textos_b03: [aparencia]", "textos_b03: [voz]")
        assert "apta.textos_b03: 'voz'" in _erros(tmp_path, conteudo)

    def test_chave_desconhecida(self, tmp_path):
        assert "extra" in _erros(tmp_path, _yaml_real() + "extra: 1\n")
