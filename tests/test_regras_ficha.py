"""config/regras_ficha.yaml: a tabela de dieta se valida ao carregar."""

import pytest

from avesrag_builder.core.regras_ficha import carregar_regras_ficha, regras_ficha_padrao
from avesrag_builder.core.vocabulario import VocabularioInvalido


def _escrever(tmp_path, texto):
    caminho = tmp_path / "regras_ficha.yaml"
    caminho.write_text(texto, encoding="utf-8")
    return caminho


BASE = """
versao: "1"
ordem_dieta: [avonet, birdbase]
dieta:
  avonet: {Omnivore: onívora}
  birdbase: {Fruit: frugívora, Beeswax: null}
"""


def test_arquivo_do_projeto_carrega_e_traduz():
    regras = regras_ficha_padrao()
    assert regras.dieta("Insectivore", None) is None
    assert regras.dieta("Invertivore", "Fruit") == ("insetívora", "avonet")
    assert regras.dieta(None, "Fish") == ("piscívora", "birdbase")
    assert regras.dieta("", "") is None


def test_a_ordem_decide_a_fonte(tmp_path):
    regras = carregar_regras_ficha(
        _escrever(tmp_path, BASE.replace("[avonet, birdbase]", "[birdbase, avonet]"))
    )
    assert regras.dieta("Omnivore", "Fruit") == ("frugívora", "birdbase")


def test_categoria_nula_passa_para_a_proxima_fonte(tmp_path):
    regras = carregar_regras_ficha(_escrever(tmp_path, BASE))
    assert regras.dieta("Omnivore", "Beeswax") == ("onívora", "avonet")
    assert regras.dieta(None, "Beeswax") is None


@pytest.mark.parametrize(
    ("troca", "trecho"),
    [
        ("[avonet, birdbase]", "[avonet, avonet]"),
        ("[avonet, birdbase]", "[avonet, wikiaves]"),
        ("Omnivore: onívora", 'Omnivore: " "'),
    ],
)
def test_arquivo_invalido_falha_ao_carregar(tmp_path, troca, trecho):
    with pytest.raises(VocabularioInvalido):
        carregar_regras_ficha(_escrever(tmp_path, BASE.replace(troca, trecho)))


def test_campo_desconhecido_falha(tmp_path):
    with pytest.raises(VocabularioInvalido):
        carregar_regras_ficha(_escrever(tmp_path, BASE + "extra: 1\n"))
