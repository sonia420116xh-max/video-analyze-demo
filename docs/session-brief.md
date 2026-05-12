# 窗口交接摘要

这个文件用于在不同 Codex 窗口之间交接上下文。保持简短；当任务方向变化或完成一个有用检查点时更新它。

## 当前重点

- 最近处理：多模型视频拆解工作流增强。
- 当前实现：
  - `claude-sonnet-4-5-20250929` 已作为 gptproto 模型接入，走 `/v1/chat/completions` 的 openai-format File Analysis，关键帧用 `file.file_data` 传 data URL。
  - `gpt-4o` 仍走 gptproto `/v1/responses`，`gemini-2.5-pro` 仍走 `/v1/chat/completions`。
  - `run_analysis_pipeline` 在“开始调用 AI 分析”前打印视频转音频和字幕/ASR 耗时，并把 `audio_extract_seconds`、`asr_seconds` 写入 job timing。
  - 多模型结果卡片中，正在重新拆解的模型会显示“停止生成”按钮；点击后二次确认并调用后端取消接口。取消重拆任务会保留原分析结果并恢复记录状态为已完成。
- 之前已实现：`/api/analyses` 合并已完成 `analyses` 记录，以及 `analysis_jobs` 中仍处于 `queued`/`processing` 的初始上传任务占位记录；`failed`/`canceled` 且没有生成 `analysis_id` 的孤立 job 不再常驻显示为视频记录。

## 当前仓库状态

- 创建这套交接文档之前，已经存在改动的文件：
  - `frontend/src/views/VideoAnalyze.vue`
  - `tests/test_storage.py`
- 这些改动应视为用户/当前工作中的改动，不要随意回滚。
- 后端入口已迁移到 `backend/main.py`；根目录不再保留 `main.py` 兼容入口。
- 本次上下文交接设置新增或更新：
  - `AGENTS.md`
  - `docs/session-brief.md`
  - `backend/__init__.py`
  - `backend/main.py`
  - `README.md`
- 最近改动还涉及：
  - `docs/project-structure.md`：补充 SQLite 表语义和历史列表合并规则。
  - `backend/main.py`：列表接口合并运行中的初始上传任务；启动时才清理重启遗留任务；job helper 支持测试传入 `db_path`；新增 Claude 模型分支和音频/字幕耗时日志。
  - `frontend/src/views/VideoAnalyze.vue`：历史列表 pending 占位项显示状态，点击后恢复轮询；多模型结果卡片支持停止正在重拆的模型任务并保留原结果。
  - `tests/test_storage.py`：覆盖 pending job 列表行为、terminal job 过滤、job 测试库隔离、Claude File Analysis 请求格式、音频/字幕耗时日志顺序。

## 最近验证

- `python3 -m unittest discover -s tests`：29 个测试通过。输出中仍有既有 MoviePy `/tmp/demo.mp4` 缺文件打印，但退出码为 0。
- `cd frontend && pnpm build`：构建通过，仍有 Vite/Rollup 的第三方注释和 chunk size 警告。

## 注意事项

- 用户曾在聊天中贴出 gptproto key；后续不要复制到新文件或文档，建议用户在平台轮换。
- 本机 macOS 系统代理为 `127.0.0.1:6666`；此前一次 gptproto 请求失败是 `ProxyError`，curl/Python 探测均证明 gptproto base 和 endpoint 可达，失败更像代理瞬断。

## 新窗口快速恢复提示词

开启新的 Codex 窗口后，粘贴这段：

```text
请先读取 AGENTS.md 和 docs/session-brief.md，然后运行 git status --short。
不要重新扫描全仓库；只读取和我接下来任务相关的文件。
当前任务是：<在这里写一句话>
```

或

```text
按 AGENTS.md 和 docs/session-brief.md 接着来。当前任务：XXX
```

## 怎么使用这个文件

### 正常工作流

1. 像平时一样在当前 Codex 窗口里工作。
2. 到达一个有用的检查点时，对 Codex 说：

```text
更新 session brief
```

3. Codex 应该把当前状态更新到这个文件里。
4. 更新后可以继续使用当前窗口。更新这个文件只是创建一个备份点，不代表必须立刻换窗口。
5. 当窗口太长，或者你想重新开始一个干净窗口时，打开新的 Codex 窗口，并粘贴上面的“新窗口快速恢复提示词”。

### 什么时候说“更新 session brief”

- 一个功能或修复到达阶段性检查点。
- 后端改动、前端改动、测试验证作为一个独立阶段完成。
- 排查问题时已经找到重要原因，但完整修复还没完成。
- 准备切换到另一个任务区域。
- 对话已经持续比较久，大约 20-30 分钟，或已经来回很多轮。
- 准备暂停工作、关电脑，或明天继续。
- Codex 开始像忘了前文一样：重复问已经回答过的问题，或者给出忽略之前决定的建议。

### 什么时候打开新窗口

- 更新这个文件后，如果当前窗口仍然稳定，可以继续用当前窗口。
- 如果当前对话很长、已经发生自动压缩、Codex 明显混乱，或者你要切换到一个大的新任务，就打开新窗口。
- 在新窗口里，让 Codex 只读取 `AGENTS.md`、本文件，以及和新任务直接相关的文件。

## 常用命令

- 后端测试：`python3 -m unittest discover -s tests`
- 后端开发服务：`PORT=8001 python3 -m backend.main`
- 前端构建：`cd frontend && pnpm build`
- 前端开发服务：`cd frontend && pnpm dev`

## 更新规范

- 在关闭长窗口之前，让 Codex 更新这个文件，记录：
  - 已经改了什么，
  - 还剩什么，
  - 运行过哪些命令以及结果，
  - 改动过哪些文件，
  - 仍然存在的风险或待决策问题。
- 尽量让这个文件保持在 100 行以内。长细节放到其他文档里，这里只写链接或摘要。
