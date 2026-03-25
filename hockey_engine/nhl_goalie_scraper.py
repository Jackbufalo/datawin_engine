import requests
from bs4 import BeautifulSoup
import time

class NHLGoalieScraper:
    def __init__(self):
        self.url = "https://www.dailyfaceoff.com/starting-goalies"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    def get_starting_goalies(self):
        print("🧤 Buscando porteros confirmados en DailyFaceoff...")
        try:
            response = requests.get(self.url, headers=self.headers, timeout=15)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Buscamos los contenedores de cada partido
            matchups = soup.find_all('div', class_='flex flex-col gap-4') # El selector puede variar ligeramente según el diseño del sitio
            
            goalie_data = []

            # Nota: DailyFaceoff estructura los porteros por pares (Home/Away)
            # Buscamos los nombres y el estatus (Confirmed/Likely)
            names = soup.find_all('article', class_='goalie-card') # Selector común en su estructura actual
            
            for card in names:
                name = card.find('h4').text.strip() if card.find('h4') else "Unknown"
                status_element = card.find('span', class_='status-label') # Ejemplo de clase de estatus
                status = status_element.text.strip() if status_element else "Likely"
                
                # Aquí también solemos encontrar el equipo
                team_div = card.find('div', class_='team-name')
                team = team_div.text.strip() if team_div else "TBD"

                goalie_data.append({
                    "goalie_name": name,
                    "team": team,
                    "status": status
                })

            print(f"✅ Se encontraron {len(goalie_data)} porteros en la lista.")
            return goalie_data

        except Exception as e:
            print(f"❌ Error al scrapear porteros: {e}")
            # Fallback: Si falla el scraping, el motor usará el promedio del equipo
            return []

if __name__ == "__main__":
    scraper = NHLGoalieScraper()
    goalies = scraper.get_starting_goalies()
    for g in goalies:
        print(f"Team: {g['team']} | Goalie: {g['goalie_name']} | Status: {g['status']}")