# AI 视频分镜拆解工具 - 后端

基于 Python + FastAPI 实现，支持本地 Whisper/OpenAI 转写，以及 gemini-2.5-pro、gpt-4o、qwen-turbo 等具体模型做分镜拆解。

项目目录和运行时文件说明见：[`docs/project-structure.md`](docs/project-structure.md)。

## 一、安装依赖

```bash
pip3 install fastapi uvicorn openai python-multipart requests moviepy pillow
```

项目还使用 `yt-dlp` 作为视频下载/解析工具。如果 `pip3 install -r requirements.txt` 因其他依赖失败，但只需要先安装这个新增工具，可以单独执行：

```bash
python3 -m pip install yt-dlp
```

macOS 用户安装后如果提示 `yt-dlp` 脚本目录不在 `PATH`，可以先用模块方式验证和调用：

```bash
python3 -m yt_dlp --version
```

如果你想优先走本地 Whisper 转写，再安装：

```bash
pip3 install faster-whisper ctranslate2 huggingface-hub tokenizers onnxruntime
```

## 二、环境变量

推荐接入 `gptproto`：

```bash
export GPTPROTO_API_KEY=你的gptproto_key
export BRAIN_BASE_URL=https://gptproto.com/v1
export BRAIN_MODEL=gemini-2.5-pro
```

可选项：

```bash
# 兼容旧变量名；如果已设置 GPTPROTO_API_KEY，可以不再设置这个
export BRAIN_API_KEY=你的gptproto_key

# 没装本地 whisper 时，会回退到 OpenAI Whisper
export OPENAI_API_KEY=你的openai_key

# 本地 whisper 模型名，默认 base；ASR 默认开启
export WHISPER_MODEL=base
```

说明：

- 当前代码会优先使用 `faster-whisper`
- 如果你另外装了 `stable-whisper`，也会作为后备分支
- 第一次本地转写时会自动下载模型，耗时会比后续运行更久
- ASR 默认开启；如果某台电脑需要临时关闭自动字幕识别，可以设置 `ENABLE_ASR=0`
- 如果本地 Whisper 不可用且没有配置 `OPENAI_API_KEY`，后端会以空字幕继续分析

前端模型说明：

- `gemini-2.5-pro`：走 `gptproto /v1/chat/completions`，实际模型名就是 `gemini-2.5-pro`
- `gpt-4o`：走 `gptproto /v1/responses`，使用 `input_text + input_image` 传入字幕与关键帧，实际模型名就是 `gpt-4o`
- `qwen-turbo`：走 DashScope 文本生成接口，需要 `DASHSCOPE_KEY`

视频分析不是只把 ASR 文本发给模型。后端会把视频抽成带编号和秒数的视觉关键帧，例如 `F01 @ 1.48s`，再以 base64 图片形式随同 prompt 发给支持图片的模型。每张图片前都会附一段文本说明帧编号和时间点，因此模型可以把画面证据绑定回视频时间轴。完整请求结构和抽帧规则见 [`docs/video-analysis-report.md`](docs/video-analysis-report.md#视觉关键帧采样规则)。

## 三、启动后端

```bash
PORT=8001 python3 -m backend.main
```

## 四、前端代理

前端默认会把 `/api/*` 代理到 `http://127.0.0.1:8001`。

如果你想改成别的后端地址，可以在启动前端前设置：

```bash
VITE_API_TARGET=http://127.0.0.1:9000
```
