# 智能对话工作台开发计划

> 基于 `Requirement.md`（v1.0）制定。本计划按阶段拆分任务，每个任务尽量具体到可执行的下一步动作。

---

## 0. 前提假设与待确认问题

在按本计划执行前，以下问题需要你确认；若未特别说明，我将按“默认方案”推进。

| # | 问题 | 默认方案 | 影响范围 |
|---|------|----------|----------|
| 1 | **是否同时实现前端 + 后端？** | 是，前后端都实现 | 工作量、目录结构 |
| 2 | **会话/消息数据如何持久化？** | 后端用 SQLite + SQLAlchemy（简单、可迁移） | 后端模型设计、API 行为 |
| 3 | **是否需要用户认证/多用户？** | 否，单用户本地/内网使用 | 无 Auth 模块 |
| 4 | **上传文件是否长期保存？** | 仅解析文本后随消息存储，不保留原始文件 | 存储、隐私 |
| 5 | **v1.0 具体支持哪些模型？** | 见下方“模型清单”默认列表 | 适配器、models.json |
| 6 | **是否提供 Docker / Nginx 部署配置？** | 是，提供 `Dockerfile` + `docker-compose.yml` + Nginx 示例 | 部署阶段 |
| 7 | **是否需要单元测试 / E2E 测试？** | 后端写 pytest 单元测试；前端不做 E2E，仅关键 hook 测试 | 工作量 |
| 8 | **项目目录结构？** | 根目录下 `backend/` 与 `frontend/` 并列 | 仓库组织 |

### 默认支持的模型清单（v1.0）

初始由后端启动时自动写入模型注册表，后续可通过 API 动态增删改，**不写死在代码里**。

```json
[
  { "id": "gpt-5.5", "vendor": "openai", "name": "GPT-5.5", "adapter_type": "openai" },
  { "id": "gpt-5.4", "vendor": "openai", "name": "GPT-5.4", "adapter_type": "openai" },
  { "id": "claude-opus-4.8", "vendor": "anthropic", "name": "Claude Opus 4.8", "adapter_type": "anthropic" },
  { "id": "claude-sonnet-5", "vendor": "anthropic", "name": "Claude Sonnet 5", "adapter_type": "anthropic" },
  { "id": "gemini-3.1-pro", "vendor": "gemini", "name": "Gemini 3.1 Pro", "adapter_type": "gemini" },
  { "id": "gemini-3.5-flash", "vendor": "gemini", "name": "Gemini 3.5 Flash", "adapter_type": "gemini" },
  { "id": "deepseek-v4-flash", "vendor": "deepseek", "name": "DeepSeek-V4-Flash", "adapter_type": "openai_compatible" },
  { "id": "deepseek-v4-pro", "vendor": "deepseek", "name": "DeepSeek-V4-Pro", "adapter_type": "openai_compatible" },
  { "id": "kimi-k2.6", "vendor": "kimi", "name": "Kimi K2.6", "adapter_type": "openai_compatible" },
  { "id": "glm-5.2", "vendor": "glm", "name": "GLM-5.2", "adapter_type": "openai_compatible" },
  { "id": "glm-4.7", "vendor": "glm", "name": "GLM-4.7", "adapter_type": "openai_compatible" }
]
```

> 如果你只想先做后端 MVP，或想换用其他前端/数据库方案，请告诉我。

---

## 1. 项目目标与验收标准

### 1.1 目标
交付一个可本地运行的“类 Kimi Workspace”纯文本 AI 对话工作台：
- 前端：React + TypeScript + Vite + shadcn/ui，支持会话管理、流式对话、文件上传、模型切换、思考强度调节。
- 后端：FastAPI 统一代理 OpenAI / Anthropic / OpenAI 兼容厂商，提供 SSE 流式响应。
- 预留 RAG / Skills 扩展点，当前不实现具体逻辑。

### 1.2 验收标准（Definition of Done）
- [ ] 可创建、切换、重命名、删除、搜索会话。
- [ ] 可向至少 3 个不同厂商模型发送文本消息并收到流式回复。
- [ ] 可上传 `.txt`、`.md`、`.pdf`、`.docx` 文件，文本内容作为上下文发送。
- [ ] 思考强度滑块能影响模型调用参数。
- [ ] 消息列表在 1000 条消息下滚动流畅（虚拟滚动生效）。
- [ ] 后端 pytest 测试通过。
- [ ] `docker compose up` 能一键启动前后端。

---

## 2. 项目结构

```
My_Agent/
├── Requirement.md
├── DEVELOPMENT_PLAN.md      # 本文件
├── README.md                # 后续补充：快速开始、环境变量说明
├── docker-compose.yml
├── nginx.conf               # 生产/本地反向代理示例
├── backend/
│   ├── pyproject.toml       # uv 依赖
│   ├── .env.example         # 环境变量模板
│   ├── main.py              # FastAPI 入口
│   ├── Dockerfile
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py        # pydantic-settings
│   │   ├── database.py      # SQLAlchemy 会话/模型基类
│   │   ├── models.py        # Conversation / Message / UploadedFile ORM
│   │   ├── schemas.py       # Pydantic 请求/响应模型
│   │   ├── dependencies.py  # 公共依赖（如 DB session）
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── chat.py
│   │   │   ├── conversations.py
│   │   │   ├── upload.py
│   │   │   ├── models.py
│   │   │   └── skills.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── file_parser.py
│   │   │   └── conversation_service.py
│   │   └── adapters/
│   │       ├── __init__.py
│   │       ├── base.py
│   │       ├── factory.py
│   │       ├── openai_adapter.py
│   │       ├── anthropic_adapter.py
│   │       └── gemini_adapter.py
│   └── tests/
│       ├── test_chat.py
│       ├── test_upload.py
│       └── test_conversations.py
└── frontend/
    ├── package.json
    ├── vite.config.ts
    ├── tsconfig.json
    ├── tailwind.config.js
    ├── components.json        # shadcn/ui
    ├── Dockerfile
    ├── index.html
    ├── src/
    │   ├── main.tsx
    │   ├── App.tsx
    │   ├── api/
    │   │   ├── client.ts
    │   │   ├── chat.ts
    │   │   ├── upload.ts
    │   │   └── models.ts
    │   ├── store/
    │   │   └── workspaceStore.ts   # Zustand
    │   ├── components/
    │   │   ├── WorkspaceLayout.tsx
    │   │   ├── Sidebar.tsx
    │   │   ├── ConversationList.tsx
    │   │   ├── ChatHeader.tsx
    │   │   ├── MessageList.tsx
    │   │   ├── MessageItem.tsx
    │   │   └── InputArea.tsx
    │   ├── hooks/
    │   │   ├── useChatStream.ts
    │   │   └── useConversation.ts
    │   ├── types/
    │   │   └── index.ts
    │   └── lib/
    │       └── utils.ts
    └── tests/
        └── ...
```

---

## 3. 阶段一：项目脚手架（预计 0.5 天）

### 3.1 后端初始化
1. 在 `backend/` 下创建 `pyproject.toml`，使用 `uv` 管理：
   - 核心：`fastapi`, `uvicorn[standard]`, `httpx`, `python-multipart`, `pydantic-settings`
   - 解析：`pdfplumber`, `python-docx`
   - 持久化：`sqlalchemy`, `aiosqlite`
   - 测试：`pytest`, `pytest-asyncio`, `httpx`
2. 创建 `.env.example`，列出所有厂商 API Key 与 Base URL。
3. 创建 `app/config.py`，用 `pydantic-settings` 加载环境变量。
4. 创建 `main.py` 入口，注册 CORS 与 `app` 实例。

### 3.2 前端初始化
1. 用 Vite 创建 React + TypeScript 项目到 `frontend/`。
2. 初始化 Tailwind CSS。
3. 初始化 shadcn/ui（`npx shadcn-ui@latest init`）。
4. 安装依赖：`zustand`, `react-markdown`, `remark-gfm`, `react-syntax-highlighter`, `@tanstack/react-virtual`, `react-dropzone`, `date-fns`, `nanoid`, `lucide-react`。
5. 配置 `vite.config.ts` 代理 `/api` 到 `http://localhost:8000`（开发环境）。

### 3.3 交付物
- `backend/pyproject.toml`、`.env.example`、`main.py`
- `frontend/package.json`、`vite.config.ts`、`tsconfig.json`、`tailwind.config.js`
- 根目录 `docker-compose.yml`（后续再填内容，先占位）

---

## 4. 阶段二：后端核心实现（预计 2 天）

### 4.1 数据库模型（SQLAlchemy）
1. 创建 `app/database.py`：异步 engine、sessionmaker、Base。
2. 创建 `app/models.py`：
   - `Conversation`：`id`, `title`, `created_at`, `updated_at`
   - `Message`：`id`, `conversation_id`, `role`, `content`, `model`, `effort`, `created_at`, `status`（pending/streaming/done/error）
   - `UploadedFile`：`id`, `conversation_id`, `name`, `text_content`, `created_at`
   - `ModelConfig`（新增）：`id`, `model_id`（唯一）, `vendor`, `name`, `adapter_type`, `base_url`（可选，覆盖 vendor 默认）, `is_active`, `created_at`, `updated_at`
3. 在 `main.py` 启动时调用 `create_all()`。
4. 启动时若 `ModelConfig` 表为空，则把初始模型清单 seed 进去。

### 4.2 Pydantic Schemas
1. 创建 `app/schemas.py`：
   - `ChatMessage`, `FileContent`, `ChatRequest`, `ChatResponseChunk`
   - `ConversationCreate`, `ConversationUpdate`, `ConversationOut`
   - `MessageOut`, `UploadedFileOut`

### 4.3 适配器层
1. 创建 `app/adapters/base.py`：抽象基类 `BaseAdapter` + `StreamChunk`。
2. 创建 `app/adapters/openai_adapter.py`：
   - 处理 SSE `data:` 行解析
   - effort 映射到 `temperature` / `top_p`
   - 对推理类模型按需去掉 temperature（由 `ModelConfig.adapter_type` 或模型特征决定）
3. 创建 `app/adapters/anthropic_adapter.py`：
   - 转换 messages、解析 SSE
   - 构造函数接受可选 `base_url`，默认 Anthropic 官方地址
   - 通过传入自定义 `base_url` 即可支持 Anthropic 兼容厂商/私有化部署
4. 创建 `app/adapters/gemini_adapter.py`：REST SSE 调用。
5. 创建 `app/adapters/openai_compatible_adapter.py`：
   - 继承 `OpenAIAdapter`，通过传入 `base_url` + `api_key` 支持任意 OpenAI 兼容厂商
   - 实际与 `OpenAIAdapter` 可复用同一类，但构造函数接收动态 `base_url`
7. 创建 `app/adapters/factory.py`：
   - 查询 `ModelConfig` 表获取模型配置
   - 根据 `adapter_type` 返回对应适配器实例：
     - `openai` → `OpenAIAdapter(settings.openai_api_key, settings.openai_base_url)`
     - `anthropic` → `AnthropicAdapter(settings.anthropic_api_key)`
     - `gemini` → `GeminiAdapter(settings.gemini_api_key)`
     - `openai_compatible` → `OpenAIAdapter(vendor_api_key, vendor_base_url)`
   - `vendor -> (api_key, base_url)` 映射由 `config.py` 维护
   - 若 `ModelConfig` 中 `base_url` 非空，优先使用自定义 base_url
8. **移除 `models.json` 硬编码文件**，初始清单改为启动 seed 逻辑写入数据库。

### 4.4 文件解析服务
1. 创建 `app/services/file_parser.py`：
   - `parse_uploaded_file(filename, bytes)` 分发到 pdf/docx/txt 解析
   - 限制文件大小（如 10MB）
   - PDF 解析失败时返回友好错误

### 4.5 业务服务
1. 创建 `app/services/conversation_service.py`：
   - 创建会话（默认标题“新会话”或首条用户消息前 20 字）
   - 获取会话列表（支持搜索标题）
   - 重命名、删除会话
   - 保存用户消息与助手消息

### 4.6 API 路由
1. `routers/conversations.py`：
   - `GET /api/conversations` 列表 + 搜索参数 `q`
   - `POST /api/conversations` 创建
   - `GET /api/conversations/{id}` 详情（含 messages）
   - `PATCH /api/conversations/{id}` 重命名
   - `DELETE /api/conversations/{id}` 删除
2. `routers/upload.py`：
   - `POST /api/upload`：校验扩展名、解析文本、返回 `{file_id, name, text_content}`
3. `routers/models.py`（升级为动态模型管理）：
   - `GET /api/models`：返回当前启用的模型清单（供前端下拉框使用）
   - `GET /api/models/all`：返回全部模型（含已禁用）
   - `POST /api/models`：新增模型配置
   - `PUT /api/models/{model_id}`：更新模型配置（名称、adapter_type、base_url、is_active 等）
   - `DELETE /api/models/{model_id}`：删除模型配置
   - 请求体/响应体使用 Pydantic schema `ModelConfigCreate`, `ModelConfigUpdate`, `ModelConfigOut`
4. `routers/chat.py`：
   - `POST /api/chat`：接收 `ChatRequest`
   - 若 `conversation_id` 为空则新建会话
   - 保存用户消息到数据库
   - 调用适配器流式生成，SSE 返回 `type=text|done|error`
   - 流结束后保存完整助手消息
   - 若请求中携带 `files`，将文本拼接到最后一条 user 消息
5. `routers/skills.py`：
   - `POST /api/skills/{skill_name}` 返回 `{"status": "not_implemented"}`
6. 在 `main.py` 统一注册 router，加 `/api` 前缀。

### 4.7 错误处理与日志
1. 添加全局异常处理器，返回统一 JSON 错误。
2. 配置 `logging`，记录关键调用与错误。

### 4.8 后端测试
1. `tests/test_conversations.py`：CRUD 测试。
2. `tests/test_upload.py`：上传 txt/pdf 测试。
3. `tests/test_chat.py`：用 `respx` 或 `unittest.mock` mock 适配器，测试 SSE 输出。

---

## 5. 阶段三：前端核心实现（预计 2.5 天）

### 5.1 类型与 API 客户端
1. `src/types/index.ts`：定义 `Conversation`, `Message`, `UploadedFile`, `ModelConfig`。
2. `src/api/client.ts`：封装 `fetch`，处理 JSON 请求。
3. `src/api/chat.ts`：`sendChatStream(params, onChunk, onDone, onError)` 使用 `fetch` + `ReadableStream` 解析 SSE。
4. `src/api/upload.ts`：`uploadFile(file)` FormData 上传。
5. `src/api/models.ts`：
   - `fetchModels()`：供选择框使用
   - `createModel(data)`, `updateModel(modelId, data)`, `deleteModel(modelId)`：模型管理
6. `src/api/conversations.ts`：CRUD。

### 5.2 Zustand Store
1. `src/store/workspaceStore.ts`：
   - 状态：`conversations`, `activeId`, `isStreaming`, `inputText`, `attachedFiles`, `selectedModel`, `effort`, `models`
   - 动作：`setActive`, `createConversation`, `loadConversations`, `renameConversation`, `deleteConversation`, `addMessage`, `appendToAssistant`, `setStreaming`, `setModel`, `setEffort`, `attachFile`, `removeFile`, `loadModels`, `addModel`, `updateModel`, `removeModel`
   - 持久化：会话数据来自后端，不存 localStorage（避免前后端不一致）；仅 `selectedModel`/`effort` 可存 localStorage。

### 5.3 布局组件
1. `WorkspaceLayout.tsx`：左右布局，`Sidebar` + `MainArea`。
2. `Sidebar.tsx`：可拖拽调整宽度（最小 220px，最大 400px）。
3. `SidebarHeader.tsx`：新建会话按钮、搜索输入框。
4. `ConversationList.tsx`：`@tanstack/react-virtual` 虚拟滚动，右键菜单重命名/删除。
5. `ChatHeader.tsx`：当前会话标题、RAG 知识库选择（占位 disabled）、Skills 按钮（占位）。
6. `MessageList.tsx`：虚拟滚动消息列表。
7. `MessageItem.tsx`：用户消息纯文本、助手消息 Markdown + 代码高亮。
8. `InputArea.tsx`：
   - 文件拖拽/点击上传（react-dropzone）
   - 已上传文件标签展示，可删除
   - 模型下拉选择（从 `/api/models` 拉取，支持禁用/启用后刷新）
   - 思考强度滑块（0-1，步长 0.1）
   - 多行文本框（Enter 发送，Shift+Enter 换行）
   - 发送按钮
9. **新增 `ModelManager.tsx`（可选 v1.0 简单版）**：
   - 放在设置弹窗或独立页面
   - 展示模型列表，支持新增/编辑/删除/启用禁用
   - v1.0 先保证后端 API 完整，前端管理 UI 做最小可用版本

### 5.4 自定义 Hooks
1. `useChatStream.ts`：封装 SSE 调用与 store 更新，处理中断（AbortController）。
2. `useConversation.ts`：加载当前会话消息、创建新会话。

### 5.5 细节打磨
1. 空状态：无会话时的引导页。
2. Loading 状态：助手消息显示闪烁光标/骨架屏。
3. 错误提示：toast 或 inline 错误。
4. Markdown 渲染安全：禁用 raw HTML，使用 `remark-gfm`。

---

## 6. 阶段四：集成与测试（预计 1 天）

### 6.1 端到端联调
1. 启动后端 `uvicorn main:app --reload`。
2. 启动前端 `npm run dev`。
3. 用真实 API Key 测试至少 3 个厂商（OpenAI、Anthropic、DeepSeek）。
4. 测试文件上传后的上下文效果。
5. 测试切换模型后继续对话。

### 6.2 性能测试
1. 构造 1000 条消息会话，验证虚拟滚动不卡顿。
2. 测试大文件（5MB PDF）上传与解析时间。

### 6.3 Bug 修复
1. 根据联调结果修复适配器解析、前端状态更新、滚动定位等问题。

---

## 7. 阶段五：部署与文档（预计 0.5 天）

### 7.1 Docker 化
1. 后端 `Dockerfile`：多阶段构建，基于 `python:3.11-slim`，安装 uv，复制依赖与代码。
2. 前端 `Dockerfile`：基于 `node:20-alpine`，build 后复制到 Nginx。
3. 根目录 `docker-compose.yml`：
   - `backend` 服务：端口 8000，挂载 `.env`
   - `frontend` 服务：用 Nginx 容器，反向代理 `/api` 到 backend
4. 提供 `nginx.conf` 示例。

### 7.2 文档
1. `README.md`：
   - 快速开始（开发/生产）
   - 环境变量说明
   - 添加新厂商/模型的步骤
   - 运行测试命令
2. 更新 `DEVELOPMENT_PLAN.md` 状态为完成。

---

## 8. 里程碑与排期（总计约 6.5 天）

| 阶段 | 内容 | 预计工时 | 可交付验证点 |
|------|------|----------|--------------|
| 一 | 前后端脚手架 | 0.5 天 | `npm run dev` / `uvicorn main:app` 能跑通 |
| 二 | 后端核心 | 2 天 | pytest 全绿；Postman 可拉模型列表、CRUD 会话、发 SSE 聊天 |
| 三 | 前端核心 | 2.5 天 | 前端页面可创建会话、发消息、上传文件、切换模型 |
| 四 | 集成测试 | 1 天 | 多厂商真实调用通过；1000 条消息不卡 |
| 五 | 部署文档 | 0.5 天 | `docker compose up` 一键启动 |

---

## 9. 风险与规避

| 风险 | 影响 | 规避措施 |
|------|------|----------|
| 某些厂商 SSE 格式与标准 OpenAI 不完全一致 | 流式解析失败 | 为每个厂商单独测试并做容错解析 |
| 用户通过 API 添加的模型配置错误 | 调用失败 | 新增/更新时校验 adapter_type、base_url 格式；调用失败返回明确错误 |
| PDF 解析质量差（扫描版/复杂排版） | 上下文不准 | 明确只支持文本型 PDF；解析失败返回错误 |
| 大文件导致内存/超时 | 服务崩溃 | 限制 10MB，流式读取，必要时分页 |
| 前端虚拟滚动与动态高度消息冲突 | 滚动跳动 | 用 `@tanstack/react-virtual` + 预估高度 |
| 多厂商 API Key 不全 | 无法联调 | 先用一个 OpenAI 兼容厂商跑通，再逐个加 |

---

## 10. 下一步行动（等你确认后即可开始）

1. 你确认“默认方案”或有修改后，我立刻开始 **阶段一：项目脚手架**。
2. 期间我会按阶段产出代码，并在每个阶段结束时简单汇报进度。
