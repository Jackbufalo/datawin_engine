import os
import requests
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client

# Cargar variables de entorno
load_dotenv()

# Configuración de Supabase y API
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
api_key = os.getenv("SPORT_DATA_IO_KEY")

def fetch_daily_games():
    # 1. Obtener fecha de hoy en formato YYYY-MMM-DD (ej: 2026-MAR-18)
    # Nota: Sportsdata.io es estricto con el formato de fecha
    today = datetime.now().strftime("%Y-%b-%d").upper()
    print(f"📅 Buscando partidos para hoy: {today}...")

    # 2. Endpoint de Partidos por Día (Scores)
    url = f"https://api.sportsdata.io/v3/nba/scores/json/GamesByDate/{today}?key={api_key}"
    
    try:
        response = requests.get(url)
        if response.status_code != 200:
            print(f"❌ Error API: {response.status_code} - {response.text}")
            return
        
        games = response.json()
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return

    if not games:
        print(f"📭 No hay partidos programados para hoy ({today}).")
        return

    # Mapeo de IDs de equipos (necesitamos el UUID de Supabase)
    db_teams = supabase.table("teams").select("id, api_sports_id").eq("league", "NBA").execute().data
    id_map = {str(t['api_sports_id']): t['id'] for t in db_teams}

    for game in games:
        home_api_id = str(game.get('HomeTeamID'))
        away_api_id = str(game.get('AwayTeamID'))

        # Verificamos que ambos equipos existan en nuestra base de datos
        if home_api_id in id_map and away_api_id in id_map:
            match_payload = {
                "api_match_id": str(game['GameID']),
                "home_team_id": id_map[home_api_id],
                "away_team_id": id_map[away_api_id],
                "match_date": game.get('DateTime'),
                "status": game.get('Status'),
                "league": "NBA"
            }

            try:
                # 3. Guardar o actualizar el partido en 'matches'
                # Usamos upsert para actualizar el status si el partido ya existe
                res_match = supabase.table("matches").upsert(match_payload, on_conflict="api_match_id").execute()
                
                # Extraer el UUID generado/existente para la tabla de odds
                current_match_uuid = res_match.data[0]['id']

                # 4. Guardar Momios (Odds) si están disponibles en la respuesta
                # Sportsdata.io a veces devuelve estos campos en el mismo objeto de Scores
                home_ml = game.get('HomeTeamMoneyLine')
                if home_ml is not None:
                    odds_payload = {
                        "match_id": current_match_uuid,
                        "home_odds": int(home_ml) if home_ml else None,
                        "away_odds": int(game.get('AwayTeamMoneyLine')) if game.get('AwayTeamMoneyLine') else None,
                        "spread": game.get('PointSpread'),
                        "over_under": game.get('OverUnder'),
                        "updated_at": "now()"
                    }
                    supabase.table("odds").upsert(odds_payload, on_conflict="match_id").execute()

                print(f"✅ Procesado: {game.get('AwayTeam')} @ {game.get('HomeTeam')} (ID: {game.get('GameID')})")

            except Exception as e:
                print(f"❌ Error guardando partido {game.get('GameID')}: {e}")
        else:
            print(f"⚠️ Saltando partido {game.get('GameID')}: Equipos no mapeados en BD.")

if __name__ == "__main__":
    fetch_daily_games()