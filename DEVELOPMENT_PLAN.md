# 智能对话工作台开发计划

> 基于 `Requirement.md`（v1.0）制定。本计划按阶段拆分任务，每个任务尽量具体到可执行的下一步动作。

---

## 0. 前提假设与待确认问题

在按本计划执行前，以下问题需要你确认；若未特别说明，我将按“默认方案”推进。

| # | 问题                                         | 默认方案                                                     | 影响范围               |
| - | -------------------------------------------- | ------------------------------------------------------------ | ---------------------- |
| 1 | **是否同时实现前端 + 后端？**          | 是，前后端都实现                                             | 工作量、目录结构       |
| 2 | **会话/消息数据如何持久化？**          | 后端用 SQLite + SQLAlchemy（简单、可迁移）                   | 后端模型设计、API 行为 |
| 3 | **是否需要用户认证/多用户？**          | 否，单用户本地/内网使用                                      | 无 Auth 模块           |
| 4 | **上传文件是否长期保存？**             | 仅解析文本后随消息存储，不保留原始文件                       | 存储、隐私             |
| 5 | **v1.0 具体支持哪些模型？**            | 见下方“模型清单”默认列表                                   | 适配器、models.json    |
| 6 | **是否提供 Docker / Nginx 部署配置？** | 是，提供`Dockerfile` + `docker-compose.yml` + Nginx 示例 | 部署阶段               |
| 7 | **是否需要单元测试 / E2E 测试？**      | 后端写 pytest 单元测试；前端不做 E2E，仅关键 hook 测试       | 工作量                 |
| 8 | **项目目录结构？**                     | 根目录下`backend/` 与 `frontend/` 并列                   | 仓库组织               |

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
6. 创建 `app/adapters/factory.py`：
   - 查询 `ModelConfig` 表获取模型配置
   - 根据 `adapter_type` 返回对应适配器实例：
     - `openai` → `OpenAIAdapter(settings.openai_api_key, settings.openai_base_url)`
     - `anthropic` → `AnthropicAdapter(settings.anthropic_api_key)`
     - `gemini` → `GeminiAdapter(settings.gemini_api_key)`
     - `openai_compatible` → `OpenAIAdapter(vendor_api_key, vendor_base_url)`
   - `vendor -> (api_key, base_url)` 映射由 `config.py` 维护
   - 若 `ModelConfig` 中 `base_url` 非空，优先使用自定义 base_url
7. **移除 `models.json` 硬编码文件**，初始清单改为启动 seed 逻辑写入数据库。

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

### 7.1 文档

1. `README.md`：
   - 快速开始（开发/生产）
   - 环境变量说明
   - 添加新厂商/模型的步骤
   - 运行测试命令
2. 更新 `DEVELOPMENT_PLAN.md` 状态为完成。

---

## 8. 里程碑与排期（总计约 6.5 天）

| 阶段 | 内容         | 预计工时 | 可交付验证点                                              |
| ---- | ------------ | -------- | --------------------------------------------------------- |
| 一   | 前后端脚手架 | 0.5 天   | `npm run dev` / `uvicorn main:app` 能跑通             |
| 二   | 后端核心     | 2 天     | pytest 全绿；Postman 可拉模型列表、CRUD 会话、发 SSE 聊天 |
| 三   | 前端核心     | 2.5 天   | 前端页面可创建会话、发消息、上传文件、切换模型            |
| 四   | 集成测试     | 1 天     | 多厂商真实调用通过；1000 条消息不卡                       |

---

## 9. 风险与规避

| 风险                                      | 影响         | 规避措施                                                          |
| ----------------------------------------- | ------------ | ----------------------------------------------------------------- |
| 某些厂商 SSE 格式与标准 OpenAI 不完全一致 | 流式解析失败 | 为每个厂商单独测试并做容错解析                                    |
| 用户通过 API 添加的模型配置错误           | 调用失败     | 新增/更新时校验 adapter_type、base_url 格式；调用失败返回明确错误 |
| PDF 解析质量差（扫描版/复杂排版）         | 上下文不准   | 明确只支持文本型 PDF；解析失败返回错误                            |
| 大文件导致内存/超时                       | 服务崩溃     | 限制 10MB，流式读取，必要时分页                                   |
| 前端虚拟滚动与动态高度消息冲突            | 滚动跳动     | 用`@tanstack/react-virtual` + 预估高度                          |
| 多厂商 API Key 不全                       | 无法联调     | 先用一个 OpenAI 兼容厂商跑通，再逐个加                            |

## 10. 目前状态

| 阶段                                                            | 状态                   | 说明                                                                                                                                                                                                                         |
| --------------------------------------------------------------- | ---------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 阶段一~五（脚手架 / 后端核心 / 前端核心 / 集成测试 / 部署文档） | ✅ 完成                | v1.0 验收条件全部满足，见 README 与 PROGRESS 一~九节                                                                                                                                                                         |
| 跨平台兼容 + 部署交付物 + 性能测试 + Skills 挂载                | ✅ 完成                | docker-compose 与 GHA 三平台 matrix 落地，详见 PROGRESS 第十二节                                                                                                                                                             |
| AgentService 第一期（多轮推理 / ReAct 无工具）                  | ✅ 完成                | `POST /api/agent-chat` 落地，详见 PROGRESS 第十三节                                                                                                                                                                        |
| AgentService 第二期 2a（LangChain + Tool Calling，不含 RAG）    | ✅ 完成                | Skill 经`StructuredTool` 包装接入；前端 Agent toggle；`Message.metadata` JSON 列持久化 step_count/aborted/tool_calls。详见 PROGRESS 第十四节                                                                             |
| AgentService 第二期 2b-i（RAG + 知识库管理）                    | ✅ 完成                | 本地 bge-small-zh + chromadb；KB CRUD + 文档上传/分块/检索；retrieve_notes 工厂 skill；普通 chat 静默注入、Agent 模式 ReAct 自主调用。后端 89 测试 / 前端 15 测试全过。Docker torch 烘焙 + CI 留尾巴。详见 PROGRESS 第十五节 |
| AgentService 第二期 2b-ii（AgentTrace 面板）                    | ⏳ 计划已落地，见 11.5 | 2b-i 完成后开工                                                                                                                                                                                                              |

---

## 11. 未来开发计划

### 11.1 跨平台兼容性检查 — ✅ 完成（2026-07-20）

- 检查 Windows 平台 npm 包缺失问题（如 `@rollup/rollup-darwin-arm64` 等平台特定二进制）
- 解决 Linux 平台无法下载依赖的问题（如 uv 安装、系统库缺失等）
- 补充 CI 配置（如 GitHub Actions）做多平台验证
- 落地：根 `.gitignore` + `frontend/.npmrc` + `pyproject.toml` `uvicorn[standard]` 拆 optional dep + `.github/workflows/ci.yml` 三平台 matrix。

### 11.2 新增 AgentService 编排层 — ✅ 完成（AgentService 第一期，2026-07-20）

- **保持现有架构不变**：Adapter、ConversationService、Streaming 架构不动
- 新增 `AgentService` 作为 Agent 编排层，**不让 LangChain 接管整个后端**
- AgentService 位于 `backend/app/services/agent_service.py`，与 ConversationService 平级
- 职责：接收用户意图 → 编排 Agent 执行流程 → 调用 Adapter 完成 LLM 调用 → 返回结果
- 落地：纯文本 ReAct 循环，无工具调用，详见 PROGRESS 第十三节。

### 11.3 AgentService 第二期 2a：LangChain + Tool Calling — ✅ 完成（2026-07-20）

- 在 AgentService 内部引入 LangChain/LangGraph，不污染外部架构
  - 新增 `backend/app/services/langchain_adapter.py`：`AdapterChatModel(BaseChatModel)` 桥到现有 BaseAdapter，ModelConfig/vendor key 仍是唯一入口
  - Skills 经 `_wrap_skill_as_tool` 包成 `StructuredTool` 暴露给 agent；`skills/base.py` 不感知 LangChain
  - 工具调用走 ReAct prompt 注入（不依赖厂商 native tool_calls API）
- 负责：工具调用（Tool Calling 部分）；RAG 推迟到 2b。
- 落地：`Message.metadata` JSON 列；ChatChunk 加 `action`/`observation`/`warning` 类型；前端 InputArea 加 Agent toggle；详见 PROGRESS 第十四节。

### 11.4 AgentService 第二期 2b-i：RAG + 知识库管理（计划已定，待开工）

**目标**：在已有的 Skills + Tool Calling 框架之上，引入向量检索与知识库管理，让 Agent 能在多步推理中主动查询用户上传的 markdown 笔记；普通 chat 模式也能把 KB 命中段落自动注入上下文。本期不涉及 AgentTrace 面板（留 2b-ii）。

**取舍已拍板**（详见第十五节执行记录时再展开）：

| 决策点          | 选定方案                                                                                                |
| --------------- | ------------------------------------------------------------------------------------------------------- |
| 向量库          | `chromadb`（Python-native、磁盘持久化、跨平台一致）                                                   |
| Embedding       | 本地`sentence-transformers` + `BAAI/bge-small-zh-v1.5`（512 维、中文笔记表现好、零网络成本）        |
| Chunking        | `MarkdownHeaderTextSplitter` → `RecursiveCharacterTextSplitter`（chunk_size=800、overlap=100）兜底 |
| KB 元数据持久化 | SQLAlchemy 表`KnowledgeBase`/`KnowledgeDoc` + chromadb 纯向量索引，两轨并存                         |
| KB UI           | `KnowledgeBaseManager` Modal（仿 `ModelManager` 风格）+ ChatHeader KB 下拉 select                   |
| 上传格式        | 仅`.md/.markdown/.txt`（与 PROGRESS"markdown 笔记检索"对齐，避免 PDF 噪声）                           |
| RAG 触发        | 普通 chat 自动注入；Agent 模式经`retrieve_notes` Skill 由 ReAct 自主调用                              |
| 检索算法        | 纯向量 top-K（无 BM25 hybrid，留实战验证再加）                                                          |
| 处理模型        | 同步处理（本地工作台、单 KB 上传通常 < 5s）；异步化留 2b-ii                                             |
| 测试            | 单测 fake embedder；`@pytest.mark.slow` 标真模型 smoke，CI skip                                       |

#### 11.4.1 后端文件清单

| 类型 | 路径                                           | 说明                                                                                                                                                             |
| ---- | ---------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 改   | `backend/pyproject.toml`                     | 加`chromadb>=0.5`、`langchain-chroma>=0.1`、`sentence-transformers>=2.7`、`rank-bm25`（先不加，留 2b-ii 视情况）                                         |
| 改   | `backend/app/config.py` + `.env.example`   | 加`embedding_model`、`chroma_persist_dir`、`kb_chunk_size`、`kb_chunk_overlap`、`kb_top_k`、`kb_min_score`                                           |
| 改   | `backend/app/models.py`                      | 加`KnowledgeBase`（id/name/description/created_at/updated_at）与 `KnowledgeDoc`（id/kb_id/filename/sha256/text/created_at）表                                |
| 改   | `backend/main.py` + `tests/conftest.py`    | 启动时`create_all` 创建新表；lifespan 启动 `ChromaService` 单例                                                                                              |
| 新   | `backend/app/services/knowledge_service.py`  | KnowledgeService：KB/doc CRUD、上传文本 → chunking → embedding → chromadb upsert；查询`retrieve(kb_id, query, top_k, min_score)`                            |
| 新   | `backend/app/services/embedding_service.py`  | EmbeddingService：本地`bge-small-zh-v1.5` 单例 + fake fallback（注入零向量，仅测试）                                                                           |
| 新   | `backend/app/skills/retrieve_notes.py`       | `RetrieveNotesSkill`：`run(input, args={"kb_id": "...", "top_k": 4, "min_score": 0.3})`；通过 `KnowledgeService.retrieve` 返回拼接好的 markdown chunks     |
| 改   | `backend/app/skills/registry.py`             | 注册`retrieve_notes`，但**它依赖 request 上下文的 `kb_id`** —— 改造为工厂：`get_retrieve_notes_tool(kb_id)` 由 AgentService 在每次调用时构造       |
| 改   | `backend/app/services/agent_service.py`      | 收到`request.rag_knowledge_base_id` 时把 `retrieve_notes` Skill 的 `kb_id` 通过闭包绑定暴露；其它 step 流程不变                                            |
| 改   | `backend/app/routers/chat.py`                | 若`request.rag_knowledge_base_id` 非空：发模型前用 `KnowledgeService.retrieve` 取 top-K，拼到最近一条 user 消息前. **作为新增 chunk 段而非替换原内容** |
| 改   | `backend/app/routers/agent.py`               | 在调用 AgentService 前按`request.rag_knowledge_base_id` 准备 `retrieve_notes` Skill 工具列表                                                                 |
| 新   | `backend/app/routers/knowledge.py`           | `GET/POST/DELETE /api/knowledge-bases`、`POST /api/knowledge-bases/{id}/documents`（multipart上传）、`GET …/documents`、`DELETE …/documents/{doc_id}`  |
| 改   | `backend/app/schemas.py`                     | `KnowledgeBase*` scheme、text 列表与上传响应                                                                                                                   |
| 新   | `backend/tests/test_knowledge_service.py`    | fake embedder 覆盖：KB CRUD、上传 md → chunk 入 chromadb、retrieve top-K、删除 KB 联级清理                                                                      |
| 新   | `backend/tests/test_retrieve_notes_skill.py` | 注入 fake KB + fake retrieval 验证 Skill 输出格式                                                                                                                |
| 新   | `backend/tests/test_routers_knowledge.py`    | API 端到端                                                                                                                                                       |

#### 11.4.2 前端文件清单

| 类型 | 路径                                                        | 说明                                                                                                        |
| ---- | ----------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| 改   | `frontend/src/types/index.ts`                             | 新增`KnowledgeBase`、`KnowledgeDoc` 接口；`ChatRequest.ragKnowledgeBaseId` 已存在不改动               |
| 新   | `frontend/src/api/knowledge.ts`                           | `fetchKnowledgeBases/createKnowledgeBase/deleteKnowledgeBase/uploadDocument/listDocuments/deleteDocument` |
| 改   | `frontend/src/store/workspaceStore.ts`                    | 新增`selectedKbId`、`setSelectedKbId`；persist version 升到 5                                           |
| 新   | `frontend/src/components/KnowledgeBaseManager.tsx`        | 仿`ModelManager.tsx` 风格的 Modal：KB 列表 + 创建表单 + 进入 KB 后的文档列表 + 上传/删除                  |
| 改   | `frontend/src/components/ChatHeader.tsx`                  | 「知识库」按钮变为打开`KnowledgeBaseManager`；新增 KB 下拉 `<select>`（无 KB 时 disabled "--无--"）     |
| 改   | `frontend/src/hooks/useChatStream.ts`                     | 发送 chat 与 agent-chat 时附带`ragKnowledgeBaseId: store.selectedKbId`                                    |
| 改   | `frontend/src/api/agent-chat.ts` + `chat.ts`            | 已传`rag_knowledge_base_id`，无需改动（仅类型对齐）                                                       |
| 新   | `frontend/tests/components/KnowledgeBaseManager.test.tsx` | mock API：列表渲染、创建、上传文档、删除确认                                                                |
| 改   | `frontend/tests/hooks/useChatStream.test.ts`              | 加 1 用例：选 KB 后 fetch body 含`rag_knowledge_base_id`                                                  |

#### 11.4.3 SSE / 协议变化

- 普通 chat：当 KB 生效时**不发新 SSE 事件**——只是后端把 retrieved chunks 静默拼到 user 消息。
- Agent 模式：`action` 事件已经有 `name` 字段；`retrieve_notes` 被调用时照常走 action/observation 事件，observation 内容是 retrieved chunks 的 markdown 摘要（每块标 `[来源: doc.md #heading]`）。

#### 11.4.4 DB 迁移策略

- 新表通过 `Base.metadata.create_all` 自动创建（与现有 tables 一致）。
- 不引入 alembic：项目仍走"启动迁移 + ALTER TABLE 兼容旧库"路线。
- 出厂首启：`workbench.db` 与 `chroma_persist_dir`（默认 `backend/.chroma`）都是首次运行时创建。

#### 11.4.5 Docker 镜像影响

- backend Dockerfile 需在 `uv sync` 后追加：
  - `RUN uv pip install sentence-transformers` 安装 torch（约 +400MB）
  - `RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-zh-v1.5')"` 拉模型到镜像内（避免首次启动下载等待）。
- 用户首次启动本地 dev 时若未装模型，`EmbeddingService` 会捕获 `OSError` 走 FakeEmbedder 并记录 warning 日志——保证 RAG 在没网络/没装 torch 时不至于让后端起不来。

#### 11.4.6 测试边界

- **单元**：fake embedder 全覆盖 KB/doc CRUD 与 retrieve；不依赖真模型。
- **slow**：`@pytest.mark.slow` + `pytest.ini` 注册 marker；CI 不跑；本地 `pytest -m slow` 手动验证 bge-small-zh 真实检索效果。
- **前端**：vitest + RTL mock fetch 覆盖 Modal CRUD 与上传；不依赖 EffectsLibrary。

#### 11.4.7 验证清单

- `cd backend && uv sync --frozen --all-extras` 全过；`uv run pytest -q` → 51 + ~8 新增 = ~59 全过。
- `cd frontend && npm run test && npm run build && npm run lint` 全过。
- 手动：创建 KB「我的笔记」→ 上传 `notes.md` → ChatHeader 下拉选「我的笔记」→ 普通 chat 问笔记内容 → 验证回复引用；切换 Agent 模式 → 验证 `retrieve_notes` 工具被 agent 自主调用（trace 里出 `Action: retrieve_notes`）。

### 11.5 AgentService 第二期 2b-ii：AgentTrace 面板（计划已定，2b-i 完成后开工）

**目标**：把当前 ReAct 多步思考 + Action + Observation 直接堆在 `Message.thinking` 字段、复用 `ThinkingBlock` 渲染的简陋做法，升级为独立的 `<AgentTrace>` 组件——按 step 卡片化展示 thought / action / observation 三段，为后续检索结果（retrieved chunks）留展示槽位。同时把 SSE 协议从"扁平事件流"升级为"step-bounded 事件流"，让前端能按 step 渲染而非靠 `--- 第 N 步思考 ---` 文本分隔。

**前提**：2b-i 完成后开工，可独立提交。

#### 11.5.1 SSE 协议升级（向后兼容）

新增三类事件，**保留** phase 2a 的扁平事件作为 fallback：

| 事件           | 形态                                                               | 用途                                                                                                                   |
| -------------- | ------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------- |
| `step_start` | `{type:"step_start", step:N, label:"第 N 步思考"}`               | 前端插入新 step 卡片                                                                                                   |
| `step_end`   | `{type:"step_end", step:N, finish:"final\|tool\|max_steps\|error"}` | 前端标记卡片终止状态                                                                                                   |
| `retrieved`  | `{type:"retrieved", step:N, docs:[{doc,heading,score,text}]}`    | 当 retrieved_notes 被调用时透传 top-K 块的元信息，2b-i 已隐式可拿（在 observation 里），这里改为结构化字段方便面板渲染 |

`ChatChunk.type` 扩成 `Literal[..., "step_start", "step_end", "retrieved"]`。后端 `AgentService` 按 step boundary 显式 yield `step_start`/`step_end`，扁平的 `text`/`thinking`/`action`/`observation` 事件保留 `step` 字段，便于旧版前端继续工作。

#### 11.5.2 后端改造

| 类型 | 路径                                       | 说明                                                                                                                                                                                                         |
| ---- | ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 改   | `backend/app/services/agent_service.py`  | 在每个 step 循环开始/结束 yield`step_start`/`step_end`；retrieve_notes 调用时把 chunks 同步 yield `retrieved` 事件；`Metadata.tool_calls` 增加结构化 `observation.shape = "markdown_retrieval"` 等 |
| 改   | `backend/app/skills/retrieve_notes.py`   | `SkillResult.metadata` 增加 `chunks: [{doc, heading, score, text}]` 结构化字段                                                                                                                           |
| 改   | `backend/app/schemas.py`                 | `ChatChunk.type` 扩 `step_start`/`step_end`/`retrieved`；新增 `ChatChunk.docs` 字段                                                                                                                |
| 改   | `backend/tests/test_agent_service_v2.py` | 加 4 个用例：step_start/end 在每个 step 收到一次、retrieved 事件携带 chunks、扁平事件保留向后兼容、abort 后有 step_end                                                                                       |

#### 11.5.3 前端改造

| 类型 | 路径                                              | 说明                                                                                                                                                                                               |
| ---- | ------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 新   | `frontend/src/components/AgentTrace.tsx`        | 接收 step events 数组，渲染卡片列表：每卡片 Header（`第 N 步`徽标 + finish badge）+ Body（thought 区折叠 / action 区显示 tool 名 + input / observation 区显示 retrieved_chunks 列表 + 兜底文本） |
| 改   | `frontend/src/types/index.ts`                   | `ChatChunk` 加 `step_start`/`step_end`/`retrieved` 类型；新增 `AgentStep`、`AgentTraceData` 类型                                                                                       |
| 改   | `frontend/src/api/agent-chat.ts`                | 回调接口补`onStepStart`/`onStepEnd`/`onRetrieved`                                                                                                                                            |
| 改   | `frontend/src/hooks/useChatStream.ts`           | agent 模式收到 step events 时累积进`assistant.metadata.steps` 而非 thinking 字段；`Message.thinking` 兜底只走扁平回退                                                                          |
| 改   | `frontend/src/store/workspaceStore.ts`          | `appendToAssistantThinking` 保留但 agent 模式优先走新 action `appendAgentStep` / `completeAgentStep`                                                                                         |
| 改   | `frontend/src/components/MessageItem.tsx`       | assistant 消息 + agent 模式 → 渲染`<AgentTrace steps={message.metadata.steps}>` 替代 `<ThinkingBlock>`；普通 chat 仍用 ThinkingBlock                                                          |
| 改   | `frontend/src/api/chat.ts`                      | 普通 chat 路径不变；KB 注入仍只影响 user 消息文本                                                                                                                                                  |
| 新   | `frontend/tests/components/AgentTrace.test.tsx` | 渲染 step_start/action/observation/retrieved/end 卡片全 case                                                                                                                                       |
| 改   | `frontend/tests/hooks/useChatStream.test.ts`    | 加 3 个用例：step_start/end 分发、retrieved chunks 入 metadata.steps、abort 后 step_end 状态值                                                                                                     |

#### 11.5.4 数据模型兼容

- `Message.metadata_` JSON 列已存在；2b-ii 仅扩 `metadata_.steps: AgentStep[]` 数组结构。
- 2a 数据（`metadata_.tool_calls`、`step_count`）依然可读；前端可从 `metadata_.steps` 优先读取，旧数据兜底用 `metadata_.tool_calls + thinking` 字段拼回。

#### 11.5.5 向后兼容策略

- 后端同时发扁平 + 结构化事件（feature flag by `settings.agent_structured_events`？还是无脑同时发？）—— 推荐**无脑同时发**：扁平事件保留 `step:N` 字段，结构化事件额外追加；旧前端忽略新事件不破。
- 前端优先走结构化事件渲染 `<AgentTrace>`；当用户的 `Message.metadata_.steps` 为空时回退到现 ThinkingBlock 渲染（兼容历史 DB 行）。

#### 11.5.6 验证清单

- `cd backend && uv run pytest -q` → 在 2b-i 后总数再加 ~4 新增用例。
- `cd frontend && npm run test && npm run build && npm run lint` 全过。
- 手动：Agent 模式下连发多个 Action 步骤，UI 展示卡片化轨迹；retrieved chunks 渲染为「来源：doc.md #heading」可折叠卡片。

### 11.6 Agent 模式限制

- Agent 模式下强制 Thinking，不可关闭 Thinking。

### 11.7 第三期前瞻（不在本期范围）

- 厂商原生 tool-calling API 接入（OpenAI `tool_calls` delta、Anthropic `tools` 参数）：替换 ReAct prompt 注入。
- 异步化文档处理（上传文档后立即返回 doc_id，后台 chunking embedding）。
- 混合检索（BM25 + 向量 ensemble）。
- 知识库 RAG over PDF/DOCX 放开。
- 完善 skills 模块，支持以 .md 文件形式导入技能。
