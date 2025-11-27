# -*- coding: utf-8 -*-
import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Carrega variáveis do .env
load_dotenv()

# Logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# --- CONFIGURAÇÃO ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD")
CONSULTANT_EMAIL = os.environ.get("CONSULTANT_EMAIL")
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent"


app = FastAPI(title="Agente de IA THRIVE")

# Prompt
SYSTEM_PROMPT = "Você é um Consultor Sênior."
try:
    with open('Agente_IA_THRIVE_FINAL.txt', 'r', encoding='utf-8') as f:
        SYSTEM_PROMPT = f.read()
except FileNotFoundError:
    logging.warning("Arquivo de prompt não encontrado. Usando padrão.")


from fastapi.middleware.cors import CORSMiddleware

# CORS - Configuração COMPLETA
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção: ["https://seublog.com"]
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)


# --- MODELOS ---
class MDMPScore(BaseModel):
    nome_cliente: str
    email_cliente: str
    telefone_cliente: Optional[str] = None
    scores_por_pilar: Dict[str, float]
    total_avg: float


class ConsultiveReport(BaseModel):
    status: str
    gargalo_critico: str
    ponto_forte: str
    analise_ia: str
    media_geral: float


# --- LÓGICA DE ANÁLISE ---
def analyze_scores(scores: MDMPScore):
    """Calcula gargalo/ponto forte a partir do dicionário de scores do front-end."""
    
    # Lemos os scores do dicionário aninhado 'scores_por_pilar'
    data = scores.scores_por_pilar
    
    if not data:
        raise ValueError("Nenhum score de pilar encontrado na requisição.")
        
    media = sum(data.values()) / len(data)
    gargalo = min(data, key=data.get)
    forte = max(data, key=data.get)
    details = "\n".join([f"- {k.title()}: {v:.2f}" for k, v in data.items()])

    return {
        "gargalo_critico": gargalo.replace('_', ' ').title(),
        "ponto_forte": forte.replace('_', ' ').title(),
        "media_geral": media,
        "score_details": details,
        "raw_scores": data
    }


def generate_report(analysis_data: dict):
    """Chama o Agente de IA (Gemini) para gerar o relatório consultivo."""
    if not GEMINI_API_KEY:
        logging.error("Chave GEMINI_API_KEY não configurada no ambiente.")
        return "# Erro de Configuração\nO Agente de IA não está autenticado. Por favor, verifique a chave GEMINI_API_KEY."

    gargalo = analysis_data['gargalo_critico']
    
    # Criamos um prompt claro e direto, incluindo as regras THRIVE
    prompt = f"""
    Analise estes dados e gere o Relatório Consultivo Final (Markdown) seguindo todas as regras de estrutura THRIVE (Introdução, Desenvolvimento, Conclusão):
    ---
    Scores Detalhados: {analysis_data['score_details']}
    Gargalo Crítico: {gargalo} (Score {analysis_data['raw_scores'][gargalo.lower().replace(' ', '_')]:.2f})
    Média Global: {analysis_data['media_geral']:.2f}
    """

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]}
    }

    try:
        logging.info("Chamando Inteligência Artificial...")
        response = requests.post(
            f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
            headers={'Content-Type': 'application/json'},
            json=payload
        )
        response.raise_for_status()
        return response.json()['candidates'][0]['content']['parts'][0]['text']
    except requests.exceptions.HTTPError as e:
        logging.error(f"Erro HTTP na IA (Status: {e.response.status_code}): {e.response.text}")
        return f"# Erro na Geração\nO Agente de IA retornou uma falha de serviço. Status: {e.response.status_code}"
    except Exception as e:
        logging.error(f"Erro na IA: {e}")
        return f"# Erro na Geração\nNão foi possível gerar a análise detalhada. Erro: {e}"


def send_email(scores: MDMPScore, analysis: dict, report: str):
    """Envia a notificação para o consultor sênior da THRIVE."""
    if not SENDER_PASSWORD or not CONSULTANT_EMAIL:
        logging.warning("Configurações de e-mail incompletas. E-mail de lead não será enviado.")
        return

    subject = f"LEAD THRIVE - NOVO DIAGNÓSTICO: {analysis['gargalo_critico']} | {scores.nome_cliente}"
    body = f"""
    <html><body>
    <h1>Novo Diagnóstico Premium Realizado (Via PIX)</h1>
    <p><strong>Cliente:</strong> {scores.nome_cliente} ({scores.email_cliente})</p>
    <p><strong>Telefone:</strong> {scores.telefone_cliente or 'N/A'}</p>
    <hr>
    <p><strong>MÉDIA GERAL:</strong> {analysis['media_geral']:.2f}</p>
    <p><strong>GARGALO CRÍTICO:</strong> {analysis['gargalo_critico']}</p>
    
    <h3>Scores Detalhados:</h3>
    <ul>{analysis['score_details'].replace('-', '<li>').replace(':', ': <strong>').replace('\n', '</strong></li>')}</ul>
    <br>
    
    <h2>Relatório da IA (Conteúdo para o Cliente):</h2>
    <div style="border: 1px solid #ccc; padding: 15px; background: #f9f9f9; white-space: pre-wrap; font-family: monospace;">
        {report}
    </div>
    
    <br><p><strong>AÇÃO NECESSÁRIA:</strong> Verifique o extrato (PIX) e envie este relatório ao cliente por e-mail.</p>
    </body></html>
    """

    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = CONSULTANT_EMAIL
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'html'))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)
        server.quit()
        logging.info("E-mail de notificação enviado com sucesso!")
    except Exception as e:
        logging.error(f"Erro crítico ao enviar email de notificação: {e}")


# --- ROTAS DA API ---

@app.get("/")
def root():
    return {
        "message": "API Thrive Business está online 🚀",
        "status": "running",
        "docs": "/docs",
        "health": "/api/health"
    }

# Rota principal para o Front-end (Corresponde a https://thrive-api-rp07.onrender.com/diagnostico)
@app.post("/diagnostico", response_model=ConsultiveReport)
def diagnose(scores: MDMPScore):
    analysis = analyze_scores(scores)
    report = generate_report(analysis)
    
    # Envia o e-mail de notificação (que contém o relatório e os dados do cliente)
    send_email(scores, analysis, report)

    return {
        "status": "Sucesso",
        "gargalo_critico": analysis['gargalo_critico'],
        "ponto_forte": analysis['ponto_forte'],
        "analise_ia": report,
        "media_geral": analysis['media_geral']
    }


# Rota de health check — NECESSÁRIA no Render
@app.get("/api/health")
def health():
    return {"status": "ok", "service": "Thrive Business API"}

# --- RODAR LOCAL OU NO RENDER ---
# if __name__ == "__main__":
#     import uvicorn
#     print("Iniciando Servidor THRIVE...")
#     uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))

