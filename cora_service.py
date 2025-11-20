import requests
import json
import os

class CoraService:
    # --- Configurações CORA ---
    # ATENÇÃO: VOCÊ PRECISA OBTER E INSERIR ESTAS CREDENCIAIS NO SEU AMBIENTE RENDER
    CLIENT_ID = os.environ.get("CORA_CLIENT_ID", "SEU_CLIENT_ID_AQUI")
    CLIENT_SECRET = os.environ.get("CORA_CLIENT_SECRET", "SEU_CLIENT_SECRET_AQUI")
    BASE_URL = "https://api.cora.com.br/v1" 
    
    @staticmethod
    def authenticate():
        # TODO: Implementar a lógica de autenticação OAuth 2.0
        # Requisitar o token de acesso (Bearer Token) usando o Client ID e Secret.
        try:
            response = requests.post(
                "https://auth.cora.com.br/token",
                auth=(CoraService.CLIENT_ID, CoraService.CLIENT_SECRET),
                data={"grant_type": "client_credentials"}
            )
            response.raise_for_status() # Lança exceção para erros HTTP
            return response.json().get("access_token")
        except requests.exceptions.RequestException as e:
            print(f"Erro na autenticação Cora: {e}")
            return None

    @staticmethod
    def generate_pix_qr_code(valor: float, nome: str):
        # 1. Autenticar para obter o token
        token = CoraService.authenticate()
        if not token:
            return "Erro: Falha na autenticação com a Cora."

        # 2. Construir o Payload da Cobrança PIX
        # (Este payload é um exemplo e precisa ser validado com a documentação da Cora)
        pix_payload = {
            "chave": "thrivebusinessconsultoria@gmail.com",
            "valor": f"{valor:.2f}",
            "nome": nome,
            "descricao": "Diagnóstico de Maturidade THRIVE",
            "tipo_cobranca": "ESTATICA",
            # Adicione um ID único para rastreamento (ex: UUID)
            "id_rastreamento": "THRIVE-" + str(hash(nome)) 
        }

        # 3. Enviar a requisição para a Cora
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(
                f"{CoraService.BASE_URL}/pix-cob",
                headers=headers,
                data=json.dumps(pix_payload)
            )
            response.raise_for_status()
            
            # TODO: Retornar o link ou base64 do QR Code da resposta da Cora
            return response.json().get("qr_code_base64") 
            
        except requests.exceptions.RequestException as e:
            print(f"Erro na emissão do PIX: {e}")
            return "Erro: Não foi possível emitir o QR Code dinâmico."
