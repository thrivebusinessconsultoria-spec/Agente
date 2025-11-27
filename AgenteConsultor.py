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
import urllib.parse

# Carrega variáveis do .env
load_dotenv()

# Logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# --- CONFIGURAÇÃO ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
CONSULTANT_EMAIL = os.environ.get("CONSULTANT_EMAIL")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "re_UqFhqRQj_FnZnaGkNfzqFbP5f24xRHY5t")
RESEND_API_URL = "https://api.resend.com/emails"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
WHATSAPP_NUMBER = "5524992778145"

app = FastAPI(title="Agente de IA THRIVE (Consultor Sênior Contextual)")

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
    "estrategista": { 
        "nome": "Sr. João da Terra", 
        "papel": "O Estrategista", 
        "frase": "Quem não planeia o plantio, não colhe o futuro.",
        "vocabulario": "terreno, raízes, colheita, semear, estação, clima, frutos, cultivo, safra, sustentabilidade"
    },
    "guardia": { 
        "nome": "Dra. Clara Lex", 
        "papel": "A Guardiã", 
        "frase": "Segurança não é custo, é a base do lucro.",
        "vocabulario": "blindagem, alicerce, risco, contrato, lei, proteção, conformidade, defesa, passivo, norma"
    },
    "hacker": { 
        "nome": "K4J1 (Caju)", 
        "papel": "O Hacker", 
        "frase": "Trabalhe de forma inteligente, não apenas duro.",
        "vocabulario": "sistema, bug, atualização, código, rede, conexão, upgrade, versão beta, algoritmo, automação"
    }
}

REGRAS_GATILHO = {
    "p1_q0": { 1: { "peso": 9, "msg": "⚠️ **Falta de Rumo:** Sem definir claramente a Missão, a equipa trabalha sem propósito." } },
    "p1_q3": { 1: { "peso": 7, "msg": "🎯 **Cliente Indefinido:** Tentar vender para 'todos' queima recursos de marketing." } },
    "p1_q10": { 1: { "peso": 10, "msg": "💀 **Dependência Total:** Se você faltar, a empresa para. Risco máximo de continuidade." } },
    "p2_q0": { 1: { "peso": 10, "msg": "🚨 **Caixa Misturado:** Misturar contas PF/PJ é o erro número 1 que leva à falência." } },
    "p2_q4": { 1: { "peso": 9, "msg": "📉 **Gestão no Escuro:** Sem controlo diário, não há decisão segura." } },
    "p2_q7": { 1: { "peso": 9, "msg": "⚖️ **Meta de Sobrevivência:** Desconhecer o Ponto de Equilíbrio é como pilotar sem painel." } },
    "p3_q2": { 1: { "peso": 9, "msg": "🔗 **Gargalo do Dono:** A centralização impede o crescimento além das suas 24 horas." } },
    "p4_q0": { 1: { "peso": 8, "msg": "📉 **Vendas por Sorte:** Sem Funil, a receita do mês seguinte é um mistério." } },
    "p5_q0": { 1: { "peso": 7, "msg": "👥 **Desvio de Função:** Indefinição de papéis gera retrabalho e conflitos." } },
    "p6_q0": { 1: { "peso": 9, "msg": "🤝 **Acordo de Boca:** Sócios sem contrato escrito geram conflitos fatais." } },
    "p6_q2": { 1: { "peso": 10, "msg": "⚖️ **Risco Trabalhista:** A informalidade cria um passivo oculto que pode explodir." } },
    "p7_q1": { 1: { "peso": 10, "msg": "💾 **Perda de Dados:** Sem backup na nuvem, um vírus apaga a história da empresa." } }
}

MACRO_PILARES = {
    "1. Estratégico": {
        "dor": "Falta de um caminho claro para o futuro.", 
        "acao": "Definir 3 grandes metas (OKRs).", 
        "stop_doing": "Pare de decidir baseado apenas na intuição.",
        "persona": "estrategista"
    },
    "2. Financeiro": {
        "dor": "Descontrolo financeiro e risco de falência.", 
        "acao": "Implantar o 'Caixa Zero' (controlo diário).", 
        "stop_doing": "Pare de usar o cartão da empresa para gastos pessoais.",
        "persona": "guardia"
    },
    "3. Operacional": {
        "dor": "Dependência total da sua presença física.", 
        "acao": "Escrever o manual (POP) da tarefa crítica.", 
        "stop_doing": "Pare de centralizar tarefas delegáveis.",
        "persona": "hacker"
    },
    "4. Comercial": {
        "dor": "Vendas imprevisíveis e passivas.", 
        "acao": "Organizar o Funil de Vendas.", 
        "stop_doing": "Pare de esperar que o cliente venha até si.",
        "persona": "estrategista"
    },
    "5. Pessoas (RH)": {
        "dor": "Equipa perdida ou desmotivada.", 
        "acao": "Criar descrições de cargo simples.", 
        "stop_doing": "Pare de dar feedback apenas na hora do erro.",
        "persona": "guardia"
    },
    "6. Jurídico": {
        "dor": "Vulnerabilidade legal alta.", 
        "acao": "Revisar contratos principais.", 
        "stop_doing": "Pare de fechar negócios só de boca.",
        "persona": "guardia"
    },
    "7. Tecnológico": {
        "dor": "Processos manuais lentos.", 
        "acao": "Adotar sistema de gestão central.", 
        "stop_doing": "Pare de confiar dados a papéis e memória.",
        "persona": "hacker"
    }
}

# ==============================================================================
#  MOTOR DE INTELIGÊNCIA (CONTEXTO E PORTE)
# ==============================================================================

def get_profile_context(respostas: Dict[str, int]) -> dict:
    """Analisa o porte para ajustar o tom e a severidade."""
    tamanho_idx = respostas.get("p0_q0", 1)
    
    perfil = {
        "tamanho_label": "Pequeno",
        "tom_voz": "Próximo, ágil e direto",
        "complexidade_acao": "Simples e prática",
        "foco_estrategico": "Vendas e Caixa",
        "mensagem_contexto": ""
    }
    
    if tamanho_idx == 1: # Euquipe (1-5)
        perfil["tamanho_label"] = "Micro/Euquipe"
        perfil["tom_voz"] = "Próximo e motivador (Coach)"
        perfil["complexidade_acao"] = "Ações 'faça você mesmo', foco em execução."
        perfil["foco_estrategico"] = "Sobrevivência e Vendas."
        perfil["mensagem_contexto"] = "Para equipas enxutas, a agilidade é a maior força. Organize o básico financeiro."
        
    elif tamanho_idx == 2: # Pequena (6-20)
        perfil["tamanho_label"] = "Pequena Empresa"
        perfil["tom_voz"] = "Profissional e direto"
        perfil["complexidade_acao"] = "Implementação de processos básicos."
        perfil["foco_estrategico"] = "Liderança e Processos."
        perfil["mensagem_contexto"] = "Você está na fase onde a informalidade custa caro. É hora de profissionalizar."
        
    elif tamanho_idx >= 3: # Média/Grande (21+)
        perfil["tamanho_label"] = "Média/Grande"
        perfil["tom_voz"] = "Corporativo e analítico"
        perfil["complexidade_acao"] = "Estruturação, KPIs e governança."
        perfil["foco_estrategico"] = "Governança e Cultura."
        perfil["mensagem_contexto"] = "Para este porte, a gestão baseada em dados é inegociável. Foco na estratégia."

    return perfil

def analyze_cross_patterns(scores_map: Dict[str, float], perfil: dict) -> List[Dict[str, str]]:
    """Gera insights cruzados (Causa Raiz) considerando porte."""
    insights = []
    
    def get_score(key_part):
        for k, v in scores_map.items():
            if key_part.lower() in k.lower(): return v * 3.33 
        return 0

    fin = get_score('financeiro')
    pes = get_score('pessoas')
    proc = get_score('operacional')
    vend = get_score('comercial')
    jur = get_score('jurídico')
    
    # Lógica de Causa Raiz (Financeiro + Comercial)
    if vend <= 5 and fin <= 4:
        insights.append({
            "perfil": "⚠️ Vender muito, Lucrar pouco",
            "analise": "Esforço comercial alto com retorno baixo. A baixa Margem de Contribuição está a forçar descontos, afetando a conversão.",
            "risco": "Margem Negativa e quebra de caixa.",
            "recomendacao": "Engenharia Financeira para reverter a Margem."
        })

    # Lógica de Porte (Gigante com Pés de Barro)
    if perfil["tamanho_label"] in ["Média/Grande", "Pequena Empresa"] and (jur <= 4 or fin <= 4):
        insights.append({
            "perfil": "⚠️ Gigante com Pés de Barro",
            "analise": f"Crescimento de porte ({perfil['tamanho_label']}) com gestão amadora. Riscos ocultos nesta escala são fatais.",
            "risco": "Passivo oculto gigante.",
            "recomendacao": "Blindagem Jurídica e Compliance."
        })

    # Lógica de Liderança
    if perfil["tamanho_label"] != "Micro/Euquipe" and pes <= 4:
        insights.append({
            "perfil": "⚠️ Crise de Liderança",
            "analise": "Com este tamanho de equipa, a centralização é insustentável.",
            "risco": "Burnout do dono e turnover.",
            "recomendacao": "Formação de Líderes e Delegação."
        })

    return insights

def analyze_data(scores: MDMPScore):
    data = scores.scores_por_pilar
    if not data: raise HTTPException(status_code=400, detail="Sem scores")
    
    perfil = get_profile_context(scores.respostas or {})
    
    media = sum(data.values()) / len(data)
    gargalo_key = min(data, key=data.get)
    forte_key = max(data, key=data.get)
    
    macro_key_gargalo = next((k for k in MACRO_PILARES.keys() if gargalo_key in k or k in gargalo_key), "1. Estratégico")
    macro_info_gargalo = MACRO_PILARES[macro_key_gargalo]
    persona = PERSONAS[macro_info_gargalo["persona"]]
    
    macro_key_forte = next((k for k in MACRO_PILARES.keys() if forte_key in k or k in forte_key), "1. Estratégico")

    insights = []
    if scores.respostas:
        for q_id, resp in scores.respostas.items():
            if q_id in REGRAS_GATILHO and resp in REGRAS_GATILHO[q_id]:
                regra = REGRAS_GATILHO[q_id][resp]
                idx_pilar = int(q_id.split('_')[0].replace('p', ''))
                try: nome_pilar = list(data.keys())[idx_pilar - 1] 
                except: nome_pilar = gargalo_key
                
                peso_final = regra['peso']
                if perfil["tamanho_label"] == "Média/Grande" and ("Operacional" in nome_pilar or "Pessoas" in nome_pilar):
                    peso_final += 2 
                
                urgencia = (peso_final * 2) + (10 - (data.get(nome_pilar, 5) * 3.33))
                insights.append({"texto": regra['msg'], "urgencia": urgencia})
    
    insights = sorted(insights, key=lambda x: x['urgencia'], reverse=True)[:4]
    analise_cruzada = analyze_cross_patterns(data, perfil)
    
    texto_cruzado = "\n### 🧬 Causa Raiz (Diagnóstico Cruzado)\n" + "\n".join([f"**{i['perfil']}**\n{i['analise']}\n👉 **Ação:** {i['recomendacao']}\n" for i in analise_cruzada]) if analise_cruzada else ""
    briefing_cruzado = " | ".join([f"[{i['perfil']}]" for i in analise_cruzada]) if analise_cruzada else "Padrão"

    msg_zap = f"Olá, sou {scores.nome_cliente} ({perfil['tamanho_label']}). Meu gargalo é {gargalo_key}. Quero avançar."
    link_zap = f"https://wa.me/{WHATSAPP_NUMBER}?text={urllib.parse.quote(msg_zap)}"

    return {
        "gargalo": gargalo_key,
        "gargalo_display": gargalo_key.replace('_', ' ').title(),
        "forte": forte_key,
        "forte_display": forte_key.replace('_', ' ').title(),
        "media": media,
        "persona_nome": persona["nome"],
        "persona_papel": persona["papel"],
        "frase": persona["frase"],
        "vocabulario": persona["vocabulario"],
        "dor_macro": macro_info_gargalo["dor"],
        "acao_macro": macro_info_gargalo["acao"],
        "stop_doing": macro_info_gargalo["stop_doing"],
        "insights_list": insights, 
        "insights_prioritarios": "\n".join([f"- {i['texto']}" for i in insights]),
        "texto_cruzado": texto_cruzado,
        "briefing": f"PORTE: {perfil['tamanho_label']} | {briefing_cruzado}",
        "link_zap": link_zap,
        "perfil_contexto": perfil["mensagem_contexto"],
        "tom_voz": perfil["tom_voz"],
        "complexidade_acao": perfil["complexidade_acao"],
        "scores_raw": data
    }

# ==============================================================================
#  GERAÇÃO DE RELATÓRIO (HÍBRIDA)
# ==============================================================================

def generate_fallback_report(analise: dict, cliente_nome: str) -> str:
    """Gera relatório técnico visual se IA falhar."""
    media = analise['media']
    if media < 1.6:
        nivel, cor_nivel, desc = "SOBREVIVÊNCIA", "🔴", "Risco alto. Foco em caixa."
    elif media < 2.4:
        nivel, cor_nivel, desc = "ORGANIZAÇÃO", "🟡", "Falta consistência. Foco em processos."
    else:
        nivel, cor_nivel, desc = "EXPANSÃO", "🟢", "Saudável. Foco em escala."

    lista_prob = "".join([f"❌ {i['texto'].replace('**', '')}\n" for i in analise['insights_list']]) or f"⚠️ Atenção ao pilar {analise['gargalo_display']}."

    return f"""
# 📊 Relatório de Alavancagem Estratégica THRIVE

**Cliente:** {cliente_nome} | **Data:** {datetime.now().strftime('%d/%m/%Y')}
**Especialista:** {analise['persona_nome']}

---

## 1. Diagnóstico MDMP
**Nota Geral:** {media:.2f} / 3.0

| Nível | Significado |
| :--- | :--- |
| **{cor_nivel} {nivel}** | {desc} |

ℹ️ **Contexto:** {analise['perfil_contexto']}

### 🏆 Ponto Forte: {analise['forte_display']}
Use a segurança deste pilar para financiar as melhorias necessárias.

---

## 2. Onde Dói (Gargalo Crítico)
O pilar **{analise['gargalo_display']}** é a trava do seu crescimento.

### 🔍 Diagnóstico de Precisão:
{lista_prob}
{analise['texto_cruzado']}

---

## 3. Plano de Batalha (Cronograma Tático)

### 🛑 STOP DOING (Pare Agora)
**{analise['stop_doing']}**

### ✅ ROADMAP DE 90 DIAS
| Fase | Objetivo Estratégico | Ação Tática |
| :--- | :--- | :--- |
| **1. BLINDAGEM (0-30 Dias)** | **Estancar a Sangria** | **{analise['acao_macro']}** (Foco no Gargalo). |
| **2. ESTRUTURA (30-90 Dias)** | **Profissionalização** | Criar Processos (POPs) e sair da dependência. |
| **3. ALAVANCAGEM (90+ Dias)** | **Escala e LTV** | Foco em Vendas e Inovação. |

---

## 4. Próximo Passo Oficial
Sua jornada para a Alavancagem Estratégica começa agora. O relatório completo é a base. O próximo passo é o nosso acompanhamento humano e cirúrgico.

**[Responda a este e-mail ou CLIQUE AQUI para agendar sua Sessão Estratégica de Devolutiva]({analise['link_zap']})**
*Vamos iniciar a Fase de Blindagem juntos.*

> "{analise['frase']}"

**{analise['persona_nome']}**
*{analise['persona_papel']} - Thrive Business Intelligence*
"""

def generate_report(analise: dict, cliente_nome: str):
    fallback_text = generate_fallback_report(analise, cliente_nome)
    if not GEMINI_API_KEY: return fallback_text, "Modo Técnico (Offline)"

    # Prompt Refinado com Estrutura de Fases
    prompt = f"""
    Você é o {analise['persona_nome']} ({analise['persona_papel']}) da Thrive Business.
    Escreva um relatório para o cliente {cliente_nome}.
    
    CONTEXTO:
    - Porte: {analise['perfil_contexto']}
    - Tom de Voz: {analise['tom_voz']}
    
    VOCABULÁRIO: {analise['vocabulario']}
    
    DADOS TÉCNICOS:
    - Nível: {analise['media']:.2f}
    - Gargalo: {analise['gargalo_display']}
    - Forte: {analise['forte_display']}
    - Ação Fase 1 (Blindagem): "{analise['acao_macro']}"
    - Stop Doing: "{analise['stop_doing']}"
    
    INSIGHTS: {analise['texto_cruzado']}
    PROBLEMAS: {analise['insights_prioritarios']}
    
    ESTRUTURA OBRIGATÓRIA (Markdown):
    1. Intro: Nível da empresa e contexto de porte.
    2. Ponto Forte: Elogio breve.
    3. O Gargalo: Explique o {analise['gargalo_display']} e a Causa Raiz.
    4. STOP DOING: Destaque o que parar.
    5. Tabela "Roadmap 90 Dias":
       - Fase 1 (Blindagem): Foco em {analise['acao_macro']}
       - Fase 2 (Estrutura): Profissionalização
       - Fase 3 (Alavancagem): Crescimento
    6. Conclusão com CTA EXATO: "Sua jornada para a Alavancagem Estratégica começa agora... Responda a este e-mail para agendar sua Sessão Estratégica de Devolutiva."
    
    Assine com: "{analise['frase']}"
    """

    try:
        logging.info("Solicitando análise à IA...")
        response = requests.post(
            f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
            headers={'Content-Type': 'application/json'},
            json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.7}},
            timeout=30 
        )
        if response.status_code in [403, 429, 500, 503]:
            return fallback_text, f"Modo Técnico (Erro {response.status_code})"
        response.raise_for_status()
        return response.json()['candidates'][0]['content']['parts'][0]['text'], "IA Gerativa"
    except Exception as e:
        logging.error(f"Erro IA: {e}")
        return fallback_text, "Modo Técnico (Exceção)"

def send_email_resend(scores: MDMPScore, analysis: dict, report: str, modo: str):
    if not RESEND_API_KEY: return
    to_email = CONSULTANT_EMAIL if CONSULTANT_EMAIL else "thrivebusinessconsultoria@gmail.com"
    subject = f"LEAD {analysis['gargalo_display'].upper()} | {scores.nome_cliente}"
    html_report = report.replace('\n', '<br>').replace('**', '<b>').replace('__', '</b>')
    
    cta_button = f"""<a href="{analysis['link_zap']}" style="background-color:#ddcea4; color:#53534a; padding:10px 20px; text-decoration:none; font-weight:bold; border-radius:5px; display:inline-block; margin-top:15px;">Agendar Devolutiva</a>"""

    body_html = f"""
    <html><body>
    <h2>Novo Lead ({modo})</h2>
    <p><strong>Cliente:</strong> {scores.nome_cliente} ({scores.email_cliente})</p>
    <p><strong>Contexto:</strong> {analysis['perfil_contexto']}</p>
    <hr>
    <div style="background: #ffebee; padding: 15px; border-left: 5px solid #f44336; margin-bottom: 20px;">
        <strong>BRIEFING ESTRATÉGICO:</strong><br>{analysis['briefing']}
    </div>
    <h3>Relatório Gerado:</h3>
    <div style="background:#f9f9f9; padding:15px; border: 1px solid #ddd;">
        {html_report}
        <br><br>
        {cta_button}
    </div>
    </body></html>
    """
    try:
        requests.post(
            RESEND_API_URL,
            json={"from": "onboarding@resend.dev", "to": [to_email], "subject": subject, "html": body_html},
            headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"}
        )
    except Exception as e: logging.error(f"Erro email: {e}")

@app.get("/")
def root(): return {"status": "Online", "mode": "Consultor Senior Contextual (Fases & Causa Raiz)"}

@app.get("/api/health")
def health(): return {"status": "ok"}

@app.post("/diagnostico", response_model=ConsultiveReport)
def diagnose(scores: MDMPScore):
    analise = analyze_data(scores)
    relatorio, modo = generate_report(analise, scores.nome_cliente)
    send_email_resend(scores, analise, relatorio, modo)
    return {"status": "Sucesso", "gargalo_critico": analise['gargalo_display'], "ponto_forte": analise['forte_display'], "analise_ia": relatorio, "media_geral": analise['media']}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
