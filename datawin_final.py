import os
import requests
import math
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
api_key = os.getenv("SPORT_DATA_IO_KEY")

def american_to_decimal(american_odds):
    if american_odds is None or american_odds == 0: return None
    try:
        val = int(american_odds)
        return round((val / 100) + 1, 2) if val > 0 else round((100 / abs(val)) + 1, 2)
    except: return None

def calcular_probabilidad_nba_lite(mu_home, mu_away):
    diff = mu_home - mu_away
    std_dev = math.sqrt(mu_home + mu_away)
    prob_home = 0.5 * (1 + math.erf(diff / (std_dev * math.sqrt(2))))
    return round(prob_home, 4), round(1 - prob_home, 4)

def process_daily_predictions():
    # Buscamos partidos para hoy según la API
    today_api = datetime.now().strftime("%Y-%b-%d").upper()
    fecha_mx_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    
    print(f"🚀 Iniciando DataWin Pro (Versión Lite) para: {today_api}")

    url = f"https://api.sportsdata.io/v3/nba/scores/json/GamesByDate/{today_api}?key={api_key}"
    try:
        response = requests.get(url)
        games = response.json()
    except Exception as e:
        print(f"❌ Error API: {e}")
        return

    if not games:
        print(f"📭 No hay partidos hoy ({today_api}).")
        return

    db_teams = supabase.table("teams").select("id, api_sports_id, name, att_index, def_index, logo_url").eq("league", "NBA").execute().data
    team_map = {str(t['api_sports_id']): t for t in db_teams if t['api_sports_id']}

    for game in games:
        h_id = str(game.get('HomeTeamID'))
        a_id = str(game.get('AwayTeamID'))

        if h_id in team_map and a_id in team_map:
            home = team_map[h_id]
            away = team_map[a_id]

            # Lambdas (basado en promedio liga 112)
            mu_h = 112 * (home['att_index'] / away['def_index'])
            mu_a = 112 * (away['att_index'] / home['def_index'])
            
            p_home, p_away = calcular_probabilidad_nba_lite(mu_h, mu_a)

            prediction_payload = {
                "match_id": str(game['GameID']),
                "fecha_mx": fecha_mx_str,
                "home_team": home['name'],
                "away_team": away['name'],
                "home_logo": home.get('logo_url'),
                "away_logo": away.get('logo_url'),
                "home_win_p": p_home,
                "away_win_p": p_away,
                "home_odds": american_to_decimal(game.get('HomeTeamMoneyLine')),
                "away_odds": american_to_decimal(game.get('AwayTeamMoneyLine')),
                "status": game.get('Status')
            }

            try:
                # AQUÍ ES DONDE SE LLENA LA TABLA QUE VISTE EN LA IMAGEN
                supabase.table("daily_predictions").upsert(prediction_payload, on_conflict="match_id").execute()
                print(f"✅ Guardado en Supabase: {away['name']} @ {home['name']}")
            except Exception as e:
                print(f"❌ Error Upsert en {game['GameID']}: {e}")
        else:
            print(f"⚠️ Equipo no mapeado: {game.get('HomeTeam')} (ID: {h_id})")

if __name__ == "__main__":
    process_daily_predictions()
    
    # Fuerza update 1