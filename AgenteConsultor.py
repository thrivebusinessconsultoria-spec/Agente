# -*- coding: utf-8 -*-
import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Union, Optional
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env
load_dotenv()

# Configuração de Logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

app = FastAPI(title="Agente de IA THRIVE")
@app.get("/")
def root():
    return {
        "message": "API Thrive Business está online 🚀",
        "status": "running",
        "docs": "http://127.0.0.1:8000/docs",
        "health": "http://127.0.0.1:8000/api/health"
    }


# --- CONFIGURAÇÃO (Lê do .env) ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD")
CONSULTANT_EMAIL = os.environ.get("CONSULTANT_EMAIL")
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent"

# Carrega o Prompt
SYSTEM_PROMPT = "Você é um Consultor Sênior."
try:
    with open('Agente_IA_THRIVE_FINAL.txt', 'r', encoding='utf-8') as f:
        SYSTEM_PROMPT = f.read()
except FileNotFoundError:
    logging.warning("Arquivo de prompt não encontrado. Usando padrão.")

# Configuração CORS (Para o Blog funcionar)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite qualquer origem para facilitar o teste
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- MODELOS ---
class ClientContact(BaseModel):
    nome_cliente: str
    email_cliente: str
    telefone_cliente: Optional[str] = None


class MDMPScore(ClientContact):
    estrategico: float
    financeiro: float
    operacional: float
    comercial: float
    pessoas_rh: float
    juridico: float
    tecnologico: float


class ConsultiveReport(BaseModel):
    status: str
    gargalo_critico: str
    ponto_forte: str
    analise_ia: str
    media_geral: float


# --- LÓGICA ---
def analyze_scores(scores: MDMPScore):
    data = scores.model_dump(exclude={'nome_cliente', 'email_cliente', 'telefone_cliente'})
    media = sum(data.values()) / len(data)
    gargalo = min(data, key=data.get)
    forte = max(data, key=data.get)
    details = "\n".join([f"- {k.title()}: {v}" for k, v in data.items()])

    return {
        "gargalo_critico": gargalo.title(),
        "ponto_forte": forte.title(),
        "media_geral": media,
        "score_details": details,
        "raw_scores": data
    }


def generate_report(analysis_data):
    gargalo = analysis_data['gargalo_critico']
    score = analysis_data['raw_scores'][gargalo.lower()]

    prompt = f"""
    Analise estes dados e gere o Relatório Consultivo Final (Markdown):
    ---
    Scores: {analysis_data['score_details']}
    Gargalo: {gargalo} (Score {score})
    Média: {analysis_data['media_geral']:.2f}
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
    except Exception as e:
        logging.error(f"Erro na IA: {e}")
        return f"# Erro na Geração\nNão foi possível gerar a análise detalhada. Erro: {e}"


def send_email(scores, analysis, report):
    if not SENDER_PASSWORD: return

    subject = f"LEAD THRIVE: {analysis['gargalo_critico']} | {scores.nome_cliente}"
    body = f"""
    <h1>Novo Diagnóstico Realizado</h1>
    <p><strong>Cliente:</strong> {scores.nome_cliente} ({scores.email_cliente})</p>
    <p><strong>Telefone:</strong> {scores.telefone_cliente}</p>
    <hr>
    <p><strong>Gargalo Crítico:</strong> {analysis['gargalo_critico']}</p>
    <br>
    <h3>Relatório da IA:</h3>
    <pre>{report}</pre>
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
        logging.info("E-mail de notificação enviado!")
    except Exception as e:
        logging.error(f"Erro ao enviar email: {e}")


@app.post("/api/diagnose", response_model=ConsultiveReport)
def diagnose(scores: MDMPScore):
    analysis = analyze_scores(scores)
    report = generate_report(analysis)
    send_email(scores, analysis, report)

    return {
        "status": "Sucesso",
        "gargalo_critico": analysis['gargalo_critico'],
        "ponto_forte": analysis['ponto_forte'],
        "analise_ia": report,
        "media_geral": analysis['media_geral']
    }


# --- ESTA PARTE PERMITE RODAR NO PYCHARM ---
if __name__ == "__main__":
    print("Iniciando Servidor THRIVE...")
    # Roda o servidor na porta 8000
    uvicorn.run(app, host="127.0.0.1", port=8000)