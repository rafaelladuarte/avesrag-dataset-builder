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
    birdalbum = "birdalbum"


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
def ingest(
    fonte: Fonte = typer.Argument(..., help="Fonte a ingerir."),
    piloto: bool = typer.Option(
        False, "--piloto", help="ebird e wikiaves: só o município do piloto e as suas espécies."
    ),
    refazer: bool = typer.Option(
        False,
        "--refazer",
        help="ebird e wikiaves: baixa de novo o que já está em raw_ebird ou raw_wikiaves.",
    ),
    limite: int = typer.Option(
        0, "--limite", min=0, help="wikiaves: no máximo N páginas nesta execução (0 = sem limite)."
    ),
) -> None:
    """[etapa 1] Lê sites, APIs e planilhas e grava em raw_<fonte> (upsert pelo id da fonte)."""
    import inspect
    from importlib import import_module

    from bson.errors import InvalidDocument
    from pymongo.errors import PyMongoError
    from requests import RequestException

    from avesrag_builder.core.settings import MissingSettingError
    from avesrag_builder.db.connection import get_db
    from avesrag_builder.ingest.base import IdDuplicado

    modulo = import_module(f"avesrag_builder.ingest.{fonte.value}")
    ingerir = getattr(modulo, "ingerir", None)
    if ingerir is None:
        nao_implementado(f"ingest {fonte.value}", "2")

    opcoes = {"piloto": piloto, "refazer": refazer, "limite": limite}
    aceitas = inspect.signature(ingerir).parameters
    kwargs = {k: v for k, v in opcoes.items() if k in aceitas}
    ignoradas = [f"--{k}" for k, v in opcoes.items() if v and k not in aceitas]
    if ignoradas:
        raise typer.BadParameter(f"{', '.join(ignoradas)} não se aplica a {fonte.value}")

    try:
        resultados = ingerir(get_db(), **kwargs)
    except (MissingSettingError, IdDuplicado, PyMongoError, InvalidDocument, RequestException) as e:
        typer.echo(f"Falhou: {e}", err=True)
        raise typer.Exit(code=1) from e

    for resultado in resultados:
        typer.echo(resultado.resumo())
        for erro in resultado.erros[:20]:
            typer.echo(f"  erro: {erro}", err=True)
    if any(r.erros for r in resultados):
        raise typer.Exit(code=1)


@app.command()
def resolve() -> None:
    """[etapa 2] raw_* -> species_registry: um species_id estável por espécie do WikiAves."""
    from pymongo.errors import PyMongoError

    from avesrag_builder.core.settings import MissingSettingError
    from avesrag_builder.db.connection import get_db
    from avesrag_builder.resolve.registry import executar

    try:
        resultado, cobertura = executar(get_db())
    except (MissingSettingError, PyMongoError, ValueError) as e:
        typer.echo(f"Falhou: {e}", err=True)
        raise typer.Exit(code=1) from e
    typer.echo(resultado.resumo())
    for linha in cobertura.linhas():
        typer.echo(linha)


@app.command()
def extract(
    piloto: bool = OPCAO_PILOTO,
    limite: int = typer.Option(
        0, "--limite", min=0, help="No máximo N espécies (0 = sem limite); para calibrar."
    ),
    sem_esperar: bool = typer.Option(
        False, "--sem-esperar", help="Só envia o lote; a próxima execução coleta."
    ),
    sincrono: bool = typer.Option(
        False, "--sincrono", help="Chamadas diretas, sem a API de batch (custa o dobro)."
    ),
) -> None:
    """[etapa 3] raw_wikiaves + species_registry -> species_extractions (LLM em batch)."""
    from pymongo.errors import PyMongoError

    from avesrag_builder.core.settings import MissingSettingError, get_settings
    from avesrag_builder.core.vocabulario import VocabularioInvalido
    from avesrag_builder.db.connection import get_db
    from avesrag_builder.extract.pipeline import executar
    from avesrag_builder.llm import fornecedor
    from avesrag_builder.llm.base import ErroFornecedor

    try:
        settings = get_settings()
        llm = fornecedor(settings)  # cobra a chave antes de conectar ao banco
        resultado = executar(
            get_db(),
            llm,
            settings,
            piloto=piloto,
            limite=limite,
            esperar=not sem_esperar,
            sincrono=sincrono,
        )
    except (
        MissingSettingError,
        VocabularioInvalido,
        ErroFornecedor,
        PyMongoError,
        ValueError,
    ) as e:
        typer.echo(f"Falhou: {e}", err=True)
        raise typer.Exit(code=1) from e
    for linha in resultado.linhas:
        typer.echo(linha)


@app.command()
def fuse(piloto: bool = OPCAO_PILOTO) -> None:
    """[etapa 4] registry, extractions e raw_* -> species e species_occurrence (sem chamadas externas)."""
    from pymongo.errors import PyMongoError

    from avesrag_builder.core.vocabulario import VocabularioInvalido
    from avesrag_builder.db.connection import get_db
    from avesrag_builder.fuse.species import executar

    try:
        resultado = executar(get_db(), piloto=piloto)
    except (VocabularioInvalido, PyMongoError, ValueError) as e:
        typer.echo(f"Falhou: {e}", err=True)
        raise typer.Exit(code=1) from e
    for linha in resultado.linhas():
        typer.echo(linha)
    if resultado.erros:
        raise typer.Exit(code=1)


@app.command()
def validate(piloto: bool = OPCAO_PILOTO) -> None:
    """[etapa 5] species -> _meta.dq_status (apta, incompleta, bloqueada) e relatório em reports/."""
    from pymongo.errors import PyMongoError

    from avesrag_builder.core.vocabulario import VocabularioInvalido
    from avesrag_builder.db.connection import get_db
    from avesrag_builder.validate.pipeline import executar

    try:
        resultado = executar(get_db(), piloto=piloto)
    except (VocabularioInvalido, PyMongoError, ValueError) as e:
        typer.echo(f"Falhou: {e}", err=True)
        raise typer.Exit(code=1) from e
    for linha in resultado.linhas():
        typer.echo(linha)


@app.command()
def docs(piloto: bool = OPCAO_PILOTO) -> None:
    """[etapa 6] species aptas -> species_retrieval_docs (até 3 documentos com embedding por espécie)."""
    from pymongo.errors import PyMongoError

    from avesrag_builder.core.settings import MissingSettingError, get_settings
    from avesrag_builder.db.connection import get_db
    from avesrag_builder.docs.pipeline import executar
    from avesrag_builder.llm import embedder
    from avesrag_builder.llm.base import ErroFornecedor

    settings = get_settings()
    try:
        resultado = executar(get_db(), lambda: embedder(settings), piloto=piloto, settings=settings)
    except (MissingSettingError, ErroFornecedor, PyMongoError, ValueError) as e:
        typer.echo(f"Falhou: {e}", err=True)
        raise typer.Exit(code=1) from e
    for linha in resultado.linhas():
        typer.echo(linha)


@app.command()
def index(
    verificar: bool = typer.Option(
        False,
        "--verificar",
        help="Só confere se o MongoDB aceita índices de busca (collection temporária).",
    ),
    fumaca: bool = typer.Option(
        False,
        "--fumaca",
        help="Depois dos índices, roda as consultas de config/consultas_fumaca.yaml (pago: embeddings).",
    ),
) -> None:
    """[etapa 7] Cria os índices $vectorSearch e $search em species_retrieval_docs."""
    from pymongo.errors import PyMongoError

    from avesrag_builder.db.busca import BuscaIndisponivel, verificar_busca
    from avesrag_builder.db.connection import get_db

    if verificar:
        typer.echo("Verificando $vectorSearch e $search no MongoDB…")
        try:
            resultado = verificar_busca(get_db())
        except (BuscaIndisponivel, PyMongoError) as e:
            typer.echo(f"Falhou: {e}", err=True)
            raise typer.Exit(code=1) from e
        typer.echo(
            f"OK: MongoDB {resultado.versao_servidor} aceita índices $vectorSearch e $search."
        )
        return

    from avesrag_builder.core.settings import MissingSettingError, get_settings
    from avesrag_builder.core.vocabulario import VocabularioInvalido
    from avesrag_builder.docs import busca, indices
    from avesrag_builder.llm import embedder
    from avesrag_builder.llm.base import ErroFornecedor

    settings = get_settings()
    try:
        db = get_db()
        for linha in indices.garantir(db).linhas():
            typer.echo(linha)
        if not fumaca:
            return
        consultas = busca.carregar_consultas(settings.CONFIG_DIR / "consultas_fumaca.yaml")
        resultado = busca.fumaca(
            db,
            embedder(settings),
            settings.EMBEDDING_MODEL,
            consultas,
            relatorio=settings.REPORTS_DIR / "fumaca.tsv",
        )
    except (
        BuscaIndisponivel,
        MissingSettingError,
        VocabularioInvalido,
        ErroFornecedor,
        PyMongoError,
    ) as e:
        typer.echo(f"Falhou: {e}", err=True)
        raise typer.Exit(code=1) from e
    for linha in resultado.linhas():
        typer.echo(linha)
    if resultado.falhas:
        raise typer.Exit(code=1)


@app.command()
def status(piloto: bool = OPCAO_PILOTO) -> None:
    """Mostra o estado de cada etapa e o próximo passo (só lê o banco; sem chave de API)."""
    from pymongo.errors import PyMongoError

    from avesrag_builder.core.settings import get_settings
    from avesrag_builder.db.connection import get_db
    from avesrag_builder.status import coletar, linhas

    try:
        estado = coletar(get_db(), piloto, get_settings().PILOTO_MUNICIPIO_IBGE)
    except PyMongoError as e:
        typer.echo(f"Falhou: {e}", err=True)
        raise typer.Exit(code=1) from e
    for linha in linhas(estado):
        typer.echo(linha)


@app.command()
def run(
    piloto: bool = OPCAO_PILOTO,
    sem_esperar: bool = typer.Option(
        False,
        "--sem-esperar",
        help="Não espera o lote do extract; se houver lote em andamento, para depois do extract.",
    ),
) -> None:
    """Executa as etapas 2 a 7 em sequência (resolve, extract, fuse, validate, docs, index).

    Para na primeira etapa que falhar. Com tudo em cache, não grava nada nem faz
    chamadas pagas (o `extract` cobra a OPENAI_API_KEY mesmo assim).
    """
    typer.echo("== resolve")
    resolve()
    typer.echo("== extract")
    extract(piloto=piloto, limite=0, sem_esperar=sem_esperar, sincrono=False)
    if sem_esperar:
        from avesrag_builder.db.collections import LLM_BATCHES
        from avesrag_builder.db.connection import get_db

        if get_db()[LLM_BATCHES].count_documents({"status": "enviado"}):
            typer.echo("Lote do extract em andamento: rode `run` de novo quando ele terminar.")
            raise typer.Exit(code=0)
    typer.echo("== fuse")
    fuse(piloto=piloto)
    typer.echo("== validate")
    validate(piloto=piloto)
    typer.echo("== docs")
    docs(piloto=piloto)
    typer.echo("== index")
    index(verificar=False, fumaca=False)


if __name__ == "__main__":
    app()
