# 项目进度跟踪

> 最后更新：2026-07-20（AgentService phase 2a）

## 一、总体状态

| 模块                                             | 状态      | 说明                                                                                                   |
| ------------------------------------------------ | --------- | ------------------------------------------------------------------------------------------------------ |
| 后端框架（FastAPI + SQLAlchemy async）           | ✅ 完成   | 路由、模型、会话服务、适配器层均已搭建                                                                 |
| 前端框架（React + Zustand + Vite）               | ✅ 完成   | 布局、侧边栏、聊天区、输入区、状态管理                                                                 |
| 模型列表拉取                                     | ✅ 可用   | `/api/models` 从 DB 读取 seed 模型                                                                   |
| 多 vendor 适配器（OpenAI/Anthropic/Gemini/兼容） | ✅ 完成   | OpenAI 兼容流式已实测打通（DeepSeek 200）                                                              |
| 单轮对话（流式）                                 | ✅ 可用   | 选有 key 的模型（DeepSeek/Kimi）可正常对话                                                             |
| 连续对话（多轮）                                 | ✅ 已修复 | 每轮创建独立 assistant 占位；流结束兜底复位；`abort` 已接到 UI                                       |
| 文件上传与发送                                   | ✅ 已修复 | 支持 txt/md/pdf/docx 及常见代码文件；字段映射已修复                                                    |
| 消息列表渲染（无重叠）                           | ✅ 已修复 | 虚拟列表加`measureElement` 动态测高，流式增长不再重叠                                                |
| 会话右键菜单 + 删除确认                          | ✅ 已修复 | 右键 / ⋯ 按钮双入口；删除前确认弹窗                                                                   |
| 开始界面直接发送自动建会话                       | ✅ 已修复 | 空状态下发送自动`createConversation` 再发送                                                          |
| 模型管理 UI（CRUD）                              | ✅ 已完成 | ChatHeader 入口 → Modal 弹窗，含列表/启停/新增/编辑/删除                                              |
| 模型级 API Key                                   | ✅ 已完成 | ModelConfig 加 api_key 字段；compatible 模型可填 key，factory 优先用模型 key 回退 .env；key 不回传明文 |
| 会话标题自动生成                                 | ✅ 已实现 | 后端 service 层按首条消息前 50 字生成（已验证）                                                        |
| 凭证/环境配置                                    | ✅ 已修复 | 见[已完成的修复](#三已完成的修复)                                                                       |

---

## 二、当前阻塞问题

### 问题 1：无法连续对话

**现象**：发完一条消息后，发送按钮常处于禁用状态，无法继续发送第二条。

**根因**：前端流式状态 `isStreaming` 缺少"流结束"兜底复位逻辑。

- 发送按钮的禁用条件是 `disabled={!text.trim() || isStreaming}`（[InputArea.tsx:167](frontend/src/components/InputArea.tsx#L167)）。
- `isStreaming` 只在三处被复位为 `false`：`onDone`、`onError`（[useChatStream.ts:60-69](frontend/src/hooks/useChatStream.ts#L60-L69)）。
- 但 `sendChatStream`（[chat.ts:48-81](frontend/src/api/chat.ts#L48-L81)）在 `reader.read()` 返回 `done:true`（流自然关闭）时直接 `return`，**没有任何兜底回调**。
- 因此一旦后端的 `{type:'done'}` 事件丢失或 `finishReason` 为空导致 `onDone` 未触发（已确认正常路径会触发，但异常/边界路径不会），`isStreaming` 永久为 `true` → 发送按钮永久禁用。

**实测结论**：DeepSeek 正常路径下会发出 `finish_reason='stop'`，后端会 yield `done` 事件，`onDone` 会触发复位——所以"正常情况"能连续对话。问题出现在：

- 选了 `.env` 里没配 key 的模型（GLM/OpenAI/Claude/Gemini）→ 后端 yield `{type:'error'}`，理论上 `onError` 会复位，但若 error 事件格式异常也会漏；
- 流中途网络中断 / 后端异常关闭但未发 done 或 error 事件 → **死锁**。

**修复方向**（未实施）：

1. 在 `sendChatStream` 的 `processStream` 正常结束（`done:true`）后，补一个"流结束"兜底，确保 `onDone` 或一个 finalize 回调一定被调用。
2. 把 `isStreaming` 复位从分散的 `onDone`/`onError` 收敛到一个 `finally` 式逻辑，保证任何退出路径都复位。
3. 给 `useChatStream` 返回的 `abort` 接到 InputArea（目前 `abort: null` 没接线），允许用户手动中止卡住的流。

---

### 问题 2：文件无法发送

**现象**：上传文件后发送，模型收不到文件内容（或行为异常）。

**根因**：前端 `upload.ts` 绕过了统一的 `apiFetch`，缺少 snake_case → camelCase 转换，导致上传响应字段全部变成 `undefined`。

- 后端 `/api/upload` 返回：`{"file_id": "...", "name": "...", "text_content": "..."}`（snake_case，已实测 200 正常）。
- 项目其它 API 调用走 `apiFetch`，会用 `snakeToCamel` 把 `file_id`→`fileId`、`text_content`→`textContent`（[client.ts:24](frontend/src/api/client.ts#L24)）。
- 但 [upload.ts:3-18](frontend/src/api/upload.ts#L3-L18) **直接用 `fetch` + `response.json()`**，没有转换 → 拿到的是 `file_id` / `text_content`。
- [InputArea.tsx:46-50](frontend/src/components/InputArea.tsx#L46-L50) 按 camelCase 读取：`uploaded.fileId`、`uploaded.textContent` → **两者都是 `undefined`**。
- 于是 `attachFile({ id: undefined, name: undefined, textContent: undefined })` 把一个坏文件存进 store。
- 发送时 [useChatStream.ts:42-45](frontend/src/hooks/useChatStream.ts#L42-L45) 转成 `{ name: undefined, content: undefined }`，后端 [chat.py:16-26](backend/app/routers/chat.py#L16-L26) `_attach_files_to_messages` 拼出 `[文件: undefined]\nundefined` 附到消息里 → 模型收到的是无意义内容。

**已排除**：文件解析器（`file_parser.py`）和 upload 路由本身正常——实测 `.txt` 上传返回 200 且 `text_content` 正确。问题纯粹是前端字段映射。

**修复方向**（未实施）：

1. 让 `uploadFile` 复用 `apiFetch`（但 `apiFetch` 强制 `Content-Type: application/json`，与 `FormData` 冲突，需要小改 `apiFetch` 支持跳过该 header），或
2. 在 `uploadFile` 内手动对响应做一次 `snakeToCamel` 转换（最小改动，推荐）。
3. 修完后端到端验证：上传 → 附件标签显示文件名 → 发送 → 模型回复中体现文件内容。

---

## 三、已完成的修复

### 修复 A：API 凭证读取与防御性检查（2026-07-10）

**背景**：原现象"无法读取 .env 内 API 信息来真正调用"。实测确认 `.env` 本身能被加载（DeepSeek 实测 200），真因是 `.env` 只配了 DeepSeek/Kimi 两个 vendor，其余模型用空 key 调用失败且无提示。

改动文件：

- [backend/app/config.py](backend/app/config.py)：`env_file` 从相对路径 `".env"`（依赖 CWD）改为基于 `config.py` 文件位置的绝对路径，消除"从非 backend 目录启动则 .env 静默失效"的隐患。
- [backend/app/adapters/factory.py](backend/app/adapters/factory.py)：`get_adapter` 增加两道防御——未知 vendor 报错、空 API key 报清晰错误（如 `No API key configured for vendor 'glm'. Set GLM_API_KEY in backend/.env and restart the server.`）。
- [backend/tests/test_adapters.py](backend/tests/test_adapters.py)：adapter 流解析测试改为直接构造 adapter，不再依赖真实 `.env` 凭证。

验证：13 个测试全过；从项目根目录启动也能正确加载 `.env`。

**待用户操作**：在 `backend/.env` 中按需补充想用的 vendor key（`GLM_API_KEY`、`OPENAI_API_KEY`、`ANTHROPIC_API_KEY`、`GEMINI_API_KEY`），补完重启后端生效。

---

## 四、本次修复记录

### 修复 B：连续对话死锁 & 文件发送字段映射（2026-07-10）

**改动文件**：

- `frontend/src/api/chat.ts`
  - 新增 `onFinally` 回调，保证流式请求任何退出路径（`onDone` / `onError` / 流自然关闭 / 用户中止）都会触发复位。
  - 流正常关闭但未收到 `{type:'done'}` 时，自动补发 `onDone('stop')` 兜底。
- `frontend/src/hooks/useChatStream.ts`
  - 用 `onFinally` 统一复位 `isStreaming`。
  - 返回真实 `abort()` 函数，并支持发送新消息前自动中止旧流。
- `frontend/src/components/InputArea.tsx`
  - 流式中显示"停止"按钮，调用 `onAbort`。
- `frontend/src/components/WorkspaceLayout.tsx`
  - 把 `abort` 从 `useChatStream` 传给 `InputArea`。
- `frontend/src/api/upload.ts`
  - 上传响应用 `snakeToCamel` 转换，修复 `fileId` / `textContent` 为 `undefined` 的问题。
- `frontend/src/hooks/useChatStream.ts`
  - 过滤掉 `name` 或 `textContent` 为空的附件，避免把坏文件发给后端。

---

## 五、本次修复记录（追加）

### 修复 C：连续对话文本重叠 & 全文本文件支持（2026-07-10）

**改动文件**：

- `frontend/src/hooks/useChatStream.ts`
  - 发送新消息前自动中止旧的流式请求。
  - 每轮对话独立创建新的 assistant 占位消息，避免把新回答追加到上一轮已完成的回答里。
- `frontend/src/store/workspaceStore.ts`
  - `appendToAssistant` / `setAssistantStatus` 只操作状态为 `streaming` 的最后一条 assistant 消息，防止已结束的消息被误改。
- `frontend/src/components/InputArea.tsx`
  - 用 `validator` 替代严格 MIME 类型过滤，支持 `.md` 及各类代码文件上传。
- `backend/app/services/file_parser.py`
  - 扩展支持的文本扩展名：`.md`、`.json`、`.yaml`、代码文件（`.py`、`.js`、`.ts` 等）、`.csv`、`.log` 等。
  - 对未知扩展名增加 UTF-8 文本启发式检测，无扩展名的纯文本文件也能上传。
- `backend/app/routers/upload.py`
  - 改为读取文件内容后做启发式检测，兼容无扩展名或扩展名不在白名单的文本文件。

---

## 六、本次修复记录（追加）

### 修复 D：消息列表重叠 + 右键删除会话菜单 + 删除确认弹窗（2026-07-13）

**问题 1：连续对话输出重叠**

- 现象：在已有对话里发新问题，新回答与上一轮内容视觉重叠。
- 根因：[MessageList.tsx](frontend/src/components/MessageList.tsx) 用 `@tanstack/react-virtual` 虚拟列表时 `estimateSize` 固定返回 80px，而 assistant 流式消息内容会从几行动态增长到几十行，固定估算高度导致后续项 `translateY` 定位落在前一项内容中间 → 重叠。
- 修复：每个虚拟项根 div 加 `ref={virtualizer.measureElement}` + `data-index`，v3 内部用 ResizeObserver 自动测量真实高度，内容增长时自动重排。`estimateSize: 80` 仅作初始占位。

**问题 2：右键删除会话菜单**

- 需求：右键历史会话出二级菜单含"重命名 / 删除"，与现有 ⋯ 按钮菜单并存。
- 修复 [ConversationList.tsx](frontend/src/components/ConversationList.tsx)：
  - 会话项加 `onContextMenu`，右键弹 `position: fixed` 浮层菜单，定位到鼠标位置并做视口边缘 clamp。
  - 抽出 `renderMenuItems` 供右键菜单和 ⋯ 按钮菜单共用。
  - 外部点击 / Esc 关闭菜单：用 `target.closest('[data-menu]')` 判断点击是否落在菜单内——**关键**，不能无差别 `mousedown` 关闭，否则 `mousedown` 先于 `click` 触发会卸载菜单项导致 `onClick` 失效（⋯ 菜单的删除/重命名曾因此失效）。

**问题 3：删除确认弹窗**

- 需求：删除会话前加确认防误删。
- 修复：`confirmDeleteId` 状态 + 居中 modal（取消 / 确认删除），右键菜单和 ⋯ 菜单的删除都走它。

**问题 4：确认弹窗背景不显示（Tailwind v4 配置坑）**

- 现象：遮罩 / 弹窗卡片背景不显示，背后文字透过来。
- 根因：项目 [index.css](frontend/src/index.css) 用 Tailwind v4 + 自定义 `@theme`，`--color-background` 存的是裸 HSL 值 `0 0% 100%`。`bg-black/40`、`bg-background` 等工具类在这个配置下未正确包成 `hsl(...)`，背景实际透明。
- 修复：遮罩与弹窗卡片都改用内联样式（`rgba(0,0,0,0.4)` 遮罩 + `rgb(255,255,255)` 卡片），不依赖 Tailwind 调色板，确保背景一定生效。

**验证**：前端 `tsc -b` 干净、`oxlint` 无新问题；后端 29 测试全过。用户实测消息不再重叠，⋯ 菜单和右键菜单均正常，确认弹窗背景清晰。

**问题 5：右键菜单和二级菜单背景不显示（Tailwind v4 配置坑）**

- 现象：同上，发生在右键菜单和"..."二级菜单上
- 根因：同上
- 修复：`rgb(255,255,255)` 卡片

---

## 七、本次修复记录（追加）

### 修复 E：开始界面自动建会话 + 模型管理 UI（2026-07-14）

**问题 1：开始界面发送不自动建会话**

- 现象：进入应用在 EmptyState 界面直接用下方输入框发消息，无反应、不建会话。
- 根因：[useChatStream.ts:18-19](frontend/src/hooks/useChatStream.ts#L18-L19) `sendMessage` 开头 `if (!conversationId) return`——空状态无 `activeId`，直接返回。而 [WorkspaceLayout.tsx:63](frontend/src/components/WorkspaceLayout.tsx#L63) 的 InputArea 在 `!currentConversation` 时仍渲染，用户能输入但发了没反应。
- 修复 [WorkspaceLayout.tsx](frontend/src/components/WorkspaceLayout.tsx)：`handleSend` 改为 async，发送前判断 `!activeId || !currentConversation` 则先 `await createConversation()`，再 `sendMessage`。修好后端会话标题自动生成（首条消息前 50 字）随之生效。

**问题 2：模型管理 UI（完整 CRUD）**

- 背景：后端 `/api/models` CRUD、前端 `api/models.ts` 封装、store 的 `addModel/updateModel/removeModel` 全部已就绪，只缺前端组件。UI 库无 Dialog 组件。
- 新增文件：
  - [frontend/src/components/ui/modal.tsx](frontend/src/components/ui/modal.tsx)：可复用 Modal，遮罩/卡片用内联 `backgroundColor`（沿用修复 D 的 Tailwind v4 坑规避）。
  - [frontend/src/components/ModelManager.tsx](frontend/src/components/ModelManager.tsx)：模型管理弹窗。列表（名称/id/vendor/adapterType + 启停切换 + 编辑 + 删除）、新增/编辑表单（model_id/名称/vendor/adapterType 下拉 5 枚举/base_url/启用开关）、删除二次确认。`fetchAllModels` 拉全部（含禁用），操作后同步 store 与重载列表。
- 改动文件：
  - [frontend/src/components/ChatHeader.tsx](frontend/src/components/ChatHeader.tsx)：加"模型管理"按钮（Settings2 图标）+ `ModelManager` 弹窗状态。

**验证**：前端 `tsc -b` 干净、`oxlint` 无新问题、`npm run build` 成功；后端 29 测试全过；实测模型 CRUD API（创建/禁用/active 列表排除/删除/数据回归）全链路 200。

---

## 八、本次修复记录（追加）

### 修复 F：模型级 API Key 入口（2026-07-14）

**背景**：模型管理 UI 此前只能配 model_id/vendor/adapter_type/base_url/启用，没有 API key 入口。openai_compatible / anthropic_compatible 类模型接入第三方服务时需要自己的 key + base_url，而 .env 只有 6 个固定 vendor 的 key，新增的 compatible 模型无法调用。

**架构决策**（经确认）：**模型级 key**，而非写回 .env。

- ModelConfig 表加 `api_key` 字段（可空）。
- factory 解析顺序：模型自带 `api_key` → .env 的 vendor key（向后兼容 6 个固定 vendor）。
- GET 接口不回传 key 明文，只返回 `has_api_key` 布尔。

**改动文件**：

- 后端
  - [backend/app/models.py](backend/app/models.py)：ModelConfig 加 `api_key` 字段。
  - [backend/main.py](backend/main.py)：lifespan 加轻量迁移 `ALTER TABLE model_configs ADD COLUMN api_key`（create_all 不改已有表，try/except 兼容已升级的 DB）。
  - [backend/app/schemas.py](backend/app/schemas.py)：Create/Update 加 `api_key`；Out 加 `has_api_key`，用 `model_validator(mode="before")` 从 ORM 的 `api_key` 派生且**不泄露明文**。
  - [backend/app/routers/models.py](backend/app/routers/models.py)：所有端点声明 `response_model=ModelConfigOut` 防泄露；PUT 时 `api_key` 未传=不变、传 null=清空、传字符串=更新。
  - [backend/app/adapters/factory.py](backend/app/adapters/factory.py)：`get_adapter` 加 `api_key` 参数，优先用模型 key 回退 vendor key；`get_adapter_by_model_id` 传入 `config.api_key`。错误提示补充"或通过模型管理 UI 提供 key"。
  - [backend/tests/conftest.py](backend/tests/conftest.py)：测试 DB 加同样的 ALTER TABLE 迁移。
- 前端
  - [frontend/src/types/index.ts](frontend/src/types/index.ts)：ModelConfig 加 `hasApiKey?`。
  - [frontend/src/api/models.ts](frontend/src/api/models.ts)：createModel 传 `api_key`；updateModel 用 `ModelUpdatePayload`，**只发送设置的 `apiKey` 字段**（undefined 丢弃，配合后端 exclude_unset 的"不变"语义）。
  - [frontend/src/components/ModelManager.tsx](frontend/src/components/ModelManager.tsx)：表单加 API Key 输入框（password 类型）。兼容适配器（openai/anthropic compatible）新建时必填 key；编辑时留空=保持不变、输入新值=替换，hint 区分"已配置/未配置"。列表加"已配Key"徽标。

**验证**：

- 后端 29 测试全过；前端 tsc/oxlint/build 全过。
- 实测：创建 vendor=openai、adapter=openai_compatible、自带 key+base_url 指向 DeepSeek 的模型，factory 用模型级 key 成功调通 DeepSeek 返回回复。
- 实测：GET `/api/models/all` 不含 `api_key` 字段，只返回 `has_api_key` 布尔。

**安全说明**：API key 以明文存 SQLite（与 .env 同级别）。GET 接口不回传明文，但本地 DB 文件本身未加密——与 .env 存 key 的风险等级一致。

---

## 九、下一步待办

按优先级排序：

- [X] **修复问题 2（文件发送）**：`upload.ts` 加 camelCase 转换。
- [X] **修复问题 1（连续对话）**：`sendChatStream` 加流结束兜底复位 `isStreaming`；把 `abort` 接到 UI。
- [X] **修复消息列表重叠**：虚拟列表动态测高。
- [X] **右键删除会话 + 确认弹窗**。
- [X] **问题待修复**：在开始界面直接在下面的对话框输入问题发送后不会自动生成新会话 → 已修复（`WorkspaceLayout.handleSend` 空状态先 `createConversation`）。
- [X] **端到端验证连续对话 + 文件发送两个场景**。
- [X] **会话标题自动生成（当前后端已实现，前端需验证）**：已确认后端 `conversation_service.add_message` 按首条消息前 50 字生成标题，修好"开始界面发送"后自动生效。
- [X] **模型管理 UI（后端 CRUD 已就绪，前端已接）**：ChatHeader "模型管理" 按钮 → Modal 弹窗，列表 + 启停 + 新增/编辑表单 + 删除确认。
- [X] **跨平台兼容**：根 `.gitignore` + `frontend/.npmrc`；`backend/pyproject.toml` 拆出 `uvicorn[standard]` 平台相关的 `watchfiles`/`httptools`/`uvloop` 用 PEP 508 marker 仅在非 Windows 安装，Windows 走纯 asyncio loop；新增 `.github/workflows/ci.yml` 三平台 matrix（ubuntu/windows/macos × 前后端）。
- [X] **部署交付物**：补齐前后端 `Dockerfile` + 根目录 `docker-compose.yml` + `frontend/nginx.conf`，实现 `docker compose up` 一键启动（DEVELOPMENT_PLAN 验收标准第 7 条）。
- [X] **性能验证**：构造 1000 条消息会话，`frontend/tests/perf/MessageList.bench.tsx` 自动 bench 挂载耗时；`scripts/seed-1000msgs.py` 手动灌库用来 dev 实测滚动流畅度（DEVELOPMENT_PLAN 验收标准第 5 条）。
- [X] **前端关键 hook 测试**：新增 `vitest` + `@testing-library/react` + `jsdom`；`frontend/tests/hooks/{useChatStream,useConversation}.test.ts` 7 个用例覆盖流式 chunk 拼接 / done / error / abort / onFinally / 装载会话与模型。
- [X] **Skills 挂载开发**：新增 `backend/app/skills/` 包（`base.py` Skill Protocol、`registry.py` 启动扫描、`echo.py` + `current_time.py` 示例）；重写 `routers/skills.py` 为 `{status,skill,output,metadata,message}` 统一信封；新增 6 个 `test_skills.py` 用例。
- [X] **多轮推理（AgentService 第一期）**：新增 `backend/app/services/agent_service.py` 编排层，与 `conversation_service.py` 平级，仅支持多轮推理（ReAct 思考链），**不含 tool calling / RAG**，保持现有 Adapter + Streaming 架构不动。详见第十三节工作记录。

- [~] **AgentService 第二期（2a：LangChain + Tool Calling，不含 RAG）**：完成 LangChain/LangGraph 引入、Skill → LangChain Tool 桥、temperature 透传到 adapter、SSE `action`/`observation`/`warning` 事件、`Message.metadata` JSON 列持久化 step_count/aborted/tool_calls、前端 Agent 模式 toggle。详见第十四节工作记录。**2b（RAG + 知识库 UI + Agent 轨迹面板）仍待启动。**

- [ ] **AgentService 第二期**：在 AgentService 内部引入 LangChain/LangGraph（范围严格限制在该模块内），叠加 **Tool Calling** 与 **RAG**（markdown 笔记检索）能力；Skills 挂载可在此之后接入。

---

## 十、关键技术细节备忘

- 后端启动：`cd backend && uv run uvicorn main:app --reload`（注意入口是顶层 `main.py`，不是 `app.main`）。
- 前端启动：`cd frontend && npm run dev`（5173，已配 `/api` 代理到 8000）。
- `.env` 现在只配了 `DEEPSEEK_API_KEY`、`KIMI_API_KEY`，其余 vendor 留空。
- DB：`backend/workbench.db`（SQLite + aiosqlite），seed 了 11 个模型，全部 `is_active=1`。
- 适配器约定：DeepSeek/Kimi/GLM 走 `openai_compatible`；OpenAI 走 `openai`；Anthropic 走 `anthropic`；Gemini 走 `gemini`。

---

## 十一、未来开发计划

### 1. 跨平台兼容性检查

- 检查 Windows 平台 npm 包缺失问题
- 解决 Linux 平台无法下载依赖的问题（如 uv 安装、系统库缺失等）
- 补充 CI 配置（如 GitHub Actions）做多平台验证

### 1.1 部署交付物

- 补齐 `backend/Dockerfile`、`frontend/Dockerfile`
- 补齐根目录 `docker-compose.yml` + `nginx.conf`（生产/本地反向代理示例）
- 验证 `docker compose up` 一键启动前后端（DEVELOPMENT_PLAN 验收标准第 7 条）

### 1.2 性能与测试补齐

- 构造 1000 条消息会话，验证 `@tanstack/react-virtual` 虚拟滚动流畅（验收标准第 5 条）
- 补前端关键 hook 测试：`useChatStream` / `useConversation`（`frontend/tests/` 目前为空）

### 1.3 Skills 挂载

- 基于已预留的 `backend/app/routers/skills.py`（`POST /api/skills/{name}` + `GET /api/skills`）
- 补齐技能注册与调用机制，本期 Skills 仅作为路由占位与简单流程，深度的 Agent tool 接入留待下节 AgentService 第二期

### 2. 新增 AgentService 编排层（第一期：多轮推理）

- **保持现有架构不变**：Adapter、ConversationService、Streaming 架构不动
- 新增 `AgentService` 作为 Agent 编排层，**不让 LangChain 接管整个后端**
- AgentService 位于 `backend/app/services/agent_service.py`，与 ConversationService 平级
- 职责：接收用户意图 → 编排 Agent 执行流程 → 调用 Adapter 完成 LLM 调用 → 返回结果
- **本期范围**：仅多轮推理（ReAct 思考链），不含 Tool Calling / RAG

### 3. 在 AgentService 内部引入 LangChain/LangGraph（第二期）

- 在 AgentService 内部使用 LangChain/LangGraph，不污染外部架构
- 负责：工具调用（Tool Calling）、RAG（检索增强生成，解析 markdown 笔记）等能力
- 保持 Adapter 层作为纯 LLM 调用抽象，AgentService 通过 Adapter 获取 LLM 响应
- 确保 LangChain 的引入范围仅限于 AgentService 内部，不扩散到其他模块

---

## 十二、本次工作记录（跨平台 + 部署 + 性能测试 + Skills 挂载，2026-07-20）

落地了第十节"下一步待办"中从跨平台兼容到 Skills 挂载的 5 项任务。AgentService 第一期/第二期仍保持未启动。

### 改动文件

- 跨平台兼容
  - [.gitignore](.gitignore)：根目录新增统一 gitignore，合并前后端规则；解决 `frontend/workbench.db` 等脏文件之前被纳入版本控制的问题。
  - [frontend/.npmrc](frontend/.npmrc)：`fund=false` / `audit=false`，CI 输出更安静；**不再设 `optional=false`**（曾误以为该选项是"启用可选依赖"，实际反向——会跳过 `@rollup/*` 平台子包导致 rollup 启动报错，已撤销）。
  - [backend/pyproject.toml](backend/pyproject.toml)：把 `uvicorn[standard]` 拆为基础 `uvicorn` + `watchfiles` / `httptools` / `uvloop`，三者各加 `; platform_system != 'Windows'` PEP 508 marker，使 Windows 走纯 asyncio loop（无 Rust/C 扩展构建失败），其他平台继续享受 fast loop 与 `--reload`。
  - [.github/workflows/ci.yml](.github/workflows/ci.yml)：新增 GHA workflow，matrix `[ubuntu-latest, windows-latest, macos-latest]` × `{backend: uv sync --frozen → uv run pytest, frontend: npm ci → npm run lint → npm run test → npm run build}`。`fail-fast: false` 以便看到三平台各自的真实失败。
- 部署交付物
  - [backend/Dockerfile](backend/Dockerfile) + [backend/.dockerignore](backend/.dockerignore)：基于 `ghcr.io/astral-sh/uv:python3.11-bookworm-slim`，`uv sync --frozen --no-dev` 仅装运行时依赖；DB 放 `/app/data` 卷。
  - [frontend/Dockerfile](frontend/Dockerfile) + [frontend/.dockerignore](frontend/.dockerignore)：多阶段，`node:20-alpine` build → `nginx:alpine` 托管 `dist/`。
  - [docker-compose.yml](docker-compose.yml)：`backend` + `frontend` 两服务；backend 挂 `./backend/.env:ro` 与命名的 `backend-data` 卷；frontend 暴露 80；带 healthcheck 让 frontend 等 backend `/health` 就绪后启动。
  - [frontend/nginx.conf](frontend/nginx.conf)：`/api/` → `proxy_pass http://backend:8000`，关闭 `proxy_buffering` 保证 SSE 直通；其余走 `try_files … /index.html` SPA fallback。
- 性能与测试补齐
  - [frontend/package.json](frontend/package.json)：新增 devDep `vitest` / `@testing-library/react` / `@testing-library/jest-dom` / `jsdom`；新增 scripts `test` / `test:watch`。
  - [frontend/vitest.config.ts](frontend/vitest.config.ts) + [frontend/tsconfig.vitest.json](frontend/tsconfig.vitest.json) + [frontend/tests/setup.ts](frontend/tests/setup.ts)：jsdom 环境、`@` alias 沿用、`scrollIntoView` / `ResizeObserver` 在 jsdom 下的 polyfill、`cleanup()` 每用例后挂载卸载。
  - [frontend/tests/hooks/useChatStream.test.ts](frontend/tests/hooks/useChatStream.test.ts)：4 个用例——文本流拼接 + `done`、纯 `done` 走 `onFinally` 复位 `isStreaming`、`error` chunk 不漏恢复、abort 不产生未捕获异常。
  - [frontend/tests/hooks/useConversation.test.ts](frontend/tests/hooks/useConversation.test.ts)：2 个用例——装载 conversations + models；HTTP 失败 graceful 不抛。
  - [frontend/tests/perf/MessageList.bench.tsx](frontend/tests/perf/MessageList.bench.tsx)：构造 1000 条 mock 消息，断言虚拟化包装层挂载且耗时 < 2000ms；为绕过 jsdom 零高度问题临时把 `HTMLElement.prototype.clientHeight` 提升到 800。
  - [scripts/seed-1000msgs.py](scripts/seed-1000msgs.py)：直接 `sqlite3` 往 `backend/workbench.db` 灌一个会话 + 1000 条交替消息，用于 dev 实测 `react-virtual` 滚动体验。
- Skills 挂载（方案 A：内存注册表，不落库、无前端 UI）
  - [backend/app/skills/__init__.py](backend/app/skills/__init__.py)：包入口，import 触发注册。
  - [backend/app/skills/base.py](backend/app/skills/base.py)：`SkillResult` TypedDict + `Skill` Protocol（`name` / `description` / `async run(input, args)`）。
  - [backend/app/skills/registry.py](backend/app/skills/registry.py)：启动时扫描子模块 `SKILL`，按 `name` 入字典；`list_skills()` 返回 manifest，`get_skill(name)` 查表；重复注册抛错。
  - [backend/app/skills/echo.py](backend/app/skills/echo.py) + [backend/app/skills/current_time.py](backend/app/skills/current_time.py)：两个示例 skill（echo 支持 `args.upper`，current_time 返回 UTC/本地 ISO 串）。
  - [backend/app/routers/skills.py](backend/app/routers/skills.py)：重写为 `GET /api/skills` 返回 manifest + `POST /api/skills/{name}` 接 `{input, args}`（body 可省），统一信封 `{status, skill, output, metadata, message}`；未知 skill / 运行异常均走 error 信封而非 HTTP 5xx。
  - [backend/tests/test_skills.py](backend/tests/test_skills.py)：6 个用例覆盖 manifest 包含 echo+current_time、echo 原样返回 / upper 标志、空 body、current_time 输出 ISO、未知 skill 返回 error 信封。

### 验证

- 后端：`cd backend && uv run pytest -q` → **35 passed**（原 29 + 新增 6 skill 用例）。
- 前端：`cd frontend && npm run test` → **7 passed**（4 + 2 + 1 bench）。`npm run build` 成功。
- 未跑：`docker compose up` 与 GHA 三平台 matrix（需要推送触发）。
- 已知小问题：`useChatStream` 测试控制台出现 act() 警告（状态更新在异步流回调里发生），不影响断言通过；后续可在 sendMessage 内部把流读循环包到 `act()` 里以消音。

### 未启动（保留待办）

- AgentService 第一期（多轮推理 / ReAct 思考链）——已完成，见第十三节
- AgentService 第二期（引入 LangChain/LangGraph + Tool Calling + RAG）——本期 Skills 挂载的深度工具化将在此阶段统一做。

---

## 十三、本次工作记录（AgentService 第一期：多轮推理，2026-07-20）

按第十节"下一步待办"第 7 条落地。一期边界严格遵守事先对齐的范围：纯文本 ReAct 循环、无工具调用、无 RAG、不动 Adapter 公共签名、不动 DB schema、前端本期无入口。

### 改动文件

- 共享 helper 抽离
  - [backend/app/services/_chat_helpers.py](backend/app/services/_chat_helpers.py)：抽出 `_attach_files_to_messages` 为纯函数 `attach_files_to_messages`，供 `/api/chat` 与 `/api/agent-chat` 共用。
  - [backend/app/routers/chat.py](backend/app/routers/chat.py)：改 import 复用，删掉本地实现。
- Schema / Config
  - [backend/app/schemas.py](backend/app/schemas.py)：
    - `ChatChunk.type` 从 `["text","thinking","done","error"]` 扩为加入 `"warning"`，用于 `max-steps-exceeded` 信号。
    - 新增 `AgentChatRequest(ChatRequest)`：前置继承，新增 `max_steps: int = 8`、`step_temperature: float | None`、`final_temperature: float | None`。
  - [backend/app/config.py](backend/app/config.py)：`Settings` 新增 `agent_max_steps=8`、`agent_step_temperature=0.7`、`agent_final_temperature=0.4`；注释明确温度为 placeholder（adapters 当前不接 temperature 参数），第二期再接通。
  - [backend/.env.example](backend/.env.example)：补 `AGENT_MAX_STEPS` / `AGENT_STEP_TEMPERATURE` / `AGENT_FINAL_TEMPERATURE` 三行示例。
- ReAct 编排核心
  - [backend/app/services/prompts/react_system.txt](backend/app/services/prompts/react_system.txt)：中文 ReAct 提示模板，明确规定当前无工具、Action 必须为 `none`、最多 8 步、必须在末尾给出 `Final Answer:`。
  - [backend/app/services/agent_service.py](backend/app/services/agent_service.py)：
    - `AgentService` 类，与 `ConversationService` 平级；构造接 AsyncSession，内部组合 conversation_service 落库。
    - `stream_agent_chat(request, adapter, conversation) -> AsyncIterator[str]`：SSE 协议与 `/api/chat` 一致（`text` / `thinking` / `warning` / `done` / `error`）。
    - 每步：透传 chunk → 累加 step_thinking/step_content → 步末持久化 thinking（带 `--- 第 N 步思考 ---` 边界注释）→ 扫描 `Final Answer:` 决定终止 / append assistant turn + 回填 `Observation: 无可用工具…` 继续循环。
    - `max_steps` 触发：发 `warning max-steps-exceeded` + 把最后一步当作 final 落库 + `done finish_reason="agent"`。
    - 错误路径：SSE `error` + 落 status=error、content=`[Agent 出错: {ex}]`、thinking 携带已累积 partial。
    - abort 路径：捕 `asyncio.CancelledError`，partial 持久化 status=error（**不**在 DB 加 metadata 字段，遵守"不动表结构"约束），吞掉异常让 ASGI 不打 traceback。
    - 启动时读 `react_system.txt` 一次缓存到模块级 `REACT_SYSTEM_PROMPT`；文件缺失走内联回退。
- 路由
  - [backend/app/routers/agent.py](backend/app/routers/agent.py)：`POST /api/agent-chat`，镜像 `/api/chat` 的会话校验/用户消息持久化/StreamingResponse 头；不再检查 `stream=False`（继承时已校验）。
  - [backend/main.py](backend/main.py)：注册 `agent.router`，prefix `/api`，与其它 router 并列。
- 测试
  - [backend/tests/test_agent_service.py](backend/tests/test_agent_service.py)：7 个用例。
    - `_extract_final_answer` 三分支（命中、命中带换行、未命中、纯 sentinel）。
    - 单步 `Final Answer:` 早退（`stream_chat` 仅 1 次 / `done` 出现）。
    - 多步累积：`step1/2 thoughts` 都进 thinking 事件、DB 单条 assistant status=done、content=`ok`、thinking 含两条 `第 N 步思考` 注释。
    - `max_steps=2` 不给 Final Answer → warning 事件触发且 `max_steps=2` → done。
    - adapter 抛 `RuntimeError` → SSE error 事件 + DB status=error + thinking 含 `partial thoughts before boom`。
    - adapter raise `asyncio.CancelledError` → 不抛、无 error/done 事件、DB status=error + thinking 含 partial。
    - `/api/agent-chat` 路由注册校验（422 而非 404）。
  - `_ScriptedAdapter` 按 turn 而非按 chunk 推进指针，避免多步自增错位。
- 联调脚本
  - [scripts/test-agent-chat.py](scripts/test-agent-chat.py)：用 `urllib.request` 流式读 SSE，按事件类型分别 stdout（text 正常 / thinking 暗色 ANSI / done 结尾 / error / warning 走 stderr），支持 `--model` `--prompt` `--max-steps` `--thinking`。

### 验证

- `cd backend && uv run pytest -q` → **42 passed**（之前 35 + 新增 7 agent 用例）。
- 手动联调脚本未执行（需启动后端 + 真实 key，由开发者自测）。

### 已知限制（按设计约束，非缺陷）

- **温度未注入**：`agent_step_temperature` / `agent_final_temperature` 仅在 schema 与 `.env` 可读取，未转发给 adapter——现 `BaseAdapter.stream_chat` 不接 temperature 参数。第二期统一接入。
- **前端无入口**：本期前端未加 Agent 模式 toggle，新端点靠 `scripts/test-agent-chat.py` 或 Postman 验证；UI 入口与"Agent 轨迹"面板留待第二期。
- **无真工具调用**：协议规定 Action 必为 `none`，系统固定回填 Observation，不接 Skills。第二期把 Skills 接入工具列表。
- **无 RAG**：第二期补。
- **abort 不带 metadata**：DB 未新增字段；非零 cost 留到第二期再决定是否扩 schema。

### 未启动（2b）

- 引入向量库 + RAG（markdown 笔记检索）。
- 知识库前端入口与 Agent 轨迹面板组件。
- 厂商原生 tool-calling API（OpenAI tool_calls delta / Anthropic tools）—— 2a 仍走 ReAct prompt 注入。

---

## 十四、本次工作记录（AgentService 2a：LangChain + Tool Calling，2026-07-20）

落地第十三节中划为 2a 的子集：在不破坏现有 Adapter/ModelConfig 单一入口的前提下，把 LangChain/LangGraph 引入 `agent_service.py` 内部，让模型可以真实调用 Skills 暴露的工具，并补上前端 Agent 模式入口。RAG 与轨迹面板延后到 2b。

### 改动文件

- 依赖
  - [backend/pyproject.toml](backend/pyproject.toml)：新增 `langchain-core>=0.3,<0.4` 与 `langgraph>=0.2,<0.3`。**不引** `langchain-openai`/`langchain-anthropic`：用自家的 `AdapterChatModel` 桥到现有 BaseAdapter，绕开"装第二个 LLM 客户端栈、重复配 key"的退化。
- Adapter 层扩 temperature（让 Agent 步级温度真正发到模型）
  - [backend/app/adapters/base.py](backend/app/adapters/base.py)：`stream_chat` 签名加 `temperature: float | None = None`、`top_p: float | None = None` 命名关键字。
  - [backend/app/adapters/openai_adapter.py](backend/app/adapters/openai_adapter.py)：仅在 `temperature/top_p != None` 时注入 params，保留推理模型（o1/o3/deepseek-reasoner）不接温度的默认行为。
  - [backend/app/adapters/anthropic_adapter.py](backend/app/adapters/anthropic_adapter.py)：同上策略，注入 `payload["temperature"]`、`payload["top_p"]`。
  - [backend/app/adapters/gemini_adapter.py](backend/app/adapters/gemini_adapter.py)：注入到 `generationConfig.temperature`/`topP`。
- DB schema 扩一项
  - [backend/app/models.py](backend/app/models.py)：`Message` 新增 `metadata_` 字段，类型 `JSON`（SQLite 存 TEXT），默认空 dict。属性名带下划线避开 SQLAlchemy 保留字 `metadata`。
  - [backend/main.py](backend/main.py) + [backend/tests/conftest.py](backend/tests/conftest.py)：lifespan 与测试 fixture 各加 `ALTER TABLE messages ADD COLUMN metadata TEXT DEFAULT '{}'` 兼容迁移。
- Schema
  - [backend/app/schemas.py](backend/app/schemas.py)：
    - `ChatChunk.type` 扩 `Literal[..., "warning", "action", "observation"]`；新增 `name`/`step`/`input`/`maxSteps` 字段。
    - `AgentChatRequest` 新增 `enable_skills: list[str] | None`（None=全部注册 skill；显式列表是白名单）。
    - `MessageOut` 增加 `metadata: dict = {}` 字段，并用 `@model_validator(mode="before")` 把 ORM 的 `metadata_` 别名映射成 API 字段 `metadata`，避免前端拿到 SQLAlchemy 的保留字属性。
- Skills 暴露给 Agent
  - [backend/app/skills/registry.py](backend/app/skills/registry.py) + [backend/app/skills/__init__.py](backend/app/skills/__init__.py)：新增 `iter_skills()` 返回所有 `Skill` 实例。
- LangChain 适配层
  - [backend/app/services/langchain_adapter.py](backend/app/services/langchain_adapter.py)（新增）：`AdapterChatModel(BaseChatModel)`。实现 `_agenerate` + `_astream`（async 路径，LangGraph 走的就是这条）；同步 `_generate`/`_stream` 走 `concurrent.futures.ThreadPoolExecutor` 包装，仅供 sync 回退场景。`bind_tools` **显式 NotImplemented**：第二期 2a 仍走 ReAct prompt 注入，不依赖厂商原生 tool_calls API。`thinking` 字段塞到 `AIMessage.additional_kwargs["thinking"]`（langchain-core 0.3 把 `additional_metadata` 移除了，沿用坑见第十三节）。
- 重写 AgentService
  - [backend/app/services/agent_service.py](backend/app/services/agent_service.py)：
    - 仍保留 TextReAct 解析（`Action:` / `Action Input:` / `Final Answer:`），不依赖 native tool_calls。
    - 每步发起用 `chat_model._astream(messages)` 替代直接 await `adapter.stream_chat`；LangChain `AIMessageChunk` 流式累积。
    - Skills 通过 `_wrap_skill_as_tool` 包成 `StructuredTool`，agent 循环里 `await tool.ainvoke({"input": action_input})` 执行——错误走 error envelope 而非抛异常，loop 不中断。
    - SSE 协议扩三类：`{"type":"action","name","input","step"}`、`{"type":"observation","name","content","step"}`、`{"type":"warning","message":"max-steps-exceeded","max_steps"}`。
    - 步计数策略改为每步开始递增 `step_count`，warning 触发条件改为 `step_count >= max_steps`；后路径（cancel/error）依赖 `step_count` 的语义自洽。
    - `Message.metadata_` JSON 列落 `{step_count, aborted, tool_calls: [{name, step, input, output}]}`；正常运行也是 `{step_count: N, aborted: false, tool_calls: [...]}`。
- ReAct 模板更新
  - [backend/app/services/prompts/react_system.txt](backend/app/services/prompts/react_system.txt)：新增 `{tools_section}` 占位符；运行时由 AgentService 用注册 skill 动态注入；保留 `Action: none` 与 `Final Answer:` 终止符语义。
- Router
  - [backend/app/routers/agent.py](backend/app/routers/agent.py)：构造时 `iter_skills()` 传入 AgentService，由 `enable_skills` 实际过滤。
- 测试
  - [backend/tests/test_agent_service_v2.py](backend/tests/test_agent_service_v2.py)（新增，9 个用例）：
    - 单步 Final Answer、两步带 `echo` 工具调用、未知工具→observation+续推、`max_steps=2` 触发 warning、adapter 抛错→SSE error + DB metadata.error、abort→metadata.aborted=true + status=error 且无 done/error 事件、单元函数 `_parse_action` / `_extract_final_answer` / `_wrap_skill_as_tool` 校验、`/api/agent-chat` 路由仍注册。
    - 用 `_ScriptedChatModel(BaseChatModel)` 替代第一期的 `_ScriptedAdapter`，更贴近真实 LangGraph 路径。
  - [backend/tests/test_agent_service.py](backend/tests/test_agent_service.py)：保留作为第一期 ReAct 解析回归保护；`test_extract_final_answer` 改为 import module-level `_extract_final_answer` 函数。
- 前端
  - [frontend/src/types/index.ts](frontend/src/types/index.ts)：`Message` 加 `metadata?: Record<string, unknown>`；`ChatChunk.type` 扩 `warning`/`action`/`observation` 与新字段；新增 `AgentChatRequest` 接口。
  - [frontend/src/api/agent-chat.ts](frontend/src/api/agent-chat.ts)（新增）：`sendAgentChatStream` 与 `chat.ts` 同形态，新增 `onAction` / `onObservation` / `onWarning` 回调。
  - [frontend/src/api/chat.ts](frontend/src/api/chat.ts)：补 `warning` 事件分发到 `onWarning`，保持与 agent 路径行为一致。
  - [frontend/src/hooks/useChatStream.ts](frontend/src/hooks/useChatStream.ts)：`sendMessage` 内根据 `useWorkspaceStore.getState().agentMode` 分流到 `/api/agent-chat`；ReAct viewport（Action/Observation 行）写入 `assistant.thinking` 字段，复用现有 `ThinkingBlock` 组件无需新组件。
  - [frontend/src/components/InputArea.tsx](frontend/src/components/InputArea.tsx)：新增 `agentMode` prop 与「Agent」toggle 按钮（闪电图标 `Zap`，琥珀色 active 态），与「深度思考」并列；开启时下方显示一行提示文案。
  - [frontend/src/components/WorkspaceLayout.tsx](frontend/src/components/WorkspaceLayout.tsx)：把 `agentMode` 与 `onAgentModeToggle` 接到 InputArea。
  - [frontend/src/store/workspaceStore.ts](frontend/src/store/workspaceStore.ts)：新增 `agentMode` + `setAgentMode`；persist version 升到 4，partialize 把 agentMode 加入持久化字段。
  - [frontend/tests/hooks/useChatStream.test.ts](frontend/tests/hooks/useChatStream.test.ts)：新增 2 个用例覆盖 agent 路径——fetch URL 切换到 `/api/agent-chat`、SSE action/observation 走 thinking 字段、error 事件正确写入 `**Agent Error**`。

### 验证

- 后端：`cd backend && uv run pytest -q` → **51 passed**（42 + 9 新增 v2 用例）。
- 前端：`cd frontend && npm run test` → **9 passed**（原 7 + 2 新 agent 用例）；`npm run build` 成功；`npm run lint` 无新告警。
- 手动端到端：未跑（需启动后端 + 真实 key；可用 `scripts/test-agent-chat.py` 自测）。

### 已知限制（按设计约束，非缺陷）

- **RAG 未做**：留 2b，会一起补向量库选型、知识库 UI、Agent 轨迹面板组件。
- **不接厂商原生 tool_calls**：第二期仍用 ReAct prompt 注入。原 OpenAI/Anthropic 的 function-calling API 会另起 Phase 3 再接。`AdapterChatModel.bind_tools` 已显式 raise 提示。
- **Agent 轨迹不是独立 UI**：step_thinking / Action / Observation 直接拼进 `Message.thinking`，沿用 `ThinkingBlock` 渲染。等 2b 的轨迹面板会拆出 `<AgentTrace>` 组件。
- **Abort 持久化 metadata.aborted=true 但 SSE 不发 error**：与第一期一致，前端靠 `onFinally` 复位 streaming 状态；UI 上表现为「停止」按钮复位，无错误提示。
- **温度最终未开关**：`agent_final_temperature` 仍是 schema 字段，但 Agent 不会"再发一次 final 调用"——一旦步骤输出 `Final Answer:` 就用该文做 final_content，并不会用 final_temperature 再发一次模型调用。

### 项目依赖锁定

- `uv.lock` 已刷新；LangGraph 自带的 `langsmith`/`tenacity`/`pyyaml` 等传递依赖被纳入。CI 在 `langchain-core` 出 minor 版本时按 `>=0.3,<0.4` 锁，避免链式漂移。

---

## 十五、本次工作记录（AgentService 2b-i：RAG + 知识库管理，2026-07-21）

落地 §11.4 的 2b-i：在 Skills + Tool Calling 框架之上引入向量检索与知识库管理。Agent 模式经 `retrieve_notes` 工具自主检索用户上传的 markdown 笔记；普通 chat 模式把 KB 命中段落静默注入上下文。AgentTrace 面板留 2b-ii。

**用户本轮确认的两个决策**：(1) Embedding 用本地 `bge-small-zh`（按原计划，配 FakeEmbedder 兜底）；(2) 范围先做核心，Docker torch 烘焙 + CI 留尾巴。

**探索中发现的 3 处偏差（相对原 §11.4）**：(1) `langchain-text-splitters` 未安装——`MarkdownHeaderTextSplitter`/`RecursiveCharacterTextSplitter` 在该包而非 `langchain-core`；(2) 无 `pytest.ini`——`slow` marker 须注册在 `pyproject.toml [tool.pytest.ini_options]`；(3) ChatHeader「知识库」按钮是 disabled 占位而非已接线。

**关键设计修正**：原计划 FakeEmbedder「注入零向量」在 chromadb cosine 下返回 nan/退化为平局，改为 **no-op**——`embed_*` 返回 `[]`、`is_available()=False`、`retrieve()` 返回 `[]`、`upload_document()` 抛 `RuntimeError`→HTTP 503。dev 不装 torch 时优雅降级，上传时显式报错。

### 改动文件

- 依赖
  - [backend/pyproject.toml](backend/pyproject.toml)：加 `chromadb>=0.5`、`langchain-chroma>=0.1`、`langchain-text-splitters>=0.3`（关键缺失）、`sentence-transformers>=2.7`；`[tool.pytest.ini_options]` 加 `markers = ["slow: ..."]`。
- Config / 模型
  - [backend/app/config.py](backend/app/config.py) + [.env.example](backend/.env.example)：加 `embedding_model`、`chroma_persist_dir`（默认 `.chroma`，相对 backend root 解析）、`kb_chunk_size=800`、`kb_chunk_overlap=100`、`kb_top_k=4`、`kb_min_score=0.3`。
  - [backend/app/models.py](backend/app/models.py)：新增 `KnowledgeBase`（id/name/description/created_at/updated_at）与 `KnowledgeDoc`（id/kb_id FK CASCADE+index/filename/sha256/text/created_at），relationship `cascade="all, delete-orphan"`。无 `(kb_id,sha256)` 唯一约束——dedup 走显式 SELECT 返回 `deduplicated=True`。
  - [backend/app/schemas.py](backend/app/schemas.py)：新增 `KnowledgeBaseCreate`/`KnowledgeBaseUpdate`/`KnowledgeBaseOut`/`KnowledgeDocOut`（不含 text）/`DocumentUploadResponse`/`RetrievedChunk`，照 `ModelConfig*` 风格。`ChatChunk` 本期不改。
- 新后端服务
  - [backend/app/services/embedding_service.py](backend/app/services/embedding_service.py)：`EmbeddingService` 模块单例，懒加载 `SentenceTransformer('BAAI/bge-small-zh-v1.5')`（import 放进 `_load_model()` 避免测试链路引 torch）；不可用时回退 `FakeEmbedder`（no-op，返 `[]`）。`is_available()`/`embed_texts()`/`embed_query()`。
  - [backend/app/services/knowledge_service.py](backend/app/services/knowledge_service.py)：`KnowledgeService(db)` KB/doc CRUD + chunking + embed + retrieve。模块内懒 chromadb `PersistentClient` 单例（`_get_chroma_client()`，persist dir 对 `_BACKEND_ROOT` 解析）；collection-per-kb（`f"kb_{kb_id}"`，cosine space，删 KB = O(1) `delete_collection`）；`_chunk_text` 用 `MarkdownHeaderTextSplitter`→`RecursiveCharacterTextSplitter`；`retrieve` 返回 `RetrievedChunk`，score=1-distance。不可用时 `retrieve` 返 `[]`、`upload_document` 抛错。
  - [backend/app/skills/retrieve_notes.py](backend/app/skills/retrieve_notes.py)：**工厂** `get_retrieve_notes_skill(kb_id, knowledge_service)` 返回 `_RetrieveNotesSkill`，**不进 `registry._REGISTRY`**。`run` 返回带 `[来源: doc.md #heading | score=..]` 标签的 markdown，**不加 `Observation:` 前缀**（agent_service 会加），`metadata.chunks` 透传结构化片段。流经 `_wrap_skill_as_tool` 无需改 agent_service（duck-typed）。
  - [backend/app/routers/knowledge.py](backend/app/routers/knowledge.py)：`GET/POST/DELETE /api/knowledge-bases`、`GET/POST/DELETE /api/knowledge-bases/{id}/documents`。multipart 用 `UploadFile = File(...)`，仅 `.md/.markdown/.txt`、10MB 上限；embedding 不可用→503；未知 KB→404。
- 接线
  - [backend/app/routers/agent.py](backend/app/routers/agent.py)：`skills = list(iter_skills())` 后，若 `request.rag_knowledge_base_id` 非空，构造 `KnowledgeService(db)` + `get_retrieve_notes_skill` append；若 `enable_skills` 是 list 则追加 `"retrieve_notes"`（always-on 防白名单过滤）。
  - [backend/app/routers/chat.py](backend/app/routers/chat.py)：`attach_files_to_messages` 后，若 `rag_knowledge_base_id` 非空，`try: KnowledgeService.retrieve(...)` + `inject_retrieved_context`；`except: log warning + continue`（检索失败不阻断 chat）。
  - [backend/app/services/_chat_helpers.py](backend/app/services/_chat_helpers.py)：新增 `inject_retrieved_context(messages, chunks)`，prepend `[知识库检索结果]\n{chunks}\n\n[以下为用户原始问题]` 到最后一条 user 消息，**不替换**原内容。
  - [backend/main.py](backend/main.py)：注册 `knowledge.router`；model import 加 `KnowledgeBase, KnowledgeDoc` 让 `create_all` 看见。**不做** lifespan eager-init（懒加载）。
- 前端
  - [frontend/src/types/index.ts](frontend/src/types/index.ts)：加 `KnowledgeBase`/`KnowledgeDoc`/`DocumentUploadResponse`/`RetrievedChunk`（`ragKnowledgeBaseId` 已存在不改）。
  - [frontend/src/api/knowledge.ts](frontend/src/api/knowledge.ts)（新增）：CRUD 用 `apiFetch`（mirror `models.ts`）；`uploadDocument` 绕过 apiFetch 走原生 fetch 发 FormData（mirror `upload.ts`），响应 `snakeToCamel`。
  - [frontend/src/store/workspaceStore.ts](frontend/src/store/workspaceStore.ts)：加 `knowledgeBases`/`selectedKbId`('' sentinel)/`setSelectedKbId`/`loadKnowledgeBases`/`addKnowledgeBase`/`removeKnowledgeBase`；persist version 4→5，`selectedKbId` **同时**加进 `partialize` 与 `merge`（坑：只加 partialize 会让 hydration 静默重置）。
  - [frontend/src/components/KnowledgeBaseManager.tsx](frontend/src/components/KnowledgeBaseManager.tsx)（新增）：mirror `ModelManager.tsx` 结构，两级视图（KB 列表 → 选中 KB → 文档列表 + 上传/删除），删除确认用内联样式嵌套 overlay（Tailwind v4 @theme 使 bg-* 透明）。
  - [frontend/src/components/ChatHeader.tsx](frontend/src/components/ChatHeader.tsx)：知识库按钮移除 disabled + 接 onClick 开 KnowledgeBaseManager；新增 KB `<select>` 下拉（空时 `--无--`）；**直接读 store**（不经 WorkspaceLayout props）。
  - [frontend/src/hooks/useConversation.ts](frontend/src/hooks/useConversation.ts)：mount 时 `loadModels` 后追加 `loadKnowledgeBases`。
  - [frontend/src/hooks/useChatStream.ts](frontend/src/hooks/useChatStream.ts)：agent 与 chat 两分支请求体加 `ragKnowledgeBaseId: useWorkspaceStore.getState().selectedKbId || undefined`（用 `getState()` 避免 stale，mirror agentMode 模式）。
- 测试
  - [backend/tests/test_knowledge_service.py](backend/tests/test_knowledge_service.py)（新增 15 用例）：fake embedder（hash 派生确定性非零向量）+ temp chroma 目录，覆盖 KB CRUD、上传→chunk→索引、dedup、坏类型/超大/未知 KB、删文档、retrieve 排序与 min_score 过滤、FakeEmbedder no-op 路径。
  - [backend/tests/test_retrieve_notes_skill.py](backend/tests/test_retrieve_notes_skill.py)（新增 7 用例）：fake KB + fake retrieval 验证输出格式（来源标签、无 `Observation:` 前缀）、`metadata.chunks`、args 透传、空结果消息。
  - [backend/tests/test_routers_knowledge.py](backend/tests/test_routers_knowledge.py)（新增 9 用例）：httpx ASGITransport 端到端，覆盖 list/create/delete KB、上传/dedup/坏类型/未知 KB、删文档。
  - [backend/tests/test_chat_helpers.py](backend/tests/test_chat_helpers.py)（新增 5 用例）：`inject_retrieved_context` prepend/不替换/no-op/无 heading/与文件 attach 共存。
  - [backend/tests/test_agent_service_v2.py](backend/tests/test_agent_service_v2.py)：新增 2 用例——retrieve_notes 流经 agent loop（action/observation 事件 + tool_calls 持久化 + 无重复前缀）、空结果 observation。
  - [frontend/tests/components/KnowledgeBaseManager.test.tsx](frontend/tests/components/KnowledgeBaseManager.test.tsx)（新增，建 `tests/components/` 目录）：mock API 覆盖列表渲染/创建/上传/删除确认。
  - [frontend/tests/hooks/useChatStream.test.ts](frontend/tests/hooks/useChatStream.test.ts)：新增 2 用例——chat 与 agent 两端点 fetch body 含 `rag_knowledge_base_id`。

### 验证

- 后端：`cd backend && uv run pytest -q` → **89 passed**（原 51 + 38 新增）。`uv run pytest -m "not slow"` → 89 passed（CI 等价）。
- 前端：`cd frontend && npm run test` → **15 passed**（原 7 + 4 KB manager + 2 KB body + 2 已有 agent）；`npm run build` 成功；`npm run lint` 仅 1 个**预先存在**的 `useConversation.ts` exhaustive-deps 警告（本次未新增）。
- 手动端到端 smoke（dev，真 bge 已随 `uv sync` 装上）：建 KB → 上传 md（验证 chunks 数）→ 普通 chat 问笔记内容（验证回复引用）→ Agent 模式问笔记（验证 `Action: retrieve_notes`）。脚本未单独固化。
- 实测检索质量：上传含「安装」「部署」两节的中文 md，问「怎么安装 fastapi?」top-1 命中 `#安装` 节 score≈0.81。

### 已知限制（按设计约束，非缺陷）

- **AgentTrace 面板未做**：2b-i 的检索结果经现有 `observation` 事件透传，复用 `ThinkingBlock` 渲染。结构化 `step_start`/`step_end`/`retrieved` 事件与 `<AgentTrace>` 组件留 2b-ii。
- **纯向量检索**：无 BM25 hybrid；同步处理文档（异步化留 2b-ii）。
- **上传格式**：仅 `.md/.markdown/.txt`（PDF/DOCX 留后续）。
- **FakeEmbedder 路径**：不装 torch 时上传返 503、检索返空——RAG 优雅降级而非崩。生产用真 bge 需 `uv sync` 装上（已含）或 Docker 烘焙（留尾巴）。

### 尾巴任务（本期未做）

- `backend/Dockerfile` 追加 `sentence-transformers` 安装 + 预烘焙 `bge-small-zh-v1.5` 到镜像。
- CI matrix（`.github/workflows/ci.yml`）评估 torch/onnxruntime 对三平台构建时长影响，必要时 split 或缓存。
- `@pytest.mark.slow` 真模型 smoke 用例（marker 已注册，用例待补；本地 `pytest -m slow` 跑）。

## 十六、本次工作记录（AgentService 2b-ii：AgentTrace 面板，2026-07-22）

落地 2b-i 遗留的 AgentTrace 面板：把 Agent 模式的 ReAct 多步推理从「堆在 `Message.thinking` 文本、复用 `ThinkingBlock`」升级为**结构化 step 卡片**展示（Thought / Action / Observation / retrieved chunks），并升级 SSE 协议为 step-bounded 事件流（`step_start`/`step_end`/`retrieved`），**保留**扁平事件向后兼容。

**用户本轮确认的四个决策**（详见 `PLAN_2b-ii.md`）：(1) retrieved 数据通道 = 拓宽 `_wrap_skill_as_tool`，用 `tool._last_metadata` 属性 stash 结构化结果（不动 LangChain `ainvoke` 返 str 契约）；(2) `step_end` 全路径覆盖（含 abort），finish ∈ {final, tool, empty, max_steps, error}；(3) agent 消息标记 = `metadata.agent`（占位 + 三处 persist 都写，否则 reload 丢失）；(4) Agent 消息正文只留最终答案——后端对每步 Thought/Action/Final Answer 都发 `text`，前端累积进 step.text，仅 `finish==="final"` 时去 `Final Answer:` 前缀后提升为 `message.content`，`thinking` 对 agent 消息保持空。

**探索中确认的关键事实**：ReAct 循环有 5 条正常终止路径 + 2 条异常路径（外层 CancelledError 跳过 step_end，因 `step_number` 可能未绑定）；`_wrap_skill_as_tool._arun` 原先丢弃 `result["metadata"]`；retrieve_notes 成功返回的 metadata 无 chunks（局部变量 `chunks` 含 `KnowledgeRetrievalResult` 可用）；前后端 `ChatChunk` schema 已漂移（TS 有 `input`/`maxSteps`，Python 无）。

**实现中踩到的坑**：

- **`tool` 闭包引用 NameError**：原 `_wrap_skill_as_tool` 在 `return StructuredTool.from_function(...)` 内联构造 tool，`_arun` 闭包引用 `tool` 时该名从未绑定。改为先 `tool = StructuredTool.from_function(...)` 再 `return tool`，闭包按 cell 引用即可在调用时解析。
- **zustand `set` 类型不匹配**：helper 函数若声明自定义 `StoreSet` 类型，与 zustand `set` 的重载签名（`replace` 可为 `true`）冲突。改为传入 `StoreApi<WorkspaceState>`（工厂第三参数 `api`），用 `api.setState`。
- **Tailwind v4 @theme 透明坑**（同 2b-i）：AgentTrace 的徽标/卡片背景用内联 `rgba()` 样式，不用 `bg-*`。
- **`<details>` 折叠文本仍在 DOM**：jsdom 下 `queryByText` 不看 CSS 可见性，retrieved 非空时 observation 文本进 `<details>` 仍被找到——测试改为断言「原始观察文本」summary 存在，而非断言 observation 文本消失。

### 改动文件

- 后端协议/服务
  - [backend/app/schemas.py](backend/app/schemas.py)：`ChatChunk.type` 加 `step_start`/`step_end`/`retrieved`；加 `input`/`max_steps`/`finish`/`label`/`docs` 字段（消除前后端漂移）。
  - [backend/app/services/agent_service.py](backend/app/services/agent_service.py)：(1a) `_wrap_skill_as_tool._arun` stash `tool._last_metadata`；(1c) 循环里 `step_start`→`steps.append(current_step)`，`thinking`/`text`/`action`/`observation` 累积进 current_step，`matching.ainvoke` 后读 `getattr(matching,"_last_metadata")` 发 `retrieved` 事件；(1d) 8 路径发 `step_end`（外层 cancel 跳过），warning/error/done 加 `step` 字段；(1e) 三处 persist 写 `"agent":True`+`"steps"`。
  - [backend/app/skills/retrieve_notes.py](backend/app/skills/retrieve_notes.py)：成功返回的 metadata 加 `chunks` 数组（`doc_id`/`filename`/`heading`/`score`/`text`）。
- 前端
  - [frontend/src/types/index.ts](frontend/src/types/index.ts)：`ChatChunk.type` 加 3 新类型 + `finish`/`label`/`docs` 字段；新增 `RetrievedChunkDoc`/`AgentStepAction`/`AgentStepObservation`/`AgentStep`。
  - [frontend/src/api/agent-chat.ts](frontend/src/api/agent-chat.ts)：`AgentStreamCallbacks` 加 `onStepStart`/`onStepEnd`/`onRetrieved`；switch 加 3 case，`retrieved` 显式蛇→驼映射（SSE 无拦截器）。
  - [frontend/src/store/workspaceStore.ts](frontend/src/store/workspaceStore.ts)：加 `mutateLastStep(api, mutate)` helper + 7 个 action（`appendAgentStep`/`appendAgentStepThinking`/`appendAgentStepText`/`setAgentStepAction`/`setAgentStepObservation`/`setAgentStepRetrieved`/`completeAgentStep`），操作 `lastMessage.metadata.steps`；工厂签名 `(set, get, api) =>`。
  - [frontend/src/components/AgentTrace.tsx](frontend/src/components/AgentTrace.tsx)（新增）：mirror `ThinkingBlock` 折叠/自动滚动；`StepCard` 子组件含 finish 徽标 + thinking/text/action/observation/retrieved 段（retrieved 非空时 observation 折进 `<details>`），retrieved chunk 一张 `<details>` 卡片。
  - [frontend/src/components/MessageItem.tsx](frontend/src/components/MessageItem.tsx)：三分支渲染——`metadata.agent && steps 非空`→AgentTrace；`metadata.agent && thinking 非空无 steps`→ThinkingBlock（旧 2a/2b-i 兜底）；普通 chat→ThinkingBlock。
  - [frontend/src/hooks/useChatStream.ts](frontend/src/hooks/useChatStream.ts)：`agentMode` 读取上移到占位创建前；占位 agentMode 时设 `metadata:{agent:true,steps:[]}`；agent 分支回调重写（onStepStart→appendAgentStep 等，onText→appendAgentStepText，onStepEnd finish==="final" 时去前缀提升为 content），不再调 `appendToAssistantThinking`。
- 测试
  - [backend/tests/test_agent_service_v2.py](backend/tests/test_agent_service_v2.py)：更新 5 用例加 steps/agent/retrieved 断言；新增 `test_wrap_skill_as_tool_stashes_metadata`（EchoSkill `_last_metadata=={"length":5}`）、`test_step_events_pair_on_every_path`（final/tool/max_steps 各路径 step_start/step_end 配对）。
  - [backend/tests/test_agent_service.py](backend/tests/test_agent_service.py)：phase-1 回归 `test_single_step_final_answer` 断言 `events[0]=="step_start"`（原断言 `=="thinking"`）。
  - [frontend/tests/components/AgentTrace.test.tsx](frontend/tests/components/AgentTrace.test.tsx)（新增 7 用例）：N 步 N 卡片、finish 徽标、retrieved 非空时 observation 折进 summary、retrieved null 时显示 observation、折叠/展开、空 steps、chunk 文本渲染。
  - [frontend/tests/hooks/useChatStream.test.ts](frontend/tests/hooks/useChatStream.test.ts)：重写 agent 测试用 step-bounded SSE，断言 `metadata.steps.length===2`、`steps[0].finish==="tool"`、`steps[1].finish==="final"`、`content==="Final answer."`（前缀已去）、`thinking` 为空；新增 retrieved chunks 入 steps + step_end error 保留 partial step 用例。

### 验证

- 后端：`cd backend && uv run pytest -q` → **87 passed**（原 85 + 2 新增）。
- 前端：`cd frontend && npm run test` → **23 passed**（原 15 + 7 AgentTrace + 1 新增 useChatStream）；`npm run build` 成功；`npm run lint` 仅 1 个**预先存在**的 `useConversation.ts` 警告（本次未新增）。
- `npx tsc -p tsconfig.app.json --noEmit` 通过。

### 向后兼容

- 后端同时发扁平 + 结构化事件；旧前端 switch 无新 case → 静默 fall through，扁平事件保留 `step:N`。
- 前端 agent 消息三分支兜底：旧 2a/2b-i 持久化消息（`metadata.agent && thinking 非空无 steps`）仍渲染 ThinkingBlock。
- 后端三处 persist 都写 `agent:True`+`steps`，reload 后标记/轨迹在。

### 已知限制

- 手动 E2E（Agent 模式 + 选 KB + 多步 prompt 触发 retrieve_notes → step 卡片 / retrieved chunks 卡片 / 正文只留最终答案 / 中途 abort→末卡 finish="error" 徽标）按计划执行但未固化为自动化用例，依赖上文的脚本化测试覆盖。
- 外层 CancelledError 不发 step_end（内层已覆盖流式 cancel，step_number 可能未绑定）——属设计取舍，非缺陷。

## 十七、本次工作记录（修复 Agent 无工具死循环 + KB 未选提示，2026-07-22）

用户实测 2b-ii 后发现两个 bug（trace 见对话）：Agent 模式问「hw5 是我最近学的课程的作业……」时，因 KB 未选导致 `retrieve_notes` 没挂载（`tools=[]`），agent 每步输出 `Action: none` → 收到 `_NO_TOOL_OBSERVATION`「无可用工具，请基于已知信息继续推理」→ 模型再纠结一轮 → 又 `Action: none`……空转到 `max-steps-exceeded`（8 步），正文堆满重复的通用建议。根因：`tools=[]` 时 ReAct 循环仍无条件运行，无 escape。

**用户确认的两个决策**：(1) 无工具时**跳过 ReAct 直接作答**（单次流式生成，不跑 Thought/Action 循环）；(2) KB 未选时**前端拦 + 后端兜底**——前端提示但不阻止发送，后端在 `tools=[]` 时优雅降级为直接作答。

**不修的**（超范围/模型层）：GLM 在 ReAct 文本里渗出 `<|begin_of_action|>`/`<|tool_call|>` 原生 function-calling token（跳过 ReAct 的直接作答路径恰好绕开，无 `Action:` 触发）；「有工具但连续 `Action: none`」的 escape hatch（用户只选了「跳过 ReAct」，不加 none 计数器，保持改动最小）。

### 改动文件

- 后端
  - [backend/app/services/agent_service.py](backend/app/services/agent_service.py)：新增 `_DIRECT_ANSWER_TEMPLATE` 常量（禁止 ReAct/Thought/Action 格式）；在 `stream_agent_chat` 的 `persist_done`/`persist_error` 定义后、外层 `try:` 前插入 early-branch——`not tools` 时用 direct 模板重建 messages（`_build_initial_messages` 已 prepend SystemMessage，直接调用即得），单步流式 `step_start`→thinking/text→`step_end(finish="final")`→`done`，复用 `chat_model`/`assistant_msg`/`persist_*`；`metadata` 形状与 ReAct 一致（`agent:True`/`steps`/`tool_calls:[]`），reload 后前端三分支仍走 AgentTrace。直接作答 text 原样进 content（无 `Final Answer:` 前缀剥离——direct prompt 禁止该格式）。
  - [backend/app/routers/agent.py](backend/app/routers/agent.py)：`skills = list(iter_skills())` 处加注释说明「无 KB + 无注册 skill 时 `tools=[]` → AgentService 跳过 ReAct 直接作答，不崩」。
- 前端
  - [frontend/src/components/WorkspaceLayout.tsx](frontend/src/components/WorkspaceLayout.tsx)：`handleSend` 在 `selectedModel` guard 后加 `agentMode && !selectedKbId` toast 提示（warning，「未选择知识库：本轮 Agent 将直接作答，无法检索笔记」），**不阻止发送**——agent 模式不等于必须检索，强制拦会误伤无需 KB 的提问（如「写首诗」）。
  - [frontend/src/components/InputArea.tsx](frontend/src/components/InputArea.tsx)：`agentMode` 提示段落里条件渲染无 KB 警告（amber 文字「未选择知识库，将无法检索笔记，直接作答」）；`selectedKbId` 直接从 store 读（同 ChatHeader 模式，避免 prop drilling）。
- 测试
  - [backend/tests/test_agent_service_v2.py](backend/tests/test_agent_service_v2.py)：新增 `test_no_tools_skips_react_direct_answer`（`skills=[]` → 单步直接作答，无 action/observation/warning 事件，`content`/`steps[0].text` 原样，`finish=="final"`，仅消耗 1 个 model turn）；`test_single_step_final_answer`/`test_max_steps_exceeded`/`test_abort_persists_metadata_aborted` 改挂 `skills=[EchoSkill()]` 保持 ReAct 路径（否则 `tools=[]` 触发 direct 分支，max-steps 永不触发、thinking 断言失败）。
  - [backend/tests/test_agent_service.py](backend/tests/test_agent_service.py)（phase-1 回归）：导入 `EchoSkill`，5 个 `stream_agent_chat` 调用点全挂 `skills=[EchoSkill()]`（multi-step/max-steps/exploding/abort 测试断言 `msg.thinking` 含 step 内容，direct 分支 thinking 为空会失败）。

### 验证

- 后端：`cd backend && uv run pytest -q` → **88 passed**（原 87 + 1 新增 direct-answer）。
- 前端：`cd frontend && npm run test` → **23 passed**（无新增测试，UI 改动由现有 agent 测试间接覆盖）；`npm run build` 成功；`npm run lint` 仅 1 个**预先存在**的 `useConversation.ts` 警告；`tsc --noEmit` 通过。
- 手动 E2E（未固化）：Agent 模式 + 不选 KB + 问「hw5 ……」→ 不再死循环，单步直接作答，AgentTrace 一张卡片 finish="final"，正文是模型直接回答，toast 提示「未选择知识库」；Agent 模式 + 选含 hw5 的 KB + 同问题 → `retrieve_notes` 挂载成功，retrieved 卡片显示 hw5 内容。

### 设计取舍

- **KB 未选拦而不阻**：toast + inline 提示，不 `return`。理由：agent 模式 ≠ 必须检索，强制拦误伤无需 KB 的提问；后端兜底已保证不崩。把「是否需要检索」的选择权交给用户。
- **direct 分支复用 AgentTrace 契约**：单步 `step_start`/`step_end(finish="final")` + `metadata.agent`/`steps`，前端无需特殊处理，一张 trace 卡片 + 正文提升逻辑（`onStepEnd finish==="final"` 去 `Final Answer:` 前缀——direct text 无此前缀，regex 不匹配，原样保留）。
- **不加 none 计数器 escape**：用户只选「跳过 ReAct」，`tools=[]` 已是唯一死循环入口；有工具时连续 `Action: none` 是模型/prompt 层面问题（含 GLM 原生 token 渗出），留后续。
