"""Etapa 5 (`validate`): species -> `_meta.dq_status` + relatório.

Classifica cada ficha do escopo em `apta`, `incompleta` ou `bloqueada`
(`validate/regras.py`) e grava o `dq_status` só quando ele muda. O texto de
aparência do `b03`, exigido para `apta`, é lido de `species_extractions`,
porque não fica na ficha.
"""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pymongo import UpdateOne
from pymongo.database import Database

from avesrag_builder.core.logging import get_logger
from avesrag_builder.core.models import FonteChave
from avesrag_builder.core.regras_fusao import TEXTOS_B03, RegrasFusao, regras_fusao_padrao
from avesrag_builder.core.settings import Settings, get_settings
from avesrag_builder.core.vocabulario import Vocabulario, vocabulario_padrao
from avesrag_builder.db.collections import SPECIES, SPECIES_EXTRACTIONS, SPECIES_REGISTRY
from avesrag_builder.fuse.regras import B03
from avesrag_builder.fuse.species import escopo
from avesrag_builder.validate import regras as v

log = get_logger(__name__)

LOTE = 500
FONTES: tuple[FonteChave, ...] = ("cbro", "avonet", "birdbase", "ebird")


@dataclass
class ResultadoValidate:
    escopo: int = 0
    sem_ficha: list[str] = field(default_factory=list)
    status: Counter[str] = field(default_factory=Counter)
    gravados: int = 0
    inalterados: int = 0
    faltas: Counter[str] = field(default_factory=Counter)
    erros: Counter[str] = field(default_factory=Counter)
    cobertura: Counter[str] = field(default_factory=Counter)
    sem_match: Counter[str] = field(default_factory=Counter)
    relatorio: Path | None = None

    @property
    def avaliadas(self) -> int:
        return sum(self.status.values())

    @property
    def pct_aptas(self) -> float:
        return 100 * self.status["apta"] / self.avaliadas if self.avaliadas else 0.0

    def linhas(self) -> list[str]:
        n = self.avaliadas
        out = [
            f"validate: {n} fichas de {self.escopo} espécies no escopo; "
            f"{self.gravados} gravados, {self.inalterados} inalterados",
            f"  apta {self.status['apta']} ({self.pct_aptas:.1f}%), "
            f"incompleta {self.status['incompleta']}, bloqueada {self.status['bloqueada']}",
        ]
        if self.sem_ficha:
            out.append(f"  {len(self.sem_ficha)} espécies do escopo sem ficha: rode `fuse`")
        if self.faltas:
            itens = ", ".join(f"{k} {q}" for k, q in self.faltas.most_common())
            out.append(f"  o que falta nas incompletas: {itens}")
        if self.erros:
            out.append("  erros das bloqueadas:")
            out += [f"    {k}: {q}" for k, q in self.erros.most_common(10)]
        out.append("  cobertura dos atributos:")
        for campo, qtd in sorted(self.cobertura.items()):
            out.append(f"    {campo}: {qtd} ({100 * qtd / n if n else 0:.1f}%)")
        sem = ", ".join(f"{f} {self.sem_match[f]}" for f in FONTES)
        out.append(f"  sem casamento no registry: {sem}")
        if self.relatorio:
            out.append(f"  relatório: {self.relatorio}")
        return out


def textos_b03(db: Database, ids: list[str]) -> dict[str, set[str]]:
    """Textos do b03 presentes, por espécie (só extrações válidas)."""
    out: dict[str, set[str]] = {}
    for doc in db[SPECIES_EXTRACTIONS].find(
        {"species_id": {"$in": ids}, "prompt": B03, "validacao.ok": True}
    ):
        saida = doc.get("saida") or {}
        out[doc["species_id"]] = {t for t in TEXTOS_B03 if (saida.get(t) or "").strip()}
    return out


def _chave_erro(erro: str) -> str:
    """Agrupa erros parecidos no resumo: o campo, sem o valor."""
    return erro.split(":")[0]


def executar(
    db: Database,
    piloto: bool = False,
    settings: Settings | None = None,
    vocab: Vocabulario | None = None,
    regras: RegrasFusao | None = None,
) -> ResultadoValidate:
    settings = settings or get_settings()
    vocab = vocab or vocabulario_padrao()
    regras = regras or regras_fusao_padrao()

    ids = escopo(db, piloto)
    if not ids:
        raise ValueError("nenhuma espécie no escopo: rode `resolve` antes")
    res = ResultadoValidate(escopo=len(ids))

    registros = list(db[SPECIES_REGISTRY].find({}, {"species_id": 1, "match": 1}))
    registrados = {d["species_id"] for d in registros}
    no_escopo = set(ids)
    for reg in registros:
        if reg["species_id"] in no_escopo:
            for fonte in FONTES:
                res.sem_match[fonte] += (reg.get("match") or {}).get(fonte) == "sem_match"

    repetidos = {
        sid
        for sid, q in Counter(
            d["species_id"] for d in db[SPECIES].find({}, {"species_id": 1})
        ).items()
        if q > 1
    }
    textos = textos_b03(db, ids)
    fichas = {d["species_id"]: d for d in db[SPECIES].find({"species_id": {"$in": ids}})}
    res.sem_ficha = sorted(no_escopo - set(fichas))

    linhas: list[list[Any]] = []
    ops: list[UpdateOne] = []
    for sid in sorted(fichas):
        doc = fichas[sid]
        erros = v.erros(doc, vocab, regras, registrados)
        if sid in repetidos:
            erros.append("species_id: repetido em species")
        faltas = [] if erros else v.faltas(doc, regras, textos.get(sid, set()))
        status = v.classificar(erros, faltas)

        res.status[status] += 1
        res.faltas.update(f.split(" ")[0] for f in faltas)
        res.erros.update(_chave_erro(e) for e in erros)
        for campo in v.campos_preenchidos(doc):
            if campo.startswith("atributos."):
                res.cobertura[campo.removeprefix("atributos.")] += 1
        linhas.append([sid, status, "; ".join(faltas), "; ".join(erros)])

        if (doc.get("_meta") or {}).get("dq_status") == status:
            res.inalterados += 1
        else:
            ops.append(UpdateOne({"_id": doc["_id"]}, {"$set": {"_meta.dq_status": status}}))
            res.gravados += 1

    for i in range(0, len(ops), LOTE):
        db[SPECIES].bulk_write(ops[i : i + LOTE], ordered=False)

    settings.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    res.relatorio = settings.REPORTS_DIR / "validate.tsv"
    with res.relatorio.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["species_id", "dq_status", "faltas", "erros"])
        w.writerows(linhas)
        w.writerows([sid, "sem_ficha", "", "rode `fuse`"] for sid in res.sem_ficha)

    log.info(f"validate: {res.gravados} gravados, {res.inalterados} inalterados")
    return res
