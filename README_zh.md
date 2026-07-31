# AI Chat Workbench

[English](./README.md)

智能对话工作台（类 Kimi Workspace），前后端分离实现。它不止于流式对话：**Agent 模式**驱动多步 ReAct 推理与**工具调用**，支持个人知识库的 **RAG**、结构化**步骤轨迹**、**Markdown 技能**系统及管理 UI、**联网搜索**，所有能力都建立在统一的多厂商大模型接入层之上。

> 已在 Windows / Linux / macOS 三平台 CI 验证，支持 `docker compose up` 一键部署。

---

## 它能做什么？

| 能力 | 说明 |
| ---- | ---- |
| **多厂商对话** | OpenAI / Anthropic / Gemini（原生）+ DeepSeek / GLM / Kimi（OpenAI 兼容）。策略模式适配器，无感知切换，每个模型可独立配置 API Key 与 Base URL。 |
| **流式对话** | 基于 SSE 的逐 token 流式输出，实时渲染、可中止，多轮对话持久化到 SQLite。 |
| **深度思考** | 输入区一键开关，模型正式回答前流式输出思考过程，可折叠区块呈现，刷新后仍可见。 |
| **Agent 模式** | 基于 LangGraph 的 ReAct 循环 + 真实**工具调用**。Skills 包装为工具；每步的 Thought / Action / Observation 均流式输出。 |
| **RAG / 知识库** | 本地 `bge-small-zh` 向量化 + Chroma 向量库。上传 `.md` 笔记；普通对话自动注入，Agent 模式经 `retrieve_notes` 工具**自主检索**。 |
| **AgentTrace 面板** | 结构化步骤卡片（Thought / Action / Observation / 检索片段）+ step-bounded SSE，不再是扁平文本。 |
| **技能系统** | `.md` 文件定义技能（YAML frontmatter + 正文 system prompt），支持热重载。内置 `echo` / `current_time` / `web_search` / `retrieve_notes` + 通过**技能管理 UI** 编辑 MD 技能。 |
| **联网搜索** | 基于 Tavily 的 `web_search` 技能（替换了被限流的 DuckDuckGo 方案）。 |
| **文件上传** | `.txt` / `.md` / 代码文件 / `.pdf` / `.docx` 解析为文本作为上下文发送。 |
| **模型管理** | 预置 11 个模型，运行时增删改；模型级 API Key 不暴露给前端。 |
| **虚拟滚动** | `@tanstack/react-virtual` 动态测高，1000+ 消息下保持流畅。 |

---

## 架构概览

```text
┌──────────────────────────────────────────────────────────────────┐
│  Frontend (React 19 + Vite + Tailwind CSS v4)                    │
│  ┌───────────┐ ┌─────────────────────────────────────────────┐  │
│  │  Sidebar  │ │  Workspace                                  │  │
│  │ Chat List │ │  ┌─────────────────────────────────────┐    │  │
│  │ Search    │ │  │ ChatHeader (模型/思考/Agent 开关       │    │  │
│  │ New Chat  │ │  │  / 知识库选择 / 技能 / 模型管理)        │    │  │
│  │           │ │  ├─────────────────────────────────────┤    │  │
│  │           │ │  │ MessageList (虚拟滚动)                │    │  │
│  │           │ │  │  MessageItem                          │    │  │
│  │           │ │  │   ├ MarkdownContent (渲染 + 高亮)      │    │  │
│  │           │ │  │   ├ ThinkingBlock (可折叠)            │    │  │
│  │           │ │  │   └ AgentTrace (步骤卡片)             │    │  │
│  │           │ │  ├─────────────────────────────────────┤    │  │
│  │           │ │  │ InputArea (输入 + 文件上传 + 发送      │    │  │
│  │           │ │  │  + 思考/Agent 开关)                   │    │  │
│  │           │ │  └─────────────────────────────────────┘    │  │
│  └───────────┘ └─────────────────────────────────────────────┘  │
│            │  Zustand store + localStorage 持久化                 │
└────────────┼─────────────────────────────────────────────────────┘
             │ HTTP (Vite 代理 /api → :8000)
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
│  │ Models (ORM) │ │ Skills (注册表)                            │ │
│  │  + Pydantic  │ │  echo · current_time · web_search (Tavily)│ │
│  └──────────────┘ │  retrieve_notes (RAG) · MarkdownSkill(.md)│ │
│  ┌──────────────┐ └──────────────────────────────────────────┘ │
│  │ SQLite       │  ┌─────────────────────────────────────────┐ │
│  │  + aiosqlite │  │ ChromaDB (向量) · bge-small-zh 向量化    │ │
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

## 技术栈

### 前端

| 类别 | 技术 | 用途 |
| ---- | ---- | ---- |
| 框架 | React 19 | UI 构建 |
| 语言 | TypeScript | 类型安全 |
| 构建 | Vite | 开发/构建 |
| 样式 | Tailwind CSS v4 | 原子化 CSS |
| 组件库 | shadcn/ui | UI 原语（Button, Input, Modal, Select） |
| 状态管理 | Zustand 5 + persist | 全局状态 + localStorage 持久化 |
| 虚拟滚动 | @tanstack/react-virtual | 长列表性能优化 |
| Markdown | react-markdown + remark-gfm | 消息渲染 |
| 代码高亮 | react-syntax-highlighter | 代码块语法高亮 |
| 文件上传 | react-dropzone | 拖拽/点击上传 |
| 图标 | lucide-react | UI 图标 |
| 日期 | date-fns | 时间格式化 |

### 后端

| 类别 | 技术 | 用途 |
| ---- | ---- | ---- |
| 框架 | FastAPI (≥0.115) | Web 服务 |
| 运行时 | Uvicorn | ASGI 服务器 |
| ORM | SQLAlchemy 2.0 (async) | 数据库操作 |
| 数据库 | SQLite + aiosqlite | 持久化存储 |
| 校验 | Pydantic v2 + pydantic-settings | 请求校验 + 配置管理 |
| HTTP | httpx | 调用 LLM API |
| Agent 编排 | LangGraph + langchain-core | ReAct 循环、工具调用 |
| LLM 桥接 | langchain-text-splitters | Markdown / 递归分块 |
| 向量库 | chromadb | 磁盘持久化向量存储 |
| 向量化 | sentence-transformers + `BAAI/bge-small-zh-v1.5` | 本地 embedding 模型 |
| 联网搜索 | tavily-python | `web_search` 技能后端 |
| PDF | pdfplumber | PDF 文件解析 |
| DOCX | python-docx | Word 文件解析 |

---

## 功能特性

### 多厂商模型适配

- **原生适配器**：OpenAI / Anthropic / Gemini 各自独立实现。
- **兼容适配器**：DeepSeek、GLM、Kimi 走 OpenAI 兼容协议。
- **统一接口**：适配器模式（Strategy Pattern），上层无感知切换。
- **模型级凭证**：每个模型携带自己的 API Key 与 Base URL；factory 解析顺序为模型级 key → `.env` 的 vendor key（向后兼容）。Key 不回传前端（仅 `has_api_key` 布尔值）。

### 流式对话

- 基于 SSE 的逐 token 流式输出。
- 前端实时渲染，支持中止发送（AbortController）。
- 消息状态：pending → streaming → done / error。

### 深度思考（Thinking）

- 输入区一键开关。
- 模型正式回答前流式输出思考过程。
- 思考内容以可折叠区块呈现，与回复正文有区分。
- 持久化到 SQLite，刷新或重开会话后仍可见。
- 生效范围：**Anthropic**（原生 `thinking_delta`）、**OpenAI 兼容厂商**（DeepSeek / GLM / Kimi 经 `reasoning_content`）；Gemini 暂不支持。

### Agent 模式

- 基于 LangGraph 的 ReAct 循环 + 真实**工具调用**——Skills 包装为 LangChain `StructuredTool`，在循环内执行。
- 每步流式输出 **Thought / Action / Observation**，以及一行 **narration** 作为正文渲染（与可折叠推理卡片交错）。
- `max_steps` 安全网；优雅中止（partial 轨迹持久化）。
- **无工具兜底**：无 skill / KB 时，Agent 跳过 ReAct 直接作答（不死循环）。
- 每条 assistant 消息持久化 metadata（`step_count` / `aborted` / `tool_calls` / `steps` / `agent`）。

### RAG / 知识库

- **本地向量化**：`bge-small-zh-v1.5` 经 `sentence-transformers`（零网络成本）；未装 torch / 模型时回退 no-op 的 `FakeEmbedder`（上传返 503、检索返 `[]`）。
- **向量库**：ChromaDB（磁盘持久化，每个 KB 一个 collection）。
- **普通对话**：KB 命中段落静默 prepend 到 user 消息。
- **Agent 模式**：`retrieve_notes` 工具让 Agent 自主检索笔记；结果以结构化 `retrieved` 片段出现在轨迹中。
- **分块**：`MarkdownHeaderTextSplitter` → `RecursiveCharacterTextSplitter`（可配置 size / overlap / top-k / min-score）。
- 上传格式：`.md` / `.markdown` / `.txt`（PDF/DOCX RAG 计划中）。

### AgentTrace 面板

- 结构化**步骤卡片**而非扁平推理文本：每张卡片含 Thought / Action / Observation / 检索片段 + finish 徽标。
- step-bounded SSE 协议（`step_start` / `step_end` / `retrieved`），扁平事件保留以向后兼容。
- narration（`说明:` 行）作为始终可见的正文渲染在卡片下方；仅最终答案提升为 `message.content`。

### 技能系统

- **Markdown 技能**：`.md` 文件放 `backend/skills_md/`（YAML frontmatter 提供 `name`/`description`，正文作 system prompt）。`POST /api/skills/reload` 热重载。
- **Python 技能**：内置 `echo`、`current_time`、`web_search`（Tavily）、`retrieve_notes`。
- **技能管理 UI**：ChatHeader 内新建 / 编辑 / 删除 `.md` 技能；Python 技能只读。
- **联网搜索**：基于 Tavily 的 `web_search` 技能（替换被限流的 DuckDuckGo 方案）。

### 会话管理

- 多会话并行，侧边栏列表展示。
- 会话标题自动从首条用户消息生成。
- 搜索过滤（后端 ILIKE 模糊匹配）、重命名 / 删除（含确认）、右键菜单。

### 文件上传

- 格式：`.txt` / `.md` / `.json` / `.yaml` / `.xml` / `.html` / `.css` / 代码文件（`.js` / `.ts` / `.py` / `.java` / `.c` / `.cpp` / `.go` / `.rs` 等）+ `.pdf` + `.docx`；未知扩展名做 UTF-8 文本启发式检测。
- 解析为文本随对话上下文发送；拖拽上传。

### 模型管理

- 预置 11 个默认模型（GPT-5.5 / GPT-5.4 / Claude Opus 4.8 / Claude Sonnet 5 / Gemini 3.1 Pro / Gemini 3.5 Flash / DeepSeek-V4-Flash / DeepSeek-V4-Pro / Kimi K2.6 / GLM-5.2 / GLM-4.7）。
- 运行时增删改；每个模型可独立配置 adapter 类型、Base URL、API Key。

### 虚拟滚动

- `@tanstack/react-virtual` + 动态 `measureElement`，大量消息下保持高性能。

---

## 快速开始

### 环境要求

- Python ≥ 3.11（推荐使用 [uv](https://docs.astral.sh/uv/)）
- Node.js ≥ 20

### 1. 克隆并进入项目

```bash
git clone <repo-url>
cd My_Agent
```

### 2. 启动后端

```bash
cd backend
cp .env.example .env
# 编辑 .env：
#   - 填入 vendor API Key（OPENAI / ANTHROPIC / DEEPSEEK / GLM / KIMI / GEMINI）
#   - DeepSeek / GLM / Kimi 请填写对应的 OpenAI 兼容 Base URL
#   - TAVILY_API_KEY（可选，启用 web_search 技能）
uv sync
uv run uvicorn main:app --reload
```

后端运行在 **<http://localhost:8000>** · Swagger 文档：<http://localhost:8000/docs>

> **RAG 提示**：`uv sync` 会安装 `sentence-transformers` + torch。若跳过，后端仍可启动，`FakeEmbedder` 会让 RAG 降级为 no-op（上传 → 503，检索 → `[]`）。

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端运行在 **<http://localhost:5173>**，Vite 已配置代理 `/api` → `http://localhost:8000`。

### Docker 一键部署

```bash
docker compose up
```

前端在 **<http://localhost>**（80 端口），后端经 nginx 反代；已关闭 `proxy_buffering` 保证 SSE 直通。

---

## 配置说明（`.env`）

| 变量 | 默认值 | 说明 |
| ---- | ------ | ---- |
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` | — | OpenAI 原生 |
| `ANTHROPIC_API_KEY` | — | Anthropic 原生 |
| `DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL` | — | DeepSeek（OpenAI 兼容） |
| `GLM_API_KEY` / `GLM_BASE_URL` | — | GLM / 智谱（OpenAI 兼容） |
| `KIMI_API_KEY` / `KIMI_BASE_URL` | — | Kimi / 月之暗面（OpenAI 兼容） |
| `GEMINI_API_KEY` | — | Gemini 原生 |
| `TAVILY_API_KEY` | — | Tavily 联网搜索（有免费额度） |
| `AGENT_MAX_STEPS` | `8` | Agent ReAct 最大步数 |
| `AGENT_STEP_TEMPERATURE` | `0.7` | 步级温度（占位） |
| `AGENT_FINAL_TEMPERATURE` | `0.4` | 最终答案温度（占位） |
| `EMBEDDING_MODEL` | `BAAI/bge-small-zh-v1.5` | 本地 embedding 模型 |
| `EMBEDDING_DEVICE` | `cpu` | 向量化设备（`cpu` / `cuda`） |
| `CHROMA_PERSIST_DIR` | `.chroma` | ChromaDB 索引目录（相对 backend root 解析） |
| `KB_CHUNK_SIZE` / `KB_CHUNK_OVERLAP` | `800` / `100` | 分块参数 |
| `KB_TOP_K` / `KB_MIN_SCORE` | `4` / `0.3` | 检索参数 |
| `DATABASE_URL` | `sqlite+aiosqlite:///./workbench.db` | 数据库 URL |

---

## API 文档

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| `GET` | `/health` | 健康检查 |
| `GET` | `/api/conversations?q=` | 列出会话（可选搜索） |
| `POST` | `/api/conversations` | 创建会话 |
| `GET` | `/api/conversations/{id}` | 获取会话详情（含消息） |
| `PATCH` | `/api/conversations/{id}` | 重命名会话 |
| `DELETE` | `/api/conversations/{id}` | 删除会话 |
| `POST` | `/api/chat` | 发送消息（SSE 流式） |
| `POST` | `/api/agent-chat` | Agent ReAct 对话（SSE 流式） |
| `POST` | `/api/upload` | 上传文件 |
| `GET` | `/api/models` | 列出活跃模型 |
| `GET` | `/api/models/all` | 列出所有模型 |
| `POST` | `/api/models` | 创建模型 |
| `PUT` | `/api/models/{id}` | 更新模型 |
| `DELETE` | `/api/models/{id}` | 删除模型 |
| `GET` | `/api/skills` | 列出技能清单（含 `source`） |
| `POST` | `/api/skills/{name}` | 调用技能 |
| `POST` | `/api/skills/reload` | 热重载 markdown 技能 |
| `GET` | `/api/skills/md/{name}` | 获取 markdown 技能源码 |
| `POST` | `/api/skills/md` | 新建 markdown 技能 |
| `PUT` | `/api/skills/md/{name}` | 更新 markdown 技能 |
| `DELETE` | `/api/skills/md/{name}` | 删除 markdown 技能 |
| `GET` | `/api/knowledge-bases` | 列出知识库 |
| `POST` | `/api/knowledge-bases` | 创建知识库 |
| `GET` | `/api/knowledge-bases/{id}` | 获取知识库 |
| `PATCH` | `/api/knowledge-bases/{id}` | 更新知识库 |
| `DELETE` | `/api/knowledge-bases/{id}` | 删除知识库（含文档） |
| `GET` | `/api/knowledge-bases/{id}/documents` | 列出文档 |
| `POST` | `/api/knowledge-bases/{id}/documents` | 上传文档（multipart） |
| `DELETE` | `/api/knowledge-bases/{id}/documents/{doc_id}` | 删除文档 |

### 流式聊天请求体 (`POST /api/chat`)

```json
{
  "conversation_id": "uuid-or-null",
  "model": "deepseek-v4-flash",
  "messages": [{ "role": "user", "content": "你好" }],
  "files": [],
  "stream": true,
  "thinking": true,
  "rag_knowledge_base_id": null
}
```

### Agent 对话请求体 (`POST /api/agent-chat`)

在 `ChatRequest` 基础上扩展：

```json
{
  "max_steps": 8,
  "enable_skills": null,
  "step_temperature": null,
  "final_temperature": null
}
```

### SSE 响应格式

普通对话：

```text
data: {"type":"thinking","content":"思考过程..."}
data: {"type":"text","content":"回答内容..."}
data: {"type":"done","message":{"id":"...","content":"...","thinking":"..."}}
```

Agent 对话额外发送 step-bounded 事件（同时发送扁平的 `action` / `observation` / `warning` / `narration` 事件以向后兼容）：

```text
data: {"type":"step_start","step":1,"label":"第 1 步思考"}
data: {"type":"action","name":"retrieve_notes","input":"...","step":1}
data: {"type":"observation","name":"retrieve_notes","content":"...","step":1}
data: {"type":"retrieved","step":1,"docs":[{"doc":"notes.md","heading":"安装","score":0.81,"text":"..."}]}
data: {"type":"narration","content":"我先查一下笔记...","step":1}
data: {"type":"step_end","step":1,"finish":"tool"}
data: {"type":"done","message":{"id":"...","metadata":{"agent":true,"steps":[...]}}}
```

`step_end` 的 finish 取值：`final` | `tool` | `empty` | `max_steps` | `error`。

---

## 项目结构

```text
My_Agent/
├── backend/                       # Python 后端
│   ├── main.py                    # FastAPI 入口（路由注册、lifespan、迁移）
│   ├── pyproject.toml             # uv 依赖管理
│   ├── .env.example               # 环境变量模板
│   ├── skills_md/                 # Markdown 定义的技能（translator.md, summarizer.md）
│   └── app/
│       ├── config.py              # pydantic-settings 配置
│       ├── database.py            # SQLAlchemy 异步引擎
│       ├── models.py              # ORM（Conversation, Message, ModelConfig, UploadedFile, KnowledgeBase, KnowledgeDoc）
│       ├── schemas.py             # Pydantic 请求/响应模型
│       ├── dependencies.py        # FastAPI 依赖注入
│       ├── seed.py                # 默认模型播种
│       ├── adapters/              # LLM 适配器（策略模式）
│       │   ├── base.py            # BaseAdapter + StreamChunk
│       │   ├── factory.py         # 适配器工厂（模型级 key → vendor key）
│       │   ├── openai_adapter.py
│       │   ├── anthropic_adapter.py
│       │   └── gemini_adapter.py
│       ├── routers/               # API 路由
│       │   ├── chat.py            # /api/chat (SSE)
│       │   ├── agent.py           # /api/agent-chat (SSE, ReAct)
│       │   ├── conversations.py
│       │   ├── models.py
│       │   ├── upload.py
│       │   ├── skills.py          # 技能清单 + MD CRUD + reload
│       │   └── knowledge.py       # 知识库 + 文档
│       ├── services/
│       │   ├── conversation_service.py
│       │   ├── agent_service.py   # LangGraph ReAct + 工具调用 + step 事件
│       │   ├── langchain_adapter.py  # AdapterChatModel → BaseAdapter 桥接
│       │   ├── knowledge_service.py  # KB/doc CRUD + 分块 + 检索
│       │   ├── embedding_service.py  # bge-small-zh 单例 + FakeEmbedder 兜底
│       │   ├── file_parser.py
│       │   ├── _chat_helpers.py
│       │   └── prompts/react_system.txt
│       └── skills/                # 技能注册表 + 内置技能
│           ├── base.py            # Skill Protocol + SkillResult
│           ├── registry.py        # markdown + Python 技能发现/重载
│           ├── markdown_skill.py
│           ├── retrieve_notes.py  # RAG 工厂技能
│           ├── web_search.py      # Tavily
│           ├── echo.py
│           └── current_time.py
├── frontend/                      # React 前端
│   ├── index.html · vite.config.ts · package.json
│   └── src/
│       ├── main.tsx · App.tsx
│       ├── types/index.ts         # TypeScript 类型（含 AgentStep, AgentTraceData）
│       ├── api/                   # API 客户端层（snake_case ↔ camelCase）
│       │   ├── client.ts · chat.ts · agent-chat.ts
│       │   ├── conversations.ts · models.ts · upload.ts
│       │   ├── knowledge.ts · skills.ts
│       ├── components/
│       │   ├── WorkspaceLayout.tsx · Sidebar.tsx · ConversationList.tsx
│       │   ├── ChatHeader.tsx · MessageList.tsx · MessageItem.tsx
│       │   ├── InputArea.tsx · ThinkingBlock.tsx · MarkdownContent.tsx
│       │   ├── AgentTrace.tsx     # 步骤卡片轨迹面板
│       │   ├── ModelManager.tsx · KnowledgeBaseManager.tsx · SkillsManager.tsx
│       │   ├── EmptyState.tsx · ErrorBoundary.tsx · ToastContainer.tsx
│       │   └── ui/                # shadcn/ui 原语
│       ├── hooks/                 # useChatStream · useConversation
│       ├── store/                 # workspaceStore (Zustand) · toastStore
│       └── lib/                   # case.ts (命名转换) · utils.ts (cn)
├── scripts/                       # 开发辅助（seed-1000msgs.py, test-agent-chat.py）
├── docker-compose.yml
├── Requirement.md                 # 需求文档
├── DEVELOPMENT_PLAN.md            # 开发计划
├── PROGRESS.md                    # 进度跟踪
├── README.md                      # 英文 README
└── README_zh.md                   # 本文件
```

---

## 数据库模型

| 表 | 说明 | 关键字段 |
| ---- | ---- | ---------- |
| `conversations` | 会话 | id, title, created_at, updated_at |
| `messages` | 消息 | id, conversation_id, role, content, thinking, model, status, metadata_ |
| `uploaded_files` | 上传文件 | id, conversation_id, name, text_content |
| `model_configs` | 模型配置 | id, model_id, vendor, name, adapter_type, base_url, api_key, is_active |
| `knowledge_bases` | 知识库 | id, name, description, created_at, updated_at |
| `knowledge_docs` | KB 文档 | id, kb_id, filename, sha256, text, created_at |

Schema 变更通过启动时的轻量 `ALTER TABLE` 迁移应用（无 Alembic）。

---

## 开发

### 运行测试

```bash
# 后端
cd backend && uv run pytest -q            # CI 等价：uv run pytest -m "not slow"

# 前端
cd frontend && npm run test && npm run build && npm run lint
```

### 性能验证

```bash
python scripts/seed-1000msgs.py          # 灌入 1000 条消息的会话用于 dev 实测
```

---

## 路线图

完整计划见 [DEVELOPMENT_PLAN.md](./DEVELOPMENT_PLAN.md)，最新进度见 [PROGRESS.md](./PROGRESS.md)。

### 阶段概览

| 阶段 | 状态 | 内容 |
| ---- | ---- | ---- |
| Phase 1 | ✅ 完成 | 后端框架 + 数据库 + 模型适配 + 流式聊天 API |
| Phase 2 | ✅ 完成 | 前端框架 + 会话管理 + 消息展示 + 流式渲染 |
| Phase 3 | ✅ 完成 | 深度思考全链路 |
| Phase 4 | ✅ 完成 | 文件上传 + 模型管理 + 虚拟滚动 |
| 跨平台 + 部署 | ✅ 完成 | Docker + GHA 三平台 matrix + 性能/hook 测试 |
| AgentService 第一期 | ✅ 完成 | ReAct 多轮推理（无工具） |
| AgentService 第二期 2a | ✅ 完成 | LangGraph + 工具调用（Skills → 工具） |
| AgentService 第二期 2b-i | ✅ 完成 | RAG + 知识库管理 |
| AgentService 第二期 2b-ii | ✅ 完成 | AgentTrace 面板 + step-bounded SSE |
| 第三期第一轮 | ✅ 完成 | Markdown 技能 + 联网搜索 + Agent 交错输出 |
| 第三期第二轮 | ✅ 完成 | 技能管理 UI + Tavily 联网搜索 |

### 计划中（第三期第三轮，范围待确认）

- 厂商原生 tool-calling API（OpenAI `tool_calls` delta / Anthropic `tools`）替换 ReAct prompt 注入。
- 异步化文档处理（上传立即返回 doc_id，后台 chunking + embedding）。
- 混合检索（BM25 + 向量 ensemble）。
- PDF / DOCX 的 RAG 放开。

---

## 安全说明

- **单用户设计**：无认证授权，仅限本地 / 内网使用。
- **API Key**：存储在服务端 `.env` 或数据库 `model_configs` 表中，不会暴露给前端（仅返回 `has_api_key`）。
- **技能名校验**：仅允许 `^[a-zA-Z][a-zA-Z0-9_-]*$`（防路径穿越）。
- **数据库**：默认使用本地 SQLite 文件（`workbench.db`），无远程访问。
