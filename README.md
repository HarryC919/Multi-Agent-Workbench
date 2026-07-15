# AI Chat Workbench

智能对话工作台（类 Kimi Workspace），前后端分离实现。

## 技术栈

- **前端**：React 19 + TypeScript + Vite + Tailwind CSS v4 + shadcn/ui
- **后端**：FastAPI + SQLAlchemy (async SQLite) + httpx

## 功能特性

- 多厂商模型适配：OpenAI / Anthropic / Gemini 原生适配器，DeepSeek / GLM / Kimi 走 OpenAI 兼容协议
- 流式对话：基于 SSE 的逐 token 流式输出
- **深度思考（Thinking）**：输入区可一键开关思考模式
  - 开启后，模型在正式回答前流式输出思考过程
  - 思考内容以可折叠区块呈现，与回复正文在字体大小和颜色上有区分
  - 流式时自动展开、正文开始后自动折叠，也可手动切换
  - 思考内容持久化到数据库，刷新或重开会话后仍可见
  - 生效范围：Anthropic（原生 extended thinking）与 OpenAI 兼容厂商的 reasoning 模型（DeepSeek / GLM / Kimi，解析 `reasoning_content`）；Gemini 暂不支持

## 快速开始

### 后端

```bash
cd backend
cp .env.example .env
# 编辑 .env 填入你的 API Key, DeepSeek, GLM 和 Kimi 请填入 OpenAI 的 BaseURL
uv sync
uv run uvicorn main:app --reload
```

后端默认运行在 http://localhost:8000

### 前端

```bash
cd frontend
npm install
npm run dev
```

前端默认运行在 http://localhost:5173，并已配置代理 `/api` 到后端。

## 开发计划

详见 [DEVELOPMENT_PLAN.md](./DEVELOPMENT_PLAN.md)。
