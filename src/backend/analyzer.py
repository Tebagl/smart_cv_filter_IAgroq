"""
================================================================================
SMART CV FILTER - AI ANALYZER ENGINE (GROQ CLOUD)
================================================================================
Author: Tebagl
Date: April 2026
Version: 2.0 (Cloud Migration)

Description:
Core analysis module that interfaces with Groq's LPU™ infrastructure. 
This engine processes raw CV text against job descriptions using 
Llama-3.1-8b-instant to provide objective scoring and justification.

TECHNICAL SPECIFICATIONS:
- Provider: Groq Cloud API
- Model: llama-3.1-8b-instant
- Response Format: Strict JSON (score, apto, motivo)
- Temperature: 0.0 (Deterministic output for consistency)

SECURITY & PRIVACY:
- API keys are loaded via environment variables (.env) to prevent leaks.
- No local LLM overhead: Offloads processing to remote inference.
- Data handled via encrypted HTTPS requests.

DATA FLOW:
1. Load API Key -> 2. Construct Prompt -> 3. POST Request -> 4. JSON Parse
================================================================================
"""

import requests
import json
import os
from dotenv import load_dotenv
from pathlib import Path

class CVAnalyzer:
    def __init__(self):
        # 1. Intentar cargar el .env con ruta absoluta dentro del init
        # Localización robusta: subimos dos niveles desde src/backend a la raíz
        script_dir = Path(__file__).resolve().parent
        dotenv_path = script_dir.parent.parent / 'conf.env'
        
        load_dotenv(dotenv_path=dotenv_path)
        
        raw_key = os.getenv("GROQ_API_KEY")
        self.api_key = raw_key.strip() if raw_key else None
        
        self.url = "https://api.groq.com/openai/v1/chat/completions"
        self.model = "llama-3.1-8b-instant"
        
        # 3. Inicializar headers
        self.headers = {
            "Content-Type": "application/json"
        }
        if self.api_key:
            self.headers["Authorization"] = f"Bearer {self.api_key}"

        # 3. DEFINICIÓN DE LA PLANTILLA
        self.prompt_template = """
        Misión: Actúa como un reclutador profesional para evaluar la idoneidad del candidato para el puesto: {job_description}.
        
        ANÁLISIS DE COHERENCIA PROFESIONAL:
        1. PESO DE LA TRAYECTORIA: Valora el historial completo del candidato. Una experiencia sólida de más de 10 años en las competencias requeridas por el puesto es un activo de alto valor.
        
        2. FACTOR DE DESCONEXIÓN ACTUAL: Analiza si el candidato está actualmente en un proceso de cambio de carrera (estudiando o trabajando en algo totalmente ajeno a la vacante).
           - REGLA: Si el candidato tiene gran experiencia pasada en el sector de la vacante, pero su presente indica una reorientación activa hacia otra industria, resta entre 15 y 20 puntos al score.
           - MOTIVO: Estos perfiles son "Transicionales". Tienen el conocimiento, pero su interés profesional actual está en otro lugar. Deben ser validados manualmente.

        3. AJUSTE DE NIVEL:
           - Para puestos de entrada (Junior/Ayudante): Prioriza formación reciente y actitud.
           - Para puestos especialistas: Prioriza experiencia técnica demostrable.

        ESCALAS DE PUNTUACIÓN:
        - 85-100: PERFIL ACTIVO. Coincidencia total entre su situación actual, su formación y el puesto.
        - 60-84: PERFIL TRANSICIONAL O CON LAGUNAS (DUDAS). Posee las capacidades técnicas por su pasado, pero su situación actual genera dudas sobre su permanencia o foco.
        - 0-59: PERFIL NO ALINEADO. Falta de competencias base o trayectoria totalmente ajena.

        Responde en JSON:
        {{
          "score": número,
          "apto": "SI" o "NO",
          "motivo": "Explica la relación entre la trayectoria pasada del candidato y su situación profesional presente respecto a la vacante."
        }}

        TEXTO DEL CV (ANONIMIZADO):
        {cv_text}
        """


    def set_api_key(self, api_key):
        """Actualiza la clave y los headers para las peticiones."""
        if api_key:
            self.api_key = api_key.strip()
            # Esta línea es la que permite que la conexión funcione tras meterla en el popup
            self.headers["Authorization"] = f"Bearer {self.api_key}"
            print("✅ Analyzer: API Key actualizada correctamente.")
            return True # Indicamos que todo salió bien
        else:
            print("❌ Error: Se intentó configurar una API Key vacía o inválida.")
            return False # Indicamos que hubo un fallo


    def analyze(self, cv_text, job_description):
        # Usamos self.prompt_template que definimos en el __init__
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": "Eres un reclutador experto que responde solo en JSON."},
                {"role": "user", "content": self.prompt_template.format(cv_text=cv_text, job_description=job_description)}
            ],
            "temperature": 0.1 
        }

        try:
            response = requests.post(self.url, headers=self.headers, json=payload, timeout=20)
            if response.status_code == 200:
                # Retornamos el contenido si la respuesta es exitosa
                return response.json()['choices'][0]['message']['content']
            else:
                # Si hay error de API (ej. 401, 429), devolvemos string vacío para evitar el NoneType
                print(f"❌ Error API Groq: {response.status_code} - {response.text}")
                return "" 
        except Exception as e:
            # Si hay error de conexión o timeout, devolvemos string vacío
            print(f"❌ Error de conexión: {e}")
            return ""
        
        #traza
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            # ESTA LÍNEA ES CLAVE: Mira tu terminal cuando ejecutes
            print(f"DEBUG GROQ ERROR: {response.status_code} -> {response.text}") 
            return ""