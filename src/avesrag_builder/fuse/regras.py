"""Regras de fusão por campo (Especificação > Regras de derivação e fusão).

Uma função pura por campo: recebe os dados já carregados da espécie e devolve um
`Campo` (valor + proveniência) ou `None` quando nenhuma fonte tem valor. Nenhuma
função lê o banco; os cortes e mapeamentos vêm de `config/`.

Itens do `b01` e do `b02` cuja evidência não foi encontrada no texto de entrada
são descartados aqui (`itens_validos`); extrações com `validacao.ok = false`
(as `sem_texto`) não contribuem.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from avesrag_builder.core.models import Prov
from avesrag_builder.core.regras_fusao import RegrasFusao
from avesrag_builder.core.vocabulario import RegrasBico, Vocabulario
from avesrag_builder.ingest import birdalbum as ba

B01 = "b01_aparencia"
B02 = "b02_comportamento"
B03 = "b03_textos_busca"

# Fontes que entram numa união, na ordem em que aparecem no `_prov.fonte`.
ORDEM_FONTES = ("avonet", "birdalbum", "birdbase", "cbro", "ebird", "ibge", "wikiaves")

# reference_type do Bird Album -> do que a ilustração partiu.
REFERENCIA_BIRDALBUM = {"photo": "foto", "reference-board": "quadro", "": "descricao"}


@dataclass(frozen=True)
class Campo:
    valor: Any
    prov: Prov


@dataclass
class DadosEspecie:
    """Tudo o que a fusão precisa de uma espécie, já lido do banco."""

    species_id: str
    nome_cientifico: str
    nome_comum: str | None = None
    wikiaves: dict[str, Any] = field(default_factory=dict)  # `dados` do raw_wikiaves
    cbro: dict[str, Any] | None = None
    avonet: dict[str, Any] | None = None
    birdbase: dict[str, Any] | None = None
    extracoes: dict[str, dict[str, Any]] = field(default_factory=dict)  # prompt -> doc
    ocorrencia: dict[str, Any] | None = None  # doc de species_occurrence
    birdalbum: dict[str, Any] | None = None  # `dados` do raw_birdalbum
    birdalbum_por: str | None = None  # como casou: "ebird" ou "nome"

    @property
    def pagina(self) -> dict[str, Any]:
        return self.wikiaves.get("pagina") or {}

    @property
    def lista(self) -> dict[str, Any]:
        return self.wikiaves.get("lista") or {}


def _texto(valor: Any) -> str | None:
    if valor is None:
        return None
    texto = str(valor).strip()
    return texto or None


def _numero(valor: Any) -> float | None:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    return numero if numero > 0 else None  # NaN também sai aqui (NaN > 0 é falso)


def fonte_unida(fontes: Iterable[str]) -> str:
    unicas = set(fontes)
    return "+".join(f for f in ORDEM_FONTES if f in unicas)


def ordenar(vocab: Vocabulario, atributo: str, valores: Iterable[str]) -> list[str]:
    """Sem repetição, na ordem do vocabulário; valor desconhecido vai para o fim
    (o `validate` é quem acusa)."""
    ordem = {v: i for i, v in enumerate(vocab.valores(atributo))}
    return sorted(set(valores), key=lambda v: (ordem.get(v, len(ordem)), v))


# ---------------------------------------------------------------------------
# Extrações
# ---------------------------------------------------------------------------


def ref(extracao: dict[str, Any]) -> str:
    return f"{extracao['prompt']}@{extracao['versao']}"


def _utilizavel(extracao: dict[str, Any] | None) -> bool:
    return bool(extracao) and bool((extracao.get("validacao") or {}).get("ok"))


def itens_validos(extracao: dict[str, Any] | None, campo: str) -> tuple[list[dict[str, Any]], int]:
    """Itens do campo com evidência encontrada e quantos foram descartados."""
    if not _utilizavel(extracao):
        return [], 0
    nao_encontradas = set(extracao["validacao"].get("evidencias_nao_encontradas") or [])
    itens = (extracao.get("saida") or {}).get(campo) or []
    validos = [it for it in itens if it.get("evidencia") not in nao_encontradas]
    return validos, len(itens) - len(validos)


@dataclass
class Descartes:
    """Itens descartados por evidência não encontrada, por prompt."""

    por_prompt: dict[str, int] = field(default_factory=dict)

    def somar(self, prompt: str, n: int) -> None:
        if n:
            self.por_prompt[prompt] = self.por_prompt.get(prompt, 0) + n

    @property
    def total(self) -> int:
        return sum(self.por_prompt.values())


def _valores_llm(
    d: DadosEspecie, prompt: str, campo: str, descartes: Descartes, chave: str = "valor"
) -> list[str]:
    itens, descartados = itens_validos(d.extracoes.get(prompt), campo)
    descartes.somar(prompt, descartados)
    return [it[chave] for it in itens if it.get(chave)]


def _prov_llm(d: DadosEspecie, prompt: str) -> Prov:
    return Prov(fonte="wikiaves", metodo="llm", ref=ref(d.extracoes[prompt]))


# ---------------------------------------------------------------------------
# Identidade e taxonomia
# ---------------------------------------------------------------------------


def nomes_pt(d: DadosEspecie) -> Campo | None:
    nome = _texto(d.lista.get("nome_comum")) or _texto(d.nome_comum)
    return Campo([nome], Prov(fonte="wikiaves")) if nome else None


def nomes_en(d: DadosEspecie) -> Campo | None:
    nome = _texto((d.cbro or {}).get("English Name"))
    if nome:
        return Campo([nome], Prov(fonte="cbro"))
    nome = _texto(d.pagina.get("nome_ingles"))
    return Campo([nome], Prov(fonte="wikiaves", metodo="reserva")) if nome else None


def taxonomia(d: DadosEspecie) -> Campo | None:
    """Ordem, família e gênero da mesma linha de uma única fonte, nunca misturados."""
    cbro = d.cbro or {}
    trio = {
        "ordem": _texto(cbro.get("Ordem")),
        "familia": _texto(cbro.get("Família")),
        "genero": _texto(cbro.get("Gênero")),
    }
    if all(trio.values()):
        return Campo(trio, Prov(fonte="cbro"))
    classificacao = d.pagina.get("classificacao_cientifica") or {}
    trio = {
        "ordem": _texto(classificacao.get("Ordem")),
        "familia": _texto(classificacao.get("Família")),
        "genero": _texto(d.nome_cientifico.split(" ")[0]),
    }
    if all(trio.values()):
        return Campo(trio, Prov(fonte="wikiaves", metodo="reserva"))
    return None


def status_ocorrencia(d: DadosEspecie) -> Campo | None:
    status = _texto((d.cbro or {}).get("Status"))
    return Campo(status, Prov(fonte="cbro")) if status else None


def iucn(d: DadosEspecie, vocab: Vocabulario) -> Campo | None:
    bruto = _texto((d.birdbase or {}).get("2024 IUCN Red List category"))
    valor = vocab.normalizar("iucn", bruto) if bruto else None
    if valor:
        return Campo(valor, Prov(fonte="birdbase"))
    bruto = _texto(d.pagina.get("estado_de_conservacao"))
    valor = vocab.normalizar("iucn", bruto) if bruto else None
    return Campo(valor, Prov(fonte="wikiaves", metodo="reserva")) if valor else None


def midia(d: DadosEspecie) -> Campo | None:
    """Só o link para a página do WikiAves. A foto do WikiAves não entra na ficha:
    o Termo de Uso proíbe a reprodução (B8); a foto vem do iNaturalist ou do Commons."""
    url = _texto(d.pagina.get("url"))
    return Campo({"url_wikiaves": url}, Prov(fonte="wikiaves")) if url else None


def ilustracao(d: DadosEspecie, repo: str, ref: str) -> Campo | None:
    """Ilustração do Bird Album (mídia secundária): só com arquivo, licença CC BY e
    o selo de qualidade do próprio projeto."""
    b = d.birdalbum or {}
    arquivo = _texto(b.get("sticker_file"))
    if not arquivo or b.get("sticker_license") != ba.LICENCA_FONTE:
        return None
    if str(b.get("meets_quality_bar")).strip().lower() != "true":
        return None
    referencia = REFERENCIA_BIRDALBUM.get((b.get("reference_type") or "").strip())
    if referencia is None:
        return None
    valor = {
        "url": ba.url_raw(repo, ref, arquivo),
        "credito": ba.CREDITO,
        "licenca": ba.LICENCA,
        "link": ba.link_repositorio(repo),
        "gerada_por_ia": True,
        "referencia": referencia,
    }
    return Campo(valor, Prov(fonte="birdalbum", metodo=d.birdalbum_por))


def ocorrencia(d: DadosEspecie) -> Campo | None:
    occ = d.ocorrencia
    if not occ:
        return None
    valor: dict[str, Any] = {"n_municipios": occ["n_municipios"]}
    if occ.get("biomas"):
        valor["biomas"] = list(occ["biomas"])
    return Campo(valor, Prov(fonte="ebird+ibge"))


# ---------------------------------------------------------------------------
# Atributos de aparência (b01)
# ---------------------------------------------------------------------------


def comprimento_cm(d: DadosEspecie, regras: RegrasFusao, descartes: Descartes) -> Campo | None:
    extracao = d.extracoes.get(B01)
    if not _utilizavel(extracao):
        return None
    comp = (extracao.get("saida") or {}).get("comprimento_cm")
    if not comp:
        return None
    if comp.get("evidencia") in set(extracao["validacao"].get("evidencias_nao_encontradas") or []):
        descartes.somar(B01, 1)
        return None
    medidas = [m for m in (_numero(comp.get("min")), _numero(comp.get("max"))) if m]
    if not medidas:
        return None
    valor = regras.arredondar_comprimento(sum(medidas) / len(medidas))
    return Campo(valor, _prov_llm(d, B01))


def massa_g(d: DadosEspecie) -> tuple[float, str] | None:
    """Average Mass do BIRDBASE; senão, Mass do AVONET."""
    for fonte, dados, coluna in (
        ("birdbase", d.birdbase, "Average Mass"),
        ("avonet", d.avonet, "Mass"),
    ):
        massa = _numero((dados or {}).get(coluna))
        if massa:
            return massa, fonte
    return None


def tamanho(
    d: DadosEspecie, comprimento: Campo | None, regras: RegrasFusao, vocab: Vocabulario
) -> Campo | None:
    if comprimento is not None:
        faixas = regras.tamanho_por_comprimento(comprimento.valor)
        prov = Prov(fonte="wikiaves", metodo="comprimento", ref=comprimento.prov.ref)
        return Campo(ordenar(vocab, "tamanho", faixas), prov)
    massa = massa_g(d)
    if massa is None:
        return None
    valor, fonte = massa
    faixas = regras.tamanho_por_massa(valor)
    return Campo(ordenar(vocab, "tamanho", faixas), Prov(fonte=fonte, metodo="massa"))


def cores_por_parte(d: DadosEspecie, vocab: Vocabulario, descartes: Descartes) -> Campo | None:
    itens, descartados = itens_validos(d.extracoes.get(B01), "cores_por_parte")
    descartes.somar(B01, descartados)
    pares = {(it["parte"], it["cor"]) for it in itens if it.get("parte") and it.get("cor")}
    if not pares:
        return None
    ordem_parte = {p: i for i, p in enumerate(vocab.partes())}
    ordem_cor = {c: i for i, c in enumerate(vocab.valores("cores"))}
    ordenados = sorted(
        pares, key=lambda pc: (ordem_parte.get(pc[0], 99), ordem_cor.get(pc[1], 99), pc)
    )
    valor = [{"parte": p, "cor": c} for p, c in ordenados]
    return Campo(valor, _prov_llm(d, B01))


def cores(
    d: DadosEspecie, por_parte: Campo | None, vocab: Vocabulario, descartes: Descartes
) -> Campo | None:
    """Cores do b01 mais toda cor que aparece em `cores_por_parte`."""
    valores = _valores_llm(d, B01, "cores", descartes)
    if por_parte is not None:
        valores += [item["cor"] for item in por_parte.valor]
    if not valores:
        return None
    return Campo(ordenar(vocab, "cores", valores), _prov_llm(d, B01))


def lista_llm(
    d: DadosEspecie, prompt: str, atributo: str, vocab: Vocabulario, descartes: Descartes
) -> Campo | None:
    """Atributo que só vem do LLM (`marcas`, `cauda`, `o_que_fazia`, `atividade`)."""
    valores = _valores_llm(d, prompt, atributo, descartes)
    if not valores:
        return None
    return Campo(ordenar(vocab, atributo, valores), _prov_llm(d, prompt))


# ---------------------------------------------------------------------------
# Bico
# ---------------------------------------------------------------------------


def bico_tipo(d: DadosEspecie, familia: str | None, bico: RegrasBico) -> Campo | None:
    """Família; senão, nicho trófico do AVONET; senão, dieta principal do BIRDBASE."""
    tipo = bico.tipo_por_familia(familia) if familia else None
    if tipo:
        return Campo(tipo, Prov(fonte="regra_familia"))
    for fonte, origem, dados, coluna in (
        ("dieta_avonet", "avonet.trophic_niche", d.avonet, "Trophic.Niche"),
        ("dieta_birdbase", "birdbase.primary_diet", d.birdbase, "Primary Diet"),
    ):
        dieta = _texto((dados or {}).get(coluna))
        tipo = bico.tipo_por_dieta(origem, dieta) if dieta else None
        if tipo:
            return Campo(tipo, Prov(fonte=fonte))
    return None


# ---------------------------------------------------------------------------
# Comportamento (b02 + planilhas)
# ---------------------------------------------------------------------------


def ambiente(d: DadosEspecie, vocab: Vocabulario, descartes: Descartes) -> Campo | None:
    """União do habitat do AVONET (mapeado) com o b02."""
    do_llm = _valores_llm(d, B02, "ambiente", descartes)
    habitat = _texto((d.avonet or {}).get("Habitat"))
    do_avonet = (vocab.mapear("avonet.habitat", habitat) if habitat else None) or []
    if not do_llm and not do_avonet:
        return None
    valor = ordenar(vocab, "ambiente", [*do_avonet, *do_llm])
    if do_llm and do_avonet:
        prov = Prov(
            fonte=fonte_unida(["avonet", "wikiaves"]), metodo="uniao", ref=ref(d.extracoes[B02])
        )
    elif do_llm:
        prov = _prov_llm(d, B02)
    else:
        prov = Prov(fonte="avonet", metodo="mapeamento")
    return Campo(valor, prov)


def onde_estava(d: DadosEspecie, vocab: Vocabulario, descartes: Descartes) -> Campo | None:
    """b02; sem valor, a locomoção do AVONET."""
    valores = _valores_llm(d, B02, "onde_estava", descartes)
    if valores:
        return Campo(ordenar(vocab, "onde_estava", valores), _prov_llm(d, B02))
    estilo = _texto((d.avonet or {}).get("Primary.Lifestyle"))
    reserva = vocab.mapear("avonet.primary_lifestyle", estilo) if estilo else None
    if not reserva:
        return None
    return Campo(ordenar(vocab, "onde_estava", reserva), Prov(fonte="avonet", metodo="reserva"))


def grupo(d: DadosEspecie, vocab: Vocabulario, descartes: Descartes) -> Campo | None:
    """b02; sem valor, as colunas sociais do BIRDBASE marcadas com 1."""
    valores = _valores_llm(d, B02, "grupo", descartes)
    if valores:
        return Campo(ordenar(vocab, "grupo", valores), _prov_llm(d, B02))
    mapa = vocab.arquivo.mapeamentos["birdbase.social"].valores
    reserva: list[str] = []
    for coluna in mapa:
        if _numero((d.birdbase or {}).get(coluna)) == 1:
            reserva += vocab.mapear("birdbase.social", coluna) or []
    if not reserva:
        return None
    return Campo(ordenar(vocab, "grupo", reserva), Prov(fonte="birdbase", metodo="reserva"))
