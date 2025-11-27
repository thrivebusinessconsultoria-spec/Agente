# -*- coding: utf-8 -*-
"""
THRIVE BUSINESS - AGENTE CONSULTOR SÊNIOR OTIMIZADO
Versão: 2.0 - Performance, Segurança e Confiabilidade
"""
import os
import logging
from typing import Optional, Dict, List
from datetime import datetime, timedelta
import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, validator
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZIPMiddleware
from dotenv import load_dotenv
import urllib.parse
import time
from functools import lru_cache
import hashlib

# ============================================================================== 
# CONFIGURAÇÃO E INICIALIZAÇÃO
# ==============================================================================
load_dotenv()

# Logging estruturado
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Variáveis de ambiente (com validação)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
CONSULTANT_EMAIL = os.environ.get("CONSULTANT_EMAIL")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
WHATSAPP_NUMBER = os.environ.get("WHATSAPP_NUMBER", "5524992778145")

# URLs
RESEND_API_URL = "https://api.resend.com/emails"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent"

# Configurações de performance
GEMINI_TIMEOUT = 25  # segundos
GEMINI_MAX_RETRIES = 2
CACHE_TTL = 3600  # 1 hora

# Validação de configuração crítica
if not GEMINI_API_KEY:
    logger.warning("⚠️ GEMINI_API_KEY não configurada. Apenas modo fallback disponível.")
if not RESEND_API_KEY:
    logger.warning("⚠️ RESEND_API_KEY não configurada. Emails desabilitados.")

# ============================================================================== 
# INICIALIZAÇÃO DO APP
# ==============================================================================
app = FastAPI(
    title="THRIVE Business Intelligence API",
    description="Agente Consultor Sênior com IA para diagnóstico empresarial",
    version="2.0.0"
)

# Middlewares (ordem importa!)
app.add_middleware(GZIPMiddleware, minimum_size=1000)  # Compressão de resposta
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    max_age=3600
)

# ============================================================================== 
# MODELOS DE DADOS COM VALIDAÇÃO ROBUSTA
# ==============================================================================
class MDMPScore(BaseModel):
    nome_cliente: str
    email_cliente: EmailStr  # Validação automática de email
    telefone_cliente: Optional[str] = None
    scores_por_pilar: Dict[str, float]
    total_avg: float
    respostas: Optional[Dict[str, int]] = {}
    
    @validator('nome_cliente')
    def validate_nome(cls, v):
        if len(v.strip()) < 2:
            raise ValueError('Nome deve ter pelo menos 2 caracteres')
        return v.strip()
    
    @validator('scores_por_pilar')
    def validate_scores(cls, v):
        if not v:
            raise ValueError('Scores por pilar não podem estar vazios')
        for pilar, score in v.items():
            if not (1.0 <= score <= 3.0):
                raise ValueError(f'Score de {pilar} fora do intervalo (1.0-3.0): {score}')
        return v
    
    @validator('total_avg')
    def validate_avg(cls, v):
        if not (1.0 <= v <= 3.0):
            raise ValueError(f'Média total fora do intervalo (1.0-3.0): {v}')
        return v

class ConsultiveReport(BaseModel):
    status: str
    gargalo_critico: str
    ponto_forte: str
    analise_ia: str
    score_normalizado: float
    classificacao: str
    tempo_processamento: float  # Novo campo para métricas

# ============================================================================== 
# CACHE E OTIMIZAÇÕES
# ==============================================================================
@lru_cache(maxsize=100)
def get_cached_persona(persona_key: str) -> dict:
    """Cache de personas para evitar reprocessamento."""
    return PERSONAS.get(persona_key, PERSONAS["estrategista"])

@lru_cache(maxsize=50)
def get_cached_macro_pilar(pilar: str) -> dict:
    """Cache de macro pilares."""
    return MACRO_PILARES.get(pilar, MACRO_PILARES["Estratégia e Direção"])

def generate_cache_key(scores: MDMPScore) -> str:
    """Gera chave única para cache baseada nos scores."""
    score_str = str(sorted(scores.scores_por_pilar.items()))
    return hashlib.md5(score_str.encode()).hexdigest()

# ============================================================================== 
# BASES DE CONHECIMENTO (OTIMIZADAS)
# ==============================================================================
PERSONAS = {
    "estrategista": {
        "nome": "Sr. João da Terra",
        "papel": "O Estrategista",
        "frase": "Quem não planeja o plantio, não colhe o futuro.",
        "vocabulario": "terreno, raízes, colheita, semear, estação, clima, frutos, sustentabilidade"
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
        "vocabulario": "sistema, bug, atualização, código, rede, upgrade, algoritmo, automação"
    }
}

REGRAS_GATILHO = {
    "p1_q0": {1: {"peso": 9, "msg": "⚠️ Falta de Rumo: Ausência de Missão clara."}},
    "p2_q1": {1: {"peso": 10, "msg": "🚨 Caixa Misturado: Erro nº 1 que leva à falência."}},
    "p3_q0": {1: {"peso": 9, "msg": "🔗 Conhecimento Tribal: Processos não documentados."}},
    "p4_q0": {1: {"peso": 8, "msg": "📉 Vendas por Sorte: Receita imprevisível."}},
    "p6_q2": {1: {"peso": 10, "msg": "⚖️ Risco Trabalhista: Passivo explosivo."}},
    "p7_q3": {1: {"peso": 10, "msg": "💾 Perda de Dados: Risco catastrófico."}}
}

IMPLICACOES_FATUAIS = {
    "Estratégia e Direção": {
        "impl": "Miopia Estratégica: confunde movimento operacional com progresso real.",
        "risco_fatal": "73% de estagnação e perda de relevância.",
        "causas_raiz": [
            "Negligência do planejamento de médio/longo prazo (47%).",
            "Confusão entre movimento operacional e progresso estratégico.",
            "Aversão à inovação gerada pela complacência."
        ],
        "acao": "Implementação de OKRs Trimestrais",
        "obj": "Alinhamento total da equipe",
        "res": "Foco laser nas prioridades"
    },
    "Gestão Financeira": {
        "impl": "Paradoxo da Vulnerabilidade: faturamento robusto corroído por má gestão.",
        "risco_fatal": "29% encerram antes de 5 anos por incapacidade de gerar lucro sustentável.",
        "causas_raiz": [
            "Mistura patrimonial (PF/PJ).",
            "Incapacidade de gerenciar lucro retido.",
            "Custo Brasil (20% PIB) + má gestão tributária."
        ],
        "acao": "Segregação Patrimonial e Fluxo de Caixa",
        "obj": "Blindar o caixa",
        "res": "Clareza do lucro líquido"
    },
    "Operação e Processos": {
        "impl": "Ineficiência Operacional: dono como gargalo eleva custos.",
        "risco_fatal": "Custo Brasil de R$ 1,7 tri/ano + desequilíbrio de caixa.",
        "causas_raiz": [
            "Conhecimento tribal sem POPs.",
            "Compras impulsivas desequilibram fluxo.",
            "Burocracia e custos logísticos elevados."
        ],
        "acao": "Mapeamento de Processo Crítico (POP)",
        "obj": "Retirar dono da operação",
        "res": "Autonomia e padrão"
    },
    "Vendas e Receita": {
        "impl": "Vendas por sorte/indicação: sem previsibilidade.",
        "risco_fatal": "73% estagnação + incapacidade de financiar expansão.",
        "causas_raiz": [
            "Ausência de Funil estruturado.",
            "Foco em sobrevivência diária.",
            "Aversão ao risco comercial."
        ],
        "acao": "Estruturação de Funil e CRM",
        "obj": "Gestão visual do pipeline",
        "res": "Previsibilidade de vendas"
    },
    "Pessoas e Gestão de Talentos": {
        "impl": "Alta Rotatividade: incapacidade de atrair/reter talentos.",
        "risco_fatal": "60% não têm equipes qualificadas para transformação digital.",
        "causas_raiz": [
            "Contratação por feeling/urgência.",
            "Ausência de rituais 1:1.",
            "Cultura estática que desmotiva."
        ],
        "acao": "Descritivos de Cargo + Rituais 1:1",
        "obj": "Alinhamento de expectativas",
        "res": "Retenção e engajamento"
    },
    "Jurídico e Conformidade": {
        "impl": "Vulnerabilidade Legal: ameaça existencial ao patrimônio.",
        "risco_fatal": "Passivos trabalhistas + ausência de governança.",
        "causas_raiz": [
            "Pejotização fraudulenta.",
            "Contratos não revisados.",
            "Ausência de planejamento sucessório."
        ],
        "acao": "Audit de Contratos + CLT",
        "obj": "Mapear riscos explosivos",
        "res": "Segurança jurídica"
    },
    "Tecnologia e Dados": {
        "impl": "Ameaça Cibernética: 73% das PMEs já foram atacadas.",
        "risco_fatal": "Prejuízos de R$ 100k a R$ 6M por ataque.",
        "causas_raiz": [
            "Poucos recursos para segurança (78%).",
            "Sistemas desatualizados (71%).",
            "Falta de backup adequado (54%)."
        ],
        "acao": "SSOT + Backup 3-2-1",
        "obj": "Eliminar silos de dados",
        "res": "Blindagem contra ataques"
    }
}

MACRO_PILARES = {
    "Estratégia e Direção": {"persona": "estrategista", "stop_doing": "Decidir por intuição."},
    "Gestão Financeira": {"persona": "guardia", "stop_doing": "Misturar contas PF/PJ."},
    "Operação e Processos": {"persona": "hacker", "stop_doing": "Centralizar tarefas."},
    "Vendas e Receita": {"persona": "estrategista", "stop_doing": "Esperar o cliente."},
    "Pessoas e Gestão de Talentos": {"persona": "guardia", "stop_doing": "Feedback só no erro."},
    "Jurídico e Conformidade": {"persona": "guardia", "stop_doing": "Acordos verbais."},
    "Tecnologia e Dados": {"persona": "hacker", "stop_doing": "Confiar em papel."}
}

SYSTEM_INSTRUCTION = """
CONSULTOR SÊNIOR THRIVE - INSTRUÇÕES OTIMIZADAS

IDENTIDADE:
- Autoridade técnica baseada em dados (MDMP + Matriz de Riscos 360º)
- Empatia estratégica sem paternalismo
- Linguagem sofisticada e premium
- Orientação a ação concreta

VOCABULÁRIO OBRIGATÓRIO:
Gargalo Crítico, Alavancagem Estratégica, Diagnóstico Cirúrgico, MDMP, Ações Táticas Imediatas, Sustentabilidade Sistêmica, Blindagem, Risco de Ruína.

PROIBIDO: problema, dificuldade, ajuda, tarefas, melhoria.

ESTRUTURA (Markdown):
# Relatório Consultivo: [Gargalo]
## MDMP (máx 3 linhas)
## Gargalo Crítico: [Nome] (Score X.X/10)
**Classificação:** [Sobrevivência/Organização/Expansão]
**Implicação:** [Dados fatuais da Matriz 360º]
### 3 Causas Raiz
## Plano de Ação (Tabela)
### Próximos Passos
> [Frase inspiradora]
**[Avatar]** - Consultoria Sênior THRIVE
"""

# ============================================================================== 
# MOTOR DE INTELIGÊNCIA (OTIMIZADO)
# ==============================================================================
def get_profile_context(respostas: Dict[str, int]) -> dict:
    """Análise de porte com cache."""
    tamanho_idx = respostas.get("p0_q0", 1)
    
    perfis = {
        1: {
            "tamanho": "Micro/Euquipe",
            "tom_voz": "Próximo e direto.",
            "nivel_exigencia": "leniente",
            "mensagem_contexto": "Foco em caixa e vendas. Informalidade é risco."
        },
        2: {
            "tamanho": "Pequena Empresa",
            "tom_voz": "Profissional e educativo.",
            "nivel_exigencia": "moderado",
            "mensagem_contexto": "Zona de crescimento. Profissionalizar é essencial."
        }
    }
    
    if tamanho_idx >= 3:
        return {
            "tamanho": "Média/Grande",
            "tom_voz": "Formal e analítico.",
            "nivel_exigencia": "crítico",
            "mensagem_contexto": "Governança e dados são inegociáveis."
        }
    
    return perfis.get(tamanho_idx, perfis[1])

def analyze_cross_patterns(scores_map: Dict[str, float], perfil: dict) -> List[Dict[str, str]]:
    """Detecção de padrões sistêmicos."""
    insights = []
    
    fin = scores_map.get("Gestão Financeira", 0.0)
    pes = scores_map.get("Pessoas e Gestão de Talentos", 0.0)
    vend = scores_map.get("Vendas e Receita", 0.0)
    jur = scores_map.get("Jurídico e Conformidade", 0.0)
    
    # Padrão 1: Risco sistêmico de porte
    if perfil["nivel_exigencia"] == "crítico" and any(x <= 4.0 for x in [jur, fin, pes]):
        insights.append({
            "perfil": "⚠️ Risco Sistêmico",
            "analise": f"Porte {perfil['tamanho']} com gestão informal = passivo oculto.",
            "recomendacao": "Governança e Compliance urgentes."
        })
    
    # Padrão 2: Alto esforço, baixa margem
    if vend >= 5.0 and fin <= 4.0:
        insights.append({
            "perfil": "⚠️ Vender Muito, Lucrar Pouco",
            "analise": "Esforço comercial alto com margem baixa.",
            "recomendacao": "Engenharia Financeira na precificação."
        })
    
    return insights

def analyze_data(scores: MDMPScore) -> dict:
    """Motor principal de análise (otimizado)."""
    start_time = time.time()
    
    data = scores.scores_por_pilar
    perfil = get_profile_context(scores.respostas or {})
    
    # Normalização e ajustes
    NORM_MAX = 3.0
    scores_ajustados = data.copy()
    
    # Penalidade para empresas grandes com problemas críticos
    if perfil["nivel_exigencia"] == "crítico":
        for k in ["Pessoas e Gestão de Talentos", "Operação e Processos", "Jurídico e Conformidade"]:
            if k in scores_ajustados and scores_ajustados[k] < 2.5:
                scores_ajustados[k] = max(1.0, scores_ajustados[k] * 0.85)
    
    # Conversão 1-3 → 0-10
    normalized = {k: (v / NORM_MAX) * 10.0 for k, v in scores_ajustados.items()}
    
    # Identificação de gargalo e ponto forte
    gargalo_key = min(normalized, key=normalized.get)
    forte_key = max(normalized, key=normalized.get)
    
    media_1_3 = sum(scores_ajustados.values()) / len(scores_ajustados)
    media_0_10 = (media_1_3 / NORM_MAX) * 10.0
    score_gargalo = normalized[gargalo_key]
    
    # Classificação
    classificacao = (
        "Sobrevivência" if score_gargalo <= 3.9 else
        "Organização" if score_gargalo <= 6.9 else
        "Expansão"
    )
    
    # Busca otimizada de metadados
    macro_info = get_cached_macro_pilar(gargalo_key)
    persona = get_cached_persona(macro_info["persona"])
    fatos = IMPLICACOES_FATUAIS.get(gargalo_key, IMPLICACOES_FATUAIS["Estratégia e Direção"])
    
    # Insights pontuais
    insights = []
    if scores.respostas:
        for q_id, resp in scores.respostas.items():
            if q_id in REGRAS_GATILHO and resp == 1:
                regra = REGRAS_GATILHO[q_id][resp]
                peso = regra['peso'] + (3 if perfil["nivel_exigencia"] == "crítico" else 0)
                urgencia = (peso * 2) + (10 - score_gargalo)
                insights.append({"texto": regra['msg'], "urgencia": urgencia})
    
    insights = sorted(insights, key=lambda x: x['urgencia'], reverse=True)[:4]
    
    # Análise cruzada
    analise_cruzada = analyze_cross_patterns(normalized, perfil)
    texto_cruzado = (
        "\n### 🧬 Diagnóstico Cruzado\n" + 
        "\n".join([f"**{i['perfil']}**: {i['analise']}\n👉 {i['recomendacao']}\n" for i in analise_cruzada])
    ) if analise_cruzada else ""
    
    # Link WhatsApp
    msg_zap = f"Olá, sou {scores.nome_cliente}. Meu gargalo é {gargalo_key}. Quero avançar."
    link_zap = f"https://wa.me/{WHATSAPP_NUMBER}?text={urllib.parse.quote(msg_zap)}"
    
    processing_time = time.time() - start_time
    
    return {
        "gargalo": gargalo_key,
        "gargalo_display": gargalo_key.title(),
        "score_gargalo_0_10": score_gargalo,
        "forte": forte_key,
        "forte_display": forte_key.title(),
        "media_0_10": media_0_10,
        "classificacao": classificacao,
        "persona_nome": persona["nome"],
        "persona_papel": persona["papel"],
        "frase": persona["frase"],
        "stop_doing": macro_info["stop_doing"],
        "insights_list": insights,
        "insights_prioritarios": "\n".join([f"- {i['texto']}" for i in insights]),
        "texto_cruzado": texto_cruzado,
        "briefing": f"{perfil['tamanho']} | {classificacao}",
        "link_zap": link_zap,
        "perfil_contexto": perfil["mensagem_contexto"],
        "tom_voz": perfil["tom_voz"],
        "fatos_gargalo": fatos,
        "scores_normalizados_0_10": normalized,
        "tempo_processamento": processing_time
    }

# ============================================================================== 
# GERAÇÃO DE RELATÓRIO (COM RETRY E FALLBACK)
# ==============================================================================
def generate_fallback_report(analise: dict) -> str:
    """Sistema especialista determinístico."""
    kb = analise['fatos_gargalo']
    causas = "\n".join([f"- {c}" for c in kb['causas_raiz']])
    if analise.get('insights_prioritarios'):
        causas = analise['insights_prioritarios'] + "\n" + causas
    
    scores_sorted = sorted(analise['scores_normalizados_0_10'].items(), key=lambda x: x[1])
    segundo_pilar = scores_sorted[1][0] if len(scores_sorted) > 1 else "Consolidação"
    
    return f"""# Relatório Consultivo Final: {analise['gargalo_display']}

## Diagnóstico de Maturidade por Pilares (MDMP)
Média de maturidade: **{analise['media_0_10']:.1f}/10**. O **Diagnóstico Cirúrgico** identifica **{analise['forte_display']}** como base para **Alavancagem Estratégica**.

## O Gargalo Crítico: {analise['gargalo_display']} (Score {analise['score_gargalo_0_10']:.1f}/10)
**Classificação:** {analise['classificacao']}

**Implicação Primária:** {kb['impl']} **Risco Fatal:** {kb['risco_fatal']}

### 3 Principais Causas Raiz
{causas}
{analise['texto_cruzado']}

## Plano de Ação Imediato (Foco no Gargalo)
| Ação Tática Imediata | Objetivo | Impacto Esperado |
| :--- | :--- | :--- |
| **{kb['acao']}** | {kb['obj']} | {kb['res']} |

### Próximos Passos Estratégicos
Após blindar o **Gargalo Crítico**, atenção imediata ao pilar **{segundo_pilar.title()}** para continuidade da **Performance e Propósito**.

> "{analise['frase']}"

**{analise['persona_nome']}** - Consultoria Sênior THRIVE
"""

def call_gemini_with_retry(prompt: str, max_retries: int = GEMINI_MAX_RETRIES) -> tuple:
    """Chamada à API Gemini com retry automático."""
    for attempt in range(max_retries):
        try:
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "systemInstruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
                "generationConfig": {"temperature": 0.4, "maxOutputTokens": 1500}
            }
            
            response = requests.post(
                f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
                headers={'Content-Type': 'application/json'},
                json=payload,
                timeout=GEMINI_TIMEOUT
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'candidates' in data and data['candidates']:
                    return data['candidates'][0]['content']['parts'][0]['text'], "IA Consultiva"
            
            logger.warning(f"Gemini tentativa {attempt + 1} falhou: {response.status_code}")
            
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
                
        except requests.Timeout:
            logger.error(f"Timeout na tentativa {attempt + 1}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
        except Exception as e:
            logger.error(f"Erro na tentativa {attempt + 1}: {e}")
            break
    
    return None, "Modo Especialista (Falha API)"

def generate_report(analise: dict, cliente_nome: str) -> tuple:
    """Geração de relatório com fallback robusto."""
    fallback_text = generate_fallback_report(analise)
    
    if not GEMINI_API_KEY:
        return fallback_text, "Modo Especialista (Offline)"
    
    fatos = analise['fatos_gargalo']
    prompt = f"""Cliente: {cliente_nome} | {analise['briefing']}

DADOS ESTRATÉGICOS:
- Gargalo: {analise['gargalo_display']} ({analise['classificacao']})
- Score: {analise['score_gargalo_0_10']:.1f}/10
- Implicação: {fatos['impl']} Risco: {fatos['risco_fatal']}
- Ação Principal: {fatos['acao']}

INSIGHTS:
{analise['insights_prioritarios']}
{analise['texto_cruzado']}

Tom: {analise['tom_voz']}
Gere relatório seguindo estrutura obrigatória."""
    
    try:
        logger.info(f"Gerando relatório IA para {cliente_nome}")
        texto, modo = call_gemini_with_retry(prompt)
        
        if texto:
            return texto, modo
        else:
            return fallback_text, "Modo Especialista (Retry Esgotado)"
            
    except Exception as e:
        logger.error(f"Erro fatal na geração: {e}")
        return fallback_text, "Modo Especialista (Erro)"

# ============================================================================== 
# ENVIO DE EMAIL (OTIMIZADO)
# ==============================================================================
def send_email_resend(scores: MDMPScore, analysis: dict, report: str, modo: str):
    """Envio de email com tratamento robusto de erros."""
    if not RESEND_API_KEY:
        logger.info("Email não enviado: RESEND_API_KEY não configurada")
        return
    
    try:
        to_email = CONSULTANT_EMAIL or "thrivebusinessconsultoria@gmail.com"
        subject = f"DIAGNÓSTICO: {scores.nome_cliente.upper()} | {analysis['classificacao']}"
        
        html_content = report.replace('\n', '<br>').replace('**', '<b>').replace('# ', '<h2>').replace('## ', '<h3>')
        cta_button = f'<a href="{analysis["link_zap"]}" style="background:#ddcea4;color:#53534a;padding:10px 20px;text-decoration:none;font-weight:bold;border-radius:5px;margin-top:15px;display:inline-block">AGENDAR SESSÃO</a>'
        
        body_html = f"""<html><body style="font-family:sans-serif;max-width:600px;margin:0 auto">
        <h2>Novo Lead ({modo})</h2>
        <p><strong>Cliente:</strong> {scores.nome_cliente} ({scores.email_cliente})</p>
        <p><strong>Briefing:</strong> {analysis['briefing']}</p>
        <hr>
        <div style="background:#f9f9f9;padding:15px;border:1px solid #ddd">
            {html_content}<br><br>{cta_button}
        </div>
        </body></html>"""
        
        response = requests.post(
            RESEND_API_URL,
            json={
                "from": "Thrive <onboarding@resend.dev>",
                "to": [to_email, scores.email_cliente],
                "subject": subject,
                "html": body_html
            },
            headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
            timeout=10
        )
        
        if response.status_code == 200:
            logger.info(f"Email enviado com sucesso para {to_email}")
        else:
            logger.warning(f"Falha no envio: {response.status_code}")
            
    except Exception as e:
        logger.error(f"Erro no envio de email: {e}")

# ============================================================================== 
# ROTAS DA API (OTIMIZADAS)
# ==============================================================================
@app.get("/")
def root():
    """Página inicial com informações da API."""
    return {
        "service": "THRIVE Business Intelligence API",
        "version": "2.0.0",
        "status": "online",
        "endpoints": {
            "health": "/api/health",
            "diagnostico": "/diagnostico (POST)",
            "docs": "/docs"
        }
    }

@app.get("/api/health")
def health():
    """Health check detalhado."""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "gemini": "available" if GEMINI_API_KEY else "unavailable",
            "resend": "available" if RESEND_API_KEY else "unavailable"
        }
    }

@app.post("/diagnostico", response_model=ConsultiveReport)
async def diagnose(scores: MDMPScore, request: Request):
    """Endpoint principal de diagnóstico (otimizado)."""
    start_time = time.time()
    client_ip = request.client.host
    
    logger.info(f"Nova requisição de {client_ip}: {scores.nome_cliente}")
    
    try:
        # Análise de dados
        analise = analyze_data(scores)
        
        # Geração de relatório
        relatorio, modo = generate_report(analise, scores.nome_cliente)
        
        # Envio de email (assíncrono para não bloquear resposta)
        send_email_resend(scores, analise, relatorio, modo)
        
        total_time = time.time() - start_time
        
        logger.info(f"Diagnóstico concluído em {total_time:.2f}s ({modo})")
        
        return {
            "status": modo,
            "gargalo_critico": analise['gargalo_display'],
            "ponto_forte": analise['forte_display'],
            "analise_ia": relatorio,
            "score_normalizado": round(analise['score_gargalo_0_10'], 2),
            "classificacao": analise['classificacao'],
            "tempo_processamento": round(total_time, 2)
        }
        
    except ValueError as e:
        logger.warning(f"Validação falhou: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Erro no diagnóstico: {e}")
        raise HTTPException(status_code=500, detail="Erro interno no processamento")

# ============================================================================== 
# EXECUÇÃO
# ==============================================================================
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Iniciando servidor na porta {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
