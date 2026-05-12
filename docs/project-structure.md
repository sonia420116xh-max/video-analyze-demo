# 项目目录说明

这个项目由 FastAPI 后端和 Vue 3 前端组成。根目录里同时有源码、文档、测试，以及后端运行时生成的本地文件。

## 主要源码目录

| 路径 | 作用 | 是否建议提交 |
| --- | --- | --- |
| `backend/` | 后端 Python 包。`backend/main.py` 是 FastAPI 应用入口，包含模型调用、视频处理、存储 API 和后台任务。 | 是 |
| `frontend/` | 前端 Vue 3 + Vite 项目。主要页面在 `frontend/src/views/VideoAnalyze.vue`。 | 是 |
| `tests/` | 后端单元测试。当前主要测试模型路由、存储、任务和后处理行为。 | 是 |
| `docs/` | 项目文档、交接摘要和设计说明。 | 是 |

## 后端运行时目录

这些目录由后端运行时使用，通常不应提交到 git。

| 路径 | 作用 | 清理建议 |
| --- | --- | --- |
| `videos/` | 上传后待分析的临时视频目录。后端用 `TEMP_VIDEO_DIR` 读取这里的文件。 | 没有分析任务运行时可以清理。 |
| `frames/` | 临时抽帧目录。后端挂载为 `/frames`，前端分析过程中用它显示临时分镜图。 | 没有分析任务运行时可以清理。 |
| `debug_outputs/` | 调试输出目录，保存 ASR 文本、最终 prompt、视觉关键帧摘要等排查材料。 | 通常可以清理。 |
| `storage/` | 持久化存储目录，保存历史分析数据库、已保存视频、已保存分镜图和任务文件。 | 谨慎清理，删除会影响历史记录。 |
| `storage/videos/` | 已保存的原视频文件。历史分析详情会引用这里的视频。 | 谨慎清理。 |
| `storage/frames/` | 已保存的分镜图片。历史分析详情会引用这里的图片。 | 谨慎清理。 |
| `storage/jobs/` | 后台分析或重新分析任务使用的中间文件目录。 | 没有任务运行时可按需清理。 |
| `storage/analysis.db` | SQLite 数据库，保存分析历史和版本信息。 | 不要随意删除，除非确认要重置历史数据。 |

## SQLite 数据表语义

`storage/analysis.db` 目前主要保存三类数据：

| 表 | 作用 |
| --- | --- |
| `analyses` | 已完成并持久化的视频拆解主记录。历史列表里的正常视频记录来自这里。 |
| `analysis_versions` | 同一个视频在不同模型下的最新拆解结果。用于详情页的多模型版本和对比。 |
| `analysis_jobs` | 后台分析/重新拆解任务状态。用于刷新后恢复进度、取消任务和记录失败原因。 |

历史列表接口 `/api/analyses` 会返回：

- `analyses` 中已经完成保存的记录。
- `analysis_jobs` 中 `status IN ('queued', 'processing')`、`analysis_id IS NULL`、`replace_analysis_id IS NULL` 的初始上传任务占位记录。

它不会把已经 `failed` 或 `canceled` 且没有生成 `analysis_id` 的孤立任务长期显示为视频记录；这类任务只保留在 `analysis_jobs` 中用于排查。后端启动时会把上次进程遗留的 `queued`/`processing` 任务标记为 `failed`，普通列表查询不会修改任务状态。

## 根目录文件

| 路径 | 作用 |
| --- | --- |
| `README.md` | 安装、环境变量、启动命令和前端代理说明。 |
| `requirements.txt` | 后端 Python 依赖清单。新环境可用 `pip3 install -r requirements.txt` 安装。 |
| `AGENTS.md` | 给 Codex/agent 使用的项目上下文和工作规则。 |
| `.gitignore` | git 忽略规则。应覆盖运行时文件、构建产物和本地缓存。 |

## 前端子目录

| 路径 | 作用 |
| --- | --- |
| `frontend/src/` | 前端源码。 |
| `frontend/src/views/` | 页面级 Vue 组件，当前主页面是 `VideoAnalyze.vue`。 |
| `frontend/src/components/` | 可复用 Vue 组件。 |
| `frontend/src/assets/` | 前端静态资源。 |
| `frontend/public/` | Vite public 静态资源。 |
| `frontend/dist/` | 前端构建输出目录。通常不提交。 |
| `frontend/package.json` | 前端依赖和脚本。 |
| `frontend/pnpm-lock.yaml` | 前端依赖锁文件。 |

## 常用命令

```bash
# 启动后端
PORT=8001 python3 -m backend.main

# 运行后端测试
python3 -m unittest discover -s tests

# 启动前端
cd frontend && pnpm dev

# 构建前端
cd frontend && pnpm build
```

## 清理原则

- 可以清理：`frames/`、`videos/`、`debug_outputs/`、`frontend/dist/`。
- 谨慎清理：`storage/`，尤其是 `storage/analysis.db`、`storage/videos/`、`storage/frames/`。
- 不要在后端分析任务运行中清理 `frames/`、`videos/`、`storage/jobs/`。
