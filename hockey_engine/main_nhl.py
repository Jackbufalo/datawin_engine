import os
from dotenv import load_dotenv
from supabase import create_client
from hockey_intelligence_engine import HockeyEngine
from nhl_scraper import NHLScraper
from nhl_advanced_scraper import NHLAdvancedScraper

# 1. CARGAR CONFIGURACIÓN DESDE .ENV
load_dotenv()
URL = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_KEY")

# --- AÑADE ESTO PARA DEPURAR ---
print(f"DEBUG: URL leída -> {URL}")
if URL:
    print(f"DEBUG: Longitud de la Key -> {len(KEY)}")
# -------------------------------

if not URL or not KEY or "TU_URL" in URL:
    print("❌ Error: Credenciales de Supabase no válidas en el archivo .env")
    exit()

# 2. INICIALIZAR CLIENTE Y MOTORES
# Pasamos las credenciales solo una vez aquí
supabase = create_client(URL, KEY)
engine = HockeyEngine(URL, KEY)
calendar_provider = NHLScraper()
stats_provider = NHLAdvancedScraper()

def run_production_pipeline():
    print("🧊 --- INICIANDO HOCKEY INTELLIGENCE (PIPELINE) ---")
    
    # Obtener partidos de hoy (NHL API)
    print("📅 Buscando calendario oficial...")
    games = calendar_provider.get_todays_schedule()
    
    # Obtener analítica (BeautifulSoup - Natural Stat Trick)
    print("📊 Extrayendo métricas avanzadas (Corsi/xG)...")
    advanced_stats_list = stats_provider.get_advanced_stats()
    
    if not games:
        print("⚠️ No hay partidos programados para hoy según la API.")
        return
    
    if not advanced_stats_list:
        print("⚠️ No se pudo obtener analítica avanzada. Usando valores neutros para no detener el proceso.")
        advanced_stats_list = [] # Continuamos con valores por defecto

    # Crear diccionario de búsqueda para los nombres de equipos
    stats_dict = {s['team_name']: s for s in advanced_stats_list}

    for game in games:
        # Construcción de nombres para el match
        h_place = game['homeTeam']['placeName']['default']
        h_common = game['homeTeam']['commonName']['default']
        a_place = game['awayTeam']['placeName']['default']
        a_common = game['awayTeam']['commonName']['default']
        
        h_full_name = f"{h_place} {h_common}"
        a_full_name = f"{a_place} {a_common}"
        
        # Intentar match por nombre completo o por nombre común (ej: "Rangers")
        h_stats = stats_dict.get(h_full_name) or stats_dict.get(h_common)
        a_stats = stats_dict.get(a_full_name) or stats_dict.get(a_common)

        # Valores de seguridad si el equipo no se encuentra
        if not h_stats:
            print(f"❓ No hay stats para {h_full_name}, usando promedios.")
            h_stats = {'cf_pct': 0.50, 'xgf': 3.1, 'xga': 3.1}
        if not a_stats:
            print(f"❓ No hay stats para {a_full_name}, usando promedios.")
            a_stats = {'cf_pct': 0.50, 'xgf': 3.1, 'xga': 3.1}

        # 3. PREPARAR DATOS PARA EL CÁLCULO
        # Dividimos xG entre 3 (promedio goles) para obtener un rating relativo
        input_data = {
            "h_att": h_stats.get('xgf', 3.1) / 3.1, 
            "h_def": h_stats.get('xga', 3.1) / 3.1,
            "a_att": a_stats.get('xgf', 3.1) / 3.1,
            "a_def": a_stats.get('xga', 3.1) / 3.1,
            "h_cf_pct": h_stats['cf_pct'],
            "a_cf_pct": a_stats['cf_pct'],
            "h_goalie_pct": 0.910, # Base (se puede mejorar con el goalie_scraper)
            "a_goalie_pct": 0.910
        }

        # 4. EJECUTAR MOTOR MATEMÁTICO (Poisson/Skellam)
        res = engine.calculate_game(input_data)

        # 5. PREPARAR PAYLOAD PARA SUPABASE
        payload = {
            "event_date": game['gameDate'],
            "home_team": h_full_name,
            "away_team": a_full_name,
            "home_logo": game['homeTeam']['logo'],
            "away_logo": game['awayTeam']['logo'],
            "lambda_home": res['l1'],
            "lambda_away": res['l2'],
            "prob_home_win": res['prob_h'],
            "prob_away_win": res['prob_a'],
            "prob_over_5_5": res['prob_o'],
            "prob_under_5_5": round(100 - res['prob_o'], 2),
            "status": "pending"
        }

        # 6. ENVIAR A SUPABASE (Upsert basado en nombres y fecha)
        try:
            supabase.table("nhl_predictions").upsert(
                payload, on_conflict="home_team, away_team, event_date"
            ).execute()
            print(f"✅ Procesado: {h_common} vs {a_common} | Prob H: {res['prob_h']}%")
        except Exception as e:
            print(f"❌ Error al subir {h_common} a Supabase: {e}")

if __name__ == "__main__":
    run_production_pipeline()