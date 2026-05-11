from fastapi import FastAPI, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import asyncio
import os
import json
import base64
import re
import shutil
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
import openai
import requests
from moviepy.editor import VideoFileClip
from PIL import Image

try:
    import stable_whisper
except ImportError:
    stable_whisper = None

try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None

app = FastAPI()

# 跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ====================== 填写你的 KEY ======================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
DASHSCOPE_KEY = os.getenv("DASHSCOPE_KEY", "")
BAIDU_KEY = os.getenv("BAIDU_KEY", "")
BRAIN_API_KEY = os.getenv("BRAIN_API_KEY", "sk-5ab89919fe6c4891903754352bc1df72")
GPTPROTO_API_KEY = os.getenv("GPTPROTO_API_KEY", BRAIN_API_KEY)
BRAIN_BASE_URL = os.getenv("BRAIN_BASE_URL", "https://gptproto.com/v1")
BRAIN_MODEL = os.getenv("BRAIN_MODEL", "gemini-2.5-pro")
GPTPROTO_VISION_MODEL = os.getenv("GPTPROTO_VISION_MODEL", "gpt-4o")
WHISPER_MODEL_NAME = os.getenv("WHISPER_MODEL", "base")
# ==========================================================

BASE_DIR = Path(__file__).resolve().parent
TEMP_VIDEO_DIR = BASE_DIR / "videos"
TEMP_FRAME_DIR = BASE_DIR / "frames"
STORAGE_DIR = BASE_DIR / "storage"
STORED_VIDEO_DIR = STORAGE_DIR / "videos"
STORED_FRAME_DIR = STORAGE_DIR / "frames"
JOB_UPLOAD_DIR = STORAGE_DIR / "jobs"
DB_PATH = STORAGE_DIR / "analysis.db"

for directory in (TEMP_VIDEO_DIR, TEMP_FRAME_DIR, STORED_VIDEO_DIR, STORED_FRAME_DIR, JOB_UPLOAD_DIR):
    directory.mkdir(parents=True, exist_ok=True)

app.mount("/frames", StaticFiles(directory=str(TEMP_FRAME_DIR)), name="frames")
app.mount("/storage", StaticFiles(directory=str(STORAGE_DIR)), name="storage")

_whisper_model = None
_faster_whisper_model = None
analysis_jobs = {}
analysis_jobs_lock = threading.Lock()
analysis_pipeline_lock = threading.Lock()


PATTERN_TAXONOMY = """
内部爆款模式分类体系：

1. 第一人称视角
适用判断：手持近景、POV、像观众亲手体验产品；常见于清洁、工具、个护、组装、功能测试。
小类：
- 困境解决型：第一视角直接进入问题现场，边操作边证明产品如何解决麻烦。
- 过程演示型：第一视角连续展示操作流程、组装步骤、使用路径或功能触发过程。
- 探索发现型：以发现、尝试、测评新东西的口吻推进，重点是“我刚发现/我来试试”。
- 日常切片型：第一视角截取日常片段，产品自然出现，不像正式广告。

2. 开箱 / ASMR
适用判断：拆包装、取出配件、触摸材质、摩擦/撕膜/摆放等感官细节明显；以期待感和质感建立兴趣。
小类：
- 开箱评测型：从拆箱进入产品认知，随后给出功能、质感或体验评价。
- 纯感官型：以包装声、材质声、摆放、触摸和细节特写为核心，弱口播也成立。
- 惊喜揭晓型：强调期待、反差、套装感、赠品感或“打开后发现”的惊喜。
- 礼物叙事型：围绕送礼、节日、关系、仪式感来包装产品价值。

3. GRWM + 产品
适用判断：创作者在镜前、浴室、卧室、化妆/护肤/穿搭/整理流程中亲自使用产品，强调个人变化和真实感。
小类：
- 仪式步骤型：产品嵌入个人准备流程，强调步骤、顺序、习惯和使用仪式感。
- 教学穿插型：一边准备一边讲解用法、技巧、注意点或搭配方式。
- 场景驱动型：围绕出门、约会、上班、旅行、洗护等具体准备场景展开。
- 情感叙事型：个人困扰、身体变化、外貌焦虑、生活状态或自我改善驱动产品出现。
- 产品对决型：在个人使用场景中比较不同产品、不同效果或不同选择。

4. 分屏对比
适用判断：左右分屏、前后对比、有无产品对比、竞品/平替对比、淘汰赛式测试；核心是直观证明差异。
小类：
- 方法对比型：比较两种做法、两种使用路径或错误/正确方法。
- 淘汰赛型：多个产品或方案被逐个测试、筛选、淘汰，最后突出胜出者。
- 平替对决型：把目标产品与贵价、竞品或常规方案对比，强调替代价值。
- 前后分屏型：通过使用前后、有无产品、左右半边等画面证明变化。

5. 日常 Vlog
适用判断：产品被自然放进生活流，如晨间、家庭、通勤、运动、旅行、家务；重点是让用户想象自己也会这样用。
小类：
- 日常碎片型：多个生活片段拼接，产品像生活习惯的一部分。
- 从早到晚型：围绕一天的时间线或连续生活流程展示产品用途。
- 主题日型：围绕某个活动、节日、任务、家庭日、运动日或旅行日展开。

全局叙事步骤词库：
这些步骤不是固定流程，也不绑定某个小类。请根据视频真实出现内容，按时间顺序选择最贴切的步骤作为每个分镜的 title/content_tag。
- 故事开场：用人物、事件、悬念、日常瞬间或一句话引入。
- 用户痛点：提出困扰、需求、焦虑、不便、失败体验或未满足的场景。
- 需求产生：说明为什么需要某类产品或解决方案。
- 场景设定：交代浴室、卧室、厨房、通勤、旅行、健身、家务等使用环境。
- 产品亮相：产品首次被拿出、展示、命名或进入画面中心。
- 产品信息：品牌、品类、规格、套装、包装、配件、材质等基础信息。
- 产品特写：包装、质地、刷头、滚珠、按钮、接口、面料、配件等细节镜头。
- 使用说明：怎么打开、怎么涂、怎么装、怎么按、怎么清洁、怎么携带。
- 功能演示：实际操作产品并展示功能发生过程。
- 产品卖点：明确讲一个可购买理由，如便携、保湿、省时、防漏、好看、耐用。
- 产品差异：与旧方法、竞品、普通产品、贵价产品或其他方案的不同。
- 卖点对比：并列比较多个卖点或多个选择的强弱。
- 痛点解决：说明产品如何解决前面出现的问题。
- 产品功效：展示或宣称结果、改善、效果、体验收益。
- 效果对比：使用前后、有无产品、左右半边、竞品对照等差异证据。
- 真实体验：创作者个人感受、验证、评价、复购、搜索经验或使用心得。
- 使用感受：肤感、口感、手感、舒适度、声音、气味、轻重、便利度等。
- 适用场景：说明适合哪些人、什么时间、什么地点或什么任务。
- 适用人群：点名妈妈、上班族、健身人群、懒人、旅行者、宠物家庭等。
- 情绪营销：惊喜、自信、治愈、安心、焦虑缓解、仪式感、被理解等情绪价值。
- 价格促销：价格、折扣、优惠、套装、限时、库存、性价比等信息。
- 优惠活动：优惠券、促销活动、买赠、折扣入口等转化信息。
- 行动号召：引导点击链接、购物车、下方链接、评论区、主页等。
"""


def normalize_json_text(text):
    if not isinstance(text, str):
        return text

    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    array_start = cleaned.find("[")
    array_end = cleaned.rfind("]")
    if array_start != -1 and array_end != -1 and array_start < array_end:
        return cleaned[array_start:array_end + 1].strip()

    object_start = cleaned.find("{")
    object_end = cleaned.rfind("}")
    if object_start != -1 and object_end != -1 and object_start < object_end:
        return cleaned[object_start:object_end + 1].strip()

    return cleaned


def init_db(db_path=DB_PATH):
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analyses (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                model TEXT NOT NULL,
                video_path TEXT NOT NULL,
                video_url TEXT NOT NULL,
                result_json TEXT NOT NULL,
                formula TEXT,
                subtype TEXT,
                category_reason TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def _row_to_dict(row):
    return dict(row) if row else None


def _connect_db(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def parse_result_items(result_json):
    cleaned = normalize_json_text(result_json)
    try:
        parsed = json.loads(cleaned)
    except (TypeError, json.JSONDecodeError):
        return []

    if isinstance(parsed, dict):
        parsed = parsed.get("shots") or parsed.get("items") or parsed.get("data") or []
    return parsed if isinstance(parsed, list) else []


def save_analysis_record(record, db_path=DB_PATH):
    init_db(db_path)
    with _connect_db(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO analyses (
                id, filename, model, video_path, video_url, result_json,
                formula, subtype, category_reason, created_at
            ) VALUES (
                :id, :filename, :model, :video_path, :video_url, :result_json,
                :formula, :subtype, :category_reason, :created_at
            )
            """,
            record,
        )
        conn.commit()


def store_result_frame_images(analysis_id, items, stored_frame_dir=STORED_FRAME_DIR, temp_frame_dir=TEMP_FRAME_DIR):
    analysis_frame_dir = Path(stored_frame_dir) / analysis_id
    if analysis_frame_dir.exists():
        shutil.rmtree(analysis_frame_dir, ignore_errors=True)
    analysis_frame_dir.mkdir(parents=True, exist_ok=True)

    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        image_url = item.get("image_url", "")
        if not image_url.startswith("/frames/"):
            continue

        frame_name = Path(image_url.split("?", 1)[0]).name or f"shot_{index + 1:02d}.jpg"
        temp_frame_path = Path(temp_frame_dir) / frame_name
        stored_frame_path = analysis_frame_dir / frame_name
        if temp_frame_path.exists():
            shutil.copy2(temp_frame_path, stored_frame_path)
            item["image_url"] = f"/storage/frames/{analysis_id}/{frame_name}"

    return items


def update_analysis_record_result(
    analysis_id,
    model,
    result_json,
    db_path=DB_PATH,
    stored_frame_dir=STORED_FRAME_DIR,
    temp_frame_dir=TEMP_FRAME_DIR,
):
    record = fetch_analysis_detail(analysis_id, db_path)
    if not record:
        raise ValueError("分析记录不存在")

    items = parse_result_items(result_json)
    store_result_frame_images(analysis_id, items, stored_frame_dir, temp_frame_dir)
    normalized_result_json = json.dumps(items, ensure_ascii=False)
    first_item = next((item for item in items if isinstance(item, dict)), {})
    with _connect_db(db_path) as conn:
        conn.execute(
            """
            UPDATE analyses
            SET model = ?,
                result_json = ?,
                formula = ?,
                subtype = ?,
                category_reason = ?,
                created_at = ?
            WHERE id = ?
            """,
            (
                model,
                normalized_result_json,
                first_item.get("viral_formula", ""),
                first_item.get("formula_subtype", ""),
                first_item.get("category_reason", ""),
                datetime.now(timezone.utc).isoformat(),
                analysis_id,
            ),
        )
        conn.commit()

    return {
        "analysis_id": analysis_id,
        "video_url": record["video_url"],
        "data": normalized_result_json,
    }


def delete_analysis_record(analysis_id, db_path=DB_PATH, stored_frame_dir=STORED_FRAME_DIR):
    record = fetch_analysis_detail(analysis_id, db_path)
    if not record:
        return False

    with _connect_db(db_path) as conn:
        conn.execute("DELETE FROM analyses WHERE id = ?", (analysis_id,))
        conn.commit()

    video_path = Path(record.get("video_path") or "")
    try:
        if video_path.exists() and video_path.is_file():
            video_path.unlink()
    except Exception as e:
        print("删除视频文件失败:", e)

    try:
        shutil.rmtree(Path(stored_frame_dir) / analysis_id, ignore_errors=True)
    except Exception as e:
        print("删除分镜图片失败:", e)

    return True


def fetch_analysis_list(db_path=DB_PATH):
    init_db(db_path)
    with _connect_db(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, filename, model, video_url, formula, subtype,
                   category_reason, result_json, created_at
            FROM analyses
            ORDER BY created_at DESC
            """
        ).fetchall()

    records = []
    for row in rows:
        record = _row_to_dict(row)
        record["shot_count"] = len(parse_result_items(record.pop("result_json", "[]")))
        records.append(record)
    return records


def fetch_analysis_detail(analysis_id, db_path=DB_PATH):
    init_db(db_path)
    with _connect_db(db_path) as conn:
        row = conn.execute(
            """
            SELECT id, filename, model, video_path, video_url, result_json,
                   formula, subtype, category_reason, created_at
            FROM analyses
            WHERE id = ?
            """,
            (analysis_id,),
        ).fetchone()

    record = _row_to_dict(row)
    if not record:
        return None

    record["data"] = parse_result_items(record.pop("result_json", "[]"))
    record["shot_count"] = len(record["data"])
    return record


def safe_filename(filename):
    stem = Path(filename or "video.mp4").stem
    suffix = Path(filename or "video.mp4").suffix or ".mp4"
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._") or "video"
    safe_suffix = re.sub(r"[^A-Za-z0-9.]+", "", suffix) or ".mp4"
    return f"{safe_stem}{safe_suffix}"


def persist_analysis(video_path, original_filename, model, result_json):
    analysis_id = uuid.uuid4().hex
    filename = safe_filename(original_filename)
    stored_video_name = f"{analysis_id}_{filename}"
    stored_video_path = STORED_VIDEO_DIR / stored_video_name
    shutil.copy2(video_path, stored_video_path)

    items = parse_result_items(result_json)
    store_result_frame_images(analysis_id, items)

    normalized_result_json = json.dumps(items, ensure_ascii=False)
    first_item = next((item for item in items if isinstance(item, dict)), {})
    created_at = datetime.now(timezone.utc).isoformat()
    video_url = f"/storage/videos/{stored_video_name}"
    record = {
        "id": analysis_id,
        "filename": original_filename or filename,
        "model": model,
        "video_path": str(stored_video_path),
        "video_url": video_url,
        "result_json": normalized_result_json,
        "formula": first_item.get("viral_formula", ""),
        "subtype": first_item.get("formula_subtype", ""),
        "category_reason": first_item.get("category_reason", ""),
        "created_at": created_at,
    }
    save_analysis_record(record)
    return {
        "analysis_id": analysis_id,
        "video_url": video_url,
        "data": normalized_result_json,
    }


def update_analysis_job(job_id, **updates):
    with analysis_jobs_lock:
        current = analysis_jobs.setdefault(job_id, {})
        current.update(updates)
        current["updated_at"] = datetime.now(timezone.utc).isoformat()
        return dict(current)


def get_analysis_job(job_id):
    with analysis_jobs_lock:
        job = analysis_jobs.get(job_id)
        return dict(job) if job else None


def create_analysis_job(filename, model):
    job_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    with analysis_jobs_lock:
        analysis_jobs[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "filename": filename,
            "model": model,
            "message": "任务已提交，等待后台分析",
            "created_at": now,
            "updated_at": now,
        }
    return job_id


def prepare_reanalysis_job(analysis_id, model=None, db_path=DB_PATH, job_upload_dir=JOB_UPLOAD_DIR):
    record = fetch_analysis_detail(analysis_id, db_path)
    if not record:
        raise ValueError("分析记录不存在")

    source_video_path = Path(record.get("video_path") or "")
    if not source_video_path.exists() or not source_video_path.is_file():
        raise FileNotFoundError("原视频文件不存在，无法重新拆解")

    target_model = model or record.get("model") or "gpt4o"
    filename = record.get("filename") or source_video_path.name
    job_id = create_analysis_job(filename, target_model)
    job_dir = Path(job_upload_dir) / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    video_path = job_dir / safe_filename(filename)
    shutil.copy2(source_video_path, video_path)

    update_analysis_job(
        job_id,
        message="重新拆解任务已提交，等待后台分析",
        replace_analysis_id=analysis_id,
    )
    return {
        "job_id": job_id,
        "filename": filename,
        "model": target_model,
        "video_path": str(video_path),
        "replace_analysis_id": analysis_id,
    }


init_db()


def parse_time_value(value, fallback=0.0):
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return fallback

    text = value.strip().replace(",", ".")
    try:
        return float(text)
    except ValueError:
        pass

    parts = text.split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
    except ValueError:
        return fallback

    return fallback


def extract_storyboard_images(video_path, items):
    try:
        clip = VideoFileClip(video_path)
        duration = clip.duration or 0
        for index, item in enumerate(items):
            start = parse_time_value(item.get("start_time"), 0)
            end = parse_time_value(item.get("end_time"), start + 1)
            midpoint = start + max(end - start, 0.5) * 0.45
            evidence_time = parse_time_value(item.get("evidence_timestamp"), midpoint)
            timestamp = min(max(evidence_time, 0), max(duration - 0.05, 0))

            frame = clip.get_frame(timestamp)
            image = Image.fromarray(frame)
            frame_name = f"shot_{index + 1:02d}.jpg"
            image.save(TEMP_FRAME_DIR / frame_name, quality=88)
            item["image_url"] = f"/frames/{frame_name}"
        clip.close()
    except Exception as e:
        print("分镜抽帧错误:", e)

    return items


def sample_visual_frames(video_path, max_frames=40):
    frames = []
    try:
        clip = VideoFileClip(video_path)
        duration = clip.duration or 0
        if duration <= 0:
            clip.close()
            return frames

        step = duration / max_frames if duration > max_frames else 1
        count = max_frames if duration > max_frames else max(1, int(duration))
        timestamps = [
            min(index * step + step * 0.45, max(duration - 0.05, 0))
            for index in range(count)
        ]

        for index, timestamp in enumerate(timestamps):
            frame = clip.get_frame(timestamp)
            image = Image.fromarray(frame).convert("RGB")
            image.thumbnail((900, 1600))
            buffer = BytesIO()
            image.save(buffer, format="JPEG", quality=82, optimize=True)
            encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
            frames.append({
                "id": f"F{index + 1:02d}",
                "timestamp": round(timestamp, 2),
                "data_url": f"data:image/jpeg;base64,{encoded}",
            })
        clip.close()
    except Exception as e:
        print("视觉关键帧抽取错误:", e)

    return frames


def build_gptproto_messages(prompt, visual_frames):
    if not visual_frames:
        return [{"role": "user", "content": prompt}]

    content = [{"type": "text", "text": prompt}]
    for frame in visual_frames:
        content.append({"type": "text", "text": f"{frame['id']}，时间：{frame['timestamp']}s。请只描述这张图中能明确看到的商品和颜色。"})
        content.append({
            "type": "image_url",
            "image_url": {"url": frame["data_url"]},
        })

    return [{"role": "user", "content": content}]


def build_analysis_prompt(transcript, visual_frames=None):
    visual_frames = visual_frames or []
    visual_note = """
你还会收到按时间顺序排列的视频关键帧图片，每张图都有编号和时间点，例如 F01 1.2s。
分类、商品品类、场景和分镜必须优先依据关键帧画面证据；字幕或音频可能只是背景音乐歌词，不能把无关歌词当成商品说明。
如果画面显示服装试穿、穿搭展示、换装、转身展示版型，请识别为服饰/穿搭相关内容，不要写成护肤品、清洁用品或其他画面中不存在的品类。
每个分镜必须绑定一个 evidence_frame 和 evidence_timestamp，描述只能来自该分镜证据帧附近的画面，不要把其他关键帧里的颜色、款式、商品串到当前分镜。
如果关键帧中只有画面展示、没有真实口播销售词，script 字段写“画面/字幕摘要”，不要编造创作者说过的推销话术。
服装试穿类视频请优先按“每套穿搭/每次换装”拆分；如果同一套服装连续展示多个角度，可以合并为一个分镜。
""" if visual_frames else """
你只会收到音频转写，因此如果字幕内容像背景音乐歌词、缺少商品信息，请在分类和分镜中保持保守，不要编造画面里不存在的产品。
"""

    return f"""
你是专业跨境短视频爆款模式分析师，严格输出JSON数组，不要任何多余解释。

你的任务不是固定套用某一种模式，而是先判断视频属于哪一个大类与小类，再按该类型的高转化叙事链路拆分分镜。

{visual_note}

{PATTERN_TAXONOMY}

分类判断规则：
1. 先判断视频主导表达方式，而不是单句台词。优先看：产品如何出场、是否真人亲测、是否开箱、是否分屏/前后对比、是否生活流叙事、是否第一人称沉浸演示。
2. 如果同时命中多个类型，选择贯穿全片最多、承担转化最强的那个作为 viral_formula。
3. formula_subtype 必须从该大类的小类中选择，不要创造新小类。
4. 小类只用于判断视频形态，不代表固定步骤顺序；不要为了套小类而强行补不存在的段落。
5. 分镜步骤从“全局叙事步骤词库”里选择，按视频真实出现顺序标注；一个视频可以只出现其中一部分步骤，也可以重复出现某类步骤。
6. 请进行细颗粒度分镜拆解。每当画面动作、商品状态、人物站位、试穿状态、展示角度、口播主题或转化目的发生变化，都应拆成新的分镜。一个 2 分钟视频通常应拆成 8-15 个分镜；如果口播信息密集，宁可拆得更细，不要把 20 秒以上的多主题内容塞进一个分镜。
7. 如果字幕里有西语、英语或其他语言，script 保留原语言；中文只写在分析字段里。
8. 小类判定优先级：平替对决型必须有明确双对象/双方案对比，例如贵价品牌 vs 平替、竞品 A vs 竞品 B、常规方案 vs 替代方案、每份成本/价格差并列比较、dupe/alternative 对照；只有单一品牌开箱、haul、试穿或测评时，即使提到 sale、cheaper、kid sizes、优惠购买技巧，也不要判为平替对决型。
9. 开箱主导结构优先归为开箱 / ASMR：如果视频从包裹/包装/袋子开始，持续出现打开、取出、展示、触摸材质、试穿或评价，主类应为“开箱 / ASMR”，小类通常为“开箱评测型”。价格促销只是分镜标签，不改变全片主类。

输出格式：
[
  {{
    "start_time": 数字,
    "end_time": 数字,
    "title": "从全局叙事步骤词库中选择的该分镜叙事角色",
    "scene_description": "画面描述",
    "script": "台词",
    "product_category": "画面中真实出现的商品品类，例如服装/护肤/清洁/工具/食品等",
    "evidence_frame": "证据关键帧编号，例如F03",
    "evidence_timestamp": 数字,
    "shot_type": "特写/镜前特写/分屏/对比/第一人称/全景",
    "content_tag": "从全局叙事步骤词库中选择，必须贴合该段真实内容",
    "viral_formula": "第一人称视角/开箱 / ASMR/GRWM + 产品/分屏对比/日常 Vlog",
    "formula_subtype": "对应大类下的小类",
    "category_reason": "为什么判定为这个大类和小类，简洁说明",
    "visual_tactic": "该段使用的视觉手法，例如手持POV/开箱特写/镜前真人实测/左右分屏/生活流植入",
    "conversion_point": "这一段承担的转化作用"
  }}
]

要求：
- 只输出JSON数组，严禁markdown代码块。
- 如果存在真实口播，script 保留原语言，不要编造原文没有的句子；如果只有背景音乐歌词或无关音频，script 写画面/字幕摘要。
- product_category 必须依据关键帧画面判断，不能依据无关音频歌词猜测。
- evidence_frame/evidence_timestamp 必须对应你用于描述该分镜的关键帧；颜色、款式、商品只允许来自这个证据帧附近。
- 对服饰视频，不要在没有证据时写具体颜色；如果写颜色，必须是 evidence_frame 中清楚可见的颜色。
- scene_description 至少 30 个中文字符，要同时写清楚人物动作、商品状态/款式、镜头关系，以及这一段在爆款叙事中的作用；不要只写“展示产品”“创作者介绍商品”这种泛描述。
- script 需要覆盖该段完整语义。若同一时间段有多句口播，请合并保留关键原文；如果是画面摘要，也要写清楚画面里发生的具体动作。
- 每个分镜的 conversion_point 必须具体到“为什么让用户更想买/更信任/更省钱/更理解差异”，不要写空泛的“促进转化”。
- content_tag 以该段核心转化作用为准。只要该段提到便宜购买方法、优惠、折扣、deal、sale、coupon、price、save、link、shop、cart、购买路径或下单引导，即使画面里也在展示产品，也优先标为“优惠活动”或“价格促销”，不要标为“产品信息”。
- 如果画面或字幕出现“X vs Y”、“Which is better?”、“哪个更好”、竞品并列、两个产品同框比较、胜负结果、winner、价格/成分/功能对照，这类段落优先标为“产品差异”或“卖点对比”，不要标为“产品信息”或“产品亮相”。
- 对比类视频的开头即使只是展示两个产品，只要同时出现 vs/which is better/对比问题，也应视为“产品差异”，因为它承担的是建立对比对象和选择悬念。
- 只有出现明确双对象/双方案对比，且包含 cheaper、cheap、dupe、alternative、save money、price、per serving、cost、same look、same quality、平替/贵价/大牌/竞品等替代价值表达时，formula_subtype 才优先选择“平替对决型”。单一品牌开箱中提到 sale、kids size、cheaper 只能作为“优惠活动/价格促销”分镜，不得覆盖“开箱 / ASMR”的主类判断。
- scene_description用中文写，结合画面动作和对应类型套路解释。
- 时间必须覆盖字幕中的关键内容，尽量与语义段落对齐。
- 所有分镜的 viral_formula 和 formula_subtype 应保持一致，除非视频明显是混合结构；混合时也要以主类型为准。
- 不要把某个小类的示例流程当作硬性模板；title/content_tag 必须来自视频真实内容。

字幕内容：
{transcript}
"""


def normalize_content_tag(item):
    text = " ".join([
        str(item.get("title", "")),
        str(item.get("scene_description", "")),
        str(item.get("script", "")),
        str(item.get("conversion_point", "")),
    ]).lower()

    promo_keywords = [
        "便宜", "省钱", "优惠", "折扣", "促销", "活动", "价格", "购买", "买", "下单", "链接",
        "coupon", "discount", "deal", "sale", "cheap", "cheaper", "save", "price", "buy", "purchase",
        "link", "shop", "cart", "tiktok shop",
    ]
    if any(keyword in text for keyword in promo_keywords):
        item["content_tag"] = "优惠活动"
        if not item.get("conversion_point"):
            item["conversion_point"] = "通过价格、优惠或购买路径降低决策门槛"

    contrast_keywords = [
        " vs ", "vs.", "对比", "哪个更好", "哪一个更好", "更好", "差异", "区别", "比较", "胜出", "winner",
        "which is better", "compare", "comparison", "versus", "better than", "difference",
    ]
    if any(keyword in text for keyword in contrast_keywords):
        item["content_tag"] = "产品差异"
        if not item.get("conversion_point"):
            item["conversion_point"] = "通过并列比较建立产品选择理由"

    return item


def _combined_story_text(items):
    parts = []
    for item in items:
        if not isinstance(item, dict):
            continue
        parts.extend([
            str(item.get("title", "")),
            str(item.get("scene_description", "")),
            str(item.get("script", "")),
            str(item.get("content_tag", "")),
            str(item.get("visual_tactic", "")),
            str(item.get("conversion_point", "")),
        ])
    return " ".join(parts).lower()


def should_reclassify_as_alternative_showdown(items):
    text = _combined_story_text(items)
    if not text.strip():
        return False

    alternative_keywords = [
        "平替", "替代", "替代品", "同款", "大牌", "贵价", "高价", "竞品", "常规方案",
        "价格", "单价", "每份", "成本", "低价", "$", "price", "cost", "per serving",
        "童码", "儿童码", "成人码", "尺码", "dupe", "alternative", "cheaper", "cheap",
        "affordable", "expensive", "save money", "save", "same look", "same quality",
        "instead of", "rather than", "kid size", "kid sizes", "kids size", "kids sizes",
    ]
    comparison_keywords = [
        " vs ", "vs.", "versus", "which is better", "哪个更好", "哪一个更好", "对比",
        "比较", "差异", "区别", "compare", "comparison", "better than", "instead of",
        "rather than", "winner", "胜出",
    ]
    before_after_keywords = [
        "使用前后", "前后效果", "before and after", "有无产品", "半边脸", "半边画面",
        "左右半边", "使用前", "使用后",
    ]

    alternative_hits = sum(1 for keyword in alternative_keywords if keyword in text)
    comparison_hits = sum(1 for keyword in comparison_keywords if keyword in text)
    before_after_hits = sum(1 for keyword in before_after_keywords if keyword in text)

    if alternative_hits >= 1 and comparison_hits >= 1:
        return True

    current_subtypes = {
        str(item.get("formula_subtype", ""))
        for item in items
        if isinstance(item, dict)
    }
    if "前后分屏型" in current_subtypes and alternative_hits >= 2 and before_after_hits == 0:
        return True

    return False


def should_classify_as_unboxing_review(items):
    text = _combined_story_text(items)
    if not text.strip():
        return False

    unboxing_keywords = [
        "开箱", "拆箱", "拆包", "拆开", "打开", "包裹", "包装", "袋子", "取出", "拿出",
        "package", "packaging", "open it", "open this", "let's open", "unbox", "unboxing",
        "haul", "bag",
    ]
    review_keywords = [
        "试穿", "尺寸", "尺码", "材质", "柔软", "质感", "评价", "测评", "真实体验",
        "使用感受", "产品信息", "产品特写", "fit", "size", "soft", "obsessed", "try on",
        "hoodie", "pants", "sale",
    ]
    direct_showdown_keywords = [
        " vs ", "vs.", "versus", "which is better", "winner", "compare", "comparison",
        "dupe", "alternative", "竞品", "贵价", "大牌", "常规方案", "替代品",
    ]

    unboxing_hits = sum(1 for keyword in unboxing_keywords if keyword in text)
    review_hits = sum(1 for keyword in review_keywords if keyword in text)
    direct_showdown_hits = sum(1 for keyword in direct_showdown_keywords if keyword in text)

    return unboxing_hits >= 2 and review_hits >= 1 and direct_showdown_hits == 0


def normalize_as_unboxing_review(items):
    reason = "视频主线从包裹/包装开场，持续拆开、取出、展示并评价商品；促销或童码价格技巧只是开箱测评中的卖点，因此判定为开箱评测型。"
    for item in items:
        if not isinstance(item, dict):
            continue
        item["viral_formula"] = "开箱 / ASMR"
        item["formula_subtype"] = "开箱评测型"
        item["category_reason"] = reason
    return items


def normalize_formula_classification(items):
    if should_classify_as_unboxing_review(items):
        return normalize_as_unboxing_review(items)

    if not should_reclassify_as_alternative_showdown(items):
        return items

    reason = "核心表达是贵价/竞品/常规方案与更便宜或替代方案的对比，强调平替价值，因此判定为平替对决型。"
    for item in items:
        if not isinstance(item, dict):
            continue
        item["viral_formula"] = "分屏对比"
        item["formula_subtype"] = "平替对决型"
        item["category_reason"] = reason
    return items


def enrich_storyboard_result(result_text, video_path):
    cleaned = normalize_json_text(result_text)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return cleaned

    if isinstance(parsed, dict):
        parsed = parsed.get("shots") or parsed.get("items") or parsed.get("data") or []
    if not isinstance(parsed, list):
        return cleaned

    for index, item in enumerate(parsed):
        if not isinstance(item, dict):
            continue
        item.setdefault("title", item.get("narrative_role") or f"分镜 {index + 1}")
        item.setdefault("viral_formula", item.get("pattern_category") or "未识别模式")
        item.setdefault("formula_subtype", item.get("pattern_subtype") or "待判断")
        item.setdefault("visual_tactic", "按画面与口播综合判断")
        item.setdefault("conversion_point", "")
        item.setdefault("category_reason", "")
        item.setdefault("product_category", "")
        item.setdefault("evidence_frame", "")
        item.setdefault("evidence_timestamp", item.get("start_time", 0))
        normalize_content_tag(item)

    normalize_formula_classification(parsed)

    return json.dumps(extract_storyboard_images(video_path, parsed), ensure_ascii=False)

def clean_temp():
    for path in TEMP_VIDEO_DIR.iterdir():
        if path.is_file():
            path.unlink()
    for path in TEMP_FRAME_DIR.iterdir():
        if path.is_file():
            path.unlink()
    if os.path.exists("audio.mp3"):
        os.remove("audio.mp3")

def extract_frames(video_path):
    # 清空旧帧
    for path in TEMP_FRAME_DIR.iterdir():
        if path.is_file():
            path.unlink()
    try:
        clip = VideoFileClip(video_path)
        for t in range(0, int(clip.duration), 2):
            frame = clip.get_frame(t)
            im = Image.fromarray(frame)
            im.save(TEMP_FRAME_DIR / f"{t:04d}.jpg")
        clip.close()
    except Exception as e:
        print("抽帧错误:", e)

def extract_audio(video_path):
    try:
        clip = VideoFileClip(video_path)
        if clip.audio is None:
            clip.close()
            return False
        clip.audio.write_audiofile("audio.mp3", logger=None)
        clip.close()
        return True
    except Exception as e:
        print("提取音频错误:", e)
        return False


def get_whisper_model():
    global _whisper_model
    if stable_whisper is None:
        return None
    if _whisper_model is None:
        _whisper_model = stable_whisper.load_model(WHISPER_MODEL_NAME)
    return _whisper_model


def get_faster_whisper_model():
    global _faster_whisper_model
    if WhisperModel is None:
        return None
    if _faster_whisper_model is None:
        # cpu + int8 is a safe default for local development on laptops
        _faster_whisper_model = WhisperModel(
            WHISPER_MODEL_NAME,
            device="cpu",
            compute_type="int8",
        )
    return _faster_whisper_model


def audio_to_text():
    faster_model = get_faster_whisper_model()
    if faster_model is not None:
        try:
            segments, _info = faster_model.transcribe("audio.mp3", vad_filter=True)
            lines = []
            for segment in segments:
                text = (segment.text or "").strip()
                if text:
                    lines.append(f"{segment.start:.2f} --> {segment.end:.2f} {text}")
            if lines:
                return "\n".join(lines)
        except Exception as e:
            print("faster-whisper 转写错误:", e)

    whisper_model = get_whisper_model()
    if whisper_model is not None:
        try:
            result = whisper_model.transcribe("audio.mp3", fp16=False)
            segments = getattr(result, "segments", None) or []
            if segments:
                lines = []
                for segment in segments:
                    start = getattr(segment, "start", 0)
                    end = getattr(segment, "end", 0)
                    text = getattr(segment, "text", "").strip()
                    if text:
                        lines.append(f"{start:.2f} --> {end:.2f} {text}")
                if lines:
                    return "\n".join(lines)
            text = getattr(result, "text", "")
            if text:
                return text.strip()
        except Exception as e:
            print("stable_whisper 转写错误:", e)

    if not OPENAI_API_KEY:
        print("未配置 OPENAI_API_KEY，跳过音频转文字，使用无字幕模式继续分析")
        return "未识别到音频"

    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    try:
        with open("audio.mp3", "rb") as f:
            transcript = client.audio.transcriptions.create(
                model="whisper-1", file=f, response_format="srt"
            )
        return transcript
    except openai.AuthenticationError:
        raise RuntimeError("OpenAI API Key 无效，请检查 OPENAI_API_KEY")
    except openai.RateLimitError:
        raise RuntimeError("OpenAI 额度不足或配额已用尽，请检查 billing/配额")
    except Exception as e:
        print("语音转文字错误:", e)
        return "未识别到音频"

def analyze_video(transcript, model_type, video_path=None):
    visual_frames = sample_visual_frames(video_path) if video_path else []
    prompt = build_analysis_prompt(transcript, visual_frames)

    if model_type == "gpt4o":
        if not OPENAI_API_KEY:
            raise RuntimeError("未配置 OPENAI_API_KEY")

        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}]
            )
            return normalize_json_text(response.choices[0].message.content)
        except openai.AuthenticationError:
            raise RuntimeError("OpenAI API Key 无效，请检查 OPENAI_API_KEY")
        except openai.RateLimitError:
            raise RuntimeError("OpenAI 额度不足或配额已用尽，请检查 billing/配额")
        except Exception as e:
            print("GPT 分析错误:", e)
            raise RuntimeError(f"OpenAI 分析失败: {e}")

    elif model_type in {"gptproto", "gemini", "gemini-2.5-pro", "gptproto-gpt4o"}:
        if not GPTPROTO_API_KEY:
            raise RuntimeError("未配置 GPTPROTO_API_KEY")

        target_model = GPTPROTO_VISION_MODEL if visual_frames else ("gpt-4o" if model_type == "gptproto-gpt4o" else BRAIN_MODEL)
        messages = build_gptproto_messages(prompt, visual_frames)

        try:
            response = requests.post(
                f"{BRAIN_BASE_URL.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": GPTPROTO_API_KEY,
                    "Content-Type": "application/json",
                },
                json={
                    "model": target_model,
                    "messages": messages,
                },
                timeout=180,
            )
            if response.status_code == 401:
                raise RuntimeError("GPTPROTO_API_KEY 无效，请检查配置")
            if response.status_code == 429:
                raise RuntimeError("gptproto 额度不足或请求受限，请检查配额")
            response.raise_for_status()

            data = response.json()
            return normalize_json_text(data["choices"][0]["message"]["content"])
        except requests.HTTPError as e:
            detail = ""
            try:
                detail = response.text
            except Exception:
                detail = str(e)
            raise RuntimeError(f"gptproto 请求失败: {detail}")
        except requests.RequestException as e:
            raise RuntimeError(f"gptproto 网络请求失败: {e}")
        except Exception as e:
            print("gptproto 分析错误:", e)
            raise RuntimeError(f"gptproto 分析失败: {e}")

    elif model_type == "tongyi":
        if not DASHSCOPE_KEY:
            raise RuntimeError("未配置 DASHSCOPE_KEY")
        res = requests.post(
            "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation",
            headers={"Authorization": f"Bearer {DASHSCOPE_KEY}"},
            json={"model": "qwen-turbo", "input": {"messages": [{"role": "user", "content": prompt}]}}
        )
        return normalize_json_text(res.json()["output"]["text"])

    return "[]"


def run_analysis_pipeline(video_path, filename, model, replace_analysis_id=None):
    video_path = str(video_path)
    extract_frames(video_path)
    has_audio = extract_audio(video_path)
    transcript = audio_to_text() if has_audio else "未识别到音频"
    result = analyze_video(transcript, model, video_path)
    result = enrich_storyboard_result(result, video_path)
    if replace_analysis_id:
        return update_analysis_record_result(replace_analysis_id, model, result)
    return persist_analysis(video_path, filename, model, result)


def run_analysis_job(job_id, video_path, filename, model, replace_analysis_id=None):
    update_analysis_job(job_id, status="processing", message="正在抽帧、转写和分析视频")
    try:
        # The frame/audio helpers use shared temp folders, so serialize pipelines for safety.
        with analysis_pipeline_lock:
            clean_temp()
            stored = run_analysis_pipeline(video_path, filename, model, replace_analysis_id)
            clean_temp()

        update_analysis_job(
            job_id,
            status="completed",
            message="分析完成",
            analysis_id=stored["analysis_id"],
            video_url=stored["video_url"],
            data=stored["data"],
        )
    except Exception as e:
        print("后台分析任务异常:", e)
        update_analysis_job(job_id, status="failed", message=str(e))
    finally:
        try:
            shutil.rmtree(Path(video_path).parent, ignore_errors=True)
        except Exception:
            pass


async def _analyze_impl(
    file: UploadFile = None,
    video_url: str = Form(None),
    model: str = Form("gpt4o"),
    async_mode: bool = Form(False)
):
    try:
        if file:
            filename = file.filename or "video.mp4"
            if async_mode:
                job_id = create_analysis_job(filename, model)
                job_dir = JOB_UPLOAD_DIR / job_id
                job_dir.mkdir(parents=True, exist_ok=True)
                video_path = job_dir / safe_filename(filename)
                with open(video_path, "wb") as f:
                    f.write(await file.read())

                thread = threading.Thread(
                    target=run_analysis_job,
                    args=(job_id, video_path, filename, model),
                    daemon=True,
                )
                thread.start()
                return {
                    "code": 0,
                    "job_id": job_id,
                    "status": "queued",
                    "msg": "任务已提交，后台分析中",
                }

            with analysis_pipeline_lock:
                clean_temp()
                video_path = TEMP_VIDEO_DIR / "temp.mp4"
                with open(video_path, "wb") as f:
                    f.write(await file.read())
                stored = await asyncio.to_thread(
                    run_analysis_pipeline,
                    video_path,
                    filename,
                    model,
                )
        else:
            return JSONResponse(status_code=400, content={"code": 400, "msg": "请上传视频文件"})

        return {
            "code": 0,
            "data": stored["data"],
            "analysis_id": stored["analysis_id"],
            "video_url": stored["video_url"],
        }
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        print("分析接口异常:", e)
        raise HTTPException(status_code=500, detail="服务内部异常，请查看后端日志")


@app.post("/analyze")
async def analyze(
    file: UploadFile = None,
    video_url: str = Form(None),
    model: str = Form("gpt4o"),
    async_mode: bool = Form(False)
):
    return await _analyze_impl(file=file, video_url=video_url, model=model, async_mode=async_mode)


@app.post("/api/analyze")
async def analyze_with_api_prefix(
    file: UploadFile = None,
    video_url: str = Form(None),
    model: str = Form("gpt4o"),
    async_mode: bool = Form(False)
):
    return await _analyze_impl(file=file, video_url=video_url, model=model, async_mode=async_mode)


@app.get("/analysis-jobs/{job_id}")
async def analysis_job_detail(job_id: str):
    job = get_analysis_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="分析任务不存在或后端已重启")
    return {"code": 0, "data": job}


@app.get("/api/analysis-jobs/{job_id}")
async def analysis_job_detail_with_api_prefix(job_id: str):
    return await analysis_job_detail(job_id)


@app.get("/analyses")
async def analyses():
    return {"code": 0, "data": fetch_analysis_list()}


@app.get("/api/analyses")
async def analyses_with_api_prefix():
    return await analyses()


@app.get("/analyses/{analysis_id}")
async def analysis_detail(analysis_id: str):
    record = fetch_analysis_detail(analysis_id)
    if not record:
        raise HTTPException(status_code=404, detail="分析记录不存在")
    return {"code": 0, "data": record}


@app.get("/api/analyses/{analysis_id}")
async def analysis_detail_with_api_prefix(analysis_id: str):
    return await analysis_detail(analysis_id)


def start_reanalysis_background_job(analysis_id, model=None):
    prepared = prepare_reanalysis_job(analysis_id, model=model)
    thread = threading.Thread(
        target=run_analysis_job,
        args=(
            prepared["job_id"],
            prepared["video_path"],
            prepared["filename"],
            prepared["model"],
            prepared["replace_analysis_id"],
        ),
        daemon=True,
    )
    thread.start()
    return prepared


@app.post("/analyses/{analysis_id}/reanalyze")
async def reanalyze(analysis_id: str, model: str = Form(None)):
    try:
        prepared = start_reanalysis_background_job(analysis_id, model=model)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        print("重新拆解接口异常:", e)
        raise HTTPException(status_code=500, detail="重新拆解任务提交失败，请查看后端日志")

    return {
        "code": 0,
        "job_id": prepared["job_id"],
        "status": "queued",
        "msg": "重新拆解任务已提交，后台分析中",
    }


@app.post("/api/analyses/{analysis_id}/reanalyze")
async def reanalyze_with_api_prefix(analysis_id: str, model: str = Form(None)):
    return await reanalyze(analysis_id, model=model)


@app.delete("/analyses/{analysis_id}")
async def delete_analysis(analysis_id: str):
    deleted = delete_analysis_record(analysis_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="分析记录不存在")
    return {"code": 0, "msg": "删除成功"}


@app.delete("/api/analyses/{analysis_id}")
async def delete_analysis_with_api_prefix(analysis_id: str):
    return await delete_analysis(analysis_id)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8001"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
