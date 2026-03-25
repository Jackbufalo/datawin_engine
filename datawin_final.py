# datawin_final.py
import os
import requests
import math
import json
import google.generativeai as genai
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
from supabase import create_client
from scipy.stats import norm

load_dotenv()

# Configuración Supabase y API
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
api_key_sports = os.getenv("SPORT_DATA_IO_KEY")

# Configuración Gemini 2.0
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-2.0-flash')

# --- FUNCIONES DE APOYO ---

def american_to_decimal(american_odds):
    if american_odds is None or american_odds == 0: return None
    try:
        val = int(american_odds)
        return round((val / 100) + 1, 2) if val > 0 else round((100 / abs(val)) + 1, 2)
    except: return None

def calcular_ev(prob_decimal, cuota_decimal):
    if not cuota_decimal or not prob_decimal: return 0
    return round((float(prob_decimal) * float(cuota_decimal)) - 1, 4)

# --- DETECTOR DE FATIGA (B2B) ---

def check_back_to_back(team_id):
    """Verifica si el equipo jugó ayer consultando la tabla de predicciones."""
    ayer = (datetime.now() - timedelta(days=1)).strftime("%d/%m/%Y")
    try:
        res = supabase.table("daily_predictions").select("match_id")\
            .or_(f"home_team.eq.{team_id},away_team.eq.{team_id}")\
            .filter("fecha_mx", "ilike", f"%{ayer}%").execute()
        return len(res.data) > 0
    except:
        return False

# --- MOTOR MATEMÁTICO REFINADO ---

def proyectar_puntos_nba(home_stats, away_stats, liga_stats, h_b2b=False, a_b2b=False):
    # Ratings base
    off_h = float(home_stats.get('off_rating') or liga_stats['rating'])
    def_h = float(home_stats.get('def_rating') or liga_stats['rating'])
    off_a = float(away_stats.get('off_rating') or liga_stats['rating'])
    def_a = float(away_stats.get('def_rating') or liga_stats['rating'])
    
    # Penalización por Fatiga (B2B)
    if h_b2b: 
        off_h *= 0.975  # -2.5% eficiencia ofensiva
        def_h *= 1.015  # +1.5% puntos permitidos
    if a_b2b:
        off_a *= 0.975
        def_a *= 1.015

    pace_h = float(home_stats.get('pace') or liga_stats['pace'])
    pace_a = float(away_stats.get('pace') or liga_stats['pace'])

    pace_proyectado = (pace_h * pace_a) / liga_stats['pace']
    mu_h = (off_h * def_a / liga_stats['rating']) * (pace_proyectado / 100)
    mu_a = (off_a * def_h / liga_stats['rating']) * (pace_proyectado / 100)
    
    return round(float(mu_h), 2), round(float(mu_a), 2)

def calcular_probabilidades_nba(mu_home, mu_away, sigma_diff=13.8, sigma_total=18.5, linea_bookie=None):
    diff = mu_home - mu_away
    total_proy = mu_home + mu_away
    
    # Probabilidades Moneyline
    sigma_ml = sigma_diff * math.sqrt(total_proy / 222)
    p_home = 1 - norm.cdf(0, loc=diff, scale=sigma_ml)
    p_away = 1 - p_home

    # Ajuste de Línea Inteligente (Margen de Seguridad de 2.0 puntos)
    if linea_bookie and float(linea_bookie) > 150:
        linea = float(linea_bookie)
        is_official = True
    else:
        # Si no hay línea, creamos una competitiva para generar varianza en %
        linea = round(total_proy - 2.0, 1) 
        is_official = False

    p_under = norm.cdf(linea + 0.5, loc=total_proy, scale=sigma_total)
    p_over = 1 - p_under
    
    ou_pick = "OVER" if p_over > p_under else "UNDER"
    if not is_official: ou_pick = f"PROY {ou_pick}"

    return round(p_home, 4), round(p_away, 4), linea, round(p_over, 4), round(p_under, 4), ou_pick

# --- ANÁLISIS IA ELITE ---

def generar_analisis_ia_gemini(home, away, p_h, p_a, linea_ou, pick_ou, h_b2b, a_b2b):
    fatiga_txt = "Ambos descansados."
    if h_b2b and a_b2b: fatiga_txt = "Ambos en Back-to-Back (Fatiga extrema)."
    elif h_b2b: fatiga_txt = f"{home} viene de jugar ayer (Ventaja física para {away})."
    elif a_b2b: fatiga_txt = f"{away} viene de jugar ayer (Ventaja física para {home})."

    prompt = f"""
    Eres un 'Sharp Bettor' y analista senior de la NBA. Tu objetivo es validar el valor de una apuesta.
    Partido: {home} vs {away}.
    
    Métricas de DataWin Pro:
    - Win Prob: {home} {round(p_h*100,1)}% | {away} {round(p_a*100,1)}%
    - O/U Line: {linea_ou} | Pick sugerido: {pick_ou}
    - Estado Físico: {fatiga_txt}

    Genera un JSON con este formato (Sé directo, cínico y profesional):
    {{
      "injuries": "Identifica jugadores clave en duda y cómo afectan el spread.",
      "context": "Analiza cómo el factor fatiga ({fatiga_txt}) y el estilo de juego afectan el pick.",
      "final_verdict": "Justificación de por qué el pick {pick_ou} tiene valor real contra la línea {linea_ou}."
    }}
    """
    try:
        response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        return response.text
    except:
        return json.dumps({
            "injuries": "Reporte dinámico en proceso.",
            "context": f"Evaluando impacto de fatiga: {fatiga_txt}",
            "final_verdict": f"Valor detectado en {pick_ou} tras ajuste de varianza matemática."
        })

# --- PROCESO PRINCIPAL ---

def process_daily_predictions():
    today_api = datetime.now().strftime("%Y-%b-%d").upper()
    fecha_mx_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    
    print(f"🔥 DATAWIN PRO ENGINE | REFINADO 2026 | {today_api}")

    url = f"https://api.sportsdata.io/v3/nba/scores/json/GamesByDate/{today_api}?key={api_key_sports}"
    games = requests.get(url).json()

    if not games or not isinstance(games, list):
        print("📭 No hay acción hoy."); return

    stats_data = supabase.table("nba_raw_stats").select("*").execute().data
    stats_map = {str(s['team_id']): s for s in stats_data}
    teams_info = supabase.table("teams").select("id, api_sports_id, name").eq("league", "NBA").execute().data
    team_map = {str(t['api_sports_id']): t for t in teams_info}

    liga_stats = {"pace": 99.2, "rating": 115.1}

    for game in games:
        h_api_id, a_api_id = str(game.get('HomeTeamID')), str(game.get('AwayTeamID'))

        if h_api_id in team_map and a_api_id in team_map:
            home, away = team_map[h_api_id], team_map[a_api_id]
            h_stats, a_stats = stats_map.get(str(home['id'])), stats_map.get(str(away['id']))
            if not h_stats or not a_stats: continue

            # Detección de Fatiga
            h_b2b = check_back_to_back(home['name'])
            a_b2b = check_back_to_back(away['name'])

            # 1. Proyección con Factor Fatiga
            mu_h, mu_a = proyectar_puntos_nba(h_stats, a_stats, liga_stats, h_b2b, a_b2b)
            p_h, p_a, linea_ou, p_over, p_under, ou_pick = calcular_probabilidades_nba(
                mu_h, mu_a, linea_bookie=game.get('OverUnder')
            )

            # 2. Análisis IA Premium
            print(f"🤖 Analizando: {home['name']} vs {away['name']} (B2B: H:{h_b2b} A:{a_b2b})")
            analisis_ia = generar_analisis_ia_gemini(home['name'], away['name'], p_h, p_a, linea_ou, ou_pick, h_b2b, a_b2b)
            
            time.sleep(10) # Estabilidad API

            # 3. Guardado
            h_odds = american_to_decimal(game.get('HomeTeamMoneyLine'))
            a_odds = american_to_decimal(game.get('AwayTeamMoneyLine'))

            payload = {
                "match_id": str(game['GameID']),
                "fecha_mx": fecha_mx_str,
                "home_team": home['name'],
                "away_team": away['name'],
                "home_win_p": round(p_h * 100, 1),
                "away_win_p": round(p_a * 100, 1),
                "home_ev": calcular_ev(p_h, h_odds),
                "away_ev": calcular_ev(p_a, a_odds),
                "over_under_line": linea_ou,
                "over_p": round(p_over * 100, 1),
                "under_p": round(p_under * 100, 1),
                "ou_pick": ou_pick,
                "ai_analysis": analisis_ia
            }

            supabase.table("daily_predictions").upsert(payload, on_conflict="match_id").execute()
            print(f"✅ Pick Generado: {ou_pick} ({max(p_over, p_under)*100:.1f}%)")

if __name__ == "__main__":
    process_daily_predictions()