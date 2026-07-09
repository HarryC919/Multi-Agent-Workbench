# AI Chat Workbench

智能对话工作台（类 Kimi Workspace），前后端分离实现。

## 技术栈

- **前端**：React 19 + TypeScript + Vite + Tailwind CSS v4 + shadcn/ui
- **后端**：FastAPI + SQLAlchemy (async SQLite) + httpx

## 快速开始

### 后端

```bash
cd backend
cp .env.example .env
# 编辑 .env 填入你的 API Key
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
