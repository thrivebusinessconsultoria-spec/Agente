# -*- coding: utf-8 -*-
import os
import logging
from typing import Optional, Dict, Any, List
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

# --- CONFIGURAÇÃO E SEGURANÇA ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
CONSULTANT_EMAIL = os.environ.get("CONSULTANT_EMAIL")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")

if not RESEND_API_KEY:
    logging.warning(" ⚠ RESEND_API_KEY não configurada. O envio de e-mails será ignorado.")

RESEND_API_URL = "https://api.resend.com/emails"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent"
WHATSAPP_NUMBER = os.environ.get("WHATSAPP_NUMBER", "5524992778145")

app = FastAPI(title="Agente IA THRIVE - Consultor Sênior Consolidado")

# CORS - Permitindo acesso de qualquer origem para evitar bloqueios no Front
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# --- MODELOS DE DADOS ---
# Este modelo reflete exatamente o JSON enviado pelo Javascript
class MDMPScore(BaseModel):
    nome_cliente: str
    email_cliente: str
    telefone_cliente: Optional[str] = None
    scores_por_pilar: Dict[str, float]
    total_avg: float  # Média na escala 1.0 a 3.0
    respostas: Optional[Dict[str, int]] = {}

class ConsultiveReport(BaseModel):
    status: str
    gargalo_critico: str
    ponto_forte: str
    analise_ia: str
    score_normalizado: float
    classificacao: str

# ==============================================================================
#  PERSONALIDADES E BASES DE CONHECIMENTO
# ==============================================================================
PERSONAS = {
    "estrategista": {
        "nome": "Sr. João da Terra",
        "papel": "O Estrategista (Coruja Agricultor)",
        "frase": "Quem não planeja o plantio, não colhe o futuro.",
        "vocabulario": "terreno, raízes, colheita, semear, estação, clima, frutos, cultivo, sustentabilidade"
    },
    "guardia": {
        "nome": "Dra. Clara Lex",
        "papel": "A Guardiã (Loba Advogada)",
        "frase": "Segurança não é custo, é a base do lucro.",
        "vocabulario": "blindagem, alicerce, risco, contrato, lei, proteção, conformidade, defesa, passivo, norma"
    },
    "hacker": {
        "nome": "K4J1 (Caju)",
        "papel": "O Hacker (Raposa Hacker)",
        "frase": "Trabalhe de forma inteligente, não apenas duro.",
        "vocabulario": "sistema, bug, atualização, código, rede, conexão, upgrade, versão beta, algoritmo, automação"
    }
}

REGRAS_GATILHO = {
    "p1_q0": {1: {"peso": 9, "msg": " ⚠ **Falta de Rumo:** Ausência de Missão clara deixa a equipa sem propósito."}},
    "p1_q1": {1: {"peso": 8, "msg": " 🔥 **Miopia Estratégica:** Planeamento de longo prazo inexistente ou na cabeça."}},
    "p2_q1": {1: {"peso": 10, "msg": " 🚨 **Caixa Misturado:** Misturar contas PF/PJ é o erro nº 1 que leva à falência."}},
    "p2_q2": {1: {"peso": 9, "msg": " 📉 **Pró-labore Irregular:** Sem valor fixo, não há separação financeira real."}},
    "p3_q0": {1: {"peso": 9, "msg": " 🔗 **Conhecimento Tribal:** Processos não documentados. A qualidade depende de quem executa."}},
    "p4_q0": {1: {"peso": 8, "msg": " 📉 **Vendas por Sorte:** Sem Funil visual, a receita futura é imprevisível."}},
    "p5_q1": {1: {"peso": 8, "msg": " ❌ **Contratação de Risco:** Seleção baseada em urgência, sem fit cultural ou teste de perfil."}},
    "p6_q2": {1: {"peso": 10, "msg": " ⚖ **Risco Trabalhista:** Informalidade na contratação pode gerar multas explosivas."}},
    "p7_q3": {1: {"peso": 10, "msg": " 💾 **Perda de Dados:** Sem backup automático na nuvem (3-2-1), risco de perda catastrófica."}}
}

# BASE DE CONHECIMENTO CIENTÍFICA (Matriz de Riscos 360º)
IMPLICACOES_FATUAIS = {
    "Estratégia e Direção": {
        "impl": "A empresa reage ao mercado em vez de ditá-lo. A ausência de 'Norte Verdadeiro' gera a **Miopia Estratégica**, confundindo movimento operacional com progresso real.",
        "risco_fatal": "Atingir 73% de estagnação (dado de 2024) e perda de relevância, pois 47% das PMEs negligenciam o longo prazo.",
        "causas_raiz": ["Negligência do planejamento de médio e longo prazo (47% das lideranças).", "Confundir movimento operacional diário com progresso estratégico real.", "Aversão à inovação gerada pela complacência."],
        "acao": "Implementação de OKRs Trimestrais", "obj": "Alinhamento total da equipe", "res": "Foco laser nas prioridades"
    },
    "Gestão Financeira": {
        "impl": "O **Paradoxo da Vulnerabilidade** é real: o faturamento robusto (crescimento de 4,5% em 2024) é corroído pela má gestão interna. Isso leva à falência prematura.",
        "risco_fatal": "Fechamento precoce da empresa (29% das PMEs encerram antes de 5 anos) por incapacidade de converter receita em lucro líquido sustentável.",
        "causas_raiz": ["Mistura patrimonial (Caixa da Empresa vs Pessoal).", "Incapacidade de gerenciar o lucro retido e reinvestir estrategicamente.", "O Custo Brasil (20% do PIB) comprime o fluxo de caixa, exacerbado pela má gestão tributária."],
        "acao": "Segregação Patrimonial e Controle de Fluxo", "obj": "Blindar o caixa da empresa", "res": "Clareza real do lucro líquido"
    },
    "Operação e Processos": {
        "impl": "A **Ineficiência Operacional** e logística (Custo Brasil) transformam o dono no gargalo. Isso eleva os custos e desvia recursos gerenciais valiosos.",
        "risco_fatal": "Aumento significativo do Custo Brasil interno (R$ 1,7 trilhão/ano) e desequilíbrio do fluxo de caixa por compras impulsivas e má gestão de estoques.",
        "causas_raiz": ["Conhecimento tribal: processos na cabeça, sem Padrões Operacionais (POPs) documentados.", "Compras impulsivas motivadas por promoções, desequilibrando o fluxo de caixa.", "Burocracia interna e custos logísticos elevados, característicos do Custo Brasil."],
        "acao": "Mapeamento do Processo Crítico (POP)", "obj": "Retirar o dono da operação", "res": "Autonomia da equipe e padrão"
    },
    "Vendas e Receita": {
        "impl": "Vendas por 'sorte' ou indicação. A falta de previsibilidade de receita impede investimentos seguros e compromete a performance, sendo um sintoma de **Complacência**.",
        "risco_fatal": "Estagnação (73% de prevalência) e incapacidade de financiar a expansão em um mercado dinâmico.",
        "causas_raiz": ["Ausência de Funil de Vendas estruturado (planilhas ou informalidade).", "Foco excessivo na sobrevivência operacional diária, negligenciando a prospecção contínua.", "Fidelidade de clientes consolidada gera aversão ao risco e inovação."],
        "acao": "Estruturação do Funil de Vendas e CRM", "obj": "Gestão visual do pipeline", "res": "Previsibilidade de fechamentos"
    },
    "Pessoas e Gestão de Talentos": {
        "impl": "Baixa performance crônica. A **Alta Rotatividade** de funcionários-chave é uma manifestação da incapacidade da PME de fornecer uma **Proposta de Valor atrativa** ao empregado.",
        "risco_fatal": "Perda de talentos e incapacidade de lidar com a **Transformação Digital** (60% das PMEs não possuem equipes qualificadas).",
        "causas_raiz": ["Contratação baseada apenas em 'feeling' ou urgência.", "Ausência de rituais de feedback (1:1) e avaliação formal.", "Cultura estática que desmotiva colaboradores, levando à saída para concorrentes mais ágeis."],
        "acao": "Criar Descritivos de Cargos e Rituais 1:1", "obj": "Alinhamento de expectativas", "res": "Retenção e engajamento"
    },
    "Jurídico e Conformidade": {
        "impl": "Vulnerabilidade Legal e Passivos. O risco de litígio é uma ameaça existencial que pode destruir anos de lucro em semanas, comprometendo a **Blindagem** e o **Legado**.",
        "risco_fatal": "Risco Sistêmico da Sucessão (ausência de Holding e Acordo de Quotistas) e passivos trabalhistas explosivos (Pejotização fraudulenta).",
        "causas_raiz": ["Informalidade nas contratações (Pejotização fraudulenta e risco subsidiário na Terceirização).", "Contratos com clientes e fornecedores não revisados juridicamente.", "Ausência de planejamento sucessório e Governança Corporativa."],
        "acao": "Audit de Contratos Críticos e CLT", "obj": "Mapear riscos explosivos", "res": "Segurança jurídica e blindagem"
    },
    "Tecnologia e Dados": {
        "impl": "A **Ameaça Cibernética** é existencial. 73% das PMEs brasileiras já foram vítimas de ataques, com prejuízos entre R$ 100 mil e R$ 6 milhões.",
        "risco_fatal": "Perda total de dados, interrupção operacional e falência por ataque cibernético (Ransomware é 67% das ameaças).",
        "causas_raiz": ["Poucos recursos dedicados à segurança (78% vulneráveis).", "Sistemas desatualizados (71%) e falta de Backup adequado (54%).", "Erro humano não mitigado por treinamento e autenticação multifator."],
        "acao": "Implementar SSOT (Sistema Único) e Backup 3-2-1", "obj": "Eliminar silos de dados", "res": "Blindagem contra ataques"
    }
}

MACRO_PILARES = {
    "Estratégia e Direção": {"dor": "Falta de Rumo e Visão.", "acao": "Definir OKRs Trimestrais.", "stop_doing": "Decidir apenas por intuição.", "persona": "estrategista"},
    "Gestão Financeira": {"dor": "Risco de Ruína e Descontrolo de Caixa.", "acao": "Segregação Patrimonial e Fluxo de Caixa.", "stop_doing": "Misturar contas PF/PJ.", "persona": "guardia"},
    "Operação e Processos": {"dor": "Ineficiência e Dependência do Dono.", "acao": "Mapear Processos Críticos (POP).", "stop_doing": "Centralizar tarefas delegáveis.", "persona": "hacker"},
    "Vendas e Receita": {"dor": "Receita Imprevisível.", "acao": "Estruturar Funil de Vendas e CRM.", "stop_doing": "Esperar que o cliente venha até si.", "persona": "estrategista"},
    "Pessoas e Gestão de Talentos": {"dor": "Equipa Desengajada e Alto Turnover.", "acao": "Criar Descritivos de Cargos e Rituais 1:1.", "stop_doing": "Dar feedback apenas na falha.", "persona": "guardia"},
    "Jurídico e Conformidade": {"dor": "Vulnerabilidade Legal e Passivos.", "acao": "Blindagem Contratual e Registros.", "stop_doing": "Acordos verbais.", "persona": "guardia"},
    "Tecnologia e Dados": {"dor": "Processos Manuais e Inseguros.", "acao": "SSOT (Sistema Único) e Backup Automatizado.", "stop_doing": "Confiar gestão a papel e memória.", "persona": "hacker"}
}

# O MANUAL OPERACIONAL
SYSTEM_INSTRUCTION = """
VOCÊ É O CONSULTOR SÊNIOR DA THRIVE BUSINESS.
1. IDENTIDADE E VOZ
- Autoridade Técnica: Baseie-se no MDMP e nas **Implicações Fatuais** da Matriz de Riscos 360º. Seja assertivo, nunca hipotético.
- Empatia Estratégica: Zero paternalismo. Postura de parceiro de crescimento.
- Sofisticação: Linguagem formal, elegante, premium. Sem gírias.
- Orientação a Ação: Conduza a Ações Táticas Imediatas. Sem perguntas retóricas.
2. VOCABULÁRIO OBRIGATÓRIO
Use sempre: "Gargalo Crítico", "Alavancagem Estratégica", "Diagnóstico Cirúrgico", "MDMP", "Ações Táticas Imediatas", "Performance e Propósito", "Sustentabilidade Sistêmica", "Blindagem".
Se Classificação = Sobrevivência, use: "Risco de Ruína" e "Risco Sistêmico".
3. VOCABULÁRIO PROIBIDO (CRIME CAPITAL USAR)
NUNCA use: "problema", "problemas", "dificuldade", "ajuda", "ajudar", "tarefas", "melhoria", "coisas para fazer".
4. ESTRUTURA OBRIGATÓRIA DO RELATÓRIO (MARKDOWN):
# Relatório Consultivo Final: [Nome do Gargalo Crítico]
## Diagnóstico de Maturidade por Pilares (MDMP)
(Breve análise técnica da média e do ponto forte. Máx 3 linhas.)
## O Gargalo Crítico: Pilar [Nome] (Score X.X/10)
**Classificação:** [Sobrevivência / Organização / Expansão]
**Implicação Primária:** (Qual o impacto central na empresa, usando os dados Fatuais?)
### 3 Principais Causas Raiz
- [Causa 1 - Sistêmica: Relacionar a um Risco Fatal da Matriz 360º]
- [Causa 2 - Processual/Gerencial: Usar um Gatilho Pontual da resposta]
- [Causa 3 - Estratégica/Comportamental: Relacionar ao score baixo]
## Plano de Ação Imediato (Foco no Gargalo)
| Ação Tática Imediata | Objetivo | Impacto Esperado |
| :--- | :--- | :--- |
| [Ação prática e mensurável p/ 7-15 dias] | [O que resolve?] | [Resultado concreto] |
### Próximos Passos Estratégicos
(Indicar o 2º pilar mais fraco e a razão estratégica de atacá-lo na sequência).
> "[Frase elegante, inspiradora, com vocabulário premium, reforçando Performance e Propósito]"
**[Assinatura do Avatar]**
Consultoria Sênior THRIVE
"""

# ==============================================================================
#  MOTOR DE INTELIGÊNCIA
# ==============================================================================
def get_profile_context(respostas: Dict[str, int]) -> dict:
    tamanho_idx = respostas.get("p0_q0", 1)
    perfil = {
        "tamanho": "Micro/Euquipe",
        "tom_voz": "Próximo e direto. Linguagem simples (não use siglas).",
        "nivel_exigencia": "leniente",
        "mensagem_contexto": "Para microempresas, a sobrevivência depende de caixa e vendas. A informalidade é esperada, mas arriscada."
    }
    if tamanho_idx == 2: # Pequena (6-20)
        perfil["tamanho"] = "Pequena Empresa"
        perfil["tom_voz"] = "Profissional, direto e educativo. Foco em processos."
        perfil["nivel_exigencia"] = "moderado"
        perfil["mensagem_contexto"] = "Você está na zona de crescimento. A informalidade que funcionava antes agora é o seu maior risco."
    elif tamanho_idx >= 3: # Média/Grande (21+)
        perfil["tamanho"] = "Média/Grande"
        perfil["tom_voz"] = "Formal, estruturado e analítico. Use termos executivos e KPIs."
        perfil["nivel_exigencia"] = "crítico"
        perfil["mensagem_contexto"] = "Para o seu porte, a falta de governança e dados é um risco inaceitável. O foco é Governança e Cultura."
    return perfil

def analyze_cross_patterns(scores_map: Dict[str, float], perfil: dict) -> List[Dict[str, str]]:
    insights = []
    fin = scores_map.get("Gestão Financeira", 0.0)
    pes = scores_map.get("Pessoas e Gestão de Talentos", 0.0)
    vend = scores_map.get("Vendas e Receita", 0.0)
    jur = scores_map.get("Jurídico e Conformidade", 0.0)
    
    if perfil["nivel_exigencia"] == "crítico" and (jur <= 4.0 or fin <= 4.0 or pes <= 4.0):
        insights.append({
            "perfil": " ⚠ Risco Sistêmico no Porte",
            "analise": f"Sua organização tem porte de corporação ({perfil['tamanho']}), mas gestão de startup. Isso gera **passivo oculto insustentável**.",
            "risco": "Implosão por falta de compliance.",
            "recomendacao": "Reestruturação de Governança e Compliance Imediato."
        })
    if vend >= 5.0 and fin <= 4.0:
        insights.append({
            "perfil": " ⚠ Vender muito, Lucrar pouco",
            "analise": "O esforço comercial é alto, mas a margem é baixa. O problema provável é a **precificação ou custos**.",
            "risco": "Quebrar por overtrading (vender mais e perder mais rápido).",
            "recomendacao": "Engenharia Financeira para analisar Margem de Contribuição."
        })
    return insights

def apply_score_penalty(data: Dict[str, float], perfil: dict) -> Dict[str, float]:
    scores_ajustados = data.copy()
    if perfil["nivel_exigencia"] == "crítico":
        for k in scores_ajustados.keys():
            if "Pessoas" in k or "Operação" in k or "Jurídico" in k:
                if scores_ajustados[k] < 2.5:
                    scores_ajustados[k] = max(1.0, scores_ajustados[k] * 0.85)
    return scores_ajustados

def get_classification(score_0_10: float) -> str:
    if score_0_10 <= 3.9: return "Sobrevivência"
    if score_0_10 <= 6.9: return "Organização"
    return "Expansão"

def analyze_data(scores: MDMPScore):
    data = scores.scores_por_pilar
    if not data: raise HTTPException(status_code=400, detail="Sem scores")

    NORMALIZATION_MAX_SCORE = 3.0
    perfil = get_profile_context(scores.respostas or {})
    scores_ajustados_1_3 = apply_score_penalty(data, perfil)
    
    # Normalização para 0-10
    normalized_data_ajustado = {k: (v / NORMALIZATION_MAX_SCORE) * 10.0 for k, v in scores_ajustados_1_3.items()}

    gargalo_key = min(normalized_data_ajustado, key=normalized_data_ajustado.get)
    forte_key = max(normalized_data_ajustado, key=normalized_data_ajustado.get)
    
    media_geral_1_3 = sum(scores_ajustados_1_3.values()) / len(scores_ajustados_1_3)
    media_geral_0_10 = (media_geral_1_3 / NORMALIZATION_MAX_SCORE) * 10.0
    score_gargalo_0_10 = normalized_data_ajustado[gargalo_key]
    classificacao = get_classification(score_gargalo_0_10)

    macro_info_gargalo = MACRO_PILARES.get(gargalo_key, MACRO_PILARES["Estratégia e Direção"])
    persona = PERSONAS[macro_info_gargalo["persona"]]

    insights = []
    if scores.respostas:
        for q_id, resp in scores.respostas.items():
            if q_id in REGRAS_GATILHO and resp == 1:
                regra = REGRAS_GATILHO[q_id][resp]
                peso_final = regra['peso']
                if perfil["nivel_exigencia"] == "crítico":
                    peso_final += 3
                urgencia = (peso_final * 2) + (10 - score_gargalo_0_10)
                insights.append({"texto": regra['msg'], "urgencia": urgencia})
    
    insights = sorted(insights, key=lambda x: x['urgencia'], reverse=True)[:4]
    analise_cruzada = analyze_cross_patterns(normalized_data_ajustado, perfil)
    
    texto_cruzado = ""
    if analise_cruzada:
        texto_cruzado = "\n### 🧬 Diagnóstico Cruzado (Causa Raiz)\n" + "\n".join([f"**{i['perfil']}**\n{i['analise']}\n 👉 **Ação:** {i['recomendacao']}\n" for i in analise_cruzada])
    
    briefing_cruzado = " | ".join([f"[{i['perfil']}]" for i in analise_cruzada]) if analise_cruzada else "Cliente Padrão"
    fatos_gargalo = IMPLICACOES_FATUAIS.get(gargalo_key, IMPLICACOES_FATUAIS["Estratégia e Direção"])
    
    msg_zap = f"Olá, sou {scores.nome_cliente} ({perfil['tamanho']}). Meu gargalo é {gargalo_key} ({classificacao}). Quero avançar."
    link_zap = f"https://wa.me/{WHATSAPP_NUMBER}?text={urllib.parse.quote(msg_zap)}"

    return {
        "gargalo": gargalo_key,
        "gargalo_display": gargalo_key.title(),
        "score_gargalo_0_10": score_gargalo_0_10,
        "forte": forte_key,
        "forte_display": forte_key.title(),
        "media_0_10": media_geral_0_10,
        "classificacao": classificacao,
        "persona_nome": persona["nome"],
        "persona_papel": persona["papel"],
        "frase": persona["frase"],
        "vocabulario": persona["vocabulario"],
        "dor_macro": macro_info_gargalo["dor"],
        "acao_macro": fatos_gargalo["acao"],
        "stop_doing": macro_info_gargalo["stop_doing"],
        "insights_list": insights,
        "insights_prioritarios": "\n".join([f"- {i['texto']}" for i in insights]),
        "texto_cruzado": texto_cruzado,
        "briefing": f"PORTE: {perfil['tamanho']} | {briefing_cruzado}",
        "link_zap": link_zap,
        "perfil_contexto": perfil["mensagem_contexto"],
        "tom_voz": perfil["tom_voz"],
        "fatos_gargalo": fatos_gargalo,
        "scores_normalizados_0_10": normalized_data_ajustado
    }

# ==============================================================================
#  GERAÇÃO DE RELATÓRIO
# ==============================================================================
def generate_fallback_report(analise: dict) -> str:
    kb_content = analise['fatos_gargalo']
    causas_pontuais = analise.get('insights_prioritarios', "")
    causas_kb = "\n".join([f"- {c}" for c in kb_content['causas_raiz']])
    causas_md = causas_pontuais + "\n" + causas_kb
    causas_md = causas_md.strip()

    scores_sorted = sorted(analise['scores_normalizados_0_10'].items(), key=lambda item: item[1])
    segundo_pilar = scores_sorted[1][0] if len(scores_sorted) > 1 else "Implementação"
    implicacao_primaria = kb_content['impl']

    return f"""
# Relatório Consultivo Final: {analise['gargalo_display']}
## Diagnóstico de Maturidade por Pilares (MDMP)
Sua média de maturidade é **{analise['media_0_10']:.1f}/10**. O **Diagnóstico Cirúrgico** indica que sua **Sustentabilidade Sistêmica** está ancorada em **{analise['forte_display']}**, o que gera a base para a **Alavancagem Estratégica**.
## O Gargalo Crítico: {analise['gargalo_display']} (Score {analise['score_gargalo_0_10']:.1f}/10)
**Classificação:** {analise['classificacao']}
**Implicação Primária:**
{implicacao_primaria}
### 3 Principais Causas Raiz
{causas_md}
{analise['texto_cruzado']}
## Plano de Ação Imediato (Foco no Gargalo)
| Ação Tática Imediata | Objetivo | Impacto Esperado |
| :--- | :--- | :--- |
| **{kb_content['acao']}** | {kb_content['obj']} | {kb_content['res']} |
### Próximos Passos Estratégicos
Após blindar o **Gargalo Crítico**, o ciclo MDMP sugere a imediata atenção ao pilar **{segundo_pilar.title()}** para garantir a continuidade da **Performance e Propósito**.
> "{analise['frase']}"
**{analise['persona_nome']}**
Consultoria Sênior THRIVE
"""

def generate_report(analise: dict, cliente_nome: str):
    fallback_text = generate_fallback_report(analise)
    if not GEMINI_API_KEY:
        return fallback_text, "Modo Especialista (Offline)"
    
    fatos = analise['fatos_gargalo']
    prompt = f"""
    Você é o {analise['persona_nome']} ({analise['persona_papel']}) da Thrive Business.
    INSTRUÇÃO DE LINGUAGEM: O seu tom de voz deve ser {analise['tom_voz']}. Use o vocabulário obrigatório.
    
    CLIENTE: {cliente_nome} | PORTE: {analise['briefing']}
    
    DECISÕES ESTRATÉGICAS JÁ TOMADAS (NÃO ALTERE AS ESTRATÉGIAS NEM A CLASSIFICAÇÃO):
    - Gargalo Crítico (Foco): {analise['gargalo_display']} (Classificação: {analise['classificacao']})
    - Score (0-10): {analise['score_gargalo_0_10']:.1f}
    - Ponto Forte: {analise['forte_display']}
    - Ação Principal (Fase 1): "{fatos['acao']}"
    - Implicação Primária FATUAL (Use no H2): "{fatos['impl']} Risco Fatal: {fatos['risco_fatal']}"
    - Stop Doing: "{analise['stop_doing']}"
    
    INSIGHTS ESPECÍFICOS (Use para gerar as 3 Causas Raiz):
    1. **Fatos da Matriz 360º:** {fatos['causas_raiz']}
    2. **Gatilhos Pontuais:** {analise['insights_prioritarios']}
    3. **Cruzamentos Sistêmicos:** {analise['texto_cruzado']}
    
    Gere o Relatório Consultivo Final seguindo ESTRITAMENTE a Estrutura Obrigatória (Markdown).
    """
    try:
        logging.info(f"Solicitando análise IA para {cliente_nome}...")
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "systemInstruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
            "generationConfig": {"temperature": 0.4, "maxOutputTokens": 1500}
        }
        
        response = requests.post(
            f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
            headers={'Content-Type': 'application/json'},
            json=payload,
            timeout=20
        )
        
        if response.status_code != 200:
            logging.error(f"Erro API Gemini: {response.text}")
            return fallback_text, f"Modo Especialista (Erro API {response.status_code})"
            
        data = response.json()
        if 'candidates' not in data or not data['candidates']:
             logging.warning("Gemini retornou vazio. Usando Fallback.")
             return fallback_text, "Modo Especialista (Segurança)"
        return data['candidates'][0]['content']['parts'][0]['text'], "IA Consultiva"
    
    except Exception as e:
        logging.error(f"Exceção na geração IA: {e}")
        return fallback_text, "Modo Especialista (Erro Conexão)"

def send_email_resend(scores: MDMPScore, analysis: dict, report: str, modo: str):
    if not RESEND_API_KEY: return
    to_email = CONSULTANT_EMAIL if CONSULTANT_EMAIL else "thrivebusinessconsultoria@gmail.com"
    subject = f"DIAGNÓSTICO MDMP: {scores.nome_cliente.upper()} | {analysis['classificacao']}"
    
    html_content = report.replace('\n', '<br>').replace('**', '<b>').replace('__', '</b>')
    html_content = html_content.replace('## ', '<h3>').replace('# ', '<h2>')
    
    cta_button = f"""<a href="{analysis['link_zap']}" style="background-color:#ddcea4; color:#53534a; padding:10px 20px; text-decoration:none; font-weight:bold; border-radius:5px; display:inline-block; margin-top:15px;">AGENDAR IMPLEMENTAÇÃO TÁTICA</a>"""
    body_html = f"""
    <html><body>
    <div style="font-family: sans-serif; color: #333; max-width: 600px; margin: 0 auto;">
        <h2>Novo Lead ({modo}) - {scores.nome_cliente}</h2>
        <p><strong>E-mail:</strong> {scores.email_cliente}</p>
        <p><strong>Contexto:</strong> {analysis['perfil_contexto']}</p>
        <hr>
        <div style="background: #ffebee; padding: 15px; border-left: 5px solid #f44336; margin-bottom: 20px;">
            <strong>BRIEFING ESTRATÉGICO:</strong><br>{analysis['briefing']}
        </div>
        <h3>Relatório Gerado:</h3>
        <div style="background:#f9f9f9; padding:15px; border: 1px solid #ddd;">
            {html_content}
            <br><br>
            {cta_button}
        </div>
    </div>
    </body></html>
    """
    try:
        requests.post(
            RESEND_API_URL,
            json={"from": "Thrive Diagnostico <onboarding@resend.dev>", "to": [to_email, scores.email_cliente], "subject": subject, "html": body_html},
            headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"}
        )
    except Exception as e: logging.error(f"Erro email: {e}")

@app.get("/")
def root(): return {"status": "Online", "mode": "Consultor Senior Consolidado"}

@app.get("/api/health")
def health(): return {"status": "ok"}

@app.post("/diagnostico", response_model=ConsultiveReport)
def diagnose(scores: MDMPScore):
    analise = analyze_data(scores)
    relatorio, modo = generate_report(analise, scores.nome_cliente)
    send_email_resend(scores, analise, relatorio, modo)
    
    return {
        "status": modo, 
        "gargalo_critico": analise['gargalo_display'], 
        "ponto_forte": analise['forte_display'], 
        "analise_ia": relatorio, 
        "score_normalizado": analise['score_gargalo_0_10'],
        "classificacao": analise['classificacao']
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
