"""Etapa 3 (`extract`): raw_wikiaves + species_registry -> species_extractions.

Para cada espécie × prompt (b01–b03):

1. monta o pedido e o `input_hash` (modelo + system renderizado + entrada + schema);
2. pula o par se já há extração com o mesmo hash e a mesma versão (cache);
3. par sem texto de entrada vira extração `sem_texto`, sem chamar o LLM;
4. envia os pendentes num lote da API de batch, grava o lote em `llm_batches`
   antes de esperar e coleta ao concluir (ou na próxima execução, se o processo cair);
5. valida cada resposta contra o contrato, confere as evidências e grava;
   resposta inválida ou com erro é refeita uma vez, por chamada síncrona.
"""

from __future__ import annotations

import csv
import json
import time
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError
from pymongo import ReplaceOne
from pymongo.database import Database

from avesrag_builder.core.logging import get_logger
from avesrag_builder.core.models import Extraction, LoteLLM, Validacao, compute_source_hash
from avesrag_builder.core.settings import Settings, get_settings
from avesrag_builder.core.vocabulario import Vocabulario, vocabulario_padrao
from avesrag_builder.db.collections import (
    LLM_BATCHES,
    RAW_WIKIAVES,
    SPECIES_EXTRACTIONS,
    SPECIES_REGISTRY,
)
from avesrag_builder.extract.contratos import SCHEMAS, contrato, normalizar_saida, schema_estrito
from avesrag_builder.extract.evidencias import evidencias, nao_encontradas
from avesrag_builder.llm.base import Fornecedor, Pedido, Resposta
from avesrag_builder.llm.prompts import CAMPOS_WIKIAVES, Prompt, carregar_prompts
from avesrag_builder.resolve.registry import especies_do_piloto

log = get_logger(__name__)

SEM_TEXTO = "sem_texto"
INTERVALO_S = 60
LOTE_MONGO = 500


# ---------------------------------------------------------------------------
# Tarefas (espécie × prompt)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Tarefa:
    species_id: str
    prompt: Prompt
    modelo: str
    contrato: type[BaseModel]
    pedido: Pedido
    input_hash: str
    texto_fonte: str  # textos de entrada juntos, para conferir as evidências
    sem_texto: bool

    @property
    def extraction_id(self) -> str:
        return f"{self.species_id}:{self.prompt.id}"


def custom_id(species_id: str, prompt_id: str, input_hash: str) -> str:
    return f"{species_id}:{prompt_id}:{input_hash[:12]}"


def montar_tarefa(
    species_id: str,
    textos: dict[str, str],
    prompt: Prompt,
    voc: Vocabulario,
    settings: Settings,
) -> Tarefa:
    modelo = prompt.modelo or settings.LLM_MODEL
    modelo_contrato = contrato(prompt.schema_nome, prompt.vocabulario, voc)
    schema = schema_estrito(modelo_contrato)
    system = prompt.render_system(voc)
    usados = {c: (textos.get(c) or "").strip() for c in prompt.campos}
    entrada = prompt.render_entrada(usados)
    input_hash = compute_source_hash(
        {"modelo": modelo, "system": system, "entrada": entrada, "schema": schema}
    )
    return Tarefa(
        species_id=species_id,
        prompt=prompt,
        modelo=modelo,
        contrato=modelo_contrato,
        pedido=Pedido(
            id=custom_id(species_id, prompt.id, input_hash),
            modelo=modelo,
            system=system,
            entrada=entrada,
            schema=schema,
            temperatura=prompt.temperatura,
        ),
        input_hash=input_hash,
        texto_fonte="\n".join(t for t in usados.values() if t),
        sem_texto=not any(usados.values()),
    )


def escopo(db: Database, piloto: bool, limite: int = 0) -> list[str]:
    """`species_id` a processar: o piloto, ou todas as espécies com página coletada."""
    if piloto:
        ids = especies_do_piloto(db)
    else:
        com_pagina = [
            d["_id"] for d in db[RAW_WIKIAVES].find({"dados.pagina": {"$exists": True}}, {"_id": 1})
        ]
        docs = db[SPECIES_REGISTRY].find(
            {"chaves.wikiaves": {"$in": com_pagina}}, {"species_id": 1}
        )
        ids = sorted(d["species_id"] for d in docs)
    return ids[:limite] if limite else ids


def carregar_textos(db: Database, species_ids: Iterable[str]) -> dict[str, dict[str, str]]:
    """Textos do WikiAves de cada espécie (vazios se a página não foi coletada)."""
    ids = list(species_ids)
    chave = {
        d["species_id"]: d["chaves"]["wikiaves"]
        for d in db[SPECIES_REGISTRY].find(
            {"species_id": {"$in": ids}}, {"species_id": 1, "chaves.wikiaves": 1}
        )
    }
    projecao = {f"dados.pagina.{c}": 1 for c in CAMPOS_WIKIAVES}
    paginas = {
        d["_id"]: (d.get("dados") or {}).get("pagina") or {}
        for d in db[RAW_WIKIAVES].find({"_id": {"$in": list(chave.values())}}, projecao)
    }
    faltando = sorted(set(ids) - set(chave))
    if faltando:
        raise ValueError(f"species_id fora do species_registry: {', '.join(faltando[:5])}")
    return {
        sid: {c: paginas.get(chave[sid], {}).get(c) or "" for c in CAMPOS_WIKIAVES} for sid in ids
    }


# ---------------------------------------------------------------------------
# Respostas -> extrações
# ---------------------------------------------------------------------------


def _agora() -> datetime:
    return datetime.now(UTC)


def _extraction(t: Tarefa, saida: dict[str, Any], validacao: Validacao) -> Extraction:
    return Extraction(
        id=t.extraction_id,
        species_id=t.species_id,
        prompt=t.prompt.id,
        versao=t.prompt.versao,
        modelo=t.modelo,
        input_hash=t.input_hash,
        saida=saida,
        validacao=validacao,
        criado_em=_agora(),
    )


def extracao_sem_texto(t: Tarefa) -> Extraction:
    return _extraction(t, {}, Validacao(ok=False, erro=SEM_TEXTO))


def extracao_com_erro(t: Tarefa, erro: str) -> Extraction:
    return _extraction(t, {}, Validacao(ok=False, erro=erro))


def interpretar(t: Tarefa, r: Resposta) -> tuple[Extraction | None, str | None]:
    """Resposta válida -> (extração, None); senão (None, motivo)."""
    if r.erro:
        return None, r.erro if r.erro.startswith("erro_api") else f"erro_api: {r.erro}"
    try:
        bruto = json.loads(r.conteudo or "")
    except json.JSONDecodeError as e:
        return None, f"invalido: JSON malformado ({e})"
    if not isinstance(bruto, dict):
        return None, "invalido: a saída não é um objeto JSON"
    try:
        saida = t.contrato.model_validate(normalizar_saida(bruto)).model_dump(mode="json")
    except ValidationError as e:
        erros = "; ".join(
            ".".join(str(p) for p in err["loc"]) + f": {err['msg']}" for err in e.errors()[:5]
        )
        return None, f"invalido: {erros}"
    faltando = nao_encontradas(saida, t.texto_fonte)
    return _extraction(t, saida, Validacao(ok=True, evidencias_nao_encontradas=faltando)), None


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------


@dataclass
class Resultado:
    pares: int = 0
    cache: int = 0
    sem_texto: int = 0
    enviados: int = 0  # pedidos novos (lote ou síncrono)
    coletados: int = 0  # respostas processadas nesta execução
    retentativas: int = 0
    descartados: int = 0  # respostas de lote que não batem mais com a entrada atual
    em_lote: int = 0  # pedidos em lote ainda não concluído
    lotes_enviados: list[str] = field(default_factory=list)
    lotes_coletados: list[str] = field(default_factory=list)
    lotes_em_andamento: list[str] = field(default_factory=list)
    tokens_entrada: int = 0
    tokens_saida: int = 0
    custo_usd: float = 0.0
    linhas: list[str] = field(default_factory=list)  # resumo do estado final

    def somar_uso(self, r: Resposta, preco: tuple[float, float], fator: float) -> None:
        self.tokens_entrada += r.tokens_entrada
        self.tokens_saida += r.tokens_saida
        self.custo_usd += fator * (r.tokens_entrada * preco[0] + r.tokens_saida * preco[1]) / 1e6


class Extrator:
    def __init__(
        self,
        db: Database,
        fornecedor: Fornecedor,
        settings: Settings | None = None,
        vocabulario: Vocabulario | None = None,
        intervalo_s: float = INTERVALO_S,
        dormir: Callable[[float], None] = time.sleep,
    ):
        self.db = db
        self.fornecedor = fornecedor
        self.settings = settings or get_settings()
        self.voc = vocabulario or vocabulario_padrao()
        self.prompts = carregar_prompts(self.settings.CONFIG_DIR / "prompts", self.voc, SCHEMAS)
        self.intervalo_s = intervalo_s
        self.dormir = dormir
        self.preco = (self.settings.LLM_PRECO_ENTRADA, self.settings.LLM_PRECO_SAIDA)
        self.resultado = Resultado()

    # -- tarefas --------------------------------------------------------------

    def tarefas(self, species_ids: Iterable[str]) -> dict[str, Tarefa]:
        """custom_id -> tarefa, para as espécies dadas."""
        textos = carregar_textos(self.db, species_ids)
        tarefas = (
            montar_tarefa(sid, txt, p, self.voc, self.settings)
            for sid, txt in textos.items()
            for p in self.prompts
        )
        return {t.pedido.id: t for t in tarefas}

    def _em_cache(self, tarefas: Iterable[Tarefa]) -> set[str]:
        """custom_id das tarefas com extração atual (mesmo hash e versão)."""
        por_id = {t.extraction_id: t for t in tarefas}
        atuais = set()
        for d in self.db[SPECIES_EXTRACTIONS].find(
            {"_id": {"$in": list(por_id)}}, {"input_hash": 1, "versao": 1, "validacao": 1}
        ):
            t = por_id[d["_id"]]
            validacao = d.get("validacao") or {}
            reaproveita = validacao.get("ok") or validacao.get("erro") == SEM_TEXTO
            if d.get("input_hash") == t.input_hash and d.get("versao") == t.prompt.versao:
                if reaproveita:
                    atuais.add(t.pedido.id)
        return atuais

    def _gravar(self, extracoes: list[Extraction]) -> None:
        ops = [ReplaceOne({"_id": e.id}, e.to_mongo(), upsert=True) for e in extracoes]
        for i in range(0, len(ops), LOTE_MONGO):
            self.db[SPECIES_EXTRACTIONS].bulk_write(ops[i : i + LOTE_MONGO], ordered=False)

    # -- respostas ------------------------------------------------------------

    def _processar(self, pares: list[tuple[Tarefa, Resposta]], fator: float) -> None:
        """Valida, refaz uma vez o que falhou (síncrono) e grava."""
        extracoes = []
        for t, r in pares:
            self.resultado.somar_uso(r, self.preco, fator)
            self.resultado.coletados += 1
            extracao, erro = interpretar(t, r)
            if extracao is None:
                log.warning(f"{t.extraction_id}: {erro}; tentando de novo")
                self.resultado.retentativas += 1
                r2 = self.fornecedor.gerar(t.pedido)
                self.resultado.somar_uso(r2, self.preco, 2.0)
                extracao, erro2 = interpretar(t, r2)
                if extracao is None:
                    log.error(f"{t.extraction_id}: {erro2}")
                    extracao = extracao_com_erro(t, erro2 or erro or "erro desconhecido")
            extracoes.append(extracao)
        self._gravar(extracoes)

    def _esperar(self, lote_id: str) -> str:
        while True:
            situacao = self.fornecedor.situacao_lote(lote_id)
            log.info(f"lote {lote_id}: {situacao.detalhe or situacao.status}")
            if situacao.status != "em_andamento":
                return situacao.status
            self.dormir(self.intervalo_s)

    def _coletar(self, lote: dict[str, Any], status: str, tarefas: dict[str, Tarefa]) -> None:
        col = self.db[LLM_BATCHES]
        if status == "falhou":
            col.update_one(
                {"_id": lote["_id"]},
                {"$set": {"status": "falhou", "atualizado_em": _agora()}},
            )
            log.error(f"lote {lote['_id']} falhou; os pedidos voltam a ser pendentes")
            return
        respostas = {r.id: r for r in self.fornecedor.resultados_lote(lote["_id"])}
        pares = []
        for pid in lote["pedidos"]:
            t = tarefas.get(pid)
            if t is None:  # a entrada mudou desde o envio: a resposta não vale mais
                self.resultado.descartados += 1
                continue
            pares.append(
                (t, respostas.get(pid) or Resposta(id=pid, erro="erro_api: sem resposta no lote"))
            )
        self._processar(pares, fator=1.0)
        col.update_one(
            {"_id": lote["_id"]}, {"$set": {"status": "coletado", "atualizado_em": _agora()}}
        )
        self.resultado.lotes_coletados.append(lote["_id"])

    def _lotes_abertos(self, tarefas: dict[str, Tarefa], esperar: bool) -> set[str]:
        """Coleta os lotes enviados antes; devolve os custom_id ainda em andamento."""
        em_andamento: set[str] = set()
        for lote in list(self.db[LLM_BATCHES].find({"status": "enviado"})):
            situacao = self.fornecedor.situacao_lote(lote["_id"])
            status = situacao.status
            if status == "em_andamento" and esperar:
                status = self._esperar(lote["_id"])
            if status == "em_andamento":
                log.info(f"lote {lote['_id']} ainda em andamento ({situacao.detalhe})")
                em_andamento.update(lote["pedidos"])
                self.resultado.lotes_em_andamento.append(lote["_id"])
                continue
            self._coletar(lote, status, tarefas)
        return em_andamento

    def executar(
        self,
        piloto: bool = False,
        limite: int = 0,
        esperar: bool = True,
        sincrono: bool = False,
    ) -> Resultado:
        res = self.resultado
        ids = escopo(self.db, piloto, limite)
        if not ids:
            raise ValueError(
                "nenhuma espécie no escopo: rode `resolve` (e `ingest wikiaves`) antes"
            )

        # Espécies de lotes abertos entram também, para não descartar respostas já pagas.
        abertos = self.db[LLM_BATCHES].find({"status": "enviado"}, {"pedidos": 1})
        dos_lotes = {pid.split(":")[0] for lote in abertos for pid in lote["pedidos"]}
        tarefas = self.tarefas(sorted(set(ids) | dos_lotes))
        do_escopo = {pid: t for pid, t in tarefas.items() if t.species_id in set(ids)}
        res.pares = len(do_escopo)

        em_andamento = self._lotes_abertos(tarefas, esperar)

        cache = self._em_cache(do_escopo.values())
        res.cache = len(cache)
        sem_texto = [t for pid, t in do_escopo.items() if t.sem_texto and pid not in cache]
        self._gravar([extracao_sem_texto(t) for t in sem_texto])
        res.sem_texto = len(sem_texto)

        pendentes = [
            t
            for pid, t in do_escopo.items()
            if pid not in cache and pid not in em_andamento and not t.sem_texto
        ]
        res.em_lote = len(em_andamento & set(do_escopo))
        res.enviados = len(pendentes)
        if pendentes:
            if sincrono:
                log.info(f"{len(pendentes)} pedidos síncronos")
                pares = [(t, self.fornecedor.gerar(t.pedido)) for t in pendentes]
                self._processar(pares, fator=2.0)
            else:
                self._enviar(pendentes, tarefas, esperar)
        else:
            log.info("0 pendentes: nada a enviar ao LLM")

        res.linhas = self._relatorio(do_escopo)
        return res

    def _enviar(self, pendentes: list[Tarefa], tarefas: dict[str, Tarefa], esperar: bool) -> None:
        lote_id = self.fornecedor.enviar_lote([t.pedido for t in pendentes])
        lote = LoteLLM(
            id=lote_id,
            fornecedor=self.fornecedor.nome,
            pedidos=[t.pedido.id for t in pendentes],
            criado_em=_agora(),
        )
        self.db[LLM_BATCHES].insert_one(lote.to_mongo())
        self.resultado.lotes_enviados.append(lote_id)
        log.info(f"lote {lote_id} enviado com {len(pendentes)} pedidos")
        if not esperar:
            self.resultado.lotes_em_andamento.append(lote_id)
            self.resultado.em_lote += len(pendentes)
            return
        status = self._esperar(lote_id)
        self._coletar(lote.to_mongo(), status, tarefas)

    # -- relatório ------------------------------------------------------------

    def _relatorio(self, tarefas: dict[str, Tarefa]) -> list[str]:
        """reports/extract.tsv com o estado de cada par do escopo, e o resumo."""
        por_extracao = {t.extraction_id: t for t in tarefas.values()}
        docs = {
            d["_id"]: d
            for d in self.db[SPECIES_EXTRACTIONS].find({"_id": {"$in": list(por_extracao)}})
        }
        linhas_tsv = []
        por_prompt: dict[str, Counter] = {p.id: Counter() for p in self.prompts}
        ev: dict[str, Counter] = {p.id: Counter() for p in self.prompts}
        for eid, t in sorted(por_extracao.items()):
            d = docs.get(eid)
            contagem = por_prompt[t.prompt.id]
            if d is None or d.get("input_hash") != t.input_hash:
                status, n_valores, faltando, erro = "pendente", 0, [], ""
            else:
                v = d.get("validacao") or {}
                erro = v.get("erro") or ""
                status = (
                    "ok"
                    if v.get("ok")
                    else (SEM_TEXTO if erro == SEM_TEXTO else erro.split(":")[0])
                )
                n_valores = _n_valores(d.get("saida") or {})
                faltando = v.get("evidencias_nao_encontradas") or []
                ev[t.prompt.id]["total"] += len(evidencias(d.get("saida") or {}))
                ev[t.prompt.id]["faltando"] += len(faltando)
            contagem[status] += 1
            linhas_tsv.append([t.species_id, t.prompt.id, status, n_valores, len(faltando), erro])

        caminho = Path(self.settings.REPORTS_DIR) / "extract.tsv"
        caminho.parent.mkdir(parents=True, exist_ok=True)
        with open(caminho, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, delimiter="\t", lineterminator="\n")
            w.writerow(
                [
                    "species_id",
                    "prompt",
                    "status",
                    "n_valores",
                    "n_evidencias_nao_encontradas",
                    "erro",
                ]
            )
            w.writerows(linhas_tsv)

        res = self.resultado
        linhas = [
            f"extract: {res.pares} pares ({res.pares // max(len(self.prompts), 1)} espécies × "
            f"{len(self.prompts)} prompts); cache {res.cache}, sem texto {res.sem_texto}, "
            f"enviados {res.enviados}, em lote {res.em_lote}",
        ]
        for pid, c in por_prompt.items():
            com_texto = sum(c.values()) - c[SEM_TEXTO]
            validas = c["ok"]
            pct = 100 * validas / com_texto if com_texto else 0.0
            linhas.append(
                f"  {pid}: {validas} válidas de {com_texto} com texto ({pct:.1f}%), "
                f"{c[SEM_TEXTO]} sem texto, {c['invalido']} inválidas, {c['erro_api']} erro de API, "
                f"{c['pendente']} pendentes; evidências não encontradas: "
                f"{ev[pid]['faltando']} de {ev[pid]['total']}"
            )
        if res.lotes_enviados or res.lotes_coletados or res.lotes_em_andamento:
            linhas.append(
                f"  lotes: enviados {res.lotes_enviados}, coletados {res.lotes_coletados}, "
                f"em andamento {res.lotes_em_andamento}"
            )
        if res.retentativas or res.descartados:
            linhas.append(
                f"  retentativas {res.retentativas}, respostas descartadas {res.descartados}"
            )
        linhas.append(
            f"  tokens: entrada {res.tokens_entrada}, saída {res.tokens_saida}; "
            f"custo estimado US$ {res.custo_usd:.4f}"
        )
        linhas.append(f"  relatório: {caminho}")
        return linhas


def _n_valores(saida: dict[str, Any]) -> int:
    n = 0
    for valor in saida.values():
        if isinstance(valor, list):
            n += len(valor)
        elif valor is not None:
            n += 1
    return n


def executar(
    db: Database,
    fornecedor: Fornecedor,
    settings: Settings | None = None,
    **opcoes: Any,
) -> Resultado:
    return Extrator(db, fornecedor, settings).executar(**opcoes)
