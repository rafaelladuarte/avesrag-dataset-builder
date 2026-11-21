"""CLI `avesrag-builder`: um comando por etapa do pipeline.

Cada etapa lê só das anteriores, pode ser rodada sozinha e é idempotente.
A ingestão fica fora do `run` porque o scraping do WikiAves é lento.
"""

from enum import Enum

import typer

from avesrag_builder import __version__
from avesrag_builder.core.logging import set_level

app = typer.Typer(
    name="avesrag-builder",
    help="Constrói a base de espécies do AvesRAG a partir das fontes.",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode=None,
)

OPCAO_PILOTO = typer.Option(
    False, "--piloto", help="Só as espécies do município do piloto (PILOTO_MUNICIPIO_IBGE)."
)


class Fonte(str, Enum):
    wikiaves = "wikiaves"
    avonet = "avonet"
    birdbase = "birdbase"
    cbro = "cbro"
    ebird = "ebird"
    ibge = "ibge"


def nao_implementado(comando: str, marco: str) -> None:
    typer.echo(f"`{comando}` ainda não foi implementado: chega no Marco {marco}.", err=True)
    raise typer.Exit(code=2)


def _versao(valor: bool) -> None:
    if valor:
        typer.echo(f"avesrag-builder {__version__}")
        raise typer.Exit()


@app.callback()
def principal(
    log_level: str = typer.Option("INFO", "--log-level", help="DEBUG, INFO, WARNING ou ERROR."),
    versao: bool = typer.Option(
        False, "--version", callback=_versao, is_eager=True, help="Mostra a versão e sai."
    ),
) -> None:
    try:
        set_level(log_level)
    except ValueError as e:
        raise typer.BadParameter(str(e), param_hint="--log-level") from e


@app.command()
def ingest(fonte: Fonte = typer.Argument(..., help="Fonte a ingerir.")) -> None:
    """[etapa 1] Lê sites, APIs e planilhas e grava em raw_<fonte> (upsert pelo id da fonte)."""
    nao_implementado(f"ingest {fonte.value}", "2")


@app.command()
def resolve() -> None:
    """[etapa 2] raw_* -> species_registry: um species_id estável por espécie do WikiAves."""
    nao_implementado("resolve", "3")


@app.command()
def extract(piloto: bool = OPCAO_PILOTO) -> None:
    """[etapa 3] raw_wikiaves + species_registry -> species_extractions (LLM em batch)."""
    nao_implementado("extract", "4")


@app.command()
def fuse(piloto: bool = OPCAO_PILOTO) -> None:
    """[etapa 4] registry, extractions e raw_* -> species e species_occurrence (sem chamadas externas)."""
    nao_implementado("fuse", "5")


@app.command()
def validate(piloto: bool = OPCAO_PILOTO) -> None:
    """[etapa 5] species -> _meta.dq_status (apta, incompleta, bloqueada) e relatório em reports/."""
    nao_implementado("validate", "5")


@app.command()
def docs(piloto: bool = OPCAO_PILOTO) -> None:
    """[etapa 6] species aptas -> species_retrieval_docs (3 documentos com embedding por espécie)."""
    nao_implementado("docs", "6")


@app.command()
def index() -> None:
    """[etapa 7] Cria os índices $vectorSearch e $search em species_retrieval_docs."""
    nao_implementado("index", "6")


@app.command()
def run(piloto: bool = OPCAO_PILOTO) -> None:
    """Executa as etapas 2 a 7 em sequência (resolve, extract, fuse, validate, docs, index)."""
    nao_implementado("run", "6")


if __name__ == "__main__":
    app()
