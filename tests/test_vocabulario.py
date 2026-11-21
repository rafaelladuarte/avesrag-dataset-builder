"""Testes para config/vocabulario.yaml e avesrag_builder.core.vocabulario."""

import textwrap

import pandas as pd
import pytest

from avesrag_builder.core.settings import get_settings
from avesrag_builder.core.vocabulario import (
    VocabularioInvalido,
    carregar_vocabulario,
    vocabulario_padrao,
)

ATRIBUTOS_DO_MODELO = {
    "tamanho": {"pequeno", "medio", "grande"},
    "cores": {
        "preto", "branco", "cinza", "marrom", "bege", "amarelo",
        "laranja", "vermelho", "verde", "azul", "roxo", "rosa",
    },
    "marcas": {
        "mascara", "sobrancelha", "topete", "capuz", "anel_no_olho", "coleira",
        "garganta_contrastante", "mancha_no_peito", "listrado", "pintado",
        "faixa_na_asa", "cauda_com_branco",
    },
    "bico_tipo": {
        "generalista", "insetivoro", "granivoro", "quebrador", "frugivoro", "nectarivoro",
        "insetos_em_troncos", "raptorial", "carniceiro", "pescador", "filtrador",
        "limicola_sondador",
    },
    "cauda": {"curta", "longa", "bifurcada", "em_leque"},
    "ambiente": {
        "area_urbana", "parque_jardim", "mata", "borda_de_mata",
        "cerrado_campo", "brejo", "beira_de_agua", "pasto_plantacao",
    },
    "onde_estava": {"chao", "vegetacao_baixa", "meio_da_arvore", "copa", "no_ar", "na_agua"},
    "o_que_fazia": {
        "andando_no_chao", "pousada", "escalando_tronco", "parada_no_ar", "planando",
        "cacando_em_voo", "nadando", "mergulhando", "balancando_a_cauda",
    },
    "grupo": {"sozinha", "casal", "bando"},
    "atividade": {"diurna", "crepuscular", "noturna"},
}  # fmt: skip

PARTES_DO_MODELO = [
    "cabeca", "olho", "garganta", "peito", "barriga", "dorso", "asas", "cauda", "bico", "pernas",
]  # fmt: skip

YAML_MINIMO = """
versao: "t"
atributos:
  cores:
    descricao: d
    valores:
      cinza: {descricao: d, sinonimos: [acinzentado]}
      preto: {descricao: d, sinonimos: [negro]}
  ambiente:
    descricao: d
    valores:
      mata: {descricao: d}
cores_por_parte:
  descricao: d
  cor: cores
  partes:
    barriga: {descricao: d, sinonimos: [ventre]}
mapeamentos:
  fonte.habitat:
    origem: o
    destino: ambiente
    valores:
      Forest: [mata]
      Marine: null
"""


def _escrever(tmp_path, conteudo: str):
    path = tmp_path / "vocabulario.yaml"
    path.write_text(textwrap.dedent(conteudo), encoding="utf-8")
    return path


def _erros(tmp_path, conteudo: str) -> str:
    with pytest.raises(VocabularioInvalido) as exc:
        carregar_vocabulario(_escrever(tmp_path, conteudo))
    return str(exc.value)


@pytest.fixture(scope="module")
def vocab():
    return vocabulario_padrao()


# ---------------------------------------------------------------------------
# Arquivo real
# ---------------------------------------------------------------------------


class TestArquivoReal:
    def test_carrega(self, vocab):
        assert vocab.versao

    @pytest.mark.parametrize("atributo", sorted(ATRIBUTOS_DO_MODELO))
    def test_valores_do_modelo_de_dados(self, vocab, atributo):
        assert set(vocab.valores(atributo)) == ATRIBUTOS_DO_MODELO[atributo]

    def test_partes_do_modelo_de_dados(self, vocab):
        assert vocab.partes() == PARTES_DO_MODELO

    def test_iucn(self, vocab):
        assert set(vocab.valores("iucn")) == {"LC", "NT", "VU", "EN", "CR", "EW", "EX", "DD", "NE"}

    def test_multiplicidade(self, vocab):
        assert vocab.multiplo("cores") is True
        assert vocab.multiplo("bico_tipo") is False

    def test_marcas_tem_grupo(self, vocab):
        marcas = vocab.arquivo.atributos["marcas"]
        assert {v.grupo for v in marcas.valores.values()} == set(marcas.grupos)


class TestNormalizar:
    @pytest.mark.parametrize(
        "atributo, termo, esperado",
        [
            ("cores", "Acinzentado", "cinza"),
            ("cores", "negro", "preto"),
            ("cores", "cinza-escuro", "cinza"),
            ("cores", "Marrom avermelhado", "marrom"),
            ("cores", "esbranquiçadas", "branco"),
            ("cores", "ferrugíneo", "marrom"),
            ("cores", "alaranjado", "laranja"),
            ("cores", "verde-oliváceo", "verde"),
            ("cores", "cor-de-rosa", "rosa"),
            ("tamanho", "pequena", "pequeno"),
            ("tamanho", "Média", "medio"),
            ("bico_tipo", "insetos em troncos", "insetos_em_troncos"),
            ("bico_tipo", "sondador", "limicola_sondador"),
            ("ambiente", "Borda da mata", "borda_de_mata"),
            ("cauda", "rabo de tesoura", "bifurcada"),
            ("atividade", "cripuscular", "crepuscular"),
            ("iucn", "Pouco Preocupante", "LC"),
            ("iucn", "Vulnerável", "VU"),
        ],
    )
    def test_reconhece(self, vocab, atributo, termo, esperado):
        assert vocab.normalizar(atributo, termo) == esperado

    @pytest.mark.parametrize("termo", ["escuro", "claro", "iridescente", "", "tons mais escuros"])
    def test_nao_reconhece(self, vocab, termo):
        assert vocab.normalizar("cores", termo) is None

    def test_valor_exato_vale_como_termo(self, vocab):
        for atributo in ATRIBUTOS_DO_MODELO:
            for valor in vocab.valores(atributo):
                assert vocab.normalizar(atributo, valor) == valor

    def test_partes(self, vocab):
        assert vocab.normalizar_parte("Ventre") == "barriga"
        assert vocab.normalizar_parte("rabo") == "cauda"
        assert vocab.normalizar_parte("asa") == "asas"

    def test_atributo_desconhecido(self, vocab):
        with pytest.raises(KeyError, match="atributo desconhecido"):
            vocab.normalizar("plumagem", "cinza")

    def test_cobertura_das_cores_do_dataset_v1(self, vocab):
        """As cores livres do assistant v1 servem de régua para os sinônimos."""
        import json
        from collections import Counter

        path = get_settings().CONFIG_DIR.parent.parent / (
            "avesrag-assistant/app/script/data/oficial_dataset_udi.json"
        )
        if not path.exists():
            pytest.skip("avesrag-assistant não está ao lado do builder")
        dados = json.loads(path.read_text(encoding="utf-8"))
        contagem = Counter(t for d in dados for t in (d.get("cores") or []))
        cobertas = sum(n for t, n in contagem.items() if vocab.normalizar("cores", t))
        assert cobertas / sum(contagem.values()) >= 0.95


class TestMapear:
    def test_valor_mapeado(self, vocab):
        assert vocab.mapear("avonet.habitat", "Forest") == ["mata"]
        assert vocab.mapear("avonet.primary_lifestyle", "Terrestrial") == ["chao"]

    def test_valor_nulo_e_desconhecido(self, vocab):
        assert vocab.mapear("avonet.habitat", "Marine") is None
        assert vocab.mapear("avonet.habitat", "Lua") is None

    def test_origem_desconhecida(self, vocab):
        with pytest.raises(KeyError, match="mapeamento desconhecido"):
            vocab.mapear("xpto", "Forest")


class TestParaPrompt:
    def test_lista_valores_e_descricoes(self, vocab):
        texto = vocab.para_prompt(["tamanho", "cores_por_parte"])
        assert texto.startswith("- tamanho (um ou mais): pequeno (")
        assert "parte ∈ cabeca, olho" in texto
        assert "cor ∈ valores de cores" in texto


# ---------------------------------------------------------------------------
# Validação do próprio arquivo
# ---------------------------------------------------------------------------


class TestValidacao:
    def test_minimo_valido(self, tmp_path):
        vocab = carregar_vocabulario(_escrever(tmp_path, YAML_MINIMO))
        assert vocab.normalizar("cores", "negro") == "preto"

    def test_valor_fora_de_snake_case(self, tmp_path):
        erros = _erros(tmp_path, YAML_MINIMO.replace("cinza:", "Cinza Escuro:"))
        assert "use snake_case" in erros

    def test_chave_duplicada(self, tmp_path):
        conteudo = YAML_MINIMO.replace(
            "      preto: {descricao: d, sinonimos: [negro]}",
            "      preto: {descricao: d}\n      preto: {descricao: e}",
        )
        assert "chave duplicada: 'preto'" in _erros(tmp_path, conteudo)

    def test_sinonimo_em_dois_valores(self, tmp_path):
        erros = _erros(tmp_path, YAML_MINIMO.replace("[negro]", "[negro, Acinzentado]"))
        assert "'Acinzentado' aponta para 'cinza' e para 'preto'" in erros

    def test_sinonimo_igual_a_outro_valor(self, tmp_path):
        erros = _erros(tmp_path, YAML_MINIMO.replace("[negro]", "[negro, cinza]"))
        assert "aponta para 'cinza' e para 'preto'" in erros

    def test_mapeamento_para_valor_inexistente(self, tmp_path):
        erros = _erros(tmp_path, YAML_MINIMO.replace("Forest: [mata]", "Forest: [matas]"))
        assert "mapeamentos.fonte.habitat.Forest: 'matas' não é valor de ambiente" in erros

    def test_mapeamento_com_destino_inexistente(self, tmp_path):
        erros = _erros(tmp_path, YAML_MINIMO.replace("destino: ambiente", "destino: habitat"))
        assert "atributo 'habitat' não existe" in erros

    def test_mapeamento_com_lista_vazia(self, tmp_path):
        erros = _erros(tmp_path, YAML_MINIMO.replace("Marine: null", "Marine: []"))
        assert "lista vazia" in erros

    def test_cor_de_parte_aponta_para_atributo_inexistente(self, tmp_path):
        erros = _erros(tmp_path, YAML_MINIMO.replace("cor: cores", "cor: tons"))
        assert "cores_por_parte.cor" in erros

    def test_campo_desconhecido(self, tmp_path):
        erros = _erros(
            tmp_path,
            YAML_MINIMO.replace(
                "descricao: d\n    valores", "descricao: d\n    cor: x\n    valores", 1
            ),
        )
        assert "atributos.cores.cor" in erros

    def test_grupo_fora_da_lista(self, tmp_path):
        conteudo = YAML_MINIMO.replace(
            "  cores:\n    descricao: d\n", "  cores:\n    descricao: d\n    grupos: [cabeca]\n"
        ).replace("cinza: {descricao: d,", "cinza: {descricao: d, grupo: corpo,")
        erros = _erros(tmp_path, conteudo)
        assert "grupo 'corpo' não está em ['cabeca']" in erros
        assert "atributos.cores.preto: grupo None" in erros

    def test_varios_erros_de_uma_vez(self, tmp_path):
        conteudo = YAML_MINIMO.replace("Forest: [mata]", "Forest: [matas]").replace(
            "cor: cores", "cor: tons"
        )
        with pytest.raises(VocabularioInvalido) as exc:
            carregar_vocabulario(_escrever(tmp_path, conteudo))
        assert len(exc.value.erros) == 2

    def test_yaml_quebrado(self, tmp_path):
        assert "YAML inválido" in _erros(tmp_path, "atributos: [\n")


# ---------------------------------------------------------------------------
# Todas as categorias das fontes estão no mapeamento (mesmo que como null)
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestMapeamentosCobremAsFontes:
    @pytest.fixture(scope="class")
    def avonet(self):
        return pd.read_excel(
            get_settings().AVONET_XLSX,
            sheet_name="AVONET1_BirdLife",
            usecols=["Habitat", "Primary.Lifestyle"],
        )

    @pytest.mark.parametrize(
        "origem, coluna",
        [("avonet.habitat", "Habitat"), ("avonet.primary_lifestyle", "Primary.Lifestyle")],
    )
    def test_avonet(self, vocab, avonet, origem, coluna):
        na_fonte = set(avonet[coluna].dropna().unique())
        no_yaml = set(vocab.arquivo.mapeamentos[origem].valores)
        assert na_fonte <= no_yaml, f"faltam no YAML: {sorted(na_fonte - no_yaml)}"

    def test_birdbase_social(self, vocab):
        colunas = pd.read_excel(get_settings().BIRDBASE_XLSX, sheet_name="Data", header=1, nrows=0)
        sociais = {c for c in colunas.columns if str(c).startswith("Social_")}
        assert sociais == set(vocab.arquivo.mapeamentos["birdbase.social"].valores)
