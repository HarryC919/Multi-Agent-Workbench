# AI Chat Workbench

[简体中文](./README_zh.md)

An intelligent chat workbench (Kimi Workspace-like) with a decoupled frontend/backend architecture, providing unified access to multiple LLM vendors with streaming dialogue.

---

## Architecture Overview

```text
┌─────────────────────────────────────────────────────────────┐
│  Frontend (React 19 + Vite + Tailwind CSS v4)               │
│  ┌───────────┐ ┌──────────────────────────────────────────┐ │
│  │  Sidebar  │ │  Workspace                               │ │
│  │           │ │  ┌──────────────────────────────────┐    │ │
│  │ Chat List │ │  │ ChatHeader (Model Select +       │    │ │
│  │Search Box │ │  │            Thinking Toggle)      │    │ │
│  │ New Chat  │ │  ├──────────────────────────────────┤    │ │
│  │           │ │  │ MessageList (virtualized)        │    │ │
│  │           │ │  │ ┌──────────────────────────────┐ │    │ │
│  │           │ │  │ │ MessageItem                  │ │    │ │
│  │           │ │  │ │ ├ Markdown Render            │ │    │ │
│  │           │ │  │ │ ├ Code Highlight             │ │    │ │
│  │           │ │  │ │ └ ThinkingBlock (collapsible)│ │    │ │
│  │           │ │  │ └──────────────────────────────┘ │    │ │
│  │           │ │  ├──────────────────────────────────┤    │ │
│  │           │ │  │ InputArea (Input + File Upload   │    │ │
│  │           │ │  │            + Send)               │    │ │
│  │           │ │  └──────────────────────────────────┘    │ │
│  └───────────┘ └──────────────────────────────────────────┘ │
│            │                                                │
│            │ HTTP (Vite Proxy /api → :8000)                 │
│            ▼                                                │
│  Zustand Store (State Management + localStorage Persist)    │
└─────────────────────────────────────────────────────────────┘
                           │
                    ┌──────┴──────┐
                    ▼             ▼
┌─────────────────────────────────────────────────────────────┐
│  Backend (FastAPI + SQLAlchemy + SQLite)                    │
│  ┌────────────┐ ┌────────────────┐ ┌──────────────────┐     │
│  │ Routers    │ │ Services       │ │ Adapters         │     │
│  │ /api/chat  │ │ Conversation   │ │ OpenAI           │     │
│  │ /api/conv. │ │ Service        │ │ Anthropic        │     │
│  │ /api/models│ │ File Parser    │ │ Gemini           │     │
│  │ /api/upload│ └────────────────┘ │ OpenAI-Compatible│     │
│  └────────────┘                    │ (DeepSeek/GLM/   │     │
│  ┌────────────┐                    │  Kimi)           │     │
│  │ Models     │                    └──────────────────┘     │
│  │ ORM +      │                     ▲                       │
│  │ Pydantic   │                     │ httpx + SSE           │
│  └────────────┘                     │                       │
│  ┌────────────┐                     │                       │
│  │ SQLite     │◄────────────────────┘                       │
│  │ (aiosqlite)│                                             │
│  └────────────┘                                             │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
              ┌──────────────────────────┐
              │  LLM Providers           │
              │  OpenAI / Anthropic      │
              │  Gemini / DeepSeek       │
              │  GLM / Kimi              │
              └──────────────────────────┘
```

---

## Tech Stack

### Frontend

| Category | Tech | Purpose |
| ---------- | ------ | --------- |
| Framework | React 19 | UI construction |
| Language | TypeScript ~6.0 | Type safety |
| Build | Vite 8 | Dev / build tooling |
| Styling | Tailwind CSS v4 | Utility-first CSS |
| Components | shadcn/ui | UI primitives (Button, Input, Modal, Select) |
| State Mgmt | Zustand 5 + persist | Global state + localStorage persistence |
| Virtual Scroll | @tanstack/react-virtual | Long-list performance |
| Markdown | react-markdown + remark-gfm | Message rendering |
| Code Highlight | react-syntax-highlighter | Syntax highlighting for code blocks |
| File Upload | react-dropzone | Drag-and-drop / click upload |
| Icons | lucide-react | UI icons |
| Date | date-fns | Time formatting |

### Backend

| Category | Tech | Purpose |
| ---------- | ------ | --------- |
| Framework | FastAPI (≥0.115) | Web server |
| Runtime | Uvicorn | ASGI server |
| ORM | SQLAlchemy 2.0 (async) | Database operations |
| Database | SQLite + aiosqlite | Persistent storage |
| Validation | Pydantic v2 + pydantic-settings | Request validation + config management |
| HTTP | httpx | LLM API calls |
| PDF | pdfplumber | PDF file parsing |
| DOCX | python-docx | Word file parsing |

---

## Features

### Multi-Vendor Model Adapters

- **Native adapters**: OpenAI, Anthropic, Gemini — independent implementations
- **Compatible adapters**: DeepSeek, GLM, Kimi via OpenAI-compatible protocol
- **Unified interface**: Strategy Pattern — transparent switching at higher layers
- **Runtime management**: Add, edit, delete model configurations on the fly; each model can have its own API Key and Base URL

### Streaming Chat

- SSE (Server-Sent Events) based token-by-token streaming
- Real-time rendering with abort support (AbortController)
- Message state lifecycle: pending → streaming → done / error

### Deep Thinking

- One-click toggle in the input area
- When enabled, the model streams its reasoning process before the final answer
- Thinking content shown in collapsible blocks, visually distinct from the reply (font size & color)
- Auto-expands during streaming, auto-collapses when the main answer begins; manual toggle also supported
- Thinking content persisted to SQLite — visible after refresh or session reopen
- Supported vendors:
  - **Anthropic**: Native extended thinking (`thinking_delta` event)
  - **OpenAI-compatible** (DeepSeek / GLM / Kimi): via `reasoning_content` field
  - **Gemini**: Not yet supported

### Conversation Management

- Multiple parallel conversations listed in the sidebar
- Auto-generated titles from the first user message
- Search filtering (backend ILIKE fuzzy match)
- Rename / delete conversations

### File Upload

- Supported formats: `.txt` / `.md` / `.json` / `.yaml` / `.xml` / `.html` / `.css` / `.js` / `.ts` / `.py` / `.java` / `.c` / `.cpp` / `.go` / `.rs` + `.pdf` + `.docx`
- File content parsed to text and sent as conversation context
- Drag-and-drop upload (react-dropzone)

### Model Management

- 11 pre-seeded default models (GPT-5.5, GPT-5.4, Claude Opus 4.8, Claude Sonnet 5, Gemini 3.1 Pro, Gemini 3.5 Flash, DeepSeek-V4-Flash, DeepSeek-V4-Pro, Kimi K2.6, GLM-5.2, GLM-4.7)
- CRUD operations at runtime
- Each model independently configurable: adapter type, Base URL, API Key
- API Key never exposed to the frontend (only `has_api_key` boolean returned)

### Virtual Scrolling

- `@tanstack/react-virtual` for message list virtualization
- High performance even with large message volumes

---

## Quick Start

### Prerequisites

- Python ≥ 3.12 (recommended: [uv](https://docs.astral.sh/uv/))
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
# Edit .env with your API Keys
# For DeepSeek, GLM, Kimi, enter their OpenAI-compatible Base URLs
uv sync
uv run uvicorn main:app --reload
```

The backend runs at **<http://localhost:8000>**

Swagger docs: <http://localhost:8000/docs>

### 3. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend runs at **<http://localhost:5173>**, with Vite configured to proxy `/api` → `http://localhost:8000`.

### Docker (Experimental)

```bash
docker-compose up
```

---

## API Reference

| Method | Path | Description |
| -------- | ------ | ------------- |
| `GET` | `/health` | Health check |
| `GET` | `/api/conversations?q=` | List conversations (optional search) |
| `POST` | `/api/conversations` | Create conversation |
| `GET` | `/api/conversations/{id}` | Get conversation detail (with messages) |
| `PATCH` | `/api/conversations/{id}` | Rename conversation |
| `DELETE` | `/api/conversations/{id}` | Delete conversation |
| `POST` | `/api/chat` | Send message (SSE streaming response) |
| `POST` | `/api/upload` | Upload file |
| `GET` | `/api/models` | List active models |
| `GET` | `/api/models/all` | List all models |
| `POST` | `/api/models` | Create model |
| `PUT` | `/api/models/{id}` | Update model |
| `DELETE` | `/api/models/{id}` | Delete model |
| `GET` | `/api/skills` | List skills (placeholder) |
| `POST` | `/api/skills/{name}` | Invoke skill (placeholder) |

### Streaming Chat Request Body (`POST /api/chat`)

```json
{
  "conversation_id": "uuid-or-null",
  "model": "deepseek-v4-flash",
  "messages": [
    { "role": "user", "content": "Hello" }
  ],
  "files": [],
  "stream": true,
  "thinking": true
}
```

SSE Response Format:

```text
data: {"type":"thinking","content":"thinking process..."}
data: {"type":"text","content":"answer content..."}
data: {"type":"done","message":{"id":"...","content":"...","thinking":"..."}}
```

---

## Project Structure

```text
My_Agent/
├── backend/                     # Python backend
│   ├── main.py                  # FastAPI entry point
│   ├── pyproject.toml           # Dependency management
│   ├── .env.example             # Environment variable template
│   └── app/
│       ├── config.py            # pydantic-settings configuration
│       ├── database.py          # SQLAlchemy async engine
│       ├── models.py            # ORM models (Conversation, Message, ModelConfig, UploadedFile)
│       ├── schemas.py           # Pydantic request/response schemas
│       ├── dependencies.py      # FastAPI dependency injection
│       ├── seed.py              # Default model seeder
│       ├── adapters/            # LLM adapters (Strategy Pattern)
│       │   ├── base.py          # Abstract BaseAdapter + StreamChunk
│       │   ├── factory.py       # Adapter factory
│       │   ├── openai_adapter.py
│       │   ├── anthropic_adapter.py
│       │   └── gemini_adapter.py
│       ├── routers/             # API routes
│       │   ├── chat.py
│       │   ├── conversations.py
│       │   ├── models.py
│       │   ├── upload.py
│       │   └── skills.py
│       └── services/
│           ├── conversation_service.py
│           └── file_parser.py
├── frontend/                    # React frontend
│   ├── index.html
│   ├── vite.config.ts
│   ├── package.json
│   └── src/
│       ├── main.tsx             # React entry point
│       ├── App.tsx              # Root component
│       ├── types/index.ts       # TypeScript type definitions
│       ├── api/                 # API client layer
│       │   ├── client.ts        # Base fetch (snake_case ←→ camelCase)
│       │   ├── chat.ts          # SSE streaming chat
│       │   ├── conversations.ts
│       │   ├── models.ts
│       │   └── upload.ts
│       ├── components/          # UI components
│       │   ├── WorkspaceLayout.tsx
│       │   ├── Sidebar.tsx
│       │   ├── ConversationList.tsx
│       │   ├── ChatHeader.tsx
│       │   ├── MessageList.tsx
│       │   ├── MessageItem.tsx
│       │   ├── InputArea.tsx
│       │   ├── ThinkingBlock.tsx
│       │   ├── ModelManager.tsx
│       │   ├── EmptyState.tsx
│       │   ├── ErrorBoundary.tsx
│       │   └── ui/              # shadcn/ui primitives
│       ├── hooks/
│       │   ├── useChatStream.ts
│       │   └── useConversation.ts
│       ├── store/
│       │   ├── workspaceStore.ts # Zustand global state
│       │   └── toastStore.ts
│       └── lib/
│           ├── case.ts          # Naming convention conversion
│           └── utils.ts         # cn() utility
├── docker-compose.yml
├── REQUIREMENT.md               # Requirements document
├── DEVELOPMENT_PLAN.md          # Development plan
├── PROGRESS.md                  # Progress tracking
├── README.md                    # README 
└── README_zh.md                 # Chinese README
```

---

## Database Models

| Table | Description | Key Fields |
| ------- | ------------- | ------------ |
| `conversations` | Conversations | id, title, created_at, updated_at |
| `messages` | Messages | id, conversation_id, role, content, thinking, model, status |
| `uploaded_files` | Uploaded files | id, conversation_id, name, text_content |
| `model_configs` | Model configs | id, model_id, vendor, name, adapter_type, base_url, api_key, is_active |

---

## Development Plan

See [DEVELOPMENT_PLAN.md](./DEVELOPMENT_PLAN.md) for details.

### Phase Summary

| Phase | Status | Description |
| ------- | -------- | ------------- |
| Phase 1 | ✅ Done | Backend framework + database + model adapters + streaming chat API |
| Phase 2 | ✅ Done | Frontend framework + conversation management + message display + streaming render |
| Phase 3 | ✅ Done | Deep Thinking end-to-end |
| Phase 4 | ✅ Done | File upload + model management + virtual scrolling |

Latest progress: [PROGRESS.md](./PROGRESS.md)

---

## Security Notes

- **Single-user design**: No authentication — intended for local / intranet use only
- **API Keys**: Stored server-side in `.env` or the `model_configs` database table; never exposed to the frontend
- **Database**: Local SQLite file (`workbench.db`) by default; no remote access
