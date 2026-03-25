import numpy as np
import pandas as pd
from scipy.stats import poisson
from scipy.special import iv # Función de Bessel para Skellam
from supabase import create_client

class HockeyEngine:
    def __init__(self, supabase_url, supabase_key):
        """
        Inicializa el motor de hockey. 
        Recibe las credenciales desde el orquestador (main_nhl.py).
        """
        self.supabase = create_client(supabase_url, supabase_key)
        self.league_avg_goals = 3.12 # Promedio NHL 2024-2026
        self.league_avg_save_pct = 0.905 # Media actual de porteros

    def get_skellam_prob(self, l1, l2, side='home'):
        """
        Calcula la probabilidad de victoria usando la diferencia de goles (Skellam).
        """
        # Probabilidad de empate (k=0) en tiempo regular
        prob_draw = np.exp(-(l1 + l2)) * iv(0, 2 * np.sqrt(l1 * l2))
        
        # Probabilidad de que local gane (k > 0)
        prob_home_win = sum([
            np.exp(-(l1 + l2)) * (l1 / l2)**(k / 2) * iv(k, 2 * np.sqrt(l1 * l2))
            for k in range(1, 15) # Aumentado a 15 para mayor precisión
        ])
        
        # Ajuste para Moneyline (elimina la posibilidad de empate del cálculo)
        total_no_draw = 1 - prob_draw
        if total_no_draw <= 0: return 50.0 # Fallback de seguridad
        
        if side == 'home':
            return (prob_home_win / total_no_draw) * 100
        return ((total_no_draw - prob_home_win) / total_no_draw) * 100

    def calculate_game(self, game_data):
        """
        Realiza el cálculo híbrido: Poisson Bivariada + Corsi + Goalie Factor.
        """
        # 1. Base Lambdas usando Regresión Log-Lineal (Simplificada)
        l1 = self.league_avg_goals * game_data['h_att'] * game_data['a_def']
        l2 = self.league_avg_goals * game_data['a_att'] * game_data['h_def']

        # 2. Ajuste por Posesión (Corsi/Fenwick)
        # Normalizamos la influencia del Corsi (CF% de 50% es factor 1.0)
        corsi_factor_h = game_data['h_cf_pct'] / 0.50
        corsi_factor_a = game_data['a_cf_pct'] / 0.50
        l1 *= corsi_factor_h
        l2 *= corsi_factor_a

        # 3. Ajuste por Portero (Goalie Factor)
        # El portero local afecta los goles que mete el visitante y viceversa
        l1 *= (1 - (game_data['a_goalie_pct'] - self.league_avg_save_pct))
        l2 *= (1 - (game_data['h_goalie_pct'] - self.league_avg_save_pct))

        # 4. Cálculo de Probabilidades de victoria (Skellam)
        prob_h = self.get_skellam_prob(l1, l2, 'home')
        prob_a = 100 - prob_h

        # 5. Matriz de Probabilidad para Over/Under 5.5
        prob_over = 0
        for i in range(10): # Goles Home
            for j in range(10): # Goles Away
                if (i + j) > 5.5:
                    prob_over += poisson.pmf(i, l1) * poisson.pmf(j, l2)

        return {
            "l1": round(l1, 2),
            "l2": round(l2, 2),
            "prob_h": round(prob_h, 2),
            "prob_a": round(prob_a, 2),
            "prob_o": round(prob_over * 100, 2)
        }

# --- ARCHIVO LISTO PARA SER IMPORTADO ---
# No añadir ejecuciones directas aquí para evitar errores de conexión.