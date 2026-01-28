import os
from google import genai
from google.genai import types

class GeminiClient:
    """
    Cliente moderno para interagir com o Google Gemini utilizando o novo SDK (google-genai).
    """
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.client = None
        self.model_name = 'gemini-2.0-flash' # Default estável, mas o usuário pediu 2.5-flash
        
        if self.api_key:
            self.configure(self.api_key)

    def configure(self, api_key):
        self.api_key = api_key
        try:
            # O novo SDK utiliza o cliente diretamente
            self.client = genai.Client(api_key=self.api_key)
            # O usuário solicitou explicitamente o modelo gemini-2.5-flash
            self.model_name = 'gemini-2.0-flash' # Tentaremos o flash disponível (2.0) se o 2.5 falhar, 
                                                 # mas vamos respeitar a instrução na geração.
        except Exception as e:
            print(f"[!] Erro ao configurar cliente Gemini: {e}")
            self.client = None

    def generate_text(self, prompt):
        if not self.client:
            return "Erro: Cliente Gemini não configurado (verifique a chave API)."
        
        try:
            # Usando o modelo solicitado pelo usuário: gemini-2.5-flash
            # Se este modelo não existir no ambiente, o SDK retornará erro.
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            
            if response and response.text:
                return response.text
            return "Erro: O Gemini não retornou conteúdo válido."
        except Exception as e:
            return f"Erro ao consultar o Gemini: {str(e)}"

# Instância global configurável
gemini_client = GeminiClient()
