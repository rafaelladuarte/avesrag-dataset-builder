"""Testes para a agregação da busca, as consultas de fumaça e as definições dos índices."""

import textwrap

import pytest

from avesrag_builder.core.settings import get_settings
from avesrag_builder.core.vocabulario import VocabularioInvalido
from avesrag_builder.docs.busca import Candidata, agregar, carregar_consultas, posicao
from avesrag_builder.docs.indices import contem, definicao_texto, definicao_vetor
from avesrag_builder.docs.montar import CHAVES_FILTRO


class TestAgregar:
    def test_ordena_pela_maior_nota_e_guarda_a_soma(self):
        acertos = [("a", 0.9), ("b", 0.8), ("b", 0.7), ("a", 0.1)]
        assert agregar(acertos) == [Candidata("a", 1.0, 0.9), Candidata("b", 1.5, 0.8)]

    def test_empate_na_maior_decide_pela_soma(self):
        acertos = [("a", 0.8), ("b", 0.8), ("b", 0.1)]
        assert [c.species_id for c in agregar(acertos)] == ["b", "a"]

    def test_top_k(self):
        acertos = [(f"s{i}", 1 - i / 100) for i in range(20)]
        assert len(agregar(acertos, k=10)) == 10

    def test_posicao_pela_soma_e_pela_maior(self):
        cands = agregar([("a", 0.9), ("b", 0.8), ("b", 0.7)])
        assert posicao(cands, "a") == 1  # padrão: maior nota
        assert posicao(cands, "b", "soma") == 1
        assert posicao(cands, "x") is None


class TestConsultas:
    def test_arquivo_real(self):
        arquivo = carregar_consultas(get_settings().CONFIG_DIR / "consultas_fumaca.yaml")
        esperadas = {c.esperada for c in arquivo.consultas}
        assert {"sp_pitangus_sulphuratus", "sp_ramphastos_toco"} <= esperadas  # aceite
        assert arquivo.top == 10

    def test_dominio_invalido(self, tmp_path):
        path = tmp_path / "c.yaml"
        path.write_text(
            textwrap.dedent(
                """\
                versao: "1"
                consultas:
                  - {consulta: x, esperada: sp_a_b, dominio: canto}
                """
            ),
            encoding="utf-8",
        )
        with pytest.raises(VocabularioInvalido, match="'canto' não é domínio"):
            carregar_consultas(path)

    def test_species_id_invalido(self, tmp_path):
        path = tmp_path / "c.yaml"
        path.write_text('versao: "1"\nconsultas:\n  - {consulta: x, esperada: Bem-te-vi}\n')
        with pytest.raises(VocabularioInvalido, match="esperada"):
            carregar_consultas(path)


class TestIndices:
    def test_vetor_com_um_filtro_por_chave(self):
        campos = definicao_vetor()["fields"]
        assert campos[0] == {
            "type": "vector",
            "path": "embedding",
            "numDimensions": 3072,
            "similarity": "cosine",
        }
        filtros = {c["path"] for c in campos if c["type"] == "filter"}
        assert filtros == {"dominio", "species_id", *(f"filtros.{k}" for k in CHAVES_FILTRO)}

    def test_texto_em_portugues(self):
        campos = definicao_texto()["mappings"]["fields"]
        assert campos["texto"]["analyzer"] == "lucene.portuguese"
        assert set(campos) == {"texto", "nomes"}

    def test_contem_ignora_padroes_do_servidor_e_ordem(self):
        esperado = {"fields": [{"type": "filter", "path": "a"}, {"type": "filter", "path": "b"}]}
        atual = {
            "fields": [
                {"type": "filter", "path": "b"},
                {"type": "filter", "path": "a", "extra": 1},
            ],
            "storedSource": False,
        }
        assert contem(atual, esperado)

    def test_contem_detecta_mudanca(self):
        esperado = {"fields": [{"type": "filter", "path": "a"}]}
        assert not contem({"fields": [{"type": "filter", "path": "b"}]}, esperado)
        assert not contem({"fields": []}, esperado)
