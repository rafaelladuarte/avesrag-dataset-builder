from bs4 import BeautifulSoup
import pandas as pd

file_path = "data/treat/Espécies em Uberlândia MG.html"

with open(file_path, "r", encoding="utf-8") as f:
    html_content = f.read()

soup = BeautifulSoup(html_content, "html.parser")

table = soup.find("table", {"class": "wa-table-sp"})


rows = table.find_all("tr")

data = []

for row in rows:
    cols = row.find_all("td")
    if len(cols) >= 5:
        especie = cols[1].get_text(strip=True)
        nome_comum = cols[2].get_text(strip=True)
        sons = cols[3].get_text(strip=True)
        fotos = cols[4].get_text(strip=True)
        data.append([especie, nome_comum, sons, fotos])

df = pd.DataFrame(data, columns=["Espécie", "Nome Comum", "Sons", "Fotos"])


csv_path = "especies_uberlandia.csv"
df.to_csv(csv_path, index=False, encoding="utf-8")
