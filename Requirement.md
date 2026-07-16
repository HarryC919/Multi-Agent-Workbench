# 智能对话工作台 UI 框架技术方案（后端 FastAPI 版）

**版本**：v1.0  
**更新日期**：2026-07-09

---

## 1. 概述

本方案描述了一个类 Kimi Workspace 的**纯文本多厂商 AI 对话前端界面**。前端使用 React + TypeScript + Vite，后端采用 **Python + FastAPI**，统一代理 OpenAI、Anthropic 及其他厂商 API，提供流式输出、思考强度调节、文本文件上传及 RAG/Skills 扩展预留。当前版本**不涉及多模态、Agent 或工具调用**。

---

## 2. 需求分析

### 2.1 功能需求

- **多会话管理**：创建、切换、删除、重命名会话，会话列表搜索。
- **纯文本对话**：支持多轮对话，仅处理文本消息。
- **流式输出**：仿打字机效果，逐字/逐块展示模型回复。
- **文件上传（限定文本）**：可上传 `.txt`、`.md`、`.pdf`（解析文本内容）等文本型文件，上传后在对话中作为上下文附件。
- **模型切换**：在输入区提供模型选择下拉框，可切换不同厂商/模型，切换后对话继续（需注意上下文兼容）。
- **思考强度调节**：提供滑块或选项（如 temperature、top_p、推理深度等），影响模型输出风格。
- **多厂商兼容**：后端统一代理，适配 OpenAI 和 Anthropic 两大协议，预留扩展点以支持其他厂商。
- **RAG 预留**：界面预留“知识库选择”入口，后端架构支持检索增强生成流程。
- **Skills 预留**：左侧栏或顶部预留“技能”菜单，后续可挂载自定义处理逻辑。
- **无 Agent / 工具调用**：当前版本仅实现对话功能，不涉及 function calling 或工具调用。

### 2.2 非功能需求

- 前端性能：消息列表虚拟滚动，支持 10k+ 消息。
- 可扩展性：新增厂商只需添加配置或少量适配器代码。
- 部署简单：前后端分离，后端可通过 Docker 部署。
- 安全：API Key 仅存储在后端，前端不直接暴露。

---

## 3. 技术选型（后端部分）

| 模块               | 选型                                                         |
| ------------------ | ------------------------------------------------------------ |
| Web 框架           | FastAPI（异步高性能，完美支持 Server-Sent Events）           |
| 流式响应           | `StreamingResponse` + `async generator`                     |
| HTTP 客户端        | `httpx`（异步请求各厂商 API）                                |
| 多厂商适配         | 策略模式 + 适配器工厂                                        |
| 文件解析           | `pdfplumber`（PDF）、`python-docx`（Word）、纯文本直接读取    |
| 配置与密钥管理     | `pydantic-settings` + `.env` 文件                            |
| 数据存储（会话）   | 初期可使用内存字典或 SQLite（可通过 `sqlalchemy` 扩展）      |
| RAG 预留           | 后续集成 `chromadb` / `qdrant-client`，接口预留              |
| Skills 预留        | FastAPI 路由预留，处理逻辑后续挂载                           |

---

## 4. 系统架构（后端）

```
┌─────────────┐
│   React 前端  │
└──────┬──────┘
       │ HTTP / SSE
┌──────┴────────────────────────────────────────────────┐
│                   FastAPI 后端                          │
│  ┌────────────────┐  ┌──────────────────────────────┐ │
│  │ 路由层           │  │ 模型适配器工厂               │ │
│  │ /api/chat       │  │  - OpenAIAdapter             │ │
│  │ /api/upload     │  │  - AnthropicAdapter          │ │
│  │ /api/models     │  │  - GeminiAdapter             │ │
│  │ /api/convs ...  │  │  - OpenAICompatAdapter (通用) │ │
│  └────────────────┘  └──────────────────────────────┘ │
│  ┌────────────────┐  ┌──────────────────────────────┐ │
│  │ 文件解析服务     │  │ 配置管理 (.env)              │ │
│  └────────────────┘  └──────────────────────────────┘ │
│  ┌────────────────┐  ┌──────────────────────────────┐ │
│  │ RAG 预留接口     │  │ Skills 预留路由              │ │
│  └────────────────┘  └──────────────────────────────┘ │
└───────────────────────────────────────────────────────┘
```

---

## 5. 后端详细设计（FastAPI）

### 5.1 依赖安装

本机环境使用uv管理项目

```bash
# 先初始化uv
uv add fastapi uvicorn httpx python-multipart pdfplumber python-docx pydantic-settings
```

### 5.2 配置管理

创建 `.env` 文件，存储各厂商的 API Key 和 Base URL：

```
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.openai.com/v1
ANTHROPIC_API_KEY=sk-ant-xxx
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
GLM_API_KEY=xxx
GLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
KIMI_API_KEY=sk-xxx
KIMI_BASE_URL=https://api.moonshot.cn/v1
MINIMAX_API_KEY=xxx
MINIMAX_BASE_URL=https://api.minimax.chat/v1
MIMO_API_KEY=xxx
MIMO_BASE_URL=...
QWEN_API_KEY=sk-xxx
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
GEMINI_API_KEY=xxx
```

使用 `pydantic-settings` 加载：

```python
# config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    openai_api_key: str
    openai_base_url: str = "https://api.openai.com/v1"
    anthropic_api_key: str
    deepseek_api_key: str
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    # ... 其他厂商
    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'

settings = Settings()
```

### 5.3 模型适配器设计

定义统一的适配器接口（抽象基类），各厂商实现自己的流式调用。

```python
# adapters/base.py
from abc import ABC, abstractmethod
from typing import AsyncIterator, Dict, Any, List

class StreamChunk:
    def __init__(self, content: str, finish_reason: str = None):
        self.content = content
        self.finish_reason = finish_reason

class BaseAdapter(ABC):
    @abstractmethod
    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        effort: float,
        **kwargs
    ) -> AsyncIterator[StreamChunk]:
        pass
```

#### 5.3.1 OpenAI 及兼容厂商适配器

绝大多数国内模型（DeepSeek、GLM、Kimi、Qwen、MiniMax、Mimo）都提供 OpenAI 兼容接口，只需一个通用适配器即可。

```python
# adapters/openai_adapter.py
import httpx
import json
from typing import AsyncIterator
from .base import BaseAdapter, StreamChunk

class OpenAIAdapter(BaseAdapter):
    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=60.0)

    def _map_effort_to_params(self, effort: float):
        # 将 0-1 映射到 temperature、top_p
        temperature = 0.2 + effort * 0.8
        top_p = 0.7 + effort * 0.3
        return {"temperature": round(temperature, 2), "top_p": round(top_p, 2)}

    async def stream_chat(
        self, messages, model, effort, **kwargs
    ) -> AsyncIterator[StreamChunk]:
        params = {
            "model": model,
            "messages": messages,
            "stream": True,
            **self._map_effort_to_params(effort),
        }
        # 部分模型不支持 temperature（如 o1），可在此按模型覆盖
        if "o1" in model or "o3" in model:
            params.pop("temperature", None)
            params.pop("top_p", None)

        async with self.client.stream(
            "POST",
            f"{self.base_url}/chat/completions",
            json=params,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: ") and not line.startswith("data: [DONE]"):
                    data = json.loads(line[6:])
                    delta = data["choices"][0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield StreamChunk(content=content)
                    if data["choices"][0].get("finish_reason"):
                        yield StreamChunk(content="", finish_reason=data["choices"][0]["finish_reason"])
```

#### 5.3.2 Anthropic 适配器

Claude 的 Messages API 需要将 OpenAI 格式的 `messages` 转换，并且流式协议不同。

```python
# adapters/anthropic_adapter.py
import httpx
import json
from typing import AsyncIterator
from .base import BaseAdapter, StreamChunk

class AnthropicAdapter(BaseAdapter):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=60.0)
        self.base_url = "https://api.anthropic.com/v1"

    def _map_effort(self, effort: float) -> float:
        return round(0.2 + effort * 0.8, 2)

    def _convert_messages(self, messages):
        # Anthropic 要求 system 独立，role 必须为 user/assistant
        system_msg = ""
        converted = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg += msg["content"] + "\n"
            else:
                converted.append({"role": msg["role"], "content": msg["content"]})
        return system_msg.strip(), converted

    async def stream_chat(
        self, messages, model, effort, **kwargs
    ) -> AsyncIterator[StreamChunk]:
        system, msgs = self._convert_messages(messages)
        payload = {
            "model": model,
            "messages": msgs,
            "max_tokens": 4096,
            "temperature": self._map_effort(effort),
            "stream": True,
        }
        if system:
            payload["system"] = system

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        async with self.client.stream(
            "POST", f"{self.base_url}/messages", json=payload, headers=headers
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    if data["type"] == "content_block_delta":
                        yield StreamChunk(content=data["delta"]["text"])
                    elif data["type"] == "message_stop":
                        yield StreamChunk(content="", finish_reason="stop")
```

#### 5.3.3 Gemini 适配器

使用 Google AI SDK 或 REST API，此处简化为 REST 示例。

```python
# adapters/gemini_adapter.py
import httpx
import json
from typing import AsyncIterator
from .base import BaseAdapter, StreamChunk

class GeminiAdapter(BaseAdapter):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=60.0)

    async def stream_chat(
        self, messages, model, effort, **kwargs
    ) -> AsyncIterator[StreamChunk]:
        # 转换消息格式为 Gemini 的 contents
        contents = []
        for msg in messages:
            role = "user" if msg["role"] in ["user", "system"] else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse&key={self.api_key}"
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.2 + effort * 0.8,
                "topP": 0.7 + effort * 0.3,
            },
        }
        async with self.client.stream("POST", url, json=payload) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    try:
                        text = data["candidates"][0]["content"]["parts"][0]["text"]
                        yield StreamChunk(content=text)
                    except (KeyError, IndexError):
                        pass
```

### 5.4 适配器工厂

根据模型名称或配置返回正确的适配器实例。

```python
# adapters/factory.py
from .openai_adapter import OpenAIAdapter
from .anthropic_adapter import AnthropicAdapter
from .gemini_adapter import GeminiAdapter
from config import settings

ADAPTER_REGISTRY = {
    "openai": lambda: OpenAIAdapter(settings.openai_api_key, settings.openai_base_url),
    "deepseek": lambda: OpenAIAdapter(settings.deepseek_api_key, settings.deepseek_base_url),
    "glm": lambda: OpenAIAdapter(settings.glm_api_key, settings.glm_base_url),
    "kimi": lambda: OpenAIAdapter(settings.kimi_api_key, settings.kimi_base_url),
    "minimax": lambda: OpenAIAdapter(settings.minimax_api_key, settings.minimax_base_url),
    "mimo": lambda: OpenAIAdapter(settings.mimo_api_key, settings.mimo_base_url),
    "qwen": lambda: OpenAIAdapter(settings.qwen_api_key, settings.qwen_base_url),
    "anthropic": lambda: AnthropicAdapter(settings.anthropic_api_key),
    "gemini": lambda: GeminiAdapter(settings.gemini_api_key),
}

def get_adapter(model_id: str):
    # model_id 示例： "claude-3-opus", "gpt-4o", "deepseek-chat"
    if model_id.startswith("claude"):
        return ADAPTER_REGISTRY["anthropic"]()
    elif model_id.startswith("gemini"):
        return ADAPTER_REGISTRY["gemini"]()
    elif model_id.startswith("gpt") or model_id.startswith("o1"):
        return ADAPTER_REGISTRY["openai"]()
    else:
        # 通过厂商映射表，这里简化：根据配置中模型前缀判断
        # 实际项目可以维护一个 model -> vendor 的配置
        for vendor in ["deepseek", "glm", "kimi", "minimax", "mimo", "qwen"]:
            # 此处仅为示例，真实场景应查询数据库或配置
            pass
        # 默认尝试 OpenAI 兼容
        return ADAPTER_REGISTRY["deepseek"]()  # 此处为演示
```

更规范的做法：维护一个模型清单文件（如 `models.json`），包含 `model_id`、`vendor`、`adapter_type`，工厂根据 `vendor` 实例化。

### 5.5 文件上传与文本提取

```python
# services/file_parser.py
import pdfplumber
import docx
from io import BytesIO

def extract_text_from_pdf(file_bytes: bytes) -> str:
    text = ""
    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    return text

def extract_text_from_docx(file_bytes: bytes) -> str:
    doc = docx.Document(BytesIO(file_bytes))
    return "\n".join([para.text for para in doc.paragraphs])

def extract_text_from_txt(file_bytes: bytes) -> str:
    return file_bytes.decode("utf-8", errors="ignore")

def parse_uploaded_file(filename: str, file_bytes: bytes) -> str:
    if filename.endswith(".pdf"):
        return extract_text_from_pdf(file_bytes)
    elif filename.endswith(".docx"):
        return extract_text_from_docx(file_bytes)
    else:
        return extract_text_from_txt(file_bytes)
```

### 5.6 API 路由实现

#### 5.6.1 对话接口（核心）

```python
# routes/chat.py
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
from adapters.factory import get_adapter
import json

router = APIRouter()

class ChatMessage(BaseModel):
    role: str
    content: str

class FileContent(BaseModel):
    name: str
    content: str

class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    model: str
    messages: List[ChatMessage]
    effort: float = 0.7
    files: List[FileContent] = []
    stream: bool = True

async def generate_stream(request: ChatRequest):
    adapter = get_adapter(request.model)
    # 如果有文件，将文件内容附加到最后一条用户消息
    messages = [m.dict() for m in request.messages]
    if request.files:
        file_texts = "\n\n".join(
            [f"[文件: {f.name}]\n{f.content}" for f in request.files]
        )
        # 找到最后一条 user 消息
        for i in range(len(messages)-1, -1, -1):
            if messages[i]["role"] == "user":
                messages[i]["content"] += f"\n\n{file_texts}"
                break

    try:
        async for chunk in adapter.stream_chat(messages, request.model, request.effort):
            yield f"data: {json.dumps({'type': 'text', 'content': chunk.content})}\n\n"
            if chunk.finish_reason:
                yield f"data: {json.dumps({'type': 'done', 'finish_reason': chunk.finish_reason})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

@router.post("/chat")
async def chat_endpoint(request: ChatRequest):
    if not request.stream:
        raise HTTPException(status_code=400, detail="Only streaming is supported")
    return StreamingResponse(
        generate_stream(request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

#### 5.6.2 文件上传接口

```python
# routes/upload.py
from fastapi import APIRouter, UploadFile, File, HTTPException
from services.file_parser import parse_uploaded_file
import uuid

router = APIRouter()

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    allowed_ext = (".txt", ".md", ".pdf", ".docx")
    if not file.filename.endswith(allowed_ext):
        raise HTTPException(status_code=400, detail="Only text-based files are allowed")
    content_bytes = await file.read()
    text = parse_uploaded_file(file.filename, content_bytes)
    file_id = str(uuid.uuid4())
    # 实际项目中可将 file_id 和文本存储到数据库，这里直接返回
    return {"file_id": file_id, "name": file.filename, "text_content": text}
```

#### 5.6.3 模型列表接口

```python
# routes/models.py
from fastapi import APIRouter

router = APIRouter()

AVAILABLE_MODELS = [
    {"id": "gpt-4o", "vendor": "openai", "name": "GPT-4o"},
    {"id": "claude-3-5-sonnet", "vendor": "anthropic", "name": "Claude 3.5 Sonnet"},
    {"id": "deepseek-chat", "vendor": "deepseek", "name": "DeepSeek Chat"},
    # ... 添加所有需要的模型
]

@router.get("/models")
async def list_models():
    return {"models": AVAILABLE_MODELS}
```

### 5.7 RAG 与 Skills 预留

- 在 `ChatRequest` 中增加可选字段 `rag_knowledge_base_id: Optional[str] = None`，当前不处理。
- Skills 路由预留：`router.post("/skills/{skill_name}")`，返回提示“技能暂未开放”。

---

## 6. 前端部分

### 6.1 技术选型

| 模块         | 选型                                 |
|--------------|--------------------------------------|
| 框架         | React 18 + TypeScript                |
| 构建工具     | Vite                                 |
| UI 组件库    | shadcn/ui + Tailwind CSS             |
| 状态管理     | Zustand                              |
| Markdown 渲染| react-markdown + remark-gfm          |
| 代码高亮     | react-syntax-highlighter              |
| 虚拟滚动     | @tanstack/react-virtual              |
| 文件上传     | react-dropzone                       |
| 流式接收     | EventSource / fetch ReadableStream   |
| 工具函数     | date-fns, nanoid                     |

前端技术选型、布局、状态管理、流式处理等保持原文档不变。只需调整 API 请求地址指向 FastAPI 后端，并注意文件上传后取回 `text_content`，发送聊天时携带。

### 6.2 前端设计

#### 6.2.1 前端架构

┌──────────────────────────────────────────────────────┐
│                       前端 (SPA)                       │
│  ┌──────────┐  ┌──────────┐  ┌─────────────────────┐ │
│  │ 聊天界面  │  │ 会话管理  │  │ 输入区 (文件/设置)   │ │
│  └──────────┘  └──────────┘  └─────────────────────┘ │
│  状态管理 (Zustand)          API 客户端 (Fetch/SSE)    │
└─────┬────────────────────────────────────────────────┘
      │ HTTP/SSE
┌─────────────┐
│ FastAPI 后端 │
└─────────────┘
#### 6.2.2 组件树与布局

```
App
├── WorkspaceLayout (flex h-screen)
│   ├── Sidebar (可拖拽宽度)
│   │   ├── SidebarHeader (新建会话、搜索)
│   │   ├── ConversationList (虚拟滚动列表)
│   │   └── SkillsPanel (预留，可折叠)
│   ├── MainArea (flex flex-col flex-1)
│   │   ├── ChatHeader (当前会话标题、RAG知识库选择、Skills触发)
│   │   ├── MessageList (虚拟滚动)
│   │   │   ├── MessageItem (用户)
│   │   │   └── MessageItem (助手, Markdown渲染)
│   │   └── InputArea
│   │       ├── FilePreview (已上传文本文件标签)
│   │       ├── ModelSelector (下拉)
│   │       ├── EffortSlider (思考强度)
│   │       ├── TextArea (自动高度)
│   │       └── SendButton
```

#### 6.2.3 核心状态 (Zustand Store)

```typescript
interface WorkspaceState {
  conversations: Conversation[];
  activeId: string | null;
  isStreaming: boolean;

  // 当前输入区状态
  inputText: string;
  attachedFiles: UploadedFile[];
  selectedModel: string;       // e.g. "claude-3-opus"
  effort: number;              // 0-1 或预设档位

  // 动作
  setActive: (id: string) => void;
  createConversation: () => string;
  addMessage: (convId: string, msg: Message) => void;
  appendToAssistant: (convId: string, chunk: string) => void;
  updateMessageStatus: (convId: string, msgId: string, status: string) => void;
  setModel: (model: string) => void;
  setEffort: (value: number) => void;
  // ...
}
```

#### 6.2.4 流式交互流程

1. 用户在输入区填入文本并点击发送（或 Enter）。
2. 调用后端 `/api/chat` 接口，请求体包含：
   - `messages`: 历史消息数组 (role + content)
   - `model`: 所选模型标识
   - `effort`: 强度参数
   - `files`: 已上传文件的文本内容 (可选)
3. 后端返回 SSE 流，前端使用 `EventSource` 或 `fetch` 读取 `ReadableStream`。
4. 每收到一个 data chunk，通过 `appendToAssistant` 追加到当前活动的助手消息中，React 实时渲染 Markdown。
5. 流结束后，将消息状态设为 `done`。

**调整点**：

- 文件上传后返回的 JSON 包含 `text_content`，前端存于状态中，在发送消息时将其放入请求体的 `files` 数组。
- 模型列表从 `/api/models` 拉取，构建下拉选项。
- 流式接收与之前相同，使用 `fetch` 读取 `ReadableStream` 或 `EventSource`（注意 FastAPI SSE 要求 `text/event-stream`）。

---

## 7. 部署建议

- **后端**：使用 `uvicorn` 启动 FastAPI 应用。  
  ```bash
  uvicorn main:app --host 0.0.0.0 --port 8000 --reload
  ```
  生产环境可用 `gunicorn` + `uvicorn.workers.UvicornWorker`。
- **前端**：`npm run build` 产出静态文件，由 Nginx 代理 `/api` 到后端 8000 端口。
