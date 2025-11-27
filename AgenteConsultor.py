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
# Configuração RESEND (E-mail Transacional)
# Chave fornecida pelo utilizador. Em produção, recomenda-se mover para variáveis de ambiente.
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "re_UqFhqRQj_FnZnaGkNfzqFbP5f24xRHY5t")
RESEND_API_URL = "https://api.resend.com/emails"
# Configuração IA (Modelo Estável)
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
# Número do WhatsApp para o CTA (Substitua pelo seu número real)
WHATSAPP_NUMBER = "5511999999999" 

app = FastAPI(title="Agente de IA THRIVE (Consultor Sênior Blindado)")

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
#  CÉREBRO DA THRIVE (BASE DE CONHECIMENTO RÍGIDA)
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

# GATILHOS CIRÚRGICOS (Mapeamento Direto: Problema -> Solução Específica)
# Estas são as DECISÕES que o agente vai tomar, a IA apenas vai reescrever.
REGRAS_GATILHO = {
    # ESTRATÉGICO (p1)
    "p1_q0": { 1: { "peso": 9, "msg": "⚠️ **Falta de Rumo:** A ausência de Missão clara deixa a equipa sem propósito." } },
    "p1_q3": { 1: { "peso": 7, "msg": "🎯 **Cliente Indefinido:** Vender para 'todos' dispersa recursos e baixa a conversão." } },
    "p1_q10": { 1: { "peso": 10, "msg": "💀 **Dependência Total:** O negócio para sem você. Risco máximo de continuidade." } },
    
    # FINANCEIRO (p2)
    "p2_q0": { 1: { "peso": 10, "msg": "🚨 **MISTURA PATRIMONIAL:** O erro nº 1. Impossível saber o lucro real misturando contas PF/PJ." } },
    "p2_q4": { 1: { "peso": 9, "msg": "📉 **Cegueira de Caixa:** Sem registo diário, você gere no escuro e reage a crises." } },
    "p2_q7": { 1: { "peso": 9, "msg": "⚖️ **Meta de Sobrevivência:** Desconhecer o Ponto de Equilíbrio impede o planeamento financeiro." } },
    
    # OPERACIONAL (p3)
    "p3_q2": { 1: { "peso": 9, "msg": "🔗 **Centralização Extrema:** Você tornou-se o gargalo do crescimento. Delegar é preciso." } },
    
    # COMERCIAL (p4)
    "p4_q0": { 1: { "peso": 8, "msg": "📉 **Vendas por Sorte:** Sem Funil visual, a receita futura é imprevisível." } },
    
    # PESSOAS (p5)
    "p5_q0": { 1: { "peso": 7, "msg": "👥 **Desvio de Função:** Indefinição de papéis gera retrabalho e conflitos." } },
    
    # JURÍDICO (p6)
    "p6_q0": { 1: { "peso": 9, "msg": "🤝 **Acordo de Boca:** Sócios sem contrato escrito é o maior risco societário." } },
    "p6_q2": { 1: { "peso": 10, "msg": "⚖️ **Risco Trabalhista:** A informalidade cria um passivo oculto explosivo." } },
    
    # TECNOLÓGICO (p7)
    "p7_q1": { 1: { "peso": 10, "msg": "💾 **Perda de Dados:** Sem backup na nuvem, um vírus pode fechar a empresa." } }
}

MACRO_PILARES = {
    "1. Estratégico": {
        "dor": "Falta de Direção e Estratégia Clara.", 
        "acao": "Definir OKRs Trimestrais.", 
        "stop_doing": "Decidir apenas por intuição ('achismo').",
        "persona": "estrategista"
    },
    "2. Financeiro": {
        "dor": "Descontrolo de Caixa e Risco de Ruína.", 
        "acao": "Segregação Patrimonial e Caixa Zero.", 
        "stop_doing": "Misturar contas pessoais e empresariais.",
        "persona": "guardia"
    },
    "3. Operacional": {
        "dor": "Ineficiência e Dependência do Dono.", 
        "acao": "Mapear Processos Críticos (POP).", 
        "stop_doing": "Centralizar tarefas operacionais delegáveis.",
        "persona": "hacker"
    },
    "4. Comercial": {
        "dor": "Vendas Imprevisíveis e Passivas.", 
        "acao": "Estruturar Funil de Vendas e CRM.", 
        "stop_doing": "Esperar que o cliente venha até si.",
        "persona": "estrategista"
    },
    "5. Pessoas (RH)": {
        "dor": "Equipa Desengajada ou Perdida.", 
        "acao": "Criar Descritivos de Cargos e Rituais 1:1.", 
        "stop_doing": "Dar feedback apenas na hora do erro.",
        "persona": "guardia"
    },
    "6. Jurídico": {
        "dor": "Vulnerabilidade Legal e Passivos.", 
        "acao": "Audit e Blindagem Contratual.", 
        "stop_doing": "Fechar negócios apenas com acordos verbais.",
        "persona": "guardia"
    },
    "7. Tecnológico": {
        "dor": "Processos Manuais e Inseguros.", 
        "acao": "Implementar SSOT (Sistema Único).", 
        "stop_doing": "Confiar gestão a papel e memória.",
        "persona": "hacker"
    }
}

# ==============================================================================
#  MOTOR DE INTELIGÊNCIA (LÓGICA DETERMINÍSTICA)
# ==============================================================================

def get_profile_context(respostas: Dict[str, int]) -> dict:
    """Analisa o porte para ajustar a severidade."""
    tamanho_idx = respostas.get("p0_q0", 1)
    
    if tamanho_idx == 1: # Euquipe (1-5)
        return {
            "tamanho": "Micro/Euquipe",
            "mensagem_contexto": "Para equipas enxutas, a falta de processos é comum, mas o foco deve ser total em Vendas e Caixa."
        }
    elif tamanho_idx == 2: # Pequena (6-20)
        return {
            "tamanho": "Pequena Empresa",
            "mensagem_contexto": "Você está na zona de crescimento. A informalidade que funcionava antes agora é o seu maior risco."
        }
    elif tamanho_idx >= 3: # Média/Grande (21+)
        return {
            "tamanho": "Média/Grande",
            "mensagem_contexto": "Para o seu porte, a falta de governança é um risco inaceitável. O foco é Cultura e Gestão."
        }
    return {"tamanho": "Pequeno", "mensagem_contexto": ""}

def analyze_cross_patterns(scores_map: Dict[str, float], perfil: dict) -> List[Dict[str, str]]:
    """Gera insights cruzados (Causa Raiz) com base em lógica rígida."""
    insights = []
    
    def get_score(key_part):
        for k, v in scores_map.items():
            if key_part.lower() in k.lower(): return v * 3.33 
        return 0

    fin, pes, est, proc, vend, jur = get_score('financeiro'), get_score('pessoas'), get_score('estratégico'), get_score('operacional'), get_score('comercial'), get_score('jurídico')

    # Lógica 1: Gigante com Pés de Barro (Risco Sistêmico)
    if perfil["tamanho"] in ["Média/Grande", "Pequena Empresa"] and (jur <= 4 or fin <= 4):
        insights.append({
            "perfil": "⚠️ Gigante com Pés de Barro",
            "analise": f"Você cresceu ({perfil['tamanho']}), mas a base de gestão continua frágil. Riscos jurídicos ou financeiros nesta escala podem ser fatais.",
            "risco": "Passivo oculto gigante.",
            "recomendacao": "Blindagem Jurídica e Compliance Imediato."
        })

    # Lógica 2: Venda sem Margem (Financeiro x Comercial)
    if vend <= 5 and fin <= 4:
        insights.append({
            "perfil": "⚠️ Vender muito, Lucrar pouco",
            "analise": "Esforço comercial alto com retorno baixo. O problema provável não é a equipa de vendas, é a precificação ou custos.",
            "risco": "Quebrar por falta de capital de giro (overtrading).",
            "recomendacao": "Engenharia Financeira antes de Marketing."
        })

    # Lógica 3: Gargalo de Liderança (Pessoas x Tamanho)
    if perfil["tamanho"] != "Micro/Euquipe" and pes <= 4:
        insights.append({
            "perfil": "⚠️ Crise de Liderança",
            "analise": "Com uma equipa deste tamanho, a centralização é insustentável. A baixa nota em 'Pessoas' indica sobrecarga da gestão.",
            "risco": "Burnout do dono e turnover da equipa.",
            "recomendacao": "Formação de Líderes e Delegação."
        })

    return insights

def analyze_data(scores: MDMPScore):
    data = scores.scores_por_pilar
    if not data: raise HTTPException(status_code=400, detail="Sem scores")
    
    # Contexto
    perfil = get_profile_context(scores.respostas or {})
    media = sum(data.values()) / len(data)
    gargalo_key = min(data, key=data.get)
    forte_key = max(data, key=data.get)
    
    # Mapeamento Macro (Decisão do Pilar)
    macro_key_gargalo = next((k for k in MACRO_PILARES.keys() if gargalo_key in k or k in gargalo_key), "1. Estratégico")
    macro_info_gargalo = MACRO_PILARES[macro_key_gargalo]
    persona = PERSONAS[macro_info_gargalo["persona"]]
    
    # Gatilhos Específicos (Decisão dos Problemas Pontuais)
    insights = []
    if scores.respostas:
        for q_id, resp in scores.respostas.items():
            if q_id in REGRAS_GATILHO and resp in REGRAS_GATILHO[q_id]:
                regra = REGRAS_GATILHO[q_id][resp]
                idx_pilar = int(q_id.split('_')[0].replace('p', ''))
                try: nome_pilar = list(data.keys())[idx_pilar - 1] 
                except: nome_pilar = gargalo_key
                
                # Penalidade por porte
                peso_final = regra['peso']
                if perfil["tamanho"] == "Média/Grande" and ("Operacional" in nome_pilar or "Pessoas" in nome_pilar):
                    peso_final += 2 
                
                urgencia = (peso_final * 2) + (10 - (data.get(nome_pilar, 5) * 3.33))
                insights.append({"texto": regra['msg'], "urgencia": urgencia})
    
    insights = sorted(insights, key=lambda x: x['urgencia'], reverse=True)[:4]
    
    analise_cruzada = analyze_cross_patterns(data, perfil)
    
    texto_cruzado = ""
    if analise_cruzada:
        texto_cruzado = "\n### 🧬 Diagnóstico Cruzado (Causa Raiz)\n" + "\n".join([f"**{i['perfil']}**\n{i['analise']}\n👉 **Ação:** {i['recomendacao']}\n" for i in analise_cruzada])

    briefing_cruzado = " | ".join([f"[{i['perfil']}]" for i in analise_cruzada]) if analise_cruzada else "Cliente Padrão"

    # Link WhatsApp
    msg_zap = f"Olá, sou {scores.nome_cliente} ({perfil['tamanho']}). Meu gargalo é {gargalo_key}. Quero avançar."
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
        # DECISÕES TOMADAS PELO PYTHON (Não pela IA):
        "dor_macro": macro_info_gargalo["dor"],
        "acao_macro": macro_info_gargalo["acao"],
        "stop_doing": macro_info_gargalo["stop_doing"],
        "insights_list": insights, 
        "insights_prioritarios": "\n".join([f"- {i['texto']}" for i in insights]),
        "texto_cruzado": texto_cruzado,
        "briefing": f"PORTE: {perfil['tamanho']} | {briefing_cruzado}",
        "link_zap": link_zap,
        "perfil_contexto": perfil["mensagem_contexto"],
        "scores_raw": data
    }

# ==============================================================================
#  GERAÇÃO DE RELATÓRIO (HÍBRIDA)
# ==============================================================================

def generate_fallback_report(analise: dict, cliente_nome: str) -> str:
    """Relatório Técnico Determinístico (Garantia de qualidade sem IA)."""
    media = analise['media']
    if media < 1.6:
        nivel, cor_nivel, desc = "SOBREVIVÊNCIA", "🔴", "Risco alto. Foco em caixa."
    elif media < 2.4:
        nivel, cor_nivel, desc = "ORGANIZAÇÃO", "🟡", "Falta consistência. Foco em processos."
    else:
        nivel, cor_nivel, desc = "EXPANSÃO", "🟢", "Saudável. Foco em escala."

    lista_prob = "".join([f"❌ {i['texto'].replace('**', '')}\n" for i in analise['insights_list']]) or f"⚠️ Atenção ao pilar {analise['gargalo_display']}."

    return f"""
# 📊 Relatório de Diagnóstico Empresarial THRIVE

**Cliente:** {cliente_nome} | **Data:** {datetime.now().strftime('%d/%m/%Y')}
**Especialista:** {analise['persona_nome']}

---

## 1. Análise de Contexto
**Nota Geral:** {media:.2f} / 3.0

| Nível | O Que Significa |
| :--- | :--- |
| **{cor_nivel} {nivel}** | {desc} |

ℹ️ **Nota do Consultor:** {analise['perfil_contexto']}

### 🏆 Ponto Forte: {analise['forte_display']}
Esta área é o motor do seu negócio hoje. Use a segurança daqui para financiar as correções.

---

## 2. Onde Dói (Gargalo Crítico)
Identificámos que o **{analise['gargalo_display']}** é a trava do seu crescimento.

### 🔍 Problemas Detectados:
{lista_prob}
{analise['texto_cruzado']}

---

## 3. Plano de Ação (90 Dias)

### 🛑 STOP DOING (Pare Agora)
**{analise['stop_doing']}**

### ✅ START DOING (O Plano)
| Fase | Ação Prática | Objetivo |
| :--- | :--- | :--- |
| **IMEDIATO** | **{analise['acao_macro']}** | Estancar a sangria. |
| **30 DIAS** | Criar Processo Padrão (POP) | Reduzir caos e erros. |
| **90 DIAS** | Definir Metas (KPIs) | Garantir crescimento. |

---

## 4. Próximo Passo
Não tente resolver tudo sozinho. 

**[CLIQUE AQUI PARA AGENDAR SUA DEVOLUTIVA]({analise['link_zap']})**

> "{analise['frase']}"

**{analise['persona_nome']}**
*{analise['persona_papel']}*
"""

def generate_report(analise: dict, cliente_nome: str):
    """Tenta gerar com IA, mas obriga-a a seguir as decisões do Python."""
    fallback_text = generate_fallback_report(analise, cliente_nome)
    if not GEMINI_API_KEY: return fallback_text, "Modo Técnico (Offline)"

    # PROMPT BLINDADO (A IA apenas formata, não decide)
    prompt = f"""
    Você é o {analise['persona_nome']} ({analise['persona_papel']}) da Thrive Business.
    Reescreva este relatório técnico para o cliente {cliente_nome}, tornando-o mais fluido e persuasivo, MAS MANTENDO AS DECISÕES EXATAS.
    
    VOCABULÁRIO OBRIGATÓRIO: {analise['vocabulario']}
    
    DECISÕES ESTRATÉGICAS JÁ TOMADAS (NÃO ALTERE):
    1. Nível: {analise['media']:.2f}
    2. Contexto de Porte: "{analise['perfil_contexto']}"
    3. Gargalo Crítico: {analise['gargalo_display']}
    4. Ponto Forte: {analise['forte_display']}
    5. Ação Principal: "{analise['acao_macro']}"
    6. Stop Doing: "{analise['stop_doing']}"
    
    INSIGHTS CRUZADOS (Inclua na íntegra): {analise['texto_cruzado']}
    LISTA DE PROBLEMAS (Inclua na íntegra): {analise['insights_prioritarios']}
    
    ESTRUTURA DO RELATÓRIO (Markdown):
    1. Introdução: Nível e Contexto de Porte.
    2. Ponto Forte: Elogio breve.
    3. O Problema: Explique o {analise['gargalo_display']} e os Problemas listados.
    4. Secção STOP DOING em destaque.
    5. Tabela de Ação (Imediato, Curto Prazo, Médio Prazo) usando a Ação Principal.
    6. Conclusão com Link: "Clique aqui para agendar: {analise['link_zap']}"
    
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
    
    cta_button = f"""<a href="{analysis['link_zap']}" style="background-color:#ddcea4; color:#53534a; padding:10px 20px; text-decoration:none; font-weight:bold; border-radius:5px; display:inline-block; margin-top:15px;">Falar com Consultor</a>"""

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
def root(): return {"status": "Online", "mode": "Consultor Senior Blindado"}

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
