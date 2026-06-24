"""
dags/dag_pipeline_aves_brasil.py
DAG principal — coleta e enriquecimento de aves do Brasil.
Frequência: semanal (domingo às 02h)
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from src.database.conexoes import DatabaseConnection
from src.extractors.gbif import GBIFExtractor
from src.extractors.avonet import AvonetExtractor
from src.extractors.ebird import EbirdExtractor
from src.extractors.sibbr import SibbrExtractor
from src.extractors.iucn import IUCNExtractor
from src.extractors.worldclim import WorldclimExtractor

log = logging.getLogger(__name__)

DEFAULT_ARGS = {
    "owner": "aves_brasil",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,
}

def t_descobrir_especies(**ctx):
    extractor = GBIFExtractor()
    especies = extractor.buscar_especies_brasil(limite_total=15000)
    ctx["ti"].xcom_push(key="especies", value=list(especies))
    log.info("Espécies descobertas: %d", len(especies))

def t_carregar_avonet(**ctx):
    db = DatabaseConnection()
    extractor = AvonetExtractor()
    especies = set(ctx["ti"].xcom_pull(key="especies", task_ids="descobrir_especies") or [])
    carregadas = extractor.run(db_connection=db, especies_alvo=especies)
    log.info("AVONET: %d espécies carregadas", len(carregadas))

def t_coletar_ebird(**ctx):
    db = DatabaseConnection()
    extractor = EbirdExtractor()
    extractor.run(db_connection=db)

def t_coletar_ocorrencias(**ctx):
    db = DatabaseConnection()
    gbif_ext = GBIFExtractor()
    sibbr_ext = SibbrExtractor()
    especies = ctx["ti"].xcom_pull(key="especies", task_ids="descobrir_especies") or []
    
    for nome in especies:
        gbif_ext.run_for_species(nome, db)
        sibbr_ext.run_for_species(nome, db)
        time.sleep(0.2)

def t_enriquecer_iucn(**ctx):
    db = DatabaseConnection()
    extractor = IUCNExtractor()
    especies = ctx["ti"].xcom_pull(key="especies", task_ids="descobrir_especies") or []
    
    for nome in especies:
        extractor.run_for_species(nome, db)
        time.sleep(0.3)

def t_enriquecer_worldclim(**ctx):
    db = DatabaseConnection()
    extractor = WorldclimExtractor()
    especies = ctx["ti"].xcom_pull(key="especies", task_ids="descobrir_especies") or []
    
    for nome in especies:
        extractor.run_for_species(nome, db)

def t_resumo(**ctx):
    db_conn = DatabaseConnection()
    db = db_conn.get_mongo_db()
    total_especies = db.especies.count_documents({})
    
    total_ocorr = 0
    with db_conn.get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM ocorrencias")
            row = cur.fetchone()
            if row:
                total_ocorr = row[0]
                
    log.info("=" * 50)
    log.info("PIPELINE CONCLUÍDO")
    log.info("  Espécies   : %d", total_especies)
    log.info("  Ocorrências: %d", total_ocorr)
    log.info("=" * 50)


with DAG(
    dag_id="pipeline_aves_brasil",
    default_args=DEFAULT_ARGS,
    description="Coleta e enriquecimento de dados morfológicos de aves do Brasil",
    schedule_interval="0 2 * * 0",   # domingo às 02h
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["aves", "biodiversidade", "brasil"],
) as dag:

    descobrir = PythonOperator(
        task_id="descobrir_especies",
        python_callable=t_descobrir_especies,
    )

    avonet = PythonOperator(
        task_id="carregar_avonet",
        python_callable=t_carregar_avonet,
    )

    ebird = PythonOperator(
        task_id="coletar_ebird",
        python_callable=t_coletar_ebird,
    )

    ocorrencias = PythonOperator(
        task_id="coletar_ocorrencias",
        python_callable=t_coletar_ocorrencias,
    )

    iucn = PythonOperator(
        task_id="enriquecer_iucn",
        python_callable=t_enriquecer_iucn,
    )

    worldclim = PythonOperator(
        task_id="enriquecer_worldclim",
        python_callable=t_enriquecer_worldclim,
    )

    resumo = PythonOperator(
        task_id="resumo_pipeline",
        python_callable=t_resumo,
    )

    descobrir >> [avonet, ebird, ocorrencias]
    ocorrencias >> iucn >> worldclim
    [avonet, ebird, worldclim] >> resumo
