# stats_feeder.py (Optimizado)
import os
import requests
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
api_key = os.getenv("SPORT_DATA_IO_KEY")
SEASON = "2025" 

def fetch_nba_stats():
    print(f"🚀 Iniciando actualización de estadísticas NBA...")
    
    api_url = f"https://api.sportsdata.io/v3/nba/scores/json/TeamSeasonStats/{SEASON}?key={api_key}"
    response = requests.get(api_url)
    
    if response.status_code != 200:
        print(f"❌ Error API: {response.status_code}")
        return
        
    all_stats = response.json()
    db_teams = supabase.table("teams").select("id, api_sports_id, name").eq("league", "NBA").execute().data
    id_map = {str(t['api_sports_id']): t['id'] for t in db_teams if t['api_sports_id']}

    for stats in all_stats:
        api_id = str(stats.get('TeamID'))
        
        if api_id in id_map:
            games = stats.get('Games', 0)
            if games < 5: continue # Evitar equipos con pocos datos

            # 1. Puntos Anotados
            pts_scored = stats.get('Points', 0)
            
            # 2. Puntos Concedidos (Mejorado)
            # Buscamos específicamente OpponentStat si OpponentPoints falla
            pts_conceded = stats.get('OpponentPoints') or 0
            if pts_conceded == 0:
                pts_conceded = stats.get('OpponentStat', {}).get('Points', 0)

            # Si sigue siendo 0, el dato no es fiable, saltamos equipo
            if pts_conceded == 0 or pts_scored == 0:
                print(f"⚠️ Datos incompletos para ID {api_id}, saltando...")
                continue

            # 3. Posesiones y Ratings
            poss = stats.get('Possessions')
            if not poss or poss == 0:
                fga = stats.get('FieldGoalsAttempted', 0)
                fta = stats.get('FreeThrowsAttempted', 0)
                orb = stats.get('OffensiveRebounds', 0)
                tov = stats.get('Turnovers', 0)
                poss = fga + (0.44 * fta) - orb + tov

            pace = round(poss / games, 2)
            # OffR: Puntos anotados por cada 100 posesiones
            off_rating = round((pts_scored / poss) * 100, 2)
            # DefR: Puntos permitidos por cada 100 posesiones
            def_rating = round((pts_conceded / poss) * 100, 2)

            payload = {
                "team_id": id_map[api_id],
                "league_name": "NBA",
                "points_scored_avg": round(pts_scored / games, 2),
                "points_conceded_avg": round(pts_conceded / games, 2),
                "games_played": int(games),
                "pace": pace,
                "off_rating": off_rating,
                "def_rating": def_rating
            }

            try:
                supabase.table("nba_raw_stats").upsert(payload, on_conflict="team_id").execute()
                print(f"✅ ID: {api_id.ljust(4)} | Pace: {pace} | OffR: {off_rating} | DefR: {def_rating}")
            except Exception as e:
                print(f"❌ Error en equipo {api_id}: {e}")

if __name__ == "__main__":
    fetch_nba_stats()