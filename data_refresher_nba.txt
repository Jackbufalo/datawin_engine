import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

def refresh_all_indices():
    print("🧠 Calculando promedios de la liga y actualizando índices...")
    
    # 1. Obtener todas las estadísticas crudas de la NBA
    stats_data = supabase.table("nba_raw_stats").select("points_scored_avg, points_conceded_avg").eq("league_name", "NBA").execute().data
    
    if not stats_data:
        print("❌ No hay datos en nba_raw_stats para calcular.")
        return

    # 2. Calcular el promedio de puntos de TODA la liga
    total_pts = sum(s['points_scored_avg'] for s in stats_data)
    league_avg = total_pts / len(stats_data)
    
    print(f"📊 Promedio de puntos de la NBA (Temporada 2025): {round(league_avg, 2)}")

    # 3. Obtener todos los equipos NBA
    db_teams = supabase.table("teams").select("id, name").eq("league", "NBA").execute().data
    
    for team in db_teams:
        try:
            # Buscamos sus stats. Usamos execute() sin .single() para evitar el crash
            res = supabase.table("nba_raw_stats").select("*").eq("team_id", team['id']).execute()
            
            if res.data:
                team_stat = res.data[0]
                att_index = team_stat['points_scored_avg'] / league_avg
                def_index = team_stat['points_conceded_avg'] / league_avg
                
                supabase.table("teams").update({
                    "att_index": round(att_index, 4),
                    "def_index": round(def_index, 4)
                }).eq("id", team['id']).execute()
                
                print(f"✅ {team['name'].ljust(20)} | Att: {round(att_index, 2)} | Def: {round(def_index, 2)}")
            else:
                print(f"⚠️ {team['name'].ljust(20)} | Sin estadísticas en nba_raw_stats.")

        except Exception as e:
            print(f"❌ Error procesando {team['name']}: {e}")

if __name__ == "__main__":
    refresh_all_indices()