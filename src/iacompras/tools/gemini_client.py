import os
import google.generativeai as genai

class GeminiClient:
    """
    Cliente base para interagir com o Google Gemini.
    """
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = None
        
        if self.api_key:
            self.configure(self.api_key)

    def configure(self, api_key):
        self.api_key = api_key
        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-2.5-flash')
        except Exception as e:
            print(f"[!] Erro ao configurar Gemini: {e}")
            self.model = None

    def generate_text(self, prompt):
        if not self.model:
            return "Resumo inteligente indisponível (chave de API não configurada)."
        
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Erro ao consultar o Gemini: {str(e)}"

# Instância global configurável
gemini_client = GeminiClient()
