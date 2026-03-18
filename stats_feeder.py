import os
import requests
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
api_key = os.getenv("SPORT_DATA_IO_KEY")
SEASON = "2025" 

def fetch_nba_stats():
    print(f"🚀 Obteniendo estadísticas de la temporada {SEASON}...")
    
    url = f"https://api.sportsdata.io/v3/nba/scores/json/TeamSeasonStats/{SEASON}?key={api_key}"
    response = requests.get(url)
    
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
            
            if games == 0: continue

            pts_scored = stats.get('Points', 0)
            pts_conceded = stats.get('OpponentPoints')
            
            if pts_conceded is None:
                pts_conceded = stats.get('OpponentStat', {}).get('Points', 0)

            payload = {
                "team_id": id_map[api_id],
                "league_name": "NBA",
                "points_scored_avg": round(pts_scored / games, 2),
                "points_conceded_avg": round(pts_conceded / games, 2),
                "games_played": int(games)
            }

            try:
                # El upsert necesita que 'team_id' sea único en la base de datos
                supabase.table("nba_raw_stats").upsert(payload, on_conflict="team_id").execute()
                print(f"✅ Guardado: {next(t['name'] for t in db_teams if str(t['api_sports_id']) == api_id)}")
            except Exception as e:
                print(f"❌ Error en {api_id}: {e}")

if __name__ == "__main__":
    fetch_nba_stats()