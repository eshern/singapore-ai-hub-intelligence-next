"""
Singapore AI Hub Intelligence — FastAPI Deployment
===================================================
Exposes the multi-agent LangGraph system as a production-ready REST API.

Agents
------
- sg_policy_agent               ChromaDB RAG — Singapore AI policy PDFs (3 docs)
- investment_ecosystem_agent    ChromaDB RAG — EDB / workforce PDFs (3 docs)
- regional_comparison_agent     ChromaDB RAG — ASEAN comparison PDFs (9 docs)
- cybersecurity_compliance_agent ChromaDB RAG — LLM security PDFs (6 docs)
- web_search_agent              Live internet search via DuckDuckGo (no ChromaDB)
- general_agent                 Fallback — base LLM only, no retrieval

Endpoints
---------
GET  /              Health check
POST /query         Single investor query → structured JSON response
POST /query/stream  Streaming version (SSE) for real-time token output
GET  /agents        List available agents and their descriptions
GET  /collections   List ChromaDB collections and their document counts
POST /rebuild-kb    Re-ingest all PDFs into ChromaDB (admin endpoint)

Run (development)
-----------------
    uvicorn api:app --reload --host 0.0.0.0 --port 8000

Run (production)
----------------
    uvicorn api:app --host 0.0.0.0 --port 8000 --workers 2
"""

from __future__ import annotations

import json
import os
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, List, Optional, TypedDict

import chromadb
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Security, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from fastapi.security import APIKeyHeader
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

# ─────────────────────────────────────────────────────────────────────────────
# Environment
# ─────────────────────────────────────────────────────────────────────────────
load_dotenv()

_REQUIRED_KEYS = ["GROQ_API_KEY"]
for _k in _REQUIRED_KEYS:
    if not os.getenv(_k):
        raise RuntimeError(f"Missing required environment variable: {_k}")

os.environ["GROQ_API_KEY"] = os.getenv("GROQ_API_KEY", "")
os.environ["LANGCHAIN_TRACING_V2"] = os.getenv("LANGCHAIN_TRACING_V2", "false")
os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGCHAIN_API_KEY", "")
os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT", "sg-ai-hub-intelligence")

_BASE = os.path.dirname(os.path.abspath(__file__))
DATA_AGENTS_DIR = os.path.join(_BASE, "data_agents")
CHROMA_DB_PATH = os.path.join(_BASE, "chroma_db_agents")
EMBEDDING_MODEL = "all-mpnet-base-v2"
LLM_MODEL = "llama-3.3-70b-versatile"  # PRIMARY: best quality, 131K ctx (100K TPD quota)
# Switch to one of these if daily quota is exhausted (each has its own quota):
# LLM_MODEL = "openai/gpt-oss-120b"    # BEST ALT: 120B params, production-grade
# LLM_MODEL = "openai/gpt-oss-20b"     # LIGHTER ALT: 20B params, faster
# LLM_MODEL = "llama-3.1-8b-instant"   # FASTEST: 8B params, lower quality
# (Verified active Apr 2026 — see console.groq.com/docs/models)

# Optional API key guard for the admin /rebuild-kb endpoint
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")
api_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)

# ─────────────────────────────────────────────────────────────────────────────
# PDF → Collection mapping
# ─────────────────────────────────────────────────────────────────────────────
PDF_COLLECTION_MAP: Dict[str, str] = {
    # ── SG Policy ─────────────────────────────────────────────────────────────
    "Singapore AI Opportunity.pdf": "sg_policy_collection",
    "CSET-Examining-Singapores-AI-Progress.pdf": "sg_policy_collection",
    "Model-AI-Governance-Framework-for-Generative-AI-19-June-2024.pdf": "sg_policy_collection",
    # ── Investment Ecosystem ──────────────────────────────────────────────────
    "EDB_Singapore-Tech-Ecosystem.pdf": "investment_ecosystem_collection",
    "EDB_Guide-to-Hiring-Your-Dream-Tech-Team-in-Singapore.pdf": "investment_ecosystem_collection",
    "Gen-AI_Artificial Intelligence and the Future of Work _sdnea2024001.pdf": "investment_ecosystem_collection",
    # ── Regional Comparison ───────────────────────────────────────────────────
    "State_of_Ai_SEA_Digital.pdf": "regional_comparison_collection",
    "The AI Readiness Barometer-ASEAN AI Landscape.pdf": "regional_comparison_collection",
    "unlocking-southeast-asias-ai-potential.pdf": "regional_comparison_collection",
    "ASEAN-Guide-on-AI-Governance-and-Ethics_beautified_201223_v2.pdf": "regional_comparison_collection",
    "e_conomy_sea_2025_report.pdf": "regional_comparison_collection",
    "ERIA-One-ASEAN-Start-up-White-Paper-2024.pdf": "regional_comparison_collection",
    "Accelerating_SME_AI_Adoption_Through_Open_Source_in_Malaysia_s_Digital_Future_NAIO.pdf": "regional_comparison_collection",
    "THE-NATIONAL-GUIDELINES-ON-AI-GOVERNANCE-ETHICS.pdf": "regional_comparison_collection",
    "Accelerating-AI-Discussions-in-ASEAN-.pdf": "regional_comparison_collection",
    # ── Cybersecurity & Compliance ────────────────────────────────────────────
    "Cybersecurity_Playbook_for_Large_Language_Model_LLM_Applications.pdf": "cybersecurity_compliance_collection",
    "Companion Guide on Securing AI Systems.pdf": "cybersecurity_compliance_collection",
    "Guidelines on Securing AI Systems.pdf": "cybersecurity_compliance_collection",
    "large-language-model-starter-kit.pdf": "cybersecurity_compliance_collection",
    "Securing LLM Backed Systems_ Essential Authorization Practices 20240823.pdf": "cybersecurity_compliance_collection",
    "Singapore Cyber Landscape 2024_2025.pdf": "cybersecurity_compliance_collection",
}

AGENT_TO_COLLECTION: Dict[str, str] = {
    "sg_policy_agent": "sg_policy_collection",
    "investment_ecosystem_agent": "investment_ecosystem_collection",
    "regional_comparison_agent": "regional_comparison_collection",
    "cybersecurity_compliance_agent": "cybersecurity_compliance_collection",
}

AGENT_PERSONA: Dict[str, str] = {
    "sg_policy_agent": (
        "Singapore AI Policy Expert. "
        "You specialise in NAIS 2.0, Model AI Governance Framework (MAIGF), "
        "PDPC guidelines, MAS AI regulations, AI ethics, and the Smart Nation initiative."
    ),
    "investment_ecosystem_agent": (
        "Singapore Investment and Ecosystem Advisor. "
        "You specialise in EDB incentives, Singapore tech clusters, talent pools, "
        "startup grants, industry transformation maps, and setting up a tech company."
    ),
    "regional_comparison_agent": (
        "ASEAN AI Regional Analyst. "
        "You specialise in comparing AI readiness, policy maturity, digital infrastructure, "
        "talent, data centre capacity, and investment climate across Singapore, Malaysia, "
        "Thailand, Indonesia, Vietnam, and Philippines."
    ),
    "cybersecurity_compliance_agent": (
        "LLM Cybersecurity and Compliance Specialist. "
        "You specialise in OWASP LLM Top 10, prompt injection, data poisoning, "
        "PDPA compliance, and regulatory requirements for generative AI deployments."
    ),
}

AGENT_DESCRIPTIONS: Dict[str, str] = {
    "sg_policy_agent": "Singapore national AI strategy, governance, and regulatory frameworks",
    "investment_ecosystem_agent": "EDB incentives, tech talent, ecosystem, and company setup",
    "regional_comparison_agent": "AI readiness and investment climate comparison across ASEAN",
    "cybersecurity_compliance_agent": "LLM security, OWASP, PDPA, and compliance requirements",
    "web_search_agent": "Live internet search for latest news, recent announcements, and real-time data",
    "general_agent": "General assistant for off-topic or greeting queries",
}

VALID_AGENTS = list(AGENT_TO_COLLECTION.keys()) + ["web_search_agent", "general_agent"]

# ─────────────────────────────────────────────────────────────────────────────
# Singleton infrastructure (initialised once on startup)
# ─────────────────────────────────────────────────────────────────────────────
_llm: Optional[ChatGroq] = None
_embeddings: Optional[HuggingFaceEmbeddings] = None
_persistent_client: Optional[chromadb.PersistentClient] = None
_app_graph = None


def get_infrastructure():
    global _llm, _embeddings, _persistent_client
    if _llm is None:
        _llm = ChatGroq(model=LLM_MODEL, temperature=0.2)
        _embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
        _persistent_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    return _llm, _embeddings, _persistent_client


# ─────────────────────────────────────────────────────────────────────────────
# Knowledge base builder
# ─────────────────────────────────────────────────────────────────────────────
def build_knowledge_base(force_rebuild: bool = False) -> Dict[str, int]:
    llm, embeddings, client = get_infrastructure()
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

    existing = {c.name for c in client.list_collections()}
    expected = set(PDF_COLLECTION_MAP.values())
    stats: Dict[str, int] = {}

    if not force_rebuild and expected.issubset(existing):
        for name in expected:
            col = client.get_collection(name)
            stats[name] = col.count()
        return stats

    collection_docs: Dict[str, list] = {}
    for pdf_file, collection_name in PDF_COLLECTION_MAP.items():
        pdf_path = os.path.join(DATA_AGENTS_DIR, pdf_file)
        if not os.path.exists(pdf_path):
            continue
        try:
            docs = PyPDFLoader(pdf_path).load()
            splits = splitter.split_documents(docs)
            collection_docs.setdefault(collection_name, []).extend(splits)
        except Exception:
            pass

    for collection_name, docs in collection_docs.items():
        try:
            try:
                client.delete_collection(collection_name)
            except Exception:
                pass
            Chroma(
                client=client,
                collection_name=collection_name,
                embedding_function=embeddings,
            ).add_documents(docs)
            stats[collection_name] = len(docs)
        except Exception as e:
            stats[collection_name] = -1

    return stats


# ─────────────────────────────────────────────────────────────────────────────
# Agent executors
# ─────────────────────────────────────────────────────────────────────────────
def run_grounded_agent(query: str, agent_name: str, k: int = 5) -> Dict:
    llm, embeddings, client = get_infrastructure()
    collection_name = AGENT_TO_COLLECTION[agent_name]
    persona = AGENT_PERSONA[agent_name]
    try:
        db = Chroma(client=client, collection_name=collection_name, embedding_function=embeddings)
        docs = db.similarity_search(query, k=k)
    except Exception as e:
        return {"agent": agent_name, "answer": f"Retrieval error: {e}", "used_docs": 0}

    context = "\n\n".join(d.page_content for d in docs)
    if not context.strip():
        return {"agent": agent_name, "answer": "No relevant information found.", "used_docs": 0}

    system_prompt = (
        f"You are the {persona}\n\n"
        "STRICT INSTRUCTIONS:\n"
        "- Answer ONLY from the provided Context.\n"
        "- Cite specific data points, statistics, or policy names when present.\n"
        "- If the answer is absent, state: 'This specific information is not available in my knowledge base.'\n"
        "- Use bullet points or numbered lists for clarity.\n"
        "- Do not fabricate information.\n\n"
        f"Context:\n{context}"
    )
    resp = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=query)])
    return {"agent": agent_name, "answer": resp.content, "used_docs": len(docs)}


def run_web_search_agent(query: str) -> Dict:
    '''Search the internet for up-to-date information and synthesise an answer.'''
    llm, _, _ = get_infrastructure()
    search_tool = DuckDuckGoSearchRun()
    try:
        results = search_tool.run(query)
    except Exception as e:
        return {"agent": "web_search_agent",
                "answer": f"Web search unavailable: {e}",
                "used_docs": 0}

    if not results or not results.strip():
        return {"agent": "web_search_agent",
                "answer": "No web search results found for this query.",
                "used_docs": 0}

    system_prompt = (
        "You are a knowledgeable AI assistant specialising in Singapore technology, "
        "AI investment, ASEAN digital economy, and current events. "
        "Use ONLY the web search results below to answer the question accurately and concisely. "
        "Cite key facts and note the recency of information where relevant. "
        "Do not fabricate information beyond what the search results provide.\n\n"
        f"Web Search Results:\n{results}"
    )
    resp = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=query)])
    return {"agent": "web_search_agent", "answer": resp.content, "used_docs": 0}


def run_general_agent(query: str) -> Dict:
    llm, _, _ = get_infrastructure()
    resp = llm.invoke([
        SystemMessage(content=(
            "You are a knowledgeable AI assistant specialising in Singapore technology "
            "and investment landscape. Answer helpfully and concisely."
        )),
        HumanMessage(content=query),
    ])
    return {"agent": "general_agent", "answer": resp.content, "used_docs": 0}


def keyword_fallback_route(query: str) -> List[str]:
    q = query.lower()
    picked = []
    if any(k in q for k in ["policy", "nais", "governance", "regulation", "pdpc", "mas",
                              "framework", "strategy", "ethic", "smart nation"]):
        picked.append("sg_policy_agent")
    if any(k in q for k in ["invest", "edb", "incentive", "talent", "hire", "ecosystem",
                              "company", "setup", "establish", "hub", "cost", "grant",
                              "workforce", "cluster", "startup"]):
        picked.append("investment_ecosystem_agent")
    if any(k in q for k in ["compare", "malaysia", "thailand", "indonesia", "vietnam",
                              "philippines", "asean", "sea", "regional", "readiness",
                              "ranking", "other countr", "neighbour", "neighbor"]):
        picked.append("regional_comparison_agent")
    if any(k in q for k in ["security", "cybersecurity", "llm", "owasp", "compliance",
                              "risk", "prompt injection", "pdpa", "vulnerab"]):
        picked.append("cybersecurity_compliance_agent")
    if any(k in q for k in ["latest", "recent", "current", "now", "today",
                              "news", "2025", "2026", "update", "live",
                              "breaking", "announce", "new report", "this week",
                              "this month", "this year", "just released"]):
        picked.append("web_search_agent")
    return picked or ["general_agent"]


# ─────────────────────────────────────────────────────────────────────────────
# LangGraph state and nodes
# ─────────────────────────────────────────────────────────────────────────────
class InvestorState(TypedDict):
    query: str
    allowed: bool          # set by gatekeeper_node
    selected_agents: List[str]
    routing_reason: str
    agent_outputs: Dict[str, str]
    response: str
    debug_log: str


def gatekeeper_node(state: InvestorState) -> dict:
    """Topic relevance guardrail — runs before any RAG or routing."""
    llm, _, _ = get_infrastructure()
    query = state["query"]

    gatekeeper_prompt = f"""You are a topic relevance classifier for the
Singapore AI Hub Investment Intelligence system.

The system exists to help tech companies evaluate Singapore (and ASEAN) as a
regional AI hub. Answer ONLY with ALLOW or BLOCK.

ALLOWED topics:
- Singapore AI policy: NAIS 2.0, Smart Nation, MAS/PDPC regulations, AI governance
- Singapore investment: EDB incentives, grants, startup ecosystem, operational costs
- Singapore tech ecosystem: talent, hiring, data centres, One-North, tech parks
- ASEAN regional comparison: AI readiness rankings, digital economy, investment climate
  across Singapore, Malaysia, Thailand, Indonesia, Vietnam, Philippines
- Cybersecurity & compliance for AI/LLM deployments (OWASP, PDPA, GenAI frameworks)
- Latest AI news, funding rounds, policy announcements in Singapore or Southeast Asia
- General greetings or clarifying questions about what this chatbot does

BLOCK topics (clearly off-topic):
- Sports, entertainment, celebrities, music, movies, gaming
- Cooking, food, recipes, travel, lifestyle
- Medical or health advice
- Personal finance questions unrelated to Singapore AI investment
- Software debugging / coding help unrelated to AI deployment in Singapore
- Topics about regions with no connection to ASEAN AI investment

RULES:
- When uncertain → ALLOW (a broad AI or investment question may still be useful)
- Partially relevant queries → ALLOW
- Only BLOCK when the query has no plausible connection to Singapore/ASEAN AI investment

EXAMPLES:
Q: What is Singapore's National AI Strategy (NAIS) 2.0?     → ALLOW
Q: How does Singapore rank on AI readiness?                 → ALLOW
Q: Latest AI funding news in 2025?                          → ALLOW
Q: What are OWASP LLM Top 10 risks?                         → ALLOW
Q: Who won the football World Cup?                          → BLOCK
Q: Give me a pasta recipe                                   → BLOCK
Q: What is Python list comprehension?                       → BLOCK

Output ONLY: ALLOW or BLOCK

Query: {query}"""

    result = llm.invoke([SystemMessage(content=gatekeeper_prompt)]).content.strip().upper()
    allowed = "BLOCK" not in result  # ALLOW if response is not exactly BLOCK
    return {
        "allowed": allowed,
        "debug_log": f"[Gatekeeper] {'ALLOWED' if allowed else 'BLOCKED'}: {query[:80]}",
    }


def blocked_response_node(state: InvestorState) -> dict:
    """Polite refusal for queries outside the Singapore/ASEAN AI investment domain."""
    return {
        "response": (
            "I'm specialised in **Singapore AI hub investment intelligence** and can only help with:\n\n"
            "- \U0001f1f8\U0001f1ec Singapore AI policy (NAIS 2.0, Smart Nation, MAS/PDPC regulations)\n"
            "- EDB investment incentives, grants, and ecosystem for tech companies\n"
            "- ASEAN regional comparison (AI readiness, digital economy, investment climate)\n"
            "- Cybersecurity & compliance for AI/LLM deployments in Singapore\n"
            "- Latest AI news, funding, and policy updates in Singapore/Southeast Asia\n\n"
            "Your question appears to be outside this scope. "
            "Please ask something related to Singapore or ASEAN as an AI investment destination."
        ),
        "debug_log": state.get("debug_log", "") + "\n[Gatekeeper] Query blocked — off-topic.",
    }


def router_node(state: InvestorState) -> dict:
    llm, _, _ = get_infrastructure()
    query = state["query"]
    router_prompt = (
        "You are an investment intelligence router for a Singapore AI hub analysis system.\n"
        "Select the most relevant agents for this investor query:\n\n"
        "- sg_policy_agent: NAIS 2.0, governance, PDPC, MAS, AI ethics, Smart Nation\n"
        "- investment_ecosystem_agent: EDB incentives, Singapore tech talent, ecosystem, grants\n"
        "- regional_comparison_agent: Singapore vs ASEAN countries on AI readiness and investment\n"
        "- cybersecurity_compliance_agent: LLM security, OWASP, prompt injection, PDPA\n"
        "- web_search_agent: Queries requiring up-to-date / real-time information: "
        "breaking news, recent announcements, live statistics, current events, "
        "or topics that may have changed after the knowledge base was built "
        "(use for 'latest', 'recent', 'current', 'news', '2025', '2026', etc.)\n"
        "- general_agent: Off-topic or greetings only\n\n"
        'Return STRICT JSON only — no markdown fences:\n'
        '{"agents": ["agent_name", ...], "reason": "one-sentence explanation"}\n\n'
        "Rules:\n"
        "- Include ALL relevant agents for multi-part questions.\n"
        "- For comparison questions always include regional_comparison_agent AND investment_ecosystem_agent.\n"
        "- For queries explicitly asking about latest/recent/current information or news, "
        "always include web_search_agent (alongside domain agents if also relevant).\n"
        "- Avoid general_agent unless the query is clearly off-topic or a simple greeting.\n"
        "- Avoid web_search_agent for stable topics already well-covered by the knowledge base."
    )
    selected, reason = [], "fallback keyword routing"
    try:
        raw = llm.invoke([SystemMessage(content=router_prompt), HumanMessage(content=query)]).content
        clean = raw.strip().lstrip("`").rstrip("`")
        if clean.lower().startswith("json"):
            clean = clean[4:]
        parsed = json.loads(clean.strip())
        selected = [a for a in parsed.get("agents", []) if a in VALID_AGENTS]
        reason = str(parsed.get("reason", "")).strip() or "LLM routing"
        if not selected:
            selected = keyword_fallback_route(query)
    except Exception:
        selected = keyword_fallback_route(query)
    return {
        "selected_agents": selected,
        "routing_reason": reason,
        "debug_log": f"[Router] -> {selected} | {reason}",
    }


def execute_agents_node(state: InvestorState) -> dict:
    query = state["query"]
    selected = state.get("selected_agents", ["general_agent"])
    logs = [state.get("debug_log", "")]
    outputs: Dict[str, str] = {}
    for agent in selected:
        if agent == "general_agent":
            result = run_general_agent(query)
        elif agent == "web_search_agent":
            result = run_web_search_agent(query)
        else:
            result = run_grounded_agent(query, agent)
        outputs[agent] = result["answer"]
        if agent == "web_search_agent":
            logs.append(f"[{agent}] live internet search completed")
        else:
            logs.append(f"[{agent}] retrieved {result.get('used_docs', 0)} chunks")
    return {"agent_outputs": outputs, "debug_log": "\n".join(logs)}


def synthesize_node(state: InvestorState) -> dict:
    llm, _, _ = get_infrastructure()
    query = state["query"]
    outputs = state.get("agent_outputs", {})
    selected = state.get("selected_agents", [])

    if not outputs:
        return {"response": "No response could be generated.", "debug_log": state.get("debug_log", "")}

    if len(outputs) == 1:
        agent = selected[0] if selected else next(iter(outputs))
        return {
            "response": outputs[agent],
            "debug_log": state.get("debug_log", "") + f"\n[Synthesizer] single-agent: {agent}",
        }

    specialist_reports = "\n\n".join(f"[{name}]\n{text}" for name, text in outputs.items())
    synthesis_prompt = (
        "You are a senior investment intelligence analyst preparing an executive briefing.\n"
        "Synthesise the specialist reports into ONE cohesive, executive-level answer.\n\n"
        "Guidelines:\n"
        "- Integrate insights seamlessly — do NOT simply concatenate.\n"
        "- Lead with Singapore's key competitive advantages supported by evidence.\n"
        "- Use structured tables or bullet lists when comparing countries.\n"
        "- Be direct, concise, and actionable.\n"
        "- Do NOT add facts beyond the specialist reports.\n"
        "- If reports conflict, acknowledge the discrepancy.\n\n"
        f"Investor Question:\n{query}\n\n"
        f"Specialist Reports:\n{specialist_reports}"
    )
    final = llm.invoke([
        SystemMessage(content=synthesis_prompt),
        HumanMessage(content="Provide the synthesised executive-level briefing."),
    ]).content
    return {
        "response": final,
        "debug_log": state.get("debug_log", "") + f"\n[Synthesizer] merged {len(outputs)} agents",
    }


def build_graph():
    workflow = StateGraph(InvestorState)
    workflow.add_node("gatekeeper", gatekeeper_node)
    workflow.add_node("blocked", blocked_response_node)
    workflow.add_node("router", router_node)
    workflow.add_node("executor", execute_agents_node)
    workflow.add_node("synthesizer", synthesize_node)
    # Entry point: gatekeeper fires first
    workflow.set_entry_point("gatekeeper")
    # ALLOW → router, BLOCK → immediate polite refusal
    workflow.add_conditional_edges(
        "gatekeeper",
        lambda s: "router" if s.get("allowed", True) else "blocked",
    )
    workflow.add_edge("blocked", END)      # short-circuit — no RAG consumed
    workflow.add_edge("router", "executor")
    workflow.add_edge("executor", "synthesizer")
    workflow.add_edge("synthesizer", END)
    return workflow.compile()


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI lifespan — initialise on startup
# ─────────────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _app_graph
    print("Initialising infrastructure...")
    get_infrastructure()
    build_knowledge_base(force_rebuild=False)
    _app_graph = build_graph()
    print("Ready.")
    yield
    print("Shutting down.")


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI app
# ─────────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Singapore AI Hub Intelligence API",
    description=(
        "Multi-agent investment intelligence system grounded in Singapore AI policy, "
        "EDB ecosystem, ASEAN regional comparison, and LLM cybersecurity datasets."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic schemas
# ─────────────────────────────────────────────────────────────────────────────
class QueryRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=5,
        max_length=2000,
        json_schema_extra={"example": "Why should I set up my AI company in Singapore over Malaysia?"},
    )
    include_debug: bool = Field(False, description="Include orchestration debug log in the response")


class AgentOutput(BaseModel):
    agent: str
    answer: str


class QueryResponse(BaseModel):
    question: str
    answer: str
    agents_used: List[str]
    routing_reason: str
    agent_outputs: Dict[str, str]
    debug_log: Optional[str] = None
    latency_ms: float


class CollectionInfo(BaseModel):
    name: str
    document_count: int


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    """Suppress browser favicon 404 noise."""
    return Response(status_code=204)


@app.get("/", summary="Health check")
def health_check():
    return {"status": "ok", "service": "Singapore AI Hub Intelligence API", "version": "1.0.0"}


@app.post("/query", response_model=QueryResponse, summary="Submit an investor question")
def query_endpoint(request: QueryRequest):
    if _app_graph is None:
        raise HTTPException(status_code=503, detail="System not ready. Retry in a moment.")

    t0 = time.monotonic()
    try:
        result = _app_graph.invoke({"query": request.question})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {e}")
    latency_ms = (time.monotonic() - t0) * 1000

    return QueryResponse(
        question=request.question,
        answer=result.get("response", ""),
        agents_used=result.get("selected_agents", []),
        routing_reason=result.get("routing_reason", ""),
        agent_outputs=result.get("agent_outputs", {}),
        debug_log=result.get("debug_log") if request.include_debug else None,
        latency_ms=round(latency_ms, 1),
    )


@app.post("/query/stream", summary="Submit a question and stream the synthesised answer (SSE)")
async def query_stream_endpoint(request: QueryRequest):
    if _app_graph is None:
        raise HTTPException(status_code=503, detail="System not ready.")

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            result = _app_graph.invoke({"query": request.question})
            answer: str = result.get("response", "")
            agents: List[str] = result.get("selected_agents", [])

            # SSE: send agents header
            yield f"data: {json.dumps({'type': 'agents', 'agents': agents})}\n\n"

            # Stream answer word by word
            words = answer.split(" ")
            buffer = ""
            for i, word in enumerate(words):
                buffer += word + (" " if i < len(words) - 1 else "")
                if len(buffer) >= 40 or i == len(words) - 1:
                    yield f"data: {json.dumps({'type': 'token', 'text': buffer})}\n\n"
                    buffer = ""

            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/agents", summary="List available agents and their descriptions")
def list_agents():
    return {
        "agents": [
            {"name": name, "description": desc}
            for name, desc in AGENT_DESCRIPTIONS.items()
        ]
    }


@app.get("/collections", response_model=List[CollectionInfo], summary="ChromaDB collection stats")
def list_collections():
    _, _, client = get_infrastructure()
    result = []
    for col in client.list_collections():
        try:
            count = client.get_collection(col.name).count()
        except Exception:
            count = -1
        result.append(CollectionInfo(name=col.name, document_count=count))
    return result


@app.post("/rebuild-kb", summary="Re-ingest all PDFs into ChromaDB (admin only)")
def rebuild_knowledge_base(x_admin_key: str = Security(api_key_header)):
    if ADMIN_API_KEY and x_admin_key != ADMIN_API_KEY:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid admin key.")
    stats = build_knowledge_base(force_rebuild=True)
    return {"status": "rebuilt", "collections": stats}
