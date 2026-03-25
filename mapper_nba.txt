import os
import requests
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
api_key = os.getenv("SPORT_DATA_IO_KEY")

def map_nba_teams():
    print("🔍 Obteniendo equipos de Sportsdata.io (NBA)...")
    
    # 1. Llamada a Sportsdata.io
    url = f"https://api.sportsdata.io/v3/nba/scores/json/Teams?key={api_key}"
    response = requests.get(url)
    
    if response.status_code != 200:
        print(f"❌ Error en API: {response.status_code}")
        return
        
    api_teams = response.json()

    # 2. Obtener tus equipos de Supabase (solo NBA)
    db_teams = supabase.table("teams").select("id, name").eq("league", "NBA").execute().data

    for db_team in db_teams:
        db_name_clean = db_team['name'].lower().strip()
        
        # Buscamos coincidencia
        # Intentamos match con "Ciudad Nombre" o solo "Nombre"
        match = next((t for t in api_teams if 
                     f"{t['City']} {t['Name']}".lower() == db_name_clean or 
                     t['Name'].lower() in db_name_clean), None)
        
        if match:
            # 3. Actualizamos Supabase
            supabase.table("teams").update({
                "api_sports_id": match['TeamID'],
                "logo_url": match['WikipediaLogoUrl'] # Sportsdata.io da logos de Wikipedia de alta calidad
            }).eq("id", db_team['id']).execute()
            
            print(f"✅ Vinculado: {db_team['name']} -> API ID: {match['TeamID']}")
        else:
            print(f"❌ No se encontró coincidencia para: {db_team['name']}")

if __name__ == "__main__":
    map_nba_teams()