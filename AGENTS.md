# 项目上下文

这个仓库是一个 AI 视频分析 demo：后端使用 Python/FastAPI，前端使用 Vue 3 + Vite。

## 技术栈

- 后端：Python、FastAPI、SQLite、`requests`、`moviepy`、Pillow，可选 Whisper 相关库。
- 前端：Vue 3、Vite、Element Plus、Axios。
- 存储：本地文件在 `storage/` 目录下，SQLite 数据库在 `storage/analysis.db`。

## 常用命令

- 启动后端开发服务：`PORT=8001 python3 -m backend.main`
- 运行后端测试：`python3 -m unittest discover -s tests`
- 安装前端依赖：`cd frontend && pnpm install`
- 启动前端开发服务：`cd frontend && pnpm dev`
- 构建前端：`cd frontend && pnpm build`

## 重要文件

- `backend/main.py`：FastAPI 应用、模型路由、视频分析流程、持久化辅助函数、存储 API。
- `tests/test_storage.py`：后端单元测试，覆盖模型路由和存储行为。
- `frontend/src/views/VideoAnalyze.vue`：主前端工作流和分析页面。
- `README.md`：安装说明、模型环境变量、后端启动方式。
- `docs/session-brief.md`：给新 Codex 窗口使用的当前交接摘要。

## 项目特定说明

- `gemini-2.5-pro` 和 `gpt-4o` 通过 `gptproto` 调用。
- `gpt-4o` 使用 `https://gptproto.com/v1/responses`，内容格式是 `input_text` 和 `input_image`。
- `gemini-2.5-pro` 使用 `https://gptproto.com/v1/chat/completions`。
- `qwen-turbo` 使用 DashScope，需要 `DASHSCOPE_KEY`。
- OpenAI 直连的 `gpt4o` 和百度模型目前在模型选项里属于未实现。
- 前端默认把 `/api/*` 代理到 `http://127.0.0.1:8001`。

## 工作规则

- 修改行为前，先读取相关源文件和相关测试文件。
- 保留用户已有改动。工作区可能本来就是 dirty 状态。
- 除非任务明确要求，不要修改生成文件、调试文件、媒体文件：
  `storage/`、`frames/`、`videos/`、`debug_outputs/`、`frontend/dist/`、`*.db`、`*.mp4`。
- 不要提交密钥。`backend/main.py` 当前有默认 API key 相关值；不要把密钥扩散或复制到新文件。
- 后端行为变更优先补充聚焦的单元测试。
- 前端变更在可行时运行 `cd frontend && pnpm build`。

## 新窗口启动步骤

在这个项目里开启新的 Codex 窗口时：

1. 先读取本文件。
2. 再读取 `docs/session-brief.md`。
3. 运行 `git status --short`。
4. 只读取当前任务相关的文件，通常是 `backend/main.py`、`tests/test_storage.py` 和/或 `frontend/src/views/VideoAnalyze.vue`。
