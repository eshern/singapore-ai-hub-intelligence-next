# Singapore AI Hub Investment Intelligence
## Multi-Agent Intelligence Framework — Developer & User Guide

> **Scope:** This document covers the full system: the `Singapore AI Hub Intelligence.ipynb` notebook, the FastAPI backend (`api.py`), and the Next.js production frontend (`frontend/`).

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Dataset](#3-dataset)
4. [Prerequisites](#4-prerequisites)
5. [Installation](#5-installation)
6. [Environment Configuration](#6-environment-configuration)
7. [Quick Start — Jupyter Notebook](#7-quick-start--jupyter-notebook)
8. [FastAPI Deployment (Backend)](#8-fastapi-deployment-backend)
9. [Frontend (Next.js UI)](#9-frontend-nextjs-ui)
10. [Developer Collaboration](#10-developer-collaboration)
11. [API Reference](#11-api-reference)
12. [LangSmith Observability](#12-langsmith-observability)
13. [User Guide — Investor Chatbot](#13-user-guide--investor-chatbot)
14. [Extending the System](#14-extending-the-system)
15. [Troubleshooting](#15-troubleshooting)

---

## 1. Overview

This project builds a **grounded multi-agent RAG system** that powers an investment intelligence
chatbot. Its central question:

> *As a tech AI company planning a regional AI hub in Asia, why Singapore — and how does it
> compare to neighbouring ASEAN countries?*

The system ingests twenty-one authoritative PDF documents (Singapore government, EDB, CSA Singapore,
and regional research reports), embeds them into domain-specific vector collections, and routes
investor queries to the most appropriate specialist agent(s) before synthesising a single
executive-level answer.

**Key capabilities:**

| Capability | Detail |
|---|---|
| Grounded RAG | All answers cite the source PDFs — no hallucination from training data |
| Multi-agent routing | LLM intent classifier dispatches to 1–5 agents (4 RAG domains + live web search) per query |
| Multi-document synthesis | Specialist outputs are merged into one coherent briefing |
| LangSmith tracing | Full observability: every retrieval, LLM call, and routing decision is traced |
| Dual interface | Gradio chatbot (notebook) + REST API (FastAPI) + Next.js production UI |

---

## 2. Architecture

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│   INVESTOR QUERY INTERFACE  (Gradio Chatbot / FastAPI REST / Next.js UI)         │
└────────────────────────────────────┬─────────────────────────────────────────────┘
                                     │
                                     ▼
          ┌────────────────────────────────────────────────────────────────┐
          │                    GATEKEEPER NODE                             │
          │         (LLM Topic Classifier — LangGraph Entry Point)         │
          │   Is this query within the 5 supported investment domains?     │
          └───────────────────────────┬────────────────────────────────────┘
                                      │
               ┌──────────────────────┴────────────────────────┐
               │ BLOCK                                         │ ALLOW
               ▼                                               ▼
  ┌─────────────────────────────┐    ┌────────────────────────────────────────────────────┐
  │   BLOCKED RESPONSE NODE     │    │            ORCHESTRATOR / ROUTER                   │
  │  Polite refusal — lists 5   │    │   (LLM Intent Classifier + Keyword Fallback)       │
  │  supported domains. Zero    │    │              - selects 1 to 5 agents               │
  │  RAG / LLM calls consumed.  │    └──┬─────────┬──────────┬────────────┬────────────┬──┘
  └─────────────────────────────┘       │         │          │            │            │  
                                        ▼         ▼          ▼            ▼            ▼
                                 ┌──────────┐ ┌─────────┐ ┌────────┐ ┌──────────┐ ┌──────────┐
                                 │SG Policy │ │Invest.  │ │Regional│ │Cybersec  │ │Web Search│  
                                 │Agent     │ │Ecosystem│ │Comp.   │ │Compliance│ │Agent     │
                                 │(RAG)     │ │Agent    │ │Agent   │ │Agent     │ │          │
                                 └────┬─────┘ └───┬─────┘ └───┬────┘ └─┬────────┘ └────┬─────┘
                                      │           │           │        │               │
                                      ▼           ▼           ▼        ▼               ▼
                                 ChromaDB    ChromaDB    ChromaDB  ChromaDB      DuckDuckGo
                                sg_policy_  invest_eco_ reg_cmp_  cybsec_cmp   (live internet)
                                collection  collection  collection collection
                                      │           │          │        │               │
                                      └───────────┴──────────┴────────┴───────────────┘
                                                             │
                                                             ▼  (all agent outputs)
                                               ┌─────────────────────────────┐
                                               │       SYNTHESIZER NODE      │
                                               │   (Executive-Level Answer)  │
                                               └─────────────┬───────────────┘
                                                             │
                                                             ▼
                                                    Final investor answer
                                              ┌──────────────┴──────────────┐
                                              ▼                             ▼
                                      Gradio Chatbot             FastAPI JSON Response
                                      (notebook UI)              (:8000) ← consumed by
                                                                 Next.js Frontend (:3000)
```

### LangGraph Node Responsibilities

| Node | Role | Inputs | Outputs |
|---|---|---|---|
| `gatekeeper_node` | **Entry point** — topic guardrail; runs before any RAG or routing | Raw query | `allowed: bool` |
| `blocked_response_node` | Short-circuit refusal path; **zero RAG/LLM calls consumed** | `allowed=False` | Polite refusal listing 5 supported domains |
| `router_node` | Intent classifier; selects which agents to invoke | Raw query | `selected_agents`, `routing_reason` |
| `execute_agents_node` | Runs each selected agent sequentially; collects grounded answers | Query + agent list | `agent_outputs` (per-agent answers + doc counts) |
| `synthesize_node` | Merges all agent outputs into one executive briefing | Query + all agent outputs | `response` (final answer) |

### LangGraph Wiring

```python
workflow.set_entry_point('gatekeeper')
workflow.add_conditional_edges('gatekeeper',
    lambda s: 'router' if s.get('allowed', True) else 'blocked')
workflow.add_edge('blocked',     END)   # short-circuit — no RAG consumed
workflow.add_edge('router',      'executor')
workflow.add_edge('executor',    'synthesizer')
workflow.add_edge('synthesizer', END)
```

The `gatekeeper_node` decision is the **only** conditional edge in the graph. All other transitions
are deterministic. A `BLOCK` decision exits immediately at `END` without touching ChromaDB, the
router LLM, or any agent.

### Agent–Collection Mapping

| Agent | Source | Knowledge Base |
|---|---|---|
| `sg_policy_agent` | ChromaDB RAG | `sg_policy_collection` — 3 SG policy PDFs |
| `investment_ecosystem_agent` | ChromaDB RAG | `investment_ecosystem_collection` — 3 EDB/workforce PDFs |
| `regional_comparison_agent` | ChromaDB RAG | `regional_comparison_collection` — 9 ASEAN PDFs |
| `cybersecurity_compliance_agent` | ChromaDB RAG | `cybersecurity_compliance_collection` — 6 CSA PDFs |
| `web_search_agent` | Live internet (DuckDuckGo) | Real-time web results — no ChromaDB |
| `general_agent` | LLM only | No retrieval — base model answer |

---

## 3. Dataset

> **Note:** The `data_agents/` folder and `chroma_db_agents/` vector database are **not included** in this repository (gitignored — PDFs are 109 MB; vector DB is 55 MB).
> Download the PDFs from the public sources listed below, place them in `data_agents/`, then run Cell 7 (`build_knowledge_base()`) to rebuild the ChromaDB collections automatically.

```bash
mkdir -p data_agents
```

All 21 source documents are publicly available. The file number in the table corresponds to the numbered filename list below.

| # | Publisher | Download / Source | Knowledge Domain |
|---|---|---|---|
| 1 | IMDA Singapore | [IMDA.gov.sg](https://www.imda.gov.sg) | NAIS 2.0 strategy, AI governance, Smart Nation |
| 2 | CSET (Georgetown) | [cset.georgetown.edu](https://cset.georgetown.edu) | Independent assessment of Singapore's AI capabilities and global standing |
| 3 | IMDA / PDPC Singapore | [PDPC.gov.sg](https://www.pdpc.gov.sg) | Model AI Governance Framework for Generative AI — responsible GenAI deployment guidelines |
| 4 | EDB Singapore | [EDB.gov.sg](https://www.edb.gov.sg) | Tech clusters, industries, R&D ecosystem |
| 5 | EDB Singapore | [EDB.gov.sg](https://www.edb.gov.sg) | Talent acquisition, workforce, hiring market |
| 6 | SDNEA / Research | SDNEA / ILO publications | Generative AI impact on workforce, jobs, and skills across SEA |
| 7 | Industry research | Publicly available research report | AI adoption and state across Southeast Asia |
| 8 | Research institute | Publicly available research report | ASEAN AI readiness rankings and scores |
| 9 | Consulting firm | Publicly available research report | SEA AI growth potential and investment outlook |
| 10 | ASEAN | [asean.org](https://asean.org) | Regional AI governance principles, ethics guidelines across ASEAN |
| 11 | Google / Temasek / Bain | [Think with Google](https://www.thinkwithgoogle.com) | Digital economy size, growth, and AI trends across Southeast Asia |
| 12 | ERIA | [eria.org](https://www.eria.org) | ASEAN startup ecosystems, cross-border investment, and policy enablers |
| 13 | Ecosystm / NAIO | [ecosystm.io](https://ecosystm.io) | Malaysia SME AI adoption via open source, digital transformation |
| 14 | National govt | National AI governance publication | National-level AI governance and ethics guidelines across the region |
| 15 | ASEAN / Policy body | [asean.org](https://asean.org) | Key AI policy discussions, priorities, and collaboration being accelerated across ASEAN |
| 16 | CSA Singapore | [CSA.gov.sg](https://www.csa.gov.sg) | LLM security, OWASP, compliance for AI deployments |
| 17 | CSA Singapore | [CSA.gov.sg](https://www.csa.gov.sg) | Practical guidance for securing AI infrastructure and pipelines |
| 18 | CSA Singapore | [CSA.gov.sg](https://www.csa.gov.sg) | Security guidelines and controls for AI system deployment |
| 19 | CSA Singapore | [CSA.gov.sg](https://www.csa.gov.sg) | Safe LLM implementation practices, risks, and mitigations |
| 20 | CSA Singapore | [CSA.gov.sg](https://www.csa.gov.sg) | Authorization and access control practices for LLM-backed systems |
| 21 | CSA Singapore | [CSA.gov.sg](https://www.csa.gov.sg) | Singapore cybersecurity threat landscape, incidents, and national posture |

**Source PDF filenames** — save each to `data_agents/` with the exact name shown:

1. `Singapore AI Opportunity.pdf`
2. `CSET-Examining-Singapores-AI-Progress.pdf`
3. `Model-AI-Governance-Framework-for-Generative-AI-19-June-2024.pdf`
4. `EDB_Singapore-Tech-Ecosystem.pdf`
5. `EDB_Guide-to-Hiring-Your-Dream-Tech-Team-in-Singapore.pdf`
6. `Gen-AI_Artificial Intelligence and the Future of Work _sdnea2024001.pdf`
7. `State_of_Ai_SEA_Digital.pdf`
8. `The AI Readiness Barometer-ASEAN AI Landscape.pdf`
9. `unlocking-southeast-asias-ai-potential.pdf`
10. `ASEAN-Guide-on-AI-Governance-and-Ethics_beautified_201223_v2.pdf`
11. `e_conomy_sea_2025_report.pdf`
12. `ERIA-One-ASEAN-Start-up-White-Paper-2024.pdf`
13. `Accelerating_SME_AI_Adoption_Through_Open_Source_in_Malaysia_s_Digital_Future_NAIO.pdf`
14. `THE-NATIONAL-GUIDELINES-ON-AI-GOVERNANCE-ETHICS.pdf`
15. `Accelerating-AI-Discussions-in-ASEAN-.pdf`
16. `Cybersecurity_Playbook_for_Large_Language_Model_LLM_Applications.pdf`
17. `Companion Guide on Securing AI Systems.pdf`
18. `Guidelines on Securing AI Systems.pdf`
19. `large-language-model-starter-kit.pdf`
20. `Securing LLM Backed Systems_ Essential Authorization Practices 20240823.pdf`
21. `Singapore Cyber Landscape 2024_2025.pdf`

---

## 4. Prerequisites

### Backend (Python)

| Requirement | Version |
|---|---|
| Python | 3.10 or 3.11 |
| pip | ≥ 23 |
| [Groq API key](https://console.groq.com) | Free tier sufficient |
| [LangSmith API key](https://smith.langchain.com) | Free tier sufficient |
| RAM | ≥ 8 GB (embedding model loads into memory) |
| Disk | ≥ 2 GB (ChromaDB + embedding model cache) |

### Frontend (Next.js)

| Requirement | Version |
|---|---|
| Node.js | ≥ 18 (tested with v24) |
| npm | ≥ 9 (tested with v11) |
| Backend API | Running at `http://localhost:8000` |

---

## 5. Installation

### pip (recommended for FastAPI deployment)

```bash
# Clone or navigate to the project directory
cd singapore-ai-hub-intelligence

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# Install all dependencies
pip install -r requirements.txt
```

### Verify installation

```bash
python -c "import langchain, langgraph, chromadb, fastapi; print('OK')"
```

---

## 6. Environment Configuration

Create a `.env` file in the project root (same folder as `api.py`):

```env
# ── Required ──────────────────────────────────────────────────────────────────
GROQ_API_KEY=gsk_...your_groq_key...

# ── LangSmith observability (add these three lines to enable tracing) ─────────
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls__...your_langsmith_key...
LANGCHAIN_PROJECT=sg-ai-hub-intelligence

# ── Optional: other models / services ─────────────────────────────────────────
HF_TOKEN=hf_...your_huggingface_token...
GEMINI_API_KEY=...
OPENAI_API_KEY=...

# ── Optional: FastAPI admin endpoint protection ────────────────────────────────
ADMIN_API_KEY=choose_a_strong_secret_here
```

> **Security note:** Never commit `.env` to version control. It is already listed in `.gitignore`.

### What LangSmith captures automatically

Once `LANGCHAIN_TRACING_V2=true` is set, **every** LangChain and LangGraph call is traced with
zero code changes:

- Router LLM prompt + agent selection decision
- Per-agent ChromaDB similarity search queries and retrieved chunks
- Synthesizer prompt and final LLM output
- End-to-end latency and token usage per Groq call

View traces at [smith.langchain.com](https://smith.langchain.com) → project `sg-ai-hub-intelligence`.

---

## 7. Quick Start — Jupyter Notebook

```bash
# Activate your environment
conda activate genai_local   # or source .venv/bin/activate

# Launch Jupyter
jupyter lab
```

Open `Singapore AI Hub Intelligence.ipynb` and **run cells top-to-bottom**:

| Cell | Action | Expected output |
|---|---|---|
| 3 | Install deps (if needed) | `Dependencies ready.` |
| 4 | Imports + config | `Environment configured.` |
| 6 | Define PDF→collection map | Prints mapping table |
| 7 | `build_knowledge_base()` | Ingests 21 PDFs on first run, shows chunk counts; skips on subsequent runs |
| 9 | Define agents | `Agent tools and routing functions defined.` |
| 11–15 | Build LangGraph | `Singapore AI Hub Intelligence graph compiled.` |
| 17 | Define investor queries | 8 sample queries ready |
| 18 | Run flagship query | Full investor briefing printed |
| 21 | Launch Gradio | Browser tab opens at `http://127.0.0.1:7860` |

> **First run:** Cell 7 downloads the `all-mpnet-base-v2` embedding model (~420 MB) and
> processes all 21 PDFs. This takes 15–25 minutes. Subsequent runs skip ingestion automatically.

---

## 8. FastAPI Deployment (Backend)

### Development server

```bash
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

The `--reload` flag restarts the server on code changes (do not use in production).

### Production server

```bash
uvicorn api:app --host 0.0.0.0 --port 8000 --workers 2
```

> **Note:** `--workers > 1` requires the ChromaDB path to be on a shared or network filesystem,
> or use a single worker with async handling. For a single-server deployment, `--workers 1` is safe.

### Docker (optional)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t sg-ai-hub .
docker run --env-file .env -p 8000:8000 -v $(pwd)/chroma_db_agents:/app/chroma_db_agents sg-ai-hub
```

### Startup sequence

On startup `api.py` automatically:
1. Loads all environment variables
2. Initialises `ChatGroq`, `HuggingFaceEmbeddings`, and `chromadb.PersistentClient`
3. Calls `build_knowledge_base(force_rebuild=False)` — skips ingestion if collections exist
4. Compiles the LangGraph workflow
5. Returns `Ready.` — API is now accepting requests

---

## 9. Frontend (Next.js UI)

The `frontend/` directory is a production-ready Next.js 16 application that connects to the
FastAPI backend via a server-side proxy route. It replaces the notebook-only Gradio interface
with a persistent, shareable web UI.

### Technology stack

| Component | Version / Choice |
|---|---|
| Framework | Next.js 16.2 (App Router) |
| Language | TypeScript 5 |
| UI | React 19 + Tailwind CSS v4 |
| Icons | lucide-react |
| Markdown rendering | react-markdown + remark-gfm + rehype-highlight |
| Theming | next-themes (dark / light mode toggle) |
| Styling utilities | clsx + tailwind-merge |

### Directory structure

```
frontend/
├── app/
│   ├── api/chat/route.ts      # Next.js proxy → FastAPI SSE stream
│   ├── globals.css            # Tailwind v4 base + dark/light CSS variables
│   ├── layout.tsx             # Root layout — fonts, ThemeProvider, metadata
│   └── page.tsx               # Entry page — renders <ChatInterface />
├── components/
│   ├── chat/
│   │   ├── AgentBadgeRow.tsx  # Agent pill badges shown on each response
│   │   ├── ChatInterface.tsx  # Main shell — sidebar + chat column
│   │   ├── InputBar.tsx       # Fixed-bottom textarea + send button
│   │   ├── MessageBubble.tsx  # Markdown-rendered message bubble
│   │   ├── MessageList.tsx    # Scrollable message history
│   │   └── TypingIndicator.tsx
│   ├── debug/
│   │   └── DebugPanel.tsx     # Accordion — routing reason + per-agent outputs
│   ├── sidebar/
│   │   ├── AgentRoster.tsx    # Agent list with descriptions
│   │   ├── Sidebar.tsx        # Collapsible desktop / mobile drawer
│   │   └── SuggestedQueries.tsx  # 18 categorised suggested questions
│   ├── providers.tsx          # next-themes ThemeProvider wrapper
│   └── ThemeToggle.tsx        # Dark / light mode toggle button
├── lib/
│   ├── api.ts                 # Typed fetch wrappers for all FastAPI endpoints
│   ├── constants.ts           # SUGGESTED_QUESTIONS, AGENT_COLORS, AGENT_LABELS
│   ├── hooks/
│   │   └── useChat.ts         # SSE stream reader, abort control, message state
│   ├── types.ts               # Shared TypeScript types (QueryRequest, ChatMessage, StreamEvent)
│   └── utils.ts               # cn() helper (clsx + tailwind-merge)
├── .env.local                 # API_URL=http://localhost:8000
├── next.config.ts
├── package.json
└── tsconfig.json
```

### Environment setup

`frontend/.env.local` is included in the repo and pre-configured for local development:

```env
# URL of the running FastAPI backend — change if your backend runs elsewhere
API_URL=http://localhost:8000
```

> **Note:** `API_URL` is a server-side Next.js variable. It is read only by
> `app/api/chat/route.ts` and is never exposed to the browser.

### Install dependencies

```bash
cd frontend
npm install
```

### Development server

```bash
# From the frontend/ directory
npm run dev
```

The UI is available at `http://localhost:3000`.  
The FastAPI backend must be running at `http://localhost:8000` before sending queries.

### Production build

```bash
# From the frontend/ directory
npm run build      # TypeScript type-check + compile
npm start          # Serve the compiled output
```

### How the SSE proxy works

`app/api/chat/route.ts` is a lightweight server-side proxy:

1. Browser sends `POST /api/chat` → Next.js route handler
2. Route handler forwards `POST http://localhost:8000/query/stream` → FastAPI SSE endpoint
3. FastAPI streams `data: {...}` events; the proxy pipes them back to the browser verbatim
4. `lib/hooks/useChat.ts` parses each event and updates React state in real time

This design keeps the backend URL server-side only — no CORS configuration is needed in the browser.

---

## 10. Developer Collaboration

Recommended workflow for teams where different developers own different layers of the stack.

### Repository layout

```
singapore-ai-hub-intelligence-next/
├── api.py                               # FastAPI backend — single entry point
├── requirements.txt                     # Python dependencies
├── .env                                 # Backend secrets (gitignored)
├── data_agents/                         # Source PDFs (gitignored — 109 MB)
├── chroma_db_agents/                    # ChromaDB vector store (gitignored — 55 MB)
├── Singapore AI Hub Intelligence.ipynb  # Notebook — research + Gradio UI
└── frontend/                            # Next.js production UI
    ├── .env.local                       # Frontend config — API_URL (gitignored)
    ├── package.json
    └── ...
```

### Ownership model

| Layer | Files | Responsible role |
|---|---|---|
| LangGraph pipeline / Agents | `api.py` (nodes, graph), `*.ipynb` | ML / AI Engineer |
| Knowledge base | `data_agents/`, `chroma_db_agents/` | ML Engineer |
| REST API layer | `api.py` (routes, schemas, lifespan) | Backend Engineer |
| Next.js UI | `frontend/` | Frontend Engineer |
| DevOps / Infra | Docker, env files, deployment config | DevOps Engineer |

### Setting up a fresh development environment

#### 1. Clone the repository

```bash
git clone <repo-url>
cd singapore-ai-hub-intelligence-next
```

#### 2. Python backend

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Create `.env` in the project root (see [Section 6](#6-environment-configuration) for all variables):

```bash
# Minimum required
echo "GROQ_API_KEY=gsk_..." > .env
```

#### 3. Next.js frontend

```bash
cd frontend
npm install
```

`frontend/.env.local` is already committed with local defaults — no changes needed for local development.

#### 4. Run the full stack

Open **two terminal windows** from the project root:

**Terminal 1 — Backend:**

```bash
source .venv/bin/activate
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

Wait for `Application startup complete` before starting the frontend.

**Terminal 2 — Frontend:**

```bash
cd frontend
npm run dev
```

| Service | URL |
|---|---|
| Next.js frontend | http://localhost:3000 |
| FastAPI backend | http://localhost:8000 |
| Swagger / API docs | http://localhost:8000/docs |

### Git branching strategy

```
main                   ← production-ready, protected branch
├── feat/backend-*     ← LangGraph, agent, or API changes
├── feat/frontend-*    ← Next.js UI changes
└── fix/*              ← bug fixes for either layer
```

Examples:
- `feat/backend-add-gemini-model` — adding a new LLM option to `api.py`
- `feat/frontend-export-chat` — new UI export feature
- `fix/backend-gatekeeper-prompt` — refining the gatekeeper LLM prompt
- `fix/frontend-sse-disconnect` — fixing SSE reconnection in the browser

### Pull request checklist

**Backend (`api.py` / notebook):**

- [ ] `python -c "import ast; ast.parse(open('api.py').read()); print('Syntax OK')"` passes
- [ ] All five LangGraph nodes present: `gatekeeper`, `blocked`, `router`, `executor`, `synthesizer`
- [ ] Graph entry point is `"gatekeeper"` (not `"router"`)
- [ ] `InvestorState` TypedDict includes the `allowed: bool` field
- [ ] New agents added to `VALID_AGENTS`, `AGENT_DESCRIPTIONS`, `AGENT_TO_COLLECTION`, `AGENT_PERSONA`
- [ ] `keyword_fallback_route()` updated for any new agent keyword triggers
- [ ] `.env` updated with any new required variables (and documented in Section 6)

**Frontend (`frontend/`):**

- [ ] `cd frontend && npm run build` completes without TypeScript errors
- [ ] No secrets committed — `.env.local` changes must not be in the PR
- [ ] New agents added to `lib/constants.ts` (`AGENT_LABELS`, `AGENT_COLORS`, `AGENT_ICONS`, `STATIC_AGENTS`)

### Syncing knowledge base across machines

The `chroma_db_agents/` vector store is gitignored. When PDFs are added or `PDF_COLLECTION_MAP` changes:

1. Place new PDFs in `data_agents/` on the target machine.
2. Rebuild the vector store via one of two methods:
   ```bash
   # Option A — via the notebook
   # Run Cell 7: build_knowledge_base(force_rebuild=True)

   # Option B — via the API (backend must be running)
   curl -X POST http://localhost:8000/rebuild-kb \
     -H "X-Admin-Key: $ADMIN_API_KEY"
   ```
3. For larger teams, store the pre-built `chroma_db_agents/` in shared object storage
   (e.g. S3 / GCS) and download it on first setup instead of rebuilding locally.

### Environment variables — full reference

| Variable | File | Required | Description |
|---|---|---|---|
| `GROQ_API_KEY` | `.env` | **Yes** | LLM API key from [console.groq.com](https://console.groq.com) |
| `LANGCHAIN_TRACING_V2` | `.env` | No | `true` to enable LangSmith tracing |
| `LANGCHAIN_API_KEY` | `.env` | No | LangSmith API key |
| `LANGCHAIN_PROJECT` | `.env` | No | LangSmith project name (default: `sg-ai-hub-intelligence`) |
| `ADMIN_API_KEY` | `.env` | No | Guards the `POST /rebuild-kb` admin endpoint |
| `API_URL` | `frontend/.env.local` | **Yes** | FastAPI base URL (default: `http://localhost:8000`) |

---

## 11. API Reference

Interactive docs available at `http://localhost:8000/docs` (Swagger UI) after server start.

### `GET /`
Health check.

```bash
curl http://localhost:8000/
```
```json
{"status": "ok", "service": "Singapore AI Hub Intelligence API", "version": "1.0.0"}
```

---

### `POST /query`
Submit an investor question. Returns a structured JSON response.

**Request body:**
```json
{
  "question": "Why should I set up my AI company in Singapore over Malaysia?",
  "include_debug": false
}
```

**Response:**
```json
{
  "question": "Why should I set up my AI company in Singapore over Malaysia?",
  "answer": "Based on the source documents...",
  "agents_used": ["investment_ecosystem_agent", "regional_comparison_agent"],
  "routing_reason": "Comparison + investment query triggers two agents",
  "agent_outputs": {
    "investment_ecosystem_agent": "...",
    "regional_comparison_agent": "..."
  },
  "debug_log": null,
  "latency_ms": 4821.3
}
```

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is NAIS 2.0?", "include_debug": true}'
```

---

### `POST /query/stream`
Same as `/query` but streams the answer as Server-Sent Events (SSE).

```bash
curl -N -X POST http://localhost:8000/query/stream \
  -H "Content-Type: application/json" \
  -d '{"question": "Compare Singapore and Vietnam for AI investment."}'
```

SSE event types: `agents` → `token` (repeated) → `done`

---

### `GET /agents`
List all available agents and their descriptions.

```bash
curl http://localhost:8000/agents
```

---

### `GET /collections`
List ChromaDB collections and document counts.

```bash
curl http://localhost:8000/collections
```

---

### `POST /rebuild-kb`
Force re-ingestion of all PDFs (drops and rebuilds all collections).  
Protected by `X-Admin-Key` header if `ADMIN_API_KEY` is set in `.env`.

```bash
curl -X POST http://localhost:8000/rebuild-kb \
  -H "X-Admin-Key: your_admin_key"
```

---

## 12. LangSmith Observability

LangSmith provides full, automatic tracing of every agent run — **no code changes required**.
All you need are three environment variables. This section walks you from account creation to
reading live traces in the portal.

---

### Step 1 — Create a LangSmith Account

1. Open [smith.langchain.com](https://smith.langchain.com) in your browser.
2. Click **Sign Up** (top-right). Use your GitHub account or email — both are free.
3. On first login you are placed in a personal workspace named after your username (e.g. `my-org`).
   This is fine for personal use; teams can create a shared organisation workspace later.

---

### Step 2 — Create the Project

LangSmith groups traces by **Project**. You need to create the project before your first run so
traces land in the right place.

1. In the left sidebar click **Projects**.
2. Click **+ New Project** (top-right of the projects list).
3. Set the project name to exactly: `sg-ai-hub-intelligence`
   *(this matches the `LANGCHAIN_PROJECT` value used in this codebase — do not rename it).*
4. Leave all other settings as defaults and click **Create**.

You now have an empty project ready to receive traces.

---

### Step 3 — Generate an API Key

1. Click your **profile avatar** (bottom-left of the sidebar) → **Settings**.
2. Select the **API Keys** tab.
3. Click **Create API Key**.
4. Give it a description (e.g. `sg-ai-hub local dev`) and click **Create**.
5. **Copy the key immediately** — it is shown only once. It starts with `lsv2_pt_...`.

> **Security:** treat this key like a password. Never paste it into a notebook cell or commit it
> to git. Store it only in `.env`.

---

### Step 4 — Configure `.env`

Open (or create) `.env` in the project root and add the three LangSmith lines:

```env
# ── Required ──────────────────────────────────────────────────────────────────
GROQ_API_KEY=gsk_...your_groq_key...

# ── LangSmith tracing (enables portal visibility) ─────────────────────────────
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_pt_...your_langsmith_key...
LANGCHAIN_PROJECT=sg-ai-hub-intelligence
```

`LANGCHAIN_TRACING_V2=true` is the master switch. Remove or set to `false` to disable tracing
without changing any other code.

---

### Step 5 — Verify the Environment Loads

Before running any queries, confirm the variables are visible to Python:

```bash
python - <<'EOF'
import os
from dotenv import load_dotenv
load_dotenv()
assert os.getenv("LANGCHAIN_TRACING_V2") == "true", "Tracing switch not set"
assert os.getenv("LANGCHAIN_API_KEY", "").startswith("lsv2"), "API key missing or malformed"
assert os.getenv("LANGCHAIN_PROJECT") == "sg-ai-hub-intelligence", "Project name mismatch"
print("LangSmith environment OK")
EOF
```

Expected output: `LangSmith environment OK`

---

### Step 6 — Run a Query and Confirm Tracing

#### In the Jupyter notebook

Run all cells (1–19). Cell 19 executes the flagship query. Within a few seconds of the cell
completing, a trace will appear in the LangSmith portal.

#### Via FastAPI

```bash
uvicorn api:app --reload --port 8000

curl -s -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Why should I choose Singapore over Malaysia for my AI hub?"}'
```

---

### Step 7 — Navigate the LangSmith Portal

1. Go to [smith.langchain.com](https://smith.langchain.com) → **Projects** → **`sg-ai-hub-intelligence`**.
2. The **Runs** table shows one row per query. Columns include:
   - **Name** — `LangGraph` (the graph) and child nodes
   - **Status** — green tick = success; red circle = error
   - **Latency** — end-to-end wall-clock time
   - **Tokens** — total input + output tokens consumed
   - **Start Time** — when the query was received
3. Click any run row to open the **Trace Detail** panel.

---

### Step 8 — Read the Trace Tree

Each query expands into a tree of child spans. Here is what to expect for this project:

```
▼ LangGraph  [total latency e.g. 8.4 s]
  │
  ├── gatekeeper_node
  │     └── ChatGroq  [~0.5 s]
  │           Input:  system prompt listing 5 supported domains + user query
  │           Output: "ALLOW"  (or "BLOCK" for off-topic queries)
  │           Tokens: ~280 in / 1 out
  │
  ├── router_node                            (skipped if gatekeeper returned BLOCK)
  │     └── ChatGroq  [~0.8 s]
  │           Input:  routing system prompt + user query
  │           Output: {"agents": ["regional_comparison_agent",
  │                                "investment_ecosystem_agent"],
  │                    "reason": "Query involves ASEAN comparison and SG ecosystem"}
  │           Tokens: ~312 in / 28 out
  │
  ├── execute_agents_node
  │     ├── Chroma.similarity_search  (regional_comparison_agent, k=5)
  │     │     Query:     user's question
  │     │     Retrieved: 5 document chunks from regional_comparison_collection
  │     ├── ChatGroq  [~2.1 s]  — regional_comparison_agent answer
  │     │     Tokens: ~2 140 in / 380 out
  │     ├── Chroma.similarity_search  (investment_ecosystem_agent, k=5)
  │     └── ChatGroq  [~1.8 s]  — investment_ecosystem_agent answer
  │           Tokens: ~1 890 in / 290 out
  │
  │   ── (for queries containing "latest", "2025", "news", etc.) ──
  │     └── DuckDuckGoSearchRun
  │           Input:  raw user query string sent to DuckDuckGo
  │           Output: concatenated search result snippets
  │           └── ChatGroq  [~3.4 s]  — web_search_agent synthesis
  │                 Tokens: ~3 100 in / 420 out
  │
  └── synthesize_node
        └── ChatGroq  [~3.2 s]
              Input:  all agent outputs + user query wrapped in synthesis prompt
              Output: final executive briefing (markdown)
              Tokens: ~1 842 in / 412 out
```

**What to click first:** open `synthesize_node → ChatGroq → Input` — this shows you the complete
prompt that was assembled from all agent answers. It is the fastest way to verify the system is
working end-to-end.

---

### Step 9 — Use the Portal Features

#### Filter and search runs

- Use the **search bar** at the top of the Runs table to filter by query text.
- Use the **Status** filter to show only failed runs.
- Use **Date range** to compare behaviour before/after a code change.

#### Inspect token usage

- Click **Metrics** tab inside any run to see per-node token breakdown.
- The **Tokens** column on the Runs list shows cumulative usage — useful for estimating Groq
  daily quota consumption (free tier: 100K tokens/day for `llama-3.3-70b-versatile`).

#### Compare runs side-by-side

1. Tick two run rows using the checkboxes on the left.
2. Click **Compare** (appears in the toolbar).
3. The diff view shows prompt and output differences between runs — useful for A/B testing
   prompts or model changes.

#### Annotate runs for evaluation

1. Open a run, click **Add Annotation** (flag icon).
2. Score on a 1–5 scale and add a note (e.g. "Synthesis missed the cybersecurity angle").
3. Annotations accumulate into a labelled dataset you can use later for automated eval.

---

### Step 10 — Enable Feedback Collection (Optional)

LangSmith can record thumbs-up / thumbs-down feedback from the Gradio UI. Add this snippet after
Cell 15 (`synthesize_node`) in the notebook to attach a `run_id` to each response:

```python
# Cell 15a — attach run_id for LangSmith feedback (optional)
from langchain_core.tracers.context import collect_runs

def synthesize_node_with_run_id(state: InvestorState) -> dict:
    with collect_runs() as cb:
        result = synthesize_node(state)
        result["run_id"] = cb.traced_runs[0].id if cb.traced_runs else None
    return result
```

Then in the Gradio callback, call:

```python
from langsmith import Client as LangSmithClient
_ls_client = LangSmithClient()

def record_feedback(run_id, score: int):
    """score: 1 = thumbs up, 0 = thumbs down"""
    if run_id:
        _ls_client.create_feedback(run_id, key="user_rating", score=score)
```

> This is optional. The core tracing in Steps 1–9 works without it.

---

### Typical Debugging Workflow

| Symptom | Node to inspect | What to look for |
|---|---|---|
| Off-topic query got through | `gatekeeper_node → ChatGroq → Output` | Did the LLM output contain `BLOCK`? Check the raw string |
| Wrong agents selected | `router_node → ChatGroq → Output` | Is the JSON valid? Is `web_search_agent` present for "latest" queries? |
| RAG answer not grounded in PDFs | `execute_agents_node → Chroma → Output` | Are retrieved chunks topically relevant? Try rephrasing the query |
| Web search returned nothing useful | `execute_agents_node → DuckDuckGoSearchRun → Output` | Check the raw snippet text — DuckDuckGo may be rate-limited; retry |
| Synthesizer skipped an agent | `synthesize_node → ChatGroq → Input` | Check `specialist_reports` block — is that agent's output present? |
| High end-to-end latency | Top-level `LangGraph` waterfall | Expand each node; the ChatGroq call with the most tokens is usually the bottleneck |
| JSON parse failure (keyword fallback used) | `router_node → ChatGroq → Output` | Look for markdown fences (` ```json `) or extra text wrapping the JSON |
| Gatekeeper blocked a valid query | `gatekeeper_node → ChatGroq → Output` | Check exact output; adjust the gatekeeper system prompt if needed |

---

### Quick Reference — LangSmith Variables

| Variable | Required | Example Value | Purpose |
|---|---|---|---|
| `LANGCHAIN_TRACING_V2` | Yes | `true` | Master on/off switch for tracing |
| `LANGCHAIN_API_KEY` | Yes | `lsv2_pt_abc123...` | Authenticates with LangSmith servers |
| `LANGCHAIN_PROJECT` | Yes | `sg-ai-hub-intelligence` | Routes traces to this project in the portal |

All three must be present and correct in `.env` for traces to appear. If runs do not show up
within 30 seconds of a query, re-run the verification command in Step 5.

---

## 13. User Guide — Investor Chatbot

### Starting the Gradio interface (notebook)

Run all cells in `Singapore AI Hub Intelligence.ipynb`, then navigate to the URL
printed in Cell 21 (typically `http://127.0.0.1:7860`).

### Suggested questions to try

| Category | Sample Question |
|---|---|
| Policy | *What is latest Singapore's NAIS (National Artificial Intelligence Strategy) and its key pillars?* |
| Investment | *What government incentives and EDB programs does Singapore offer to AI companies?* |
| Comparison | *How does Singapore compare to Malaysia and Thailand on AI readiness?* |
| Cybersecurity | *What LLM compliance and security frameworks apply to AI deployments in Singapore?* |
| Comprehensive | *As a tech AI company, why should I choose Singapore over Indonesia or Vietnam as my regional hub?* |
| Talent | *What is the tech talent landscape in Singapore vs other ASEAN countries?* |
| Market opportunity | *What are the major AI growth opportunities across Southeast Asia?* |
| Executive summary | *Give me a full executive briefing on Singapore's AI competitive advantages vs all ASEAN nations.* |
| AI Security | *What does the Companion Guide on Securing AI Systems recommend for protecting AI infrastructure?* |
| AI Security | *What are the key guidelines for securing AI systems against adversarial threats?* |
| LLM Implementation | *What does the LLM Starter Kit recommend for safely implementing large language models?* |
| LLM Authorization | *What essential authorization practices should be applied to LLM-backed systems?* |
| ASEAN Governance | *How does the ASEAN Guide on AI Governance and Ethics shape responsible AI deployment across the region?* |
| Singapore AI Progress | *How does the CSET assessment evaluate Singapore's AI capabilities and global ranking?* |
| Digital Economy | *What does the e-Conomy SEA 2025 report reveal about digital economy growth and AI opportunities across Southeast Asia?* |
| Startup Ecosystem | *What does the ERIA One ASEAN Startup White Paper say about startup ecosystems and cross-border investment opportunities in ASEAN?* |
| Malaysia / Open Source | *How is Malaysia accelerating SME AI adoption through open source, and what does this mean for regional competitiveness?* |
| Future of Work | *What are the key impacts of Generative AI on the future of work in Southeast Asia, and how should companies prepare their workforce?* |
| Cyber Landscape | *What does the Singapore Cyber Landscape 2024/2025 report reveal about key threats and Singapore's national cybersecurity posture?* |
| National AI Ethics | *What national AI governance and ethics guidelines are shaping AI deployment standards across the ASEAN region?* |
| GenAI Governance | *What does Singapore's Model AI Governance Framework for Generative AI recommend for responsible GenAI deployment?* |
| ASEAN AI Policy | *What are the key AI policy discussions and priorities being accelerated across ASEAN member states?* |
| Live News | *What are the latest AI investment announcements and funding rounds in Singapore in 2025/2026?* |
| Live News | *What recent AI policy updates or new regulations has Singapore announced this year?* |

### Understanding the response

Each answer is grounded **only** in the twenty-one source PDFs. The chatbot will explicitly state
*"This specific information is not available in my knowledge base"* rather than hallucinate.

The expandable **Orchestration Details** section in each chat response shows:
- Which agents were activated and why
- How many document chunks were retrieved per agent
- The full debug log of the LangGraph run

---

## 14. Extending the System

### Add a new knowledge domain

1. Place new PDF(s) in `data_agents/`
2. Add entries to `PDF_COLLECTION_MAP` in both `Singapore AI Hub Intelligence.ipynb` (Cell 6) and `api.py`
3. Add a new agent entry to `AGENT_TO_COLLECTION` and `AGENT_PERSONA`
4. Update `VALID_AGENTS` and `AGENT_DESCRIPTIONS`
5. Add keywords to `keyword_fallback_route()`
6. Call `build_knowledge_base(force_rebuild=True)` or `POST /rebuild-kb`

### Switch the LLM

Change `LLM_MODEL` in Cell 4 / `api.py`. Groq-supported models include:

| Model | Speed | Context | Notes |
|---|---|---|---|
| `llama-3.3-70b-versatile` | Fast | 128k | Default — best balance |
| `llama-3.1-8b-instant` | Very fast | 128k | Lower quality, good for testing |
| `mixtral-8x7b-32768` | Fast | 32k | Alternative |

### Enable conditional deep-agent loops

For multi-hop ASEAN comparison queries, add a re-retrieval step in `synthesize_node`:
if the synthesized answer contains `"not available in my knowledge base"`, re-invoke
`execute_agents_node` with a rephrased query before producing the final answer.

### Swap the vector database

Replace `langchain-chroma` with `langchain-pinecone` or `langchain-qdrant`.
The agent executor (`run_grounded_agent`) only calls `.similarity_search(query, k=5)` — 
swap the `Chroma(...)` constructor call and the rest of the code is unchanged.

---

## 15. Troubleshooting

| Symptom | Fix |
|---|---|
| `GROQ_API_KEY missing` | Check `.env` file exists and key is spelled correctly |
| `chromadb.errors.InvalidCollectionException` | Run `build_knowledge_base(force_rebuild=True)` to rebuild |
| PDF not found warning during ingestion | Verify filename in `data_agents/` matches exactly (spaces, case) |
| Embedding model download fails | Set `HF_TOKEN` in `.env`; or run `huggingface-cli login` |
| `503 System not ready` from API | Server is still loading the embedding model on startup; wait 30–60 s |
| Gradio `OSError: Port already in use` | Kill the existing Gradio process or change port: `demo.launch(server_port=7861)` |
| LangSmith traces not appearing | Confirm `LANGCHAIN_TRACING_V2=true` (lowercase, no quotes) in `.env`; if using `= 'True'` format, change to `LANGCHAIN_TRACING_V2=true` |
| Slow first query (30–60 s) | Normal — embedding model is warming up; subsequent queries are 3–8 s |

Acknowledgement
---
Portions of this repo’s framework documentation and correction were supported by Anthropic’s Claude, used for drafting and refining explanatory text.

