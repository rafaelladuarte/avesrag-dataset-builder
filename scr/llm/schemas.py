from typing import Optional

from pydantic import BaseModel, Field


class LLMAudit(BaseModel):
    prompt_name: str
    prompt_version: str
    model_name: str
    timestamp: str


class P01Morfologia(BaseModel):
    colors_raw: list[str] = Field(default_factory=list)
    body_parts_raw: list[str] = Field(default_factory=list)
    bill_description_raw: list[str] = Field(default_factory=list)
    wing_description_raw: list[str] = Field(default_factory=list)
    tail_description_raw: list[str] = Field(default_factory=list)
    size_description_raw: list[str] = Field(default_factory=list)
    measurements_raw: list[str] = Field(default_factory=list)
    sexual_dimorphism_raw: list[str] = Field(default_factory=list)
    juvenile_description_raw: list[str] = Field(default_factory=list)
    plumage_description_raw: list[str] = Field(default_factory=list)
    distinctive_features_raw: list[str] = Field(default_factory=list)
    _audit: Optional[LLMAudit] = None


class P02Alimentacao(BaseModel):
    food_items_raw: list[str] = Field(default_factory=list)
    feeding_behavior_raw: list[str] = Field(default_factory=list)
    feeding_locations_raw: list[str] = Field(default_factory=list)
    _audit: Optional[LLMAudit] = None


class P03Habitos(BaseModel):
    habitats_raw: list[str] = Field(default_factory=list)
    activity_raw: list[str] = Field(default_factory=list)
    social_behavior_raw: list[str] = Field(default_factory=list)
    flight_behavior_raw: list[str] = Field(default_factory=list)
    vocalization_raw: list[str] = Field(default_factory=list)
    _audit: Optional[LLMAudit] = None


class P04Reproducao(BaseModel):
    nest_raw: list[str] = Field(default_factory=list)
    courtship_raw: list[str] = Field(default_factory=list)
    clutch_raw: list[str] = Field(default_factory=list)
    incubation_raw: list[str] = Field(default_factory=list)
    fledging_raw: list[str] = Field(default_factory=list)
    _audit: Optional[LLMAudit] = None


class SpeciesRaw(BaseModel):
    morfologia: P01Morfologia
    alimentacao: Optional[P02Alimentacao] = None
    habitos: Optional[P03Habitos] = None
    reproducao: Optional[P04Reproducao] = None


class P05NormalizacaoSemantica(BaseModel):
    normalized_data: dict[str, list[str]] = Field(default_factory=dict)
    _audit: Optional[LLMAudit] = None


class Measurement(BaseModel):
    value: Optional[float] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    unit: Optional[str] = None


class P06PadronizacaoMedidas(BaseModel):
    measurements: list[Measurement] = Field(default_factory=list)
    _audit: Optional[LLMAudit] = None


class P07PadronizacaoTaxonomica(BaseModel):
    reino: Optional[str] = None
    filo: Optional[str] = None
    classe: Optional[str] = None
    ordem: Optional[str] = None
    familia: Optional[str] = None
    genero: Optional[str] = None
    especie: Optional[str] = None
    _audit: Optional[LLMAudit] = None


class P08EstruturaCanonica(BaseModel):
    identificacao: Optional[str] = None
    descricao_curta: Optional[str] = None
    caracteristicas_diagnosticas: list[str] = Field(default_factory=list)
    _audit: Optional[LLMAudit] = None
