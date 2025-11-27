# -*- coding: utf-8 -*-
"""
THRIVE BUSINESS - Sistema de Diagnóstico de Maturidade Empresarial (MDMP)
Agente Consultivo Inteligente com Arquitetura Híbrida (IA + Sistema Especialista)
"""

import os
import logging
from typing import Optional, Dict, List
from datetime import datetime
import urllib.parse

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# ============================================================================
# CONFIGURAÇÃO INICIAL
# ============================================================================

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# VARIÁVEIS DE AMBIENTE
# ============================================================================

class Config:
    """Centraliza todas as configurações do sistema"""
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    RESEND_API_KEY = os.getenv("RESEND_API_KEY")
    CONSULTANT_EMAIL = os.getenv("CONSULTANT_EMAIL", "thrivebusinessconsultoria@gmail.com")
    WHATSAPP_NUMBER = os.getenv("WHATSAPP_NUMBER", "5524992778145")
    
    GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent"
    RESEND_API_URL = "https://api.resend.com/emails"
    
    # Validação
    if not RESEND_API_KEY:
        logger.warning("⚠️ RESEND_API_KEY não configurada. Emails desabilitados.")

# ============================================================================
# MODELOS DE DADOS (PYDANTIC)
# ============================================================================

class DiagnosisRequest(BaseModel):
    """Payload recebido do frontend"""
    nome_cliente: str = Field(..., min_length=2, max_length=200)
    email_cliente: str = Field(..., regex=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    telefone_cliente: Optional[str] = Field(None, max_length=20)
    scores_por_pilar: Dict[str, float] = Field(..., description="Scores na escala 1.0-3.0")
    total_avg: float = Field(..., ge=1.0, le=3.0)
    respostas: Dict[str, int] = Field(default_factory=dict)


class DiagnosisResponse(BaseModel):
    """Resposta enviada ao frontend"""
    status: str
    gargalo_critico: str
    ponto_forte: str
    analise_ia: str
    score_normalizado: float
    classificacao: str
    media_geral: Optional[float] = None

# ============================================================================
# BASE DE CONHECIMENTO - PERSONAS
# ============================================================================

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

# ============================================================================
# BASE DE CONHECIMENTO - GATILHOS CRÍTICOS
# ============================================================================

CRITICAL_TRIGGERS = {
    "p1_q0": {
        1: {
            "peso": 9,
            "msg": "⚠️ **Falta de Rumo:** Ausência de Missão clara deixa a equipa sem propósito."
        }
    },
    "p1_q1": {
        1: {
            "peso": 8,
            "msg": "🔥 **Miopia Estratégica:** Planeamento de longo prazo inexistente ou na cabeça."
        }
    },
    "p2_q0": {
        1: {
            "peso": 10,
            "msg": "🚨 **Caixa Misturado:** Misturar contas PF/PJ é o erro nº 1 que leva à falência."
        }
    },
    "p2_q1": {
        1: {
            "peso": 9,
            "msg": "📉 **Pró-labore Irregular:** Sem valor fixo, não há separação financeira real."
        }
    },
    "p3_q0": {
        1: {
            "peso": 9,
            "msg": "🔗 **Conhecimento Tribal:** Processos não documentados. A qualidade depende de quem executa."
        }
    },
    "p4_q0": {
        1: {
            "peso": 8,
            "msg": "📉 **Vendas por Sorte:** Sem Funil visual, a receita futura é imprevisível."
        }
    },
    "p5_q1": {
        1: {
            "peso": 8,
            "msg": "❌ **Contratação de Risco:** Seleção baseada em urgência, sem fit cultural ou teste de perfil."
        }
    },
    "p6_q2": {
        1: {
            "peso": 10,
            "msg": "⚖️ **Risco Trabalhista:** Informalidade na contratação pode gerar multas explosivas."
        }
    },
    "p7_q3": {
        1: {
            "peso": 10,
            "msg": "💾 **Perda de Dados:** Sem backup automático na nuvem (3-2-1), risco de perda catastrófica."
        }
    }
}

# ============================================================================
# BASE DE CONHECIMENTO - MATRIZ DE RISCOS 360º
# ============================================================================

RISK_MATRIX = {
    "Estratégia e Direção": {
        "impl": "A empresa reage ao mercado em vez de ditá-lo. A ausência de 'Norte Verdadeiro' gera a **Miopia Estratégica**, confundindo movimento operacional com progresso real.",
        "risco_fatal": "Atingir 73% de estagnação (dado de 2024) e perda de relevância, pois 47% das PMEs negligenciam o longo prazo.",
        "causas_raiz": [
            "Negligência do planejamento de médio e longo prazo (47% das lideranças).",
            "Confundir movimento operacional diário com progresso estratégico real.",
            "Aversão à inovação gerada pela complacência."
        ],
        "acao": "Implementação de OKRs Trimestrais",
        "obj": "Alinhamento total da equipe",
        "res": "Foco laser nas prioridades"
    },
    "Gestão Financeira": {
        "impl": "O **Paradoxo da Vulnerabilidade** é real: o faturamento robusto (crescimento de 4,5% em 2024) é corroído pela má gestão interna. Isso leva à falência prematura.",
        "risco_fatal": "Fechamento precoce da empresa (29% das PMEs encerram antes de 5 anos) por incapacidade de converter receita em lucro líquido sustentável.",
        "causas_raiz": [
            "Mistura patrimonial (Caixa da Empresa vs Pessoal).",
            "Incapacidade de gerenciar o lucro retido e reinvestir estrategicamente.",
            "O Custo Brasil (20% do PIB) comprime o fluxo de caixa, exacerbado pela má gestão tributária."
        ],
        "acao": "Segregação Patrimonial e Controle de Fluxo",
        "obj": "Blindar o caixa da empresa",
        "res": "Clareza real do lucro líquido"
    },
    "Operação e Processos": {
        "impl": "A **Ineficiência Operacional** e logística (Custo Brasil) transformam o dono no gargalo. Isso eleva os custos e desvia recursos gerenciais valiosos.",
        "risco_fatal": "Aumento significativo do Custo Brasil interno (R$ 1,7 trilhão/ano) e desequilíbrio do fluxo de caixa por compras impulsivas e má gestão de estoques.",
        "causas_raiz": [
            "Conhecimento tribal: processos na cabeça, sem Padrões Operacionais (POPs) documentados.",
            "Compras impulsivas motivadas por promoções, desequilibrando o fluxo de caixa.",
            "Burocracia interna e custos logísticos elevados, característicos do Custo Brasil."
        ],
        "acao": "Mapeamento do Processo Crítico (POP)",
        "obj": "Retirar o dono da operação",
        "res": "Autonomia da equipe e padrão"
    },
    "Vendas e Receita": {
        "impl": "Vendas por 'sorte' ou indicação. A falta de previsibilidade de receita impede investimentos seguros e compromete a performance, sendo um sintoma de **Complacência**.",
        "risco_fatal": "Estagnação (73% de prevalência) e incapacidade de financiar a expansão em um mercado dinâmico.",
        "causas_raiz": [
            "Ausência de Funil de Vendas estruturado (planilhas ou informalidade).",
            "Foco excessivo na sobrevivência operacional diária, negligenciando a prospecção contínua.",
            "Fidelidade de clientes consolidada gera aversão ao risco e inovação."
        ],
        "acao": "Estruturação do Funil de Vendas e CRM",
        "obj": "Gestão visual do pipeline",
        "res": "Previsibilidade de fechamentos"
    },
    "Pessoas e Gestão de Talentos": {
        "impl": "Baixa performance crônica. A **Alta Rotatividade** de funcionários-chave é uma manifestação da incapacidade da PME de fornecer uma **Proposta de Valor atrativa** ao empregado.",
        "risco_fatal": "Perda de talentos e incapacidade de lidar com a **Transformação Digital** (60% das PMEs não possuem equipes qualificadas).",
        "causas_raiz": [
            "Contratação baseada apenas em 'feeling' ou urgência.",
            "Ausência de rituais de feedback (1:1) e avaliação formal.",
            "Cultura estática que desmotiva colaboradores, levando à saída para concorrentes mais ágeis."
        ],
        "acao": "Criar Descritivos de Cargos e Rituais 1:1",
        "obj": "Alinhamento de expectativas",
        "res": "Retenção e engajamento"
    },
    "Jurídico e Conformidade": {
        "impl": "Vulnerabilidade Legal e Passivos. O risco de litígio é uma ameaça existencial que pode destruir anos de lucro em semanas, comprometendo a **Blindagem** e o **Legado**.",
        "risco_fatal": "Risco Sistêmico da Sucessão (ausência de Holding e Acordo de Quotistas) e passivos trabalhistas explosivos (Pejotização fraudulenta).",
        "causas_raiz": [
            "Informalidade nas contratações (Pejotização fraudulenta e risco subsidiário na Terceirização).",
            "Contratos com clientes e fornecedores não revisados juridicamente.",
            "Ausência de planejamento sucessório e Governança Corporativa."
        ],
        "acao": "Audit de Contratos Críticos e CLT",
        "obj": "Mapear riscos explosivos",
        "res": "Segurança jurídica e blindagem"
    },
    "Tecnologia e Dados": {
        "impl": "A **Ameaça Cibernética** é existencial. 73% das PMEs brasileiras já foram vítimas de ataques, com prejuízos entre R$ 100 mil e R$ 6 milhões.",
        "risco_fatal": "Perda total de dados, interrupção operacional e falência por ataque cibernético (Ransomware é 67% das ameaças).",
        "causas_raiz": [
            "Poucos recursos dedicados à segurança (78% vulneráveis).",
            "Sistemas desatualizados (71%) e falta de Backup adequado (54%).",
            "Erro humano não mitigado por treinamento e autenticação multifator."
        ],
        "acao": "Implementar SSOT (Sistema Único) e Backup 3-2-1",
        "obj": "Eliminar silos de dados",
        "res": "Blindagem contra ataques"
    }
}

# ============================================================================
# BASE DE CONHECIMENTO - MACRO PILARES
# ============================================================================

MACRO_PILLARS = {
    "Estratégia e Direção": {
        "dor": "Falta de Rumo e Visão.",
        "acao": "Definir OKRs Trimestrais.",
        "stop_doing": "Decidir apenas por intuição.",
        "persona": "estrategista"
    },
    "Gestão Financeira": {
        "dor": "Risco de Ruína e Descontrolo de Caixa.",
        "acao": "Segregação Patrimonial e Fluxo de Caixa.",
        "stop_doing": "Misturar contas PF/PJ.",
        "persona": "guardia"
    },
    "Operação e Processos": {
        "dor": "Ineficiência e Dependência do Dono.",
        "acao": "Mapear Processos Críticos (POP).",
        "stop_doing": "Centralizar tarefas delegáveis.",
        "persona": "hacker"
    },
    "Vendas e Receita": {
        "dor": "Receita Imprevisível.",
        "acao": "Estruturar Funil de Vendas e CRM.",
        "stop_doing": "Esperar que o cliente venha até si.",
        "persona": "estrategista"
    },
    "Pessoas e Gestão de Talentos": {
        "dor": "Equipa Desengajada e Alto Turnover.",
        "acao": "Criar Descritivos de Cargos e Rituais 1:1.",
        "stop_doing": "Dar feedback apenas na falha.",
        "persona": "guardia"
    },
    "Jurídico e Conformidade": {
        "dor": "Vulnerabilidade Legal e Passivos.",
        "acao": "Blindagem Contratual e Registros.",
        "stop_doing": "Acordos verbais.",
        "persona": "guardia"
    },
    "Tecnologia e Dados": {
        "dor": "Processos Manuais e Inseguros.",
        "acao": "SSOT (Sistema Único) e Backup Automatizado.",
        "stop_doing": "Confiar gestão a papel e memória.",
        "persona": "hacker"
    }
}

# ============================================================================
# SYSTEM PROMPT PARA IA
# ============================================================================

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
| :-- | :-- | :-- |
| [Ação prática e mensurável p/ 7-15 dias] | [O que resolve?] | [Resultado concreto] |

### Próximos Passos Estratégicos
(Indicar o 2º pilar mais fraco e a razão estratégica de atacá-lo na sequência).

> "[Frase elegante, inspiradora, com vocabulário premium, reforçando Performance e Propósito]"

**[Assinatura do Avatar]**
Consultoria Sênior THRIVE
"""

# ============================================================================
# MOTOR DE ANÁLISE - CLASSE PRINCIPAL
# ============================================================================

class MaturityAnalyzer:
    """Motor de inteligência para análise de maturidade empresarial"""
    
    NORMALIZATION_MAX = 3.0
    
    def __init__(self, request: DiagnosisRequest):
        self.request = request
        self.profile = self._get_company_profile()
        self.scores_adjusted = self._apply_penalties()
        self.scores_normalized = self._normalize_scores()
        
    def _get_company_profile(self) -> dict:
        """Camada 1: Interpretação Contextual e Ponderação de Risco"""
        company_size = self.request.respostas.get("p0_q0", 1)
        
        profiles = {
            1: {
                "tamanho": "Micro/Euquipe",
                "tom_voz": "Próximo e direto. Linguagem simples (não use siglas).",
                "nivel_exigencia": "leniente",
                "mensagem_contexto": "Para microempresas, a sobrevivência depende de caixa e vendas. A informalidade é esperada, mas arriscada."
            },
            2: {
                "tamanho": "Pequena Empresa",
                "tom_voz": "Profissional, direto e educativo. Foco em processos.",
                "nivel_exigencia": "moderado",
                "mensagem_contexto": "Você está na zona de crescimento. A informalidade que funcionava antes agora é o seu maior risco."
            }
        }
        
        # Default para empresas médias/grandes (3+)
        if company_size >= 3:
            return {
                "tamanho": "Média/Grande",
                "tom_voz": "Formal, estruturado e analítico. Use termos executivos e KPIs.",
                "nivel_exigencia": "crítico",
                "mensagem_contexto": "Para o seu porte, a falta de governança e dados é um risco inaceitável. O foco é Governança e Cultura."
            }
        
        return profiles.get(company_size, profiles[1])
    
    def _apply_penalties(self) -> Dict[str, float]:
        """Aplica penalidades baseadas no porte da empresa"""
        scores = self.request.scores_por_pilar.copy()
        
        if self.profile["nivel_exigencia"] == "crítico":
            critical_pillars = ["Pessoas e Gestão de Talentos", "Operação e Processos", "Jurídico e Conformidade"]
            for pillar in critical_pillars:
                if pillar in scores and scores[pillar] < 2.5:
                    scores[pillar] = max(1.0, scores[pillar] * 0.85)
        
        return scores
    
    def _normalize_scores(self) -> Dict[str, float]:
        """Normaliza scores de 1.0-3.0 para 0-10"""
        return {
            pillar: (score / self.NORMALIZATION_MAX) * 10.0
            for pillar, score in self.scores_adjusted.items()
        }
    
    def get_statistics(self) -> dict:
        """Calcula estatísticas principais"""
        bottleneck = min(self.scores_normalized, key=self.scores_normalized.get)
        strength = max(self.scores_normalized, key=self.scores_normalized.get)
        
        avg_1_3 = sum(self.scores_adjusted.values()) / len(self.scores_adjusted)
        avg_0_10 = (avg_1_3 / self.NORMALIZATION_MAX) * 10.0
        
        bottleneck_score = self.scores_normalized[bottleneck]
        classification = self._classify_score(bottleneck_score)
        
        return {
            "gargalo": bottleneck,
            "forte": strength,
            "media_0_10": avg_0_10,
            "score_gargalo_0_10": bottleneck_score,
            "classificacao": classification
        }
    
    @staticmethod
    def _classify_score(score: float) -> str:
        """Classifica o score em níveis de maturidade"""
        if score <= 3.9:
            return "Sobrevivência"
        elif score <= 6.9:
            return "Organização"
        return "Expansão"
    
    def extract_critical_insights(self) -> List[dict]:
        """Camada 2: Extrai gatilhos críticos das respostas"""
        insights = []
        bottleneck_score = self.get_statistics()["score_gargalo_0_10"]
        
        for question_id, answer in self.request.respostas.items():
            if question_id in CRITICAL_TRIGGERS and answer == 1:
                trigger = CRITICAL_TRIGGERS[question_id][answer]
                weight = trigger["peso"]
                
                # Aumenta peso para empresas grandes
                if self.profile["nivel_exigencia"] == "crítico":
                    weight += 3
                
                urgency = (weight * 2) + (10 - bottleneck_score)
                insights.append({
                    "texto": trigger["msg"],
                    "urgencia": urgency
                })
        
        # Retorna os 4 mais urgentes
        return sorted(insights, key=lambda x: x["urgencia"], reverse=True)[:4]
    
    def analyze_cross_patterns(self) -> List[dict]:
        """Camada 2: Análise de padrões cruzados entre pilares"""
        patterns = []
        
        fin = self.scores_normalized.get("Gestão Financeira", 0.0)
        people = self.scores_normalized.get("Pessoas e Gestão de Talentos", 0.0)
        sales = self.scores_normalized.get("Vendas e Receita", 0.0)
        legal = self.scores_normalized.get("Jurídico e Conformidade", 0.0)
        
        # Padrão 1: Risco Sistêmico em empresas grandes
        if self.profile["nivel_exigencia"] == "crítico" and (legal <= 4.0 or fin <= 4.0 or people <= 4.0):
            patterns.append({
                "perfil": "⚠️ Risco Sistêmico no Porte",
                "analise": f"Sua organização tem porte de corporação ({self.profile['tamanho']}), mas gestão de startup. Isso gera **passivo oculto insustentável** (Ref. Seção IV.1 da Matriz 360º).",
                "risco": "Implosão por falta de compliance.",
                "recomendacao": "Reestruturação de Governança e Compliance Imediato."
            })
        
        # Padrão 2: Vender muito, lucrar pouco
        if sales >= 5.0 and fin <= 4.0:
            patterns.append({
                "perfil": "⚠️ Vender muito, Lucrar pouco",
                "analise": "O esforço comercial é alto, mas a margem é baixa. O problema provável é a **precificação ou custos** (Ref. Paradoxo da Vulnerabilidade: crescimento oco).",
                "risco": "Quebrar por overtrading (vender mais e perder mais rápido).",
                "recomendacao": "Engenharia Financeira para analisar Margem de Contribuição."
            })
        
        return patterns
    
    def generate_analysis(self) -> dict:
        """Gera análise completa consolidada"""
        stats = self.get_statistics()
        bottleneck = stats["gargalo"]
        
        # Mapeia persona e dados do pilar
        macro_info = MACRO_PILLARS.get(bottleneck, MACRO_PILLARS["Estratégia e Direção"])
        persona = PERSONAS[macro_info["persona"]]
        risk_data = RISK_MATRIX.get(bottleneck, RISK_MATRIX["Estratégia e Direção"])
        
        # Extrai insights
        critical_insights = self.extract_critical_insights()
        cross_patterns = self.analyze_cross_patterns()
        
        # Monta texto cruzado
        cross_text = ""
        if cross_patterns:
            cross_text = "\n### 🧬 Diagnóstico Cruzado (Causa Raiz)\n" + "\n".join([
                f"**{p['perfil']}**\n{p['analise']}\n👉 **Ação:** {p['recomendacao']}\n"
                for p in cross_patterns
            ])
        
        briefing = f"PORTE: {self.profile['tamanho']}"
        if cross_patterns:
            briefing += " | " + " | ".join([f"[{p['perfil']}]" for p in cross_patterns])
        
        # Gera link WhatsApp
        whatsapp_msg = f"Olá, sou {self.request.nome_cliente} ({self.profile['tamanho']}). Meu gargalo é {bottleneck} ({stats['classificacao']}). Quero avançar."
        whatsapp_link = f"https://wa.me/{Config.WHATSAPP_NUMBER}?text={urllib.parse.quote(whatsapp_msg)}"
