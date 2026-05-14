from fastapi import FastAPI, UploadFile, Form, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import asyncio
import os
import json
import base64
import math
import re
import shutil
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import List
import openai
import requests
try:
    import yt_dlp
except ImportError:
    yt_dlp = None
try:
    from moviepy.editor import VideoFileClip
except ModuleNotFoundError:
    from moviepy import VideoFileClip
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
GPTPROTO_CLAUDE_MODEL = os.getenv("GPTPROTO_CLAUDE_MODEL", "claude-sonnet-4-5-20250929")
WHISPER_MODEL_NAME = os.getenv("WHISPER_MODEL", "base")


def is_asr_enabled_by_default():
    value = os.getenv("ENABLE_ASR")
    if value is None:
        return True
    return value.strip().lower() not in {"0", "false", "no", "off"}


ENABLE_ASR = is_asr_enabled_by_default()
# ==========================================================

MODEL_OPTIONS = [
    {
        "label": "gemini-2.5-pro",
        "value": "gemini-2.5-pro",
        "required_key": "GPTPROTO_API_KEY",
        "implemented": True,
    },
    {
        "label": "gemini-2.5-flash",
        "value": "gemini-2.5-flash",
        "required_key": "GPTPROTO_API_KEY",
        "implemented": True,
    },
    {
        "label": "gpt-4o",
        "value": "gpt-4o",
        "required_key": "GPTPROTO_API_KEY",
        "implemented": True,
    },
    {
        "label": "claude-sonnet-4-5-20250929",
        "value": "claude-sonnet-4-5-20250929",
        "required_key": "GPTPROTO_API_KEY",
        "implemented": True,
    },
    {
        "label": "GPT-4o (OpenAI)",
        "value": "gpt4o",
        "required_key": "OPENAI_API_KEY",
        "implemented": False,
    },
    {
        "label": "qwen-turbo",
        "value": "qwen-turbo",
        "required_key": "DASHSCOPE_KEY",
        "implemented": True,
    },
    {
        "label": "文心一言",
        "value": "baidu",
        "required_key": "BAIDU_KEY",
        "implemented": False,
    },
]

PRODUCT_CLASSIFICATION_OPTIONS = [
    "家居用品",
    "厨房用品",
    "家纺布艺",
    "家电",
    "女装与女士内衣",
    "穆斯林时尚",
    "鞋靴",
    "美妆个护",
    "手机与数码",
    "电脑办公",
    "宠物用品",
    "母婴用品",
    "运动与户外",
    "玩具和爱好",
    "家具",
    "五金工具",
    "家装建材",
    "汽车与摩托车",
    "时尚配件",
    "食品饮料",
    "保健",
    "图书&杂志&音频",
    "儿童时尚",
    "男装与男士内衣",
    "箱包",
    "虚拟商品",
    "二手",
    "收藏品",
    "珠宝与衍生品",
    "票务与代金券",
]

PRODUCT_CLASSIFICATION_KEYWORDS = [
    ("手机与数码", ["手机", "数码", "充电", "耳机", "数据线", "手机壳", "phone", "digital", "charger", "earbuds", "case"]),
    ("电脑办公", ["电脑", "办公", "笔记本", "键盘", "鼠标", "打印机", "computer", "laptop", "office", "keyboard", "mouse", "printer"]),
    ("宠物用品", ["宠物", "猫", "狗", "猫砂", "pet", "cat", "dog"]),
    ("母婴用品", ["母婴", "婴儿", "宝宝", "奶瓶", "尿布", "baby", "infant", "diaper"]),
    ("运动与户外", ["运动", "健身", "户外", "露营", "瑜伽", "sport", "fitness", "outdoor", "camping", "yoga"]),
    ("玩具和爱好", ["玩具", "模型", "爱好", "手办", "toy", "hobby", "game"]),
    ("五金工具", ["工具", "五金", "电钻", "螺丝刀", "扳手", "tool", "hardware", "drill", "wrench"]),
    ("家装建材", ["家装", "建材", "装修", "墙纸", "灯具", "home improvement", "building", "decor"]),
    ("汽车与摩托车", ["汽车", "摩托", "车载", "车灯", "auto", "car", "motorcycle", "vehicle"]),
    ("时尚配件", ["配饰", "帽子", "围巾", "腰带", "太阳镜", "accessory", "accessories", "hat", "belt", "sunglasses"]),
    ("食品饮料", ["食品", "饮料", "零食", "咖啡", "茶", "food", "drink", "beverage", "snack", "coffee", "tea"]),
    ("保健", ["保健", "营养", "维生素", "补剂", "health", "wellness", "vitamin", "supplement"]),
    ("图书&杂志&音频", ["图书", "杂志", "音频", "书", "book", "magazine", "audio"]),
    ("儿童时尚", ["童装", "儿童时尚", "儿童服装", "kids fashion", "children fashion"]),
    ("男装与男士内衣", ["男装", "男士内衣", "男士服装", "menswear", "men's clothing", "men clothing"]),
    ("女装与女士内衣", ["女装", "女士内衣", "女士服装", "裙", "连衣裙", "women", "womenswear", "lingerie", "dress"]),
    ("穆斯林时尚", ["穆斯林", "头巾", "hijab", "muslim"]),
    ("鞋靴", ["鞋", "靴", "运动鞋", "凉鞋", "shoe", "shoes", "boots", "sneaker"]),
    ("箱包", ["箱包", "包", "背包", "手提包", "行李箱", "bag", "backpack", "handbag", "luggage"]),
    ("美妆个护", ["美妆", "个护", "护肤", "彩妆", "洗护", "香水", "口红", "精华", "面霜", "beauty", "skincare", "makeup", "cosmetic", "personal care", "serum", "cream"]),
    ("家居用品", ["家居", "收纳", "清洁", "浴室", "卧室", "home", "household", "storage", "cleaning", "bathroom"]),
    ("厨房用品", ["厨房", "厨具", "锅", "餐具", "kitchen", "cookware", "utensil"]),
    ("家纺布艺", ["家纺", "床品", "被子", "窗帘", "地毯", "textile", "bedding", "curtain", "rug"]),
    ("家电", ["家电", "电器", "吸尘器", "空气炸锅", "appliance", "vacuum", "air fryer"]),
    ("家具", ["家具", "椅子", "桌子", "沙发", "柜", "furniture", "chair", "table", "sofa"]),
    ("虚拟商品", ["虚拟商品", "数字商品", "充值", "virtual", "digital goods"]),
    ("二手", ["二手", "used", "second hand", "pre-owned"]),
    ("收藏品", ["收藏", "藏品", "collectible", "collectibles"]),
    ("珠宝与衍生品", ["珠宝", "首饰", "项链", "戒指", "jewelry", "jewellery", "necklace", "ring"]),
    ("票务与代金券", ["票", "门票", "代金券", "券", "ticket", "voucher", "coupon"]),
]

BACKEND_DIR = Path(__file__).resolve().parent
BASE_DIR = BACKEND_DIR.parent
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
# 任务状态已迁移到 SQLite，这里只保留取消事件（内存线程对象无法持久化）
job_cancel_events = {}
analysis_jobs_lock = threading.Lock()
analysis_pipeline_lock = threading.Lock()


class AnalysisCancelled(RuntimeError):
    pass


class VideoDownloadError(RuntimeError):
    pass


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
补充判断：如果是镜前 GRWM POV / 对镜自拍试穿，创作者按正面亮相、侧身/背面转身、版型/洗水/剪裁/尺码/购买信息这样的固定顺序展示单件服装，优先判为“仪式步骤型”，不要创造“穿搭展示型”等体系外小类。
补充判断：如果是护肤/护发/美妆/洗护产品嵌入个人护理流程，字幕或画面包含使用频率、使用顺序、按摩/涂抹/清洗等操作步骤、成分说明、使用后体验中的至少两类，优先判为“仪式步骤型”。即使开头有强情绪钩子或个人困扰，也不要仅凭开头判为“情感叙事型”；情感只作为黄金3秒或分镜标题处理。

4. 分屏对比
适用判断：左右分屏、前后对比、有无产品对比、竞品/平替对比、淘汰赛式测试；核心是直观证明差异。
小类：
- 产品对比型：同款或多个产品、款式、颜色、尺码、姿态被同框或分屏展示，重点是让观众直接比较选择。
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
- 产品对比：两个或多个产品、品牌、方案被同框、分屏、口播或字幕放在一起比较，建立选择关系。
- 产品差异：单个产品相对旧方法、普通产品、常规方案或竞品的不同点；如果已经形成明确双对象比较，优先用“产品对比”。
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
- 行动号召：引导点击链接、购物车、下方链接、评论区、主页，或明确推荐观众选择、购买、下单某个品牌/产品。
"""

MARKETING_TACTIC_TAXONOMY = """
卖点角度分类体系：
这些角度用于判断视频主要用什么购买理由说服观众，必须选择一个主角度和一个小类。
1. 专家背书
- 从业者内幕：在职专业人士、行业人士或真实从业者揭露自己私下会用什么。
- 专业背书：持有资质的医生、营养师、教练、技师、达人测评人等推荐或解释。
- 机构认证：官方认证、实验室报告、监管批准、临床数据、专利或检测报告建立可信度。
- 反向信任：先批评热门产品、行业误区或夸大宣传，再推荐当前产品建立信任。

2. 展示效果
- 实时演示：在镜头前实时展示产品效果，强调无剪切、无编辑、眼见为实。
- 对照测试：同时测试产品与对照组、竞品、旧方法或错误方法，直观看出差异。
- 前后时间线：通过使用前后、多个时间节点或连续变化证明效果积累。
- 个人蜕变故事：讲述产品如何改变创作者生活、状态、外貌或体验。
- 用户证言集：汇总多条用户评价、评分、评论区反馈或购买数据作为社会证明。
- 数据证明：使用具体数字、实验室结果、临床数据、续航时长或性能指标证明有效。

3. 轻松便捷
- 免决策：把产品定位为唯一明显选择，终结选择疲劳或复杂挑选。
- 随时随地：展示产品在旅行、通勤、户外、车内、包里等非理想场所也能用。
- 零门槛：证明任何人无需技能、经验或复杂安装也能成功使用。
- 省时间：强调几秒、几分钟、快速完成或替代长流程。
- 省步骤：展示一个简单动作替代多个步骤、多个工具或繁琐准备。

4. 制造紧迫感
- 库存警告：产品即将售罄、此前已售罄、刚补货、库存有限或快没了。
- 限时折扣：即将过期的折扣、coupon、deal、today only、倒计时、截止日期等促销时效。仅出现 sale、price、right now 但没有时间限制或库存压力时，优先归为价格优势。
- 渠道独占：强调只有 TikTok Shop、直播间、某渠道或当前链接可以买到。
- 社证加速：用近期高购买量、评论区催促、爆单、榜单等制造跟风压力。

5. 天然安全
- 成分透明：精确列出包含和不包含的成分，如天然、有机、无添加、无酒精、低糖。
- 敏感群体安全：证明产品对儿童、婴儿、宠物、敏感肌、孕妇或家庭环境安全。
- 安全恐吓：警告竞品、旧方法或常见成分里的隐藏危险，再引出当前产品。
- 低负担安心：强调无毒、低刺激、环保、食品级、纯棉、clean ingredients 等低风险。

6. 价格优势
- 隐性成本曝光：揭示观众在无效替代品、旧方法、耗材或错误购买上浪费了多少钱。
- 替代价值：展示一个产品替代多个昂贵物品、多个工具或多次服务，计算总节省金额。
- 日均成本拆解：把总价拆成日均、每次、每份、每件或 per serving 的小成本。
- 平替发现：把发现平价替代品、dupe、alternative 包装成寻宝式胜利。
- 直接比价：把两个产品、品牌或方案与价格标签并排展示，证明更低价格获得相似品质。
- 普通折扣价：强调原价、全价、很少打折、现在 sale price 或 look at the price 的划算感，但没有明确倒计时或库存稀缺。

7. 贩卖生活方式
- 圈层标识：把产品包装为属于某个社群、风格圈层、亚文化或人群身份的标识。
- 理想自我投射：把产品与观众想成为的人、状态、身材、风格或生活秩序连接起来。
- 送礼叙事：把产品定位为节日、关系、家庭、朋友或伴侣场景里的完美礼物。
- 场景代入：将产品自然嵌入令人向往的生活场景，如庭院、卧室、旅行、派对、通勤。
- 文化认同：将产品与流行美学、TikTok 趋势、亚文化、季节氛围或文化运动关联。
- 审美升级：把产品包装成个人审美、居家氛围、穿搭品味或生活质感的升级。

黄金3秒钩子分类体系：
这些钩子只根据视频开头约 0-3 秒或最早分镜判断。并非每条爆款视频都有明确黄金3秒；只有开头存在强钩子时才选择主钩子和小类，没有明确命中时 golden_3s_* 字段留空。
1. 提问式
- 痛点提问：直接问观众是否遇到某个困扰，例如 Got shedding pets?
- 好奇提问：用“你知道吗/为什么/有没有发现”制造信息缺口。
- 比价追问：用 Which is better、X vs Y、贵价 vs 平价等便宜选项对比昂贵选项。
- 成本提问：追问真实花费、单次成本、总价或浪费多少钱，触发价格敏感。
- 共鸣提问：追问观众日常是否也经历某个烦恼、尴尬、需求或生活场景。
- 从众提问：用“为什么所有人都在做/买/聊 X”触发错失恐惧或社交好奇。
- 场景驱动型：用特定场景里的问题开场，例如宠物家庭、夏日庭院、通勤、健身、浴室清洁。

2. 挑战式
- 悬念验证：以“这个真的有用吗？”“我来试试看”的框架制造不确定感。
- 潮流参与：加入观众能立即认出的病毒式趋势、音乐、格式或热门挑战。
- 极限测试：将产品置于极端、荒谬、高压力或高难度条件下测试耐久和效果。
- 参与邀请：邀请观众猜测结果、一起见证、评论选择或接受挑战。
- 故事悬念：以个人危机、转折点、失败经历或未揭晓结果开场。
- 场景还原：还原观众每天经历的真实生活场景，让人想看解决过程。

3. 秘诀/技巧
- 避坑技巧：Learn from my mistakes、别踩坑、我早知道就好了。
- 省钱秘笈：隐藏折扣、童码/平替/购买路径、怎么更便宜买。
- 权威对抗：声称专家、品牌、平台或权威机构没有公开某个重要信息。
- 圈内信息：承诺提供只有行业内部人士、老用户或懂行的人才知道的信息。
- 捷径承诺：承诺用更快、更省事、更少步骤的方法实现某个结果。
- 稀缺框架：声称只有少数人知道、很少人会说、别让太多人知道。
- 生活妙招：以编号技巧清单、实用 hack、便宜好物清单或快速做法开场。
注意：普通“我来告诉你这个 sale”不算省钱秘笈；必须有隐藏路径、避坑经验、购买技巧、折扣入口或反常识省钱方法。

4. 震撼数据
- 逆认知数据：用数据直接反驳大众观点、常见误区或直觉判断。
- 结果前置：开头先抛出最终结果数字或巨大变化，再解释产品如何做到。
- 大数锚定：用销售额、播放量、购买人数、库存量、评论量等规模数字建立冲击。
- 百分比冲击：用百分比、倍数、提升/下降比例证明效果或价值。
- 时间线震撼：把惊人效果压缩在极短时间框架内展示，如几秒、几分钟、几天。
- 对比冲击：将数字与意想不到的参照物对比，放大价值差异。

5. 争议式
- 立场对抗：以争议性个人观点、unpopular opinion、I said what I said 迫使观众选边站。
- 价格挑衅：用便宜选项挑战昂贵选项，暗示效果一样或更值得买。
- 情绪挑衅：以可见的沮丧、愤怒、恼火、吐槽或强烈反应开场。
- 槽点揭露：指出热门产品、品牌、做法或旧方案的具体缺陷。
- 颠覆认知：直接反驳一个广泛接受的观点、常见做法或行业话术。
- 冲突叙事：用两方观点、两个选择、踩雷到真香等矛盾推动观看。
- 禁忌揭秘：承诺揭露行业、品牌或平台对消费者隐瞒的信息。
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

    object_start = cleaned.find("{")
    object_end = cleaned.rfind("}")
    array_start = cleaned.find("[")
    array_end = cleaned.rfind("]")
    if object_start != -1 and object_end != -1 and object_start < object_end and (
        array_start == -1 or object_start < array_start
    ):
        return cleaned[object_start:object_end + 1].strip()
    if array_start != -1 and array_end != -1 and array_start < array_end:
        return cleaned[array_start:array_end + 1].strip()

    return cleaned


def init_db(db_path=DB_PATH, mark_interrupted_jobs=False):
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
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
                product_classification TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analysis_versions (
                analysis_id TEXT NOT NULL,
                model TEXT NOT NULL,
                result_json TEXT NOT NULL,
                formula TEXT,
                subtype TEXT,
                category_reason TEXT,
                product_classification TEXT,
                created_at TEXT NOT NULL,
                PRIMARY KEY (analysis_id, model)
            )
            """
        )
        for table_name in ("analyses", "analysis_versions"):
            columns = [row[1] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()]
            if "product_classification" not in columns:
                conn.execute(f"ALTER TABLE {table_name} ADD COLUMN product_classification TEXT")
        conn.execute(
            """
            INSERT OR IGNORE INTO analysis_versions (
                analysis_id, model, result_json, formula, subtype, category_reason, product_classification, created_at
            )
            SELECT id, model, result_json, formula, subtype, category_reason, product_classification, created_at
            FROM analyses
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analysis_jobs (
                job_id TEXT PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'queued',
                filename TEXT,
                model TEXT,
                message TEXT,
                analysis_id TEXT,
                video_url TEXT,
                replace_analysis_id TEXT,
                cancel_requested INTEGER DEFAULT 0,
                timing_json TEXT,
                data TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        if mark_interrupted_jobs:
            # 清理旧的无主任务：如果后端重启了，之前 processing/queued 的任务已经死了。
            conn.execute(
                """
                UPDATE analysis_jobs
                SET status = 'failed',
                    message = '后端重启，任务中断',
                    updated_at = ?
                WHERE status IN ('queued', 'processing')
                """,
                (datetime.now(timezone.utc).isoformat(),)
            )
        conn.commit()
    finally:
        conn.close()


def _job_row_to_dict(row):
    if not row:
        return None
    record = dict(row)
    record["cancel_requested"] = bool(record.get("cancel_requested", 0))
    # 解析 JSON 字段
    val = record.pop("timing_json", None)
    if val and isinstance(val, str):
        try:
            record["timing"] = json.loads(val)
        except json.JSONDecodeError:
            record["timing"] = None
    val = record.pop("data", None)
    if val and isinstance(val, str):
        try:
            record["data"] = json.loads(val)
        except json.JSONDecodeError:
            pass
    return record


def _row_to_dict(row):
    return dict(row) if row else None


def normalize_product_classification(value):
    text = str(value or "").strip()
    if not text:
        return ""
    if text in PRODUCT_CLASSIFICATION_OPTIONS:
        return text

    lowered = text.lower()
    for option, keywords in PRODUCT_CLASSIFICATION_KEYWORDS:
        if any(product_classification_keyword_matches(lowered, keyword) for keyword in keywords):
            return option
    return ""


def product_classification_keyword_matches(text, keyword):
    keyword_text = str(keyword or "").strip().lower()
    if not keyword_text:
        return False
    if re.search(r"[a-z0-9]", keyword_text):
        return re.search(rf"(?<![a-z0-9]){re.escape(keyword_text)}(?![a-z0-9])", text) is not None
    return keyword_text in text


def infer_product_classification(items):
    for item in items:
        if not isinstance(item, dict):
            continue
        normalized = normalize_product_classification(item.get("product_classification"))
        if normalized:
            return normalized
    for item in items:
        if not isinstance(item, dict):
            continue
        normalized = normalize_product_classification(item.get("product_category"))
        if normalized:
            return normalized
    return ""


def _pending_job_to_history_record(job):
    return {
        "id": job["job_id"],
        "job_id": job["job_id"],
        "is_pending_job": True,
        "status": job["status"],
        "message": job.get("message") or "",
        "filename": job.get("filename") or "未命名视频",
        "model": job.get("model") or "",
        "video_url": job.get("video_url") or "",
        "formula": "",
        "subtype": "",
        "category_reason": job.get("message") or "",
        "product_classification": "",
        "created_at": job.get("created_at") or job.get("updated_at") or "",
        "shot_count": 0,
        "cover_url": "",
        "models": [job["model"]] if job.get("model") else [],
        "model_count": 1 if job.get("model") else 0,
    }


@contextmanager
def _connect_db(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


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
    record = {
        **record,
        "product_classification": normalize_product_classification(record.get("product_classification")),
    }
    with _connect_db(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO analyses (
                id, filename, model, video_path, video_url, result_json,
                formula, subtype, category_reason, product_classification, created_at
            ) VALUES (
                :id, :filename, :model, :video_path, :video_url, :result_json,
                :formula, :subtype, :category_reason, :product_classification, :created_at
            )
            """,
            record,
        )
        save_analysis_version(conn, record["id"], record["model"], record)
        conn.commit()


def save_analysis_version(conn, analysis_id, model, record):
    conn.execute(
        """
        INSERT INTO analysis_versions (
            analysis_id, model, result_json, formula, subtype, category_reason, product_classification, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(analysis_id, model) DO UPDATE SET
            result_json = excluded.result_json,
            formula = excluded.formula,
            subtype = excluded.subtype,
            category_reason = excluded.category_reason,
            product_classification = excluded.product_classification,
            created_at = excluded.created_at
        """,
        (
            analysis_id,
            model,
            record.get("result_json", "[]"),
            record.get("formula", ""),
            record.get("subtype", ""),
            record.get("category_reason", ""),
            normalize_product_classification(record.get("product_classification")),
            record.get("created_at") or datetime.now(timezone.utc).isoformat(),
        ),
    )


def store_result_frame_images(analysis_id, items, stored_frame_dir=STORED_FRAME_DIR, temp_frame_dir=TEMP_FRAME_DIR, frame_scope=None):
    frame_scope = frame_scope or analysis_id
    analysis_frame_dir = Path(stored_frame_dir) / frame_scope
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
            item["image_url"] = f"/storage/frames/{frame_scope}/{frame_name}"

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
    frame_scope = f"{analysis_id}/{safe_storage_key(model)}"
    store_result_frame_images(analysis_id, items, stored_frame_dir, temp_frame_dir, frame_scope=frame_scope)
    normalized_result_json = json.dumps(items, ensure_ascii=False)
    first_item = next((item for item in items if isinstance(item, dict)), {})
    product_classification = infer_product_classification(items)
    created_at = datetime.now(timezone.utc).isoformat()
    with _connect_db(db_path) as conn:
        version_record = {
            "result_json": normalized_result_json,
            "formula": first_item.get("viral_formula", ""),
            "subtype": first_item.get("formula_subtype", ""),
            "category_reason": first_item.get("category_reason", ""),
            "product_classification": product_classification,
            "created_at": created_at,
        }
        save_analysis_version(conn, analysis_id, model, version_record)
        conn.execute(
            """
            UPDATE analyses
            SET model = ?,
                result_json = ?,
                formula = ?,
                subtype = ?,
                category_reason = ?,
                product_classification = ?,
                created_at = ?
            WHERE id = ?
            """,
            (
                model,
                normalized_result_json,
                first_item.get("viral_formula", ""),
                first_item.get("formula_subtype", ""),
                first_item.get("category_reason", ""),
                product_classification,
                created_at,
                analysis_id,
            ),
        )
        conn.commit()

    return {
        "analysis_id": analysis_id,
        "video_url": record["video_url"],
        "data": normalized_result_json,
    }


def cancel_active_jobs_for_analysis(analysis_id, db_path=DB_PATH):
    with analysis_jobs_lock:
        with _connect_db(db_path) as conn:
            rows = conn.execute(
                """
                SELECT job_id
                FROM analysis_jobs
                WHERE (analysis_id = ? OR replace_analysis_id = ?)
                  AND status IN ('queued', 'processing')
                """,
                (analysis_id, analysis_id),
            ).fetchall()

    for row in rows:
        cancel_analysis_job(row["job_id"], db_path=db_path)


def cancel_pending_job_record(job_id, db_path=DB_PATH):
    job = get_analysis_job(job_id, db_path=db_path)
    if not job or is_terminal_job_status(job.get("status")):
        return False
    cancel_analysis_job(job_id, db_path=db_path)
    return True


def delete_analysis_record(analysis_id, db_path=DB_PATH, stored_frame_dir=STORED_FRAME_DIR):
    record = fetch_analysis_detail(analysis_id, db_path)
    if not record:
        return cancel_pending_job_record(analysis_id, db_path=db_path)

    cancel_active_jobs_for_analysis(analysis_id, db_path=db_path)

    with _connect_db(db_path) as conn:
        conn.execute("DELETE FROM analysis_versions WHERE analysis_id = ?", (analysis_id,))
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
                   category_reason, product_classification, result_json, created_at
            FROM analyses
            ORDER BY created_at DESC
            """
        ).fetchall()
        version_rows = conn.execute(
            """
            SELECT analysis_id, model
            FROM analysis_versions
            ORDER BY created_at DESC
            """
        ).fetchall()
        pending_job_rows = conn.execute(
            """
            SELECT job_id, status, filename, model, message, analysis_id,
                   video_url, created_at, updated_at
            FROM analysis_jobs
            WHERE status IN ('queued', 'processing')
              AND replace_analysis_id IS NULL
              AND analysis_id IS NULL
            ORDER BY created_at DESC
            """
        ).fetchall()

    models_by_analysis = {}
    for row in version_rows:
        models_by_analysis.setdefault(row["analysis_id"], [])
        if row["model"] not in models_by_analysis[row["analysis_id"]]:
            models_by_analysis[row["analysis_id"]].append(row["model"])

    records = []
    for row in rows:
        record = _row_to_dict(row)
        result_items = parse_result_items(record.pop("result_json", "[]"))
        if not record.get("product_classification"):
            record["product_classification"] = infer_product_classification(result_items)
        record["shot_count"] = len(result_items)
        record["cover_url"] = next((item.get("image_url", "") for item in result_items if item.get("image_url")), "")
        record["models"] = models_by_analysis.get(record["id"], [record["model"]])
        record["model_count"] = len(record["models"])
        records.append(record)
    records.extend(_pending_job_to_history_record(_row_to_dict(row)) for row in pending_job_rows)
    records.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    return records


def fetch_analysis_detail(analysis_id, db_path=DB_PATH):
    init_db(db_path)
    with _connect_db(db_path) as conn:
        row = conn.execute(
            """
            SELECT id, filename, model, video_path, video_url, result_json,
                   formula, subtype, category_reason, product_classification, created_at
            FROM analyses
            WHERE id = ?
            """,
            (analysis_id,),
        ).fetchone()
        version_rows = conn.execute(
            """
            SELECT model, result_json, formula, subtype, category_reason, product_classification, created_at
            FROM analysis_versions
            WHERE analysis_id = ?
            ORDER BY created_at DESC
            """,
            (analysis_id,),
        ).fetchall()

    record = _row_to_dict(row)
    if not record:
        return None

    record["data"] = parse_result_items(record.pop("result_json", "[]"))
    if not record.get("product_classification"):
        record["product_classification"] = infer_product_classification(record["data"])
    record["shot_count"] = len(record["data"])
    versions = []
    for version_row in version_rows:
        version = _row_to_dict(version_row)
        version["data"] = parse_result_items(version.pop("result_json", "[]"))
        if not version.get("product_classification"):
            version["product_classification"] = infer_product_classification(version["data"])
        version["shot_count"] = len(version["data"])
        version["is_active"] = version["model"] == record["model"]
        versions.append(version)

    if not versions:
        versions = [
            {
                "model": record["model"],
                "formula": record.get("formula", ""),
                "subtype": record.get("subtype", ""),
                "category_reason": record.get("category_reason", ""),
                "product_classification": record.get("product_classification", ""),
                "created_at": record.get("created_at", ""),
                "data": record["data"],
                "shot_count": record["shot_count"],
                "is_active": True,
            }
        ]

    record["versions"] = versions
    return record


def safe_filename(filename):
    stem = Path(filename or "video.mp4").stem
    suffix = Path(filename or "video.mp4").suffix or ".mp4"
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._") or "video"
    safe_suffix = re.sub(r"[^A-Za-z0-9.]+", "", suffix) or ".mp4"
    return f"{safe_stem}{safe_suffix}"


def safe_storage_key(value):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "default")).strip("._") or "default"


def guess_video_filename_from_url(video_url):
    try:
        from urllib.parse import urlparse, unquote

        parsed = urlparse(video_url)
        filename = Path(unquote(parsed.path or "")).name
    except Exception:
        filename = ""
    return safe_filename(filename or "downloaded-video.mp4")


def normalize_download_error(error):
    message = str(error or "").strip()
    lowered = message.lower()
    if "unsupported url" in lowered:
        reason = "当前链接平台暂不支持自动下载"
    elif "private" in lowered or "login" in lowered or "sign in" in lowered or "cookies" in lowered:
        reason = "该视频可能需要登录、Cookie 或权限才能下载"
    elif "unavailable" in lowered or "removed" in lowered or "not found" in lowered or "404" in lowered:
        reason = "该视频不可用、已删除或链接无法访问"
    elif "timeout" in lowered or "timed out" in lowered:
        reason = "下载超时，可能是网络或平台限制造成"
    elif "http error 403" in lowered or "forbidden" in lowered:
        reason = "平台拒绝下载请求，可能需要登录或存在防盗链限制"
    else:
        reason = message or "未知下载错误"
    return f"{reason}。请下载到本地后使用“上传视频”手动上传解析。"


def download_video_from_url(video_url, target_dir):
    url = (video_url or "").strip()
    if not re.match(r"^https?://", url, re.IGNORECASE):
        raise VideoDownloadError("请输入以 http:// 或 https:// 开头的视频链接。请改为手动上传视频文件。")
    if yt_dlp is None:
        raise VideoDownloadError("后端未安装 yt-dlp，暂时无法从 TikTok、Instagram 或 YouTube 链接下载。请安装依赖后重试，或手动上传视频文件。")

    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(target_dir / "%(title).120B-%(id)s.%(ext)s")
    options = {
        "outtmpl": output_template,
        "format": "bv*+ba/b[ext=mp4]/b",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 30,
        "retries": 1,
    }

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            if info.get("_type") == "playlist":
                entries = [item for item in info.get("entries") or [] if item]
                info = entries[0] if entries else info
            downloaded_path = ydl.prepare_filename(info)
    except Exception as e:
        raise VideoDownloadError(normalize_download_error(e)) from e

    candidates = []
    if downloaded_path:
        candidates.append(Path(downloaded_path))
        candidates.append(Path(downloaded_path).with_suffix(".mp4"))
    candidates.extend(sorted(target_dir.glob("*"), key=lambda path: path.stat().st_mtime, reverse=True))
    video_path = next((path for path in candidates if path.exists() and path.is_file()), None)
    if not video_path:
        raise VideoDownloadError("链接下载完成后没有找到视频文件。请手动上传视频文件。")

    filename = safe_filename(info.get("title") or video_path.name)
    if not Path(filename).suffix:
        filename = f"{filename}{video_path.suffix or '.mp4'}"
    return video_path, filename


def get_model_api_key(key_name):
    if key_name == "GPTPROTO_API_KEY":
        return GPTPROTO_API_KEY
    if key_name == "OPENAI_API_KEY":
        return OPENAI_API_KEY
    if key_name == "DASHSCOPE_KEY":
        return DASHSCOPE_KEY
    if key_name == "BAIDU_KEY":
        return BAIDU_KEY
    return ""


def get_available_model_options():
    options = []
    for option in MODEL_OPTIONS:
        if not option.get("implemented", True):
            continue
        required_key = option.get("required_key")
        if required_key and not str(get_model_api_key(required_key) or "").strip():
            continue
        options.append({
            "label": option["label"],
            "value": option["value"],
        })
    return options


def persist_analysis(video_path, original_filename, model, result_json):
    analysis_id = uuid.uuid4().hex
    filename = safe_filename(original_filename)
    stored_video_name = f"{analysis_id}_{filename}"
    stored_video_path = STORED_VIDEO_DIR / stored_video_name
    shutil.copy2(video_path, stored_video_path)

    items = parse_result_items(result_json)
    store_result_frame_images(analysis_id, items, frame_scope=f"{analysis_id}/{safe_storage_key(model)}")

    normalized_result_json = json.dumps(items, ensure_ascii=False)
    first_item = next((item for item in items if isinstance(item, dict)), {})
    product_classification = infer_product_classification(items)
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
        "product_classification": product_classification,
        "created_at": created_at,
    }
    save_analysis_record(record)
    return {
        "analysis_id": analysis_id,
        "video_url": video_url,
        "data": normalized_result_json,
    }


def persist_job_preview_video(job_id, video_path, filename):
    safe_name = safe_filename(filename)
    stored_video_name = f"job_{safe_storage_key(job_id)}_{safe_name}"
    stored_video_path = STORED_VIDEO_DIR / stored_video_name
    shutil.copy2(video_path, stored_video_path)
    return f"/storage/videos/{stored_video_name}"


def update_analysis_job(job_id, db_path=DB_PATH, **updates):
    with analysis_jobs_lock:
        with _connect_db(db_path) as conn:
            row = conn.execute(
                "SELECT * FROM analysis_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            if not row:
                return None
            current = _job_row_to_dict(row)
            # 如果任务已被取消，且本次更新不是取消操作，则拒绝更新
            if current.get("status") == "canceled" and updates.get("status") != "canceled":
                return sanitize_analysis_job(current)

            now = datetime.now(timezone.utc).isoformat()
            allowed_fields = {
                "status", "message", "analysis_id", "video_url",
                "replace_analysis_id", "cancel_requested", "timing_json", "data", "model"
            }
            field_mapping = {"timing": "timing_json"}
            set_clauses = []
            values = []
            for key, value in updates.items():
                db_key = field_mapping.get(key, key)
                if db_key in allowed_fields:
                    set_clauses.append(f"{db_key} = ?")
                    if db_key == "timing_json" and isinstance(value, (dict, list)):
                        values.append(json.dumps(value, ensure_ascii=False))
                    elif db_key == "cancel_requested":
                        values.append(1 if value else 0)
                    else:
                        values.append(value)
            if not set_clauses:
                return sanitize_analysis_job(current)

            set_clauses.append("updated_at = ?")
            values.append(now)
            values.append(job_id)

            conn.execute(
                f"UPDATE analysis_jobs SET {', '.join(set_clauses)} WHERE job_id = ?",
                values,
            )
            conn.commit()

            new_row = conn.execute(
                "SELECT * FROM analysis_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            return sanitize_analysis_job(_job_row_to_dict(new_row))


def get_analysis_job(job_id, db_path=DB_PATH):
    with analysis_jobs_lock:
        with _connect_db(db_path) as conn:
            row = conn.execute(
                "SELECT * FROM analysis_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            return sanitize_analysis_job(_job_row_to_dict(row))


def get_analysis_job_by_analysis_id(analysis_id, db_path=DB_PATH):
    with analysis_jobs_lock:
        with _connect_db(db_path) as conn:
            rows = conn.execute(
                """
                SELECT * FROM analysis_jobs
                WHERE analysis_id = ? OR replace_analysis_id = ?
                ORDER BY updated_at DESC
                """,
                (analysis_id, analysis_id),
            ).fetchall()
        if not rows:
            return None
        jobs = [sanitize_analysis_job(_job_row_to_dict(r)) for r in rows]
        active_jobs = [j for j in jobs if not is_terminal_job_status(j.get("status"))]
        candidates = active_jobs or jobs
        return candidates[0]


def sanitize_analysis_job(job):
    return {key: value for key, value in dict(job).items() if not key.startswith("_")}


def is_terminal_job_status(status):
    return status in {"completed", "failed", "canceled"}


def cancel_analysis_job(job_id, db_path=DB_PATH):
    with analysis_jobs_lock:
        with _connect_db(db_path) as conn:
            row = conn.execute(
                "SELECT * FROM analysis_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            if not row:
                return None
            job = _job_row_to_dict(row)
            if is_terminal_job_status(job.get("status")):
                return sanitize_analysis_job(job)

            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                """
                UPDATE analysis_jobs
                SET cancel_requested = 1,
                    status = 'canceled',
                    message = '任务已取消，后台正在停止当前处理',
                    updated_at = ?
                WHERE job_id = ?
                """,
                (now, job_id),
            )
            conn.commit()

            new_row = conn.execute(
                "SELECT * FROM analysis_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            result = sanitize_analysis_job(_job_row_to_dict(new_row))

    # 触发内存中的取消事件（让正在运行的线程感知到）
    event = job_cancel_events.get(job_id)
    if event:
        event.set()
    return result


def check_analysis_cancelled(job_id, db_path=DB_PATH):
    if not job_id:
        return
    with analysis_jobs_lock:
        # 查数据库标志位
        with _connect_db(db_path) as conn:
            row = conn.execute(
                "SELECT cancel_requested, status FROM analysis_jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
            db_canceled = bool(row and (row["cancel_requested"] or row["status"] == "canceled"))
        # 查内存事件
        event = job_cancel_events.get(job_id)
        event_canceled = bool(event and event.is_set())
    if db_canceled or event_canceled:
        raise AnalysisCancelled("任务已取消")


def create_analysis_job(filename, model, db_path=DB_PATH):
    job_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    with analysis_jobs_lock:
        with _connect_db(db_path) as conn:
            conn.execute(
                """
                INSERT INTO analysis_jobs (
                    job_id, status, filename, model, message,
                    cancel_requested, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (job_id, "queued", filename, model, "任务已提交，等待后台分析", now, now),
            )
            conn.commit()
        # 内存里给这个 job 准备一个取消事件
        job_cancel_events[job_id] = threading.Event()
    return job_id


def prepare_reanalysis_job(analysis_id, model=None, db_path=DB_PATH, job_upload_dir=JOB_UPLOAD_DIR):
    record = fetch_analysis_detail(analysis_id, db_path)
    if not record:
        raise ValueError("分析记录不存在")

    source_video_path = Path(record.get("video_path") or "")
    if not source_video_path.exists() or not source_video_path.is_file():
        raise FileNotFoundError("原视频文件不存在，无法重新拆解")

    target_model = model or record.get("model") or "gpt-4o"
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


init_db(mark_interrupted_jobs=True)


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


GRANULARITY_OPTIONS = {"coarse", "balanced", "fine"}


def normalize_breakdown_granularity(value):
    value = (value or "balanced").strip().lower()
    return value if value in GRANULARITY_OPTIONS else "balanced"


def extract_transcript_time_ranges(transcript):
    ranges = []
    for match in re.finditer(
        r"(?P<start>\d+(?:[.,]\d+)?|\d+:\d+(?::\d+)?(?:[.,]\d+)?)\s*-->\s*"
        r"(?P<end>\d+(?:[.,]\d+)?|\d+:\d+(?::\d+)?(?:[.,]\d+)?)",
        transcript or "",
    ):
        start = parse_time_value(match.group("start"), None)
        end = parse_time_value(match.group("end"), None)
        if start is None or end is None:
            continue
        if end < start:
            start, end = end, start
        ranges.append((start, end))
    return ranges


def extract_transcript_segments(transcript):
    segments = []
    for line in str(transcript or "").splitlines():
        match = re.match(
            r"\s*(?P<start>\d+(?:[.,]\d+)?|\d+:\d+(?::\d+)?(?:[.,]\d+)?)\s*-->\s*"
            r"(?P<end>\d+(?:[.,]\d+)?|\d+:\d+(?::\d+)?(?:[.,]\d+)?)\s*(?P<text>.*)\s*$",
            line,
        )
        if not match:
            continue
        start = parse_time_value(match.group("start"), None)
        end = parse_time_value(match.group("end"), None)
        text = match.group("text").strip()
        if start is None or end is None or not text:
            continue
        if end < start:
            start, end = end, start
        segments.append({"start": start, "end": end, "text": text})
    return segments


def transcript_text_for_time_range(transcript_segments, start_time, end_time):
    if not transcript_segments:
        return ""
    start = parse_time_value(start_time, 0)
    end = parse_time_value(end_time, start)
    if end < start:
        start, end = end, start

    selected = []
    for segment in transcript_segments:
        segment_duration = max(segment["end"] - segment["start"], 0.01)
        midpoint = segment["start"] + segment_duration * 0.5
        overlap = min(end, segment["end"]) - max(start, segment["start"])
        if start <= midpoint < end or overlap / segment_duration >= 0.6:
            selected.append(segment["text"])
    return " ".join(selected).strip()


def text_has_cjk(text):
    return bool(re.search(r"[\u4e00-\u9fff]", str(text or "")))


def fill_storyboard_scripts_from_transcript(items, transcript):
    transcript_segments = extract_transcript_segments(transcript)
    if not transcript_segments:
        return items

    for item in items:
        if not isinstance(item, dict):
            continue
        transcript_script = transcript_text_for_time_range(
            transcript_segments,
            item.get("start_time", 0),
            item.get("end_time", 0),
        )
        if not transcript_script:
            continue

        existing_script = str(item.get("script", "") or "").strip()
        if existing_script and existing_script != transcript_script and text_has_cjk(existing_script) and not item.get("script_translation"):
            item["script_translation"] = existing_script
        item["script"] = transcript_script
    return items


def clamp_timestamp(timestamp, duration):
    return min(max(float(timestamp), 0), max(float(duration or 0) - 0.05, 0))


def dedupe_timestamps(timestamps, duration, min_gap=0.2):
    deduped = []
    for timestamp in sorted(clamp_timestamp(value, duration) for value in timestamps):
        rounded = round(timestamp, 2)
        if deduped and abs(rounded - deduped[-1]) < min_gap:
            continue
        deduped.append(rounded)
    return deduped


def pick_evenly_spaced_values(values, count):
    if count <= 0 or not values:
        return []
    if count >= len(values):
        return list(values)
    if count == 1:
        return [values[len(values) // 2]]

    last_index = len(values) - 1
    indexes = [
        round(index * last_index / (count - 1))
        for index in range(count)
    ]
    return [values[index] for index in indexes]


def compute_priority_visual_frame_timestamps(duration, transcript=None):
    duration = float(duration or 0)
    if duration <= 0:
        return []
    # 当前：前 3 秒固定 3 帧
    timestamps = [0.35, 1.2, 2.4]
    # 可以改成：前 3 秒固定 2 帧，避免和均匀帧过度重叠
    # timestamps = [0.5, 2.0]
    for start, end in extract_transcript_time_ranges(transcript):
        if start < 3:
            continue
        if start > duration:
            continue
        timestamps.append(start + 0.2)
        if end > start + 0.6:
            timestamps.append(end - 0.2)
        midpoint = start + (end - start) * 0.5
        if end - start >= 6:
            timestamps.append(midpoint)

    return dedupe_timestamps(timestamps, duration)


def compute_visual_frame_timestamps(duration, max_frames=None, granularity="balanced", transcript=None):
    duration = float(duration or 0)
    if duration <= 0:
        return []

    granularity = normalize_breakdown_granularity(granularity)
    if max_frames is None:
        if granularity == "coarse":
            target_step = 1.5 if duration <= 30 else 3.0 if duration <= 90 else 5.0
            max_frames = 30 if duration <= 30 else 35 if duration <= 90 else 45
        elif granularity == "fine":
            target_step = 0.75 if duration <= 30 else 1.0 if duration <= 90 else 1.5
            max_frames = 50 if duration <= 30 else 80 if duration <= 90 else 100
        else:
            target_step = 1.0 if duration <= 30 else 2.0 if duration <= 90 else 3.5
            max_frames = 40 if duration <= 30 else 45 if duration <= 90 else 60
    else:
        max_frames = max(1, int(max_frames))
        target_step = duration / max_frames

    target_count = max(1, int(math.ceil(duration / target_step)))
    count = min(max_frames, target_count)
    step = duration / count
    uniform_timestamps = [
        min(index * step + step * 0.45, max(duration - 0.05, 0))
        for index in range(count)
    ]
    priority_timestamps = compute_priority_visual_frame_timestamps(duration, transcript) if transcript is not None else []
    combined = dedupe_timestamps(priority_timestamps + uniform_timestamps, duration)
    if len(combined) <= max_frames:
        return combined

    priority_limit = min(len(priority_timestamps), max(3, int(max_frames * 0.4)))
    selected_priority = priority_timestamps[:priority_limit]
    uniform_budget = max_frames - len(selected_priority)
    selected_uniform = pick_evenly_spaced_values(uniform_timestamps, uniform_budget)
    selected = dedupe_timestamps(selected_priority + selected_uniform, duration)

    if len(selected) < max_frames:
        for timestamp in uniform_timestamps + priority_timestamps[priority_limit:]:
            candidate = round(clamp_timestamp(timestamp, duration), 2)
            if any(abs(candidate - existing) < 0.2 for existing in selected):
                continue
            selected.append(candidate)
            if len(selected) >= max_frames:
                break
    return sorted(selected[:max_frames])


def sample_visual_frames(video_path, max_frames=None, granularity="balanced", transcript=None):
    frames = []
    try:
        clip = VideoFileClip(video_path)
        duration = clip.duration or 0
        if duration <= 0:
            clip.close()
            return frames

        timestamps = compute_visual_frame_timestamps(
            duration,
            max_frames=max_frames,
            granularity=granularity,
            transcript=transcript,
        )

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


def build_gptproto_claude_messages(prompt, visual_frames):
    if not visual_frames:
        return [{"role": "user", "content": prompt}]

    content = [{"type": "text", "text": prompt}]
    for frame in visual_frames:
        frame_id = frame.get("id") or "frame"
        content.append({
            "type": "text",
            "text": f"{frame_id}，时间：{frame.get('timestamp', 0)}s。请只描述这张图中能明确看到的商品和颜色。",
        })
        content.append({
            "type": "file",
            "file": {
                "filename": f"{safe_storage_key(frame_id)}.jpg",
                "file_data": frame["data_url"],
            },
        })

    return [{"role": "user", "content": content}]


def build_gptproto_responses_input(prompt, visual_frames):
    content = [{"type": "input_text", "text": prompt}]
    for frame in visual_frames:
        content.append({
            "type": "input_text",
            "text": f"{frame['id']}，时间：{frame['timestamp']}s。请只描述这张图中能明确看到的商品和颜色。",
        })
        content.append({
            "type": "input_image",
            "image_url": frame["data_url"],
        })

    return [{"role": "user", "content": content}]


def upload_file_to_data_url(upload_file):
    if not upload_file:
        return None
    content = upload_file.file.read()
    if not content:
        return None
    content_type = upload_file.content_type or "image/jpeg"
    encoded = base64.b64encode(content).decode("utf-8")
    return {
        "id": safe_storage_key(Path(upload_file.filename or "product-image").stem or "product-image"),
        "timestamp": 0,
        "data_url": f"data:{content_type};base64,{encoded}",
    }


def extract_gptproto_responses_text(data):
    if isinstance(data, dict):
        output_text = data.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text

        output = data.get("output")
        if isinstance(output, list):
            parts = []
            for item in output:
                if not isinstance(item, dict):
                    continue
                content = item.get("content")
                if not isinstance(content, list):
                    continue
                for content_item in content:
                    if not isinstance(content_item, dict):
                        continue
                    text = content_item.get("text")
                    if isinstance(text, str) and text.strip():
                        parts.append(text)
            if parts:
                return "\n".join(parts)

        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
            content = message.get("content") if isinstance(message, dict) else None
            if isinstance(content, str):
                return content

    raise RuntimeError("gptproto responses 返回结果中未找到文本内容")


def post_with_retries(url, *, headers, json, timeout, max_attempts=3, retry_label="请求"):
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            return requests.post(url, headers=headers, json=json, timeout=timeout)
        except requests.RequestException as e:
            last_error = e
            if attempt >= max_attempts:
                break
            wait_seconds = min(2 ** (attempt - 1), 4)
            print(f"{retry_label} 网络异常，准备重试 {attempt}/{max_attempts}: {e}")
            time.sleep(wait_seconds)
    raise last_error


def format_gptproto_network_error(provider_label, error):
    return (
        f"{provider_label} 网络请求失败：外部接口网络/TLS 连接连续重试后仍失败，"
        f"请稍后重试或切换模型。原始错误: {error}"
    )


def build_granularity_instruction(granularity):
    granularity = normalize_breakdown_granularity(granularity)
    if granularity == "coarse":
        return """
拆解粒度：粗略。优先合并同一商品组、同一场景、同一转化目的下的连续镜头；只有主体/场景/转化目的明显变化时才拆分。适合开箱、试穿、长口播和复盘型视频。60 秒以上视频通常控制在 3-5 个分镜，2-5 分钟视频最多 6 个分镜；多个相近商品可按商品组或阶段合并。
"""
    if granularity == "fine":
        return """
拆解粒度：精细。保留更多有独立转化作用的视觉切点；当价格页、文字贴纸、分屏对比、产品切换、关键动作步骤或行动号召出现时，尽量拆成独立分镜。不要为了细分而切断完整台词。
"""
    return """
拆解粒度：均衡。重大视觉切换和转化目的变化需要拆分；同一商品同一目的下的连续角度、手部细节和过渡 B-roll 可以合并。60 秒以上视频通常控制在 4-6 个分镜，2-5 分钟视频最多 6 个分镜；开箱、试穿、haul、长口播按商品组/叙事阶段合并，不按每个小商品或每次换装机械拆分。
"""


def build_analysis_prompt(transcript, visual_frames=None, granularity="balanced"):
    visual_frames = visual_frames or []
    granularity_note = build_granularity_instruction(granularity)

    # 视觉帧相关说明
    if visual_frames:
        frame_list = "\n".join([
            f"- {f['id']} @ {f['timestamp']}s"
            for f in visual_frames
        ])
        visual_note = f"""
你还会收到按时间顺序排列的视频关键帧图片，每张图都有编号和时间点。
分类、商品品类、场景和分镜必须优先依据关键帧画面证据；字幕或音频可能只是背景音乐歌词，不能把无关歌词当成商品说明。
每个分镜必须绑定一个 evidence_frame 和 evidence_timestamp，描述只能来自该分镜证据帧附近的画面。
如果画面显示服装试穿、穿搭展示、换装、转身展示版型，请识别为服饰/穿搭相关内容，不要写成护肤品、清洁用品或其他画面中不存在的品类。
关键帧清单：
{frame_list}
"""
    else:
        visual_note = """
你只会收到音频转写，因此如果字幕内容像背景音乐歌词、缺少商品信息，请在分类和分镜中保持保守，不要编造画面里不存在的产品。
"""

    scene_description_rules = """
        【scene_description 画面描述规范 - 严格区分于分析解读】
        scene_description 的职责是"画面白描"，让没看过视频的人能靠文字还原画面。必须遵守：

        1. 客观白描优先：只写镜头里真实出现的人、物、动作、位置、文字、颜色、材质。禁止写"旨在...""为了...""建立...""强化...""证明..."等目的性分析语言。
        2. 人物具体化：如果画面中出现人物，描述其可见特征（发色、发型、肤色、穿着、表情、姿态），不要泛称"创作者""女士"。例如："一位金发女士""一位穿黑色吊带的深肤色女性"。
        3. 动作链具体化：按时间顺序写清手部/面部/产品的具体动作，例如"用食指蘸取盘中左下角的香槟色亮片，点涂在上眼睑中央"，而不是"展示产品使用方法"。
        4. 产品只描述可见形态：不要过度推断品类名。看到"一个圆形盘状彩妆品，内含四格不同颜色的粉块"即可，不要强行命名为"四色修容高光腮红盘"（除非包装/口播明确写了这个品名）。
        5. 画面文字必须原样提取：如果画面中有英文/其他语言字幕、贴纸、包装文字，必须原样写出（如"Lazy girl full glam"），不要翻译或改写。中文画面描述里保留原文，翻译可放在 script 字段。
        6. 画面结果客观描述：写"脸颊呈现珠光质感"而不是"展现出自然的光泽和立体感"；写"手臂上出现四道彩色试色条"而不是"展示了极高的显色度"。
        7. 禁止在 scene_description 中复述 conversion_point 的内容：所有关于"这一段承担什么转化作用""为什么让用户想买"的分析，只能写在 conversion_point 和 visual_tactic 字段。

        错误示例（禁止）：
        "创作者手持一个金色的四色修容高光腮红盘，用化妆刷在盘中打圈蘸取所有颜色。随后，她将刷子直接刷在自己的脸颊上，展示产品'一刷完成'的核心用法，屏幕上配有'懒人全妆'的字幕，旨在通过一个快速动作展示产品的便捷性，建立观众对产品效果的期待。"
        → 问题：塞了品类推断（四色修容高光腮红盘）、主观解读（核心用法）、目的分析（旨在...建立...）、画面文字被翻译（懒人全妆）。

        正确示例：
        "一位金发女士手持一个圆形多色粉盘，盘内分四格，颜色从浅米到深棕不等。她用一支蓬松化妆刷在盘中打圈混合颜色，随后将刷子斜扫在自己右侧脸颊上。画面左下角出现白色手写体字幕'Lazy girl full glam'。刷过的皮肤呈现均匀的暖调珠光。"
        → 特点：人物具体、动作链清晰、产品只描述形态、画面文字原样保留、无目的性分析。
        """

    script_field_rules = """
【script 字段规范】
- 如果有真实口播或销售字幕，保留原语言原文。
- 如果该段没有口播，但画面中有文字贴纸/包装文字/屏幕字幕，且这些文字对理解画面必要，script 写："[画面文字] 原文内容"。
- 如果只有背景音乐歌词或纯画面展示，script 固定写"无有效口播/字幕"。
- 禁止在 script 中写画面动作描述（画面动作只写在 scene_description）。
"""

    # 新增：结构化输出约束 + 决策树 + 反例
    structured_constraints = """
【JSON Schema 与枚举约束 - 严格遵守】
输出必须是 JSON 数组，每个元素为对象，字段约束如下：
- start_time: number（秒）
- end_time: number（秒）
- title: 必须从全局叙事步骤词库选择，严禁自创
- content_tag: 必须与 title 同枚举，贴合该段真实内容
- scene_description: string，≥30 中文字符，写清人物动作、商品状态/款式、镜头关系、该段在爆款叙事中的作用
- script: string，保留该段完整口播/字幕原文；无有效口播时固定写"无有效口播/字幕"，禁止复述画面描述或编造推销话术
- product_category: string，依据关键帧画面判断的真实商品品类，禁止依据音频歌词猜测
- product_classification: 必须从产品分类白名单选择；无法判断输出空字符串""
- evidence_frame: string，例如"F03"
- evidence_timestamp: number
- shot_type: string，如特写/镜前特写/分屏/对比/第一人称/全景
- viral_formula: enum["第一人称视角","开箱 / ASMR","GRWM + 产品","分屏对比","日常 Vlog"]
- formula_subtype: 必须从对应大类小类中选择（见分类体系），禁止创造新小类
- category_reason: string，简洁说明判定依据
- selling_point_angle: enum["专家背书","展示效果","轻松便捷","制造紧迫感","天然安全","价格优势","贩卖生活方式",""]
- selling_point_subtype: 必须从对应角度小类中选择
- selling_point_reason: string，说明解决的是信任/效果/省事/紧迫/安全/省钱/生活方式想象
- golden_3s_hook: enum["提问式","挑战式","秘诀/技巧","震撼数据","争议式",""]，仅开头0-3秒有强钩子时填写，否则留空
- golden_3s_subtype: 对应钩子下的小类，无则留空
- golden_3s_reason: string，仅引用开头0-3秒证据，无则留空
- opening_hook_summary: string，必须输出，总结开头留人机制（即使不命中固定黄金3秒分类）
- opening_hook_evidence: string，必须输出，引用开头关键台词/字幕/画面
- viral_reason_summary: string，必须输出，中文分点总结爆点（至少覆盖2个维度）
- visual_tactic: string，该段视觉手法
- conversion_point: string，具体到"为什么让用户更想买/更信任/更省钱/更理解差异"，禁止写空泛的"促进转化"
"""

    classification_decision_tree = """
【分类决策树 - 严格按优先级执行】
判断 viral_formula 时，按以下顺序匹配，一旦命中即停止；如果同时命中多个，选择贯穿全片最多、承担转化最强的：

1. 分屏对比：画面存在左右/上下分屏、前后对比、有无产品对比、竞品同框、淘汰赛式测试。核心是直观证明差异。
   - 小类选择：
     * 同一商品不同颜色/尺码/姿态的左右分屏 → 产品对比型（不是前后分屏型）
     * 同一面部/同一空间左右涂抹两种方案（如两种防晒）→ 方法对比型
     * 多个产品逐个测试筛选淘汰 → 淘汰赛型
     * 必须有明确双对象/双方案+替代价值表达（cheaper/dupe/alternative/save money/price/per serving/贵价/大牌/竞品/常规方案）→ 平替对决型
     * 同一对象使用前vs使用后、有产品vs无产品 → 前后分屏型

2. 开箱 / ASMR：视频从包裹/包装/袋子开始，持续出现打开、取出、展示、触摸材质、摩擦/撕膜/摆放。
   - 反例：服饰 TikTok Shop haul 若无拆包/包装/拆开/取出证据，创作者已穿在身上或镜前连续试穿多件服装 → 优先 GRWM + 产品 / 教学穿插型（不要仅因"haul"语境判为开箱）
   - 反例：单一品牌开箱中提到 sale/kids size/cheaper → 只影响分镜标签（优惠活动/价格促销），不改变全片主类为分屏对比或价格优势

3. GRWM + 产品：创作者在镜前/浴室/卧室/化妆/护肤/穿搭/整理流程中亲自使用产品。
   - 服饰镜前 POV 试穿：按正面亮相→侧身/背面转身→版型/洗水/剪裁/尺码/购买信息顺序展示单件服装 → 仪式步骤型（不要创造"穿搭展示型"等体系外小类）
   - 护肤/护发/美妆/洗护：出现使用频率、操作步骤（按摩/涂抹/清洗/梳理）、成分说明、使用后体验中至少两类 → 仪式步骤型（即使开头有强情绪钩子或个人困扰，也不要覆盖全片小类为情感叙事型）
   - 浴室/镜前护发洗护流程，即使字幕写 POV → 仪式步骤型（不要因 POV 文案判为第一人称视角，也不要因使用前后效果判为分屏对比）

4. 第一人称视角：手持近景、POV、像观众亲手体验；常见于清洁、工具、个护、组装、功能测试。

5. 日常 Vlog：产品自然放进生活流（晨间、家庭、通勤、运动、旅行、家务）。

【卖点角度决策规则】
selling_point_angle 必须基于全片主说服逻辑选择，通常所有分镜保持一致；只有某段明显切换到另一个购买理由时，才允许该段不同：
- 专家背书：出现从业者/专业人士/资质/机构认证/检测报告/反向批评热门产品建立信任
- 展示效果：实时演示/对照测试/前后时间线/个人蜕变/用户证言/数据证明
- 轻松便捷：免决策/随时随地/零门槛/省时间/省步骤
- 制造紧迫感：库存警告/限时折扣/渠道独占/社证加速
- 天然安全：成分透明/敏感群体安全/安全恐吓/低负担安心
- 价格优势：隐性成本曝光/替代价值/日均成本拆解/平替发现/直接比价/普通折扣价
- 贩卖生活方式：圈层标识/理想自我投射/送礼叙事/场景代入/文化认同/审美升级

注意：只有出现明确双对象/双方案对比，且包含替代价值表达时，formula_subtype 才选"平替对决型"，selling_point_angle 才关联"价格优势/平替发现"。单一品牌开箱中提到 sale/kids size/cheaper 只能作为"优惠活动/价格促销"分镜，不得覆盖全片主类或主卖点角度。

【黄金3秒钩子规则】
仅评估视频开头约 0-3 秒或最早分镜。没有明确命中时，golden_3s_hook/golden_3s_subtype/golden_3s_reason 三个字段全部输出空字符串""，禁止为填字段而强行归类。
- 提问式：痛点提问/好奇提问/比价追问/成本提问/共鸣提问/从众提问/场景驱动型
- 挑战式：悬念验证/潮流参与/极限测试/参与邀请/故事悬念/场景还原
- 秘诀/技巧：避坑技巧/省钱秘笈/权威对抗/圈内信息/捷径承诺/稀缺框架/生活妙招
- 震撼数据：逆认知数据/结果前置/大数锚定/百分比冲击/时间线震撼/对比冲击
- 争议式：立场对抗/价格挑衅/情绪挑衅/槽点揭露/颠覆认知/冲突叙事/禁忌揭秘
"""

    anti_patterns = """
【反例警示 - 以下情况极易误判，必须避免】
1. 不要把服饰 haul（无拆包证据）判为开箱/ASMR。
2. 不要把同一商品不同颜色/尺码左右分屏判为"前后分屏型"（前后分屏必须是同一对象、同一身体部位、同一空间的使用前vs使用后）。
3. 不要把单一品牌开箱中的 sale/kids size/cheaper 判为"平替对决型"（平替必须有双品牌/竞品/贵价vs平价对照）。
4. 不要把 GRWM 开头的夸张情绪宣言覆盖全片小类为"情感叙事型"（情绪只算黄金3秒或分镜标题处理）。
5. 不要把汽车配件功能演示中的规格优势（如 sequential turn signals, IP68 waterproof, durable, portable）标为"功能演示"（镜头重点展示功能如何触发/操作/流程时标"功能演示"；口播明确说出可购买理由或规格优势时优先标"产品卖点"）。
6. 不要把"我更喜欢这个颜色""去年买过另一个款""not with these shoes"标为"产品对比"（无明确同框/分屏/Which is better/价格功能对照时，属于产品卖点或真实体验）。
7. 不要把"太短所以我不穿出门"这类个人试穿限制标为"适用场景"（应标产品卖点或真实体验）。
8. 不要把普通"我来告诉你这个 sale"算为"省钱秘笈"（必须有隐藏路径/避坑经验/购买技巧/折扣入口/反常识省钱方法）。
9. 禁止输出"多角度展示、转身展示、结束展示、服装试穿与展示、穿搭展示"等动作描述型或自造类型作为 title/content_tag；这些画面动作只写在 scene_description，分镜类型必须收敛为"情绪营销/优惠活动/产品卖点/真实体验/行动号召"等标准步骤。
"""

    field_conflict_rules = """
【分镜切分与合并规则】
切分优先级（从高到低）：
1. 重大视觉场景切换：拍摄主体变化、镜头景别/机位变化、场景空间变化、新的关键视觉元素进入画面（手持手机展示价格页、文字贴纸、价格标签、分屏对比框）
2. 叙事目的切换：核心转化目的变化（如从开场悬念→优惠机制→产品展示→试穿反馈→行动号召）
3. 时间节奏：单个分镜通常 6-12 秒；视觉/口播语义/转化目的连续时可延长至 15-20 秒；超过 20 秒仍无清晰切点时，再按口播语义或动作节奏切分

强制合并：
- 同一商品同一场景同一转化目的下的连续角度、手部细节、过渡 B-roll
- 服饰单品连续正面/侧面/背面展示、版型/洗水/剪裁/尺码/材质/弹性反馈
- 同一商品不同颜色喜好、厚薄、图案、是否成套讨论

强制切分示例：
- 画面从"严重水垢的淋浴头特写" → 切换为"两个蒸汽清洁器并排摆放"：必须切分
- 画面从"单一产品使用" → 切换为"手持手机展示 TikTok Shop 价格页面"：必须切分
- 画面从"清洁动作特写" → 切换为"商店货架/产品包装盒全景"：必须切分
- 画面中出现承载新转化目的的文字贴纸/价格标签/分屏对比框：必须切分

【分镜边界语义规则】
禁止因"口播叙事完整"或"同一转化目的"而将两个明显不同的视觉画面合并为同一分镜。
禁止机械按字幕时间戳切断台词：不要把一句完整台词、因果句、转折句或从句拆到两个分镜，也不要让上一分镜 script 以未完成的连接语收尾。分镜时间边界可以围绕视觉切点前后微调，优先让每个 script 都是可独立理解的完整语义单元；如果视觉已经明显切换，则新分镜的 script 从下一句完整语义开始。

【字段冲突处理 - content_tag 优先级】
- 该段主要在讲便宜购买方法/优惠/折扣/deal/sale/coupon/price/save/link/shop/cart/购买路径/下单引导 → 优先标"优惠活动"或"价格促销"
- 出现"X vs Y"/"Which is better"/竞品并列/两个产品同框比较/胜负结果/winner/价格功能对照 → 优先标"产品对比"
- 多个购买理由强弱比较 → "卖点对比"
- 清洁/使用结果差异（使用前vs使用后） → "效果对比"
- 结尾出现 recommend/choose/go for/get yours/order/buy/入手/选择/推荐某品牌或产品，尤其同时出现 cheap/price/link/shop/购买路径 → 必须标"行动号召"（不要只标"产品功效"）
- 汽车配件：镜头重点展示某个功能如何触发、如何操作、流程如何发生 → "功能演示"；口播/字幕明确说出一个可购买理由或规格优势（sequential turn signals, IP68 waterproof, welcome sequence, durable, portable, fast）→ 优先标"产品卖点"
"""

    return f"""
【角色与输出格式】
你是专业跨境短视频爆款模式分析师。严格输出 JSON 数组，不要任何多余解释、markdown 代码块或总结文字。

{structured_constraints}

{classification_decision_tree}

{PATTERN_TAXONOMY}

{MARKETING_TACTIC_TAXONOMY}

{anti_patterns}

{field_conflict_rules}

{scene_description_rules}

产品分类白名单：
只能从以下固定类目中选择 product_classification；如果无法依据画面或口播判断，输出空字符串，不要创造新类目。
{", ".join(PRODUCT_CLASSIFICATION_OPTIONS)}

{granularity_note}

{visual_note}

字幕内容：
{transcript}
"""


SCRIPT_COPY_PRODUCT_FIELDS = [
    "product_name",
    "product_category",
    "target_audience",
    "selling_points",
    "usage_scene",
    "price_offer",
    "brand_tone",
    "duration_seconds",
    "extra_requirements",
]


SCRIPT_COPY_PRODUCT_FIELD_LABELS = {
    "product_name": "产品名称",
    "product_category": "产品品类",
    "target_audience": "目标用户",
    "selling_points": "核心卖点",
    "usage_scene": "使用场景",
    "price_offer": "价格/优惠",
    "brand_tone": "表达语气",
    "duration_seconds": "目标时长",
    "extra_requirements": "补充要求",
}


def normalize_script_copy_product_input(product_input):
    product_input = product_input or {}
    normalized = {}
    for key in SCRIPT_COPY_PRODUCT_FIELDS:
        value = str(product_input.get(key, "") or "").strip()
        if value:
            normalized[key] = value
    return normalized


def _source_formula(record):
    first_item = next((item for item in record.get("data", []) if isinstance(item, dict)), {})
    return record.get("formula") or first_item.get("viral_formula") or "自动识别模式"


def _source_subtype(record):
    first_item = next((item for item in record.get("data", []) if isinstance(item, dict)), {})
    return record.get("subtype") or first_item.get("formula_subtype") or "自动识别小类"


def _source_category_reason(record):
    first_item = next((item for item in record.get("data", []) if isinstance(item, dict)), {})
    return record.get("category_reason") or first_item.get("category_reason") or ""


def get_record_with_version(record, model=None):
    if not record or not model:
        return record
    for version in record.get("versions", []):
        if version.get("model") == model:
            return {
                **record,
                "model": version.get("model") or record.get("model"),
                "formula": version.get("formula") or record.get("formula", ""),
                "subtype": version.get("subtype") or record.get("subtype", ""),
                "category_reason": version.get("category_reason") or record.get("category_reason", ""),
                "product_classification": version.get("product_classification") or record.get("product_classification", ""),
                "data": version.get("data") or [],
                "shot_count": version.get("shot_count", 0),
            }
    return record


def first_golden_3s_item(record):
    for item in record.get("data", []):
        if not isinstance(item, dict):
            continue
        if item.get("golden_3s_hook") or item.get("golden_3s_subtype") or item.get("golden_3s_reason"):
            return item
    return {}


def first_source_item(record):
    for item in record.get("data", []):
        if isinstance(item, dict):
            return item
    return {}


def build_opening_hook_brief(record):
    first_item = first_source_item(record)
    if not first_item:
        return "源视频没有可用分镜；新脚本仍需自行设计前 0-3 秒具体开头钩子。"
    parts = [
        f"首段时间: {first_item.get('start_time', '')}-{first_item.get('end_time', '')}s",
        f"首段结构: {first_item.get('title') or first_item.get('content_tag') or '未标注'}",
        f"首段画面: {first_item.get('scene_description', '')}",
        f"首段台词/字幕: {first_item.get('script', '')}",
        f"开头爆点总结: {first_item.get('opening_hook_summary', '')}",
        f"开头证据: {first_item.get('opening_hook_evidence', '')}",
        f"爆款原因总结: {first_item.get('viral_reason_summary', '')}",
    ]
    return "\n".join(part for part in parts if not part.endswith(": "))


def build_golden_3s_recreation_instruction(item):
    hook = str(item.get("golden_3s_hook", "") or "").strip()
    subtype = str(item.get("golden_3s_subtype", "") or "").strip()
    reason = str(item.get("golden_3s_reason", "") or "").strip()
    opening_script = str(item.get("script", "") or "").strip()
    opening_scene = str(item.get("scene_description", "") or "").strip()
    if not hook and not subtype and not reason:
        return (
            "源视频没有明确命中固定黄金3秒分类；但新脚本仍必须从第一分镜提炼开头留人机制，"
            "用用户产品真实成立的痛点、冲突、价格锚点、结果证据或场景代入设计前 0-3 秒。"
        )

    return (
        f"源视频黄金3秒命中：{hook}{(' / ' + subtype) if subtype else ''}。\n"
        f"命中依据：{reason or opening_scene or opening_script}\n"
        "复刻方法：抽象出源视频前 3 秒的注意力机制，例如信息差、冲突、问题、测试、结果前置或身份代入；"
        "再把这个机制迁移到用户产品真实可证明的卖点上。\n"
        "新脚本前 3 秒必须明确写出画面动作、屏幕字幕/口播、产品出现方式和观众继续看的理由，"
        "但不要套用固定句式或把源视频的商品、价格、品牌、承诺照搬过来。"
    )


def summarize_source_shots(record):
    lines = []
    for index, item in enumerate(record.get("data", []), start=1):
        if not isinstance(item, dict):
            continue
        lines.append(
            "\n".join([
                f"分镜 {index}: {item.get('start_time', '')}-{item.get('end_time', '')}s",
                f"- 叙事角色: {item.get('title') or item.get('content_tag') or '未标注'}",
                f"- 画面逻辑: {item.get('scene_description', '')}",
                f"- 原脚本/字幕: {item.get('script', '')}",
                f"- 视觉手法: {item.get('visual_tactic', '')}",
                f"- 转化作用: {item.get('conversion_point', '')}",
                f"- 开头爆点: {item.get('opening_hook_summary', '')}" if index == 1 else "",
                f"- 爆点证据: {item.get('opening_hook_evidence', '')}" if index == 1 else "",
            ])
        )
    return "\n\n".join(lines) or "源视频未生成有效分镜。"
import re

# 定义禁止出现在 scene_description 中的目的性前缀/句式
SCENE_DESCRIPTION_PURPOSE_PATTERNS = [
    r"旨在.+?。",
    r"为了.+?。",
    r"以.*?方式，.*?。",
    r"建立观众对.+?的期待。?",
    r"强化其.+?的卖点。?",
    r"展示产品.+?的核心用法。?",
    r"证明.+?。",
    r"突出.+?的优势。?",
    r"通过.*?，.*?。",
    r"让观众.*?。",
]

# 定义需要提醒模型保留原文的画面文字常见误译
COMMON_SCREEN_TEXT_MISTRANSLATIONS = {
    "懒人全妆": "Lazy girl full glam",
    # 后续可扩展
}

def clean_scene_description(item: dict) -> dict:
    """
    轻量清洗 scene_description，只删目的性分析句，不补充内容。
    如果检测到画面文字被翻译，尝试还原（仅对已知高频误译）。
    """
    desc = str(item.get("scene_description", ""))
    original_desc = desc
    
    # 1. 删除明显的目的性分析句
    for pattern in SCENE_DESCRIPTION_PURPOSE_PATTERNS:
        desc = re.sub(pattern, "", desc)
    
    # 2. 如果检测到已知误译，且 script 里没有原文，尝试在 scene_description 中还原
    # 注意：这里只是兜底，主要靠 Prompt 约束
    for wrong, correct in COMMON_SCREEN_TEXT_MISTRANSLATIONS.items():
        if wrong in desc and correct.lower() not in desc.lower():
            # 如果 script 里有原文，不处理；如果 script 也没有，尝试还原
            script_text = str(item.get("script", ""))
            if correct.lower() not in script_text.lower():
                desc = desc.replace(wrong, correct)
    
    # 3. 清理多余空格和句号
    desc = re.sub(r"\s+", " ", desc).strip()
    desc = re.sub(r"。+", "。", desc)
    
    if desc != original_desc:
        item["scene_description"] = desc
        item["_scene_description_cleaned"] = True  # 标记被清洗过，便于后续审计
    
    return item

def detect_source_script_language(record):
    scripts = []
    placeholders = {"无有效口播/字幕", "该段无有效口播/字幕"}
    for item in record.get("data", []) or []:
        if not isinstance(item, dict):
            continue
        script = str(item.get("script", "") or "").strip()
        if not script or script in placeholders:
            continue
        if script.startswith("画面/字幕摘要") or script.startswith("画面摘要"):
            continue
        scripts.append(script)
    text = "\n".join(scripts)
    if not text:
        return "源脚本原语言"

    chinese_count = len(re.findall(r"[\u4e00-\u9fff]", text))
    latin_count = len(re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]", text))
    spanish_signals = len(re.findall(r"[áéíóúüñ¿¡ÁÉÍÓÚÜÑ]", text))
    lower_text = text.lower()
    spanish_words = len(re.findall(r"\b(que|para|con|sin|este|esta|como|porque|gracias|hola|ahora|solo|más)\b", lower_text))

    if chinese_count >= max(3, latin_count):
        return "中文"
    if spanish_signals or spanish_words >= 2:
        return "西语"
    if latin_count:
        return "英文"
    return "源脚本原语言"


def build_script_copy_prompt(source_record, product_input):
    product_input = normalize_script_copy_product_input(product_input)
    product_lines = [
        f"- {SCRIPT_COPY_PRODUCT_FIELD_LABELS[key]}: {value}"
        for key, value in product_input.items()
    ]
    first_item = next((item for item in source_record.get("data", []) if isinstance(item, dict)), {})
    golden_instruction = build_golden_3s_recreation_instruction(first_golden_3s_item(source_record))
    target_duration = product_input.get("duration_seconds", "")
    duration_rule = (
        f"新脚本总时长控制在约 {target_duration} 秒。"
        if target_duration else
        "新脚本总时长参考源视频分镜节奏，可按产品复杂度微调。"
    )
    source_script_language = detect_source_script_language(source_record)

    return f"""
你是短视频爆款脚本复刻专家。你的任务是基于源视频拆解结果，为用户的新产品生成一版可拍摄的新脚本。

核心原则：
- 复刻的是源视频的“转化骨架”，不是只复刻分镜标签。每个分镜都要先判断源视频这一段在完成什么转化任务：制造痛点/建立价格锚点/展示效果证据/补强信任/降低决策成本/引导购买。
- 新脚本必须逐分镜迁移这个转化任务，并换成用户产品真实成立的表达；不能只写“用户痛点、产品功效、产品卖点、行动号召”这种泛化结构。
- 只复制结构、节奏、钩子、证据形式和购买心理，不能照抄源视频原台词、品牌、商品、价格、数字或具体承诺。
- 新脚本必须围绕用户产品真实信息展开；用户没提供的功效、价格、认证、数量、优惠不要编造成事实，可以写成“画面展示/字幕强调/需要补充信息”。
- 如果源视频命中黄金3秒，必须复刻它的注意力机制，例如价格冲击、尴尬痛点、结果前置、对比悬念或信息差，并在第一分镜写清楚前 0-3 秒如何拍、如何说、为什么能留住观众。
- 即使源视频没有 golden_3s 分类字段，也必须从第一分镜提炼开头留人机制，并在新脚本第一分镜做出一个具体、可拍、能留人的前 0-3 秒钩子。
- 避免模板化占位词，不要在成片脚本里出现“目标用户”“目标场景”“核心卖点”“产品进入使用场景”等后台提示词；商品短名必须是自然品类名，不要把单个卖点当商品名反复复读。


源视频爆款结构：
- 爆款公式: {_source_formula(source_record)} / {_source_subtype(source_record)}
- 分类原因: {_source_category_reason(source_record)}
- 主卖点角度: {first_item.get("selling_point_angle", "")} / {first_item.get("selling_point_subtype", "")}
- 卖点依据: {first_item.get("selling_point_reason", "")}

黄金3秒复刻：
{golden_instruction}

开头爆点证据：
{build_opening_hook_brief(source_record)}

用户产品信息：
{chr(10).join(product_lines) if product_lines else "- 用户尚未填写详细产品信息，请根据上传图片中能看见的内容保守生成，并提示需要补充的拍摄信息。"}

源视频分镜模板：
{summarize_source_shots(source_record)}

生成规则：
1. {duration_rule}
2. 分镜数量尽量与源视频一致；每个分镜都要说明复刻了源视频的哪种叙事作用。
3. 默认使用源脚本语言：{source_script_language}。voiceover、screen_text、new_script 默认都用源脚本语言生成；除非用户产品信息里明确要求另一种语言，否则不要自动翻译成中文。
4. 每个分镜必须包含：时长、画面动作、口播/字幕、新脚本、拍摄要点、复刻逻辑、转化作用。
   - visual_plan 只写画面怎么拍，不要夹入口播或字幕。
   - voiceover 写可直接念出来的口播台词；如果成片没有真人口播，可以写空字符串。
   - screen_text 写可直接贴在画面上的字幕/贴纸文案；没有真人口播时也必须给出 screen_text。
   - voiceover 和 screen_text 不允许同时为空；至少要有一类可直接用于成片的文案。
   - new_script 不能只写画面描述，必须把画面动作和口播/字幕组合成完整成片脚本。
5. 第一分镜必须输出 hook_implementation，不允许为空；必须具体写清楚前 0-3 秒画面、字幕/口播、为什么能抓住观众、用户产品如何承接。
6. shots 必须是非空数组，且必须逐条输出可拍摄分镜；只返回 copy_strategy 或总结文字是不合格结果。
7. 不要输出 markdown，不要输出解释性正文，只输出 JSON 对象。

输出格式：
{{
  "copy_strategy": {{
    "source_formula": "{_source_formula(source_record)}",
    "source_subtype": "{_source_subtype(source_record)}",
    "product_short_name": "给用户商品起一个中文短名，后续脚本统一使用这个短名，不要复读商品长标题",
    "script_logic": "一句话说明复刻的脚本逻辑",
    "golden_3s_recreation": "如果有黄金3秒，说明新脚本如何命中；没有则说明自然开场策略",
    "shooting_style": "整体拍摄风格",
    "risk_notes": ["用户还需要补充或拍摄时要注意的点"]
  }},
  "shots": [
    {{
      "shot_index": 1,
      "duration_seconds": 数字,
      "title": "分镜叙事角色",
      "copied_from": "源视频对应分镜的叙事作用",
      "visual_plan": "画面怎么拍",
      "voiceover": "口播文案；没有口播则写空字符串",
      "screen_text": "屏幕字幕/贴纸文案",
      "new_script": "完整可拍的新脚本，必须包含画面动作和口播/字幕，不能只写画面描述",
      "hook_implementation": "仅第一分镜必填：黄金3秒怎么实现；无黄金3秒则写自然开场说明",
      "shooting_notes": "镜头、道具、动作、节奏提示",
      "conversion_point": "这一段如何推动信任、理解、购买或继续观看"
    }}
  ],
  "cta_options": ["可选结尾CTA 1", "可选结尾CTA 2"],
  "missing_info_questions": ["如需要，列出还缺什么信息"]
}}
"""


def build_product_selling_points_prompt(product_input):
    product_input = normalize_script_copy_product_input(product_input)
    product_lines = [
        f"- {SCRIPT_COPY_PRODUCT_FIELD_LABELS[key]}: {value}"
        for key, value in product_input.items()
        if key in {"product_name", "product_category", "target_audience", "selling_points", "usage_scene", "price_offer", "extra_requirements"}
    ]
    return f"""
你是短视频爆款脚本专用的商品卖点提炼助手，兼顾合规保守 + 短视频带货表达。请根据用户输入的商品标题、品类、目标人群、使用场景、补充内容和可选图片，生成适合短视频口播/字幕的精简卖点。

要求：
- 只输出 JSON 对象，不要 markdown，不要多余解释。
- 每个卖点为 2-12 个中文字短语，最多输出 6 条。
- 严格遵守：**不编造医疗功效、不夸大效果、不虚构认证/销量/治愈率**。
- 允许合理做「属性转用户利益」翻译：
  例：可调节 → 适配不同牙型；独立包装 → 干净便携随拿随用。
- 优先提取：品类、适用人群、规格、材质、结构、使用方式、便携性、适配场景、核心直观优势。
- 外语标题先翻译成通顺中文，再提炼短卖点，不要整段照搬标题。
- 禁止直接把完整商品标题当做卖点，不要把完整商品标题原样作为卖点。
- product_classification 必须从固定类目中选择；无法判断输出空字符串。

固定类目：
{", ".join(PRODUCT_CLASSIFICATION_OPTIONS)}

用户商品信息：
{chr(10).join(product_lines) if product_lines else "- 用户未填写文字信息，请只根据图片中能看见的内容保守生成卖点"}

输出格式：
{{
  "product_classification": "固定类目或空字符串",
  "selling_points": ["短卖点1", "短卖点2", "短卖点3"],
  "reason": "一句话说明卖点来源于标题、图片、人群或场景信息"
}}
"""


def normalize_product_selling_points_result(raw_text, product_input, model):
    cleaned = normalize_script_copy_json_text(raw_text)
    try:
        parsed = json.loads(cleaned)
    except (TypeError, json.JSONDecodeError):
        parsed = {}

    if isinstance(parsed, list):
        selling_points = parsed
        parsed = {}
    elif isinstance(parsed, dict):
        selling_points = parsed.get("selling_points") or parsed.get("points") or []
    else:
        selling_points = []

    if isinstance(selling_points, str):
        selling_points = re.split(r"[，,、\n]+", selling_points)
    if not isinstance(selling_points, list):
        selling_points = []

    normalized_points = []
    for point in selling_points:
        text = str(point or "").strip()
        if not text or text in normalized_points:
            continue
        normalized_points.append(text[:24])
        if len(normalized_points) >= 6:
            break

    return {
        "model": model,
        "product_input": normalize_script_copy_product_input(product_input),
        "product_classification": normalize_product_classification(parsed.get("product_classification", "")) if isinstance(parsed, dict) else "",
        "selling_points": normalized_points,
        "reason": str(parsed.get("reason", "") or "").strip() if isinstance(parsed, dict) else "",
    }


def generate_product_selling_points(product_input, model, product_visual_frames=None):
    product_visual_frames = product_visual_frames or []
    prompt = build_product_selling_points_prompt(product_input)
    raw_text = analyze_video(
        "",
        model,
        visual_frames=product_visual_frames,
        prompt=prompt,
    )
    return normalize_product_selling_points_result(raw_text, product_input, model)


def first_non_empty(*values):
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def estimate_source_shot_duration(item, fallback=5):
    start = parse_time_value(item.get("start_time"), 0)
    end = parse_time_value(item.get("end_time"), start + fallback)
    duration = max(1, round(end - start))
    return duration


def split_selling_points(product_input):
    points = []
    for value in [
        product_input.get("selling_points", ""),
        product_input.get("extra_requirements", ""),
        product_input.get("product_category", ""),
    ]:
        for item in re.split(r"[，,、/\n]+", str(value or "")):
            text = item.strip()
            if text and text not in points:
                points.append(text)
    return points


def derive_script_copy_product_short_name(product_input, preferred_name=""):
    preferred_name = str(preferred_name or "").strip()
    if preferred_name:
        return preferred_name[:16]
    product_input = normalize_script_copy_product_input(product_input)
    category = product_input.get("product_category", "")
    points = split_selling_points(product_input)
    title = product_input.get("product_name", "")
    text = f"{title} {' '.join(points)} {category}".lower()

    if category:
        return category[:16]
    if points:
        return points[0][:16]
    words = re.findall(r"[A-Za-z0-9]+", title)
    if words:
        return " ".join(words[:3])
    return title[:16] or "用户产品"


def get_script_copy_point(product_input, index, default_text):
    points = split_selling_points(product_input)
    if not points:
        return default_text
    return points[min(index, len(points) - 1)]


def build_fallback_hook_implementation(source_record, short_name, product_input):
    golden_item = first_golden_3s_item(source_record)
    base_instruction = build_golden_3s_recreation_instruction(golden_item)
    usage_scene = product_input.get("usage_scene") or product_input.get("target_audience") or "目标场景"
    first_point = get_script_copy_point(product_input, 0, "核心卖点")
    return (
        f"{base_instruction}\n"
        f"可拍法：0-1秒给{usage_scene}里的真实使用前状态，字幕提出具体问题；"
        f"1-2秒手拿{short_name}入镜，镜头切到产品细节；"
        f"2-3秒切到产品开始解决问题的动作，字幕强调“{first_point}”，让观众想看后续证明。"
    )


def build_fallback_visual_plan(index, title, short_name, product_input):
    point = get_script_copy_point(product_input, index - 1, "核心卖点")
    plans = [
        f"0-3秒用目标用户的使用前状态开场，手拿{short_name}快速入镜，再切到产品进入使用场景。",
        f"拍{short_name}包装、配件和手部安装/使用步骤，镜头保持近景，让观众看清怎么用。",
        f"拍使用前后对比：先给未使用状态，再切使用后状态，字幕标出“{point}”。",
        f"拍产品细节和可信证据：材质、尺寸、操作、适用条件或限制，再接购买提示。",
        f"收尾拍真人看镜头展示最终效果，旁边放产品和优惠信息，手指向购物入口。",
    ]
    if "痛点" in title or "开场" in title:
        return plans[0]
    if "功效" in title or "效果" in title:
        return plans[2]
    if "卖点" in title or "安全" in title:
        return plans[3]
    if "行动" in title or "号召" in title or "cta" in title.lower():
        return plans[4]
    return plans[min(index - 1, len(plans) - 1)]


def build_fallback_voiceover(index, title, short_name, product_input):
    usage_scene = product_input.get("usage_scene") or product_input.get("target_audience") or "目标场景"
    point = get_script_copy_point(product_input, index - 1, "核心卖点")
    price_offer = product_input.get("price_offer") or "现在的优惠"
    if index == 1 or "痛点" in title or "开场" in title:
        return f"{usage_scene}里遇到这个问题，先看这个{short_name}，重点是{point}。"
    if "功效" in title or "效果" in title:
        return f"直接看前后变化，{short_name}要让人一眼看到{point}。"
    if "卖点" in title or "安全" in title:
        return f"这段拍清楚{point}，让观众知道它为什么适合日常使用。"
    if "行动" in title or "号召" in title or "cta" in title.lower():
        return f"想试的话先看{price_offer}，按页面提示选择适合自己的规格。"
    return f"这一段只讲一个点：{point}，用画面证明，不用夸张承诺。"


def replace_product_long_title(text, product_input, preferred_name=""):
    result = str(text or "").strip()
    if not result:
        return ""
    product_input = normalize_script_copy_product_input(product_input)
    short_name = derive_script_copy_product_short_name(product_input, preferred_name)
    product_name = product_input.get("product_name", "").strip()
    if product_name and len(product_name) > 24:
        result = result.replace(product_name, short_name)
    words = re.findall(r"[A-Za-z][A-Za-z0-9-]*", product_name)
    if len(words) >= 5:
        long_prefix = r"\s+".join(re.escape(word) for word in words[:8])
        result = re.sub(long_prefix + r"(?:[\s,.-]+[A-Za-z][A-Za-z0-9-]*)*", short_name, result)
    return re.sub(r"\s{2,}", " ", result).strip()


def compact_hook_implementation(text, source_record, product_input, preferred_name=""):
    short_name = derive_script_copy_product_short_name(product_input, preferred_name)
    cleaned = replace_product_long_title(text, product_input, preferred_name)
    if all(marker in cleaned for marker in ["0-1秒", "1-2秒", "2-3秒"]):
        start = cleaned.find("0-1秒")
        return cleaned[start:].strip()[:220]
    return build_fallback_hook_implementation(source_record, short_name, product_input).split("可拍法：", 1)[-1].strip()


def compact_conversion_point(text, product_input, index):
    cleaned = str(text or "").strip()
    if cleaned:
        return cleaned[:78]
    point = get_script_copy_point(product_input, index - 1, get_script_copy_point(product_input, 0, "核心卖点"))
    return f"承接该分镜的叙事作用，突出{point}，推动继续观看或购买决策。"


def normalize_script_copy_shots_for_display(shots, source_record, product_input, product_short_name=""):
    normalized = []
    short_name = derive_script_copy_product_short_name(product_input, product_short_name)
    for index, shot in enumerate(shots, start=1):
        if not isinstance(shot, dict):
            continue
        cleaned_shot = dict(shot)
        for key in ["visual_plan", "voiceover", "screen_text", "new_script", "shooting_notes"]:
            cleaned_shot[key] = replace_product_long_title(cleaned_shot.get(key, ""), product_input, short_name)
        if index == 1:
            cleaned_shot["hook_implementation"] = compact_hook_implementation(
                cleaned_shot.get("hook_implementation", ""),
                source_record,
                product_input,
                short_name,
            )
            if not cleaned_shot.get("screen_text"):
                cleaned_shot["screen_text"] = f"{short_name}｜{get_script_copy_point(product_input, 0, '核心卖点')}"
        else:
            cleaned_shot["hook_implementation"] = replace_product_long_title(cleaned_shot.get("hook_implementation", ""), product_input, short_name)
        cleaned_shot["conversion_point"] = compact_conversion_point(
            cleaned_shot.get("conversion_point", ""),
            product_input,
            index,
        )
        normalized.append(cleaned_shot)
    return normalized


def build_script_copy_repair_prompt(source_record, product_input, previous_text):
    product_input = normalize_script_copy_product_input(product_input)
    short_name = derive_script_copy_product_short_name(product_input)
    return f"""
你上一次没有返回可拍摄分镜。请基于同一源视频和商品信息重新输出完整 JSON。

硬性要求：
- 只输出 JSON 对象，不要 markdown。
- shots 必须是非空数组，分镜数量尽量等于源视频分镜数量。
- 商品在脚本中统一称为“{short_name}”，不要反复复制英文长标题。
- 每个分镜必须有差异化画面，不要重复“拍摄实物细节、使用动作或前后变化”这种模板句。
- 每个分镜必须包含 visual_plan、voiceover、screen_text、new_script、shooting_notes、conversion_point。
- 第一分镜 hook_implementation 必须写成 0-1秒、1-2秒、2-3秒的具体拍法。

用户商品信息：
{json.dumps(product_input, ensure_ascii=False)}

源视频分镜模板：
{summarize_source_shots(source_record)}

上一次模型返回：
{str(previous_text or "")[:2000]}

输出格式仍然是：
{{
  "copy_strategy": {{"script_logic": "...", "golden_3s_recreation": "...", "shooting_style": "...", "risk_notes": []}},
  "shots": [],
  "cta_options": [],
  "missing_info_questions": []
}}
"""


def build_fallback_script_copy_shots(source_record, product_input):
    product_input = normalize_script_copy_product_input(product_input)
    product_name = derive_script_copy_product_short_name(product_input)
    selling_points = product_input.get("selling_points") or "核心卖点"
    price_offer = product_input.get("price_offer") or "当前优惠/购买理由"
    source_items = [item for item in source_record.get("data", []) if isinstance(item, dict)]
    if not source_items:
        source_items = [{
            "title": "产品开场",
            "scene_description": "展示产品和核心问题。",
            "conversion_point": "让观众理解产品适合谁、解决什么问题。",
        }]

    shots = []
    for index, item in enumerate(source_items, start=1):
        title = first_non_empty(item.get("title"), item.get("content_tag"), f"分镜 {index}")
        source_scene = first_non_empty(item.get("scene_description"), item.get("script"), "承接源视频对应段落的叙事作用")
        conversion = first_non_empty(
            item.get("conversion_point"),
            "把产品信息转成用户能理解的购买理由。",
        )
        is_first = index == 1
        visual_plan = build_fallback_visual_plan(index, title, product_name, product_input)
        voiceover = build_fallback_voiceover(index, title, product_name, product_input)
        screen_text = (
            f"{product_name}｜{get_script_copy_point(product_input, 0, selling_points)}"
            if is_first else
            first_non_empty(get_script_copy_point(product_input, index - 1, ""), selling_points, product_name)
        )
        shot = {
            "shot_index": index,
            "duration_seconds": estimate_source_shot_duration(item),
            "title": title,
            "copied_from": f"复刻源视频第 {index} 段的叙事作用：{source_scene}",
            "visual_plan": visual_plan,
            "voiceover": voiceover,
            "screen_text": screen_text,
            "new_script": f"画面：{visual_plan} 口播/字幕：{voiceover}",
            "hook_implementation": build_fallback_hook_implementation(source_record, product_name, product_input) if is_first else "",
            "shooting_notes": first_non_empty(
                item.get("visual_tactic"),
                "用近景、手部演示、前后对比或字幕标注把卖点拍具体。",
            ),
            "conversion_point": f"{conversion} 新产品承接为：突出 {selling_points}，并引导用户关注 {price_offer}。",
        }
        shots.append(shot)
    return shots


def normalize_script_copy_result(raw_text, source_record, product_input, model):
    cleaned = normalize_script_copy_json_text(raw_text)
    try:
        parsed = json.loads(cleaned)
    except (TypeError, json.JSONDecodeError):
        parsed = {"copy_strategy": {}, "shots": [], "raw_text": raw_text}

    if isinstance(parsed, list):
        parsed = {"copy_strategy": {}, "shots": parsed}
    if not isinstance(parsed, dict):
        parsed = {"copy_strategy": {}, "shots": [], "raw_text": raw_text}

    copy_strategy = parsed.get("copy_strategy")
    if not isinstance(copy_strategy, dict):
        copy_strategy = {}
    product_short_name = derive_script_copy_product_short_name(
        product_input,
        copy_strategy.get("product_short_name", ""),
    )
    copy_strategy["product_short_name"] = product_short_name
    shots = parsed.get("shots") or parsed.get("data") or parsed.get("items") or []
    if not isinstance(shots, list):
        shots = []
    shots = [shot for shot in shots if isinstance(shot, dict)]
    shots = normalize_script_copy_shots_for_display(shots, source_record, product_input, product_short_name)

    copy_strategy.setdefault("source_formula", _source_formula(source_record))
    copy_strategy.setdefault("source_subtype", _source_subtype(source_record))
    copy_strategy.setdefault("script_logic", "按源视频结构生成可拍摄分镜脚本。")
    copy_strategy.setdefault("golden_3s_recreation", build_golden_3s_recreation_instruction(first_golden_3s_item(source_record)))
    return {
        "source_analysis_id": source_record.get("id", ""),
        "source_filename": source_record.get("filename", ""),
        "source_model": source_record.get("model", ""),
        "source_formula": _source_formula(source_record),
        "source_subtype": _source_subtype(source_record),
        "model": model,
        "product_input": normalize_script_copy_product_input(product_input),
        "copy_strategy": copy_strategy,
        "shots": shots,
        "cta_options": parsed.get("cta_options") if isinstance(parsed.get("cta_options"), list) else [],
        "missing_info_questions": parsed.get("missing_info_questions") if isinstance(parsed.get("missing_info_questions"), list) else [],
        "raw_text": parsed.get("raw_text", ""),
    }


def normalize_script_copy_json_text(text):
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

    object_start = cleaned.find("{")
    object_end = cleaned.rfind("}")
    array_start = cleaned.find("[")
    array_end = cleaned.rfind("]")
    if object_start != -1 and object_end != -1 and (array_start == -1 or object_start < array_start):
        return cleaned[object_start:object_end + 1].strip()
    if array_start != -1 and array_end != -1:
        return cleaned[array_start:array_end + 1].strip()
    return cleaned


def generate_script_copy(source_record, product_input, model, product_visual_frames=None, log_context=None):
    product_visual_frames = product_visual_frames or []
    prompt = build_script_copy_prompt(source_record, product_input)
    if log_context:
        log_script_copy_job(
            log_context,
            "Prompt 构建完成",
            prompt_chars=len(prompt or ""),
            source_shots=len(source_record.get("data", []) or []),
            product_images=len(product_visual_frames),
        )
        print_script_copy_prompt_for_debug(
            log_context,
            model,
            prompt,
            normalize_script_copy_product_input(product_input),
            product_visual_frames,
            phase="初次生成",
        )
    started_at = time.perf_counter()
    if log_context:
        log_script_copy_job(log_context, "开始调用 AI 生成新脚本", model=model)
    raw_text = analyze_video(
        "",
        model,
        visual_frames=product_visual_frames,
        prompt=prompt,
    )
    ai_seconds = time.perf_counter() - started_at
    if log_context:
        log_script_copy_job(
            log_context,
            "AI 返回新脚本",
            elapsed=format_duration(ai_seconds),
            raw_chars=len(raw_text or ""),
        )
    result = normalize_script_copy_result(raw_text, source_record, product_input, model)
    if not result.get("shots"):
        repair_prompt = build_script_copy_repair_prompt(source_record, product_input, raw_text)
        if log_context:
            log_script_copy_job(
                log_context,
                "模型未返回分镜，开始二次修复",
                repair_prompt_chars=len(repair_prompt or ""),
            )
            print_script_copy_prompt_for_debug(
                log_context,
                model,
                repair_prompt,
                normalize_script_copy_product_input(product_input),
                product_visual_frames,
                phase="二次修复",
            )
        repair_started_at = time.perf_counter()
        repair_text = analyze_video(
            "",
            model,
            visual_frames=product_visual_frames,
            prompt=repair_prompt,
        )
        repair_seconds = time.perf_counter() - repair_started_at
        if log_context:
            log_script_copy_job(
                log_context,
                "二次修复返回",
                elapsed=format_duration(repair_seconds),
                raw_chars=len(repair_text or ""),
            )
        repaired_result = normalize_script_copy_result(repair_text, source_record, product_input, model)
        if not repaired_result.get("shots"):
            raise RuntimeError("模型未返回可拍摄分镜，请补充商品信息、换模型或重新生成")
        result = repaired_result
    if log_context:
        log_script_copy_job(
            log_context,
            "结果归一化完成",
            shots=len(result.get("shots", []) or []),
            cta_options=len(result.get("cta_options", []) or []),
        )
    return result


ALLOWED_STORY_STEPS = {
    "故事开场",
    "用户痛点",
    "需求产生",
    "场景设定",
    "产品亮相",
    "产品信息",
    "产品特写",
    "使用说明",
    "功能演示",
    "产品卖点",
    "产品对比",
    "产品差异",
    "卖点对比",
    "痛点解决",
    "产品功效",
    "效果对比",
    "真实体验",
    "使用感受",
    "适用场景",
    "适用人群",
    "情绪营销",
    "价格促销",
    "优惠活动",
    "行动号召",
}


def normalize_story_step_labels(item):
    title = str(item.get("title", "")).strip()
    content_tag = str(item.get("content_tag", "")).strip()

    if content_tag not in ALLOWED_STORY_STEPS:
        content_tag = ""
    if title not in ALLOWED_STORY_STEPS:
        title = content_tag or infer_standard_story_step(item)

    item["title"] = title
    item["content_tag"] = content_tag or title
    return item


def _keyword_hits(text, keywords):
    return [keyword for keyword in keywords if keyword in text]


def _opening_story_text(items):
    candidates = []
    for item in items:
        if not isinstance(item, dict):
            continue
        start = item.get("start_time", 0)
        try:
            start = float(start)
        except (TypeError, ValueError):
            start = 0
        candidates.append((start, item))

    if not candidates:
        return ""

    candidates.sort(key=lambda pair: pair[0])
    opening_items = [item for start, item in candidates if start <= 3]
    if not opening_items:
        opening_items = [candidates[0][1]]

    parts = []
    for item in opening_items:
        parts.extend([
            str(item.get("scene_description", "")),
            str(item.get("script", "")),
            str(item.get("visual_tactic", "")),
        ])
    return " ".join(parts).lower()


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
        ])
    return " ".join(parts).lower()


def _story_item_text(item):
    return " ".join([
        str(item.get("title", "")),
        str(item.get("scene_description", "")),
        str(item.get("script", "")),
        str(item.get("content_tag", "")),
        str(item.get("visual_tactic", "")),
        str(item.get("conversion_point", "")),
    ]).lower()


def _has_alternative_value_in_comparison_context(items, alternative_value_keywords, comparison_keywords):
    for item in items:
        if not isinstance(item, dict):
            continue
        item_text = _story_item_text(item)
        if _keyword_hits(item_text, alternative_value_keywords) and _keyword_hits(item_text, comparison_keywords):
            return True
    return False

def enrich_storyboard_result(result_text, video_path, transcript=None):
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
        
        # 1. 字段默认值填充（模型可能遗漏字段，做最小兜底）
        item.setdefault("title", item.get("narrative_role") or f"分镜 {index + 1}")
        item.setdefault("content_tag", item.get("title", "产品亮相"))
        item.setdefault("viral_formula", item.get("pattern_category") or "")
        item.setdefault("formula_subtype", item.get("pattern_subtype") or "")
        item.setdefault("visual_tactic", "")
        item.setdefault("conversion_point", "")
        item.setdefault("category_reason", "")
        item.setdefault("selling_point_angle", "")
        item.setdefault("selling_point_subtype", "")
        item.setdefault("selling_point_reason", "")
        item.setdefault("golden_3s_hook", "")
        item.setdefault("golden_3s_subtype", "")
        item.setdefault("golden_3s_reason", "")
        item.setdefault("opening_hook_summary", "")
        item.setdefault("opening_hook_evidence", "")
        item.setdefault("viral_reason_summary", "")
        item.setdefault("product_category", "")
        item.setdefault("product_classification", "")
        item.setdefault("evidence_frame", "")
        item.setdefault("evidence_timestamp", item.get("start_time", 0))
        
        # 2. 产品分类白名单校验（强业务约束，必须保留）
        item["product_classification"] = normalize_product_classification(
            item.get("product_classification") or item.get("product_category")
        )
        
        # 3. 叙事步骤白名单校验（轻量兜底：模型输出非法枚举值时，用 title 回退或最小兜底）
        title = str(item.get("title", "")).strip()
        content_tag = str(item.get("content_tag", "")).strip()
        
        if content_tag not in ALLOWED_STORY_STEPS:
            content_tag = ""
        if title not in ALLOWED_STORY_STEPS:
            title = content_tag or "产品亮相"
            
        item["title"] = title
        item["content_tag"] = content_tag or title
        # 新增：清洗 scene_description
        item = clean_scene_description(item)
    parsed = fill_storyboard_scripts_from_transcript(parsed, transcript)
    # 绑定抽帧图片（保留原有逻辑）
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
    if not ENABLE_ASR:
        print("自动 ASR 未启用，使用空字幕继续分析")
        return ""

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
        return ""

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
        return ""

def safe_audio_to_text():
    try:
        return audio_to_text() or ""
    except Exception as e:
        print("ASR 转写失败，使用空字幕继续分析:", e)
        return ""


def analyze_video(transcript, model_type, video_path=None, visual_frames=None, prompt=None, granularity="balanced"):
    if visual_frames is None:
        visual_frames = sample_visual_frames(video_path, granularity=granularity) if video_path else []
    if prompt is None:
        prompt = build_analysis_prompt(transcript, visual_frames, granularity=granularity)

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

    elif model_type in {"gpt-4o", "gptproto-gpt4o"}:
        if not GPTPROTO_API_KEY:
            raise RuntimeError("未配置 GPTPROTO_API_KEY")

        target_model = "gpt-4o" if model_type == "gpt-4o" else GPTPROTO_VISION_MODEL
        try:
            response = post_with_retries(
                f"{BRAIN_BASE_URL.rstrip('/')}/responses",
                headers={
                    "Authorization": GPTPROTO_API_KEY,
                    "Content-Type": "application/json",
                },
                json={
                    "model": target_model,
                    "input": build_gptproto_responses_input(prompt, visual_frames),
                },
                timeout=180,
                retry_label="gptproto responses",
            )
            if response.status_code == 401:
                raise RuntimeError("GPTPROTO_API_KEY 无效，请检查配置")
            if response.status_code == 429:
                raise RuntimeError("gptproto 额度不足或请求受限，请检查配额")
            response.raise_for_status()

            return normalize_json_text(extract_gptproto_responses_text(response.json()))
        except requests.HTTPError as e:
            detail = ""
            try:
                detail = response.text
            except Exception:
                detail = str(e)
            raise RuntimeError(f"gptproto responses 请求失败: {detail}")
        except requests.RequestException as e:
            raise RuntimeError(format_gptproto_network_error("gptproto responses", e))
        except Exception as e:
            print("gptproto responses 分析错误:", e)
            raise RuntimeError(f"gptproto responses 分析失败: {e}")

    elif model_type in {"gptproto", "gemini", "gemini-2.5-pro", "gemini-2.5-flash"}:
        if not GPTPROTO_API_KEY:
            raise RuntimeError("未配置 GPTPROTO_API_KEY")

        target_model = model_type if model_type in {"gemini-2.5-pro", "gemini-2.5-flash"} else BRAIN_MODEL
        messages = build_gptproto_messages(prompt, visual_frames)

        try:
            response = post_with_retries(
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
                retry_label="gptproto chat",
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
            raise RuntimeError(format_gptproto_network_error("gptproto", e))
        except Exception as e:
            print("gptproto 分析错误:", e)
            raise RuntimeError(f"gptproto 分析失败: {e}")

    elif model_type in {"claude-sonnet-4-5-20250929", "claude"}:
        if not GPTPROTO_API_KEY:
            raise RuntimeError("未配置 GPTPROTO_API_KEY")

        target_model = GPTPROTO_CLAUDE_MODEL if model_type == "claude" else model_type
        messages = build_gptproto_claude_messages(prompt, visual_frames)

        try:
            response = post_with_retries(
                f"{BRAIN_BASE_URL.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": GPTPROTO_API_KEY,
                    "Content-Type": "application/json",
                },
                json={
                    "model": target_model,
                    "messages": messages,
                    "max_tokens": 8000,
                    "stream": False,
                },
                timeout=180,
                retry_label="gptproto Claude",
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
            raise RuntimeError(f"gptproto Claude 请求失败: {detail}")
        except requests.RequestException as e:
            raise RuntimeError(format_gptproto_network_error("gptproto Claude", e))
        except Exception as e:
            print("gptproto Claude 分析错误:", e)
            raise RuntimeError(f"gptproto Claude 分析失败: {e}")

    elif model_type in {"tongyi", "qwen-turbo"}:
        if not DASHSCOPE_KEY:
            raise RuntimeError("未配置 DASHSCOPE_KEY")
        res = requests.post(
            "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation",
            headers={"Authorization": f"Bearer {DASHSCOPE_KEY}"},
            json={"model": "qwen-turbo", "input": {"messages": [{"role": "user", "content": prompt}]}}
        )
        return normalize_json_text(res.json()["output"]["text"])

    return "[]"


def format_duration(seconds):
    return f"{seconds:.2f}s"


def log_analysis_job(job_id, message, **fields):
    detail = " ".join(f"{key}={value}" for key, value in fields.items() if value is not None)
    suffix = f" {detail}" if detail else ""
    print(f"[分析任务 {job_id}] {message}{suffix}", flush=True)


def log_script_copy_job(analysis_id, message, **fields):
    detail = " ".join(f"{key}={value}" for key, value in fields.items() if value is not None)
    suffix = f" {detail}" if detail else ""
    print(f"[脚本复刻 {analysis_id}] {message}{suffix}", flush=True)


def print_final_prompt_for_debug(filename, model, prompt, transcript, visual_frames):
    print("\n" + "=" * 88)
    print("视频拆解最终 Prompt")
    print(f"文件名: {filename}")
    print(f"模型: {model}")
    print(f"字幕字符数: {len(transcript or '')}")
    print(f"关键帧数量: {len(visual_frames or [])}")
    print(f"Prompt 字符数: {len(prompt or '')}")
    if visual_frames:
        print("视觉关键帧清单:")
        for frame in visual_frames:
            frame_id = frame.get("id") or "frame"
            timestamp = frame.get("timestamp", 0)
            print(f"{frame_id} @ {timestamp}s")
    print("-" * 88)
    print(prompt)
    print("=" * 88 + "\n")


def print_script_copy_prompt_for_debug(analysis_id, model, prompt, product_input, visual_frames, phase="初次生成"):
    print("\n" + "=" * 88)
    print(f"脚本复刻最终 Prompt（{phase}）")
    print(f"分析ID: {analysis_id}")
    print(f"模型: {model}")
    print(f"产品名称: {product_input.get('product_name', '')}")
    print(f"卖点字符数: {len(product_input.get('selling_points', '') or '')}")
    print(f"产品图片数量: {len(visual_frames or [])}")
    print(f"Prompt 字符数: {len(prompt or '')}")
    if visual_frames:
        print("产品图片清单:")
        for frame in visual_frames:
            frame_id = frame.get("id") or "product-image"
            print(frame_id)
    print("-" * 88)
    print(prompt)
    print("=" * 88 + "\n")


def print_transcript_for_debug(filename, transcript, source):
    print("\n" + "=" * 88)
    print("ASR/字幕内容")
    print(f"文件名: {filename}")
    print(f"来源: {source}")
    print(f"字幕字符数: {len(transcript or '')}")
    print("-" * 88)
    print((transcript or "").strip() or "（空字幕）")
    print("=" * 88 + "\n")


def run_analysis_pipeline(video_path, filename, model, replace_analysis_id=None, job_id=None, transcript_override=None, breakdown_granularity="balanced"):
    total_start = time.perf_counter()
    video_path = str(video_path)
    transcript_override = (transcript_override or "").strip()
    breakdown_granularity = normalize_breakdown_granularity(breakdown_granularity)
    preprocess_start = time.perf_counter()
    check_analysis_cancelled(job_id)
    log_analysis_job(job_id, "开始抽取临时帧", filename=filename, model=model)
    extract_frames(video_path)
    check_analysis_cancelled(job_id)
    if transcript_override:
        has_audio = None
        audio_extract_seconds = 0
        asr_seconds = 0
        transcript = transcript_override
        transcript_source = "手动字幕"
        log_analysis_job(job_id, "使用手动字幕，跳过音频提取和 ASR", transcript_chars=len(transcript))
    else:
        log_analysis_job(job_id, "开始提取音频", filename=filename)
        audio_extract_start = time.perf_counter()
        has_audio = extract_audio(video_path)
        audio_extract_seconds = time.perf_counter() - audio_extract_start
        check_analysis_cancelled(job_id)
        log_analysis_job(job_id, "音频提取完成", has_audio=has_audio)
        log_analysis_job(job_id, "开始 ASR 转写" if has_audio else "视频无音频，跳过 ASR")
        asr_start = time.perf_counter()
        transcript = safe_audio_to_text() if has_audio else ""
        asr_seconds = time.perf_counter() - asr_start
        if not has_audio:
            transcript_source = "无音频"
        elif not ENABLE_ASR:
            transcript_source = "ASR 未启用"
        else:
            transcript_source = "ASR 转写"
        log_analysis_job(job_id, "ASR 转写完成", transcript_chars=len(transcript or ""))
    print_transcript_for_debug(filename, transcript, transcript_source)
    log_analysis_job(job_id, "开始采样视觉关键帧")
    visual_frames = sample_visual_frames(video_path, granularity=breakdown_granularity, transcript=transcript) if video_path else []
    check_analysis_cancelled(job_id)
    log_analysis_job(job_id, "视觉关键帧采样完成", frame_count=len(visual_frames))
    prompt = build_analysis_prompt(transcript, visual_frames, granularity=breakdown_granularity)
    check_analysis_cancelled(job_id)
    log_analysis_job(job_id, "最终 Prompt 构建完成", prompt_chars=len(prompt or ""))
    preprocess_seconds = time.perf_counter() - preprocess_start
    log_analysis_job(
        job_id,
        "音频和字幕耗时统计",
        video_to_audio=format_duration(audio_extract_seconds),
        subtitle_analysis=format_duration(asr_seconds),
        has_audio=has_audio,
    )
    print_final_prompt_for_debug(filename, model, prompt, transcript, visual_frames)

    ai_start = time.perf_counter()
    log_analysis_job(job_id, "开始调用 AI 分析", model=model)
    result = analyze_video(transcript, model, video_path, visual_frames=visual_frames, prompt=prompt, granularity=breakdown_granularity)
    check_analysis_cancelled(job_id)
    ai_seconds = time.perf_counter() - ai_start
    log_analysis_job(job_id, "AI 分析返回", elapsed=format_duration(ai_seconds))

    postprocess_start = time.perf_counter()
    log_analysis_job(job_id, "开始后处理结果")
    result = enrich_storyboard_result(result, video_path, transcript=transcript)
    if not parse_result_items(result):
        raise RuntimeError("AI 未生成有效分镜，请重新拆解或更换模型")
    check_analysis_cancelled(job_id)
    if replace_analysis_id:
        stored = update_analysis_record_result(replace_analysis_id, model, result)
    else:
        stored = persist_analysis(video_path, filename, model, result)
    postprocess_seconds = time.perf_counter() - postprocess_start
    total_seconds = time.perf_counter() - total_start
    log_analysis_job(job_id, "后处理和保存完成", elapsed=format_duration(postprocess_seconds))

    timing = {
        "audio_extract_seconds": audio_extract_seconds,
        "asr_seconds": asr_seconds,
        "preprocess_seconds": preprocess_seconds,
        "ai_seconds": ai_seconds,
        "postprocess_seconds": postprocess_seconds,
        "total_seconds": total_seconds,
    }
    stored["timing"] = timing

    print("\n" + "=" * 88)
    print("视频拆解耗时统计")
    print(f"文件名: {filename}")
    print(f"模型: {model}")
    print(f"预处理/ASR/关键帧耗时: {format_duration(preprocess_seconds)}")
    print(f"AI 分析耗时: {format_duration(ai_seconds)}")
    print(f"后处理/抽分镜图/入库耗时: {format_duration(postprocess_seconds)}")
    print(f"上传后拆解完成总耗时: {format_duration(total_seconds)}")
    print("=" * 88 + "\n")

    return stored

import re

# 定义禁止出现在 scene_description 中的目的性前缀/句式
SCENE_DESCRIPTION_PURPOSE_PATTERNS = [
    r"旨在.+?。",
    r"为了.+?。",
    r"以.*?方式，.*?。",
    r"建立观众对.+?的期待。?",
    r"强化其.+?的卖点。?",
    r"展示产品.+?的核心用法。?",
    r"证明.+?。",
    r"突出.+?的优势。?",
    r"通过.*?，.*?。",
    r"让观众.*?。",
]

# 定义需要提醒模型保留原文的画面文字常见误译
COMMON_SCREEN_TEXT_MISTRANSLATIONS = {
    "懒人全妆": "Lazy girl full glam",
    # 后续可扩展
}

def run_analysis_job(job_id, video_path, filename, model, replace_analysis_id=None, transcript_override=None, breakdown_granularity="balanced"):
    log_analysis_job(
        job_id,
        "开始后台分析",
        filename=filename,
        model=model,
        replace_analysis_id=replace_analysis_id,
    )
    update_analysis_job(job_id, status="processing", message="正在抽帧、转写和分析视频")
    try:
        # The frame/audio helpers use shared temp folders, so serialize pipelines for safety.
        log_analysis_job(job_id, "等待分析流水线锁")
        with analysis_pipeline_lock:
            log_analysis_job(job_id, "获得分析流水线锁")
            check_analysis_cancelled(job_id)
            clean_temp()
            stored = run_analysis_pipeline(
                video_path,
                filename,
                model,
                replace_analysis_id,
                job_id=job_id,
                transcript_override=transcript_override,
                breakdown_granularity=breakdown_granularity,
            )
            clean_temp()

        update_analysis_job(
            job_id,
            status="completed",
            message="分析完成",
            analysis_id=stored["analysis_id"],
            video_url=stored["video_url"],
            model=model,
            timing=stored.get("timing", {}),
            data=stored["data"],
        )
        log_analysis_job(
            job_id,
            "后台分析完成",
            analysis_id=stored["analysis_id"],
            total=format_duration(stored.get("timing", {}).get("total_seconds", 0)),
        )
    except AnalysisCancelled as e:
        log_analysis_job(job_id, "analysis canceled", reason=str(e))
        update_analysis_job(job_id, status="canceled", message=str(e), cancel_requested=True)
    except Exception as e:
        print("后台分析任务异常:", e)
        log_analysis_job(job_id, "后台分析失败", error=str(e))
        update_analysis_job(job_id, status="failed", message=str(e))
    finally:
        try:
            shutil.rmtree(Path(video_path).parent, ignore_errors=True)
        except Exception:
            pass
        # 清理内存中的取消事件
        job_cancel_events.pop(job_id, None)
        log_analysis_job(job_id, "后台任务清理完成")


# 示例：仅对特定高频 bad case 保留最小兜底
def _fallback_vehicle_step(item):
    # 只有模型明显出错时才干预，且必须留下审计日志
    text = str(item.get("script", "")) + str(item.get("scene_description", ""))
    if (item.get("title") == "功能演示" and 
        any(k in text.lower() for k in ["ip68", "waterproof", "sequential turn"])):
        item["title"] = "产品卖点"
        item["content_tag"] = "产品卖点"
        item["_fallback_reason"] = "后端兜底：规格优势词出现在功能演示标签中"

async def _analyze_impl(
    file: UploadFile = None,
    video_url: str = Form(None),
    model: str = Form("gemini-2.5-pro"),
    async_mode: bool = Form(False),
    transcript_override: str = Form(None),
    breakdown_granularity: str = Form("balanced"),
):
    try:
        source_video_url = (video_url or "").strip()
        breakdown_granularity = normalize_breakdown_granularity(breakdown_granularity)
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
                    args=(job_id, video_path, filename, model, None, transcript_override, breakdown_granularity),
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
                    transcript_override=transcript_override,
                    breakdown_granularity=breakdown_granularity,
                )
        elif source_video_url:
            job_id = start_url_analysis_job(source_video_url, model, transcript_override, breakdown_granularity=breakdown_granularity)
            return {
                "code": 0,
                "job_id": job_id,
                "status": "queued",
                "msg": "视频链接任务已提交，后端将先下载视频再分析",
            }
        else:
            return JSONResponse(status_code=400, content={"code": 400, "msg": "请上传视频文件"})

        return {
            "code": 0,
            "data": stored["data"],
            "analysis_id": stored["analysis_id"],
            "video_url": stored["video_url"],
        }
    except VideoDownloadError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        print("分析接口异常:", e)
        raise HTTPException(status_code=500, detail="服务内部异常，请查看后端日志")


def start_url_analysis_job(source_video_url, model, transcript_override=None, breakdown_granularity="balanced"):
    breakdown_granularity = normalize_breakdown_granularity(breakdown_granularity)
    job_id = create_analysis_job(guess_video_filename_from_url(source_video_url), model)
    job_dir = JOB_UPLOAD_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    def download_and_analyze_url_job():
        try:
            log_analysis_job(job_id, "开始下载视频链接", url=source_video_url)
            update_analysis_job(job_id, status="processing", message="正在下载视频链接")
            downloaded_path, downloaded_filename = download_video_from_url(source_video_url, job_dir)
            preview_url = persist_job_preview_video(job_id, downloaded_path, downloaded_filename)
            size_mb = f"{Path(downloaded_path).stat().st_size / 1024 / 1024:.2f}MB"
            log_analysis_job(
                job_id,
                "视频链接下载完成",
                filename=downloaded_filename,
                path=downloaded_path,
                size=size_mb,
                preview_url=preview_url,
            )
            update_analysis_job(
                job_id,
                filename=downloaded_filename,
                video_url=preview_url,
                message="视频下载完成，正在抽帧、转写和分析",
            )
            run_analysis_job(job_id, downloaded_path, downloaded_filename, model, None, transcript_override, breakdown_granularity)
        except VideoDownloadError as e:
            log_analysis_job(job_id, "视频链接下载失败", error=str(e))
            update_analysis_job(job_id, status="failed", message=str(e))
            job_cancel_events.pop(job_id, None)
            shutil.rmtree(job_dir, ignore_errors=True)
        except Exception as e:
            print("视频链接下载任务异常:", e)
            log_analysis_job(job_id, "视频链接下载任务异常", error=str(e))
            update_analysis_job(job_id, status="failed", message=normalize_download_error(e))
            job_cancel_events.pop(job_id, None)
            shutil.rmtree(job_dir, ignore_errors=True)

    thread = threading.Thread(target=download_and_analyze_url_job, daemon=True)
    thread.start()
    return job_id


@app.post("/analyze")
async def analyze(
    file: UploadFile = None,
    video_url: str = Form(None),
    model: str = Form("gemini-2.5-pro"),
    async_mode: bool = Form(False),
    transcript_override: str = Form(None),
    breakdown_granularity: str = Form("balanced"),
):
    return await _analyze_impl(
        file=file,
        video_url=video_url,
        model=model,
        async_mode=async_mode,
        transcript_override=transcript_override,
        breakdown_granularity=breakdown_granularity,
    )


@app.post("/api/analyze")
async def analyze_with_api_prefix(
    file: UploadFile = None,
    video_url: str = Form(None),
    model: str = Form("gemini-2.5-pro"),
    async_mode: bool = Form(False),
    transcript_override: str = Form(None),
    breakdown_granularity: str = Form("balanced"),
):
    return await _analyze_impl(
        file=file,
        video_url=video_url,
        model=model,
        async_mode=async_mode,
        transcript_override=transcript_override,
        breakdown_granularity=breakdown_granularity,
    )


@app.get("/analysis-jobs/{job_id}")
async def analysis_job_detail(job_id: str):
    job = get_analysis_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="分析任务不存在或后端已重启")
    return {"code": 0, "data": job}


@app.get("/api/analysis-jobs/{job_id}")
async def analysis_job_detail_with_api_prefix(job_id: str):
    return await analysis_job_detail(job_id)


@app.get("/analysis-jobs/by-analysis/{analysis_id}")
async def analysis_job_by_analysis(analysis_id: str):
    job = get_analysis_job_by_analysis_id(analysis_id)
    if not job:
        raise HTTPException(status_code=404, detail="分析任务不存在")
    return {"code": 0, "data": job}


@app.get("/api/analysis-jobs/by-analysis/{analysis_id}")
async def analysis_job_by_analysis_with_api_prefix(analysis_id: str):
    return await analysis_job_by_analysis(analysis_id)


@app.post("/analysis-jobs/{job_id}/cancel")
async def cancel_analysis_job_endpoint(job_id: str):
    job = cancel_analysis_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="分析任务不存在或后端已重启")
    return {"code": 0, "data": job}


@app.post("/api/analysis-jobs/{job_id}/cancel")
async def cancel_analysis_job_with_api_prefix(job_id: str):
    return await cancel_analysis_job_endpoint(job_id)


@app.get("/model-options")
async def model_options():
    return {"code": 0, "data": get_available_model_options()}


@app.get("/api/model-options")
async def model_options_with_api_prefix():
    return await model_options()


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


async def _product_selling_points_impl(
    model: str,
    product_name: str = Form(""),
    product_category: str = Form(""),
    target_audience: str = Form(""),
    current_selling_points: str = Form(""),
    usage_scene: str = Form(""),
    price_offer: str = Form(""),
    extra_requirements: str = Form(""),
    product_images: List[UploadFile] = File(None),
):
    target_model = model or "gpt-4o"
    product_input = normalize_script_copy_product_input({
        "product_name": product_name,
        "product_category": product_category,
        "target_audience": target_audience,
        "selling_points": current_selling_points,
        "usage_scene": usage_scene,
        "price_offer": price_offer,
        "extra_requirements": extra_requirements,
    })
    if not product_input and not product_images:
        raise HTTPException(status_code=400, detail="请先输入商品信息或上传产品图片")

    visual_frames = []
    for index, upload_file in enumerate(product_images or [], start=1):
        if not upload_file.content_type or not upload_file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="产品图片只能上传图片文件")
        frame = upload_file_to_data_url(upload_file)
        if frame:
            frame["id"] = f"P{index:02d}"
            visual_frames.append(frame)

    try:
        result = await asyncio.to_thread(generate_product_selling_points, product_input, target_model, visual_frames)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        print("商品卖点生成接口异常:", e)
        raise HTTPException(status_code=500, detail="商品卖点生成失败，请查看后端日志")

    return {"code": 0, "data": result}


@app.post("/product-selling-points")
async def product_selling_points(
    model: str = Form("gpt-4o"),
    product_name: str = Form(""),
    product_category: str = Form(""),
    target_audience: str = Form(""),
    current_selling_points: str = Form(""),
    usage_scene: str = Form(""),
    price_offer: str = Form(""),
    extra_requirements: str = Form(""),
    product_images: List[UploadFile] = File(None),
):
    return await _product_selling_points_impl(
        model=model,
        product_name=product_name,
        product_category=product_category,
        target_audience=target_audience,
        current_selling_points=current_selling_points,
        usage_scene=usage_scene,
        price_offer=price_offer,
        extra_requirements=extra_requirements,
        product_images=product_images,
    )


@app.post("/api/product-selling-points")
async def product_selling_points_with_api_prefix(
    model: str = Form("gpt-4o"),
    product_name: str = Form(""),
    product_category: str = Form(""),
    target_audience: str = Form(""),
    current_selling_points: str = Form(""),
    usage_scene: str = Form(""),
    price_offer: str = Form(""),
    extra_requirements: str = Form(""),
    product_images: List[UploadFile] = File(None),
):
    return await _product_selling_points_impl(
        model=model,
        product_name=product_name,
        product_category=product_category,
        target_audience=target_audience,
        current_selling_points=current_selling_points,
        usage_scene=usage_scene,
        price_offer=price_offer,
        extra_requirements=extra_requirements,
        product_images=product_images,
    )


async def _script_copy_impl(
    analysis_id: str,
    model: str,
    source_model: str = None,
    product_name: str = "",
    product_category: str = "",
    target_audience: str = "",
    selling_points: str = "",
    usage_scene: str = "",
    price_offer: str = "",
    brand_tone: str = "",
    duration_seconds: str = "",
    extra_requirements: str = "",
    product_images: List[UploadFile] = None,
):
    log_script_copy_job(analysis_id, "收到脚本复刻请求", model=model, source_model=source_model or "")
    record = fetch_analysis_detail(analysis_id)
    if not record:
        log_script_copy_job(analysis_id, "源分析不存在")
        raise HTTPException(status_code=404, detail="分析记录不存在")
    source_record = get_record_with_version(record, source_model)
    target_model = model or record.get("model") or "gemini-2.5-pro"
    if not target_model:
        raise HTTPException(status_code=400, detail="请选择脚本生成模型")
    log_script_copy_job(
        analysis_id,
        "源分析读取完成",
        filename=source_record.get("filename", ""),
        source_model=source_record.get("model", ""),
        source_shots=len(source_record.get("data", []) or []),
        formula=_source_formula(source_record),
        subtype=_source_subtype(source_record),
    )

    product_input = normalize_script_copy_product_input({
        "product_name": product_name,
        "product_category": product_category,
        "target_audience": target_audience,
        "selling_points": selling_points,
        "usage_scene": usage_scene,
        "price_offer": price_offer,
        "brand_tone": brand_tone,
        "duration_seconds": duration_seconds,
        "extra_requirements": extra_requirements,
    })
    if not product_input.get("product_name") and not product_input.get("selling_points") and not product_images:
        log_script_copy_job(analysis_id, "产品信息不足，拒绝生成")
        raise HTTPException(status_code=400, detail="请至少填写产品名称、核心卖点，或上传产品图片")
    log_script_copy_job(
        analysis_id,
        "产品信息准备完成",
        product_name=product_input.get("product_name", ""),
        product_category=product_input.get("product_category", ""),
        selling_points_chars=len(product_input.get("selling_points", "")),
    )

    visual_frames = []
    for index, upload_file in enumerate(product_images or [], start=1):
        if not upload_file.content_type or not upload_file.content_type.startswith("image/"):
            log_script_copy_job(analysis_id, "产品图片类型错误", content_type=upload_file.content_type)
            raise HTTPException(status_code=400, detail="产品图片只能上传图片文件")
        frame = upload_file_to_data_url(upload_file)
        if frame:
            frame["id"] = f"P{index:02d}"
            visual_frames.append(frame)
    log_script_copy_job(analysis_id, "产品图片处理完成", product_images=len(visual_frames))

    try:
        result = await asyncio.to_thread(
            generate_script_copy,
            source_record,
            product_input,
            target_model,
            visual_frames,
            log_context=analysis_id,
        )
    except RuntimeError as e:
        log_script_copy_job(analysis_id, "脚本复刻失败", error=e)
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        log_script_copy_job(analysis_id, "脚本复刻接口异常", error=e)
        raise HTTPException(status_code=500, detail="脚本复刻生成失败，请查看后端日志")

    log_script_copy_job(analysis_id, "脚本复刻完成", shots=len(result.get("shots", []) or []))
    return {"code": 0, "data": result}


@app.post("/analyses/{analysis_id}/script-copy")
async def script_copy(
    analysis_id: str,
    model: str = Form("gpt-4o"),
    source_model: str = Form(None),
    product_name: str = Form(""),
    product_category: str = Form(""),
    target_audience: str = Form(""),
    selling_points: str = Form(""),
    usage_scene: str = Form(""),
    price_offer: str = Form(""),
    brand_tone: str = Form(""),
    duration_seconds: str = Form(""),
    extra_requirements: str = Form(""),
    product_images: List[UploadFile] = File(None),
):
    return await _script_copy_impl(
        analysis_id=analysis_id,
        model=model,
        source_model=source_model,
        product_name=product_name,
        product_category=product_category,
        target_audience=target_audience,
        selling_points=selling_points,
        usage_scene=usage_scene,
        price_offer=price_offer,
        brand_tone=brand_tone,
        duration_seconds=duration_seconds,
        extra_requirements=extra_requirements,
        product_images=product_images,
    )


@app.post("/api/analyses/{analysis_id}/script-copy")
async def script_copy_with_api_prefix(
    analysis_id: str,
    model: str = Form("gpt-4o"),
    source_model: str = Form(None),
    product_name: str = Form(""),
    product_category: str = Form(""),
    target_audience: str = Form(""),
    selling_points: str = Form(""),
    usage_scene: str = Form(""),
    price_offer: str = Form(""),
    brand_tone: str = Form(""),
    duration_seconds: str = Form(""),
    extra_requirements: str = Form(""),
    product_images: List[UploadFile] = File(None),
):
    return await _script_copy_impl(
        analysis_id=analysis_id,
        model=model,
        source_model=source_model,
        product_name=product_name,
        product_category=product_category,
        target_audience=target_audience,
        selling_points=selling_points,
        usage_scene=usage_scene,
        price_offer=price_offer,
        brand_tone=brand_tone,
        duration_seconds=duration_seconds,
        extra_requirements=extra_requirements,
        product_images=product_images,
    )


def start_reanalysis_background_job(analysis_id, model=None, transcript_override=None, breakdown_granularity="balanced"):
    breakdown_granularity = normalize_breakdown_granularity(breakdown_granularity)
    prepared = prepare_reanalysis_job(analysis_id, model=model)
    thread = threading.Thread(
        target=run_analysis_job,
        args=(
            prepared["job_id"],
            prepared["video_path"],
            prepared["filename"],
            prepared["model"],
            prepared["replace_analysis_id"],
            transcript_override,
            breakdown_granularity,
        ),
        daemon=True,
    )
    thread.start()
    return prepared


@app.post("/analyses/{analysis_id}/reanalyze")
async def reanalyze(
    analysis_id: str,
    model: str = Form(None),
    transcript_override: str = Form(None),
    breakdown_granularity: str = Form("balanced"),
):
    try:
        prepared = start_reanalysis_background_job(
            analysis_id,
            model=model,
            transcript_override=transcript_override,
            breakdown_granularity=breakdown_granularity,
        )
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
async def reanalyze_with_api_prefix(
    analysis_id: str,
    model: str = Form(None),
    transcript_override: str = Form(None),
    breakdown_granularity: str = Form("balanced"),
):
    return await reanalyze(
        analysis_id,
        model=model,
        transcript_override=transcript_override,
        breakdown_granularity=breakdown_granularity,
    )


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
    reload_enabled = os.getenv("RELOAD", "").strip().lower() in {"1", "true", "yes", "on"}
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=port,
        reload=reload_enabled,
        reload_dirs=[str(Path(__file__).parent)] if reload_enabled else None,
    )
