# -*- coding: utf-8 -*-
import os
import logging
import smtplib
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any, List
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

app = FastAPI(title="Agente de IA THRIVE (Híbrido)")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# --- MODELOS DE DADOS ---
class MDMPScore(BaseModel):
    nome_cliente: str
    email_cliente: str
    telefone_cliente: Optional[str] = None
    scores_por_pilar: Dict[str, float]
    total_avg: float
    respostas: Dict[str, int] = {} # Respostas detalhadas para análise profunda

class ConsultiveReport(BaseModel):
    status: str
    gargalo_critico: str
    ponto_forte: str
    analise_ia: str
    media_geral: float

# ==============================================================================
#  CÉREBRO DA THRIVE (BASE DE CONHECIMENTO)
# ==============================================================================

PERSONAS = {
    "estrategista": { "nome": "Sr. João da Terra", "papel": "O Estrategista", "frase": "Quem não planeia, planeia falhar." },
    "guardia": { "nome": "Dra. Clara Lex", "papel": "A Guardiã", "frase": "Segurança primeiro, lucro depois." },
    "hacker": { "nome": "K4J1 (Caju)", "papel": "O Hacker", "frase": "Automatize o tédio, foque no valor." }
}

# GATILHOS CIRÚRGICOS (Resposta = 1 -> Problema Grave)
REGRAS_GATILHO = {
    "p0_q0": { 1: { "peso": 9, "msg": "⚠️ **Crise de Identidade:** Sem Missão/Visão claras, a equipa não sabe para onde remar." } },
    "p0_q4": { 1: { "peso": 7, "msg": "🎯 **Público:** Vender para 'todos' é erro de principiante. Defina a sua Persona." } },
    "p0_q11": { 1: { "peso": 10, "msg": "💀 **Sucessão:** Se você faltar, a empresa para. Risco mortal para o negócio." } },
    "p1_q0": { 1: { "peso": 10, "msg": "🚨 **MISTURA PATRIMONIAL:** Pagar contas de casa com a empresa leva à falência." } },
    "p1_q4": { 1: { "peso": 9, "msg": "📉 **Cegueira de Caixa:** Sem controlo diário, você gere no escuro." } },
    "p1_q10": { 1: { "peso": 9, "msg": "⚖️ **Ponto de Equilíbrio:** Você não sabe a meta mínima para não ter prejuízo." } },
    "p2_q2": { 1: { "peso": 9, "msg": "🔗 **Centralização:** A operação depende 100% de você. Você é o gargalo." } },
    "p3_q0": { 1: { "peso": 8, "msg": "📉 **Funil Invisível:** Vendas acontecem por sorte, não por processo." } },
    "p5_q0": { 1: { "peso": 9, "msg": "🤝 **Risco Societário:** Acordo de sócios 'de boca' é bomba relógio." } },
    "p5_q4": { 1: { "peso": 10, "msg": "⚖️ **Passivo Trabalhista:** Colaboradores informais podem fechar a sua empresa." } },
    "p6_q2": { 1: { "peso": 10, "msg": "💾 **Risco de Dados:** Sem backup na nuvem, um vírus apaga a história da empresa." } }
}

# COMBINAÇÕES CRÍTICAS (Diagnóstico Cruzado)
COMBINACOES_CRITICAS = [
    {
        "nome": "BOMBA RELÓGIO FINANCEIRA",
        "condicoes": {"p1_q0": 1, "p1_q4": 1},
        "analise": "Cegueira financeira total + Mistura de património. Risco iminente de insolvência.",
        "venda": "BPO Financeiro Urgente"
    },
    {
        "nome": "EMPRESA-PRESÍDIO",
        "condicoes": {"p2_q2": 1, "p0_q11": 1},
        "analise": "O dono é refém do negócio. Sem ele, o faturamento zera.",
        "venda": "Mapeamento de Processos (Liberdade)"
    },
    {
        "nome": "RISCO DE RUÍNA JURÍDICA",
        "condicoes": {"p5_q4": 1, "p5_q0": 1},
        "analise": "Construído em areia movediça legal. Passivo oculto gigante.",
        "venda": "Auditoria de Blindagem"
    }
]

MACRO_PILARES = {
    "1. Estratégico": {"dor": "Falta de direção.", "acao": "Definir OKRs trimestrais.", "persona": "estrategista"},
    "2. Financeiro": {"dor": "Descontrolo de caixa.", "acao": "Implantar gestão financeira diária.", "persona": "guardia"},
    "3. Operacional": {"dor": "Ineficiência e dependência.", "acao": "Mapear processos críticos (POP).", "persona": "hacker"},
    "4. Comercial": {"dor": "Vendas imprevisíveis.", "acao": "Estruturar funil de vendas e CRM.", "persona": "estrategista"},
    "5. Pessoas (RH)": {"dor": "Equipa desengajada.", "acao": "Criar plano de cargos e rotina de feedback.", "persona": "guardia"},
    "6. Jurídico": {"dor": "Exposição a riscos.", "acao": "Audit e regularização de contratos.", "persona": "guardia"},
    "7. Tecnológico": {"dor": "Processos manuais.", "acao": "Transformação digital e segurança.", "persona": "hacker"}
}

# ==============================================================================
#  MOTOR DE INTELIGÊNCIA
# ==============================================================================

def analyze_data(scores: MDMPScore):
    """Processa os dados brutos e gera insights lógicos."""
    
    # 1. Estatísticas Básicas
    data = scores.scores_por_pilar
    if not data: raise HTTPException(status_code=400, detail="Sem scores")
    
    media = sum(data.values()) / len(data)
    gargalo_key = min(data, key=data.get)
    forte_key = max(data, key=data.get)
    
    # 2. Identificar Macro Pilar e Persona
    # Tenta dar match no nome do pilar (ex: "Financeiro" in "2. Financeiro")
    macro_key = next((k for k in MACRO_PILARES.keys() if gargalo_key in k or k in gargalo_key), "1. Estratégico")
    macro_info = MACRO_PILARES[macro_key]
    persona = PERSONAS[macro_info["persona"]]

    # 3. Processar Gatilhos (Prioridades)
    insights = []
    if scores.respostas:
        for q_id, resp in scores.respostas.items():
            if q_id in REGRAS_GATILHO and resp in REGRAS_GATILHO[q_id]:
                regra = REGRAS_GATILHO[q_id][resp]
                # Cálculo de Urgência: Peso do Problema + (10 - Nota do Pilar)
                idx_pilar = int(q_id.split('_')[0].replace('p', ''))
                nome_pilar = list(data.keys())[idx_pilar] if idx_pilar < len(data) else gargalo_key
                nota = data.get(nome_pilar, 5)
                urgencia = (regra['peso'] * 2) + (10 - nota)
                insights.append({"texto": regra['msg'], "urgencia": urgencia})
    
    # Ordena por urgência e pega top 4
    insights = sorted(insights, key=lambda x: x['urgencia'], reverse=True)[:4]
    lista_tarefas = "\n".join([f"- {item['texto']}" for item in insights]) if insights else f"- Foco total na estruturação do pilar {gargalo_key}."

    # 4. Processar Combinações Críticas (Briefing Consultor)
    alertas_consultor = []
    if scores.respostas:
        for combo in COMBINACOES_CRITICAS:
            match = True
            for q_id, val in combo["condicoes"].items():
                if scores.respostas.get(q_id) != val:
                    match = False
                    break
            if match:
                alertas_consultor.append(f"[{combo['nome']}] -> {combo['venda']}")

    briefing_texto = " | ".join(alertas_consultor) if alertas_consultor else "Cliente padrão (Upsell de melhoria)."

    return {
        "gargalo": gargalo_key,
        "forte": forte_key,
        "media": media,
        "persona_nome": persona["nome"],
        "persona_papel": persona["papel"],
        "frase": persona["frase"],
        "dor_macro": macro_info["dor"],
        "acao_macro": macro_info["acao"],
        "insights_prioritarios": lista_tarefas,
        "briefing": briefing_texto,
        "scores_raw": data
    }

# ==============================================================================
#  GERAÇÃO DE RELATÓRIO (HÍBRIDA)
# ==============================================================================

def generate_report(analise: dict, cliente_nome: str):
    """Tenta gerar com IA usando os dados processados. Se falhar, usa template."""
    
    # Template de Fallback (Garantia de entrega)
    relatorio_fallback = f"""
# Relatório de Diagnóstico THRIVE

**Cliente:** {cliente_nome}
**Média Geral:** {analise['media']:.2f}

## 🚨 Análise de Prioridades
O sistema identificou que o seu maior gargalo é o pilar **{analise['gargalo']}**.
Abaixo listamos os pontos críticos baseados nas suas respostas:

{analise['insights_prioritarios']}

## Plano de Ação Estratégico
Para destravar o crescimento, a metodologia Thrive recomenda:
1. **Ação Imediata:** {analise['acao_macro']}
2. **Foco:** Resolver a dor principal de "{analise['dor_macro']}".

> "{analise['frase']}"
**{analise['persona_nome']}** - *{analise['persona_papel']}*
"""

    # Se não tiver chave API, retorna logo o fallback
    if not GEMINI_API_KEY:
        return relatorio_fallback, "Modo Offline"

    # Prompt Enriquecido (RAG - Retrieval Augmented Generation)
    prompt = f"""
    Você é o Consultor Sênior da Thrive Business. Use os dados técnicos abaixo para escrever um relatório elegante e persuasivo em Markdown.
    
    DADOS TÉCNICOS DO CLIENTE:
    - Nome: {cliente_nome}
    - Média: {analise['media']:.2f}
    - Pior Pilar: {analise['gargalo']}
    - Persona Atribuída: {analise['persona_nome']} ({analise['persona_papel']})
    
    INSIGHTS REAIS ENCONTRADOS (Use estes factos, não invente):
    {analise['insights_prioritarios']}
    
    DIRETRIZES:
    1. Comece com um tom empático mas direto sobre a média geral.
    2. Apresente os "Insights Reais" como "Pontos de Atenção Imediata".
    3. Termine com a recomendação de ação: "{analise['acao_macro']}".
    4. Assine como {analise['persona_nome']}.
    """

    try:
        logging.info("Solicitando análise à IA...")
        response = requests.post(
            f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
            headers={'Content-Type': 'application/json'},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.7}
            },
            timeout=40 # Timeout maior para cold start
        )
        
        if response.status_code == 429:
            logging.warning("Cota da IA excedida (429). Usando Fallback.")
            return relatorio_fallback, "Fallback (Cota)"
            
        response.raise_for_status()
        return response.json()['candidates'][0]['content']['parts'][0]['text'], "IA Gerativa"

    except Exception as e:
        logging.error(f"Erro na IA: {e}. Usando Fallback.")
        return relatorio_fallback, f"Fallback (Erro: {str(e)[:20]})"

def send_email(scores: MDMPScore, analise: dict, report: str, modo_geracao: str):
    """Envia notificação para o consultor."""
    if not SENDER_PASSWORD or not CONSULTANT_EMAIL:
        return

    subject = f"LEAD {analise['gargalo'].upper()} | {scores.nome_cliente}"
    
    body = f"""
    <html><body>
    <h2>Novo Lead Processado ({modo_geracao})</h2>
    <p><strong>Cliente:</strong> {scores.nome_cliente}</p>
    <p><strong>Contato:</strong> {scores.email_cliente} | {scores.telefone_cliente}</p>
    <hr>
    <h3>BRIEFING ESTRATÉGICO (Para Vendas):</h3>
    <p style="background: #ffebee; padding: 10px; border-left: 5px solid #f44336;">
        <strong>{analise['briefing']}</strong>
    </p>
    <hr>
    <h3>Relatório Enviado ao Cliente:</h3>
    <div style="background:#f4f4f4; padding:15px; font-size:12px; white-space: pre-wrap;">
        {report}
    </div>
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
    except Exception as e:
        logging.error(f"Erro no email: {e}")

# ==============================================================================
#  ROTAS DA API
# ==============================================================================

@app.get("/")
def root():
    return {"status": "Thrive Intelligence Online", "version": "3.0 Hybrid"}

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.post("/diagnostico", response_model=ConsultiveReport)
def diagnose(scores: MDMPScore):
    # 1. Inteligência Lógica (Rápida e Gratuita)
    analise = analyze_data(scores)
    
    # 2. Geração de Texto (Tenta IA, cai para Lógica se falhar)
    relatorio_final, modo = generate_report(analise, scores.nome_cliente)
    
    # 3. Notificação em Background
    send_email(scores, analise, relatorio_final, modo)

    return {
        "status": "Sucesso",
        "gargalo_critico": analise['gargalo'].replace('_', ' ').title(),
        "ponto_forte": analise['forte'].replace('_', ' ').title(),
        "analise_ia": relatorio_final,
        "media_geral": analise['media']
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
