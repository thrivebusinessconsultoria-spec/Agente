# Importações necessárias
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
# CORREÇÃO: Usar Union do módulo typing para compatibilidade com Python < 3.10
from typing import Dict, Union
import requests
import json
import logging

# Configuração da Aplicação e Logging
app = FastAPI(
    title="Agente de IA THRIVE - API Autônoma",
    description="API para receber scores do MDMP (Maturidade por Pilares) e retornar um Relatório Consultivo Final, utilizando o prompt do Consultor Sênior THRIVE para geração via LLM."
)
# Configuração de logging simples para a simulação
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Variável Placeholder: Chave da API e URL do Gemini (Deve ser configurada no deploy)
GEMINI_API_KEY = "SUA_CHAVE_DE_API_AQUI"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent"

# Sistema de Mensagens (Tom de Voz) - Baseado no Guia
# ESTE É O PROMPT DO CONSULTOR SÊNIOR THRIVE (o conteúdo de Agente_IA_THRIVE_FINAL.txt)
SYSTEM_PROMPT = """[Prompt de Sistema do Consultor Sênior THRIVE (Agente_IA_THRIVE_FINAL.txt)]"""


# === Dados de Contato do Cliente para a Notificação ===
class ClientContact(BaseModel):
    """Informações de contato do cliente que preencheu o MDMP."""
    nome_cliente: str = Field(..., description="Nome completo ou da empresa do cliente.")
    email_cliente: str = Field(..., description="Email do cliente para comunicação.")
    telefone_cliente: str = Field(None, description="Telefone de contato do cliente.")


# Modelo de Dados de Entrada: MDMP - 7 Scores + Contato
class MDMPScore(ClientContact):  # Herda as informações de contato
    """Modelo de dados para os 7 scores de maturidade MDMP."""

    # Cada score deve ser um float entre 1.0 e 3.0
    estrategico: float = Field(..., ge=1.0, le=3.0, description="Score do Pilar Estratégico (1.0 a 3.0)")
    financeiro: float = Field(..., ge=1.0, le=3.0, description="Score do Pilar Financeiro (1.0 a 3.0)")
    operacional: float = Field(..., ge=1.0, le=3.0, description="Score do Pilar Operacional (1.0 a 3.0)")
    comercial: float = Field(..., ge=1.0, le=3.0, description="Score do Pilar Comercial (1.0 a 3.0)")
    pessoas_rh: float = Field(..., ge=1.0, le=3.0, description="Score do Pilar Pessoas/RH (1.0 a 3.0)")
    juridico: float = Field(..., ge=1.0, le=3.0, description="Score do Pilar Jurídico (1.0 a 3.0)")
    tecnologico: float = Field(..., ge=1.0, le=3.0, description="Score do Pilar Tecnológico (1.0 a 3.0)")


# Modelo de Dados de Saída (Relatório)
class ConsultiveReport(BaseModel):
    """Modelo de dados para o Relatório Consultivo Final."""

    status: str = Field(..., description="Status da Geração (Ex: Sucesso)")
    gargalo_critico: str = Field(..., description="O Pilar de Avaliação com a pontuação mais baixa.")
    ponto_forte: str = Field(..., description="O Pilar de Avaliação com a pontuação mais alta.")
    analise_ia: str = Field(..., description="O relatório consultivo gerado pela IA (em formato Markdown).")
    media_geral: float = Field(..., description="Média de maturidade de todos os pilares (1.0 a 3.0)")


# =========================================================================
# Lógica Principal de Cálculo e Processamento
# =========================================================================

# Uso de Union para compatibilidade
def analyze_scores(scores: MDMPScore) -> Dict[str, Union[float, str, Dict]]:
    """Calcula Gargalo Crítico e Ponto Forte e retorna os dados prontos para o Prompt."""

    # Exclui os campos de contato para focar apenas nos scores para a análise numérica
    score_map = scores.model_dump(exclude={'nome_cliente', 'email_cliente', 'telefone_cliente'})

    # 1. Calcular Média
    media_geral = sum(score_map.values()) / len(score_map)

    # 2. Encontrar Gargalo Crítico e Ponto Forte
    min_score = min(score_map.values())
    max_score = max(score_map.values())

    gargalo_critico = next(key for key, value in score_map.items() if value == min_score)
    ponto_forte = next(key for key, value in score_map.items() if value == max_score)

    # Formata os scores em texto para inclusão no prompt
    score_details = "\n".join([f"- {k.replace('_', ' ').title()}: {v:.1f}" for k, v in score_map.items()])

    return {
        "gargalo_critico": gargalo_critico.replace('_', ' ').title(),
        "ponto_forte": ponto_forte.replace('_', ' ').title(),
        "media_geral": media_geral,
        "score_details": score_details,
        "raw_scores": score_map
    }


def generate_report_with_ai(analysis_data: Dict) -> str:
    """Simula a chamada à API do Gemini para gerar o relatório."""

    # 1. Estrutura o prompt específico do usuário (igual à versão anterior)
    user_prompt = (
        "Com base na análise de scores a seguir, gere o Relatório Consultivo Final para o MDMP. "
        "Siga o TOM DE VOZ PREMIUM e as regras do Agente Sênior THRIVE. "
        "O relatório deve ser estruturado em Markdown, com foco no Gargalo Crítico. "
        "1. Título do Relatório (Cirúrgico). 2. Diagnóstico Geral. 3. Detalhamento do Gargalo Crítico (Score e Classificação). 4. 3 Principais Causas Raiz. 5. Plano de Ação Imediato (Ações Táticas)."
        "\n\n--- DADOS DE ENTRADA DO CLIENTE ---\n"
        f"Scores Brutos:\n{analysis_data['score_details']}\n"
        f"Gargalo Crítico Identificado: {analysis_data['gargalo_critico']} (Score {analysis_data['raw_scores'][analysis_data['gargalo_critico'].lower().replace(' ', '_')]:.1f})"
    )

    # 2. Simulação da Geração de Conteúdo pela IA (Resposta Mockada)
    logging.info(f"Simulando chamada LLM com prompt focado em: {analysis_data['gargalo_critico']}")

    gargalo = analysis_data['gargalo_critico']
    score_gargalo = analysis_data['raw_scores'][gargalo.lower().replace(' ', '_')]

    # Define o nível
    if score_gargalo < 1.6:
        nivel = "Sobrevivência e Risco de Ruína"
    elif score_gargalo < 2.4:
        nivel = "Organização e Estagnação"
    else:
        nivel = "Expansão (Mas com Restrição)"

    # --- Pré-calcula o score do Ponto Forte ---
    ponto_forte = analysis_data['ponto_forte']
    score_ponto_forte = analysis_data['raw_scores'][ponto_forte.lower().replace(' ', '_')]

    # Simula a geração de conteúdo pela IA (Mockup formatado).
    simulated_markdown = f"""
# Relatório Consultivo Final: Expondo o Gargalo Crítico na THRIVE BUSINESS

## 1. Diagnóstico Geral (MDMP)

A análise do Modelo de Diagnóstico de Maturidade por Pilares (MDMP) revela que sua empresa possui uma Média Geral de Maturidade de **{analysis_data['media_geral']:.2f}** (em 3.0), posicionando-a majoritariamente na fase de Organização, com exceção do pilar **{gargalo}**.

**Ponto Forte (Alavancagem):** {ponto_forte} ({score_ponto_forte:.1f})

---

## 2. O Gargalo Crítico: Pilar {gargalo} (Score {score_gargalo:.1f})

O pilar **{gargalo}** é, pela Teoria das Restrições, o ponto de menor performance que anula o avanço dos demais pilares. Com um score de **{score_gargalo:.1f}**, classificamos o pilar na fase de **{nivel}**.

**Implicação Primária:** Risco de Ruína e incapacidade de prever o caixa. Sem a sustentação de uma saúde financeira transparente e previsível, a solidez de outros pilares se torna frágil.

### 3. 3 Principais Causas Raiz

1.  **Mistura Patrimonial (PF/PJ):** A confusão entre as finanças pessoais e empresariais impede a visão real da lucratividade.
2.  **Ausência de Fluxo de Caixa Projetado:** A gestão opera no presente, inviabilizando o planejamento de investimentos e a gestão de crises.
3.  **Falta de cálculo de Margem de Contribuição real:** A empresa pode estar investindo tempo e recursos em atividades que geram prejuízo.

---

## 4. Plano de Ação Imediato (Ações Táticas)

Propomos um Plano de Ação Estratégico focado na restrição, detalhado em **Ações Táticas Imediatas** com KPIs de Sucesso definidos.

| Ação Tática | Objetivo | Impacto Esperado |
| :--- | :--- | :--- |
| **Segregação Patrimonial Imediata** | Definir Pró-Labore fixo e contas exclusivas para eliminar a Mistura Patrimonial. | Visualização clara do resultado operacional. |
| **Implementação do Fluxo de Caixa Projetado** | Utilizar um sistema para projetar entradas/saídas para os próximos 90 dias, no mínimo. | Capacidade de prever necessidades de capital de giro e tomar decisões proativas. |
| **Cálculo da Margem de Contribuição** | Determinar o custo variável real por serviço/produto para calcular a Margem de Contribuição. | Focar o esforço comercial nos serviços mais rentáveis. |

**Conclusão do Consultor Sênior THRIVE:** Lembre-se: o sucesso está na execução focada na restrição. Transforme este **Gargalo Crítico** em **Alavancagem Estratégica**.
"""
    return simulated_markdown


# === Funções de Notificação e Armazenamento ===

def notify_consultant(scores: MDMPScore, analysis_data: Dict, report_markdown: str):
    """
    Simula o envio de um e-mail com os resultados do diagnóstico para o consultor sênior.
    Em uma aplicação real, aqui estaria a integração com SMTP, SendGrid, ou um sistema de CRM/Hubspot.
    """
    # Dados do Consultor (Placeholder)
    CONSULTANT_EMAIL = "consultoria@thrivebusiness.com.br"
    SENDER_EMAIL = "no-reply@thrivebusiness.com.br"

    # LOGGING: Simula o envio do Alerta de Lead Quente
    logging.info(f"--- NOTIFICANDO CONSULTOR THRIVE ---")
    logging.info(f"Assunto: NOVO LEAD | {analysis_data['gargalo_critico']} CRÍTICO | {scores.nome_cliente}")
    logging.info(
        f"Cliente: {scores.nome_cliente} | Email: {scores.email_cliente} | Telefone: {scores.telefone_cliente}")
    logging.info(
        f"Gargalo Crítico: {analysis_data['gargalo_critico']} (Score {analysis_data['raw_scores'][analysis_data['gargalo_critico'].lower().replace(' ', '_')]:.1f})")
    logging.info("--- O consultor pode agora iniciar o contato de acompanhamento (follow-up) ---")
    # O conteúdo completo do e-mail conteria o report_markdown para avaliação imediata.


# =========================================================================
# ENDPOINTS DA API
# =========================================================================

@app.get("/api/health", summary="Health check da API")
def health_check():
    """Endpoint para verificar a saúde da API."""
    return {"status": "ok", "service": "THRIVE AI Agent", "version": "1.0"}


@app.post("/api/diagnose", response_model=ConsultiveReport,
          summary="Recebe scores e retorna Relatório Consultivo Final")
def diagnose_mdmp_scores(scores: MDMPScore):
    """
    Recebe os 7 scores do MDMP (Maturidade por Pilares) e orquestra a geração do Relatório Consultivo Final.
    Inclui notificação do consultor sênior.
    """

    try:
        # 1. Análise dos scores (Cálculo do Gargalo e Ponto Forte)
        analysis_data = analyze_scores(scores)

        # 2. Geração do Relatório (Simulação da chamada à IA)
        report_markdown = generate_report_with_ai(analysis_data)

        # 3. NOVO PASSO: Notificação do Consultor
        notify_consultant(scores, analysis_data, report_markdown)

        # 4. Retorno do Relatório no formato Pydantic para o cliente
        return ConsultiveReport(
            status="Sucesso",
            gargalo_critico=analysis_data['gargalo_critico'],
            ponto_forte=analysis_data['ponto_forte'],
            analise_ia=report_markdown,
            media_geral=analysis_data['media_geral']
        )

    except Exception as e:
        logging.error(f"Erro durante o processamento do diagnóstico: {e}")
        # Deve retornar uma HTTPException se for para o cliente
        raise HTTPException(status_code=500, detail=f"Erro interno ao gerar o relatório consultivo: {str(e)}")