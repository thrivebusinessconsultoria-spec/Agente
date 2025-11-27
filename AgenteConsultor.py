# -*- coding: utf-8 -*-
import os
import logging
import random
from typing import Optional, Dict, Any
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
CONSULTANT_EMAIL = os.environ.get("CONSULTANT_EMAIL")

# Configuração RESEND (E-mail Transacional)
# Chave fornecida pelo utilizador. Em produção, recomenda-se mover para variáveis de ambiente.
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "re_UqFhqRQj_FnZnaGkNfzqFbP5f24xRHY5t")
RESEND_API_URL = "https://api.resend.com/emails"

# Configuração IA
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent"

app = FastAPI(title="Agente de IA THRIVE (Com Contingência)")

# Prompt do Sistema
SYSTEM_PROMPT = "Você é um Consultor Sênior."
try:
    with open('Agente_IA_THRIVE_FINAL.txt', 'r', encoding='utf-8') as f:
        SYSTEM_PROMPT = f.read()
except FileNotFoundError:
    logging.warning("Arquivo de prompt não encontrado. Usando padrão interno.")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MODELOS DE DADOS ---
class MDMPScore(BaseModel):
    nome_cliente: str
    email_cliente: str
    telefone_cliente: Optional[str] = None
    scores_por_pilar: Dict[str, float]
    total_avg: float
    respostas: Optional[Dict[str, int]] = {}

class ConsultiveReport(BaseModel):
    status: str
    gargalo_critico: str
    ponto_forte: str
    analise_ia: str
    media_geral: float

# --- CÉREBRO DE CONTINGÊNCIA (Lógica Local) ---
CONSELHOS_BACKUP = {
    "1. Estratégico": {"dor": "Falta de direção clara.", "acao": "Definir OKRs trimestrais.", "persona": "Sr. João da Terra"},
    "2. Financeiro": {"dor": "Descontrolo de caixa.", "acao": "Implantar gestão financeira diária.", "persona": "Dra. Clara Lex"},
    "3. Operacional": {"dor": "Ineficiência e dependência.", "acao": "Mapear processos críticos (POP).", "persona": "K4J1"},
    "4. Comercial": {"dor": "Vendas imprevisíveis.", "acao": "Estruturar funil de vendas e CRM.", "persona": "Sr. João da Terra"},
    "5. Pessoas (RH)": {"dor": "Equipa desengajada.", "acao": "Criar plano de cargos e rotina de feedback.", "persona": "Dra. Clara Lex"},
    "6. Jurídico": {"dor": "Exposição a riscos legais.", "acao": "Audit e regularização de contratos.", "persona": "Dra. Clara Lex"},
    "7. Tecnológico": {"dor": "Processos manuais lentos.", "acao": "Transformação digital e segurança.", "persona": "K4J1"}
}

def generate_fallback_report(analysis_data: dict) -> str:
    """Gera um relatório baseado em regras se a IA falhar."""
    gargalo = analysis_data['gargalo_critico']
    
    chave_pilar = next((k for k in CONSELHOS_BACKUP.keys() if gargalo in k or k in gargalo), "1. Estratégico")
    dados_backup = CONSELHOS_BACKUP.get(chave_pilar, CONSELHOS_BACKUP["1. Estratégico"])
    
    return f"""
# Relatório Consultivo Final: {gargalo} (Modo Técnico)

**Nota:** Devido à alta demanda nos nossos servidores de IA, este relatório foi gerado pelo nosso Sistema Especialista de Contingência.

## Diagnóstico de Maturidade por Pilares (MDMP)
A sua média geral é **{analysis_data['media_geral']:.2f}**.
O ponto forte identificado é **{analysis_data['ponto_forte']}**.

## O Gargalo Crítico: Pilar {gargalo}
Classificação: **Prioridade Máxima**
O Diagnóstico Técnico indica: {dados_backup['dor']}

### Principais Causas Prováveis
1. Falta de processos definidos nesta área.
2. Ausência de indicadores de performance (KPIs).
3. Baixa priorização na rotina de gestão.

## Plano de Ação Imediato
| Ação Tática | Objetivo | Impacto Esperado |
| :--- | :--- | :--- |
| **1. {dados_backup['acao']}** | Estancar a ineficiência raiz. | Recuperação imediata de controlo. |
| **2. Ritual de Gestão** | Monitorizar este pilar semanalmente. | Cultura de melhoria contínua. |
| **3. Capacitação** | Treinar a equipa responsável. | Autonomia operacional. |

**Conclusão do Consultor Sênior THRIVE:**
"A consistência precede a excelência. Resolva o básico do pilar {gargalo} antes de tentar escalar."
"""

# --- LÓGICA PRINCIPAL ---

def analyze_scores(scores: MDMPScore):
    """Calcula estatísticas básicas."""
    data = scores.scores_por_pilar
    
    if not data:
        raise HTTPException(status_code=400, detail="Nenhum score fornecido")
    
    media = sum(data.values()) / len(data)
    gargalo = min(data, key=data.get)
    forte = max(data, key=data.get)
    
    details = "\n".join([f"- {k}: {v:.2f}" for k, v in data.items()])

    return {
        "gargalo_critico": gargalo,
        "gargalo_display": gargalo.replace('_', ' ').title(),
        "ponto_forte": forte.replace('_', ' ').title(),
        "media_geral": media,
        "score_details": details,
        "raw_scores": data
    }

def generate_report(analysis_data: dict):
    """Tenta Gemini primeiro, cai para Fallback se der erro."""
    if not GEMINI_API_KEY:
        logging.warning("Sem chave Gemini. Usando Fallback.")
        return generate_fallback_report(analysis_data)

    prompt = f"""
    Analise estes dados e gere o Relatório Consultivo Final (Markdown):
    Scores Detalhados: {analysis_data['score_details']}
    Gargalo Crítico: {analysis_data['gargalo_display']} (Score {analysis_data['raw_scores'][analysis_data['gargalo_critico']]:.2f})
    Média Global: {analysis_data['media_geral']:.2f}
    """

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]}
    }

    try:
        logging.info("Tentando conectar com IA Gemini...")
        response = requests.post(
            f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
            headers={'Content-Type': 'application/json'},
            json=payload,
            timeout=30
        )
        
        if response.status_code == 429:
            logging.warning("Cota da IA excedida. Usando Fallback.")
            return generate_fallback_report(analysis_data)

        response.raise_for_status()
        return response.json()['candidates'][0]['content']['parts'][0]['text']

    except Exception as e:
        logging.error(f"Falha na IA ({str(e)}). Ativando MODO DE CONTINGÊNCIA.")
        return generate_fallback_report(analysis_data)

def send_email_resend(scores: MDMPScore, analysis: dict, report: str):
    """Envia notificação por e-mail usando a API da Resend (Funciona no Render)."""
    if not RESEND_API_KEY:
        logging.warning("Chave RESEND não configurada.")
        return

    # Destinatário: Usa o email do consultor ou um fallback seguro
    to_email = CONSULTANT_EMAIL if CONSULTANT_EMAIL else "thrivebusinessconsultoria@gmail.com"
    
    subject = f"LEAD THRIVE: {analysis['gargalo_display']} | {scores.nome_cliente}"
    html_report = report.replace('\n', '<br>').replace('**', '<b>').replace('__', '</b>')
    
    body_html = f"""
    <html><body>
    <h2>Novo Diagnóstico Realizado</h2>
    <p><strong>Cliente:</strong> {scores.nome_cliente} ({scores.email_cliente})</p>
    <p><strong>Contato:</strong> {scores.telefone_cliente or 'N/A'}</p>
    <hr>
    <p><strong>Média:</strong> {analysis['media_geral']:.2f} | <strong>Gargalo:</strong> {analysis['gargalo_display']}</p>
    <div style="background:#f4f4f4; padding:15px; border-radius:5px;">
        {html_report}
    </div>
    </body></html>
    """

    payload = {
        "from": "onboarding@resend.dev", # Domínio padrão da Resend (funciona sem configuração DNS)
        "to": [to_email],
        "subject": subject,
        "html": body_html
    }

    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        logging.info("Enviando e-mail via Resend...")
        response = requests.post(RESEND_API_URL, json=payload, headers=headers)
        
        if response.status_code == 200:
            logging.info("E-mail enviado com sucesso!")
        else:
            logging.error(f"Erro Resend: {response.status_code} - {response.text}")
            
    except Exception as e:
        logging.error(f"Erro crítico ao enviar email: {e}")

# --- ROTAS ---

@app.get("/")
def root():
    return {"status": "Thrive API Online", "mode": "Hybrid (AI + Fallback + Resend)"}

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.post("/diagnostico", response_model=ConsultiveReport)
def diagnose(scores: MDMPScore):
    analysis = analyze_scores(scores)
    final_report = generate_report(analysis)
    
    # Envia e-mail usando a nova função da Resend
    send_email_resend(scores, analysis, final_report)

    return {
        "status": "Sucesso",
        "gargalo_critico": analysis['gargalo_display'],
        "ponto_forte": analysis['ponto_forte'],
        "analise_ia": final_report,
        "media_geral": analysis['media_geral']
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
