"""Conferência de evidências contra o texto de entrada."""

from avesrag_builder.extract.evidencias import evidencias, nao_encontradas

TEXTO = (
    "Mede entre 20,5 e 25 centímetros. Tem o dorso pardo e a barriga de um amarelo vivo;\n"
    "uma listra (sobrancelha) branca no alto da cabeça. Os olhos são amarelados destacados "
    "na face cinza-claro, contornada por negro."
)


def _saida(*evs):
    return {"cores": [{"valor": "x", "evidencia": e} for e in evs], "cauda": None}


def test_trecho_literal():
    assert nao_encontradas(_saida("Tem o dorso pardo"), TEXTO) == []


def test_ignora_caixa_acento_pontuacao_e_quebra_de_linha():
    evs = ["MEDE ENTRE 20,5 E 25 CENTIMETROS", "amarelo vivo uma listra", "face cinza claro"]
    assert nao_encontradas(_saida(*evs), TEXTO) == []


def test_reticencias_e_trecho_emendado_nao_casam():
    evs = ["Mede entre ... 25 centímetros", "dorso pardo e cinza-claro"]
    assert nao_encontradas(_saida(*evs), TEXTO) == evs


def test_palavra_trocada_nao_casa():
    # Caso real do teste de 21/11: "das praças" virou "nas praças".
    assert nao_encontradas(_saida("nos olhos são amarelados"), TEXTO) == [
        "nos olhos são amarelados"
    ]


def test_nao_casa_pedaco_de_palavra():
    assert nao_encontradas(_saida("orso pard"), TEXTO) == ["orso pard"]


def test_evidencia_repetida_aparece_uma_vez():
    assert nao_encontradas(_saida("inventado", "inventado"), TEXTO) == ["inventado"]


def test_inclui_comprimento_e_ignora_textos_do_b03():
    saida = {
        "comprimento_cm": {"min": 1, "max": 2, "evidencia": "inexistente"},
        "aparencia": "texto livre",
    }
    assert evidencias(saida) == ["inexistente"]
    assert nao_encontradas(saida, TEXTO) == ["inexistente"]
