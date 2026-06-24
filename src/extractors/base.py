"""
src/extractors/base.py
Interface comum para coletores de dados.
"""
from abc import ABC, abstractmethod
import logging

class BaseExtractor(ABC):
    """
    Interface abstrata garantindo padronização para todos os coletores de dados.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        
    @abstractmethod
    def extract(self, *args, **kwargs):
        """Coleta os dados puros (API, CSV, S3, etc)."""
        pass
        
    @abstractmethod
    def transform(self, raw_data, *args, **kwargs):
        """Limpa, filtra e ajusta tipos de dados."""
        pass
        
    @abstractmethod
    def load(self, transformed_data, db_connection):
        """Grava os dados transformados no MongoDB e/ou PostGIS."""
        pass
        
    def run(self, db_connection, *args, **kwargs):
        """
        Template Method: coordena o ciclo completo do ETL.
        """
        self.logger.info("Iniciando processo de Extração...")
        raw_data = self.extract(*args, **kwargs)
        
        self.logger.info("Iniciando processo de Transformação...")
        clean_data = self.transform(raw_data)
        
        self.logger.info("Iniciando processo de Carga (Load)...")
        result = self.load(clean_data, db_connection)
        
        self.logger.info("Pipeline do extrator finalizada com sucesso.")
        return result
