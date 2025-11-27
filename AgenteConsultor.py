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
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
WHATSAPP_NUMBER = "5524992778145" # Coloque o seu número real aqui

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
    "estrategista": { 
        "nome": "Sr. João da Terra", 
        "papel": "O Estrategista", 
        "frase": "Quem não planeia o plantio, não colhe o futuro.",
        "vocabulario": "terreno, raízes, colheita, semear, estação, clima, frutos, cultivo"
    },
    "guardia": { 
        "nome": "Dra. Clara Lex", 
        "papel": "A Guardiã", 
        "frase": "Segurança não é custo, é a base do lucro.",
        "vocabulario": "blindagem, alicerce, risco, contrato, lei, proteção, conformidade, defesa"
    },
    "hacker": { 
        "nome": "K4J1 (Caju)", 
        "papel": "O Hacker", 
        "frase": "Trabalhe de forma inteligente, não apenas duro.",
        "vocabulario": "sistema, bug, atualização, código, rede, conexão, upgrade, versão beta"
    }
}

REGRAS_GATILHO = {
    "p0_q0": { 1: { "peso": 9, "msg": "⚠️ **Falta de Rumo:** Sem definir claramente a Missão, a equipa trabalha sem propósito." } },
    "p0_q4": { 1: { "peso": 7, "msg": "🎯 **Cliente Indefinido:** Tentar vender para 'todos' queima recursos de marketing." } },
    "p0_q11": { 1: { "peso": 10, "msg": "💀 **Dependência Total:** Se você faltar, a empresa para. Risco máximo de continuidade." } },
    "p1_q0": { 1: { "peso": 10, "msg": "🚨 **Caixa Misturado:** Misturar contas PF/PJ é o erro número 1 que leva à falência." } },
    "p1_q4": { 1: { "peso": 9, "msg": "📉 **Gestão no Escuro:** Sem controlo diário, não há decisão segura." } },
    "p1_q10": { 1: { "peso": 9, "msg": "⚖️ **Meta de Sobrevivência:** Desconhecer o Ponto de Equilíbrio é como pilotar sem painel." } },
    "p2_q2": { 1: { "peso": 9, "msg": "🔗 **Gargalo do Dono:** A centralização impede o crescimento além das suas 24 horas." } },
    "p3_q0": { 1: { "peso": 8, "msg": "📉 **Vendas por Sorte:** Sem Funil, a receita do mês seguinte é um mistério." } },
    "p5_q0": { 1: { "peso": 9, "msg": "🤝 **Acordo de Boca:** Sócios sem contrato escrito geram conflitos fatais." } },
    "p5_q4": { 1: { "peso": 10, "msg": "⚖️ **Risco Trabalhista:** A informalidade cria um passivo oculto que pode explodir." } },
    "p6_q2": { 1: { "peso": 10, "msg": "💾 **Perda de Dados:** Sem backup na nuvem, um vírus apaga a história da empresa." } }
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
#  MOTOR DE INTELIGÊNCIA (LÓGICA AVANÇADA)
# ==============================================================================

def analyze_cross_patterns(scores_map: Dict[str, float]) -> List[Dict[str, str]]:
    """Analisa CAUSA RAIZ e correlações complexas (Sintoma vs Causa)."""
    insights = []
    
    def get_score(key_part):
        for k, v in scores_map.items():
            if key_part.lower() in k.lower(): return v * 3.33 
        return 0

    fin = get_score('financeiro')
    pes = get_score('pessoas')
    est = get_score('estratégico')
    proc = get_score('operacional')
    vend = get_score('comercial')
    jur = get_score('jurídico')

    if vend <= 5 and fin <= 4:
        insights.append({"perfil": "⚠️ Vender muito, Lucrar pouco", "analise": "Pode estar a 'pagar para trabalhar'. O problema não é falta de clientes, é que o preço ou os custos estão a comer a margem de lucro.", "risco": "Vender cada vez mais e ver a conta bancária cada vez menor.", "recomendacao": "Revisar preços e custos antes de investir em mais vendas."})
    if fin >= 7 and pes <= 4:
        insights.append({"perfil": "⚠️ Caixa Cheio, Equipa Vazia", "analise": "A empresa tem dinheiro hoje, mas as pessoas estão infelizes. Isso vai gerar saídas de funcionários (turnover) que custarão caro no futuro.", "risco": "Perder os melhores talentos para a concorrência.", "recomendacao": "Investir em retenção e liderança humana."})
    if est >= 7 and proc <= 4:
        insights.append({"perfil": "⚠️ Muitas Ideias, Pouca Ação", "analise": "Você sabe exatamente onde quer chegar, mas o dia a dia é um caos. A operação não consegue entregar o que a sua mente cria.", "risco": "Exaustão mental (Burnout) e promessas não cumpridas aos clientes.", "recomendacao": "Organizar a casa (Processos) antes de inventar novidades."})
    if vend >= 7 and (jur <= 4 or fin <= 4):
        insights.append({"perfil": "⚠️ Gigante com Pés de Barro", "analise": "As vendas vão muito bem, mas a base (contratos e financeiro) é frágil. Um único problema legal ou fiscal pode derrubar tudo o que construiu.", "risco": "Crescer rápido demais e quebrar por falta de estrutura.", "recomendacao": "Blindagem Jurídica e Organização Financeira urgente."})

    return insights

def analyze_data(scores: MDMPScore):
    data = scores.scores_por_pilar
    if not data: raise HTTPException(status_code=400, detail="Sem scores")
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
                try: nome_pilar = list(data.keys())[idx_pilar]
                except: nome_pilar = gargalo_key
                urgencia = (regra['peso'] * 2) + (10 - (data.get(nome_pilar, 5) * 3.33))
                insights.append({"texto": regra['msg'], "urgencia": urgencia})
    
    insights = sorted(insights, key=lambda x: x['urgencia'], reverse=True)[:4]
    
    analise_cruzada = analyze_cross_patterns(data)
    texto_cruzado = "\n### 🧬 O que os números revelam (Causa Raiz)\n" + "\n".join([f"**{i['perfil']}**\n{i['analise']}\n👉 **A Solução:** {i['recomendacao']}\n" for i in analise_cruzada]) if analise_cruzada else ""
    briefing_cruzado = " | ".join([f"[{i['perfil']}]" for i in analise_cruzada]) if analise_cruzada else "Cliente Padrão"

    # Link WhatsApp Dinâmico com mensagem pré-formatada
    import urllib.parse
    msg_zap = f"Olá, recebi o meu diagnóstico Thrive. O meu gargalo é {gargalo_key} e quero resolver."
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
        "briefing": briefing_cruzado,
        "link_zap": link_zap,
        "scores_raw": data
    }

# ==============================================================================
#  GERAÇÃO DE RELATÓRIO (HÍBRIDA)
# ==============================================================================

def generate_fallback_report(analise: dict, cliente_nome: str) -> str:
    """Gera relatório técnico com linguagem acessível e layout premium se IA falhar."""
    media = analise['media']
    if media < 1.6:
        nivel, cor_nivel, desc = "SOBREVIVÊNCIA", "🔴", "A empresa corre riscos sérios. O foco é proteger o caixa."
    elif media < 2.4:
        nivel, cor_nivel, desc = "ORGANIZAÇÃO", "🟡", "A empresa fatura, mas é bagunçada. Precisa de processos."
    else:
        nivel, cor_nivel, desc = "EXPANSÃO", "🟢", "A empresa está saudável. Hora de escalar e inovar."

    lista_prob = "".join([f"❌ {i['texto'].replace('**', '')}\n" for i in analise['insights_list']]) or f"⚠️ Encontrámos ineficiências estruturais no pilar {analise['gargalo_display']}."

    return f"""
# 📊 Relatório de Diagnóstico Empresarial THRIVE

**Cliente:** {cliente_nome} | **Data:** {datetime.now().strftime('%d/%m/%Y')}
**Especialista:** {analise['persona_nome']}

---

## 1. Onde a sua empresa está (MDMP)
**Nota Geral:** {media:.2f} / 3.0

| O Seu Nível | O Que Isso Significa |
| :--- | :--- |
| **{cor_nivel} {nivel}** | {desc} |

### 🏆 O Seu Grande Trunfo: {analise['forte_display']}
A área de **{analise['forte_display']}** é o motor do seu negócio hoje. 
**Dica:** Use a segurança que tem aqui para financiar as melhorias onde tem problemas.

---

## 2. O Problema Principal (Gargalo)
Identificámos que o pilar **{analise['gargalo_display']}** é o que está a travar o seu crescimento.
É como andar com o travão de mão puxado: você gasta energia, mas não sai do lugar.

### 🔍 Pontos de Atenção Imediata:
{lista_prob}
{analise['texto_cruzado']}

---

## 3. O Plano de Ação (Próximos 90 Dias)
Para mudar este cenário, você precisa começar a fazer coisas novas e **parar** de fazer o que não funciona.

### 🛑 PARE AGORA (Stop Doing)
**{analise['stop_doing']}**
*Isso está a gastar o seu tempo e dinheiro sem trazer retorno.*

### ✅ COMECE AGORA (O Seu Plano)

| Fase | O Que Fazer (Ação Prática) | Porquê? (Objetivo) |
| :--- | :--- | :--- |
| **Fase 1: PROTEGER (0-30 Dias)** | **{analise['acao_macro']}** | Para eliminar riscos imediatos e estancar prejuízos. |
| **Fase 2: ORGANIZAR (30-90 Dias)** | Criar um processo padrão (manual) para esta área. | Para que a empresa funcione sem depender 100% de si. |
| **Fase 3: CRESCER (90+ Dias)** | Definir metas de crescimento para este setor. | Para escalar resultados de forma previsível. |

---

## 4. Próximo Passo Recomendado
Este relatório mostra **o que** está errado. O nosso trabalho é ajudar **como** resolver.
Não tente fazer tudo sozinho. 

**CONVITE ESPECIAL:**
A sua empresa tem potencial para o próximo nível.
**[CLIQUE AQUI PARA FALAR COMIGO NO WHATSAPP E AGENDAR UMA DEVOLUTIVA]({analise['link_zap']})**
*Vamos desenhar o mapa detalhado da sua Fase 1 juntos.*

> "{analise['frase']}"

**{analise['persona_nome']}**
*{analise['persona_papel']} - Thrive Business Intelligence*
"""

def generate_report(analise: dict, cliente_nome: str):
    fallback_text = generate_fallback_report(analise, cliente_nome)
    if not GEMINI_API_KEY: return fallback_text, "Modo Técnico (Offline)"

    # Prompt com Personalidade Refinada e Instruções de Layout
    prompt = f"""
    Você é o {analise['persona_nome']} ({analise['persona_papel']}) da Thrive Business.
    Escreva um relatório para o cliente {cliente_nome}.
    
    USE ESTE VOCABULÁRIO NO TEXTO: {analise['vocabulario']}
    
    OBJETIVO: O texto deve ser profissional mas acessível (executivo).
    
    DADOS:
    - Nível: {analise['media']:.2f} (Escala de 1 a 3)
    - Gargalo: {analise['gargalo_display']}
    - Forte: {analise['forte_display']}
    - Ação Principal: "{analise['acao_macro']}"
    - Stop Doing: "{analise['stop_doing']}"
    
    INSIGHTS (Inclua obrigatoriamente): {analise['texto_cruzado']}
    PROBLEMAS: {analise['insights_prioritarios']}
    
    ESTRUTURA OBRIGATÓRIA (Use Markdown e Tabelas):
    1. Intro: Nível da empresa e o que significa.
    2. Ponto Forte: Elogie {analise['forte_display']} e sugira usar como alavanca.
    3. O Problema: Explique o {analise['gargalo_display']} como uma restrição ao crescimento.
    4. Secção STOP DOING (Destaque o que ele deve parar de fazer).
    5. Tabela de Plano de Ação (Proteger, Organizar, Crescer) com a ação principal na fase 1.
    6. Conclusão com Link: "Clique aqui para agendar sua devolutiva: {analise['link_zap']}"
    
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
    
    # Pré-processamento do Markdown para HTML básico para e-mail
    # Nota: Em produção ideal, usaríamos uma lib como 'markdown', mas aqui fazemos o básico para funcionar
    html_report = report.replace('\n', '<br>').replace('**', '<b>').replace('__', '</b>')
    
    cta_button = f"""<a href="{analysis['link_zap']}" style="background-color:#ddcea4; color:#53534a; padding:10px 20px; text-decoration:none; font-weight:bold; border-radius:5px; display:inline-block; margin-top:15px;">Falar com Consultor no WhatsApp</a>"""

    body_html = f"""
    <html><body>
    <h2>Novo Lead ({modo})</h2>
    <p><strong>Cliente:</strong> {scores.nome_cliente} ({scores.email_cliente})</p>
    <p><strong>Contato:</strong> {scores.telefone_cliente or 'N/A'}</p>
    <hr>
    <div style="background: #ffebee; padding: 15px; border-left: 5px solid #f44336; margin-bottom: 20px;">
        <strong>BRIEFING ESTRATÉGICO (Confidencial):</strong><br>{analysis['briefing']}
    </div>
    <h3>Relatório Gerado:</h3>
    <div style="background:#f9f9f9; padding:15px; border: 1px solid #ddd; font-family: sans-serif;">
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
def root(): return {"status": "Online", "mode": "Consultor Senior Pro"}

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

