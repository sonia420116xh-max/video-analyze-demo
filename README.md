# AI 视频分镜拆解工具 - 后端

基于 Python + FastAPI 实现，支持本地 Whisper/OpenAI 转写，以及 GPTProto、GPT-4o、通义千问做分镜拆解。

## 一、安装依赖

```bash
pip3 install fastapi uvicorn openai python-multipart requests moviepy pillow
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

# 本地 whisper 模型名，默认 base
export WHISPER_MODEL=base
```

说明：

- 当前代码会优先使用 `faster-whisper`
- 如果你另外装了 `stable-whisper`，也会作为后备分支
- 第一次本地转写时会自动下载模型，耗时会比后续运行更久

前端模型说明：

- `Gemini 2.5 Pro`：走 `gptproto /v1/chat/completions`，模型名取 `BRAIN_MODEL`
- `GPTProto`：同上，兼容原来的自定义 `gptproto` 入口
- `GPT-4o (GPTProto Chat)`：走 `gptproto /v1/chat/completions`，固定模型名 `gpt-4o`
- `GPT-4o (OpenAI)`：直连 OpenAI 官方接口，需要 `OPENAI_API_KEY`

## 三、启动后端

```bash
PORT=8001 python3 main.py
```

## 四、前端代理

前端默认会把 `/api/*` 代理到 `http://127.0.0.1:8001`。

如果你想改成别的后端地址，可以在启动前端前设置：

```bash
VITE_API_TARGET=http://127.0.0.1:9000
```
