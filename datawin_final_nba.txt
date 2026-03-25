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
    # Desviación estándar promedio en NBA (aprox 13.5 puntos)
    std_dev = 13.5 
    prob_home = 0.5 * (1 + math.erf(diff / (std_dev * math.sqrt(2))))
    return round(prob_home, 4), round(1 - prob_home, 4)

def calcular_over_under_ajustado(mu_home, mu_away):
    """
    Calcula la línea O/U basada en la suma de proyecciones y determina 
    la probabilidad dinámica usando una distribución normal.
    """
    total_proyectado = mu_home + mu_away
    
    # La línea de apuesta "fair" (redondeo a .5 más cercano)
    linea = round(total_proyectado * 2) / 2
    
    # Diferencia entre nuestra proyección y la línea establecida
    diff = total_proyectado - linea
    
    # Desviación estándar típica para totales de la NBA (aprox. 18-20 puntos)
    # Un valor de 18 permite que pequeñas diferencias en puntos se traduzcan
    # en cambios notables en el porcentaje.
    std_dev_total = 18.0 
    
    # Cálculo de probabilidad usando la Función de Error (Distribución Normal)
    # Esto evita el "50%" constante y da una curva suave de probabilidad.
    prob_over = 0.5 * (1 + math.erf(diff / (std_dev_total * math.sqrt(2))))
    
    # Ajuste de límites para evitar valores extremos poco realistas
    prob_over = max(0.40, min(0.60, prob_over))
    
    return linea, round(prob_over, 4), round(1 - prob_over, 4)

def process_daily_predictions():
    # Fecha para API y registro
    today_api = datetime.now().strftime("%Y-%b-%d").upper()
    fecha_mx_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    
    print(f"🚀 EJECUTANDO VERSIÓN OVER-UNDER v2 para: {today_api}")

    url = f"https://api.sportsdata.io/v3/nba/scores/json/GamesByDate/{today_api}?key={api_key}"
    try:
        response = requests.get(url)
        games = response.json()
    except Exception as e:
        print(f"❌ Error API: {e}")
        return

    if not games:
        print(f"📭 Sin partidos para procesar.")
        return

    # Traemos los índices de nuestra DB de equipos
    db_teams = supabase.table("teams").select("id, api_sports_id, name, att_index, def_index, logo_url").eq("league", "NBA").execute().data
    team_map = {str(t['api_sports_id']): t for t in db_teams if t['api_sports_id']}

    for game in games:
        h_id = str(game.get('HomeTeamID'))
        a_id = str(game.get('AwayTeamID'))

        if h_id in team_map and a_id in team_map:
            home = team_map[h_id]
            away = team_map[a_id]

            # CÁLCULO DE PUNTOS PROYECTADOS (AJUSTADO)
            # Fórmula: Media Liga * (Ofensiva Equipo A / Defensiva Equipo B)
            mu_h = 114.5 * (home['att_index'] / away['def_index']) # Media moderna 2024-2026 es más alta (~114)
            mu_a = 114.5 * (away['att_index'] / home['def_index'])
            
            # Ganador
            p_home, p_away = calcular_probabilidad_nba_lite(mu_h, mu_a)
            
            # Totales (Over/Under)
            linea_ou, prob_over, prob_under = calcular_over_under_ajustado(mu_h, mu_a)

            prediction_payload = {
                "match_id": str(game['GameID']),
                "fecha_mx": fecha_mx_str,
                "home_team": home['name'],
                "away_team": away['name'],
                "home_logo": home.get('logo_url'),
                "away_logo": away.get('logo_url'),
                "home_win_p": round(p_home * 100, 1),
                "away_win_p": round(p_away * 100, 1),
                "home_odds": american_to_decimal(game.get('HomeTeamMoneyLine')),
                "away_odds": american_to_decimal(game.get('AwayTeamMoneyLine')),
                "over_under_line": linea_ou,
                "over_p": round(prob_over * 100, 1),
                "under_p": round(prob_under * 100, 1),
                "status": game.get('Status')
            }

            try:
                supabase.table("daily_predictions").upsert(prediction_payload, on_conflict="match_id").execute()
                print(f"🔥 {home['name']} vs {away['name']} | O/U: {linea_ou} | Proyección: {round(mu_h + mu_a, 1)}")
            except Exception as e:
                print(f"❌ Error: {e}")

if __name__ == "__main__":
    process_daily_predictions()