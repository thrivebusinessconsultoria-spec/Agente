# -*- coding: utf-8 -*-
"""
THRIVE BUSINESS - Backend (FastAPI)
Configurado para Render + Pydantic v2
"""

import os
import logging
import urllib.parse
import threading
from typing import Optional, Dict, List
from datetime import datetime

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# -------------------------
# Configuração e Logging
# -------------------------
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("thrive")


class Config:
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "")
    CONSULTANT_EMAIL: str = os.getenv("CONSULTANT_EMAIL", "thrivebusinessconsultoria@gmail.com")
    WHATSAPP_NUMBER: str = os.getenv("WHATSAPP_NUMBER", "5524992778145")

    # Endpoint da API Gemini
GEMINI_API_URL: str = os.getenv("GEMINI_API_URL", "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent")
RESEND_API_URL: str = os.getenv("RESEND_API_URL", "https://api.resend.com/emails")


if not Config.RESEND_API_KEY:
    logger.warning("⚠️ RESEND_API_KEY não configurada. Emails desativados.")
if not Config.GEMINI_API_KEY:
    logger.warning("⚠️ GEMINI_API_KEY não configurada. IA pode retornar fallback.")

# -------------------------
# Aplicação FastAPI
# -------------------------
app = FastAPI(title="THRIVE Business API", version="2.0.2")

# Configuração CORS para permitir pedidos do Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


# -------------------------
# Modelos Pydantic
# -------------------------
class DiagnosisRequest(BaseModel):
    nome_cliente: str = Field(..., min_length=2, max_length=200)
    email_cliente: str = Field(..., pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    telefone_cliente: Optional[str] = Field(None, max_length=30)
    scores_por_pilar: Dict[str, float] = Field(..., description="Scores na escala 1.0-3.0")
    total_avg: float = Field(..., ge=1.0, le=3.0)
    respostas: Dict[str, int] = Field(default_factory=dict)


class DiagnosisResponse(BaseModel):
    status: str
    gargalo_critico: str
    ponto_forte: str
    analise_ia: str
    score_normalizado: float
    classificacao: str
    media_geral: float


# -------------------------
# Base de Conhecimento
# -------------------------
PERSONAS = {
    "estrategista": {"nome": "Sr. João da Terra", "papel": "O Estrategista",
                     "frase": "Quem não planeia o plantio, não colhe o futuro."},
    "guardia": {"nome": "Dra. Clara Lex", "papel": "A Guardiã", "frase": "Segurança não é custo, é a base do lucro."},
    "hacker": {"nome": "K4J1 (Caju)", "papel": "O Hacker", "frase": "Trabalhe de forma inteligente, não apenas duro."}
}

CRITICAL_TRIGGERS = {
    "p1_q0": {"peso": 9, "msg": "⚠️ Falta de Rumo: ausência de missão clara deixa a equipa sem propósito."},
    "p2_q0": {"peso": 10, "msg": "🚨 Caixa Misturado: contas PF/PJ não segregadas."},
    "p3_q0": {"peso": 9, "msg": "🔗 Conhecimento tribal: processos não documentados."},
    "p7_q3": {"peso": 10, "msg": "💾 Perda de dados: sem backup automatizado na nuvem."},
}

MACRO_PILLARS = {
    "Estratégia e Direção": {"dor": "Falta de Rumo e Visão.", "acao": "Definir OKRs Trimestrais.",
                             "persona": "estrategista"},
    "Gestão Financeira": {"dor": "Risco de Ruína e Descontrolo de Caixa.",
                          "acao": "Segregação Patrimonial e Fluxo de Caixa.", "persona": "guardia"},
    "Operação e Processos": {"dor": "Ineficiência e Dependência do Dono.", "acao": "Mapear Processos Críticos (POP).",
                             "persona": "hacker"},
    "Vendas e Receita": {"dor": "Receita Imprevisível.", "acao": "Estruturar Funil de Vendas e CRM.",
                         "persona": "estrategista"},
    "Pessoas e Gestão de Talentos": {"dor": "Equipa Desengajada e Alta Rotatividade.",
                                     "acao": "Criar Descritivos de Cargos e Rituais 1:1.", "persona": "guardia"},
    "Jurídico e Conformidade": {"dor": "Vulnerabilidade Legal e Passivos.", "acao": "Blindagem Contratual e Registos.",
                                "persona": "guardia"},
    "Tecnologia e Dados": {"dor": "Processos Manuais e Inseguros.",
                           "acao": "SSOT (Sistema Único) e Backup Automatizado.", "persona": "hacker"}
}


# -------------------------
# Motor de Análise
# -------------------------
class MaturityAnalyzer:
    NORMALIZATION_MAX = 3.0

    def __init__(self, payload: DiagnosisRequest):
        self.payload = payload
        self.scores_raw = payload.scores_por_pilar.copy()
        self.respostas = payload.respostas or {}
        self.profile = self._analyze_profile()
        self.scores_adjusted = self._apply_penalties(self.scores_raw)
        self.scores_normalized = self._normalize(self.scores_adjusted)

    def _analyze_profile(self) -> dict:
        size_idx = self.respostas.get("p0_q0", 1)
        if size_idx >= 3:
            return {"tamanho": "Média/Grande", "nivel_exigencia": "crítico"}
        if size_idx == 2:
            return {"tamanho": "Pequena", "nivel_exigencia": "moderado"}
        return {"tamanho": "Micro/Euquipe", "nivel_exigencia": "leniente"}

    def _apply_penalties(self, scores: Dict[str, float]) -> Dict[str, float]:
        adjusted = scores.copy()
        if self.profile["nivel_exigencia"] == "crítico":
            for key in list(adjusted.keys()):
                if "Pessoas" in key or "Jurídico" in key or "Operação" in key:
                    if adjusted[key] < 2.5:
                        adjusted[key] = max(1.0, round(adjusted[key] * 0.85, 2))
        return adjusted

    def _normalize(self, scores: Dict[str, float]) -> Dict[str, float]:
        return {k: round((v / self.NORMALIZATION_MAX) * 10.0, 2) for k, v in scores.items()}

    def get_statistics(self) -> dict:
        if not self.scores_normalized:
            # Fallback seguro
            return {
                "gargalo": "Geral", "forte": "Nenhum", "media_1_3": 1.0,
                "media_0_10": 0.0, "score_gargalo_0_10": 0.0,
                "score_forte_0_10": 0.0, "classificacao": "Sobrevivência"
            }

        bottleneck = min(self.scores_normalized, key=self.scores_normalized.get)
        strength = max(self.scores_normalized, key=self.scores_normalized.get)

        avg_1_3 = round(sum(self.scores_adjusted.values()) / len(self.scores_adjusted), 2)
        avg_0_10 = round((avg_1_3 / self.NORMALIZATION_MAX) * 10.0, 2)

        bottleneck_score = self.scores_normalized[bottleneck]
        classification = self._classify(bottleneck_score)

        return {
            "gargalo": bottleneck,
            "forte": strength,
            "media_1_3": avg_1_3,
            "media_0_10": avg_0_10,
            "score_gargalo_0_10": bottleneck_score,
            "score_forte_0_10": self.scores_normalized[strength],
            "classificacao": classification
        }

    @staticmethod
    def _classify(score: float) -> str:
        if score <= 3.9:
            return "Sobrevivência"
        if score <= 6.9:
            return "Organização"
        return "Expansão"

    def extract_triggers(self) -> List[dict]:
        triggers = []
        stats = self.get_statistics()
        gargalo_score = stats["score_gargalo_0_10"]

        for qid, ans in self.respostas.items():
            if qid in CRITICAL_TRIGGERS and ans == 1:
                t = CRITICAL_TRIGGERS[qid]
                peso = t["peso"]
                if self.profile["nivel_exigencia"] == "crítico":
                    peso += 3
                urgencia = (peso * 2) + (10 - gargalo_score)
                triggers.append({"texto": t["msg"], "urgencia": urgencia})

        triggers.sort(key=lambda x: x["urgencia"], reverse=True)
        return triggers[:4]


# -------------------------
# Serviço IA
# -------------------------
SYSTEM_INSTRUCTION = """
VOCÊ É O CONSULTOR SÊNIOR DA THRIVE BUSINESS.
Siga a estrutura de relatório pedida e seja direto, técnico e orientado para a ação.
Utilize Português de Portugal se não especificado o contrário.
"""


def generate_ai_report(analyzer: MaturityAnalyzer) -> str:
    stats = analyzer.get_statistics()
    triggers = analyzer.extract_triggers()
    bottleneck = stats["gargalo"]
    macro = MACRO_PILLARS.get(bottleneck, list(MACRO_PILLARS.values())[0])
    persona = PERSONAS.get(macro["persona"], {"nome": "Consultor THRIVE", "frase": ""})

    whatsapp_msg = f"Olá, sou {analyzer.payload.nome_cliente}. O meu gargalo é {bottleneck}."
    whatsapp_link = f"https://wa.me/{Config.WHATSAPP_NUMBER}?text={urllib.parse.quote(whatsapp_msg)}"

    # Fallback se a IA falhar ou não estiver configurada
    if not Config.GEMINI_API_KEY:
        fallback = (
                f"# Relatório Consultivo: {bottleneck}\n\n"
                f"## Diagnóstico de Maturidade (MDMP)\nMédia Global: **{stats['media_0_10']}/10** | Classificação: **{stats['classificacao']}**\n\n"
                f"**Ponto Forte:** {stats['forte']} ({stats['score_forte_0_10']}/10)\n"
                f"**Gargalo Crítico:** {bottleneck} ({stats['score_gargalo_0_10']}/10)\n\n"
                f"### Causas identificadas\n"
                + ("\n".join(
            [f"- {t['texto']}" for t in triggers]) if triggers else "- Sem gatilhos críticos detetados.") +
                f"\n\n## Plano Imediato\n- {macro['acao']}\n\n> \"{persona.get('frase', '')}\"\n\n🔗 {whatsapp_link}\n"
        )
        return fallback

    user_prompt = (
            f"{SYSTEM_INSTRUCTION}\n\n"
            f"DADOS: Cliente={analyzer.payload.nome_cliente}, Porte={analyzer.profile['tamanho']}, "
            f"Média={stats['media_0_10']}/10, Gargalo={bottleneck} ({stats['score_gargalo_0_10']}/10)\n\n"
            f"GATILHOS:\n" + ("\n".join([f"- {t['texto']}" for t in triggers]) if triggers else "Nenhum") + "\n\n"
                                                                                                            f"AÇÃO RECOMENDADA: {macro['acao']}\n"
                                                                                                            f"WHATSAPP: {whatsapp_link}\n"
                                                                                                            "Gere o relatório em markdown seguindo a estrutura."
    )

    try:
        payload = {
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": {"temperature": 0.4, "maxOutputTokens": 1500}
        }
        resp = requests.post(f"{Config.GEMINI_API_URL}?key={Config.GEMINI_API_KEY}", json=payload, timeout=45)

        if resp.ok:
            j = resp.json()
            text = j.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text")
            if text:
                return text
            return "⚠️ A IA retornou conteúdo inesperado. Use a versão fallback."
        else:
            logger.error(f"Gemini error {resp.status_code}: {resp.text}")
            return f"⚠️ Erro IA: status {resp.status_code}"
    except Exception as e:
        logger.exception("Erro ao chamar Gemini")
        return f"⚠️ Erro ao gerar IA: {str(e)}"


# -------------------------
# Envio de Email
# -------------------------
def _send_email_sync(analyzer: MaturityAnalyzer, report: str):
    if not Config.RESEND_API_KEY:
        logger.debug("Resend não configurado; a saltar envio de email.")
        return

html_content = report.replace('\n', '<br>').replace('**', '<b>').replace('##', '<h3>')
    payload = {
        "from": "THRIVE Business <onboarding@resend.dev>",  # Obrigatório ser este email no plano grátis
        "reply_to": Config.CONSULTANT_EMAIL,                # As respostas vão para o seu Gmail
        "to": [analyzer.payload.email_cliente, Config.CONSULTANT_EMAIL],
        "subject": f"📊 Novo Diagnóstico: {analyzer.payload.nome_cliente}",
        "html": f"<h2>Diagnóstico de Maturidade</h2><p>Cliente: {analyzer.payload.nome_cliente}</p><hr>{html_content}"
    }
    try:
        resp = requests.post(Config.RESEND_API_URL, json=payload, headers={"Authorization": f"Bearer {Config.RESEND_API_KEY}", "Content-Type": "application/json"},timeout=10)
        if resp.ok:
            logger.info("Email enviado com sucesso.")
        else:
            logger.error(f"Resend failed: {resp.status_code} - {resp.text}")
    except Exception as e:
        logger.exception("Erro ao enviar email")


def send_email_notification_async(analyzer: MaturityAnalyzer, report: str):
    thread = threading.Thread(target=_send_email_sync, args=(analyzer, report), daemon=True)
    thread.start()


# -------------------------
# Rotas
# -------------------------
@app.get("/")
def root():
    return {"message": "THRIVE Business API", "version": "2.0.2"}


@app.get("/api/health")
def health():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "gemini_configured": bool(Config.GEMINI_API_KEY),
        "resend_configured": bool(Config.RESEND_API_KEY)
    }


@app.post("/diagnostico", response_model=DiagnosisResponse)
def create_diagnosis(payload: DiagnosisRequest):
    try:
        logger.info(f"Recebido diagnóstico: {payload.nome_cliente} <{payload.email_cliente}>")
        analyzer = MaturityAnalyzer(payload)
        stats = analyzer.get_statistics()

        report_text = generate_ai_report(analyzer)
        send_email_notification_async(analyzer, report_text)

        return DiagnosisResponse(
            status="success",
            gargalo_critico=stats["gargalo"],
            ponto_forte=stats["forte"],
            analise_ia=report_text,
            score_normalizado=stats["score_gargalo_0_10"],
            classificacao=stats["classificacao"],
            media_geral=stats["media_1_3"]
        )
    except Exception as e:
        logger.exception("Erro no endpoint /diagnostico")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn


    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))

