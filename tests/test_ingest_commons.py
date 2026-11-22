"""Testes para a ingestão do Commons (ingest/commons.py) e o cliente HTTP, sem rede."""

import pytest
import requests

from avesrag_builder.ingest import commons as c
from avesrag_builder.ingest.http import ClienteJson


def binding(qid, nome, arquivo):
    return {
        "item": {"value": f"http://www.wikidata.org/entity/{qid}"},
        "nome": {"value": nome},
        "img": {"value": f"http://commons.wikimedia.org/wiki/Special:FilePath/{arquivo}"},
    }


class TestWikidata:
    def test_consulta_escapa_aspas(self):
        q = c.consulta_sparql(["Pitangus sulphuratus", 'Nome "estranho"'])
        assert '"Pitangus sulphuratus"' in q
        assert '"Nome \\"estranho\\""' in q
        assert "wdt:P225" in q and "wdt:P18" in q

    def test_arquivo_da_url(self):
        url = "http://commons.wikimedia.org/wiki/Special:FilePath/Pitangus%20sulphuratus_1.jpg"
        assert c.arquivo_da_url(url) == "Pitangus sulphuratus 1.jpg"

    def test_ler_p18_junta_nomes_e_escolhe_um_arquivo_estavel(self):
        itens = c.ler_p18(
            [
                binding("Q1", "Astur bicolor", "B.jpg"),
                binding("Q1", "Accipiter bicolor", "A%20foto.jpg"),
                binding("Q2", "Pitangus sulphuratus", "Bem-te-vi.jpg"),
            ]
        )
        assert itens["Q1"] == {
            "qid": "Q1",
            "nomes": ["Accipiter bicolor", "Astur bicolor"],
            "arquivo": "A foto.jpg",
        }
        assert itens["Q2"]["arquivo"] == "Bem-te-vi.jpg"


IMAGEINFO = {
    "query": {
        "normalized": [{"from": "File:bem-te-vi.jpg", "to": "File:Bem-te-vi.jpg"}],
        "pages": [
            {
                "title": "File:Bem-te-vi.jpg",
                "imageinfo": [
                    {
                        "thumburl": "https://upload.wikimedia.org/thumb/640px-Bem-te-vi.jpg",
                        "url": "https://upload.wikimedia.org/Bem-te-vi.jpg",
                        "descriptionurl": "https://commons.wikimedia.org/wiki/File:Bem-te-vi.jpg",
                        "extmetadata": {
                            "LicenseShortName": {"value": "CC BY-SA 4.0"},
                            "LicenseUrl": {
                                "value": "https://creativecommons.org/licenses/by-sa/4.0"
                            },
                            "Artist": {
                                "value": '<a href="//commons.wikimedia.org/wiki/User:X">X</a>'
                            },
                        },
                    }
                ],
            },
            {"title": "File:Apagado.jpg", "missing": True},
        ],
    }
}


class TestCommons:
    def test_ler_imageinfo_volta_ao_nome_pedido(self):
        meta = c.ler_imageinfo(IMAGEINFO)
        assert set(meta) == {"bem-te-vi.jpg"}
        m = meta["bem-te-vi.jpg"]
        assert m["url"].endswith("640px-Bem-te-vi.jpg")
        assert m["url_original"] == "https://upload.wikimedia.org/Bem-te-vi.jpg"
        assert m["licenca"] == "CC BY-SA 4.0"
        assert m["artista"].startswith("<a ")  # HTML como veio; o fuse limpa
        assert m["credito"] is None

    def test_tira_parametros_de_rastreamento(self):
        url = (
            "https://thumb.wikimedia.org/a/960px-B%2870%29.jpg"
            "?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail"
        )
        assert c.sem_rastreamento(url) == "https://thumb.wikimedia.org/a/960px-B%2870%29.jpg"
        assert c.sem_rastreamento("https://x/a.jpg?page=2&utm_source=y") == "https://x/a.jpg?page=2"
        assert c.sem_rastreamento(None) is None

    def test_ler_categorias_junta_as_partes(self):
        partes = [
            {
                "query": {
                    "pages": [{"title": "File:A.jpg", "categories": [{"title": "Category:Z"}]}]
                }
            },
            {
                "query": {
                    "pages": [
                        {"title": "File:A.jpg", "categories": [{"title": "Category:B"}]},
                        {"title": "File:C.jpg"},
                    ]
                }
            },
        ]
        assert c.ler_categorias(partes) == {"A.jpg": ["Category:B", "Category:Z"], "C.jpg": []}

    def test_montar_registros(self):
        itens = {
            "Q2": {"qid": "Q2", "nomes": ["Pitangus sulphuratus"], "arquivo": "bem-te-vi.jpg"},
            "Q9": {"qid": "Q9", "nomes": ["Sumida"], "arquivo": "Apagado.jpg"},
        }
        registros, sem_arquivo = c.montar_registros(
            itens, c.ler_imageinfo(IMAGEINFO), {"bem-te-vi.jpg": ["Category:Tyrannidae"]}
        )
        assert [i for i, _ in registros] == ["wikidata:Q2"]
        dados = registros[0][1]
        assert dados["qid"] == "Q2"
        assert dados["categorias"] == ["Category:Tyrannidae"]
        assert dados["licenca"] == "CC BY-SA 4.0"
        assert sem_arquivo == ["Q9: Apagado.jpg não existe no Commons"]


class Resposta:
    def __init__(self, status=200, corpo=None, headers=None):
        self.status_code = status
        self._corpo = corpo or {}
        self.headers = headers or {}

    def json(self):
        return self._corpo

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


class TestClienteJson:
    def cliente(self, monkeypatch, respostas, intervalo=0.0):
        esperas = []
        cliente = ClienteJson("teste/1.0", intervalo=intervalo, dormir=esperas.append)
        fila = list(respostas)

        def get(url, params=None, timeout=None):
            r = fila.pop(0)
            if isinstance(r, Exception):
                raise r
            return r

        monkeypatch.setattr(cliente.sessao, "get", get)
        return cliente, esperas

    def test_user_agent(self):
        assert ClienteJson("teste/1.0").sessao.headers["User-Agent"] == "teste/1.0"

    def test_repete_em_429_conexao_e_5xx(self, monkeypatch):
        cliente, esperas = self.cliente(
            monkeypatch,
            [
                Resposta(429, headers={"Retry-After": "7"}),
                requests.ConnectionError("sem rota"),
                Resposta(503),
                Resposta(200, {"ok": True}),
            ],
            intervalo=1.0,
        )
        assert cliente.get("https://exemplo") == {"ok": True}
        assert esperas == [7, 30, 45, 1.0]  # Retry-After, depois 15 s × tentativa, e o intervalo

    def test_desiste_depois_das_tentativas(self, monkeypatch):
        cliente, _ = self.cliente(monkeypatch, [Resposta(503)] * 5)
        with pytest.raises(requests.HTTPError):
            cliente.get("https://exemplo")

    def test_erro_do_cliente_nao_repete(self, monkeypatch):
        cliente, esperas = self.cliente(monkeypatch, [Resposta(400)])
        with pytest.raises(requests.HTTPError):
            cliente.get("https://exemplo")
        assert esperas == []
