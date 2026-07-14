# 项目进度跟踪

> 最后更新：2026-07-14

## 一、总体状态

| 模块 | 状态 | 说明 |
| ---- | ---- | ---- |
| 后端框架（FastAPI + SQLAlchemy async） | ✅ 完成 | 路由、模型、会话服务、适配器层均已搭建 |
| 前端框架（React + Zustand + Vite） | ✅ 完成 | 布局、侧边栏、聊天区、输入区、状态管理 |
| 模型列表拉取 | ✅ 可用 | `/api/models` 从 DB 读取 seed 模型 |
| 多 vendor 适配器（OpenAI/Anthropic/Gemini/兼容） | ✅ 完成 | OpenAI 兼容流式已实测打通（DeepSeek 200） |
| 单轮对话（流式） | ✅ 可用 | 选有 key 的模型（DeepSeek/Kimi）可正常对话 |
| 连续对话（多轮） | ✅ 已修复 | 每轮创建独立 assistant 占位；流结束兜底复位；`abort` 已接到 UI |
| 文件上传与发送 | ✅ 已修复 | 支持 txt/md/pdf/docx 及常见代码文件；字段映射已修复 |
| 消息列表渲染（无重叠） | ✅ 已修复 | 虚拟列表加 `measureElement` 动态测高，流式增长不再重叠 |
| 会话右键菜单 + 删除确认 | ✅ 已修复 | 右键 / ⋯ 按钮双入口；删除前确认弹窗 |
| 开始界面直接发送自动建会话 | ✅ 已修复 | 空状态下发送自动 `createConversation` 再发送 |
| 模型管理 UI（CRUD） | ✅ 已完成 | ChatHeader 入口 → Modal 弹窗，含列表/启停/新增/编辑/删除 |
| 模型级 API Key | ✅ 已完成 | ModelConfig 加 api_key 字段；compatible 模型可填 key，factory 优先用模型 key 回退 .env；key 不回传明文 |
| 会话标题自动生成 | ✅ 已实现 | 后端 service 层按首条消息前 50 字生成（已验证） |
| 凭证/环境配置 | ✅ 已修复 | 见 [已完成的修复](#三已完成的修复) |

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

- [x] **修复问题 2（文件发送）**：`upload.ts` 加 camelCase 转换。
- [x] **修复问题 1（连续对话）**：`sendChatStream` 加流结束兜底复位 `isStreaming`；把 `abort` 接到 UI。
- [x] **修复消息列表重叠**：虚拟列表动态测高。
- [x] **右键删除会话 + 确认弹窗**。
- [x] **问题待修复**：在开始界面直接在下面的对话框输入问题发送后不会自动生成新会话 → 已修复（`WorkspaceLayout.handleSend` 空状态先 `createConversation`）。
- [x] **端到端验证连续对话 + 文件发送两个场景**。
- [x] **会话标题自动生成（当前后端已实现，前端需验证）**：已确认后端 `conversation_service.add_message` 按首条消息前 50 字生成标题，修好"开始界面发送"后自动生效。
- [x] **模型管理 UI（后端 CRUD 已就绪，前端已接）**：ChatHeader "模型管理" 按钮 → Modal 弹窗，列表 + 启停 + 新增/编辑表单 + 删除确认。

---

## 十、关键技术细节备忘

- 后端启动：`cd backend && uv run uvicorn main:app --reload`（注意入口是顶层 `main.py`，不是 `app.main`）。
- 前端启动：`cd frontend && npm run dev`（5173，已配 `/api` 代理到 8000）。
- `.env` 现在只配了 `DEEPSEEK_API_KEY`、`KIMI_API_KEY`，其余 vendor 留空。
- DB：`backend/workbench.db`（SQLite + aiosqlite），seed 了 11 个模型，全部 `is_active=1`。
- 适配器约定：DeepSeek/Kimi/GLM 走 `openai_compatible`；OpenAI 走 `openai`；Anthropic 走 `anthropic`；Gemini 走 `gemini`。
