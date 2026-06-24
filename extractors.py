from src.database.conexoes import DatabaseConnection
from src.extractors.gbif import GBIFExtractor


db_connection = DatabaseConnection()

gbif = GBIFExtractor()
especies = gbif.buscar_especies_brasil(limite_total=200)
for e in especies:
    gbif.run_for_species(e, db_connection)
