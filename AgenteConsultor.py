# -*- coding: utf-8 -*-
import os
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
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
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "re_UqFhqRQj_FnZnaGkNfzqFbP5f24xRHY5t")
RESEND_API_URL = "https://api.resend.com/emails"
# Usa o modelo estável 1.5-flash
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

app = FastAPI(title="Agente de IA THRIVE (Consultor Sênior Final)")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
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

MACRO_PILARES = {
    "1. Estratégico": {"dor": "Falta de direção estratégica.", "acao": "Definir OKRs trimestrais.", "persona": "estrategista"},
    "2. Financeiro": {"dor": "Descontrolo de caixa e risco de ruína.", "acao": "Implantar gestão financeira diária (Caixa Zero).", "persona": "guardia"},
    "3. Operacional": {"dor": "Ineficiência e dependência dos sócios.", "acao": "Mapear processos críticos (POP).", "persona": "hacker"},
    "4. Comercial": {"dor": "Vendas imprevisíveis e dependentes de sorte.", "acao": "Estruturar funil de vendas e CRM.", "persona": "estrategista"},
    "5. Pessoas (RH)": {"dor": "Equipa desengajada ou alta rotatividade.", "acao": "Criar plano de cargos e rotina de feedback.", "persona": "guardia"},
    "6. Jurídico": {"dor": "Exposição a riscos legais e passivos.", "acao": "Audit e regularização de contratos.", "persona": "guardia"},
    "7. Tecnológico": {"dor": "Processos manuais lentos e inseguros.", "acao": "Transformação digital e segurança.", "persona": "hacker"}
}

# ==============================================================================
#  MOTOR DE INTELIGÊNCIA (LÓGICA AVANÇADA)
# ==============================================================================

def analyze_cross_patterns(scores_map: Dict[str, float]) -> List[Dict[str, str]]:
    """Analisa CAUSA RAIZ e correlações complexas (Sintoma vs Causa)."""
    insights = []
    
    # Normaliza notas para escala 0-10 para facilitar a lógica
    def get_score(key_part):
        for k, v in scores_map.items():
            if key_part.lower() in k.lower():
                return v * 3.33 
        return 0

    fin = get_score('financeiro')
    pes = get_score('pessoas')
    est = get_score('estratégico')
    proc = get_score('operacional')
    vend = get_score('comercial')
    jur = get_score('jurídico')

    # 1. SINTOMA: Vendas Baixas + CAUSA RAIZ: Margem (Financeiro)
    if vend <= 5 and fin <= 4:
        insights.append({
            "perfil": "⚠️ Venda sem Margem",
            "analise": "O seu problema não é só vender, é lucrar. A baixa margem força descontos agressivos, destruindo o caixa.",
            "risco": "Margem de Contribuição Negativa (Pagar para vender).",
            "recomendacao": "Engenharia Financeira e Revisão de Precificação."
        })

    # 2. Cenário "Empresa Rica, Gestão Pobre"
    if fin >= 7 and pes <= 4:
        insights.append({
            "perfil": "⚠️ Caixa Forte, Cultura Frágil",
            "analise": "A sua empresa gera caixa, mas falha em reter quem gera esse resultado. O dinheiro hoje mascara a ineficiência.",
            "risco": "Perda de capital intelectual e dependência de mercenários.",
            "recomendacao": "Programa de Retenção de Talentos e Mentoria de Liderança."
        })

    # 3. Cenário "O Visionário Caótico"
    if est >= 7 and proc <= 4:
        insights.append({
            "perfil": "⚠️ Visionário sem Processo",
            "analise": "Você sabe onde quer chegar, mas a operação não aguenta o tranco. Tudo está centralizado na sua cabeça.",
            "risco": "Gargalo do fundador (Burnout) e inconsistência na entrega.",
            "recomendacao": "Mapeamento de Processos (POPs) e Automação Operacional."
        })

    # 4. Cenário "O Vendedor Solitário"
    if vend >= 7 and (jur <= 4 or fin <= 4):
        insights.append({
            "perfil": "⚠️ Gigante de Pés de Barro",
            "analise": "Excelente tração comercial, mas retaguarda perigosa. Acelerando um carro sem freios.",
            "risco": "Passivo oculto (trabalhista/tributário) ou descontrole de custos.",
            "recomendacao": "Blindagem Jurídica e BPO Financeiro."
        })

    return insights

def analyze_data(scores: MDMPScore):
    """Processa dados e gera estratégia."""
    data = scores.scores_por_pilar
    if not data: raise HTTPException(status_code=400, detail="Sem scores")
    
    media = sum(data.values()) / len(data)
    gargalo_key = min(data, key=data.get)
    forte_key = max(data, key=data.get)
    
    macro_key = next((k for k in MACRO_PILARES.keys() if gargalo_key in k or k in gargalo_key), "1. Estratégico")
    macro_info = MACRO_PILARES[macro_key]
    persona = PERSONAS[macro_info["persona"]]

    # Gatilhos Simples
    insights = []
    if scores.respostas:
        for q_id, resp in scores.respostas.items():
            if q_id in REGRAS_GATILHO and resp in REGRAS_GATILHO[q_id]:
                regra = REGRAS_GATILHO[q_id][resp]
                idx_pilar = int(q_id.split('_')[0].replace('p', ''))
                # Tenta buscar nome do pilar com segurança
                try:
                    nome_pilar = list(data.keys())[idx_pilar]
                except IndexError:
                    nome_pilar = gargalo_key
                
                nota = data.get(nome_pilar, 5)
                urgencia = (regra['peso'] * 2) + (10 - (nota * 3.33))
                insights.append({"texto": regra['msg'], "urgencia": urgencia})
    
    insights = sorted(insights, key=lambda x: x['urgencia'], reverse=True)[:4]
    
    # Lógica Cruzada
    analise_cruzada = analyze_cross_patterns(data)
    texto_cruzado = ""
    briefing_cruzado = ""
    if analise_cruzada:
        texto_cruzado = "\n### 🧬 Análise de Causa Raiz\n"
        for item in analise_cruzada:
            texto_cruzado += f"**{item['perfil']}**\n{item['analise']}\n👉 **Ação de Causa Raiz:** {item['recomendacao']}\n\n"
            briefing_cruzado += f"[{item['perfil']}] -> Sugerir: {item['recomendacao']} | "

    return {
        "gargalo": gargalo_key,
        "gargalo_display": gargalo_key.replace('_', ' ').title(),
        "forte": forte_key,
        "media": media,
        "persona_nome": persona["nome"],
        "persona_papel": persona["papel"],
        "frase": persona["frase"],
        "dor_macro": macro_info["dor"],
        "acao_macro": macro_info["acao"],
        "insights_list": insights, 
        "insights_prioritarios": "\n".join([f"- {i['texto']}" for i in insights]),
        "texto_cruzado": texto_cruzado,
        "briefing": briefing_cruzado or "Cliente padrão (Upsell de melhoria).",
        "scores_raw": data
    }

# ==============================================================================
#  GERAÇÃO DE RELATÓRIO (HÍBRIDA: IA + FALLBACK PREMIUM)
# ==============================================================================

def generate_fallback_report(analysis_data: dict, cliente_nome: str) -> str:
    """Gera um relatório PREMIUM, VISUAL e ESTRATÉGICO se a IA falhar."""
    
    gargalo = analysis_data['gargalo_display']
    data_hoje = datetime.now().strftime('%d/%m/%Y')
    media = analysis_data['media']
    
    # Lógica de Nível
    nivel = "SOBREVIVÊNCIA" if media < 1.6 else "ORGANIZAÇÃO" if media < 2.4 else "EXPANSÃO"
    cor_nivel = "🔴" if nivel == "SOBREVIVÊNCIA" else "🟡" if nivel == "ORGANIZAÇÃO" else "🟢"

    # Lista de Problemas Visuais
    lista_problemas = ""
    if analysis_data['insights_list']:
        for item in analysis_data['insights_list']:
            lista_problemas += f"❌ {item['texto'].replace('**', '')}\n"
    else:
        lista_problemas = f"⚠️ Ineficiência estrutural detetada no pilar {gargalo}."

    return f"""
# 📊 Relatório de Alavancagem Estratégica THRIVE

**Cliente:** {cliente_nome} | **Data:** {data_hoje}
**Consultor Responsável:** {analysis_data['persona_nome']}

---

## 1. O Estado Atual da Nação (MDMP)
A sua empresa foi auditada pela nossa metodologia proprietária.
**Resultado Global:** {media:.2f} / 3.0

| Nível Identificado | Significado Estratégico |
| :--- | :--- |
| **{cor_nivel} {nivel}** | O seu foco atual deve ser a **{analysis_data['acao_macro']}**. Qualquer outro esforço é desperdício de energia. |

---

## 2. Diagnóstico de Precisão: Onde Dói?
O sistema isolou o pilar **{gargalo}** como o Gargalo Crítico.
Na Teoria das Restrições, este é o ponto que determina a velocidade de todo o sistema.

### 🔍 Sintomas Agudos (Baseado nas suas respostas):
{lista_problemas}

{analysis_data['texto_cruzado']}

---

## 3. O Plano de Batalha (Cronograma Tático)
Não vamos tentar resolver tudo. Vamos resolver o que gera ROI.

| Fase | Objetivo Estratégico | Ação Tática (O Que Fazer) |
| :--- | :--- | :--- |
| **Fase 1: BLINDAGEM (0-30 Dias)** | **Estancar a Sangria** | Foco total em resolver: **{analysis_data['acao_macro']}**. Eliminar o Risco de Ruína. |
| **Fase 2: ESTRUTURA (30-90 Dias)** | **Profissionalização** | Criar o POP (Procedimento) para sair da dependência do dono. Implementar SSOT (Fonte Única de Verdade). |
| **Fase 3: ALAVANCAGEM (90+ Dias)** | **Escala e LTV** | Implementar rotina de gestão semanal e focar em CAC/LTV. |

---

## 4. Próximo Passo Oficial
O relatório de IA é a bússola, mas o mapa é humano.
Sua jornada para a Alavancagem Estratégica começa agora.

**CTA EXCLUSIVO:**
Sua jornada para a Alavancagem Estratégica começa agora. O relatório completo é a base. O próximo passo é o nosso acompanhamento humano e cirúrgico.
**[Responda a este e-mail para agendar a sua Sessão Estratégica de Devolutiva e iniciar a Fase de Blindagem]**

> "{analysis_data['frase']}"

**{analysis_data['persona_nome']}**
*{analysis_data['persona_papel']} - Thrive Business Intelligence*
"""

def generate_report(analise: dict, cliente_nome: str):
    """Tenta gerar com IA. Se falhar, usa o template PREMIUM acima."""
    
    fallback_text = generate_fallback_report(analise, cliente_nome)

    if not GEMINI_API_KEY:
        return fallback_text, "Modo Técnico (Offline)"

    # Prompt RAG (Retrieval Augmented Generation)
    prompt = f"""
    Você é o Consultor Sênior da Thrive Business ({analise['persona_nome']}).
    Escreva um relatório consultivo de alto nível para o cliente {cliente_nome}.
    
    DADOS:
    - Média: {analise['media']:.2f}
    - Pior Pilar: {analise['gargalo_display']}
    
    INSIGHTS DE CAUSA RAIZ (Inclua isto obrigatoriamente):
    {analise['texto_cruzado']}
    
    PROBLEMAS DETECTADOS:
    {analise['insights_prioritarios']}
    
    AÇÃO MACRO (Gargalo): "{analise['acao_macro']}"
    
    ESTRUTURA OBRIGATÓRIA (Use Markdown e Tabelas):
    1. Introdução Empática sobre o nível de maturidade.
    2. Análise do Gargalo (Use termos como 'Risco de Ruína', 'SSOT', 'Alavancagem').
    3. Tabela de Plano de Ação com 3 Fases EXATAS: 
       - Fase 1: Blindagem (0-30 Dias) -> Foco: {analise['acao_macro']}
       - Fase 2: Estrutura (30-90 Dias) -> Foco: Profissionalização
       - Fase 3: Alavancagem (90+ Dias) -> Foco: Crescimento
    4. Conclusão com este CTA EXATO: "Sua jornada para a Alavancagem Estratégica começa agora. O relatório completo é a base. O próximo passo é o nosso acompanhamento humano e cirúrgico. Responda a este e-mail para agendar sua Sessão Estratégica de Devolutiva e iniciar a Fase de Blindagem."
    
    Assine com a frase: "{analise['frase']}"
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
            timeout=30 
        )
        
        if response.status_code in [403, 429, 500, 503]:
            logging.warning(f"IA Indisponível ({response.status_code}). Usando Fallback.")
            return fallback_text, f"Modo Técnico (Erro {response.status_code})"
            
        response.raise_for_status()
        return response.json()['candidates'][0]['content']['parts'][0]['text'], "IA Gerativa"

    except Exception as e:
        logging.error(f"Erro IA: {e}")
        return fallback_text, "Modo Técnico (Exceção)"

def send_email_resend(scores: MDMPScore, analysis: dict, report: str, modo: str):
    """Envia e-mail via API Resend."""
    if not RESEND_API_KEY:
        return

    to_email = CONSULTANT_EMAIL if CONSULTANT_EMAIL else "thrivebusinessconsultoria@gmail.com"
    subject = f"LEAD {analysis['gargalo_display'].upper()} | {scores.nome_cliente}"
    
    html_report = report.replace('\n', '<br>').replace('**', '<b>').replace('__', '</b>')

    body_html = f"""
    <html><body>
    <h2>Novo Lead ({modo})</h2>
    <p><strong>Cliente:</strong> {scores.nome_cliente} ({scores.email_cliente})</p>
    <p><strong>Contato:</strong> {scores.telefone_cliente or 'N/A'}</p>
    <hr>
    <div style="background: #ffebee; padding: 15px; border-left: 5px solid #f44336; margin-bottom: 20px;">
        <strong>BRIEFING ESTRATÉGICO (Confidencial):</strong><br>
        {analysis['briefing']}
    </div>
    <h3>Relatório Gerado:</h3>
    <div style="background:#f9f9f9; padding:15px; border: 1px solid #ddd;">
        {html_report}
    </div>
    </body></html>
    """

    try:
        requests.post(
            RESEND_API_URL,
            json={
                "from": "onboarding@resend.dev",
                "to": [to_email],
                "subject": subject,
                "html": body_html
            },
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json"
            }
        )
    except Exception as e:
        logging.error(f"Erro ao enviar email: {e}")

# --- ROTAS ---
@app.get("/")
def root():
    return {"status": "Thrive API Online", "mode": "Hybrid Pro 5.0 (Senior Consultant)"}

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.post("/diagnostico", response_model=ConsultiveReport)
def diagnose(scores: MDMPScore):
    analise = analyze_data(scores)
    relatorio, modo = generate_report(analise, scores.nome_cliente)
    send_email_resend(scores, analise, relatorio, modo)

    return {
        "status": "Sucesso",
        "gargalo_critico": analise['gargalo_display'],
        "ponto_forte": analise['forte'].replace('_', ' ').title(),
        "analise_ia": relatorio,
        "media_geral": analise['media']
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
