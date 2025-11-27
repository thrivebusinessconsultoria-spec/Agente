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

app = FastAPI(title="Agente de IA THRIVE (Consultor Sênior Acessível)")

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
#  CÉREBRO DA THRIVE (BASE DE CONHECIMENTO REFINADA)
# ==============================================================================

PERSONAS = {
    "estrategista": { "nome": "Sr. João da Terra", "papel": "O Estrategista", "frase": "Quem não planeia o plantio, não colhe o futuro." },
    "guardia": { "nome": "Dra. Clara Lex", "papel": "A Guardiã", "frase": "Segurança não é custo, é a base do lucro." },
    "hacker": { "nome": "K4J1 (Caju)", "papel": "O Hacker", "frase": "Trabalhe de forma inteligente, não apenas duro." }
}

REGRAS_GATILHO = {
    "p0_q0": { 1: { "peso": 9, "msg": "⚠️ **Falta de Rumo:** Sem definir claramente a Missão (o 'Porquê'), a equipa trabalha sem propósito e com baixa energia." } },
    "p0_q4": { 1: { "peso": 7, "msg": "🎯 **Cliente Indefinido:** Tentar vender para 'todos' é a receita para gastar muito marketing e vender pouco." } },
    "p0_q11": { 1: { "peso": 10, "msg": "💀 **Dependência Total:** Se você precisar se ausentar hoje, a empresa para? Isso é um risco enorme para a sua família e patrimônio." } },
    "p1_q0": { 1: { "peso": 10, "msg": "🚨 **Caixa Misturado:** Pagar contas de casa com o dinheiro da empresa esconde o lucro real e pode levar à falência sem aviso." } },
    "p1_q4": { 1: { "peso": 9, "msg": "📉 **Gestão no Escuro:** Sem saber exatamente quanto entra e sai hoje, você não pode tomar decisões seguras para amanhã." } },
    "p1_q10": { 1: { "peso": 9, "msg": "⚖️ **Meta de Sobrevivência:** Você desconhece o seu 'Ponto de Equilíbrio'. É como dirigir sem saber quanto combustível resta." } },
    "p2_q2": { 1: { "peso": 9, "msg": "🔗 **Gargalo do Dono:** Você centraliza tudo. Enquanto não delegar, a empresa nunca vai crescer além das suas 24 horas." } },
    "p3_q0": { 1: { "peso": 8, "msg": "📉 **Vendas por Sorte:** Sem um processo visual (Funil), você não sabe quanto vai entrar no final do mês." } },
    "p5_q0": { 1: { "peso": 9, "msg": "🤝 **Acordo de Boca:** Sócios sem contrato escrito é o maior causador de brigas que fecham empresas saudáveis." } },
    "p5_q4": { 1: { "peso": 10, "msg": "⚖️ **Risco Trabalhista:** A informalidade na contratação pode gerar multas que o caixa da empresa não aguenta pagar." } },
    "p6_q2": { 1: { "peso": 10, "msg": "💾 **Perda de Dados:** Sem cópia de segurança (backup) na nuvem, um simples vírus pode apagar anos de trabalho." } }
}

MACRO_PILARES = {
    "1. Estratégico": {
        "dor": "Falta de um caminho claro para o futuro.", 
        "acao": "Definir 3 grandes metas (OKRs) para o trimestre.", 
        "stop_doing": "Pare de decidir baseado apenas no 'feeling' ou na intuição do momento.",
        "persona": "estrategista"
    },
    "2. Financeiro": {
        "dor": "Descontrolo do dinheiro e risco de fechar no vermelho.", 
        "acao": "Implantar o 'Caixa Zero' (anotar tudo o que entra e sai).", 
        "stop_doing": "Pare imediatamente de usar o cartão da empresa para despesas pessoais.",
        "persona": "guardia"
    },
    "3. Operacional": {
        "dor": "A empresa depende 100% da sua presença física.", 
        "acao": "Escrever o manual (POP) da tarefa que mais consome o seu tempo.", 
        "stop_doing": "Pare de centralizar tarefas repetitivas que outros poderiam fazer.",
        "persona": "hacker"
    },
    "4. Comercial": {
        "dor": "Vendas imprevisíveis e dependentes de indicações.", 
        "acao": "Organizar os clientes num Funil de Vendas simples.", 
        "stop_doing": "Pare de esperar sentado que o cliente bata à porta.",
        "persona": "estrategista"
    },
    "5. Pessoas (RH)": {
        "dor": "Equipa desmotivada ou que não sabe o que fazer.", 
        "acao": "Criar descrições simples do que se espera de cada cargo.", 
        "stop_doing": "Pare de dar feedback apenas quando algo corre mal (crítica destrutiva).",
        "persona": "guardia"
    },
    "6. Jurídico": {
        "dor": "Vulnerabilidade a processos e multas.", 
        "acao": "Revisar os contratos principais para garantir segurança.", 
        "stop_doing": "Pare de fechar negócios ou parcerias apenas com acordos verbais.",
        "persona": "guardia"
    },
    "7. Tecnológico": {
        "dor": "Gestão lenta baseada em papel ou memória.", 
        "acao": "Adotar um sistema simples para centralizar as informações.", 
        "stop_doing": "Pare de confiar dados importantes a cadernos ou planilhas soltas.",
        "persona": "hacker"
    }
}

# ==============================================================================
#  MOTOR DE INTELIGÊNCIA (LÓGICA TRADUZIDA)
# ==============================================================================

def analyze_cross_patterns(scores_map: Dict[str, float]) -> List[Dict[str, str]]:
    insights = []
    
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

    # Lógica traduzida para linguagem simples
    if vend <= 5 and fin <= 4:
        insights.append({
            "perfil": "⚠️ Vender muito, Lucrar pouco",
            "analise": "Você pode estar a 'pagar para trabalhar'. O problema não é falta de clientes, é que o preço ou os custos estão a comer a margem de lucro.",
            "risco": "Vender cada vez mais e ver a conta bancária cada vez menor.",
            "recomendacao": "Revisar preços e custos antes de investir em mais vendas."
        })

    if fin >= 7 and pes <= 4:
        insights.append({
            "perfil": "⚠️ Caixa Cheio, Equipa Vazia",
            "analise": "A empresa tem dinheiro hoje, mas as pessoas estão infelizes. Isso vai gerar saídas de funcionários (turnover) que custarão caro no futuro.",
            "risco": "Perder os melhores talentos para a concorrência.",
            "recomendacao": "Investir em retenção e liderança humana."
        })

    if est >= 7 and proc <= 4:
        insights.append({
            "perfil": "⚠️ Muitas Ideias, Pouca Ação",
            "analise": "Você sabe exatamente onde quer chegar, mas o dia a dia é um caos. A operação não consegue entregar o que a sua mente cria.",
            "risco": "Exaustão mental (Burnout) e promessas não cumpridas aos clientes.",
            "recomendacao": "Organizar a casa (Processos) antes de inventar novidades."
        })

    if vend >= 7 and (jur <= 4 or fin <= 4):
        insights.append({
            "perfil": "⚠️ Gigante com Pés de Barro",
            "analise": "As vendas vão muito bem, mas a base (contratos e financeiro) é frágil. Um único problema legal ou fiscal pode derrubar tudo o que construiu.",
            "risco": "Crescer rápido demais e quebrar por falta de estrutura.",
            "recomendacao": "Blindagem Jurídica e Organização Financeira urgente."
        })

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
                try:
                    nome_pilar = list(data.keys())[idx_pilar]
                except IndexError:
                    nome_pilar = gargalo_key
                
                nota = data.get(nome_pilar, 5)
                urgencia = (regra['peso'] * 2) + (10 - (nota * 3.33))
                insights.append({"texto": regra['msg'], "urgencia": urgencia})
    
    insights = sorted(insights, key=lambda x: x['urgencia'], reverse=True)[:4]
    
    analise_cruzada = analyze_cross_patterns(data)
    texto_cruzado = ""
    briefing_cruzado = ""
    if analise_cruzada:
        texto_cruzado = "\n### 🧬 O que os números revelam (Causa Raiz)\n"
        for item in analise_cruzada:
            texto_cruzado += f"**{item['perfil']}**\n{item['analise']}\n👉 **A Solução:** {item['recomendacao']}\n\n"
            briefing_cruzado += f"[{item['perfil']}] -> Sugerir: {item['recomendacao']} | "

    return {
        "gargalo": gargalo_key,
        "gargalo_display": gargalo_key.replace('_', ' ').title(),
        "forte": forte_key,
        "forte_display": forte_key.replace('_', ' ').title(),
        "media": media,
        "persona_nome": persona["nome"],
        "persona_papel": persona["papel"],
        "frase": persona["frase"],
        "dor_macro": macro_info_gargalo["dor"],
        "acao_macro": macro_info_gargalo["acao"],
        "stop_doing": macro_info_gargalo["stop_doing"],
        "insights_list": insights, 
        "insights_prioritarios": "\n".join([f"- {i['texto']}" for i in insights]),
        "texto_cruzado": texto_cruzado,
        "briefing": briefing_cruzado or "Cliente padrão (Upsell de melhoria).",
        "scores_raw": data
    }

# ==============================================================================
#  GERAÇÃO DE RELATÓRIO (HÍBRIDA: IA + FALLBACK ACESSÍVEL)
# ==============================================================================

def generate_fallback_report(analysis_data: dict, cliente_nome: str) -> str:
    """Gera um relatório CLARO, DIRETO e PROFISSIONAL se a IA falhar."""
    
    gargalo = analysis_data['gargalo_display']
    forte = analysis_data['forte_display']
    data_hoje = datetime.now().strftime('%d/%m/%Y')
    media = analysis_data['media']
    
    # Lógica de Nível Traduzida
    if media < 1.6:
        nivel = "SOBREVIVÊNCIA"
        cor_nivel = "🔴"
        descricao_nivel = "A empresa corre riscos sérios. O foco é proteger o caixa."
    elif media < 2.4:
        nivel = "ORGANIZAÇÃO"
        cor_nivel = "🟡"
        descricao_nivel = "A empresa fatura, mas é bagunçada. Precisa de processos."
    else:
        nivel = "EXPANSÃO"
        cor_nivel = "🟢"
        descricao_nivel = "A empresa está saudável. Hora de escalar e inovar."

    lista_problemas = ""
    if analysis_data['insights_list']:
        for item in analysis_data['insights_list']:
            lista_problemas += f"❌ {item['texto'].replace('**', '')}\n"
    else:
        lista_problemas = f"⚠️ Encontrámos ineficiências estruturais no pilar {gargalo}."

    return f"""
# 📊 Relatório de Diagnóstico Empresarial THRIVE

**Cliente:** {cliente_nome} | **Data:** {data_hoje}
**Especialista Responsável:** {analysis_data['persona_nome']}

---

## 1. Onde a sua empresa está hoje?
Analisámos as suas respostas e classificámos o momento atual do negócio.
**Nota Geral:** {media:.2f} / 3.0

| O Seu Nível | O Que Isso Significa |
| :--- | :--- |
| **{cor_nivel} {nivel}** | {descricao_nivel} |

### 🏆 O Seu Grande Trunfo: {forte}
A área de **{forte}** é o motor do seu negócio hoje. 
**Dica:** Use a segurança que tem aqui para financiar as melhorias onde tem problemas.

---

## 2. Onde o sapato aperta (O Problema Principal)
Identificámos que o pilar **{gargalo}** é o que está a travar o seu crescimento.
É como andar com o travão de mão puxado: você gasta energia, mas não sai do lugar.

### 🔍 Pontos de Atenção Imediata:
{lista_problemas}

{analysis_data['texto_cruzado']}

---

## 3. O Plano de Ação (Próximos 90 Dias)
Para mudar este cenário, você precisa começar a fazer coisas novas e **parar** de fazer o que não funciona.

### 🛑 PARE AGORA (Stop Doing)
**{analysis_data['stop_doing']}**
*Isso está a gastar o seu tempo e dinheiro sem trazer retorno.*

### ✅ COMECE AGORA (O Seu Plano)

| Fase | O Que Fazer (Ação Prática) | Porquê? (Objetivo) |
| :--- | :--- | :--- |
| **Fase 1: PROTEGER (0-30 Dias)** | **{analysis_data['acao_macro']}** | Para eliminar riscos imediatos e estancar prejuízos. |
| **Fase 2: ORGANIZAR (30-90 Dias)** | Criar um processo padrão (manual) para esta área. | Para que a empresa funcione sem depender 100% de si. |
| **Fase 3: CRESCER (90+ Dias)** | Definir metas de crescimento para este setor. | Para escalar resultados de forma previsível. |

---

## 4. Próximo Passo Recomendado
Este relatório mostra **o que** está errado. O nosso trabalho é ajudar **como** resolver.
Não tente fazer tudo sozinho. 

**CONVITE ESPECIAL:**
A sua empresa tem potencial para o próximo nível.
**[Responda a este e-mail para agendar uma Sessão de Devolutiva Gratuita]**
*Vamos desenhar o mapa detalhado da sua Fase 1 juntos.*

> "{analysis_data['frase']}"

**{analysis_data['persona_nome']}**
*{analysis_data['persona_papel']} - Thrive Business Intelligence*
"""

def generate_report(analise: dict, cliente_nome: str):
    """Tenta gerar com IA. Se falhar, usa o template acessível acima."""
    
    fallback_text = generate_fallback_report(analise, cliente_nome)

    if not GEMINI_API_KEY:
        return fallback_text, "Modo Técnico (Offline)"

    # Prompt RAG com Instruções de Linguagem Simples
    prompt = f"""
    Você é o Consultor Sênior da Thrive Business ({analise['persona_nome']}).
    Escreva um relatório para o cliente {cliente_nome}.
    
    OBJETIVO: O texto deve ser extremamente profissional, mas FÁCIL DE LER para um dono de pequena empresa que não entende termos técnicos difíceis.
    
    DADOS DO CLIENTE:
    - Nível: {analise['media']:.2f} (Escala de 1 a 3)
    - Principal Problema: {analise['gargalo_display']}
    - Ponto Forte: {analise['forte_display']}
    - Ação Recomendada: "{analise['acao_macro']}"
    - O que PARAR de fazer: "{analise['stop_doing']}"
    
    INSIGHTS (Traduza isso para linguagem de negócios simples):
    {analise['texto_cruzado']}
    
    LISTA DE PROBLEMAS (Seja direto):
    {analise['insights_prioritarios']}
    
    ESTRUTURA DO RELATÓRIO (Use Markdown e Tabelas):
    1. Introdução: Diga o nível da empresa de forma clara.
    2. Análise do Ponto Forte: Elogie a área {analise['forte_display']}.
    3. O Problema: Explique por que o {analise['gargalo_display']} está a travar o crescimento.
    4. Tabela "Pare e Comece": Destaque o que parar de fazer e o plano de 3 fases (Proteger, Organizar, Crescer).
    5. Conclusão: Convide para a "Sessão de Devolutiva" para ajudar a implementar.
    
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
    return {"status": "Thrive API Online", "mode": "Hybrid Pro 8.0 (Accessible Language)"}

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
        "ponto_forte": analise['forte_display'],
        "analise_ia": relatorio,
        "media_geral": analise['media']
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
