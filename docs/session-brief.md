# 窗口交接摘要

这个文件用于在不同 Codex 窗口之间交接上下文。保持简短；当任务方向变化或完成一个有用检查点时更新它。

## 当前重点

- 最近处理：视频详情页“一键复制”脚本复刻功能。
- 当前实现：
  - 详情页模型结果卡片新增“一键复制”，进入独立脚本复刻页；源视频结构、分镜模板和黄金 3 秒复刻说明在左侧展示。
  - 后端新增 `POST /api/analyses/{analysis_id}/script-copy`，读取历史拆解结果即时生成新商品脚本；不新增数据库表，不保存生成结果。
  - 复刻 prompt 会套用源视频爆款公式、分镜节奏、卖点角度、视觉手法、转化逻辑和黄金 3 秒钩子，但禁止照抄源视频台词、品牌、商品、价格或具体承诺。
  - 前端脚本复刻表单已简化为“需要带货的商品”和“希望突出的内容”；产品品类、目标用户、使用场景、优惠、时长、模型、语气等放入高级设置。
  - 新增 `POST /api/product-selling-points`，用 AI 根据商品标题、品类、补充内容和可选图片生成默认卖点；前端失败时才用本地规则兜底，用户编辑后不再覆盖。
  - 上传产品图片使用本地 object URL 预览，移除/离开页面时释放；图片只用于本次生成请求，不写入历史记录。
  - 点击生成脚本前会比较用户商品推断类目和参考视频 `product_classification`；不一致时弹窗二次确认。
  - 详情页黄金 3 秒 tag 可点击，气泡展示“怎么命中”和“怎么复刻”。
  - gptproto 的 responses/chat/Claude 请求增加瞬时网络异常重试，避免一次 `SSLError/SSLEOFError` 直接导致分析任务失败。
- 仍保留之前能力：多模型拆解、重新拆解、停止重拆、历史列表合并运行中任务、模型版本存储和产品分类筛选。

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

- `python3 -m unittest discover -s tests`：64 个测试通过。输出中仍有既有 MoviePy `/tmp/demo.mp4` 缺文件打印，但退出码为 0。
- `cd frontend && pnpm build`：构建通过，仍有 Vite/Rollup 的第三方注释和 chunk size 警告。
- `git diff --check`：通过。

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
