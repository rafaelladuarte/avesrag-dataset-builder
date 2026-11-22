"""Testes para os documentos de busca (docs/montar.py) e o embedding da OpenAI."""

import pytest

from avesrag_builder.docs.montar import CHAVES_FILTRO, esperados, filtros, nomes, planejar
from avesrag_builder.llm.base import ErroFornecedor
from avesrag_builder.llm.openai import OpenAIFornecedor

MODELO = "text-embedding-3-large"

FICHA = {
    "species_id": "sp_pitangus_sulphuratus",
    "nome_cientifico": "Pitangus sulphuratus",
    "nomes": {"pt": ["bem-te-vi"], "en": ["Great Kiskadee"]},
    "taxonomia": {"ordem": "Passeriformes", "familia": "Tyrannidae", "genero": "Pitangus"},
    "atributos": {
        "tamanho": ["medio"],
        "comprimento_cm": 23.0,
        "cores": ["preto", "amarelo"],
        "cores_por_parte": [{"parte": "barriga", "cor": "amarelo"}],
        "bico_tipo": "generalista",
        "ambiente": ["area_urbana"],
    },
    "ocorrencia": {"biomas": ["Cerrado"], "n_municipios": 1},
}


def b03(aparencia="Barriga amarela.", comportamento="Pousa em fios.", voz=None, ok=True):
    return {
        "saida": {
            "aparencia": aparencia,
            "comportamento_ambiente": comportamento,
            "voz_habitos": voz,
        },
        "validacao": {"ok": ok},
    }


class TestMontar:
    def test_filtros_copiados_da_ficha(self):
        assert filtros(FICHA) == {
            "tamanho": ["medio"],
            "cores": ["preto", "amarelo"],
            "bico_tipo": "generalista",
            "ambiente": ["area_urbana"],
            "familia": "Tyrannidae",
            "biomas": ["Cerrado"],
        }

    def test_comprimento_e_cores_por_parte_nao_sao_filtro(self):
        assert "comprimento_cm" not in CHAVES_FILTRO
        assert "cores_por_parte" not in CHAVES_FILTRO

    def test_nomes(self):
        assert nomes(FICHA) == ["bem-te-vi", "Pitangus sulphuratus", "Great Kiskadee"]

    def test_um_documento_por_dominio_com_texto(self):
        docs = esperados(FICHA, b03())
        assert [d.dominio for d in docs] == ["aparencia", "comportamento_ambiente"]
        assert docs[0].id == "sp_pitangus_sulphuratus:aparencia"
        assert docs[0].texto == "Barriga amarela."  # sem o nome da espécie
        assert docs[0].filtros == docs[1].filtros

    def test_texto_so_com_espacos_nao_gera_documento(self):
        assert [d.dominio for d in esperados(FICHA, b03(comportamento="  "))] == ["aparencia"]

    def test_b03_invalido_ou_ausente(self):
        assert esperados(FICHA, b03(ok=False)) == []
        assert esperados(FICHA, None) == []


class TestPlanejar:
    def _existente(self, doc, **mudar):
        return {
            "_id": doc.id,
            "texto": doc.texto,
            "modelo": MODELO,
            "nomes": doc.nomes,
            "filtros": doc.filtros,
            **mudar,
        }

    def test_novo(self):
        docs = esperados(FICHA, b03())
        plano = planejar(docs, {}, MODELO)
        assert [d.id for d in plano.gerar] == [d.id for d in docs]
        assert set(plano.status.values()) == {"novo"}

    def test_inalterado_nao_gera_embedding(self):
        docs = esperados(FICHA, b03())
        existentes = {d.id: self._existente(d) for d in docs}
        plano = planejar(docs, existentes, MODELO)
        assert plano.gerar == [] and plano.reaproveitar == [] and plano.remover == []
        assert set(plano.status.values()) == {"inalterado"}

    def test_texto_mudou(self):
        doc = esperados(FICHA, b03())[0]
        plano = planejar([doc], {doc.id: self._existente(doc, texto="outro")}, MODELO)
        assert plano.status[doc.id] == "alterado"
        assert plano.gerar == [doc]

    def test_modelo_mudou(self):
        doc = esperados(FICHA, b03())[0]
        plano = planejar([doc], {doc.id: self._existente(doc, modelo="antigo")}, MODELO)
        assert plano.status[doc.id] == "alterado"

    def test_so_filtros_reaproveita_o_embedding(self):
        doc = esperados(FICHA, b03())[0]
        plano = planejar([doc], {doc.id: self._existente(doc, filtros={})}, MODELO)
        assert plano.status[doc.id] == "so_filtros"
        assert plano.gerar == [] and plano.reaproveitar == [doc]

    def test_documento_que_nao_e_mais_esperado_sai(self):
        docs = esperados(FICHA, b03())
        existentes = {d.id: self._existente(d) for d in docs}
        plano = planejar(docs[:1], existentes, MODELO)
        assert plano.remover == ["sp_pitangus_sulphuratus:comportamento_ambiente"]
        assert plano.status["sp_pitangus_sulphuratus:comportamento_ambiente"] == "removido"


class _Resposta:
    def __init__(self, status_code, corpo):
        self.status_code = status_code
        self._corpo = corpo
        self.text = str(corpo)

    def json(self):
        return self._corpo


class _Sessao:
    def __init__(self, resposta):
        self.headers = {}
        self.resposta = resposta
        self.chamadas = []

    def request(self, metodo, url, timeout, **kw):
        self.chamadas.append((metodo, url, kw))
        return self.resposta


class TestEmbeddingsOpenAI:
    def test_ordem_pelo_index_e_tokens(self):
        corpo = {
            "data": [{"index": 1, "embedding": [0.2]}, {"index": 0, "embedding": [0.1]}],
            "usage": {"total_tokens": 7},
        }
        sessao = _Sessao(_Resposta(200, corpo))
        r = OpenAIFornecedor("chave", sessao=sessao).embeddings(["a", "b"], MODELO)
        assert r.vetores == [[0.1], [0.2]]
        assert r.tokens == 7
        metodo, url, kw = sessao.chamadas[0]
        assert (metodo, url) == ("POST", "https://api.openai.com/v1/embeddings")
        assert kw["json"] == {"model": MODELO, "input": ["a", "b"]}

    def test_quantidade_errada_de_vetores(self):
        sessao = _Sessao(_Resposta(200, {"data": [{"index": 0, "embedding": [0.1]}]}))
        with pytest.raises(ErroFornecedor, match="1 vetores para 2 textos"):
            OpenAIFornecedor("chave", sessao=sessao).embeddings(["a", "b"], MODELO)

    def test_erro_http(self):
        sessao = _Sessao(_Resposta(401, {"error": "sem chave"}))
        with pytest.raises(ErroFornecedor, match="HTTP 401"):
            OpenAIFornecedor("chave", sessao=sessao).embeddings(["a"], MODELO)

    def test_lista_vazia_nao_chama(self):
        sessao = _Sessao(_Resposta(500, {}))
        assert OpenAIFornecedor("chave", sessao=sessao).embeddings([], MODELO).vetores == []
        assert sessao.chamadas == []
