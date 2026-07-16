# AI Chat Workbench

智能对话工作台（类 Kimi Workspace），前后端分离实现，支持多厂商大模型统一接入与流式对话。

---

## 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (React 19 + Vite + Tailwind CSS v4)               │
│  ┌───────────┐ ┌──────────────────────────────────────────┐ │
│  │  Sidebar  │ │  Workspace                               │ │
│  │           │ │  ┌──────────────────────────────────┐    │ │
│  │ Chat List │ │  │ ChatHeader (模型选择 + 思考开关)    │    │ │
│  │Search Box │ │  ├──────────────────────────────────┤    │ │
│  │ New Chat  │ │  │ MessageList (scroll)             │    │ │
│  │           │ │  │ ┌──────────────────────────────┐ │    │ │
│  │           │ │  │ │ MessageItem                  │ │    │ │
│  │           │ │  │ │ ├ Markdown Render            │ │    │ │
│  │           │ │  │ │ ├ Code Highlight             │ │    │ │
│  │           │ │  │ │ └ ThinkingBlock (collapsible)│ │    │ │
│  │           │ │  │ └──────────────────────────────┘ │    │ │
│  │           │ │  ├──────────────────────────────────┤    │ │
│  │           │ │  │ InputArea (输入 + 文件上传 + 发送). │    │ │
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

## 技术栈

### 前端

| 类别 | 技术 | 用途 |
|------|------|------|
| 框架 | React 19 | UI 构建 |
| 语言 | TypeScript ~6.0 | 类型安全 |
| 构建 | Vite 8 | 开发/构建 |
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
|------|------|------|
| 框架 | FastAPI (≥0.115) | Web 服务 |
| 运行时 | Uvicorn | ASGI 服务器 |
| ORM | SQLAlchemy 2.0 (async) | 数据库操作 |
| 数据库 | SQLite + aiosqlite | 持久化存储 |
| 校验 | Pydantic v2 + pydantic-settings | 请求校验 + 配置管理 |
| HTTP | httpx | 调用 LLM API |
| PDF | pdfplumber | PDF 文件解析 |
| DOCX | python-docx | Word 文件解析 |

---

## 功能特性

### 多厂商模型适配

- **原生适配器**：OpenAI / Anthropic / Gemini 各自独立实现
- **兼容适配器**：DeepSeek、GLM、Kimi 走 OpenAI 兼容协议
- **统一接口**：适配器模式（Strategy Pattern），上层无感知切换
- **可管理**：运行时动态增删改模型配置，每个模型可独立配置 API Key 和 Base URL

### 流式对话

- 基于 SSE（Server-Sent Events）的逐 token 流式输出
- 前端实时渲染，支持中止发送（AbortController）
- 消息状态管理：pending → streaming → done / error

### 深度思考（Thinking）

- 输入区一键开关思考模式
- 开启后模型正式回答前流式输出思考过程
- 思考内容以可折叠区块呈现，与回复正文在字体大小和颜色上有区分
- 流式时自动展开、正文开始后自动折叠，也可手动切换
- 思考内容持久化到 SQLite，刷新或重开会话后仍可见
- 生效范围：
  - **Anthropic**：原生 extended thinking（`thinking_delta` 事件）
  - **OpenAI 兼容厂商**（DeepSeek / GLM / Kimi）：解析 `reasoning_content` 字段
  - **Gemini**：暂不支持

### 会话管理

- 多会话并行，侧边栏列表展示
- 会话标题自动从首条用户消息生成
- 搜索过滤（后端 ILIKE 模糊匹配）
- 重命名 / 删除会话

### 文件上传

- 支持的格式：`.txt` / `.md` / `.json` / `.yaml` / `.xml` / `.html` / `.css` / `.js` / `.ts` / `.py` / `.java` / `.c` / `.cpp` / `.go` / `.rs` 等代码文件 + `.pdf` + `.docx`
- 文件内容解析为文本后随对话上下文发送
- 拖拽上传（react-dropzone）

### 模型管理

- 预置 11 个默认模型（GPT-5.5 / GPT-5.4 / Claude Opus 4.8 / Claude Sonnet 5 / Gemini 3.1 Pro / Gemini 3.5 Flash / DeepSeek-V4-Flash / DeepSeek-V4-Pro / Kimi K2.6 / GLM-5.2 / GLM-4.7）
- 运行时增删改模型
- 每个模型可独立配置 adapter 类型、Base URL、API Key
- API Key 前端不可读（仅返回 `has_api_key` 布尔值）

### 虚拟滚动

- 使用 `@tanstack/react-virtual` 实现消息列表虚拟化
- 大量消息下保持高性能

---

## 快速开始

### 环境要求

- Python ≥ 3.12（推荐使用 [uv](https://docs.astral.sh/uv/)）
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
# 编辑 .env 填入你的 API Key
# DeepSeek, GLM, Kimi 请填写对应的 OpenAI 兼容 BaseURL
uv sync
uv run uvicorn main:app --reload
```

后端默认运行在 **http://localhost:8000**

Swagger 文档：http://localhost:8000/docs

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端默认运行在 **http://localhost:5173**，Vite 已配置代理 `/api` → `http://localhost:8000`。

### Docker 部署（实验性）

```bash
docker-compose up
```

---

## API 文档

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 健康检查 |
| `GET` | `/api/conversations?q=` | 列出会话（可选搜索） |
| `POST` | `/api/conversations` | 创建会话 |
| `GET` | `/api/conversations/{id}` | 获取会话详情（含消息） |
| `PATCH` | `/api/conversations/{id}` | 重命名会话 |
| `DELETE` | `/api/conversations/{id}` | 删除会话 |
| `POST` | `/api/chat` | 发送消息（SSE 流式响应） |
| `POST` | `/api/upload` | 上传文件 |
| `GET` | `/api/models` | 列出活跃模型 |
| `GET` | `/api/models/all` | 列出所有模型 |
| `POST` | `/api/models` | 创建模型 |
| `PUT` | `/api/models/{id}` | 更新模型 |
| `DELETE` | `/api/models/{id}` | 删除模型 |
| `GET` | `/api/skills` | 列出技能（预留） |
| `POST` | `/api/skills/{name}` | 调用技能（预留） |

### 流式聊天请求体 (`POST /api/chat`)

```json
{
  "conversation_id": "uuid-or-null",
  "model": "deepseek-v4-flash",
  "messages": [
    { "role": "user", "content": "你好" }
  ],
  "files": [],
  "stream": true,
  "thinking": true
}
```

SSE 响应格式：

```
data: {"type":"thinking","content":"思考过程..."}
data: {"type":"text","content":"回答内容..."}
data: {"type":"done","message":{"id":"...","content":"...","thinking":"..."}}
```

---

## 项目结构

```
My_Agent/
├── backend/                     # Python 后端
│   ├── main.py                  # FastAPI 入口
│   ├── pyproject.toml           # 依赖管理
│   ├── .env.example             # 环境变量模板
│   └── app/
│       ├── config.py            # pydantic-settings 配置
│       ├── database.py          # SQLAlchemy 异步引擎
│       ├── models.py            # ORM 模型（Conversation, Message, ModelConfig, UploadedFile）
│       ├── schemas.py           # Pydantic 请求/响应模型
│       ├── dependencies.py      # FastAPI 依赖注入
│       ├── seed.py              # 默认模型播种
│       ├── adapters/            # LLM 适配器（策略模式）
│       │   ├── base.py          # 抽象基类 BaseAdapter + StreamChunk
│       │   ├── factory.py       # 适配器工厂
│       │   ├── openai_adapter.py
│       │   ├── anthropic_adapter.py
│       │   └── gemini_adapter.py
│       ├── routers/             # API 路由
│       │   ├── chat.py
│       │   ├── conversations.py
│       │   ├── models.py
│       │   ├── upload.py
│       │   └── skills.py
│       └── services/
│           ├── conversation_service.py
│           └── file_parser.py
├── frontend/                    # React 前端
│   ├── index.html
│   ├── vite.config.ts
│   ├── package.json
│   └── src/
│       ├── main.tsx             # React 入口
│       ├── App.tsx              # 根组件
│       ├── types/index.ts       # TypeScript 类型定义
│       ├── api/                 # API 客户端层
│       │   ├── client.ts        # 基础 fetch（snake_case ←→ camelCase）
│       │   ├── chat.ts          # SSE 流式聊天
│       │   ├── conversations.ts
│       │   ├── models.ts
│       │   └── upload.ts
│       ├── components/          # UI 组件
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
│       │   └── ui/              # shadcn/ui 原语
│       ├── hooks/
│       │   ├── useChatStream.ts
│       │   └── useConversation.ts
│       ├── store/
│       │   ├── workspaceStore.ts # Zustand 全局状态
│       │   └── toastStore.ts
│       └── lib/
│           ├── case.ts          # 命名风格转换
│           └── utils.ts         # cn() 工具函数
├── docker-compose.yml
├── REQUIREMENT.md               # 需求文档
├── DEVELOPMENT_PLAN.md          # 开发计划
└── PROGRESS.md                  # 进度跟踪
```

---

## 数据库模型

| 表 | 说明 | 关键字段 |
|----|------|----------|
| `conversations` | 会话 | id, title, created_at, updated_at |
| `messages` | 消息 | id, conversation_id, role, content, thinking, model, status |
| `uploaded_files` | 上传文件 | id, conversation_id, name, text_content |
| `model_configs` | 模型配置 | id, model_id, vendor, name, adapter_type, base_url, api_key, is_active |

---

## 开发计划

详见 [DEVELOPMENT_PLAN.md](./DEVELOPMENT_PLAN.md)。

### 阶段概览

| 阶段 | 状态 | 内容 |
|------|------|------|
| Phase 1 | ✅ 完成 | 后端框架 + 数据库 + 模型适配 + 流式聊天 API |
| Phase 2 | ✅ 完成 | 前端框架 + 会话管理 + 消息展示 + 流式渲染 |
| Phase 3 | ✅ 完成 | 深度思考（Thinking）全链路 |
| Phase 4 | ✅ 完成 | 文件上传 + 模型管理 + 虚拟滚动 |
| Phase 5 | ⏳ 未开始 | Docker 部署 + 配置优化 |

当前进度详见 [PROGRESS.md](./PROGRESS.md)。

---

## 安全说明

- **单用户设计**：无认证授权，仅限本地 / 内网使用
- **API Key**：存储在服务端 `.env` 或数据库 `model_configs` 表中，不会暴露给前端
- **数据库**：默认使用本地 SQLite 文件（`workbench.db`），无远程访问
