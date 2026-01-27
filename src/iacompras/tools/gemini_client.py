import os
import google.generativeai as genai

class GeminiClient:
    """
    Cliente base para interagir com o Google Gemini.
    """
    def __init__(self):
        # A chave deve ser passada como string ou lida de variável de ambiente. 
        # Notei que você tentou colocar a chave diretamente no os.getenv.
        self.api_key = os.getenv("AIzaSyByfvE59iOhxXsKsltsM2FHMp2Cedqy3QA")
        
        if not self.api_key:
            print("[!] Aviso: GEMINI_API_KEY não encontrada.")
            self.model = None
        else:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-2.5-flash')

    def generate_text(self, prompt):
        if not self.model:
            return "Resumo inteligente indisponível (chave de API não encontrada)."
        
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Erro ao consultar o Gemini: {str(e)}"

# Instância global para ser usada pelos agentes e orquestrador
gemini_client = GeminiClient()
