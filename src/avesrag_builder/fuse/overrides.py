"""Correções manuais da ficha (curadoria): validação e aplicação.

Uma correção é `{caminho: valor}` guardada em `species_overrides`. O `fuse` a aplica
por cima de todas as fontes (`_prov.fonte = "manual"`), então ela sobrevive a toda
reconstrução. `valor: null` remove o campo da ficha. Só os caminhos de `EDITAVEIS`
podem ser corrigidos; o valor passa pelo vocabulário aqui, no `fuse` e na API.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from avesrag_builder.core.models import Foto, Prov
from avesrag_builder.core.regras_midia import RegrasMidia, regras_midia_padrao
from avesrag_builder.core.vocabulario import Vocabulario

Tipo = Literal["lista", "pares", "escolha", "numero", "texto_curto", "texto_longo", "fotos"]

# Atributos de lista do vocabulário (o mesmo nome no vocabulário e na ficha).
LISTAS = (
    "tamanho",
    "cores",
    "marcas",
    "cauda",
    "ambiente",
    "onde_estava",
    "o_que_fazia",
    "grupo",
    "atividade",
)
MASSA_MAXIMA_G = 200_000
DIETA_MAXIMO = 40
DESCRICAO_MAXIMO = 1500

EDITAVEIS: dict[str, Tipo] = {
    **{f"atributos.{nome}": "lista" for nome in LISTAS},
    "atributos.cores_por_parte": "pares",
    "atributos.bico_tipo": "escolha",
    "perfil.massa_g": "numero",
    "perfil.dieta": "texto_curto",
    "descricao": "texto_longo",
    "comportamento": "texto_longo",
    "voz": "texto_longo",
    "midia.fotos": "fotos",
}
TEXTOS = ("descricao", "comportamento", "voz")
FOTOS_MAXIMO = 6
CAMPOS_FOTO = ("url", "autor", "licenca", "licenca_url", "fonte", "link", "credito", "local")


def chave_de(caminho: str) -> str:
    """Chave do caminho em `species_overrides.campos`: o Mongo não aceita "." em chave de $set."""
    return caminho.replace(".", "/")


def caminho_de(chave: str) -> str:
    return chave.replace("/", ".")


class OverrideInvalido(ValueError):
    """O caminho não é editável ou o valor não passa na validação."""


def _unicos(valores: list[str]) -> list[str]:
    return list(dict.fromkeys(valores))


def _validar_fotos(caminho: str, valor: Any, regras: RegrasMidia) -> list[dict[str, Any]]:
    """Lista de fotos completas (o formato de `midia.foto`): a primeira é a principal.

    Cada foto precisa passar no modelo `Foto` (URLs https, crédito pronto) e ter licença
    aberta da lista do `regras_midia.yaml`; a URL da licença vem do arquivo, não do pedido."""
    if not isinstance(valor, list) or not valor:
        raise OverrideInvalido(f"{caminho}: use uma lista com ao menos uma foto")
    if len(valor) > FOTOS_MAXIMO:
        raise OverrideInvalido(f"{caminho}: no máximo {FOTOS_MAXIMO} fotos")
    por_nome = {lic.nome: lic for lic in regras.arquivo.licencas}
    saida: list[dict[str, Any]] = []
    for i, item in enumerate(valor, start=1):
        if not isinstance(item, Mapping) or set(item) - set(CAMPOS_FOTO):
            raise OverrideInvalido(f"{caminho}: a foto {i} tem campos que não existem")
        licenca = por_nome.get(item.get("licenca"))
        if licenca is None:
            raise OverrideInvalido(
                f"{caminho}: a licença da foto {i} deve ser uma de {sorted(por_nome)}"
            )
        foto = {**item, "licenca_url": licenca.url}
        try:
            validada = Foto.model_validate(foto).to_mongo()
        except ValueError as e:
            raise OverrideInvalido(f"{caminho}: foto {i} inválida ({e.errors()[0]['msg']})") from e
        if validada["link"] in {f["link"] for f in saida}:
            raise OverrideInvalido(f"{caminho}: a foto {i} se repete")
        saida.append(validada)
    return saida


def validar_valor(
    caminho: str, valor: Any, vocab: Vocabulario, midia: RegrasMidia | None = None
) -> Any:
    """O valor normalizado para gravar na ficha; `None` (remover o campo) passa direto."""
    tipo = EDITAVEIS.get(caminho)
    if tipo is None:
        raise OverrideInvalido(f"{caminho!r} não é um campo editável")
    if valor is None:
        if tipo == "fotos":
            raise OverrideInvalido(f"{caminho}: a ficha não fica sem foto; use outra foto")
        return None
    if tipo == "fotos":
        return _validar_fotos(caminho, valor, midia or regras_midia_padrao())
    if tipo == "lista":
        nome = caminho.removeprefix("atributos.")
        if not isinstance(valor, list) or not valor or not all(isinstance(v, str) for v in valor):
            raise OverrideInvalido(f"{caminho}: use uma lista de valores do vocabulário")
        for v in valor:
            if not vocab.contem(nome, v):
                raise OverrideInvalido(f"{caminho}: {v!r} não está no vocabulário")
        ordem = vocab.valores(nome)
        return sorted(_unicos(valor), key=ordem.index)
    if tipo == "pares":
        if not isinstance(valor, list) or not valor:
            raise OverrideInvalido(f"{caminho}: use uma lista de pares parte e cor")
        partes, cores = vocab.partes(), vocab.valores("cores")
        vistos, saida = set(), []
        for item in valor:
            if not isinstance(item, Mapping) or set(item) != {"parte", "cor"}:
                raise OverrideInvalido(f"{caminho}: cada item precisa de parte e cor")
            if item["parte"] not in partes or item["cor"] not in cores:
                raise OverrideInvalido(f"{caminho}: {dict(item)} fora do vocabulário")
            if item["parte"] in vistos:
                raise OverrideInvalido(f"{caminho}: a parte {item['parte']!r} se repete")
            vistos.add(item["parte"])
            saida.append({"parte": item["parte"], "cor": item["cor"]})
        return sorted(saida, key=lambda i: partes.index(i["parte"]))
    if tipo == "escolha":
        if not isinstance(valor, str) or not vocab.contem("bico_tipo", valor):
            raise OverrideInvalido(f"{caminho}: {valor!r} não é um tipo de bico do vocabulário")
        return valor
    if tipo == "numero":
        if isinstance(valor, bool) or not isinstance(valor, int | float):
            raise OverrideInvalido(f"{caminho}: use um número")
        if not 0 < valor <= MASSA_MAXIMA_G:
            raise OverrideInvalido(f"{caminho}: use um valor entre 0 e {MASSA_MAXIMA_G} g")
        return round(float(valor), 1)
    limite = DIETA_MAXIMO if tipo == "texto_curto" else DESCRICAO_MAXIMO
    if not isinstance(valor, str) or not valor.strip():
        raise OverrideInvalido(f"{caminho}: o texto não pode ser vazio")
    texto = " ".join(valor.split()) if tipo == "texto_curto" else valor.strip()
    if len(texto) > limite:
        raise OverrideInvalido(f"{caminho}: no máximo {limite} caracteres")
    return texto


def _prov_manual(entrada: Mapping[str, Any]) -> Prov:
    em = entrada.get("em")
    dia = em.strftime("%Y-%m-%d") if isinstance(em, datetime) else str(em or "")[:10]
    return Prov(fonte="manual", metodo="curadoria", ref=f"override@{dia}")


def _definir(doc: dict[str, Any], caminho: str, valor: Any) -> None:
    partes = caminho.split(".")
    if len(partes) == 1:
        doc[caminho] = valor
        return
    bloco = dict(doc.get(partes[0]) or {})
    bloco[partes[1]] = valor
    doc[partes[0]] = bloco


def _remover(doc: dict[str, Any], caminho: str) -> None:
    partes = caminho.split(".")
    if len(partes) == 1:
        doc.pop(caminho, None)
        return
    bloco = dict(doc.get(partes[0]) or {})
    bloco.pop(partes[1], None)
    # `atributos` fica como está (o modelo aceita vazio); `perfil` vazio sai da ficha.
    doc[partes[0]] = bloco or (None if partes[0] == "perfil" else {})


@dataclass
class ResultadoOverrides:
    aplicados: list[str]
    erros: list[tuple[str, str]]  # (caminho, motivo): correção inválida, ignorada


def aplicar(
    doc: dict[str, Any],
    prov: dict[str, Prov],
    overrides: Mapping[str, Mapping[str, Any]],
    vocab: Vocabulario,
    midia: RegrasMidia | None = None,
) -> ResultadoOverrides:
    """Aplica as correções em `doc` e em `prov` (no lugar). Correção inválida é ignorada."""
    res = ResultadoOverrides([], [])
    for caminho in sorted(overrides):
        entrada = overrides[caminho]
        try:
            valor = validar_valor(caminho, entrada.get("valor"), vocab, midia)
        except OverrideInvalido as e:
            res.erros.append((caminho, str(e)))
            continue
        if valor is None:
            _remover(doc, caminho)
            prov.pop(caminho, None)
        elif caminho == "midia.fotos":
            marca = _prov_manual(entrada)
            _definir(doc, "midia.foto", valor[0])
            prov["midia.foto"] = marca
            if len(valor) > 1:  # a galeria só existe com 2 ou mais fotos
                _definir(doc, "midia.fotos", valor)
                prov["midia.fotos"] = marca
            else:
                _remover(doc, "midia.fotos")
                prov.pop("midia.fotos", None)
        else:
            _definir(doc, caminho, valor)
            prov[caminho] = _prov_manual(entrada)
        res.aplicados.append(caminho)
    return res
