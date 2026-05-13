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

    array_start = cleaned.find("[")
    array_end = cleaned.rfind("]")
    if array_start != -1 and array_end != -1 and array_start < array_end:
        return cleaned[array_start:array_end + 1].strip()

    object_start = cleaned.find("{")
    object_end = cleaned.rfind("}")
    if object_start != -1 and object_end != -1 and object_start < object_end:
        return cleaned[object_start:object_end + 1].strip()

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
    visual_note = """
你还会收到按时间顺序排列的视频关键帧图片，每张图都有编号和时间点，例如 F01 1.2s。
分类、商品品类、场景和分镜必须优先依据关键帧画面证据；字幕或音频可能只是背景音乐歌词，不能把无关歌词当成商品说明。
如果画面显示服装试穿、穿搭展示、换装、转身展示版型，请识别为服饰/穿搭相关内容，不要写成护肤品、清洁用品或其他画面中不存在的品类。
每个分镜必须绑定一个 evidence_frame 和 evidence_timestamp，描述只能来自该分镜证据帧附近的画面，不要把其他关键帧里的颜色、款式、商品串到当前分镜。
script 字段只写该时间段真实口播或真实字幕原文；如果只有画面展示、背景音乐歌词或无关音频，script 写“无有效口播/字幕”，不要把画面描述改写成脚本，也不要编造创作者说过的推销话术。
服装试穿、开箱 haul 类视频请优先按“叙事阶段/核心转化目的”拆分，而不是按每一句口播或每个小动作拆分；同一商品的不同尺码讨论、颜色展示、多个角度展示、连续试穿反馈，除非转化目的明显变化，否则应合并为一个分镜。
但重大视觉场景切换（如从单人试穿切换到两个产品同框对比、从清洁特写切换到手持手机展示价格页面、从室内场景切换到室外场景）优先于叙事目的合并，应拆分为独立分镜；同一商品、同一场景、同一转化目的下的连续角度展示或轻微机位变化可以合并。
""" if visual_frames else """
你只会收到音频转写，因此如果字幕内容像背景音乐歌词、缺少商品信息，请在分类和分镜中保持保守，不要编造画面里不存在的产品。
"""

    return f"""
你是专业跨境短视频爆款模式分析师，严格输出JSON数组，不要任何多余解释。

你的任务不是固定套用某一种模式，而是先判断视频属于哪一个大类与小类，再按该类型的高转化叙事链路拆分分镜。

{visual_note}

{granularity_note}

{PATTERN_TAXONOMY}

{MARKETING_TACTIC_TAXONOMY}

产品分类白名单：
只能从以下固定类目中选择 product_classification；如果无法依据画面或口播判断，输出空字符串，不要创造新类目。
{", ".join(PRODUCT_CLASSIFICATION_OPTIONS)}

分类判断规则：
1. 先判断视频主导表达方式，而不是单句台词。优先看：产品如何出场、是否真人亲测、是否开箱、是否分屏/前后对比、是否生活流叙事、是否第一人称沉浸演示。
2. 如果同时命中多个类型，选择贯穿全片最多、承担转化最强的那个作为 viral_formula。
3. formula_subtype 必须从该大类的小类中选择，不要创造新小类。
4. 小类只用于判断视频形态，不代表固定步骤顺序；不要为了套小类而强行补不存在的段落。
5. 分镜步骤从“全局叙事步骤词库”里选择，按视频真实出现顺序标注；一个视频可以只出现其中一部分步骤，也可以重复出现某类步骤。
6. 分镜切分优先级（从高到低）：
   第一优先：重大视觉场景切换。当画面出现以下会改变主体、场景或转化目的的变化时，应切分为新分镜；同一商品同一场景里的连续角度、手部细节、表情或过渡 B-roll 可以合并：
   - 拍摄主体变化（如从"产品A特写"切换到"产品A+B同框"）
   - 镜头景别/机位变化（如从特写切换到全景、从第一人称切换到桌面平拍）
   - 场景空间变化（如从浴室切换到厨房）
   - 新的关键视觉元素进入画面（如手持手机、价格标签、文字贴纸、分屏对比画面、新的人物或物体）

   第二优先：叙事目的切换。当核心转化目的发生变化时切分（如从开场悬念转到优惠机制、从优惠机制转到产品展示、从产品展示转到试穿反馈、从试穿反馈转到行动号召）。

   第三优先：时间节奏。单个分镜通常控制在 6-12 秒；如果视觉、口播语义和转化目的都连续，可以延长到 15-20 秒左右。只有当超过 20 秒仍无清晰切点时，再按口播语义或动作节奏切分。

   注意：禁止因"口播叙事完整"或"同一转化目的"而将两个明显不同的视觉画面合并为同一分镜。
7. 对开箱 haul / 服装试穿类视频，优先参考这种阶段链路：故事开场/情绪营销 → 优惠活动或购买动机 → 产品卖点/产品信息 → 试穿或真实体验 → 行动号召。同一阶段里出现多个相近款式、颜色、尺码或重复评价时，应合并概括。重大视觉切换需要保留边界，但同一商品的连续正面/侧面/背面展示、手部细节补拍、快速 B-roll 不要仅因镜头变化就拆成多个分镜。
8. 如果字幕里有西语、英语或其他语言，script 保留原语言；中文只写在分析字段里。
9. 小类判定优先级：平替对决型必须有明确双对象/双方案对比，例如贵价品牌 vs 平替、竞品 A vs 竞品 B、常规方案 vs 替代方案、每份成本/价格差并列比较、dupe/alternative 对照；只有单一品牌开箱、haul、试穿或测评时，即使提到 sale、cheaper、kid sizes、优惠购买技巧，也不要判为平替对决型。
10. 开箱主导结构优先归为开箱 / ASMR：如果视频从包裹/包装/袋子开始，持续出现打开、取出、展示、触摸材质、试穿或评价，主类应为“开箱 / ASMR”，小类通常为“开箱评测型”。价格促销只是分镜标签，不改变全片主类。
10a. 服饰 TikTok Shop haul 不等于开箱：如果视频没有包裹/包装/拆开/取出等开箱证据，而是创作者已经穿在身上或镜前连续试穿多件服装、鞋、配饰，并讲版型、材质、尺码、搭配、舒适度或购买链接，应优先判为“GRWM + 产品 / 教学穿插型”。“haul”只是购物分享语境，不能单独作为开箱 / ASMR 依据。
10b. 服饰 GRWM haul 的分镜标签要按商品段的转化目的收敛：颜色喜好、材质、厚薄、弹性、尺码、重量、是否成套、图案含义、conversation starter、是否适合穿出门等，通常是在给购买理由，应标“产品卖点”或“产品信息”。只有出现明确同框/分屏/Which is better/竞品/价格/功能对照时才标“产品对比”；不要仅因“我更喜欢这个颜色”“去年买过另一个款”“not with these shoes”标为产品对比。只有当核心是在表达惊喜、自信、治愈、身份认同等情绪价值，而不是讲具体商品理由时，才标“情绪营销”。“太短所以我不穿出门”这类个人试穿限制不是“适用场景”，应标“产品卖点”或“真实体验”。
11. 同一品牌内的童码/成人码、不同尺码、不同颜色、sale 折扣、cheaper 购买技巧属于开箱 haul 或产品测评中的购买信息，不是“平替对决型”。只有出现两个品牌、两个产品、贵价 vs 平替、dupe/alternative 或明确竞品对照时，才允许判为平替对决型。
12. 前后分屏型必须是同一对象、同一身体部位、同一空间或同一产品在“使用前 vs 使用后”“有产品 vs 无产品”“处理前 vs 处理后”的状态对比；同款服装不同颜色、不同尺码、不同姿态的左右分屏不是前后分屏型，应标为分屏对比 / 产品对比型，不能写成“使用前后”。
13. selling_point_angle/selling_point_subtype 是全片主卖点角度，必须始终选择一个，通常所有分镜保持一致；如果某段明显切换到另一个购买理由，可以按该段真实内容调整。
14. golden_3s_hook/golden_3s_subtype 只看视频开头约 0-3 秒或最早分镜，属于全片开场钩子；没有明确命中黄金3秒钩子时，golden_3s_hook、golden_3s_subtype、golden_3s_reason 都输出空字符串，不要为了填字段强行归类。

短视频分镜补充规则：对 12-30 秒的镜前 GRWM POV / 服装试穿短视频，不要因为全片都在展示同一件衣服就合并成 1 个分镜；如果画面或字幕依次出现开场情绪/亮相、多角度转身展示、版型/洗水/剪裁/尺码/购买码/链接等不同转化目的，通常拆成 3-4 个分镜。典型结构是：0-3 秒情绪营销或故事开场 → 中段优惠活动/购买动机或多角度展示 → 后段产品卖点/真实体验/行动号召。镜前 GRWM POV 单品试穿优先判为“GRWM + 产品 / 仪式步骤型”，不要创造“穿搭展示型”等体系外小类。注意：30-60 秒视频按视觉切换通常拆成 3-5 个分镜；60-120 秒通常拆成 4-6 个；2-5 分钟长视频最多 6 个分镜。禁止为了凑数量而拆分视觉切换；多个相近商品、连续试穿反馈、连续 T 恤/配饰/颜色展示应按商品组或阶段合并。

护肤/护发/美妆/洗护 GRWM 补充规则：如果主体内容是“使用频率/适用状态 → 操作步骤（按摩、涂抹、清洗、梳理等）→ 成分或功效 → 使用后体验/促销”，优先判为“GRWM + 产品 / 仪式步骤型”。开头的夸张情绪宣言、痛点表达或个人偏好只算情绪营销/黄金3秒钩子，不能覆盖全片小类。
护发/防脱/洗护产品优先级规则：只要创作者在浴室、镜前或个人护理场景中亲自展示护发、洗护、美妆、护肤产品包装，并完成涂抹、清洗、起泡、梳理、按摩、使用后效果展示等流程，即使字幕写了 POV，也优先判为“GRWM + 产品 / 仪式步骤型”；不要因为 POV 文案判为“第一人称视角”，也不要因为有使用前后效果判为“分屏对比”。

输出格式：
[
  {{
    "start_time": 数字,
    "end_time": 数字,
    "title": "从全局叙事步骤词库中选择的该分镜叙事角色",
    "scene_description": "画面描述",
    "script": "台词",
    "product_category": "画面中真实出现的商品品类，例如服装/护肤/清洁/工具/食品等",
    "product_classification": "从产品分类白名单中选择一个类目；无法判断则为空字符串",
    "evidence_frame": "证据关键帧编号，例如F03",
    "evidence_timestamp": 数字,
    "shot_type": "特写/镜前特写/分屏/对比/第一人称/全景",
    "content_tag": "从全局叙事步骤词库中选择，必须贴合该段真实内容",
    "viral_formula": "第一人称视角/开箱 / ASMR/GRWM + 产品/分屏对比/日常 Vlog",
    "formula_subtype": "对应大类下的小类",
    "category_reason": "为什么判定为这个大类和小类，简洁说明",
    "selling_point_angle": "专家背书/展示效果/轻松便捷/制造紧迫感/天然安全/价格优势/贩卖生活方式",
    "selling_point_subtype": "对应卖点角度下的小类",
    "selling_point_reason": "为什么判定为这个卖点角度，结合画面或口播证据",
    "golden_3s_hook": "提问式/挑战式/秘诀/技巧/震撼数据/争议式；没有明确命中则为空字符串",
    "golden_3s_subtype": "对应黄金3秒钩子下的小类；没有明确命中则为空字符串",
    "golden_3s_reason": "为什么判定为这个开头钩子，只引用开头0-3秒或最早分镜证据；没有明确命中则为空字符串",
    "visual_tactic": "该段使用的视觉手法，例如手持POV/开箱特写/镜前真人实测/左右分屏/生活流植入",
    "conversion_point": "这一段承担的转化作用"
  }}
]

要求：
- 只输出JSON数组，严禁markdown代码块。
- 如果存在真实口播或真实销售字幕，script 保留原语言原文，不要编造原文没有的句子；如果只有背景音乐歌词、无关音频或纯画面展示，script 写“无有效口播/字幕”，不要在 script 中复述画面描述。
- product_category 必须依据关键帧画面判断，不能依据无关音频歌词猜测。
- product_classification 必须严格从产品分类白名单中选择，且优先依据产品画面和商品语义；不确定时输出空字符串。
- evidence_frame/evidence_timestamp 必须对应你用于描述该分镜的关键帧；颜色、款式、商品只允许来自这个证据帧附近。
- 对服饰视频，不要在没有证据时写具体颜色；如果写颜色，必须是 evidence_frame 中清楚可见的颜色。
- scene_description 至少 30 个中文字符，要同时写清楚人物动作、商品状态/款式、镜头关系，以及这一段在爆款叙事中的作用；不要只写“展示产品”“创作者介绍商品”这种泛描述。
- script 需要覆盖该段完整口播/字幕语义。若同一时间段有多句口播，请合并保留关键原文；如果该段没有有效口播或字幕，固定写“无有效口播/字幕”，画面动作只写在 scene_description。
- 分镜边界不得机械按字幕时间戳切断台词：不要把一句完整台词、因果句、转折句或从句拆到两个分镜里，也不要让上一分镜 script 以未完成的连接语、铺垫语或半句话收尾。分镜时间边界可以围绕视觉切点前后微调，优先让每个 script 都是可独立理解的完整语义单元；如果视觉已经明显切换，则新分镜的 script 从下一句完整语义开始。
- 每个分镜的 conversion_point 必须具体到“为什么让用户更想买/更信任/更省钱/更理解差异”，不要写空泛的“促进转化”。
- selling_point_angle 和 selling_point_subtype 必须严格从“卖点角度分类体系”选择；selling_point_reason 要说明它解决的是信任、效果、省事、紧迫、安全、省钱还是生活方式想象。
- golden_3s_hook 和 golden_3s_subtype 只有在开头存在明确钩子时才从“黄金3秒钩子分类体系”选择；如果只是普通场景铺垫、产品自然出现、平铺直叙或无法判断，三个 golden_3s_* 字段都留空。golden_3s_reason 只能依据开头约 0-3 秒或最早分镜，不能引用后半段内容。
- content_tag 以该段核心转化作用为准。如果该段主要在讲便宜购买方法、优惠、折扣、deal、sale、coupon、price、save、link、shop、cart、购买路径或下单引导，优先标为“优惠活动”或“价格促销”；如果价格/链接只是产品展示或试穿反馈里的附带一句，不要覆盖该段原本的“产品卖点/真实体验”。但如果该段同时存在明显视觉切换（如手持手机展示价格页面、商店货架特写），优先按视觉边界拆分为独立分镜，再分别标注 content_tag。
- 如果画面或字幕出现“X vs Y”、“Which is better?”、“哪个更好”、竞品并列、两个产品同框比较、胜负结果、winner、价格/成分/功能对照，这类段落优先标为“产品对比”；如果重点是多个购买理由强弱，再标为“卖点对比”；如果重点是清洁/使用结果差异，再标为“效果对比”。不要标为“产品信息”或“产品亮相”。
- 对比类视频的开头即使只是展示两个产品，只要同时出现 vs/which is better/对比问题，也应视为“产品对比”，因为它承担的是建立对比对象和选择悬念。
- 对比类美妆/护肤视频的 title/content_tag 要按该段真实场景、口播语义和转化目的综合判断，不要只根据单个词或单个动作决定。开头建立比较需求或使用困扰时可标“用户痛点”；中段若涂抹、推开、展示质地是为了证明购买理由，可标“产品卖点”“产品功效”或“效果对比”；结尾只有在明确承担购买引导、推荐选择或下单路径时才标“行动号召”，否则保留“真实体验”“使用感受”或“产品卖点”等更贴切标签。
- 结尾推荐式 CTA 也属于“行动号召”：例如 recommend/choose/go for/get yours/order/buy/入手/选择/推荐某品牌或产品，尤其同时出现 cheap/price/link/shop/购买路径、快速到手、优惠等购买理由时，不要只标为“产品功效”。
- 汽车配件、工具、电子产品等功能型商品中，`功能演示` 和 `产品卖点` 的区别是：如果镜头重点是展示某个功能如何触发、如何操作、流程如何发生，标“功能演示”；如果口播/字幕明确说出一个可购买理由或规格优势，例如 sequential turn signals、IP68 waterproof、welcome sequence、durable、portable、fast 等，即使画面同时在演示，也优先标“产品卖点”。同一卖点的连续动态展示不要仅因动作变化拆成多个“功能演示”。
- 只有出现明确双对象/双方案对比，且包含 cheaper、cheap、dupe、alternative、save money、price、per serving、cost、same look、same quality、平替/贵价/大牌/竞品等替代价值表达时，formula_subtype 才优先选择“平替对决型”。单一品牌开箱中提到 sale、kids size、cheaper 只能作为“优惠活动/价格促销”分镜，不得覆盖“开箱 / ASMR”的主类判断。
- scene_description用中文写，结合画面动作和对应类型套路解释。
- 时间必须覆盖字幕中的关键内容，尽量与语义段落对齐。
- 分镜数量要克制：如果多个连续片段都在围绕同一产品、同一优惠机制、同一试穿反馈或同一行动号召展开，请合并为一个分镜，在 script 字段中保留该阶段的关键原文。
- 所有分镜的 viral_formula 和 formula_subtype 应保持一致，除非视频明显是混合结构；混合时也要以主类型为准。
- 不要把某个小类的示例流程当作硬性模板；title/content_tag 必须来自视频真实内容。
- title 和 content_tag 只能从“全局叙事步骤词库”中选择，严禁输出“多角度展示、转身展示、结束展示、服装试穿与展示、穿搭展示”等动作描述型或自造类型；这些画面动作应写进 scene_description，分镜类型要归一为“情绪营销/优惠活动/产品卖点/真实体验/行动号召”等标准步骤。

### 视觉切分强制触发示例
以下重大画面变化出现时，即使口播仍在继续，也应拆分为独立分镜；同一商品同一场景中的连续角度、表情、手部细节和过渡 B-roll 可以并入同一分镜：
- 画面从"严重水垢的淋浴头特写" → 切换为"两个蒸汽清洁器并排摆放"：应切分
- 画面从"单一产品使用" → 切换为"手持手机展示 TikTok Shop 价格页面"：应切分
- 画面从"清洁动作特写" → 切换为"商店货架/产品包装盒全景"：应切分
- 画面中出现承载新转化目的的文字贴纸/价格标签/分屏对比框：应切分

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


def build_golden_3s_recreation_instruction(item):
    hook = str(item.get("golden_3s_hook", "") or "").strip()
    subtype = str(item.get("golden_3s_subtype", "") or "").strip()
    reason = str(item.get("golden_3s_reason", "") or "").strip()
    opening_script = str(item.get("script", "") or "").strip()
    opening_scene = str(item.get("scene_description", "") or "").strip()
    if not hook and not subtype and not reason:
        return "源视频没有明确命中黄金3秒；新脚本开头不要硬套强钩子，应自然进入产品场景，并用首个画面快速交代产品价值。"

    subtype_rules = {
        "省钱秘笈": "先用“低价发现/隐藏福利/划算路径”制造信息差，再立刻接产品证明，不要只喊打折。",
        "比价追问": "先提出 X vs Y 或哪一个更值得买的问题，让观众等待答案，再用分镜逐步证明选择理由。",
        "痛点提问": "先问目标用户正在经历的具体麻烦，再立刻给出产品进入问题现场的画面。",
        "好奇提问": "先制造一个未揭晓的信息缺口，再用产品细节逐步填上答案。",
        "成本提问": "先追问真实花费、浪费或单次成本，再把产品价值换算成更容易判断的数字。",
        "槽点揭露": "先指出旧方法、热门产品或常见选择的具体缺陷，再让新产品承担解决方案。",
        "价格挑衅": "先用便宜选择挑战昂贵选择，再用效果、质感或规格证明不是廉价感。",
        "悬念验证": "先承诺测试或验证结果，保留结论到中后段再揭晓。",
        "结果前置": "先把最有冲击力的结果数字或变化放出来，再倒推产品如何做到。",
    }
    rule = subtype_rules.get(subtype)
    if not rule:
        hook_rules = {
            "提问式": "开头必须是能让目标用户代入的具体问题，不要写泛泛的“你知道吗”。",
            "挑战式": "开头必须设置一个可验证的挑战、测试或悬念，后续分镜要兑现结果。",
            "秘诀/技巧": "开头必须承诺一个具体技巧、避坑经验或路径信息，后续要交付可执行方法。",
            "震撼数据": "开头必须出现具体数字、时间、比例或价格差，并在后续解释数字来源。",
            "争议式": "开头必须有明确立场或冲突对象，但不能脱离产品真实卖点。",
        }
        rule = hook_rules.get(hook, "复刻开头的信息差、悬念或冲突结构，但替换为用户产品真实可证明的卖点。")

    return (
        f"源视频黄金3秒命中：{hook}{(' / ' + subtype) if subtype else ''}。\n"
        f"命中依据：{reason or opening_scene or opening_script}\n"
        f"复刻方法：{rule}\n"
        f"新脚本前 3 秒必须明确写出画面动作、屏幕字幕/口播、产品出现方式和观众继续看的理由。"
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
            ])
        )
    return "\n\n".join(lines) or "源视频未生成有效分镜。"


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

    return f"""
你是短视频爆款脚本复刻专家。你的任务是基于源视频拆解结果，为用户的新产品生成一版可拍摄的新脚本。

核心原则：
- 只复制结构、节奏、钩子和转化逻辑，不能照抄源视频原台词、品牌、商品、价格或具体承诺。
- 新脚本必须围绕用户产品真实信息展开；用户没提供的信息不要编造成事实，可以写成“画面展示/字幕强调”。
- 保留源视频的爆款公式、分镜目的、视觉手法和购买心理，但要换成用户产品能成立的表达。
- 如果源视频命中黄金3秒，必须在新脚本第一分镜明确体现“怎么命中”和“怎么复刻”。

源视频爆款结构：
- 爆款公式: {_source_formula(source_record)} / {_source_subtype(source_record)}
- 分类原因: {_source_category_reason(source_record)}
- 主卖点角度: {first_item.get("selling_point_angle", "")} / {first_item.get("selling_point_subtype", "")}
- 卖点依据: {first_item.get("selling_point_reason", "")}

黄金3秒复刻：
{golden_instruction}

用户产品信息：
{chr(10).join(product_lines) if product_lines else "- 用户尚未填写详细产品信息，请根据上传图片中能看见的内容保守生成，并提示需要补充的拍摄信息。"}

源视频分镜模板：
{summarize_source_shots(source_record)}

生成规则：
1. {duration_rule}
2. 分镜数量尽量与源视频一致；每个分镜都要说明复刻了源视频的哪种叙事作用。
3. 每个分镜必须包含：时长、画面动作、口播/字幕、新脚本、拍摄要点、复刻逻辑、转化作用。
4. 第一分镜如果有黄金3秒，必须输出 hook_implementation，具体写清楚前 0-3 秒画面、字幕/口播、为什么能抓住观众、用户产品如何承接。
5. shots 必须是非空数组，且必须逐条输出可拍摄分镜；只返回 copy_strategy 或总结文字是不合格结果。
6. 不要输出 markdown，不要输出解释性正文，只输出 JSON 对象。

输出格式：
{{
  "copy_strategy": {{
    "source_formula": "{_source_formula(source_record)}",
    "source_subtype": "{_source_subtype(source_record)}",
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
      "new_script": "完整可拍的新脚本",
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
你是跨境电商商品标题解析和短视频带货卖点提炼助手。请根据用户输入的商品标题、品类、补充内容和可选图片，生成适合放进短视频脚本的商品卖点。

要求：
- 只输出 JSON 对象，不要 markdown，不要解释。
- 卖点必须是短词或短语，每个 2-12 个中文字符，最多 6 个。
- 优先提取商品标题中的真实属性：品类、适用人群、尺码范围、材质、规格、用途、场景、数量、容量、重量、关键成分。
- 如果标题是外语，翻译成自然中文短语，例如 Blusa/Camisa/Feminina/Plus Size/Viscolinho/46 Ao 54 可提取为“女士上衣”“大码”“粘胶纤维”“46到54”。
- 不要把完整商品标题原样作为卖点。
- 不要编造标题或图片里没有的功效、疗效、认证、销量、评价、折扣。
- 如果只能确定品类和规格，也要保守输出确定信息。
- product_classification 必须从固定类目中选择；无法判断输出空字符串。

固定类目：
{", ".join(PRODUCT_CLASSIFICATION_OPTIONS)}

用户商品信息：
{chr(10).join(product_lines) if product_lines else "- 用户未填写文字信息，请只根据图片中能看见的内容保守生成。"}

输出格式：
{{
  "product_classification": "固定类目或空字符串",
  "selling_points": ["短卖点1", "短卖点2"],
  "reason": "一句话说明卖点来自哪些标题属性或图片信息"
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


def build_fallback_script_copy_shots(source_record, product_input):
    product_input = normalize_script_copy_product_input(product_input)
    product_name = product_input.get("product_name") or "用户产品"
    selling_points = product_input.get("selling_points") or "核心卖点"
    usage_scene = product_input.get("usage_scene") or product_input.get("target_audience") or "目标使用场景"
    price_offer = product_input.get("price_offer") or "当前优惠/购买理由"
    source_items = [item for item in source_record.get("data", []) if isinstance(item, dict)]
    if not source_items:
        source_items = [{
            "title": "产品开场",
            "scene_description": "展示产品和核心问题。",
            "conversion_point": "让观众理解产品适合谁、解决什么问题。",
        }]

    golden_instruction = build_golden_3s_recreation_instruction(first_golden_3s_item(source_record))
    shots = []
    for index, item in enumerate(source_items, start=1):
        title = first_non_empty(item.get("title"), item.get("content_tag"), f"分镜 {index}")
        source_scene = first_non_empty(item.get("scene_description"), item.get("script"), "承接源视频对应段落的叙事作用")
        conversion = first_non_empty(
            item.get("conversion_point"),
            "把产品信息转成用户能理解的购买理由。",
        )
        is_first = index == 1
        visual_plan = (
            f"前 3 秒直接展示 {product_name} 和最有冲突感的使用前问题，"
            f"用手部动作或近景把观众注意力拉到产品上。"
            if is_first else
            f"延续源视频“{title}”段落节奏，拍摄 {product_name} 的实物细节、使用动作或前后变化。"
        )
        screen_text = (
            f"{product_name}｜{selling_points}"
            if is_first else
            first_non_empty(selling_points, usage_scene, product_name)
        )
        voiceover = (
            f"如果你也在找{usage_scene}能用的办法，先看这个{product_name}。"
            if is_first else
            f"这一段重点拍清楚：{selling_points}，让观众知道它为什么适合{usage_scene}。"
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
            "hook_implementation": golden_instruction if is_first else "",
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
    shots = parsed.get("shots") or parsed.get("data") or parsed.get("items") or []
    if not isinstance(shots, list):
        shots = []
    shots = [shot for shot in shots if isinstance(shot, dict)]
    if not shots:
        shots = build_fallback_script_copy_shots(source_record, product_input)
        copy_strategy.setdefault("fallback_reason", "模型未返回可拍摄分镜，系统已按源视频分镜结构生成兜底脚本。")

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
    if log_context:
        log_script_copy_job(
            log_context,
            "结果归一化完成",
            shots=len(result.get("shots", []) or []),
            cta_options=len(result.get("cta_options", []) or []),
            fallback=bool(result.get("copy_strategy", {}).get("fallback_reason")),
        )
    return result


def normalize_content_tag(item):
    text = " ".join([
        str(item.get("title", "")),
        str(item.get("content_tag", "")),
        str(item.get("scene_description", "")),
        str(item.get("script", "")),
        str(item.get("conversion_point", "")),
    ]).lower()

    cta_keywords = [
        "go for", "choose", "pick up", "grab", "get yours", "get it", "order", "buy now",
        "shop now", "click the link", "link in bio", "add to cart", "check out",
        "选择", "选它", "买它", "入手", "下单", "点击链接", "购物车", "主页",
    ]
    recommendation_keywords = [
        "recommend", "would definitely recommend", "值得推荐", "推荐", "最好的", "the best",
    ]
    purchase_context_keywords = [
        "cheap", "cheaper", "quickly", "price", "buy", "purchase", "shop", "cart", "link",
        "便宜", "省钱", "优惠", "价格", "购买", "买", "下单", "链接",
    ]
    if _keyword_hits(text, cta_keywords) and (
        _keyword_hits(text, recommendation_keywords) or _keyword_hits(text, purchase_context_keywords)
    ):
        item["title"] = "行动号召"
        item["content_tag"] = "行动号召"
        if not item.get("conversion_point"):
            item["conversion_point"] = "通过明确推荐选择或购买该产品推动转化"
        return item

    # 如果模型已经输出了有效的 content_tag，优先保留，不做强制覆盖
    current_tag = str(item.get("content_tag", "")).strip()
    if current_tag in ALLOWED_STORY_STEPS:
        return item

    promo_keywords = [
        "便宜", "省钱", "优惠", "折扣", "促销", "活动", "价格", "购买", "买", "下单", "链接",
        "coupon", "discount", "deal", "sale", "cheap", "cheaper", "save", "price", "buy", "purchase",
        "link", "shop", "cart", "tiktok shop",
    ]
    if any(keyword in text for keyword in promo_keywords):
        item["content_tag"] = "优惠活动"
        if not item.get("conversion_point"):
            item["conversion_point"] = "通过价格、优惠或购买路径降低决策门槛"
        return item

    contrast_keywords = [
        " vs ", "vs.", "对比", "哪个更好", "哪一个更好", "更好", "差异", "区别", "比较", "胜出", "winner",
        "which is better", "compare", "comparison", "versus", "better than", "difference",
    ]
    if any(keyword in text for keyword in contrast_keywords):
        item["content_tag"] = "产品对比"
        if not item.get("conversion_point"):
            item["conversion_point"] = "通过并列比较建立产品选择理由"
        return item

    return item


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


def infer_standard_story_step(item):
    text = " ".join([
        str(item.get("title", "")),
        str(item.get("content_tag", "")),
        str(item.get("scene_description", "")),
        str(item.get("script", "")),
        str(item.get("conversion_point", "")),
    ]).lower()

    if _keyword_hits(text, ["coupon", "discount", "deal", "sale", "price", "code", "link", "shop", "cart", "购买", "链接", "优惠", "折扣", "促销", "价格"]):
        return "优惠活动"
    if _keyword_hits(text, ["vs", "which is better", "compare", "comparison", "winner", "对比", "哪个更好"]):
        return "产品对比"
    if _keyword_hits(text, ["差异", "区别", "不同", "旧方法", "普通产品", "常规方案"]):
        return "产品差异"
    if _keyword_hits(text, ["wash", "cut", "fit", "sizing", "size", "denim", "版型", "剪裁", "洗水", "尺码", "腰部", "臀部", "显瘦", "包裹"]):
        return "产品卖点"
    if _keyword_hits(text, ["turn", "side", "back", "try on", "mirror", "转身", "侧面", "背面", "试穿", "上身", "多角度"]):
        return "真实体验"
    if _keyword_hits(text, ["smile", "excited", "happy", "情绪", "微笑", "开心", "自信", "满意"]):
        return "情绪营销"
    return "产品亮相"


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


def normalize_vehicle_accessory_story_step(item):
    product_category = str(item.get("product_category", "")).lower()
    if not _keyword_hits(product_category, ["汽车", "车", "vehicle", "car", "truck", "auto"]):
        return item

    text = " ".join([
        str(item.get("title", "")),
        str(item.get("content_tag", "")),
        str(item.get("scene_description", "")),
        str(item.get("script", "")),
        str(item.get("conversion_point", "")),
    ]).lower()

    if str(item.get("title", "")).strip() == "功能演示" or str(item.get("content_tag", "")).strip() == "功能演示":
        if _keyword_hits(text, [
            "sequential", "turn signal", "turn signals", "welcome sequence", "waterproof", "ip68",
            "rain or shine", "流水", "转向灯", "欢迎序列", "防水", "雨天", "耐用",
        ]):
            item["title"] = "产品卖点"
            item["content_tag"] = "产品卖点"

    return item


def _keyword_hits(text, keywords):
    return [keyword for keyword in keywords if keyword in text]


def infer_selling_point_taxonomy(text):
    text = (text or "").lower()
    rules = [
        (
            "专家背书",
            [
                ("从业者内幕", ["as a doctor", "as a trainer", "industry", "insider", "从业", "业内", "行业", "私下用"]),
                ("专业背书", ["doctor", "dermatologist", "expert", "trainer", "nutritionist", "医生", "专家", "营养师", "教练", "技师"]),
                ("机构认证", ["certified", "lab", "clinical", "patent", "tested", "approved", "认证", "实验室", "临床", "专利", "检测报告", "批准"]),
                ("反向信任", ["overhyped", "don't trust", "not worth", "别信", "吐槽", "热门产品", "智商税", "夸大"]),
            ],
            "通过背书信息降低信任门槛。",
        ),
        (
            "展示效果",
            [
                ("实时演示", ["capture", "remove", "clean", "works", "watch", "demo", "演示", "实时", "吸附", "清洁", "去除", "立刻", "马上", "现场"]),
                ("对照测试", ["vs", "compare", "comparison", "test against", "对照", "竞品", "对比测试", "同时测试"]),
                ("前后时间线", ["before and after", "before/after", "使用前后", "前后对比", "day 1", "7 days", "时间线"]),
                ("个人蜕变故事", ["changed my life", "transformation", "my journey", "改变了我", "蜕变", "变化过程"]),
                ("用户证言集", ["review", "reviews", "comment", "comments", "rating", "testimonial", "评价", "评论区", "评分", "证言"]),
                ("数据证明", ["data", "clinical", "lab", "%", "hours", "数据", "实验", "续航", "提升", "降低"]),
            ],
            "核心说服力来自画面或口播对效果的直接证明。",
        ),
        (
            "轻松便捷",
            [
                ("免决策", ["only one", "best choice", "no brainer", "不用纠结", "闭眼入", "唯一选择", "免决策"]),
                ("随时随地", ["portable", "travel", "pocket", "bag", "carry", "on the go", "便携", "旅行", "通勤", "随身", "车载"]),
                ("零门槛", ["beginner", "simple", "install", "anyone", "新手", "简单", "好上手", "安装", "零门槛"]),
                ("省时间", ["quick", "fast", "seconds", "minutes", "省时", "快速", "几秒", "几分钟"]),
                ("省步骤", ["one step", "lazy", "without", "no need", "一键", "一步", "懒人", "不用", "无需", "省步骤"]),
            ],
            "购买理由集中在降低使用成本和操作门槛。",
        ),
        (
            "制造紧迫感",
            [
                ("库存警告", ["sold out", "stock", "restock", "库存", "补货", "抢", "快没了", "售罄"]),
                ("限时折扣", ["limited-time", "limited time", "today only", "expires", "ends tonight", "last chance", "coupon", "deal ends", "限时", "截止", "倒计时", "今天结束", "最后机会", "优惠券"]),
                ("渠道独占", ["only on", "exclusive", "tiktok shop only", "独家", "渠道", "直播间", "当前链接"]),
                ("社证加速", ["viral", "everyone is buying", "bestseller", "爆单", "都在买", "榜单", "跟风"]),
            ],
            "通过时间、库存或节点压力推动立即行动。",
        ),
        (
            "天然安全",
            [
                ("成分透明", ["natural", "organic", "plant", "clean ingredients", "天然", "有机", "植物", "无添加", "成分", "不含"]),
                ("敏感群体安全", ["kids", "baby", "pet safe", "family", "pregnant", "儿童", "宝宝", "宠物", "全家", "孕妇", "敏感肌"]),
                ("安全恐吓", ["toxic", "harmful", "hidden danger", "有毒", "危险", "隐藏风险", "伤害"]),
                ("低负担安心", ["non-toxic", "nontoxic", "sensitive", "no alcohol", "低卡", "低糖", "无毒", "低刺激", "食品级", "环保"]),
            ],
            "主卖点在于降低安全风险和使用顾虑。",
        ),
        (
            "价格优势",
            [
                ("隐性成本曝光", ["waste money", "wasted", "hidden cost", "浪费钱", "隐性成本", "无效替代", "花冤枉钱"]),
                ("替代价值", ["replace", "instead of", "all in one", "替代多个", "一支搞定", "省下", "总节省"]),
                ("日均成本拆解", ["per serving", "per use", "per day", "cost breakdown", "每份", "每次", "每天", "单价", "成本"]),
                ("平替发现", ["dupe", "alternative", "same look", "same quality", "平替", "替代", "同款", "贵价", "发现"]),
                ("直接比价", ["cheap", "cheaper", "sale", "price", "full price", "on sale", "never on sale", "look at the price", "under $", "便宜", "低价", "比价", "价格标签", "原价", "全价", "打折", "划算"]),
            ],
            "通过价格、成本或折扣降低购买阻力。",
        ),
        (
            "贩卖生活方式",
            [
                ("圈层标识", ["for moms", "pet owners", "gym girls", "clean girl", "圈层", "人群", "妈妈", "宠物家庭", "健身人群"]),
                ("理想自我投射", ["confidence", "become", "dream", "自信", "理想", "想成为", "更好的自己"]),
                ("送礼叙事", ["gift", "present", "holiday gift", "礼物", "送礼", "节日", "伴侣"]),
                ("场景代入", ["summer vibes", "vacation", "patio", "party", "bedroom", "庭院", "派对", "卧室", "通勤", "度假"]),
                ("文化认同", ["aesthetic", "trend", "viral", "tiktok made me buy", "亚文化", "流行", "趋势", "同款"]),
                ("审美升级", ["outfit", "style", "fashion", "cozy", "comfy", "审美", "穿搭", "风格", "精致", "质感", "舒服"]),
            ],
            "视频把商品包装成一种可向往、可代入的生活状态。",
        ),
    ]

    for angle, subrules, reason in rules:
        for subtype, keywords in subrules:
            if _keyword_hits(text, keywords):
                return {
                    "selling_point_angle": angle,
                    "selling_point_subtype": subtype,
                    "selling_point_reason": reason,
                }

    return {
        "selling_point_angle": "展示效果",
        "selling_point_subtype": "结果场景呈现",
        "selling_point_reason": "默认按画面呈现的产品结果和使用收益归类。",
    }


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


def infer_golden_3s_taxonomy(text):
    text = (text or "").lower()
    question_keywords = [
        "?", "？", "got ", "do you", "are you", "which is better", "listen if",
        "why is everyone", "how much", "你", "吗", "为什么", "有没有", "哪个", "多少钱",
    ]
    pain_keywords = ["pain", "problem", "dirty", "dust", "hair", "毛", "脏", "痛点", "困扰", "麻烦", "失败", "焦虑"]
    if _keyword_hits(text, question_keywords):
        if _keyword_hits(text, ["which is better", "哪个", "哪一个"]):
            subtype = "比价追问"
        elif _keyword_hits(text, ["how much", "cost", "price", "spend", "多少钱", "花费", "成本"]):
            subtype = "成本提问"
        elif _keyword_hits(text, pain_keywords):
            subtype = "痛点提问"
        elif _keyword_hits(text, ["why is everyone", "everyone", "all over", "所有人", "都在", "为什么大家"]):
            subtype = "从众提问"
        elif _keyword_hits(text, ["listen if", "for ", "if your", "如果你", "适合", "人群", "pet", "summer", "bathroom", "kitchen", "通勤", "健身", "浴室", "厨房"]):
            subtype = "场景驱动型"
        else:
            subtype = "好奇提问"
        return {
            "golden_3s_hook": "提问式",
            "golden_3s_subtype": subtype,
            "golden_3s_reason": "开头通过提问制造参与感或信息缺口，促使目标观众继续看。",
        }

    if _keyword_hits(text, ["battle", "boring", "until this", "no one likes", "nobody likes", "don't like", "hate", "unpopular opinion", "i said what i said", "dupe", "alternative", "don't buy", "stop buying", "wrong", "没人喜欢", "不喜欢", "无聊", "直到这个", "别买", "真香", "争议", "平替", "槽点", "颠覆"]):
        if _keyword_hits(text, ["dupe", "alternative", "平替"]):
            subtype = "价格挑衅"
        elif _keyword_hits(text, ["angry", "annoyed", "mad", "沮丧", "愤怒", "恼火", "吐槽"]):
            subtype = "情绪挑衅"
        elif _keyword_hits(text, ["wrong", "myth", "颠覆", "误区", "用错"]):
            subtype = "颠覆认知"
        elif _keyword_hits(text, ["boring", "until this", "don't buy", "stop buying", "no one likes", "nobody likes", "don't like", "hate", "没人喜欢", "不喜欢", "无聊", "直到这个", "别买", "缺陷", "槽点"]):
            subtype = "槽点揭露"
        else:
            subtype = "立场对抗"
        return {
            "golden_3s_hook": "争议式",
            "golden_3s_subtype": subtype,
            "golden_3s_reason": "开头通过强观点、对立选择或争议表达激发讨论。",
        }

    if _keyword_hits(text, ["mistake", "mistakes", "hack", "tip", "trick", "secret", "how to", "learn from", "nobody tells", "insider", "早知道", "技巧", "秘诀", "避坑", "踩坑", "没人告诉"]):
        subtype = "避坑技巧" if _keyword_hits(text, ["mistake", "mistakes", "learn from", "避坑", "踩坑", "早知道"]) else "使用技巧"
        if _keyword_hits(text, ["cheap", "cheaper", "save", "sale", "discount", "省钱", "便宜", "折扣"]):
            subtype = "省钱秘笈"
        elif _keyword_hits(text, ["insider", "industry", "圈内", "业内"]):
            subtype = "圈内信息"
        elif _keyword_hits(text, ["nobody tells", "secret", "few people", "没人告诉", "少数人", "别让太多人"]):
            subtype = "稀缺框架"
        elif _keyword_hits(text, ["shortcut", "faster", "hack", "捷径", "更快", "省步骤"]):
            subtype = "捷径承诺"
        return {
            "golden_3s_hook": "秘诀/技巧",
            "golden_3s_subtype": subtype,
            "golden_3s_reason": "开头承诺提供技巧、经验或避坑信息，制造实用价值期待。",
        }

    if _keyword_hits(text, ["does it work", "challenge", "test", "try this", "guess", "watch me", "story time", "挑战", "测试", "猜", "看看", "故事"]):
        if _keyword_hits(text, ["does it work", "really work", "真的有用", "试试看"]):
            subtype = "悬念验证"
        elif _keyword_hits(text, ["extreme", "stress test", "耐久", "极限", "荒谬"]):
            subtype = "极限测试"
        elif _keyword_hits(text, ["guess", "comment", "猜", "评论"]):
            subtype = "参与邀请"
        elif _keyword_hits(text, ["story", "crisis", "故事", "危机", "转折"]):
            subtype = "故事悬念"
        else:
            subtype = "场景还原"
        return {
            "golden_3s_hook": "挑战式",
            "golden_3s_subtype": subtype,
            "golden_3s_reason": "开头用挑战、警示或反常识表达拉高观看张力。",
        }

    if re.search(r"(\d+%|\$\s?\d+|\d+\s?(秒|分钟|天|倍|k|m))", text):
        subtype = "大数锚定" if _keyword_hits(text, ["k", "m", "sold", "views", "comments", "销量", "播放", "评论"]) else "结果前置"
        if "$" in text or _keyword_hits(text, ["省", "钱", "cost", "price"]):
            subtype = "对比冲击"
        if "%" in text or _keyword_hits(text, ["percent", "百分比"]):
            subtype = "百分比冲击"
        if _keyword_hits(text, ["秒", "分钟", "天", "second", "minute", "day"]):
            subtype = "时间线震撼"
        return {
            "golden_3s_hook": "震撼数据",
            "golden_3s_subtype": subtype,
            "golden_3s_reason": "开头用数字降低理解成本，并制造结果或差异冲击。",
        }

    return {
        "golden_3s_hook": "",
        "golden_3s_subtype": "",
        "golden_3s_reason": "",
    }


def normalize_marketing_taxonomies(items):
    combined_text = _combined_story_text(items)
    opening_text = _opening_story_text(items)
    selling = infer_selling_point_taxonomy(combined_text)
    golden_3s = infer_golden_3s_taxonomy(opening_text)

    for item in items:
        if not isinstance(item, dict):
            continue
        current_angle = item.get("selling_point_angle", "")
        should_override_selling = (
            not current_angle
            or (current_angle == "制造紧迫感" and selling.get("selling_point_angle") == "价格优势")
        )
        if should_override_selling:
            for key, value in selling.items():
                item[key] = value

        for key, value in golden_3s.items():
            item[key] = value
    return items


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


def should_reclassify_as_alternative_showdown(items):
    text = _combined_story_text(items)
    if not text.strip():
        return False

    alternative_value_keywords = [
        "平替", "替代品", "大牌", "贵价", "高价", "价格", "单价", "每份", "成本", "低价",
        "$", "price", "cost", "per serving", "dupe", "cheaper", "cheap", "affordable",
        "expensive", "save money", "save", "same look", "same quality",
    ]
    explicit_replacement_keywords = [
        "alternative", "instead of", "rather than", "替代方案", "常规方案",
    ]
    competitor_product_keywords = [
        "bissell", "redhut", "red-hut", "steam shot",
    ]
    comparison_keywords = [
        " vs ", "vs.", "versus", "which is better", "哪个更好", "哪一个更好", "对比",
        "比较", "差异", "区别", "compare", "comparison", "better than", "instead of",
        "rather than", "winner", "胜出", "compared", "next to",
    ]

    has_replacement = bool(_keyword_hits(text, explicit_replacement_keywords))
    has_competitor_product = bool(_keyword_hits(text, competitor_product_keywords))
    has_comparison = bool(_keyword_hits(text, comparison_keywords))
    has_contextual_alternative_value = _has_alternative_value_in_comparison_context(
        items,
        alternative_value_keywords,
        comparison_keywords,
    )

    if has_comparison and (has_contextual_alternative_value or (has_replacement and has_competitor_product)):
        return True

    return False


def should_classify_as_method_comparison(items):
    text = _combined_story_text(items)
    if not text.strip():
        return False

    split_or_same_subject = _keyword_hits(text, [
        "分屏", "左右", "两侧", "半边脸", "同一张脸", "同一面部", "face split", "split screen",
        "side", "one side", "other side", "tinted sunscreen", "invisible sunscreen",
    ])
    method_or_process = _keyword_hits(text, [
        "涂抹", "推开", "点涂", "融入", "抹开", "apply", "melt", "melts", "blend", "blends",
        "wear", "sunscreen", "防晒", "透明防晒", "有色防晒",
    ])
    same_problem = _keyword_hits(text, [
        "防晒", "sunscreen", "肤色", "skin tone", "skin", "uv", "spf",
    ])
    alternative_or_cost = _keyword_hits(text, [
        "平替", "dupe", "cheaper", "cheap", "cost", "per serving", "save money",
        "贵价", "大牌", "省钱", "成本",
    ])

    return bool(split_or_same_subject and method_or_process and same_problem and not alternative_or_cost)


def normalize_as_method_comparison(items):
    reason = "画面围绕同一防晒需求，在同一面部左右区域按步骤涂抹并比较两种防晒方案的呈现效果；核心是解决同一问题的不同方法并排对比，不是价格/平替价值对决。"
    for item in items:
        if not isinstance(item, dict):
            continue
        item["viral_formula"] = "分屏对比"
        item["formula_subtype"] = "方法对比型"
        item["category_reason"] = reason
        normalize_method_comparison_story_step(item)
    return items


def normalize_method_comparison_story_step(item):
    text = " ".join([
        str(item.get("title", "")),
        str(item.get("content_tag", "")),
        str(item.get("scene_description", "")),
        str(item.get("script", "")),
        str(item.get("conversion_point", "")),
    ]).lower()
    is_applicable_people = (
        str(item.get("title", "")).strip() == "适用人群"
        or str(item.get("content_tag", "")).strip() == "适用人群"
    )
    sunscreen_method_context = _keyword_hits(text, [
        "sunscreen", "防晒", "tinted", "invisible", "makeup", "blurring", "filter",
        "skin tone", "shade", "妆前", "妆感", "肤色", "有色", "透明", "隐形",
    ])
    explicit_people_context = _keyword_hits(text, [
        "妈妈", "上班族", "健身人群", "懒人", "旅行者", "宠物家庭", "儿童", "孕妇",
        "敏感肌", "for moms", "pet owners", "gym", "travelers", "kids", "pregnant",
    ])
    if is_applicable_people and sunscreen_method_context and not explicit_people_context:
        item["title"] = "产品卖点"
        item["content_tag"] = "产品卖点"
        item["conversion_point"] = (
            "把两款防晒的妆感、可否叠加化妆和日常使用顾虑讲清楚，帮助观众按使用方式选择，"
            "不是按固定人群标签对号入座。"
        )
    return item


def should_classify_as_unboxing_review(items):
    text = _combined_story_text(items)
    if not text.strip():
        return False

    unboxing_keywords = [
        "开箱", "拆箱", "拆包", "拆开", "打开", "包裹", "包装", "袋子", "取出", "拿出",
        "package", "packaging", "open it", "open this", "let's open", "unbox", "unboxing",
        "bag",
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
    single_brand_haul_keywords = [
        "comfortbitch", "comfort", "hoodie", "pants", "tie-dye", "pink", "purple",
        "kid size", "kid sizes", "adult size", "adult sizes", "童码", "成人码",
        "扎染", "连帽衫", "运动裤", "试穿", "try them on", "soft", "sale",
    ]

    unboxing_hits = sum(1 for keyword in unboxing_keywords if keyword in text)
    review_hits = sum(1 for keyword in review_keywords if keyword in text)
    direct_showdown_hits = sum(1 for keyword in direct_showdown_keywords if keyword in text)
    haul_hits = sum(1 for keyword in single_brand_haul_keywords if keyword in text)

    if direct_showdown_hits > 0:
        return False

    return (unboxing_hits >= 2 and review_hits >= 1) or (unboxing_hits >= 1 and haul_hits >= 3)


def normalize_as_unboxing_review(items):
    reason = "视频主线从包裹/包装开场，持续拆开、取出、展示并评价商品；促销或童码价格技巧只是开箱测评中的卖点，因此判定为开箱评测型。"
    for item in items:
        if not isinstance(item, dict):
            continue
        item["viral_formula"] = "开箱 / ASMR"
        item["formula_subtype"] = "开箱评测型"
        item["category_reason"] = reason
    return items


def should_classify_as_grwm_apparel_haul(items):
    text = _combined_story_text(items)
    if not text.strip():
        return False

    actual_unboxing_hits = _keyword_hits(text, [
        "开箱", "拆箱", "拆包", "拆开", "打开包裹", "包裹", "包装", "取出",
        "package", "packaging", "open it", "open this", "let's open", "unbox", "unboxing",
    ])
    haul_hits = _keyword_hits(text, [
        "haul", "tiktok shop haul", "rapid fire", "shopping cart", "added cart", "购物车",
    ])
    worn_or_tryon_hits = _keyword_hits(text, [
        "穿着", "试穿", "上身", "换上", "展示服装", "面对镜头", "镜头前", "try on",
        "wearing", "wear", "outfit", "fit", "this is cute", "this one's even cuter",
    ])
    apparel_hits = _keyword_hits(text, [
        "服装", "服饰", "连衣裙", "裙", "t恤", "裤", "鞋", "凉鞋", "墨镜", "配饰",
        "dress", "t-shirt", "tshirts", "t-shirts", "sweater", "pants", "shoes",
        "sandals", "glasses", "boxers", "shorts",
    ])
    guidance_hits = _keyword_hits(text, [
        "material", "quality", "stretchy", "thicker", "small", "medium", "large",
        "too short", "heavy", "lightweight", "oversized", "cropped", "comfy",
        "材质", "质量", "弹性", "尺码", "偏大", "偏小", "长度", "舒适", "轻便", "搭配",
    ])
    multi_item_hits = _keyword_hits(text, [
        "two colors", "this one's even cuter", "t-shirts", "tshirts", "sweater and the pants",
        "shoes", "glasses", "boxers", "last", "bundle", "rapid fire", "多件", "多款",
        "两种颜色", "一堆", "套装", "鞋", "墨镜", "最后一件",
    ])

    return bool(
        haul_hits
        and multi_item_hits
        and worn_or_tryon_hits
        and apparel_hits
        and guidance_hits
        and not actual_unboxing_hits
    )


def normalize_grwm_apparel_haul(items):
    reason = "视频主线是创作者真人上身试穿 TikTok Shop 服饰、鞋和配饰，并穿插讲解版型、材质、尺码、搭配和舒适度；没有拆包、取出包装或 ASMR 包装细节，因此应归为 GRWM + 产品 / 教学穿插型。"
    for item in items:
        if not isinstance(item, dict):
            continue
        item["viral_formula"] = "GRWM + 产品"
        item["formula_subtype"] = "教学穿插型"
        item["category_reason"] = reason
        current_angle = str(item.get("selling_point_angle", "")).strip()
        if not current_angle or current_angle == "展示效果":
            item["selling_point_angle"] = "轻松便捷"
            item["selling_point_subtype"] = "免决策"
            item["selling_point_reason"] = "创作者用快速真人试穿和尺码材质反馈替观众完成筛选，降低多件服饰下单前的选择成本。"
        normalize_grwm_apparel_haul_story_step(item)
    return items


def normalize_grwm_apparel_haul_story_step(item):
    title = str(item.get("title", "")).strip()
    content_tag = str(item.get("content_tag", "")).strip()
    text = _story_item_text(item)

    explicit_comparison = _keyword_hits(text, [
        " vs ", "vs.", "versus", "which is better", "哪个更好", "竞品", "dupe",
        "better than", "compared with", "side by side", "同框", "分屏", "价格对比", "功能对照",
    ])
    if (title == "产品对比" or content_tag == "产品对比") and not explicit_comparison:
        title = "产品卖点"
        content_tag = "产品卖点"

    product_reason_hits = _keyword_hits(text, [
        "material", "quality", "stretchy", "thicker", "small", "medium", "large",
        "too short", "heavy", "lightweight", "oversized", "cropped", "comfy",
        "conversation starters", "not a set", "barrel", "ruffle", "doesn't stretch",
        "材质", "质量", "弹性", "尺码", "偏大", "偏小", "长度", "短", "厚", "轻",
        "舒适", "成套", "图案", "上身", "穿出门",
    ])
    if title in {"情绪营销", "适用场景"} and product_reason_hits:
        title = "产品卖点"
        content_tag = "产品卖点"

    item["title"] = title
    item["content_tag"] = content_tag or title
    return item


def should_classify_as_grwm_ritual_tryon(items):
    text = _combined_story_text(items)
    if not text.strip():
        return False

    grwm_hits = _keyword_hits(text, [
        "grwm", "get ready", "mirror", "镜前", "对镜", "穿衣镜", "自拍", "try on", "试穿",
    ])
    apparel_hits = _keyword_hits(text, [
        "牛仔裤", "裤子", "jeans", "pants", "denim", "fit", "版型", "洗水", "剪裁", "穿搭", "服装", "服饰",
    ])
    ordered_show_hits = _keyword_hits(text, [
        "正面", "侧面", "背面", "转身", "多角度", "腰部", "臀部", "尺码", "购买", "链接", "code", "coupon",
    ])

    return grwm_hits and apparel_hits and ordered_show_hits


def normalize_grwm_ritual_tryon(items):
    reason = "视频以镜前 GRWM POV 试穿为主，按亮相、多角度转身、版型/尺码/购买信息等顺序展示单件服装，属于把产品嵌入个人准备流程的仪式步骤型。"
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("viral_formula") == "GRWM + 产品":
            item["formula_subtype"] = "仪式步骤型"
            item["category_reason"] = reason
    return items


def should_classify_as_grwm_ritual_care_routine(items):
    text = _combined_story_text(items)
    if not text.strip():
        return False

    grwm_or_care_hits = _keyword_hits(text, [
        "grwm", "get ready", "routine", "rutina", "mirror", "bathroom", "shower",
        "护肤", "护发", "美妆", "洗护", "护理", "浴室", "镜前", "头皮", "头发",
        "hair", "cabello", "cuero cabelludo", "scalp", "skin", "piel",
    ])
    product_hits = _keyword_hits(text, [
        "product", "spray", "serum", "cream", "oil", "mask", "minoxidil", "keratin", "keratina",
        "jengibre", "ginger", "shampoo", "conditioner", "喷雾", "精华", "面霜", "发膜", "洗发水",
        "护发素", "米诺地尔", "角蛋白", "生姜", "成分",
    ])
    frequency_hits = _keyword_hits(text, [
        "cada tres días", "cada dos días", "diario", "every day", "daily", "every two days",
        "every three days", "per day", "一天", "每天", "两天", "三天", "每周", "频率",
    ])
    step_hits = _keyword_hits(text, [
        "masajea", "massage", "apply", "use it", "usa lo", "usalo", "rinse", "wash", "comb",
        "涂抹", "按摩", "清洗", "冲洗", "梳理", "使用", "步骤", "顺序", "发根",
    ])
    ingredient_hits = _keyword_hits(text, [
        "ingredients", "ingredientes", "minoxidil", "jengibre", "ginger", "keratin", "keratina",
        "natural", "suaves", "成分", "米诺地尔", "生姜", "角蛋白", "温和",
    ])
    experience_hits = _keyword_hits(text, [
        "relajado", "relaxed", "feels", "result", "after", "después", "smooth", "thick",
        "舒服", "放松", "使用后", "效果", "变厚", "顺滑", "体验",
    ])

    routine_signal_count = sum([
        bool(frequency_hits),
        bool(step_hits),
        bool(ingredient_hits),
        bool(experience_hits),
    ])

    return grwm_or_care_hits and product_hits and routine_signal_count >= 2


def normalize_grwm_ritual_care_routine(items):
    reason = "视频虽有开头情绪钩子，但主体围绕护肤/护发/洗护产品的使用频率、操作步骤、成分功效和使用后体验展开，属于把产品嵌入个人护理流程的仪式步骤型。"
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("viral_formula") == "GRWM + 产品":
            item["formula_subtype"] = "仪式步骤型"
            item["category_reason"] = reason
    return items


def should_classify_as_grwm_product_care_demo(items):
    text = _combined_story_text(items).lower()
    if not text.strip():
        return False

    care_hits = _keyword_hits(text, [
        "hair", "scalp", "shampoo", "anti-dht", "dht", "baldness", "hair loss",
        "thinning hair", "hairline", "redensify", "densify", "bathroom", "shower",
        "护发", "头发", "头皮", "洗发", "防脱", "脱发", "发际线", "稀疏", "浴室", "洗护",
        "护肤", "美妆", "护理",
    ])
    product_hits = _keyword_hits(text, [
        "miraj", "product", "bottle", "tube", "shampoo", "serum", "spray", "cream",
        "品牌", "产品", "瓶", "管装", "包装", "洗发水", "精华", "喷雾", "膏体",
    ])
    usage_hits = _keyword_hits(text, [
        "apply", "wash", "rinse", "comb", "brush", "lather", "foam", "massage",
        "涂抹", "清洗", "冲洗", "梳", "刷", "起泡", "泡沫", "按摩", "使用", "步骤",
    ])
    result_hits = _keyword_hits(text, [
        "result", "after", "before", "solution", "cover", "coverage", "效果", "使用后", "前后", "解决方案",
    ])

    return bool(care_hits and product_hits and usage_hits and result_hits)


def normalize_grwm_product_care_demo(items):
    reason = "视频主体是创作者在浴室或镜前亲自完成护发、洗护、美妆等个人护理流程，并清晰露出产品包装、使用步骤和使用后效果；即使画面出现 POV 文案，也应优先归为 GRWM + 产品 / 仪式步骤型，而不是第一人称视角或分屏对比。"
    for item in items:
        if not isinstance(item, dict):
            continue
        item["viral_formula"] = "GRWM + 产品"
        item["formula_subtype"] = "仪式步骤型"
        item["category_reason"] = reason
    return items


def should_classify_as_same_item_variant_split(items):
    text = _combined_story_text(items).lower()
    if not text.strip():
        return False

    split_hits = _keyword_hits(text, [
        "分屏", "左右", "同屏", "同框", "并排", "两侧", "交叉剪辑", "快速剪辑", "快速切换",
        "two colors", "split screen", "side by side",
    ])
    variant_hits = _keyword_hits(text, [
        "粉色", "灰色", "颜色", "两种颜色", "不同颜色", "同款", "同款式", "同一位", "同一名",
        "长袍", "连衣裙", "头巾", "abaya", "robe", "hijab", "scarf",
        "pink", "gray", "grey", "same style", "same item", "different color",
    ])
    before_after_hits = _keyword_hits(text, [
        "使用前", "使用后", "有无产品", "before and after", "before/after", "after use", "before use",
        "半边脸", "左右半边", "效果变化",
    ])
    alternative_hits = _keyword_hits(text, [
        "平替", "替代", "dupe", "alternative", "cheaper", "cheap", "price", "$", "贵价", "竞品", "大牌",
        "save money", "instead of", "rather than",
    ])

    return bool(split_hits and variant_hits and not before_after_hits and not alternative_hits)


def normalize_same_item_variant_split(items):
    reason = "画面是同一服装或同款商品的不同颜色/姿态分屏对照展示，核心是变体差异和上身观感；没有使用前/使用后状态，也没有价格、竞品或替代价值证据，因此属于分屏对比 / 产品对比型，不能判为前后分屏型或平替对决型。"
    for item in items:
        if not isinstance(item, dict):
            continue
        item["viral_formula"] = "分屏对比"
        item["formula_subtype"] = "产品对比型"
        item["category_reason"] = reason
    return items


def normalize_formula_classification(items):
    if should_classify_as_grwm_apparel_haul(items):
        return normalize_grwm_apparel_haul(items)

    if should_classify_as_unboxing_review(items):
        return normalize_as_unboxing_review(items)

    if should_classify_as_same_item_variant_split(items):
        return normalize_same_item_variant_split(items)

    if should_classify_as_method_comparison(items):
        return normalize_as_method_comparison(items)

    if should_classify_as_grwm_product_care_demo(items):
        return normalize_grwm_product_care_demo(items)

    if should_reclassify_as_alternative_showdown(items):
        reason = "核心表达是贵价/竞品/常规方案与更便宜或替代方案的对比，强调平替价值，因此判定为平替对决型。"
        for item in items:
            if not isinstance(item, dict):
                continue
            item["viral_formula"] = "分屏对比"
            item["formula_subtype"] = "平替对决型"
            item["category_reason"] = reason
        return items

    if should_classify_as_grwm_ritual_tryon(items):
        return normalize_grwm_ritual_tryon(items)

    if should_classify_as_grwm_ritual_care_routine(items):
        return normalize_grwm_ritual_care_routine(items)

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
        item.setdefault("selling_point_angle", "")
        item.setdefault("selling_point_subtype", "")
        item.setdefault("selling_point_reason", "")
        item.setdefault("golden_3s_hook", "")
        item.setdefault("golden_3s_subtype", "")
        item.setdefault("golden_3s_reason", "")
        item.setdefault("product_category", "")
        item["product_classification"] = normalize_product_classification(
            item.get("product_classification") or item.get("product_category")
        )
        item.setdefault("evidence_frame", "")
        item.setdefault("evidence_timestamp", item.get("start_time", 0))
        normalize_content_tag(item)
        normalize_story_step_labels(item)
        normalize_vehicle_accessory_story_step(item)

    normalize_formula_classification(parsed)
    normalize_marketing_taxonomies(parsed)

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

    elif model_type in {"gptproto", "gemini", "gemini-2.5-pro"}:
        if not GPTPROTO_API_KEY:
            raise RuntimeError("未配置 GPTPROTO_API_KEY")

        target_model = "gemini-2.5-pro" if model_type == "gemini-2.5-pro" else BRAIN_MODEL
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
    result = enrich_storyboard_result(result, video_path)
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


async def _analyze_impl(
    file: UploadFile = None,
    video_url: str = Form(None),
    model: str = Form("gpt-4o"),
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
    model: str = Form("gpt-4o"),
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
    model: str = Form("gpt-4o"),
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
    target_model = model or "gemini-2.5-pro"
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
        result = generate_product_selling_points(product_input, target_model, visual_frames)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        print("商品卖点生成接口异常:", e)
        raise HTTPException(status_code=500, detail="商品卖点生成失败，请查看后端日志")

    return {"code": 0, "data": result}


@app.post("/product-selling-points")
async def product_selling_points(
    model: str = Form("gemini-2.5-pro"),
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
    model: str = Form("gemini-2.5-pro"),
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
        result = generate_script_copy(
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
    model: str = Form("gemini-2.5-pro"),
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
    model: str = Form("gemini-2.5-pro"),
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
