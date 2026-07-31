# AI Chat Workbench

[简体中文](./README_zh.md)

An intelligent chat workbench (Kimi Workspace–like) with a decoupled frontend/backend architecture. It goes beyond plain streaming chat: an **Agent mode** drives multi-step ReAct reasoning with **tool calling**, **RAG** over a personal knowledge base, **structured step traces**, a **Markdown-defined skills** system with a management UI, and **web search** — all behind a unified multi-vendor LLM layer.

> Built and verified on Windows / Linux / macOS (CI matrix), with `docker compose up` one-click deployment.

---

## What can it do?

| Capability | Description |
| ---------- | ----------- |
| **Multi-vendor chat** | OpenAI / Anthropic / Gemini (native) + DeepSeek / GLM / Kimi (OpenAI-compatible). Strategy-pattern adapters, transparent switching, per-model API Key & Base URL. |
| **Streaming dialogue** | SSE token-by-token streaming, real-time render, abort support, multi-round conversations persisted to SQLite. |
| **Deep Thinking** | Toggle in the input area; the model streams its reasoning before the answer, shown in collapsible blocks, persisted across refresh. |
| **Agent mode** | LangGraph-based ReAct loop with real **tool calling**. Skills are exposed as tools; each step's thought / action / observation is streamed. |
| **RAG / Knowledge Base** | Local `bge-small-zh` embeddings + Chroma vector store. Upload `.md` notes; the KB is auto-injected in normal chat and **self-retrieved** by the Agent via a `retrieve_notes` tool. |
| **AgentTrace panel** | Structured step cards (thought / action / observation / retrieved chunks) with step-bounded SSE — not a flat text blob. |
| **Skills system** | `.md` files define skills (YAML frontmatter + system prompt), hot-reloaded. Built-in `echo`, `current_time`, `web_search`, `retrieve_notes` + editable MD skills via a **Skills Manager UI**. |
| **Web search** | Tavily-backed `web_search` skill (replaced the rate-limited DuckDuckGo path). |
| **File upload** | `.txt` / `.md` / code files / `.pdf` / `.docx` parsed to text and sent as context. |
| **Model management** | 11 pre-seeded models; runtime CRUD; per-model API Key never exposed to the frontend. |
| **Virtual scrolling** | `@tanstack/react-virtual` with dynamic measurement; smooth at 1000+ messages. |

---

## Architecture Overview

```text
┌──────────────────────────────────────────────────────────────────┐
│  Frontend (React 19 + Vite + Tailwind CSS v4)                    │
│  ┌───────────┐ ┌─────────────────────────────────────────────┐  │
│  │  Sidebar  │ │  Workspace                                  │  │
│  │ Chat List │ │  ┌─────────────────────────────────────┐    │  │
│  │ Search    │ │  │ ChatHeader (Model / Thinking / Agent │    │  │
│  │ New Chat  │ │  │  toggle / KB select / Skills / Models)│    │  │
│  │           │ │  ├─────────────────────────────────────┤    │  │
│  │           │ │  │ MessageList (virtualized)           │    │  │
│  │           │ │  │  MessageItem                         │    │  │
│  │           │ │  │   ├ MarkdownContent (render + hl)    │    │  │
│  │           │ │  │   ├ ThinkingBlock (collapsible)      │    │  │
│  │           │ │  │   └ AgentTrace (step cards)          │    │  │
│  │           │ │  ├─────────────────────────────────────┤    │  │
│  │           │ │  │ InputArea (text + file upload + send │    │  │
│  │           │ │  │  + Thinking/Agent toggles)           │    │  │
│  │           │ │  └─────────────────────────────────────┘    │  │
│  └───────────┘ └─────────────────────────────────────────────┘  │
│            │  Zustand store + localStorage persist               │
└────────────┼─────────────────────────────────────────────────────┘
             │ HTTP (Vite proxy /api → :8000)
             ▼
┌──────────────────────────────────────────────────────────────────┐
│  Backend (FastAPI + SQLAlchemy async + SQLite)                   │
│  ┌──────────────┐ ┌───────────────────┐ ┌────────────────────┐  │
│  │ Routers      │ │ Services          │ │ Adapters           │  │
│  │ /api/chat    │ │ ConversationSvc   │ │ OpenAI             │  │
│  │ /api/agent-  │ │ AgentService      │ │ Anthropic          │  │
│  │   chat       │ │  (LangGraph ReAct)│ │ Gemini             │  │
│  │ /api/conv.   │ │ KnowledgeService  │ │ OpenAI-Compatible  │  │
│  │ /api/models  │ │ EmbeddingService  │ │ (DeepSeek/GLM/Kimi)│  │
│  │ /api/upload  │ │ FileParser        │ └────────────────────┘  │
│  │ /api/skills  │ │ LangChainAdapter  │            ▲            │
│  │ /api/knowl…  │ └───────────────────┘            │ httpx+SSE  │
│  └──────────────┘                                  │            │
│  ┌──────────────┐ ┌────────────────────────────────┴──────────┐ │
│  │ Models (ORM) │ │ Skills (registry)                         │ │
│  │  + Pydantic  │ │  echo · current_time · web_search (Tavily)│ │
│  └──────────────┘ │  retrieve_notes (RAG) · MarkdownSkill(.md)│ │
│  ┌──────────────┐ └──────────────────────────────────────────┘ │
│  │ SQLite       │  ┌─────────────────────────────────────────┐ │
│  │  + aiosqlite │  │ ChromaDB (vectors) · bge-small-zh embed │ │
│  └──────────────┘  └─────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
             │
             ▼
   ┌────────────────────────┐
   │  LLM Providers         │
   │  OpenAI / Anthropic    │
   │  Gemini / DeepSeek     │
   │  GLM / Kimi  · Tavily  │
   └────────────────────────┘
```

---

## Tech Stack

### Frontend

| Category | Tech | Purpose |
| -------- | ---- | ------- |
| Framework | React 19 | UI construction |
| Language | TypeScript | Type safety |
| Build | Vite | Dev / build tooling |
| Styling | Tailwind CSS v4 | Utility-first CSS |
| Components | shadcn/ui | UI primitives (Button, Input, Modal, Select) |
| State Mgmt | Zustand 5 + persist | Global state + localStorage persistence |
| Virtual Scroll | @tanstack/react-virtual | Long-list performance |
| Markdown | react-markdown + remark-gfm | Message rendering |
| Code Highlight | react-syntax-highlighter | Code block syntax highlighting |
| File Upload | react-dropzone | Drag-and-drop / click upload |
| Icons | lucide-react | UI icons |
| Date | date-fns | Time formatting |

### Backend

| Category | Tech | Purpose |
| -------- | ---- | ------- |
| Framework | FastAPI (≥0.115) | Web server |
| Runtime | Uvicorn | ASGI server |
| ORM | SQLAlchemy 2.0 (async) | Database operations |
| Database | SQLite + aiosqlite | Persistent storage |
| Validation | Pydantic v2 + pydantic-settings | Request validation + config management |
| HTTP | httpx | LLM API calls |
| Agent orchestration | LangGraph + langchain-core | ReAct loop, tool calling |
| LLM bridge | langchain-text-splitters | Markdown / recursive chunking |
| Vector DB | chromadb | On-disk vector store |
| Embeddings | sentence-transformers + `BAAI/bge-small-zh-v1.5` | Local embedding model |
| Web search | tavily-python | `web_search` skill backend |
| PDF | pdfplumber | PDF file parsing |
| DOCX | python-docx | Word file parsing |

---

## Features

### Multi-Vendor Model Adapters

- **Native adapters**: OpenAI, Anthropic, Gemini — independent implementations.
- **Compatible adapters**: DeepSeek, GLM, Kimi via the OpenAI-compatible protocol.
- **Unified interface**: Strategy Pattern — switching is transparent to higher layers.
- **Per-model credentials**: Each model carries its own API Key & Base URL; factory resolves model-level key → `.env` vendor key (backward compatible). The key is never sent to the frontend (only a `has_api_key` boolean).

### Streaming Chat

- SSE (Server-Sent Events) token-by-token streaming.
- Real-time render with abort support (AbortController).
- Message lifecycle: pending → streaming → done / error.

### Deep Thinking

- One-click toggle in the input area.
- Streams the reasoning process before the final answer.
- Thinking content in collapsible blocks, visually distinct from the reply.
- Persisted to SQLite — visible after refresh or session reopen.
- Vendors: **Anthropic** (native `thinking_delta`), **OpenAI-compatible** (DeepSeek / GLM / Kimi via `reasoning_content`), Gemini not yet supported.

### Agent Mode

- LangGraph ReAct loop with **real tool calling** — Skills are wrapped as LangChain `StructuredTool`s and invoked inside the loop.
- Each step streams its **thought / action / observation**, plus a one-line **narration** rendered as body text (interleaved with collapsible reasoning cards).
- `max_steps` safety net; graceful abort (partial trace persisted).
- **No-tool fallback**: if no skills/KB is available, the Agent skips the ReAct loop and answers directly (no dead-loop).
- Metadata (`step_count`, `aborted`, `tool_calls`, `steps`, `agent`) persisted per assistant message.

### RAG / Knowledge Base

- **Local embeddings**: `bge-small-zh-v1.5` via `sentence-transformers` (no network cost); falls back to a no-op `FakeEmbedder` when torch/the model is absent (uploads return 503, retrieval returns `[]`).
- **Vector store**: ChromaDB (disk-persisted, one collection per KB).
- **Normal chat**: KB hits are silently prepended to the user message.
- **Agent mode**: the `retrieve_notes` tool lets the Agent self-retrieve notes; results surface as structured `retrieved` chunks in the trace.
- **Chunking**: `MarkdownHeaderTextSplitter` → `RecursiveCharacterTextSplitter` (configurable size/overlap/top-k/min-score).
- Upload formats: `.md` / `.markdown` / `.txt` (PDF/DOCX RAG is planned).

### AgentTrace Panel

- Structured **step cards** instead of a flat reasoning blob: each card shows Thought / Action / Observation / retrieved chunks with a finish badge.
- Step-bounded SSE protocol (`step_start` / `step_end` / `retrieved`), with flat events kept for backward compatibility.
- Narration (the `说明:` line) renders as always-visible body text beneath each card; only the final answer is promoted to `message.content`.

### Skills System

- **Markdown skills**: drop a `.md` file in `backend/skills_md/` (YAML frontmatter for `name`/`description`, body as the system prompt). Hot-reloaded via `POST /api/skills/reload`.
- **Python skills**: built-in `echo`, `current_time`, `web_search` (Tavily), `retrieve_notes`.
- **Skills Manager UI**: create / edit / delete `.md` skills from the ChatHeader; Python skills are read-only.
- **Web search**: Tavily-backed `web_search` skill (replaces the rate-limited DuckDuckGo path).

### Conversation Management

- Multiple parallel conversations in the sidebar.
- Auto-generated titles from the first user message.
- Search filtering (backend ILIKE fuzzy match), rename / delete (with confirmation), right-click context menu.

### File Upload

- Formats: `.txt` / `.md` / `.json` / `.yaml` / `.xml` / `.html` / `.css` / code files (`.js` / `.ts` / `.py` / `.java` / `.c` / `.cpp` / `.go` / `.rs` …) + `.pdf` + `.docx`; unknown extensions probed as UTF-8 text.
- Parsed to text and sent as conversation context; drag-and-drop upload.

### Model Management

- 11 pre-seeded default models (GPT-5.5, GPT-5.4, Claude Opus 4.8, Claude Sonnet 5, Gemini 3.1 Pro, Gemini 3.5 Flash, DeepSeek-V4-Flash, DeepSeek-V4-Pro, Kimi K2.6, GLM-5.2, GLM-4.7).
- Runtime CRUD; each model independently configurable (adapter type, Base URL, API Key).

### Virtual Scrolling

- `@tanstack/react-virtual` with dynamic `measureElement` — smooth even with large message volumes.

---

## Quick Start

### Prerequisites

- Python ≥ 3.11 (recommended: [uv](https://docs.astral.sh/uv/))
- Node.js ≥ 20

### 1. Clone the repository

```bash
git clone <repo-url>
cd My_Agent
```

### 2. Start the backend

```bash
cd backend
cp .env.example .env
# Edit .env:
#   - Fill vendor API Keys (OPENAI / ANTHROPIC / DEEPSEEK / GLM / KIMI / GEMINI)
#   - For DeepSeek/GLM/Kimi, set their OpenAI-compatible Base URLs
#   - TAVILY_API_KEY  (optional, enables the web_search skill)
uv sync
uv run uvicorn main:app --reload
```

The backend runs at **<http://localhost:8000>** · Swagger docs: <http://localhost:8000/docs>

> **RAG note**: `uv sync` installs `sentence-transformers` + torch. If you skip them, the backend still boots and `FakeEmbedder` makes RAG a no-op (uploads → 503, retrieval → `[]`).

### 3. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend runs at **<http://localhost:5173>**, with Vite proxying `/api` → `http://localhost:8000`.

### Docker (one-click)

```bash
docker compose up
```

Frontend on **<http://localhost>** (port 80), backend proxied via nginx; SSE passthrough enabled (`proxy_buffering off`).

---

## Configuration (`.env`)

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` | — | OpenAI native |
| `ANTHROPIC_API_KEY` | — | Anthropic native |
| `DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL` | — | DeepSeek (OpenAI-compatible) |
| `GLM_API_KEY` / `GLM_BASE_URL` | — | GLM / Zhipu (OpenAI-compatible) |
| `KIMI_API_KEY` / `KIMI_BASE_URL` | — | Kimi / Moonshot (OpenAI-compatible) |
| `GEMINI_API_KEY` | — | Gemini native |
| `TAVILY_API_KEY` | — | Tavily web search (free tier available) |
| `AGENT_MAX_STEPS` | `8` | Agent ReAct max steps |
| `AGENT_STEP_TEMPERATURE` | `0.7` | Step temperature (placeholder) |
| `AGENT_FINAL_TEMPERATURE` | `0.4` | Final-answer temperature (placeholder) |
| `EMBEDDING_MODEL` | `BAAI/bge-small-zh-v1.5` | Local embedding model |
| `EMBEDDING_DEVICE` | `cpu` | Embedding device (`cpu` / `cuda`) |
| `CHROMA_PERSIST_DIR` | `.chroma` | ChromaDB index directory (resolved vs. backend root) |
| `KB_CHUNK_SIZE` / `KB_CHUNK_OVERLAP` | `800` / `100` | Chunking params |
| `KB_TOP_K` / `KB_MIN_SCORE` | `4` / `0.3` | Retrieval params |
| `DATABASE_URL` | `sqlite+aiosqlite:///./workbench.db` | Database URL |

---

## API Reference

| Method | Path | Description |
| ------ | ---- | ----------- |
| `GET` | `/health` | Health check |
| `GET` | `/api/conversations?q=` | List conversations (optional search) |
| `POST` | `/api/conversations` | Create conversation |
| `GET` | `/api/conversations/{id}` | Get conversation detail (with messages) |
| `PATCH` | `/api/conversations/{id}` | Rename conversation |
| `DELETE` | `/api/conversations/{id}` | Delete conversation |
| `POST` | `/api/chat` | Send message (SSE streaming) |
| `POST` | `/api/agent-chat` | Agent ReAct chat (SSE streaming) |
| `POST` | `/api/upload` | Upload file |
| `GET` | `/api/models` | List active models |
| `GET` | `/api/models/all` | List all models |
| `POST` | `/api/models` | Create model |
| `PUT` | `/api/models/{id}` | Update model |
| `DELETE` | `/api/models/{id}` | Delete model |
| `GET` | `/api/skills` | List skills manifest (with `source`) |
| `POST` | `/api/skills/{name}` | Invoke a skill |
| `POST` | `/api/skills/reload` | Hot-reload markdown skills |
| `GET` | `/api/skills/md/{name}` | Get a markdown skill source |
| `POST` | `/api/skills/md` | Create a markdown skill |
| `PUT` | `/api/skills/md/{name}` | Update a markdown skill |
| `DELETE` | `/api/skills/md/{name}` | Delete a markdown skill |
| `GET` | `/api/knowledge-bases` | List knowledge bases |
| `POST` | `/api/knowledge-bases` | Create knowledge base |
| `GET` | `/api/knowledge-bases/{id}` | Get knowledge base |
| `PATCH` | `/api/knowledge-bases/{id}` | Update knowledge base |
| `DELETE` | `/api/knowledge-bases/{id}` | Delete knowledge base (+ docs) |
| `GET` | `/api/knowledge-bases/{id}/documents` | List documents |
| `POST` | `/api/knowledge-bases/{id}/documents` | Upload document (multipart) |
| `DELETE` | `/api/knowledge-bases/{id}/documents/{doc_id}` | Delete document |

### Streaming Chat Request Body (`POST /api/chat`)

```json
{
  "conversation_id": "uuid-or-null",
  "model": "deepseek-v4-flash",
  "messages": [{ "role": "user", "content": "Hello" }],
  "files": [],
  "stream": true,
  "thinking": true,
  "rag_knowledge_base_id": null
}
```

### Agent Chat Request Body (`POST /api/agent-chat`)

Extends `ChatRequest` with:

```json
{
  "max_steps": 8,
  "enable_skills": null,
  "step_temperature": null,
  "final_temperature": null
}
```

### SSE Response Format

Normal chat:

```text
data: {"type":"thinking","content":"thinking process..."}
data: {"type":"text","content":"answer content..."}
data: {"type":"done","message":{"id":"...","content":"...","thinking":"..."}}
```

Agent chat additionally emits step-bounded events (flat `action`/`observation`/`warning`/`narration` events are also sent for backward compatibility):

```text
data: {"type":"step_start","step":1,"label":"第 1 步思考"}
data: {"type":"action","name":"retrieve_notes","input":"...","step":1}
data: {"type":"observation","name":"retrieve_notes","content":"...","step":1}
data: {"type":"retrieved","step":1,"docs":[{"doc":"notes.md","heading":"安装","score":0.81,"text":"..."}]}
data: {"type":"narration","content":"我先查一下笔记...","step":1}
data: {"type":"step_end","step":1,"finish":"tool"}
data: {"type":"done","message":{"id":"...","metadata":{"agent":true,"steps":[...]}}}
```

`step_end` finish values: `final` | `tool` | `empty` | `max_steps` | `error`.

---

## Project Structure

```text
My_Agent/
├── backend/                       # Python backend
│   ├── main.py                    # FastAPI entry (router registration, lifespan, migrations)
│   ├── pyproject.toml             # uv dependency management
│   ├── .env.example               # Environment variable template
│   ├── skills_md/                 # Markdown-defined skills (translator.md, summarizer.md)
│   └── app/
│       ├── config.py              # pydantic-settings configuration
│       ├── database.py            # SQLAlchemy async engine
│       ├── models.py              # ORM (Conversation, Message, ModelConfig, UploadedFile, KnowledgeBase, KnowledgeDoc)
│       ├── schemas.py             # Pydantic request/response schemas
│       ├── dependencies.py        # FastAPI dependency injection
│       ├── seed.py                # Default model seeder
│       ├── adapters/              # LLM adapters (Strategy Pattern)
│       │   ├── base.py            # BaseAdapter + StreamChunk
│       │   ├── factory.py         # Adapter factory (model-level key → vendor key)
│       │   ├── openai_adapter.py
│       │   ├── anthropic_adapter.py
│       │   └── gemini_adapter.py
│       ├── routers/               # API routes
│       │   ├── chat.py            # /api/chat (SSE)
│       │   ├── agent.py           # /api/agent-chat (SSE, ReAct)
│       │   ├── conversations.py
│       │   ├── models.py
│       │   ├── upload.py
│       │   ├── skills.py          # skills manifest + MD CRUD + reload
│       │   └── knowledge.py       # knowledge bases + documents
│       ├── services/
│       │   ├── conversation_service.py
│       │   ├── agent_service.py   # LangGraph ReAct + tool calling + step events
│       │   ├── langchain_adapter.py  # AdapterChatModel → BaseAdapter bridge
│       │   ├── knowledge_service.py  # KB/doc CRUD + chunking + retrieve
│       │   ├── embedding_service.py  # bge-small-zh singleton + FakeEmbedder fallback
│       │   ├── file_parser.py
│       │   ├── _chat_helpers.py
│       │   └── prompts/react_system.txt
│       └── skills/                # Skill registry + built-in skills
│           ├── base.py            # Skill Protocol + SkillResult
│           ├── registry.py        # discover/reload markdown + Python skills
│           ├── markdown_skill.py
│           ├── retrieve_notes.py  # RAG factory skill
│           ├── web_search.py      # Tavily
│           ├── echo.py
│           └── current_time.py
├── frontend/                      # React frontend
│   ├── index.html · vite.config.ts · package.json
│   └── src/
│       ├── main.tsx · App.tsx
│       ├── types/index.ts         # TypeScript types (incl. AgentStep, AgentTraceData)
│       ├── api/                   # API client layer (snake_case ↔ camelCase)
│       │   ├── client.ts · chat.ts · agent-chat.ts
│       │   ├── conversations.ts · models.ts · upload.ts
│       │   ├── knowledge.ts · skills.ts
│       ├── components/
│       │   ├── WorkspaceLayout.tsx · Sidebar.tsx · ConversationList.tsx
│       │   ├── ChatHeader.tsx · MessageList.tsx · MessageItem.tsx
│       │   ├── InputArea.tsx · ThinkingBlock.tsx · MarkdownContent.tsx
│       │   ├── AgentTrace.tsx     # step-card trace panel
│       │   ├── ModelManager.tsx · KnowledgeBaseManager.tsx · SkillsManager.tsx
│       │   ├── EmptyState.tsx · ErrorBoundary.tsx · ToastContainer.tsx
│       │   └── ui/                # shadcn/ui primitives
│       ├── hooks/                 # useChatStream · useConversation
│       ├── store/                 # workspaceStore (Zustand) · toastStore
│       └── lib/                   # case.ts (naming) · utils.ts (cn)
├── scripts/                       # dev helpers (seed-1000msgs.py, test-agent-chat.py)
├── docker-compose.yml
├── Requirement.md                 # Requirements document
├── DEVELOPMENT_PLAN.md            # Development plan
├── PROGRESS.md                    # Progress tracking
├── README.md                      # This file
└── README_zh.md                   # Chinese README
```

---

## Database Models

| Table | Description | Key Fields |
| ----- | ----------- | ---------- |
| `conversations` | Conversations | id, title, created_at, updated_at |
| `messages` | Messages | id, conversation_id, role, content, thinking, model, status, metadata_ |
| `uploaded_files` | Uploaded files | id, conversation_id, name, text_content |
| `model_configs` | Model configs | id, model_id, vendor, name, adapter_type, base_url, api_key, is_active |
| `knowledge_bases` | Knowledge bases | id, name, description, created_at, updated_at |
| `knowledge_docs` | KB documents | id, kb_id, filename, sha256, text, created_at |

Schema changes are applied via lightweight `ALTER TABLE` migrations on startup (no Alembic).

---

## Development

### Run tests

```bash
# Backend
cd backend && uv run pytest -q            # CI-equivalent: uv run pytest -m "not slow"

# Frontend
cd frontend && npm run test && npm run build && npm run lint
```

### Performance check

```bash
python scripts/seed-1000msgs.py          # seed a 1000-message conversation for dev testing
```

---

## Roadmap

See [DEVELOPMENT_PLAN.md](./DEVELOPMENT_PLAN.md) for the full plan and [PROGRESS.md](./PROGRESS.md) for the latest status.

### Phase Summary

| Phase | Status | Description |
| ----- | ------ | ----------- |
| Phase 1 | ✅ Done | Backend framework + database + model adapters + streaming chat API |
| Phase 2 | ✅ Done | Frontend framework + conversation management + message display + streaming render |
| Phase 3 | ✅ Done | Deep Thinking end-to-end |
| Phase 4 | ✅ Done | File upload + model management + virtual scrolling |
| Cross-platform + deploy | ✅ Done | Docker + GHA 3-platform matrix + perf/hook tests |
| AgentService Phase 1 | ✅ Done | ReAct multi-step reasoning (no tools) |
| AgentService Phase 2a | ✅ Done | LangGraph + tool calling (Skills → tools) |
| AgentService Phase 2b-i | ✅ Done | RAG + knowledge base management |
| AgentService Phase 2b-ii | ✅ Done | AgentTrace panel + step-bounded SSE |
| Phase 3 Round 1 | ✅ Done | Markdown skills + web search + interleaved Agent output |
| Phase 3 Round 2 | ✅ Done | Skills Manager UI + Tavily web search |

### Planned (Phase 3 Round 3, scope TBD)

- Vendor-native tool-calling API (OpenAI `tool_calls` delta / Anthropic `tools`) to replace ReAct prompt injection.
- Async document processing (return `doc_id` immediately, background chunking + embedding).
- Hybrid retrieval (BM25 + vector ensemble).
- RAG over PDF / DOCX.

---

## Security Notes

- **Single-user design**: No authentication — intended for local / intranet use only.
- **API Keys**: Stored server-side in `.env` or the `model_configs` table; never exposed to the frontend (only `has_api_key`).
- **Skill names**: Validated against `^[a-zA-Z][a-zA-Z0-9_-]*$` (path-traversal safe).
- **Database**: Local SQLite file (`workbench.db`) by default; no remote access.
