"""Modelos Pydantic da v2: a fonte única do schema das collections do builder.

Toda escrita no MongoDB passa por estes modelos (`to_mongo()`), e os testes
validam contra eles. Os valores categóricos (cores, ambiente…) são `list[str]`
aqui e são conferidos contra o `vocabulario.yaml` na etapa `validate`, para
não manter as listas em dois lugares.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import UTC, datetime
from typing import Annotated, Any, ClassVar, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationInfo,
    field_validator,
    model_validator,
)

SCHEMA_VERSION = "2.0"
EMBEDDING_DIM = 3072  # text-embedding-3-large

FonteChave = Literal["cbro", "avonet", "birdbase", "ebird"]
# exato: mesmo nome; ponte: pela correspondência do AVONET (eBird);
# genero: mesmo epíteto e família equivalente, com outro gênero (eBird).
MatchTipo = Literal["exato", "ponte", "genero", "sem_match"]
DqStatus = Literal["apta", "incompleta", "bloqueada"]
Dominio = Literal["aparencia", "comportamento_ambiente", "voz_habitos"]

SpeciesId = Annotated[str, StringConstraints(pattern=r"^sp_[a-z0-9]+(_[a-z0-9]+)*$")]
TextoNaoVazio = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------


def slug_species_id(nome_cientifico: str) -> str:
    """'Pitangus sulphuratus' -> 'sp_pitangus_sulphuratus'."""
    texto = unicodedata.normalize("NFKD", nome_cientifico)
    texto = "".join(c for c in texto if not unicodedata.combining(c)).lower()
    slug = re.sub(r"[^a-z0-9]+", "_", texto).strip("_")
    if not slug:
        raise ValueError(f"nome científico sem caracteres válidos: {nome_cientifico!r}")
    return f"sp_{slug}"


def compute_source_hash(dados: dict[str, Any]) -> str:
    """sha256 do JSON canônico (chaves ordenadas), independente da ordem de inserção."""
    canonico = json.dumps(
        dados, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str
    )
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def _agora() -> datetime:
    return datetime.now(UTC)


def _sem_vazios(valor: Any, caminho: str = "") -> None:
    """Levanta ValueError se houver "" ou lista vazia em qualquer nível."""
    if isinstance(valor, str) and not valor.strip():
        raise ValueError(f"{caminho or 'valor'}: string vazia (deixe o campo de fora)")
    if isinstance(valor, list):
        if not valor:
            raise ValueError(f"{caminho or 'valor'}: lista vazia (deixe o campo de fora)")
        for i, item in enumerate(valor):
            _sem_vazios(item, f"{caminho}[{i}]")
    if isinstance(valor, dict):
        for chave, item in valor.items():
            _sem_vazios(item, f"{caminho}.{chave}" if caminho else str(chave))


class MongoModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    # Species omite campos sem valor; as demais collections guardam null explícito.
    EXCLUDE_NONE: ClassVar[bool] = False

    def to_mongo(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_none=self.EXCLUDE_NONE)

    @classmethod
    def from_mongo(cls, doc: dict[str, Any]) -> Self:
        """Valida um doc lido do Mongo; descarta o `_id` (ObjectId) se o modelo não o declara."""
        if "_id" in doc and not any(f.alias == "_id" for f in cls.model_fields.values()):
            doc = {k: v for k, v in doc.items() if k != "_id"}
        return cls.model_validate(doc)


# ---------------------------------------------------------------------------
# Bruto (raw_*)
# ---------------------------------------------------------------------------


class RawEnvelope(MongoModel):
    """Formato comum das collections raw_*: o dado da fonte sem alteração."""

    id: TextoNaoVazio = Field(alias="_id")
    dados: dict[str, Any]
    ingerido_em: datetime
    source_hash: str

    @classmethod
    def build(cls, id: str, dados: dict[str, Any], agora: datetime | None = None) -> RawEnvelope:
        return cls(
            id=id,
            dados=dados,
            ingerido_em=agora or _agora(),
            source_hash=compute_source_hash(dados),
        )


# ---------------------------------------------------------------------------
# Identidade (species_registry)
# ---------------------------------------------------------------------------


class Chaves(MongoModel):
    wikiaves: TextoNaoVazio
    cbro: str | None = None
    avonet: str | None = None
    birdbase: str | None = None
    ebird: str | None = None


class SpeciesRegistry(MongoModel):
    """Um doc por espécie do WikiAves. O `_id` é o ObjectId do Mongo (interno);
    as outras collections referenciam a espécie pelo `species_id` (slug, índice único)."""

    species_id: SpeciesId
    nome_cientifico: TextoNaoVazio
    nome_comum: str | None = None
    chaves: Chaves
    match: dict[FonteChave, MatchTipo] = Field(default_factory=dict)
    criado_em: datetime
    atualizado_em: datetime | None = None

    @model_validator(mode="after")
    def _consistencia(self) -> SpeciesRegistry:
        esperado = slug_species_id(self.nome_cientifico)
        if self.species_id != esperado:
            raise ValueError(
                f"species_id {self.species_id!r} difere do slug do nome científico ({esperado!r})"
            )
        for fonte, tipo in self.match.items():
            chave = getattr(self.chaves, fonte)
            if (chave is None) != (tipo == "sem_match"):
                raise ValueError(f"match.{fonte}={tipo!r} incoerente com chaves.{fonte}={chave!r}")
        return self


# ---------------------------------------------------------------------------
# Builder (species_extractions)
# ---------------------------------------------------------------------------


class Validacao(MongoModel):
    # ok mede só o schema; evidências não encontradas não invalidam a resposta
    # (quem descarta o valor é a fusão). erro: "sem_texto", "invalido: ..." ou "erro_api: ...".
    ok: bool
    evidencias_nao_encontradas: list[str] = Field(default_factory=list)
    erro: str | None = None


class Extraction(MongoModel):
    id: TextoNaoVazio = Field(alias="_id")
    species_id: SpeciesId
    prompt: TextoNaoVazio
    versao: TextoNaoVazio
    modelo: TextoNaoVazio
    input_hash: TextoNaoVazio
    saida: dict[str, Any]
    validacao: Validacao
    criado_em: datetime

    @model_validator(mode="after")
    def _id_composto(self) -> Extraction:
        if self.id != f"{self.species_id}:{self.prompt}":
            raise ValueError(f"_id deve ser '{self.species_id}:{self.prompt}'")
        return self


LoteStatus = Literal["enviado", "coletado", "falhou"]


class LoteLLM(MongoModel):
    """Um lote da API de batch (`llm_batches`), gravado antes de esperar, para retomar."""

    id: TextoNaoVazio = Field(alias="_id")  # id do lote no fornecedor
    fornecedor: TextoNaoVazio
    pedidos: list[TextoNaoVazio] = Field(min_length=1)  # custom_id de cada pedido
    status: LoteStatus = "enviado"
    criado_em: datetime
    atualizado_em: datetime | None = None
    erro: str | None = None


# ---------------------------------------------------------------------------
# Canônica (species)
# ---------------------------------------------------------------------------


class Nomes(MongoModel):
    pt: list[TextoNaoVazio] = Field(min_length=1)
    en: list[TextoNaoVazio] | None = None


class Taxonomia(MongoModel):
    # Completude e fonte única são checadas no `validate` (espécie bloqueada),
    # não aqui: a ficha precisa poder ser gravada para receber o dq_status.
    ordem: str | None = None
    familia: str | None = None
    genero: str | None = None


class CorPorParte(MongoModel):
    parte: TextoNaoVazio
    cor: TextoNaoVazio


class Atributos(MongoModel):
    tamanho: list[str] | None = None
    comprimento_cm: float | None = Field(default=None, gt=0)
    cores: list[str] | None = None
    cores_por_parte: list[CorPorParte] | None = None
    marcas: list[str] | None = None
    bico_tipo: str | None = None
    cauda: list[str] | None = None
    ambiente: list[str] | None = None
    onde_estava: list[str] | None = None
    o_que_fazia: list[str] | None = None
    grupo: list[str] | None = None
    atividade: list[str] | None = None


class Ocorrencia(MongoModel):
    biomas: list[str] | None = None
    n_municipios: int | None = Field(default=None, ge=0)


class Midia(MongoModel):
    foto: str | None = None
    url_wikiaves: str | None = None


class Prov(MongoModel):
    fonte: TextoNaoVazio
    metodo: str | None = None
    ref: str | None = None


class Meta(MongoModel):
    schema_version: str = SCHEMA_VERSION
    built_at: datetime
    dq_status: DqStatus | None = None


class Species(MongoModel):
    EXCLUDE_NONE: ClassVar[bool] = True

    species_id: SpeciesId  # mesmo do registry; `_id` é o ObjectId do Mongo
    nome_cientifico: TextoNaoVazio
    nomes: Nomes
    taxonomia: Taxonomia = Field(default_factory=Taxonomia)
    status_ocorrencia: str | None = None
    iucn: str | None = None
    atributos: Atributos = Field(default_factory=Atributos)
    ocorrencia: Ocorrencia | None = None
    midia: Midia | None = None
    prov: dict[str, Prov] = Field(default_factory=dict, alias="_prov")
    meta: Meta = Field(alias="_meta")

    @model_validator(mode="after")
    def _sem_campos_vazios(self) -> Species:
        # Validação 4 da Especificação: campo sem valor fica fora do documento.
        _sem_vazios(self.model_dump(by_alias=True, exclude_none=True, mode="json"))
        return self


# ---------------------------------------------------------------------------
# Busca (species_retrieval_docs)
# ---------------------------------------------------------------------------


class RetrievalDoc(MongoModel):
    id: TextoNaoVazio = Field(alias="_id")
    species_id: SpeciesId
    dominio: Dominio
    texto: TextoNaoVazio
    embedding: list[float]
    filtros: dict[str, Any] = Field(default_factory=dict)
    built_at: datetime

    @field_validator("embedding")
    @classmethod
    def _dimensao(cls, v: list[float], info: ValidationInfo) -> list[float]:
        dim = (info.context or {}).get("embedding_dim", EMBEDDING_DIM)
        if len(v) != dim:
            raise ValueError(f"embedding com {len(v)} posições; esperado {dim}")
        return v

    @model_validator(mode="after")
    def _id_composto(self) -> RetrievalDoc:
        if self.id != f"{self.species_id}:{self.dominio}":
            raise ValueError(f"_id deve ser '{self.species_id}:{self.dominio}'")
        return self
