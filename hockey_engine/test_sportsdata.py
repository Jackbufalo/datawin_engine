import os
import requests
from dotenv import load_dotenv

load_dotenv()
SD_KEY = os.getenv("SPORTSDATA_API_KEY")

# Fecha de hoy para la prueba (Formato: YYYY-MMM-DD)
# Ejemplo: 2026-MAR-24
date_str = "2026-MAR-24" 
url = f"https://api.sportsdata.io/v3/nhl/scores/json/GamesByDate/{date_str}?key={SD_KEY}"

def test_api():
    print(f"📡 Conectando a SportsData.io para la fecha: {date_str}...")
    try:
        response = requests.get(url)
        if response.status_code == 200:
            games = response.json()
            print(f"✅ Conexión exitosa. Se encontraron {len(games)} partidos.")
            for g in games:
                print(f"🏠 {g['HomeTeam']} vs 🚩 {g['AwayTeam']} | Status: {g['Status']}")
        else:
            print(f"❌ Error {response.status_code}: {response.text}")
    except Exception as e:
        print(f"❌ Error de red: {e}")

if __name__ == "__main__":
    test_api()