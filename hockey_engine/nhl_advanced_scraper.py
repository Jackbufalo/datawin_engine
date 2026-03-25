# nhl_advanced_scraper.py
import requests

class NHLAdvancedScraper:
    def __init__(self):
        # Esta es la URL más estable para posiciones actuales
        self.url = "https://api-web.nhl.com/v1/standings/now"

    def get_advanced_stats(self):
        print(f"📡 Sincronizando con la Central de Datos de la NHL...")
        try:
            response = requests.get(self.url, timeout=15)
            if response.status_code != 200:
                print(f"❌ Error API: {response.status_code}")
                return None

            data = response.json()
            
            # La API de la NHL a veces devuelve los equipos en 'standings' 
            # o directamente en la raíz del JSON.
            standings = data.get('standings') or data.get('data') or data
            
            if not isinstance(standings, list):
                print("⚠️ Estructura de API inesperada. Revisando formato...")
                # Fallback: si standings es un dict, buscamos la lista adentro
                if isinstance(standings, dict):
                    for key in standings:
                        if isinstance(standings[key], list):
                            standings = standings[key]
                            break

            if not standings or not isinstance(standings, list):
                print("❌ No se pudo localizar la lista de equipos en el JSON.")
                return None

            stats_cleaned = []
            for team in standings:
                # Extraer nombre (manejando posibles variaciones de la API)
                team_name = team.get('teamName', {}).get('default') or team.get('teamCommonName', {}).get('default')
                
                if not team_name:
                    continue

                gp = team.get('gamesPlayed', 1)
                if gp == 0: gp = 1
                
                # Goles reales para el modelo de Poisson
                stats_cleaned.append({
                    "team_name": team_name,
                    "cf_pct": 0.50, # Base neutra
                    "xgf": team.get('goalsFor', 0) / gp,
                    "xga": team.get('goalsAgainst', 0) / gp
                })
            
            print(f"✅ ¡Éxito! {len(stats_cleaned)} equipos sincronizados.")
            return stats_cleaned

        except Exception as e:
            print(f"❌ Error en el proceso de datos: {e}")
            return None

if __name__ == "__main__":
    scraper = NHLAdvancedScraper()
    res = scraper.get_advanced_stats()
    if res:
        print(f"Muestra confirmada: {res[0]['team_name']} | xGF/G: {round(res[0]['xgf'], 2)}")