# requirements.txt
# pymongo requests python-dotenv tenacity

import os, time, requests
from pymongo import MongoClient, UpdateOne
from dotenv import load_dotenv
from tenacity import retry, wait_exponential, stop_after_attempt

load_dotenv()

EBIRD_KEY = os.getenv("EBIRD_API_KEY")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")

client = MongoClient(MONGO_URI)
db = client["ebird_brasil"]

HEADERS = {"x-ebirdapitoken": EBIRD_KEY}
BASE    = "https://api.ebird.org/v2"

# Mapeamento estado → bioma(s) predominante(s)
BIOME_MAP = {
    "BR-AM": ["Amazônia"],
    "BR-PA": ["Amazônia"],
    "BR-MT": ["Amazônia", "Cerrado", "Pantanal"],
    "BR-MS": ["Pantanal", "Cerrado"],
    "BR-MG": ["Cerrado", "Mata Atlântica"],
    "BR-SP": ["Cerrado", "Mata Atlântica"],
    "BR-BA": ["Caatinga", "Mata Atlântica", "Cerrado"],
    "BR-RS": ["Pampa", "Mata Atlântica"],
    "BR-RJ": ["Mata Atlântica"],
    "BR-GO": ["Cerrado"],
    "BR-CE": ["Caatinga"],
    "BR-PE": ["Caatinga", "Mata Atlântica"],
        # ... completar os 27 estados
}

@retry(wait=wait_exponential(min=2, max=30), stop=stop_after_attempt(5))
def api_get(path, params=None):
    r = requests.get(f"{BASE}{path}", headers=HEADERS, params=params)
    r.raise_for_status()
    return r.json()

def load_taxonomy():
    """Baixa taxonomia completa e carrega a coleção species."""
    print("Baixando taxonomia eBird...")
    
    # Nome em português
    taxa_pt = api_get("/ref/taxonomy/ebird", {"locale": "pt", "fmt": "json"})
    pt_map  = {t["speciesCode"]: t.get("comName") for t in taxa_pt}

    taxa = api_get("/ref/taxonomy/ebird", {"fmt": "json"})
    
    ops = []
    for t in taxa:
        doc = {
            "speciesCode"  : t["speciesCode"],
            "sciName"      : t["sciName"],
            "comName"      : t["comName"],
            "comNamePt"    : pt_map.get(t["speciesCode"]),
            "order"        : t.get("order"),
            "familyComName": t.get("familyComName"),
            "familySciName": t.get("familySciName"),
            "taxonOrder"   : t.get("taxonOrder"),
            "category"     : t.get("category"),
            "brazilStates" : [],
            "biomes"       : [],
        }
        ops.append(UpdateOne(
            {"speciesCode": doc["speciesCode"]},
            {"$set": doc},
            upsert=True
        ))
    
    db.species.bulk_write(ops)
    print(f"  {len(ops)} espécies carregadas.")

def load_regions():
    """Carrega estados do Brasil na coleção regions."""
    states = api_get("/ref/region/list/subnational1/BR")
    
    ops = []
    for s in states:
        code   = s["code"]
        biomes = BIOME_MAP.get(code, ["Não mapeado"])
        ops.append(UpdateOne(
            {"regionCode": code},
            {"$set": {
                "regionCode" : code,
                "name"       : s["name"],
                "regionType" : "subnational1",
                "parentCode" : "BR",
                "biome"      : biomes[0],
                "biomes"     : biomes,
            }},
            upsert=True
        ))
    
    db.regions.bulk_write(ops)
    print(f"  {len(states)} estados carregados.")
    return [s["code"] for s in states]

def load_occurrences(state_codes):
    """Para cada estado, busca lista histórica de espécies
    e popula a coleção occurrences + atualiza species.brazilStates."""
    
    for code in state_codes:
        print(f"  Processando {code}...")
        region = db.regions.find_one({"regionCode": code})
        
        try:
            spp_list = api_get(f"/product/spplist/{code}")
        except:
            continue
        
        occ_ops = []
        spp_ops = []
        
        for sp_code in spp_list:
            occ_ops.append(UpdateOne(
                {"speciesCode": sp_code, "regionCode": code},
                {"$set": {
                    "speciesCode" : sp_code,
                    "regionCode"  : code,
                    "regionType"  : "subnational1",
                    "biome"       : region["biome"],
                    "biomes"      : region["biomes"],
                    "confirmed"   : True,
                    "source"      : "spplist",
                }},
                upsert=True
            ))
            # Atualiza o array brazilStates na espécie
            spp_ops.append(UpdateOne(
                {"speciesCode": sp_code},
                {"$addToSet": {
                    "brazilStates": code,
                    "biomes": {"$each": region["biomes"]}
                }}
            ))
        
        if occ_ops: db.occurrences.bulk_write(occ_ops)
        if spp_ops: db.species.bulk_write(spp_ops)
        
        # Respeitar rate limit da API
        time.sleep(1.5)

def load_recent_observations(state_codes, back=14):
    """Busca observações recentes com coordenadas para a coleção observations."""
    
    for code in state_codes:
        try:
            obs_list = api_get(
                f"/data/obs/{code}/recent",
                {"back": back, "maxResults": 10000}
            )
        except:
            continue
        
        ops = []
        for o in obs_list:
            ops.append(UpdateOne(
                {"subId": o["subId"], "speciesCode": o["speciesCode"]},
                {"$set": {
                    "subId"      : o["subId"],
                    "speciesCode": o["speciesCode"],
                    "locId"      : o["locId"],
                    "locName"    : o["locName"],
                    "obsDt"      : o["obsDt"],
                    "howMany"    : o.get("howMany"),
                    "regionCode" : code,
                    "obsValid"   : o.get("obsValid"),
                    "obsReviewed": o.get("obsReviewed"),
                        # GeoJSON para queries geoespaciais
                    "location": {
                        "type": "Point",
                        "coordinates": [o["lng"], o["lat"]]
                    }
                }},
                upsert=True
            ))
        
        if ops: db.observations.bulk_write(ops)
        time.sleep(1.5)

# Índices recomendados
def create_indexes():
    db.species.create_index("speciesCode", unique=True)
    db.species.create_index("brazilStates")
    db.species.create_index("biomes")
    db.occurrences.create_index([("speciesCode",1),("regionCode",1)], unique=True)
    db.occurrences.create_index("biome")
    db.observations.create_index([("location", "2dsphere")])
    db.observations.create_index("speciesCode")