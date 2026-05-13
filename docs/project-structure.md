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

`analyses` 和 `analysis_versions` 都保存 `product_classification` 字段。这个字段是从固定产品类目白名单归一化出来的记录级分类，用于前端历史列表筛选；未识别或不在白名单里的视频保存为空字符串，只在“全部产品分类”筛选下展示。

历史列表接口 `/api/analyses` 会返回：

- `analyses` 中已经完成保存的记录。
- `analysis_jobs` 中 `status IN ('queued', 'processing')`、`analysis_id IS NULL`、`replace_analysis_id IS NULL` 的初始上传任务占位记录。

它不会把已经 `failed` 或 `canceled` 且没有生成 `analysis_id` 的孤立任务长期显示为视频记录；这类任务只保留在 `analysis_jobs` 中用于排查。后端启动时会把上次进程遗留的 `queued`/`processing` 任务标记为 `failed`，普通列表查询不会修改任务状态。

“一键复制”脚本复刻不新增数据库表，也不持久化生成结果。前端从已完成分析详情中选择一个模型版本作为参考模板，把用户商品信息和可选产品图通过 `POST /api/analyses/{analysis_id}/script-copy` 发送给后端；后端即时构建脚本复刻 prompt 并调用所选模型，返回结构化脚本对象。用户上传的产品图会在前端用本地 object URL 预览，提交时作为 multipart 图片传给模型，不会写入 `storage/` 或 SQLite。

已保存分镜 JSON 中常用字段的职责不同：`scene_description` 是画面描述，`script` 是原始口播/字幕，`visual_tactic` 是视觉手法，`conversion_point` 是该段推动继续观看、信任或购买的转化作用。详情页分镜正文主要展示 `scene_description` 和 `script`；一键复制页左侧“源视频结构”为了突出可复刻逻辑，分镜摘要优先展示 `conversion_point`，为空时才回退到 `scene_description`。后端脚本复刻 prompt 会同时读取这些字段，不会只依赖左侧摘要。

商品默认卖点通过 `POST /api/product-selling-points` 即时生成，不写数据库。后端会把商品标题、品类、已有补充内容和可选产品图交给模型，要求输出短卖点、推断产品分类和简短依据。前端只有在该接口失败或没有返回卖点时，才使用本地规则兜底。

前端在提交脚本复刻前会做两类本地辅助判断：

- 在用户未手动编辑卖点时，接收模型生成的默认卖点；用户编辑过卖点后不再自动覆盖。
- 根据同一批文本信息推断用户商品类目，并和参考视频的 `product_classification` 比较；如果不一致，会弹窗提示用户确认不同品类复刻的适配风险。

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
