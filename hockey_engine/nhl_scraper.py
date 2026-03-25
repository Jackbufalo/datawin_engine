import requests
import pandas as pd

class NHLScraper:
    def __init__(self):
        self.base_url = "https://api-web.nhle.com/v1" # API oficial moderna de la NHL

    def get_todays_schedule(self):
        """Obtiene los partidos programados para hoy"""
        response = requests.get(f"{self.base_url}/schedule/now")
        data = response.json()
        games = data['gameWeek'][0]['games']
        return games

    def get_team_advanced_stats(self, team_abbr):
        """
        Aquí conectarías con una fuente de Corsi/Fenwick. 
        Como ejemplo, devolvemos un diccionario con valores reales 
        que podrías extraer de NaturalStatTrick o MoneyPuck.
        """
        # Nota: En una versión avanzada, aquí usarías BeautifulSoup 
        # para scrapear NaturalStatTrick.com
        return {
            "cf_pct": 0.521, # 52.1% de Corsi
            "ff_pct": 0.515,
            "att_rating": 1.05,
            "def_rating": 0.98
        }

    def get_confirmed_goalies(self):
        """
        Scrapea DailyFaceoff para saber quién inicia en la portería.
        """
        # Este es el 'Santo Grial' de las apuestas de NHL.
        # Por ahora, devolvemos un fallback por defecto.
        return "Standard Starter"