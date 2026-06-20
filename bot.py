#!/usr/bin/env python3
"""
البوت الإسلامي — Islamic Bot (النسخة الديناميكية v4)
====================================================
- يعمل في أي مجموعة/قناة يُضاف إليها (بدون حاجة لتحديد TARGET_CHATS مسبقاً)
- يتتبع الانضمام والإزالة تلقائياً عبر ملف channels.json
- أمر /leave للمشرفين لإجبار البوت على المغادرة
"""

import asyncio
import sys
import json
import logging
import random
from datetime import datetime, timedelta

# ── إصلاح مشكلة Windows مع aiodns / aiohttp ──────────────────────────────────
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
from pathlib import Path
from zoneinfo import ZoneInfo

import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from telegram import Bot, Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes,
    ChatMemberHandler,
)
from telegram.constants import ParseMode
from telegram.error import TelegramError, TimedOut, NetworkError
from telegram.request import HTTPXRequest

import config
import chat_settings as cs

# ── الميزات الإسلامية المتقدمة ─────────────────────────────────────────────────
try:
    import islamic_features
    ISLAMIC_FEATURES_ENABLED = True
except ImportError as _ie:
    ISLAMIC_FEATURES_ENABLED = False

# ── الميزات الجديدة (مسابقات، أنبياء، ردود، تذكيرات) ─────────────────────────
try:
    import new_features
    NEW_FEATURES_ENABLED = True
except ImportError as _ie2:
    NEW_FEATURES_ENABLED = False

# ── السجلات ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("IslamicBot")

# ── المسارات ───────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
BOOKS_DIR = BASE_DIR / "books"
BOOKS_DIR.mkdir(exist_ok=True)
CHANNELS_FILE = BASE_DIR / "channels.json"   # حفظ الدردشات المستهدفة ديناميكياً
SEP = "〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️"
RTL = "\u200f"

# ── تحميل المحتوى المحلي ───────────────────────────────────────────────────────
def load_json(filename: str) -> list | dict:
    for path in [BASE_DIR / filename, BASE_DIR / "content" / filename]:
        if path.exists():
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    logger.warning(f"ملف {filename} غير موجود")
    return []

STORIES    = load_json("stories.json")
DUAS       = load_json("duas.json")
FACTS      = load_json("facts.json")
ADHAN_MSGS = load_json("adhan_messages.json")
GOOD_DEEDS = load_json("good_deeds.json")

TZ = ZoneInfo(config.TIMEZONE)

# ── إدارة الدردشات المستهدفة (ديناميكي) ────────────────────────────────────
def load_target_chats() -> list[int]:
    """تحميل قائمة الدردشات من ملف JSON."""
    if CHANNELS_FILE.exists():
        with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("chats", [])
    return []

def save_target_chats(chats: list[int]):
    """حفظ قائمة الدردشات في ملف JSON."""
    with open(CHANNELS_FILE, "w", encoding="utf-8") as f:
        json.dump({"chats": chats}, f, ensure_ascii=False, indent=2)

def add_target_chat(chat_id: int):
    """إضافة دردشة إلى القائمة إذا لم تكن موجودة."""
    chats = load_target_chats()
    if chat_id not in chats:
        chats.append(chat_id)
        save_target_chats(chats)
        logger.info(f"تمت إضافة الدردشة {chat_id} إلى القائمة المستهدفة")

def remove_target_chat(chat_id: int):
    """إزالة دردشة من القائمة."""
    chats = load_target_chats()
    if chat_id in chats:
        chats.remove(chat_id)
        save_target_chats(chats)
        logger.info(f"تمت إزالة الدردشة {chat_id} من القائمة المستهدفة")

# ── جلسة HTTP ─────────────────────────────────────────────────────────────────
_session: aiohttp.ClientSession | None = None

async def get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        # ThreadedResolver بدل aiodns — يعمل مع ProactorEventLoop على Windows
        connector = aiohttp.TCPConnector(
            resolver=aiohttp.ThreadedResolver(),
            ssl=False,
        )
        _session = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=20),
            # نمنع الـ brotli encoding لأن aiohttp لا يدعمه بدون مكتبة إضافية
            headers={
                "User-Agent":      "IslamicBot/3.0",
                "Accept-Encoding": "gzip, deflate",
            },
        )
    return _session


# ══════════════════════════════════════════════════════════════════════════════
#  بيانات السور
# ══════════════════════════════════════════════════════════════════════════════

AYAH_COUNTS = {
    1:7, 2:286, 3:200, 4:176, 5:120, 6:165, 7:206, 8:75, 9:129,
    10:109, 11:123, 12:111, 13:43, 14:52, 15:99, 16:128, 17:111,
    18:110, 19:98, 20:135, 21:112, 22:78, 23:118, 24:64, 25:77,
    26:227, 27:93, 28:88, 29:69, 30:60, 31:34, 32:30, 33:73, 34:54,
    35:45, 36:83, 37:182, 38:88, 39:75, 40:85, 41:54, 42:53, 43:89,
    44:59, 45:37, 46:35, 47:38, 48:29, 49:18, 50:45, 51:60, 52:49,
    53:62, 54:55, 55:78, 56:96, 57:29, 58:22, 59:24, 60:13, 61:14,
    62:11, 63:11, 64:18, 65:12, 66:12, 67:30, 68:52, 69:52, 70:44,
    71:28, 72:28, 73:20, 74:56, 75:40, 76:31, 77:50, 78:40, 79:46,
    80:42, 81:29, 82:19, 83:36, 84:25, 85:22, 86:17, 87:19, 88:26,
    89:30, 90:20, 91:15, 92:21, 93:11, 94:8, 95:8, 96:19, 97:5,
    98:8, 99:8, 100:11, 101:11, 102:8, 103:3, 104:9, 105:5, 106:4,
    107:7, 108:3, 109:6, 110:3, 111:5, 112:4, 113:5, 114:6,
}

SURAH_NAMES = {
    1:"الفاتحة", 2:"البقرة", 3:"آل عمران", 4:"النساء", 5:"المائدة",
    6:"الأنعام", 7:"الأعراف", 8:"الأنفال", 9:"التوبة", 10:"يونس",
    11:"هود", 12:"يوسف", 13:"الرعد", 14:"إبراهيم", 15:"الحجر",
    16:"النحل", 17:"الإسراء", 18:"الكهف", 19:"مريم", 20:"طه",
    21:"الأنبياء", 22:"الحج", 23:"المؤمنون", 24:"النور", 25:"الفرقان",
    26:"الشعراء", 27:"النمل", 28:"القصص", 29:"العنكبوت", 30:"الروم",
    31:"لقمان", 32:"السجدة", 33:"الأحزاب", 34:"سبأ", 35:"فاطر",
    36:"يس", 37:"الصافات", 38:"ص", 39:"الزمر", 40:"غافر",
    41:"فصلت", 42:"الشورى", 43:"الزخرف", 44:"الدخان", 45:"الجاثية",
    46:"الأحقاف", 47:"محمد", 48:"الفتح", 49:"الحجرات", 50:"ق",
    51:"الذاريات", 52:"الطور", 53:"النجم", 54:"القمر", 55:"الرحمن",
    56:"الواقعة", 57:"الحديد", 58:"المجادلة", 59:"الحشر", 60:"الممتحنة",
    61:"الصف", 62:"الجمعة", 63:"المنافقون", 64:"التغابن", 65:"الطلاق",
    66:"التحريم", 67:"الملك", 68:"القلم", 69:"الحاقة", 70:"المعارج",
    71:"نوح", 72:"الجن", 73:"المزمل", 74:"المدثر", 75:"القيامة",
    76:"الإنسان", 77:"المرسلات", 78:"النبأ", 79:"النازعات", 80:"عبس",
    81:"التكوير", 82:"الانفطار", 83:"المطففين", 84:"الانشقاق",
    85:"البروج", 86:"الطارق", 87:"الأعلى", 88:"الغاشية", 89:"الفجر",
    90:"البلد", 91:"الشمس", 92:"الليل", 93:"الضحى", 94:"الشرح",
    95:"التين", 96:"العلق", 97:"القدر", 98:"البينة", 99:"الزلزلة",
    100:"العاديات", 101:"القارعة", 102:"التكاثر", 103:"العصر",
    104:"الهمزة", 105:"الفيل", 106:"قريش", 107:"الماعون",
    108:"الكوثر", 109:"الكافرون", 110:"النصر", 111:"المسد",
    112:"الإخلاص", 113:"الفلق", 114:"الناس",
}


# ══════════════════════════════════════════════════════════════════════════════
#  جلب البيانات
# ══════════════════════════════════════════════════════════════════════════════

async def fetch_quran_verse(surah: int = None, ayah: int = None) -> dict | None:
    if surah is None:
        surah = random.randint(1, 114)
    if ayah is None:
        ayah = random.randint(1, AYAH_COUNTS.get(surah, 10))

    surah_name = SURAH_NAMES.get(surah, f"سورة {surah}")
    session = await get_session()

    try:
        text_url = (
            f"https://cdn.jsdelivr.net/gh/fawazahmed0/quran-api@1"
            f"/editions/ara-quranacademy/{surah}/{ayah}.json"
        )
        async with session.get(text_url) as resp:
            if resp.status != 200:
                return None
            data = json.loads(await resp.text())
        arabic_text = data.get("text", "")
        if not arabic_text:
            return None

        tafsir_text = ""
        try:
            tafsir_url = (
                f"https://cdn.jsdelivr.net/gh/fawazahmed0/quran-api@1"
                f"/editions/ara-jalaladdinalmah/{surah}/{ayah}.json"
            )
            async with session.get(tafsir_url) as tresp:
                if tresp.status == 200:
                    tdata = json.loads(await tresp.text())
                    tafsir_text = tdata.get("text", "")
        except Exception:
            pass

        return {
            "surah_number": surah,
            "surah_name":   surah_name,
            "ayah_number":  ayah,
            "arabic":       arabic_text,
            "tafsir":       tafsir_text,
        }
    except Exception as e:
        logger.error(f"fetch_quran_verse error: {e}")
        return None


async def fetch_hadith() -> dict | None:
    session = await get_session()
    book_id, book_name, max_num = random.choice(config.HADITH_BOOKS)
    hadith_num = random.randint(1, max_num)
    try:
        url = (
            f"https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1"
            f"/editions/{book_id}/{hadith_num}.json"
        )
        async with session.get(url) as resp:
            if resp.status != 200:
                return None
            data = json.loads(await resp.text())
        hadiths = data.get("hadiths", [])
        if hadiths:
            entry = hadiths[0]
            text = entry.get("text", "")
            hadith_id = entry.get("id", hadith_num)
        else:
            text = data.get("text", "")
            hadith_id = data.get("id", hadith_num)
        if not text:
            return None
        return {"book_name": book_name, "hadith_num": hadith_id, "text": text}
    except Exception as e:
        logger.error(f"fetch_hadith error: {e}")
        return None


async def fetch_prayer_times() -> dict | None:
    session = await get_session()
    today = datetime.now(TZ)
    try:
        url = (
            f"https://api.aladhan.com/v1/timingsByCity"
            f"?city={config.PRAYER_CITY}"
            f"&country={config.PRAYER_COUNTRY}"
            f"&method={config.PRAYER_METHOD}"
            f"&date={today.strftime('%d-%m-%Y')}"
        )
        async with session.get(url) as resp:
            if resp.status != 200:
                return None
            data = json.loads(await resp.text())
            timings = data["data"]["timings"]
            return {k: timings[k] for k in ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]}
    except Exception as e:
        logger.error(f"fetch_prayer_times error: {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
#  أسماء الله الحسنى — 99 اسماً مع شرحها
# ══════════════════════════════════════════════════════════════════════════════

ALLAH_NAMES = [
    {"name": "الله",        "meaning": "العَلَم على الذات الإلهية الجامع لجميع الصفات"},
    {"name": "الرحمن",      "meaning": "ذو الرحمة الواسعة التي وسعت كل شيء"},
    {"name": "الرحيم",      "meaning": "كثير الرحمة بعباده المؤمنين في الآخرة خاصةً"},
    {"name": "الملك",       "meaning": "المالك لجميع الأشياء، له التصرف المطلق"},
    {"name": "القدوس",      "meaning": "المنزّه عن كل عيب ونقص، الطاهر المقدّس"},
    {"name": "السلام",      "meaning": "ذو السلامة من كل نقص، المُسلِّم عباده من العذاب"},
    {"name": "المؤمن",      "meaning": "المصدِّق عباده المؤمنين، المُؤمِّن خلقه من ظلمه"},
    {"name": "المهيمن",     "meaning": "الرقيب الحافظ على كل شيء، المسيطر بعلمه"},
    {"name": "العزيز",      "meaning": "الغالب الذي لا يُغلَب، القوي الذي لا مثيل له"},
    {"name": "الجبار",      "meaning": "القاهر لخلقه على ما يريد، الجابر لكسر عباده"},
    {"name": "المتكبر",     "meaning": "المتعظِّم عن كل سوء، الكبير المتعالي عن الشركاء"},
    {"name": "الخالق",      "meaning": "الموجِد للأشياء من العدم على غير مثال سابق"},
    {"name": "البارئ",      "meaning": "الفاطر الخالق لصور المخلوقات ومميِّز بعضها من بعض"},
    {"name": "المصوِّر",    "meaning": "الذي يصوِّر الخلق كيف يشاء ويُعطيه الصورة اللائقة"},
    {"name": "الغفار",      "meaning": "كثير الغفران لذنوب عباده مهما تكررت"},
    {"name": "القهار",      "meaning": "الغالب جميع خلقه، القاهر لكل شيء بقدرته"},
    {"name": "الوهاب",      "meaning": "كثير العطاء والمنح بلا عوض ولا سبب"},
    {"name": "الرزاق",      "meaning": "المتكفّل برزق كل مخلوق، الموسِّع على عباده"},
    {"name": "الفتاح",      "meaning": "الحاكم بين عباده، الفاتح لأبواب الرحمة والرزق"},
    {"name": "العليم",      "meaning": "المحيط علمه بكل شيء جليلاً ودقيقاً"},
    {"name": "القابض",      "meaning": "الذي يقبض الأرواح ويضيّق الرزق بحكمته"},
    {"name": "الباسط",      "meaning": "الذي يبسط الرزق ويوسّعه على من يشاء"},
    {"name": "الخافض",      "meaning": "الذي يخفض الجبابرة والطغاة ويُذلّهم"},
    {"name": "الرافع",      "meaning": "الذي يرفع المؤمنين والمتواضعين بالدرجات"},
    {"name": "المعزّ",      "meaning": "الذي يُعزّ من يشاء من عباده وينصره"},
    {"name": "المذلّ",      "meaning": "الذي يُذلّ من يشاء ممن يستحق الإذلال"},
    {"name": "السميع",      "meaning": "المحيط سمعه بكل مسموع خفيّ وجليّ"},
    {"name": "البصير",      "meaning": "المحيط بصره بكل مرئي دقيق وكبير"},
    {"name": "الحكم",       "meaning": "الحاكم بين عباده بالحق، القاضي بالعدل"},
    {"name": "العدل",       "meaning": "البالغ في العدل، لا يظلم مثقال ذرة"},
    {"name": "اللطيف",      "meaning": "الرفيق بعباده، العالم بدقائق الأمور"},
    {"name": "الخبير",      "meaning": "العالم بحقائق الأشياء ودقائقها الباطنة"},
    {"name": "الحليم",      "meaning": "الصفوح عن الزلّات، الذي لا يعجل بالعقوبة"},
    {"name": "العظيم",      "meaning": "الجامع لصفات الكمال، المتجاوز لكل حدّ وقدر"},
    {"name": "الغفور",      "meaning": "واسع المغفرة لذنوب العباد مهما عظمت"},
    {"name": "الشكور",      "meaning": "المُثيب على القليل من العمل بالكثير من الثواب"},
    {"name": "العليّ",      "meaning": "المتعالي فوق خلقه بذاته وقدره وقهره"},
    {"name": "الكبير",      "meaning": "الكبير في ذاته وصفاته، فوق كل شيء"},
    {"name": "الحفيظ",      "meaning": "الحافظ لعباده وأعمالهم وحافظ كل شيء"},
    {"name": "المقيت",      "meaning": "الحفيظ للأشياء والمقتدر على كل مخلوق"},
    {"name": "الحسيب",      "meaning": "الكافي عباده، المحاسب لهم على أعمالهم"},
    {"name": "الجليل",      "meaning": "العظيم الشأن المتصف بصفات الجلال والكمال"},
    {"name": "الكريم",      "meaning": "الجواد الوافر العطاء، المتكرّم على عباده"},
    {"name": "الرقيب",      "meaning": "المطّلع على كل شيء لا يخفى عليه خافية"},
    {"name": "المجيب",      "meaning": "الذي يجيب دعاء الداعي إذا دعاه"},
    {"name": "الواسع",      "meaning": "الواسع فضله ورحمته وعلمه لكل شيء"},
    {"name": "الحكيم",      "meaning": "المحكِم لأموره، الذي يضع كل شيء في موضعه"},
    {"name": "الودود",      "meaning": "المحبّ لعباده المؤمنين، الحبيب إليهم"},
    {"name": "المجيد",      "meaning": "العالي القدر، الواسع الإحسان والكرم"},
    {"name": "الباعث",      "meaning": "الذي يبعث الخلق يوم القيامة للحساب"},
    {"name": "الشهيد",      "meaning": "الحاضر مع خلقه لا يغيب عنه شيء"},
    {"name": "الحق",        "meaning": "الثابت الوجود الواجب الوجود، ضد الباطل"},
    {"name": "الوكيل",      "meaning": "المتولّي لأمور خلقه والكافي لمن توكّل عليه"},
    {"name": "القوي",       "meaning": "الكامل القوة الذي لا يعجزه شيء"},
    {"name": "المتين",      "meaning": "الشديد القوة الذي لا تنفد قوّته"},
    {"name": "الوليّ",      "meaning": "الناصر لأوليائه، المتولّي أمور المؤمنين"},
    {"name": "الحميد",      "meaning": "المستحق للحمد والثناء لذاته وأفعاله"},
    {"name": "المحصي",      "meaning": "المحيط علمه بعدد كل شيء لا يفوته شيء"},
    {"name": "المبدئ",      "meaning": "الذي أبدأ الخلق من غير مادة سابقة"},
    {"name": "المعيد",      "meaning": "الذي يُعيد الخلق بعد الموت للبعث والحساب"},
    {"name": "المحيي",      "meaning": "الذي يُحيي الأموات ويُوجد الحياة"},
    {"name": "المميت",      "meaning": "الذي يُميت الأحياء بأمره وقدرته"},
    {"name": "الحيّ",       "meaning": "الدائم الحياة الذي لا يموت ولا يفنى"},
    {"name": "القيوم",      "meaning": "القائم بنفسه المقيم لكل شيء"},
    {"name": "الواجد",      "meaning": "الغني الذي لا يفتقر إلى شيء"},
    {"name": "الماجد",      "meaning": "الواسع الكرم، العظيم الجود والإحسان"},
    {"name": "الواحد",      "meaning": "المنفرد بالوحدانية في ذاته وصفاته وأفعاله"},
    {"name": "الأحد",       "meaning": "المتوحِّد الذي لا شريك له ولا نظير"},
    {"name": "الصمد",       "meaning": "السيد الذي يُصمَد إليه في الحوائج والملمّات"},
    {"name": "القادر",      "meaning": "ذو القدرة التامة على كل شيء"},
    {"name": "المقتدر",     "meaning": "البالغ القدرة، لا يعجزه شيء في الأرض ولا السماء"},
    {"name": "المقدِّم",    "meaning": "الذي يقدِّم ما شاء من خلقه بحكمته"},
    {"name": "المؤخِّر",    "meaning": "الذي يؤخِّر ما شاء من خلقه بحكمته"},
    {"name": "الأول",       "meaning": "السابق لكل شيء، ليس قبله شيء"},
    {"name": "الآخر",       "meaning": "الباقي بعد فناء كل شيء"},
    {"name": "الظاهر",      "meaning": "الغالب على كل شيء، الظاهر بآياته وأدلته"},
    {"name": "الباطن",      "meaning": "المحتجب عن أبصار خلقه، العالم بالخفايا"},
    {"name": "الوالي",      "meaning": "المالك لجميع الأشياء، المتصرف في الكون"},
    {"name": "المتعالي",    "meaning": "المتنزِّه عن صفات النقص، المرتفع فوق كل شيء"},
    {"name": "البرّ",       "meaning": "الكثير الإحسان والعطاء لعباده"},
    {"name": "التوّاب",     "meaning": "الراجع بالقبول إلى التائبين، الكثير القبول للتوبة"},
    {"name": "المنتقم",     "meaning": "الشديد الانتقام ممن يستحق العذاب"},
    {"name": "العفوّ",      "meaning": "المتجاوز عن سيئات عباده، الكثير العفو"},
    {"name": "الرؤوف",      "meaning": "الرحيم بعباده رحمةً بالغةً فيها لين ورفق"},
    {"name": "مالك الملك",  "meaning": "المتصرف المطلق في ملكه، يُعطي ويمنع كيف يشاء"},
    {"name": "ذو الجلال والإكرام", "meaning": "ذو العظمة والكبرياء وأهل التعظيم والإكرام"},
    {"name": "المقسط",      "meaning": "العادل في حكمه، الذي لا يظلم أحداً"},
    {"name": "الجامع",      "meaning": "الذي يجمع الخلق ليوم لا ريب فيه"},
    {"name": "الغني",       "meaning": "المستغني عن كل شيء وكل شيء محتاج إليه"},
    {"name": "المغني",      "meaning": "الذي يُغني من يشاء من عباده برزقه"},
    {"name": "المانع",      "meaning": "الذي يمنع ما شاء لمن شاء بحكمته"},
    {"name": "الضارّ",      "meaning": "الذي يُوجِد الضرر لمن يستحقه بحكمته"},
    {"name": "النافع",      "meaning": "الذي يُوجِد النفع لمن يشاء بحكمته"},
    {"name": "النور",       "meaning": "الذي أنار السماوات والأرض والقلوب بهدايته"},
    {"name": "الهادي",      "meaning": "الذي يهدي عباده إلى معرفته وإلى الصراط المستقيم"},
    {"name": "البديع",      "meaning": "المبتدع للأشياء على غير مثال سابق"},
    {"name": "الباقي",      "meaning": "الدائم الذي لا ينتهي وجوده ولا يتغير"},
    {"name": "الوارث",      "meaning": "الذي يبقى بعد فناء الخلق وترث الأرض له"},
    {"name": "الرشيد",      "meaning": "الذي يُدبّر أمور خلقه على وفق الحكمة والصواب"},
    {"name": "الصبور",      "meaning": "الذي لا يُعاجَل بالعقوبة من عصاه وتاب"},
]


async def fetch_morning_adhkar() -> list[dict] | None:
    """جلب أذكار الصباح من API الإسلامي أو الإرجاع من قائمة مدمجة."""
    session = await get_session()
    try:
        url = "https://raw.githubusercontent.com/nawafalqari/azkar-api/56df51a5d3b809c078bcf498ece5e2c8d5c2e67f/azkar.json"
        async with session.get(url) as resp:
            if resp.status == 200:
                data = json.loads(await resp.text())
                for section in data:
                    if "صباح" in section.get("category", ""):
                        return section.get("array", [])[:7]
    except Exception as e:
        logger.debug(f"fetch_morning_adhkar fallback: {e}")
    return None


async def fetch_evening_adhkar() -> list[dict] | None:
    """جلب أذكار المساء من API الإسلامي."""
    session = await get_session()
    try:
        url = "https://raw.githubusercontent.com/nawafalqari/azkar-api/56df51a5d3b809c078bcf498ece5e2c8d5c2e67f/azkar.json"
        async with session.get(url) as resp:
            if resp.status == 200:
                data = json.loads(await resp.text())
                for section in data:
                    if "مساء" in section.get("category", ""):
                        return section.get("array", [])[:7]
    except Exception as e:
        logger.debug(f"fetch_evening_adhkar fallback: {e}")
    return None


async def fetch_quran_word_of_day() -> dict | None:
    """كلمة قرآنية يومية مع معناها."""
    day_of_year = datetime.now(TZ).timetuple().tm_yday
    short_surahs = [55, 56, 67, 69, 75, 76, 77, 78, 79, 80,
                    81, 82, 83, 84, 85, 86, 87, 88, 89, 90,
                    91, 92, 93, 94, 95, 96, 97, 98, 99, 100]
    surah = short_surahs[day_of_year % len(short_surahs)]
    max_ayah = AYAH_COUNTS.get(surah, 10)
    ayah = (day_of_year % max_ayah) + 1

    session = await get_session()
    try:
        text_url = (
            f"https://cdn.jsdelivr.net/gh/fawazahmed0/quran-api@1"
            f"/editions/ara-quranacademy/{surah}/{ayah}.json"
        )
        async with session.get(text_url) as resp:
            if resp.status != 200:
                return None
            data = json.loads(await resp.text())
        arabic_text = data.get("text", "")

        tafsir_text = ""
        try:
            tafsir_url = (
                f"https://cdn.jsdelivr.net/gh/fawazahmed0/quran-api@1"
                f"/editions/ara-jalaladdinalmah/{surah}/{ayah}.json"
            )
            async with session.get(tafsir_url) as tresp:
                if tresp.status == 200:
                    tdata = json.loads(await tresp.text())
                    tafsir_text = tdata.get("text", "")
        except Exception:
            pass

        return {
            "surah":   surah,
            "ayah":    ayah,
            "surah_name": SURAH_NAMES.get(surah, f"سورة {surah}"),
            "arabic":  arabic_text,
            "tafsir":  tafsir_text,
        }
    except Exception as e:
        logger.error(f"fetch_quran_word_of_day error: {e}")
        return None


def get_name_of_day() -> dict:
    """اسم الله الحسنى لهذا اليوم — يتغيّر كل يوم."""
    day_of_year = datetime.now(TZ).timetuple().tm_yday
    return ALLAH_NAMES[(day_of_year - 1) % len(ALLAH_NAMES)]


def get_good_deed_of_day() -> dict | None:
    """العمل الصالح اليومي من ملف good_deeds.json."""
    if not GOOD_DEEDS:
        return None
    day_of_year = datetime.now(TZ).timetuple().tm_yday
    return GOOD_DEEDS[(day_of_year - 1) % len(GOOD_DEEDS)]


# ══════════════════════════════════════════════════════════════════════════════
#  تنسيق الرسائل
# ══════════════════════════════════════════════════════════════════════════════

def format_quran_message(verse: dict) -> str:
    tafsir = ""
    if verse.get("tafsir"):
        t = verse["tafsir"]
        if len(t) > 400:
            t = t[:400].rsplit(" ", 1)[0] + "..."
        tafsir = f"\n\n📝 <b>تفسير الجلالين:</b>\n<i>{t}</i>"
    arabic_text = verse['arabic']
    return (
        f"📖 <b>آية من كتاب الله الكريم</b>\n"
        f"{SEP}\n\n"
        f"🕌 سورة <b>{verse['surah_name']}</b> — الآية <b>{verse['ayah_number']}</b>\n\n"
        f"✨ <b>{arabic_text}</b>"
        f"{tafsir}\n\n"
        f"{SEP}\n"
        f"🤲 <i>اللهم اجعل القرآن ربيع قلوبنا ونور صدورنا</i>"
    )


def format_hadith_message(hadith: dict) -> str:
    return (
        f"📜 <b>حديث نبوي شريف</b>\n"
        f"{SEP}\n\n"
        f"💬 {hadith['text']}\n\n"
        f"📚 <b>المصدر:</b> <i>{hadith['book_name']}</i> — رقم <b>{hadith['hadith_num']}</b>\n\n"
        f"{SEP}\n"
        f"🌹 <i>اللهم صلِّ وسلِّم وبارك على نبينا محمد ﷺ</i>"
    )


def format_story_message(story: dict) -> str:
    return (
        f"📚 <b>قصة إسلامية هادفة</b>\n"
        f"{SEP}\n\n"
        f"🌟 <b>{story['title']}</b>\n\n"
        f"{story['text']}\n\n"
        f"{SEP}\n"
        f"💡 <i>جعلنا الله وإياكم ممن يستمعون القول فيتبعون أحسنه</i>"
    )


def format_dua_message(dua: dict) -> str:
    return (
        f"🤲 <b>دعاء مأثور</b>\n"
        f"{SEP}\n\n"
        f"☀️ <b>{dua['title']}</b>\n\n"
        f"✨ <b>{dua['arabic']}</b>\n\n"
        f"📖 <b>المصدر:</b> <i>{dua['source']}</i>\n\n"
        f"{SEP}\n"
        f"💚 <i>اللهم تقبّل دعاءنا واستجب لنا</i>"
    )


def format_fact_message(fact: dict) -> str:
    return (
        f"💡 <b>معلومة إسلامية</b>\n"
        f"{SEP}\n\n"
        f"🔎 {fact['fact']}\n\n"
        f"{SEP}\n"
        f"🌸 <i>سبحان الله وبحمده، سبحان الله العظيم</i>"
    )


def format_morning_adhkar_message(adhkar: list[dict]) -> str:
    lines = [
        f"🌅 <b>أذكار الصباح</b>\n{SEP}\n",
        "☀️ <i>«من قال حين يصبح... كان في ذمة الله حتى يمسي»</i>\n",
    ]
    for i, zikr in enumerate(adhkar, 1):
        text = zikr.get("zikr", zikr.get("text", "")).strip()
        count = zikr.get("repeat", zikr.get("count", ""))
        if text:
            repeat_note = f"  <i>({count} مرة)</i>" if count and str(count) != "1" else ""
            lines.append(f"<b>{i}.</b> {text}{repeat_note}\n")
    lines.append(f"\n{SEP}\n🤲 <i>اللهم بك أصبحنا وبك أمسينا وبك نحيا وبك نموت وإليك النشور</i>")
    return "\n".join(lines)


MORNING_ADHKAR_FALLBACK = [
    {"zikr": "أَصْبَحْنَا وَأَصْبَحَ الْمُلْكُ لِلَّهِ، وَالْحَمْدُ لِلَّهِ، لَا إِلَهَ إِلَّا اللَّهُ وَحْدَهُ لَا شَرِيكَ لَهُ، لَهُ الْمُلْكُ وَلَهُ الْحَمْدُ وَهُوَ عَلَى كُلِّ شَيْءٍ قَدِيرٌ", "repeat": 1},
    {"zikr": "اللَّهُمَّ بِكَ أَصْبَحْنَا، وَبِكَ أَمْسَيْنَا، وَبِكَ نَحْيَا، وَبِكَ نَمُوتُ، وَإِلَيْكَ النُّشُورُ", "repeat": 1},
    {"zikr": "اللَّهُمَّ أَنْتَ رَبِّي لَا إِلَهَ إِلَّا أَنْتَ، خَلَقْتَنِي وَأَنَا عَبْدُكَ، وَأَنَا عَلَى عَهْدِكَ وَوَعْدِكَ مَا اسْتَطَعْتُ", "repeat": 1},
    {"zikr": "سُبْحَانَ اللَّهِ وَبِحَمْدِهِ", "repeat": 100},
    {"zikr": "أَعُوذُ بِكَلِمَاتِ اللَّهِ التَّامَّاتِ مِنْ شَرِّ مَا خَلَقَ", "repeat": 3},
    {"zikr": "بِسْمِ اللَّهِ الَّذِي لَا يَضُرُّ مَعَ اسْمِهِ شَيْءٌ فِي الْأَرْضِ وَلَا فِي السَّمَاءِ وَهُوَ السَّمِيعُ الْعَلِيمُ", "repeat": 3},
    {"zikr": "رَضِيتُ بِاللَّهِ رَبًّا، وَبِالْإِسْلَامِ دِينًا، وَبِمُحَمَّدٍ ﷺ نَبِيًّا وَرَسُولًا", "repeat": 3},
]

EVENING_ADHKAR_FALLBACK = [
    {"zikr": "أَمْسَيْنَا وَأَمْسَى الْمُلْكُ لِلَّهِ، وَالْحَمْدُ لِلَّهِ، لَا إِلَهَ إِلَّا اللَّهُ وَحْدَهُ لَا شَرِيكَ لَهُ، لَهُ الْمُلْكُ وَلَهُ الْحَمْدُ وَهُوَ عَلَى كُلِّ شَيْءٍ قَدِيرٌ", "repeat": 1},
    {"zikr": "اللَّهُمَّ بِكَ أَمْسَيْنَا، وَبِكَ أَصْبَحْنَا، وَبِكَ نَحْيَا، وَبِكَ نَمُوتُ، وَإِلَيْكَ الْمَصِيرُ", "repeat": 1},
    {"zikr": "اللَّهُمَّ إِنِّي أَمْسَيْتُ أُشْهِدُكَ وَأُشْهِدُ حَمَلَةَ عَرْشِكَ وَمَلَائِكَتَكَ وَجَمِيعَ خَلْقِكَ، أَنَّكَ أَنْتَ اللَّهُ لَا إِلَهَ إِلَّا أَنْتَ وَحْدَكَ لَا شَرِيكَ لَكَ", "repeat": 4},
    {"zikr": "سُبْحَانَ اللَّهِ وَبِحَمْدِهِ", "repeat": 100},
    {"zikr": "أَعُوذُ بِكَلِمَاتِ اللَّهِ التَّامَّاتِ مِنْ شَرِّ مَا خَلَقَ", "repeat": 3},
    {"zikr": "اللَّهُمَّ عَافِنِي فِي بَدَنِي، اللَّهُمَّ عَافِنِي فِي سَمْعِي، اللَّهُمَّ عَافِنِي فِي بَصَرِي، لَا إِلَهَ إِلَّا أَنْتَ", "repeat": 3},
    {"zikr": "حَسْبِيَ اللَّهُ لَا إِلَهَ إِلَّا هُوَ، عَلَيْهِ تَوَكَّلْتُ وَهُوَ رَبُّ الْعَرْشِ الْعَظِيمِ", "repeat": 7},
]


def format_evening_adhkar_message(adhkar: list[dict]) -> str:
    lines = [
        f"🌆 <b>أذكار المساء</b>\n{SEP}\n",
        "🌙 <i>«من قال حين يمسي... كان في ذمة الله حتى يصبح»</i>\n",
    ]
    for i, zikr in enumerate(adhkar, 1):
        text = zikr.get("zikr", zikr.get("text", "")).strip()
        count = zikr.get("repeat", zikr.get("count", ""))
        if text:
            repeat_note = f"  <i>({count} مرة)</i>" if count and str(count) != "1" else ""
            lines.append(f"<b>{i}.</b> {text}{repeat_note}\n")
    lines.append(f"\n{SEP}\n🤲 <i>اللهم بك أمسينا وبك أصبحنا وبك نحيا وبك نموت وإليك المصير</i>")
    return "\n".join(lines)


def format_tasbih_reminder_message() -> str:
    today = datetime.now(TZ)
    day_tasbihat = [
        ("سبحان الله",         "تنزيه الله عن كل نقص وعيب"),
        ("الحمد لله",          "شكر الله على كل نعمة ظاهرة وباطنة"),
        ("لا إله إلا الله",    "التوحيد الخالص والإقرار بأن لا رب سواه"),
        ("الله أكبر",          "تعظيم الله وأنه أكبر من كل شيء"),
        ("سبحان الله وبحمده",  "الجمع بين التنزيه والشكر في كلمة واحدة"),
        ("لا حول ولا قوة إلا بالله", "التبرؤ من الحول والقوة وإسنادها إلى الله"),
        ("سبحان الله العظيم",  "تنزيه الله مع وصفه بعظمة لا حدّ لها"),
    ]
    idx = (today.timetuple().tm_yday - 1) % len(day_tasbihat)
    tasbih, meaning = day_tasbihat[idx]
    return (
        f"📿 <b>تذكير يومي بالذكر</b>\n"
        f"{SEP}\n\n"
        f"✨ قل اليوم:\n\n"
        f"<b>« {tasbih} »</b>\n\n"
        f"📖 <i>المعنى: {meaning}</i>\n\n"
        f"💎 <i>أحبّ الكلام إلى الله أربع: سبحان الله، والحمد لله، ولا إله إلا الله، والله أكبر — صحيح مسلم</i>\n\n"
        f"{SEP}\n"
        f"🌸 <i>ردِّدها مئةً اليوم — لعلّ لسانك لا يجفّ من ذكر الله</i>"
    )


def format_quran_word_message(data: dict) -> str:
    tafsir = data.get("tafsir", "")
    if len(tafsir) > 500:
        tafsir = tafsir[:500].rsplit(" ", 1)[0] + "..."
    tafsir_block = f"\n\n📝 <b>التفسير:</b>\n<i>{tafsir}</i>" if tafsir else ""
    return (
        f"🔤 <b>كلمة قرآنية يومية</b>\n"
        f"{SEP}\n\n"
        f"📖 سورة <b>{data['surah_name']}</b> — الآية <b>{data['ayah']}</b>\n\n"
        f"✨ <b>{data['arabic']}</b>"
        f"{tafsir_block}\n\n"
        f"{SEP}\n"
        f"🌟 <i>تدبَّر القرآن — ﴿أَفَلَا يَتَدَبَّرُونَ الْقُرْآنَ﴾</i>"
    )


def format_name_of_day_message(name_data: dict) -> str:
    today_num = datetime.now(TZ).timetuple().tm_yday
    name_index = (today_num - 1) % len(ALLAH_NAMES) + 1
    return (
        f"🌟 <b>اسم الله الحسنى — اليوم</b>\n"
        f"{SEP}\n\n"
        f"✨ <b>« {name_data['name']} »</b>\n\n"
        f"📖 <b>المعنى:</b>\n<i>{name_data['meaning']}</i>\n\n"
        f"🔢 <i>الاسم {name_index} من 99</i>\n\n"
        f"{SEP}\n"
        f"🤲 <i>اللهم أنت {name_data['name']}، نسألك بهذا الاسم العظيم أن تتجلّى علينا برحمتك</i>"
    )


def format_good_deed_message(deed: dict) -> str:
    today = datetime.now(TZ).strftime("%d/%m/%Y")
    return (
        f"🌱 <b>عمل صالح يومي</b>\n"
        f"{SEP}\n\n"
        f"📅 <i>{today}</i>\n\n"
        f"💚 عملك الصالح لهذا اليوم:\n\n"
        f"<b>🌟 {deed['deed']}</b>\n\n"
        f"{SEP}\n"
        f"🤲 <i>«من عمل صالحاً من ذكر أو أنثى وهو مؤمن فلنحيينّه حياةً طيبة» — النحل 97</i>"
    )


# ══════════════════════════════════════════════════════════════════════════════
#  الإرسال
# ══════════════════════════════════════════════════════════════════════════════

async def send_to_chat(bot: Bot, chat_id: int | str, text: str) -> bool:
    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.HTML)
        return True
    except TelegramError as e:
        logger.error(f"فشل الإرسال إلى {chat_id}: {e}")
        return False


async def broadcast(bot: Bot, text: str, feature: str | None = None) -> None:
    """إرسال نص إلى كل الدردشات — مع مراعاة إعدادات كل دردشة."""
    chats = load_target_chats()
    for chat_id in chats:
        if feature and not cs.is_enabled(chat_id, feature):
            logger.debug(f"broadcast: تخطي {chat_id} — الميزة '{feature}' معطّلة")
            continue
        await send_to_chat(bot, chat_id, text)
        await asyncio.sleep(0.5)


# ══════════════════════════════════════════════════════════════════════════════
#  الرسائل الثابتة
# ══════════════════════════════════════════════════════════════════════════════

STARTUP_MESSAGE = (
    "🌙 <b>بسم الله الرحمن الرحيم</b>\n"
    "السلام عليكم ورحمة الله وبركاته 🌿\n\n"
    "✅ <b>البوت الإسلامي يعمل الآن بفضل الله</b>\n\n"
    "سيرسل إليكم بإذن الله:\n\n"
    "📖 آيات قرآنية كريمة\n"
    "📜 أحاديث نبوية شريفة\n"
    "🤲 أذكار وأدعية مأثورة\n"
    "🌅 أذكار الصباح عند الفجر\n"
    "🌆 أذكار المساء عند العصر\n"
    "📿 تذكير يومي بالتسبيح\n"
    "🔤 كلمة قرآنية يومية\n"
    "🌟 اسم الله الحسنى يومياً\n"
    "🌱 عمل صالح يومي\n"
    "📚 قصص إسلامية هادفة\n"
    "💡 معلومات إسلامية نافعة\n"
    "🖼️ صور وفيديوهات إسلامية\n"
    "🎬 تحميل فيديوهات تيك توك بدون علامة مائية\n"
    "🕌 تنبيهات أوقات الصلاة (الجزائر)\n"
    "🕌 تذكير صلاة الجمعة كل جمعة صباحاً\n"
    "🌙 تذكير صيام الاثنين والخميس\n"
    "📜 مقتطف يومي من السيرة النبوية\n"
    "🏆 مسابقات إسلامية كل ساعتين\n"
    "🔔 محتوى كل نصف ساعة — من 7 صباحاً حتى 11 مساءً\n\n"
    "أرسل /start لعرض قائمة جميع الأوامر\n\n"
    "﴿فَاذْكُرُونِي أَذْكُرْكُمْ﴾ 🌟"
)

HELP_MESSAGE = (
    "🕌 <b>البوت الإسلامي — قائمة الأوامر</b>\n"
    f"{SEP}\n\n"
    "📖 /aya — آية قرآنية عشوائية مع التفسير\n"
    "📜 /hadith — حديث نبوي شريف\n"
    "🤲 /dua — دعاء مأثور\n"
    "📚 /story — قصة إسلامية هادفة\n"
    "💡 /fact — معلومة إسلامية\n"
    "🕐 /adhan — أوقات الصلاة الآن (الجزائر)\n"
    "🌅 /morning — أذكار الصباح\n"
    "🌆 /evening — أذكار المساء\n"
    "📿 /tasbih — تذكير يومي بالتسبيح\n"
    "🔤 /word — كلمة قرآنية يومية\n"
    "🌟 /name — اسم الله الحسنى اليومي\n"
    "🌱 /deed — عمل صالح يومي\n"
    "📕 /books — مكتبة الكتب الإسلامية\n"
    "🚪 /leave — مغادرة الدردشة الحالية (للمشرفين)\n\n"
    f"{SEP}\n"
    "✨ <b>الميزات الجديدة</b>\n"
    "🎙️ /recitation — تلاوات قرآنية صوتية mp3\n"
    "🕌 /friday — ساعة الاستجابة يوم الجمعة\n"
    "📿 /tasbeeh — سبحة إلكترونية تفاعلية مع عداد\n"
    "📻 /radio — راديو القرآن المباشر 24 ساعة\n"
    "🏆 /quiz — مسابقة إسلامية عشوائية (في القنوات: تصويت للجميع)\n"
    "📊 /scores — لوحة الشرف والنقاط\n"
    "📜 /seerah — مقتطف يومي من السيرة النبوية\n\n"
    f"{SEP}\n"
    "🎵 <b>أوامر البث الصوتي</b> <i>(متاحة لجميع الأعضاء)</i>\n"
    "▶️ /play [رابط يوتيوب] — بث الصوت في المكالمة\n"
    "⏹️ /stop — إيقاف البث ومغادرة المكالمة\n"
    "⏸️ /pause — تعليق البث مؤقتاً\n"
    "▶️ /resume — استئناف البث\n"
    "🎶 /nowplaying — عرض ما يُبَث حالياً\n"
    "🎬 /tiktok [رابط] — تحميل فيديو تيك توك بدون علامة مائية\n\n"
    f"{SEP}\n"
    "🔧 <b>أوامر المشرفين</b>\n"
    "📢 /broadcast — بث رسالة مخصصة لجميع الدردشات\n"
    "⚙️ /settings — إعدادات البوت لهذه الدردشة\n"
    "🖼️ /sendimage — نشر صورة/فيديو إسلامية فوراً\n"
    "🖼️ /deletemedia — حذف صورة أو فيديو من المكتبة\n"
    "📂 /media — تصفح الميديا المخزنة (صور + فيديوهات)\n\n"
    f"{SEP}\n"
    "🛡️ <b>أوامر المدير الرئيسي</b> <i>(المعرف في config.py)</i>\n"
    "📁 /files — مدير ملفات البوت\n"
    "📥 /getfile — تنزيل ملف من مجلد البوت\n"
    "🗑️ /delfile — حذف ملف مع تأكيد\n"
    "📁 /mkdir — إنشاء مجلد جديد\n"
    "🔄 /reload — إعادة تحميل موديول بدون إعادة تشغيل\n"
    "🔁 /restart — إعادة تشغيل البوت\n"
    "📦 /update — تحديث yt-dlp + إعادة تشغيل\n"
    "📋 /logs [عدد] — عرض آخر سطور السجل\n"
    "💻 /shell — تنفيذ أمر على السيرفر\n\n"
    f"{SEP}\n"
    "🔔 <i>يرسل البوت محتوى إسلامياً كل 30 دقيقة تلقائياً</i>\n"
    "🏆 <i>مسابقات إسلامية كل ساعتين مع نظام نقاط</i>\n"
    "💚 جزاكم الله خيراً"
)


# ══════════════════════════════════════════════════════════════════════════════
#  ميزة /books — مكتبة الكتب الإسلامية
# ══════════════════════════════════════════════════════════════════════════════

def get_books() -> list[Path]:
    """يعيد قائمة مرتبة بجميع ملفات PDF في مجلد books/."""
    return sorted(BOOKS_DIR.glob("*.pdf"), key=lambda p: p.stem)


def clean_book_name(stem: str) -> str:
    """
    يحوّل اسم الملف إلى عنوان قابل للقراءة:
      - يزيل الأرقام والشرطات السفلية من البداية (مثل 02_03_)
      - يستبدل _ و - بمسافات
    """
    import re
    name = re.sub(r"^[\d_\-]+", "", stem)   # ازالة بادئة رقمية
    name = name.replace("_", " ").replace("-", " ")
    return name.strip() or stem


def make_books_keyboard(page: int = 0) -> tuple[InlineKeyboardMarkup, int, int]:
    """
    يبني لوحة مفاتيح inline للكتب مع ترقيم الصفحات.
    يعيد (keyboard, current_page, total_pages).
    """
    books = get_books()
    per_page = 8
    total_pages = max(1, -(-len(books) // per_page))  # ceiling division
    page = max(0, min(page, total_pages - 1))
    start = page * per_page
    chunk = books[start: start + per_page]

    buttons = []
    for i, book_path in enumerate(chunk):
        display = clean_book_name(book_path.stem)
        global_idx = start + i
        buttons.append([InlineKeyboardButton(
            f"📕 {display}",
            callback_data=f"book|{global_idx}"
        )])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ السابق", callback_data=f"books_page|{page-1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("التالي ▶️", callback_data=f"books_page|{page+1}"))
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton("❌ إغلاق", callback_data="books_close")])

    return InlineKeyboardMarkup(buttons), page, total_pages


def make_books_header(page: int, total_pages: int, total_books: int) -> str:
    return (
        f"📚 <b>المكتبة الإسلامية</b>\n"
        f"{SEP}\n\n"
        f"🗂️ إجمالي الكتب: <b>{total_books}</b>\n"
        f"📄 الصفحة <b>{page + 1}</b> من <b>{total_pages}</b>\n\n"
        f"👇 <i>اضغط على اسم الكتاب لتحميله</i>"
    )


async def cmd_books(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    books = get_books()
    if not books:
        await update.effective_message.reply_text(
            "📚 <b>المكتبة فارغة حالياً</b>\n\n"
            "⏳ <i>سيتم إضافة الكتب قريباً بإذن الله</i>",
            parse_mode=ParseMode.HTML,
        )
        return

    keyboard, page, total_pages = make_books_keyboard(0)
    await update.effective_message.reply_text(
        make_books_header(page, total_pages, len(books)),
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard,
    )


async def callback_books(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "books_close":
        try:
            await query.message.delete()
        except Exception:
            await query.edit_message_reply_markup(reply_markup=None)
        return

    if data.startswith("books_page|"):
        page = int(data.split("|")[1])
        books = get_books()
        keyboard, page, total_pages = make_books_keyboard(page)
        await query.edit_message_text(
            make_books_header(page, total_pages, len(books)),
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
        )
        return

    if data.startswith("book|"):
        idx = int(data.split("|")[1])
        books = get_books()
        if idx >= len(books):
            await query.answer("⚠️ الكتاب غير موجود، ربما تم حذفه.", show_alert=True)
            return

        book_path = books[idx]
        display   = clean_book_name(book_path.stem)
        size_mb   = book_path.stat().st_size / (1024 * 1024)

        caption = (
            f"📕 <b>{display}</b>\n"
            f"{SEP}\n\n"
            f"📂 <i>الحجم: {size_mb:.1f} MB</i>\n\n"
            f"بارك الله فيك وجعله في ميزان حسناتك 🤲"
        )

        await query.answer("📤 جاري إرسال الكتاب...")

        try:
            with open(book_path, "rb") as f:
                await query.message.reply_document(
                    document=f,
                    filename=book_path.name,
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                )
        except TelegramError as e:
            logger.error(f"فشل إرسال الكتاب {book_path.name}: {e}")
            await query.message.reply_text(
                f"⚠️ تعذر إرسال الكتاب، حاول مرة أخرى.\n<code>{e}</code>",
                parse_mode=ParseMode.HTML,
            )


# ══════════════════════════════════════════════════════════════════════════════
#  معالجات الأوامر
# ══════════════════════════════════════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(HELP_MESSAGE, parse_mode=ParseMode.HTML)


async def cmd_aya(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.effective_message.reply_text("📖 جاري جلب آية كريمة...")
    verse = await fetch_quran_verse()
    if verse:
        await msg.edit_text(format_quran_message(verse), parse_mode=ParseMode.HTML)
    else:
        await msg.edit_text("⚠️ تعذر جلب الآية، حاول مرة أخرى.")


async def cmd_hadith(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.effective_message.reply_text("📜 جاري جلب حديث شريف...")
    hadith = await fetch_hadith()
    if hadith:
        await msg.edit_text(format_hadith_message(hadith), parse_mode=ParseMode.HTML)
    else:
        await msg.edit_text("⚠️ تعذر جلب الحديث، حاول مرة أخرى.")


async def cmd_dua(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if DUAS:
        dua = random.choice(DUAS)
        await update.effective_message.reply_text(format_dua_message(dua), parse_mode=ParseMode.HTML)
    else:
        await update.effective_message.reply_text("لا توجد أدعية متاحة.")


async def cmd_story(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if STORIES:
        story = random.choice(STORIES)
        await update.effective_message.reply_text(format_story_message(story), parse_mode=ParseMode.HTML)
    else:
        await update.effective_message.reply_text("لا توجد قصص متاحة.")


async def cmd_fact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if FACTS:
        fact = random.choice(FACTS)
        await update.effective_message.reply_text(format_fact_message(fact), parse_mode=ParseMode.HTML)
    else:
        await update.effective_message.reply_text("لا توجد معلومات متاحة.")


async def cmd_adhan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.effective_message.reply_text("🕐 جاري جلب أوقات الصلاة...")
    timings = await fetch_prayer_times()
    if timings:
        prayer_ar = {
            "Fajr":    "🌅 الفجر",
            "Dhuhr":   "☀️ الظهر",
            "Asr":     "🌤️ العصر",
            "Maghrib": "🌇 المغرب",
            "Isha":    "🌙 العشاء",
        }
        today = datetime.now(TZ).strftime("%d/%m/%Y")
        lines = [f"🕌 <b>أوقات الصلاة — الجزائر</b>\n📅 {today}\n{SEP}\n"]
        for p, t in timings.items():
            name = prayer_ar.get(p, p)
            lines.append(f"{name}: <b>{t}</b>")
        lines.append(f"\n{SEP}\n🤲 <i>اللهم اجعلنا من المحافظين على الصلاة</i>")
        await msg.edit_text("\n".join(lines), parse_mode=ParseMode.HTML)
    else:
        await msg.edit_text("⚠️ تعذر جلب أوقات الصلاة، حاول مرة أخرى.")


async def cmd_morning_adhkar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.effective_message.reply_text("🌅 جاري جلب أذكار الصباح...")
    adhkar = await fetch_morning_adhkar()
    if not adhkar:
        adhkar = MORNING_ADHKAR_FALLBACK
    await msg.edit_text(format_morning_adhkar_message(adhkar), parse_mode=ParseMode.HTML)


async def cmd_evening_adhkar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.effective_message.reply_text("🌆 جاري جلب أذكار المساء...")
    adhkar = await fetch_evening_adhkar()
    if not adhkar:
        adhkar = EVENING_ADHKAR_FALLBACK
    await msg.edit_text(format_evening_adhkar_message(adhkar), parse_mode=ParseMode.HTML)


async def cmd_tasbih(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(format_tasbih_reminder_message(), parse_mode=ParseMode.HTML)


async def cmd_word_of_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.effective_message.reply_text("🔤 جاري جلب الكلمة القرآنية اليومية...")
    data = await fetch_quran_word_of_day()
    if data:
        await msg.edit_text(format_quran_word_message(data), parse_mode=ParseMode.HTML)
    else:
        await msg.edit_text("⚠️ تعذر جلب الكلمة القرآنية، حاول مرة أخرى.")


async def cmd_name_of_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    name_data = get_name_of_day()
    await update.effective_message.reply_text(format_name_of_day_message(name_data), parse_mode=ParseMode.HTML)


async def cmd_good_deed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    deed = get_good_deed_of_day()
    if deed:
        await update.effective_message.reply_text(format_good_deed_message(deed), parse_mode=ParseMode.HTML)
    else:
        await update.effective_message.reply_text("⚠️ تعذر جلب العمل الصالح، تأكد من وجود ملف good_deeds.json")


# ── أمر /leave ────────────────────────────────────────────────────────────────
async def cmd_leave(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """يغادر البوت المجموعة/القناة الحالية (للمشرفين)."""
    chat = update.effective_chat
    user = update.effective_user

    if chat.type in ["group", "supergroup"]:
        member = await chat.get_member(user.id)
        if not member.can_restrict_members:
            await update.effective_message.reply_text("⚠️ تحتاج إلى صلاحية 'طرد الأعضاء' لاستخدام هذا الأمر.")
            return
    elif chat.type == "channel":
        try:
            admin = await chat.get_member(user.id)
            if admin.status not in ["administrator", "creator"]:
                await update.effective_message.reply_text("⚠️ هذا الأمر متاح فقط لمشرفي القناة.")
                return
        except Exception:
            await update.effective_message.reply_text("⚠️ لا يمكن التحقق من صلاحياتك.")
            return

    remove_target_chat(chat.id)
    await update.effective_message.reply_text("👋 وداعاً! تمت مغادرة الدردشة وإيقاف البث التلقائي.")
    try:
        await chat.leave()
    except Exception as e:
        logger.error(f"خطأ في المغادرة: {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  أمر /broadcast — إرسال رسالة مخصصة لجميع الدردشات (للمشرف فقط)
#  يدعم الرسائل الطويلة جداً بالتقسيم الذكي على الفقرات
# ══════════════════════════════════════════════════════════════════════════════

# ضع معرف حسابك هنا للحماية (يمكنك معرفته بإرسال /start للبوت @userinfobot)
# ملاحظة: مصدر الحقيقة هو config.BROADCAST_ADMIN_IDS — لا تعلن قائمة محلية هنا
# كي لا تتجاوزها (القائمة الفارغة كانت تسمح لأي شخص باستخدام /broadcast).

TG_LIMIT = 4096   # الحد الأقصى لطول رسالة تيليغرام


def split_message(text: str, limit: int = TG_LIMIT) -> list[str]:
    """
    يقسّم النص الطويل إلى أجزاء لا يتجاوز كل منها limit حرفاً.
    يقسّم على حدود الفقرات (سطر فارغ) قدر الإمكان،
    وعند الضرورة يقسّم على آخر نقطة/نهاية جملة قبل الحد،
    وكآخر ملاذ يقطع على المسافة.
    يضيف مؤشر الجزء (١/٣) تلقائياً إذا كان أكثر من جزء.
    """
    if len(text) <= limit:
        return [text]

    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        candidate = (current + "\n\n" + para).strip() if current else para

        if len(candidate) <= limit:
            current = candidate
        else:
            # الفقرة الحالية تجاوزت الحد مع الجزء المتراكم
            if current:
                chunks.append(current)
                current = ""

            # إذا كانت الفقرة وحدها أطول من الحد، نقسمها على الجمل
            if len(para) > limit:
                words = para.split(" ")
                line = ""
                for word in words:
                    test = (line + " " + word).strip()
                    if len(test) <= limit:
                        line = test
                    else:
                        if line:
                            chunks.append(line)
                        line = word
                if line:
                    current = line
            else:
                current = para

    if current:
        chunks.append(current)

    # أضف مؤشر الجزء إذا كان هناك أكثر من جزء
    if len(chunks) > 1:
        total = len(chunks)
        # ترقيم بالأرقام العربية
        arabic_nums = ["١","٢","٣","٤","٥","٦","٧","٨","٩","١٠",
                       "١١","١٢","١٣","١٤","١٥","١٦","١٧","١٨","١٩","٢٠"]
        def ar(n): return arabic_nums[n-1] if n <= len(arabic_nums) else str(n)
        chunks = [f"({ar(i+1)}/{ar(total)})\n\n{chunk}" for i, chunk in enumerate(chunks)]

    return chunks


async def broadcast_long(bot: Bot, text: str) -> None:
    """
    نسخة محسّنة من broadcast() تدعم الرسائل الطويلة.
    تستبدل broadcast() العادية للرسائل اليدوية.
    """
    chats = load_target_chats()
    parts = split_message(text)
    for chat_id in chats:
        for part in parts:
            await send_to_chat(bot, chat_id, part)
            if len(parts) > 1:
                await asyncio.sleep(0.3)   # تأخير بين الأجزاء
        await asyncio.sleep(0.5)   # تأخير بين الدردشات


async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /broadcast <نص الرسالة>
    يرسل رسالة HTML مخصصة لجميع الدردشات المحفوظة في channels.json.
    يقسّم الرسائل الطويلة تلقائياً على الفقرات مع مؤشر (١/٣).
    متاح فقط للمعرفات الموجودة في BROADCAST_ADMIN_IDS.
    """
    user = update.effective_user
    if config.BROADCAST_ADMIN_IDS and user.id not in config.BROADCAST_ADMIN_IDS:
        await update.effective_message.reply_text("⛔ هذا الأمر متاح للمشرف فقط.")
        return

    if not context.args:
        await update.effective_message.reply_text(
            "📢 <b>استخدام الأمر:</b>\n"
            "<code>/broadcast نص الرسالة هنا</code>\n\n"
            "✂️ <b>الرسائل الطويلة</b> تُقسَّم تلقائياً على الفقرات مع مؤشر (١/٣)\n"
            f"📏 حد تيليغرام: <b>{TG_LIMIT}</b> حرف لكل رسالة\n"
            f"📡 عدد الدردشات الحالي: <b>{len(load_target_chats())}</b>",
            parse_mode=ParseMode.HTML,
        )
        return

    text = " ".join(context.args)
    chats = load_target_chats()
    if not chats:
        await update.effective_message.reply_text("⚠️ لا توجد دردشات مسجّلة بعد.")
        return

    parts = split_message(text)
    parts_info = f" ({len(parts)} أجزاء)" if len(parts) > 1 else ""
    status_msg = await update.effective_message.reply_text(
        f"📤 جاري الإرسال إلى {len(chats)} دردشة{parts_info}..."
    )

    success, failed = 0, 0
    for chat_id in chats:
        chat_ok = True
        for part in parts:
            ok = await send_to_chat(update.get_bot(), chat_id, part)
            if not ok:
                chat_ok = False
            if len(parts) > 1:
                await asyncio.sleep(0.3)
        if chat_ok:
            success += 1
        else:
            failed += 1
        await asyncio.sleep(0.4)

    await status_msg.edit_text(
        f"✅ <b>اكتمل البث</b>\n\n"
        f"📨 تم الإرسال: <b>{success}</b> دردشة\n"
        f"❌ فشل: <b>{failed}</b>\n"
        f"✂️ الأجزاء لكل دردشة: <b>{len(parts)}</b>\n"
        f"📊 الإجمالي: <b>{len(chats)}</b>",
        parse_mode=ParseMode.HTML,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  معالج تتبع الدردشات (ديناميكي) مع زر إضافة الحساب المساعد
# ══════════════════════════════════════════════════════════════════════════════
async def track_chat_membership(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يتتبع انضمام البوت إلى مجموعات/قنوات أو إزالته منها."""
    if not update.my_chat_member:
        return
    old = update.my_chat_member.old_chat_member
    new = update.my_chat_member.new_chat_member
    if old.status == new.status:
        return
    chat = update.effective_chat
    if not chat:
        return
    chat_id = chat.id
    if chat.type not in ["group", "supergroup", "channel"]:
        return

    if new.status in ["member", "administrator"] and old.status in ["left", "kicked"]:
        add_target_chat(chat_id)
        logger.info(f"انضم البوت إلى {chat.type} : {chat.title or chat_id}")

        try:
            await chat.send_message(
                text=(
                    "🌙 <b>تم تفعيل البوت الإسلامي في هذه الدردشة</b> ✅\n\n"
                    "سيرسل البوت المحتوى الإسلامي تلقائياً كل 30 دقيقة.\n\n"
                    "🎵 <b>لبث الصوت في المكالمة:</b>\n"
                    "1️⃣ ابدأ <b>Voice Chat</b> أو <b>Livestream</b> من إعدادات المجموعة\n"
                    "2️⃣ أرسل: <code>/play https://youtu.be/...</code>\n"
                    "↩️ البوت سينضم للمكالمة تلقائياً ويبدأ البث\n\n"
                    "أرسل /start لعرض قائمة الأوامر المتاحة."
                ),
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            logger.warning(f"لم نستطع إرسال رسالة الترحيب إلى {chat_id}: {e}")

    elif new.status in ["left", "kicked"] and old.status in ["member", "administrator"]:
        remove_target_chat(chat_id)
        logger.info(f"غادر البوت {chat.type} : {chat.title or chat_id}")


# ══════════════════════════════════════════════════════════════════════════════
#  وظائف البث التلقائي كل 30 دقيقة
# ══════════════════════════════════════════════════════════════════════════════

async def job_morning_adhkar(bot: Bot) -> None:
    logger.info("📿 إرسال أذكار الصباح...")
    adhkar = await fetch_morning_adhkar()
    if not adhkar:
        adhkar = MORNING_ADHKAR_FALLBACK
    await broadcast(bot, format_morning_adhkar_message(adhkar), feature="morning_adhkar")


async def job_evening_adhkar(bot: Bot) -> None:
    logger.info("🌙 إرسال أذكار المساء...")
    adhkar = await fetch_evening_adhkar()
    if not adhkar:
        adhkar = EVENING_ADHKAR_FALLBACK
    await broadcast(bot, format_evening_adhkar_message(adhkar), feature="evening_adhkar")


async def job_tasbih_reminder(bot: Bot) -> None:
    logger.info("📿 إرسال تذكير التسبيح...")
    await broadcast(bot, format_tasbih_reminder_message(), feature="tasbih")


async def job_word_of_day(bot: Bot) -> None:
    logger.info("🔤 إرسال الكلمة القرآنية اليومية...")
    data = await fetch_quran_word_of_day()
    if data:
        await broadcast(bot, format_quran_word_message(data), feature="word_of_day")


async def job_name_of_day(bot: Bot) -> None:
    logger.info("🌟 إرسال اسم الله الحسنى اليومي...")
    name_data = get_name_of_day()
    await broadcast(bot, format_name_of_day_message(name_data), feature="name_of_day")


async def job_good_deed(bot: Bot) -> None:
    logger.info("🌱 إرسال العمل الصالح اليومي...")
    deed = get_good_deed_of_day()
    if deed:
        await broadcast(bot, format_good_deed_message(deed), feature="good_deed")


async def job_random_content(bot: Bot) -> None:
    now = datetime.now(TZ)
    if now.hour < config.CONTENT_START_HOUR or now.hour >= config.CONTENT_END_HOUR:
        logger.debug(
            f"job_random_content: خارج نافذة البث "
            f"({config.CONTENT_START_HOUR}:00–{config.CONTENT_END_HOUR}:00) — "
            f"الوقت الحالي {now.hour}:{now.minute:02d}"
        )
        return

    all_chats = load_target_chats()

    # ── بناء قائمة الأنواع المتاحة لكل دردشة على حدة ────────────────────────
    # نختار نوعاً عشوائياً واحداً للدورة، ثم نرسله فقط للدردشات التي فعّلته
    # ملاحظة: الصور/الفيديوهات ("image") لم تعد ضمن هذا النظام العشوائي —
    # أصبحت تُنشر عبر نظام منفصل (مرتين يومياً بأوقات عشوائية)، راجع
    # schedule_daily_media / job_daily_media أدناه.
    content_type = random.choices(
        ["quran", "hadith", "dua", "story", "fact"],
        weights=[35, 23, 16, 13, 13],
        k=1
    )[0]

    # خريطة: نوع المحتوى → مفتاح الميزة في chat_settings
    CONTENT_FEATURE_MAP = {
        "quran":  "auto_quran",
        "hadith": "auto_hadith",
        "dua":    "auto_dua",
        "story":  "auto_story",
        "fact":   "auto_fact",
    }
    feature_key = CONTENT_FEATURE_MAP.get(content_type, content_type)
    logger.info(f"job_random_content: النوع المختار → {content_type}")

    # فلترة الدردشات التي فعّلت هذا النوع
    target_chats = [c for c in all_chats if cs.is_enabled(c, feature_key)]
    if not target_chats:
        logger.debug(f"job_random_content: لا توجد دردشات فعّلت '{feature_key}' — تخطي")
        return

    sent = False
    try:
        if content_type == "quran":
            verse = await fetch_quran_verse()
            if verse:
                for chat_id in target_chats:
                    await send_to_chat(bot, chat_id, format_quran_message(verse))
                    await asyncio.sleep(0.5)
                sent = True
            else:
                logger.warning("fetch_quran_verse أعاد None — سيُجرَّب الحديث بديلاً")

        if not sent and content_type in ("quran", "hadith"):
            hadith_chats = [c for c in all_chats if cs.is_enabled(c, "auto_hadith")]
            if hadith_chats:
                hadith = await fetch_hadith()
                if hadith:
                    for chat_id in hadith_chats:
                        await send_to_chat(bot, chat_id, format_hadith_message(hadith))
                        await asyncio.sleep(0.5)
                    sent = True

        if not sent and content_type == "dua":
            if DUAS:
                for chat_id in target_chats:
                    await send_to_chat(bot, chat_id, format_dua_message(random.choice(DUAS)))
                    await asyncio.sleep(0.5)
                sent = True

        if not sent and content_type == "story":
            if STORIES:
                for chat_id in target_chats:
                    await send_to_chat(bot, chat_id, format_story_message(random.choice(STORIES)))
                    await asyncio.sleep(0.5)
                sent = True

        if not sent and content_type == "fact":
            if FACTS:
                for chat_id in target_chats:
                    await send_to_chat(bot, chat_id, format_fact_message(random.choice(FACTS)))
                    await asyncio.sleep(0.5)
                sent = True

        # ── Fallback نهائي ───────────────────────────────────────────────────
        if not sent:
            logger.warning("كل مصادر API فشلت — استخدام محتوى محلي")
            fallback_chats = [c for c in all_chats if cs.is_enabled(c, "auto_dua")]
            if DUAS and fallback_chats:
                for chat_id in fallback_chats:
                    await send_to_chat(bot, chat_id, format_dua_message(random.choice(DUAS)))
                    await asyncio.sleep(0.5)
                sent = True
            else:
                fallback_chats = [c for c in all_chats if cs.is_enabled(c, "auto_fact")]
                if FACTS and fallback_chats:
                    for chat_id in fallback_chats:
                        await send_to_chat(bot, chat_id, format_fact_message(random.choice(FACTS)))
                        await asyncio.sleep(0.5)
                    sent = True

        if sent:
            logger.info(f"job_random_content: تم الإرسال (النوع: {content_type}, دردشات: {len(target_chats)})")

    except Exception as e:
        logger.error(f"خطأ في job_random_content: {e}", exc_info=True)


# ══════════════════════════════════════════════════════════════════════════════
#  نشر الصور/الفيديوهات — نظام مستقل (مرتين يومياً، أوقات عشوائية)
# ══════════════════════════════════════════════════════════════════════════════
# هذا النظام منفصل تماماً عن job_random_content (نظام الاختيار العشوائي
# كل 30 دقيقة). الصور والفيديوهات تُنشر فقط مرتين في اليوم، في وقتين
# عشوائيين يُعاد اختيارهما كل يوم ضمن نافذة البث (CONTENT_START_HOUR
# إلى CONTENT_END_HOUR)، تماماً كما تُجدوَل أوقات الأذان.

DAILY_MEDIA_BROADCASTS_PER_DAY = 2


async def job_daily_media(bot: Bot) -> None:
    """ينشر صورة أو فيديو عشوائي واحد لجميع الدردشات المفعّلة لـ auto_image."""
    all_chats = load_target_chats()
    target_chats = [c for c in all_chats if cs.is_enabled(c, "auto_image")]
    if not target_chats:
        logger.debug("job_daily_media: لا توجد دردشات فعّلت 'auto_image' — تخطي")
        return

    try:
        from image_broadcast import broadcast_image
        ok = await broadcast_image(
            bot=bot,
            chats=target_chats,
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_name=config.SESSION_NAME,
        )
        if ok:
            logger.info(f"job_daily_media: تم نشر صورة/فيديو (دردشات: {len(target_chats)})")
        else:
            logger.warning("job_daily_media: broadcast_image فشل — لا توجد ميديا متاحة")
    except ImportError:
        logger.warning("job_daily_media: image_broadcast غير موجود — تخطي")
    except Exception as e:
        logger.error(f"خطأ في job_daily_media: {e}", exc_info=True)


async def schedule_daily_media(scheduler: AsyncIOScheduler, bot: Bot) -> None:
    """
    يختار عشوائياً وقتين مختلفين خلال اليوم (ضمن نافذة البث) ويجدول
    job_daily_media عليهما. يُستدعى مرة عند الإقلاع، ثم يُعاد استدعاؤه
    تلقائياً كل يوم الساعة 00:02 لاختيار وقتين جديدين.
    """
    now = datetime.now(TZ)
    date_str = now.strftime("%Y%m%d")

    start_h = config.CONTENT_START_HOUR
    end_h   = config.CONTENT_END_HOUR
    window_minutes = max((end_h - start_h) * 60, 1)

    # نختار نقطتين عشوائيتين ضمن النافذة مع إبعاد لا يقل عن ربع النافذة
    # بينهما حتى لا يقعا متقاربتين جداً بالصدفة.
    min_gap = max(window_minutes // 4, 30)
    chosen_offsets: list[int] = []
    attempts = 0
    while len(chosen_offsets) < DAILY_MEDIA_BROADCASTS_PER_DAY and attempts < 200:
        attempts += 1
        offset = random.randint(0, window_minutes - 1)
        if all(abs(offset - existing) >= min_gap for existing in chosen_offsets):
            chosen_offsets.append(offset)
    # احتياط: إن لم نجد عدد كافٍ بالشرط أعلاه (نافذة ضيقة جداً)، نكمل عشوائياً بلا شرط
    while len(chosen_offsets) < DAILY_MEDIA_BROADCASTS_PER_DAY:
        chosen_offsets.append(random.randint(0, window_minutes - 1))

    for i, offset in enumerate(chosen_offsets):
        fire_dt = now.replace(hour=start_h, minute=0, second=0, microsecond=0) + timedelta(minutes=offset)
        if fire_dt <= now:
            # الوقت المختار عشوائياً قد يقع في الماضي (مثلاً إعادة الجدولة
            # منتصف اليوم) — نؤجله لحظياً (+1 دقيقة) كي لا يُفقد إرسال اليوم.
            fire_dt = now + timedelta(minutes=1)

        job_id = f"daily_media_{i}_{date_str}"
        scheduler.add_job(
            job_daily_media,
            trigger=DateTrigger(run_date=fire_dt, timezone=TZ),
            args=[bot],
            id=job_id,
            name=f"نشر صورة/فيديو عشوائي #{i+1}",
            replace_existing=True,
            misfire_grace_time=1800,
        )
        logger.info(f"جدول: نشر صورة/فيديو #{i+1} الساعة {fire_dt.strftime('%H:%M')}")


async def job_quiz(bot: Bot) -> None:
    """إرسال مسابقة إسلامية كل ساعتين للقنوات فقط."""
    now = datetime.now(TZ)
    if now.hour < config.CONTENT_START_HOUR or now.hour >= config.CONTENT_END_HOUR:
        return

    all_chats = load_target_chats()
    channel_chats = []
    for chat_id in all_chats:
        if not cs.is_enabled(chat_id, "quiz"):
            continue
        try:
            chat_info = await bot.get_chat(chat_id)
            if chat_info.type == "channel":
                channel_chats.append(chat_id)
        except Exception:
            pass

    if not channel_chats:
        logger.debug("job_quiz: لا توجد قنوات مفعّلة للمسابقة")
        return

    for chat_id in channel_chats:
        try:
            await new_features.send_quiz_to_chat(bot, chat_id)
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"job_quiz: فشل إرسال المسابقة إلى {chat_id}: {e}")

    logger.info(f"job_quiz: تم إرسال المسابقة إلى {len(channel_chats)} قناة")


async def job_adhan(bot: Bot, prayer_name: str) -> None:
    logger.info(f"اذان: {prayer_name}")
    if not isinstance(ADHAN_MSGS, dict):
        return

    msg_data = ADHAN_MSGS.get(prayer_name)
    if not msg_data:
        return

    # خريطة أسماء صور الأذان
    prayer_images = {
        "Fajr":    "adhan/fajr.png",
        "Dhuhr":   "adhan/dhuhr.png",
        "Asr":     "adhan/asr.png",
        "Maghrib": "adhan/maghrib.png",
        "Isha":    "adhan/isha.png",
    }

    caption = msg_data["message"]
    image_path = BASE_DIR / prayer_images.get(prayer_name, "")
    chats = [c for c in load_target_chats() if cs.is_enabled(c, "adhan")]

    for chat_id in chats:
        try:
            if image_path.exists():
                with open(image_path, "rb") as img:
                    await bot.send_photo(
                        chat_id=chat_id,
                        photo=img,
                        caption=caption,
                        parse_mode=ParseMode.HTML,
                    )
            else:
                # إذا لم توجد الصورة — أرسل النص فقط
                await bot.send_message(
                    chat_id=chat_id,
                    text=caption,
                    parse_mode=ParseMode.HTML,
                )
        except TelegramError as e:
            logger.error(f"فشل إرسال أذان {prayer_name} إلى {chat_id}: {e}")
        await asyncio.sleep(0.5)


async def schedule_adhan(scheduler: AsyncIOScheduler, bot: Bot) -> None:
    logger.info("جلب أوقات الصلاة لليوم...")
    timings = await fetch_prayer_times()
    if not timings:
        return

    now = datetime.now(TZ)
    date_str = now.strftime('%Y%m%d')

    for prayer, time_str in timings.items():
        time_clean = time_str.split(" ")[0]
        h, m = map(int, time_clean.split(":"))
        fire_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if fire_dt <= now:
            continue

        job_id = f"adhan_{prayer}_{date_str}"
        scheduler.add_job(
            job_adhan,
            trigger=DateTrigger(run_date=fire_dt, timezone=TZ),
            args=[bot, prayer],
            id=job_id,
            name=f"اذان {prayer} {time_str}",
            replace_existing=True,
        )
        logger.info(f"جدول: اذان {prayer} الساعة {time_str}")

        if prayer == "Fajr":
            fajr_adhkar_dt = fire_dt.replace(second=30)
            scheduler.add_job(
                job_morning_adhkar,
                trigger=DateTrigger(run_date=fajr_adhkar_dt, timezone=TZ),
                args=[bot],
                id=f"morning_adhkar_{date_str}",
                name="أذكار الصباح",
                replace_existing=True,
            )
            logger.info(f"جدول: أذكار الصباح الساعة {time_str}")

        if prayer == "Asr":
            asr_adhkar_dt = fire_dt.replace(second=30)
            scheduler.add_job(
                job_evening_adhkar,
                trigger=DateTrigger(run_date=asr_adhkar_dt, timezone=TZ),
                args=[bot],
                id=f"evening_adhkar_{date_str}",
                name="أذكار المساء",
                replace_existing=True,
            )
            logger.info(f"جدول: أذكار المساء الساعة {time_str}")


# ══════════════════════════════════════════════════════════════════════════════
#  نقطة الدخول
# ══════════════════════════════════════════════════════════════════════════════

async def main() -> None:
    logger.info("بدء تشغيل البوت الإسلامي (النسخة الديناميكية)...")

    if not config.BOT_TOKEN or config.BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        raise ValueError("أدخل BOT_TOKEN في config.py")

    request = HTTPXRequest(
        connect_timeout=30,
        read_timeout=30,
        write_timeout=30,
        pool_timeout=30,
    )
    app = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .request(request)
        .get_updates_request(HTTPXRequest(connect_timeout=30, read_timeout=30))
        .build()
    )
    bot = app.bot

    async def error_handler(update, context):
        err = context.error
        if isinstance(err, (TimedOut, NetworkError)):
            logger.warning(f"خطأ شبكة مؤقت (سيعاد تلقائيا): {err}")
        else:
            logger.error(f"خطأ غير متوقع: {err}", exc_info=True)
    app.add_error_handler(error_handler)

    # معالج تتبع الدردشات
    app.add_handler(ChatMemberHandler(track_chat_membership, ChatMemberHandler.MY_CHAT_MEMBER))
    # معالج زر التخطي

    await bot.set_my_commands([
        BotCommand("start",    "عرض قائمة الأوامر"),
        BotCommand("aya",      "آية قرآنية عشوائية"),
        BotCommand("hadith",   "حديث نبوي شريف"),
        BotCommand("dua",      "دعاء مأثور"),
        BotCommand("story",    "قصة إسلامية"),
        BotCommand("fact",     "معلومة إسلامية"),
        BotCommand("adhan",    "أوقات الصلاة"),
        BotCommand("morning",  "أذكار الصباح"),
        BotCommand("evening",  "أذكار المساء"),
        BotCommand("tasbih",   "تذكير بالتسبيح"),
        BotCommand("word",     "كلمة قرآنية يومية"),
        BotCommand("name",     "اسم الله الحسنى اليومي"),
        BotCommand("deed",     "عمل صالح يومي"),
        BotCommand("books",    "مكتبة الكتب الإسلامية"),
        BotCommand("leave",    "مغادرة الدردشة الحالية (للمشرفين)"),
        BotCommand("recitation","تلاوة قرآنية صوتية"),
        BotCommand("friday",   "ساعة الاستجابة — الجمعة"),
        BotCommand("tasbeeh",  "السبحة الإلكترونية"),
        BotCommand("radio",    "راديو القرآن 24 ساعة"),
        BotCommand("play",     "بث صوت يوتيوب في المكالمة"),
        BotCommand("stop",     "إيقاف البث"),
        BotCommand("pause",    "تعليق البث"),
        BotCommand("resume",   "استئناف البث"),
        BotCommand("nowplaying","ما يُبَث الآن"),
        BotCommand("tiktok",   "تحميل فيديو تيك توك بدون علامة مائية"),
        BotCommand("quiz",     "مسابقة إسلامية عشوائية"),
        BotCommand("scores",   "لوحة الشرف — أفضل المتسابقين"),
        BotCommand("seerah",   "مقتطف يومي من السيرة النبوية"),
        BotCommand("broadcast",  "بث رسالة مخصصة لجميع الدردشات (للمشرف)"),
        BotCommand("settings",   "إعدادات البوت لهذه الدردشة (للمشرفين)"),
        BotCommand("sendimage",  "نشر صورة/فيديو إسلامية (للمشرفين)"),
        BotCommand("deletemedia","حذف صورة أو فيديو من المكتبة (للمشرفين)"),
        BotCommand("media",      "تصفح الميديا المخزنة (للمشرفين)"),
        BotCommand("files",     "مدير ملفات البوت (للمدير الرئيسي)"),
        BotCommand("getfile",   "تنزيل ملف من مجلد البوت (للمدير الرئيسي)"),
        BotCommand("delfile",   "حذف ملف مع تأكيد (للمدير الرئيسي)"),
        BotCommand("mkdir",     "إنشاء مجلد جديد (للمدير الرئيسي)"),
        BotCommand("reload",    "إعادة تحميل موديول (للمدير الرئيسي)"),
        BotCommand("restart",   "إعادة تشغيل البوت (للمدير الرئيسي)"),
        BotCommand("update",    "تحديث yt-dlp + إعادة تشغيل (للمدير الرئيسي)"),
        BotCommand("logs",      "عرض آخر سطور السجل (للمدير الرئيسي)"),
        BotCommand("shell",     "تنفيذ أمر على السيرفر (للمدير الرئيسي)"),
    ])

    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("help",    cmd_start))
    app.add_handler(CommandHandler("aya",     cmd_aya))
    app.add_handler(CommandHandler("ayah",   cmd_aya))
    app.add_handler(CommandHandler("hadith",  cmd_hadith))
    app.add_handler(CommandHandler("dua",     cmd_dua))
    app.add_handler(CommandHandler("story",   cmd_story))
    app.add_handler(CommandHandler("fact",    cmd_fact))
    app.add_handler(CommandHandler("adhan",   cmd_adhan))
    app.add_handler(CommandHandler("morning", cmd_morning_adhkar))
    app.add_handler(CommandHandler("evening", cmd_evening_adhkar))
    app.add_handler(CommandHandler("tasbih",  cmd_tasbih))
    app.add_handler(CommandHandler("word",    cmd_word_of_day))
    app.add_handler(CommandHandler("name",    cmd_name_of_day))
    app.add_handler(CommandHandler("deed",    cmd_good_deed))
    app.add_handler(CommandHandler("books",   cmd_books))
    app.add_handler(CommandHandler("leave",   cmd_leave))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))

    # ── إعدادات الدردشة ──────────────────────────────────────────────────────
    cs.register_handlers(app)
    logger.info("✅ تم تسجيل أمر /settings لإعدادات كل دردشة")

    # ── الميزات الإسلامية المتقدمة ────────────────────────────────────────────
    if ISLAMIC_FEATURES_ENABLED:
        islamic_features.register_handlers(app)
        logger.info("✅ تم تسجيل الميزات الإسلامية المتقدمة (تلاوات، جمعة، سبحة، راديو صوتي)")
    else:
        logger.warning("⚠️  islamic_features.py غير موجود — تأكد من وجود الملف")

    # ── الميزات الجديدة ────────────────────────────────────────────────────────
    if NEW_FEATURES_ENABLED:
        new_features.register_handlers(app)
        logger.info("✅ تم تسجيل الميزات الجديدة (مسابقات ديناميكية، سيرة نبوية، ردود إسلامية)")
    else:
        logger.warning("⚠️  new_features.py غير موجود")

    # ── مدير الملفات عبر تيليغرام ────────────────────────────────────────────
    try:
        import file_manager
        file_manager.register_handlers(app)
        logger.info("✅ مدير الملفات /files /getfile /delfile /mkdir مُفعَّل")
    except ImportError:
        logger.info("ℹ️  file_manager.py غير موجود — مدير الملفات معطل")

    # ── إعادة التشغيل عن بُعد ────────────────────────────────────────────────
    try:
        import restart_manager
        restart_manager.register_handlers(app)
        logger.info("✅ /restart /update /logs /shell مُفعَّلون")
    except ImportError:
        logger.info("ℹ️  restart_manager.py غير موجود — أوامر الإدارة معطلة")

    # ── نشر الصور الإسلامية ───────────────────────────────────────────────────
    try:
        import image_broadcast
        image_broadcast.register_handlers(app)
        logger.info("✅ أمر /sendimage مُفعَّل")
    except ImportError:
        logger.info("ℹ️  image_broadcast.py غير موجود — نشر الصور معطل")

    # ── تحميل تيك توك ────────────────────────────────────────────────────────
    try:
        import tiktok_downloader
        tiktok_downloader.register_handlers(app)
        logger.info("✅ أمر /tiktok مُفعَّل — تحميل فيديوهات بدون علامة مائية")
    except ImportError:
        logger.info("ℹ️  tiktok_downloader.py غير موجود — ميزة /tiktok معطلة")

    # ── أوامر البث الصوتي ─────────────────────────────────────────────────────
    try:
        from voice_commands import cmd_play, cmd_stop, cmd_pause, cmd_resume, cmd_nowplaying
        app.add_handler(CommandHandler("play",       cmd_play))
        app.add_handler(CommandHandler("stop",       cmd_stop))
        app.add_handler(CommandHandler("pause",      cmd_pause))
        app.add_handler(CommandHandler("resume",     cmd_resume))
        app.add_handler(CommandHandler("nowplaying", cmd_nowplaying))
        logger.info("✅ أوامر البث الصوتي مُفعَّلة")
    except ImportError as e:
        logger.warning(f"⚠️  أوامر البث غير متاحة: {e}")
    # معالج رابط اليوتيوب (يجب أن يكون آخر MessageHandler)
    from telegram.ext import MessageHandler, filters
    app.add_handler(CallbackQueryHandler(callback_books, pattern=r"^(book\||books_page\||books_close)"))

    # ── معالج الأوامر في القنوات (channel_post) ───────────────────────────────
    # القنوات ترسل channel_post بدل message — نعيد توجيهها لنفس الـ handlers
    from telegram.ext import MessageHandler, filters

    async def channel_command_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = update.channel_post or update.edited_channel_post
        if not msg or not msg.text:
            return
        text = msg.text.strip()
        if not text.startswith("/"):
            return
        # نستخرج اسم الأمر
        cmd_part = text.split()[0].lstrip("/").split("@")[0].lower()
        context.args = text.split()[1:] if len(text.split()) > 1 else []
        cmd_map = {
            "start": cmd_start, "help": cmd_start,
            "aya": cmd_aya, "ayah": cmd_aya,
            "hadith": cmd_hadith, "dua": cmd_dua,
            "story": cmd_story, "fact": cmd_fact,
            "adhan": cmd_adhan, "morning": cmd_morning_adhkar,
            "evening": cmd_evening_adhkar, "tasbih": cmd_tasbih,
            "word": cmd_word_of_day, "name": cmd_name_of_day,
            "deed": cmd_good_deed, "books": cmd_books,
            "leave": cmd_leave, "broadcast": cmd_broadcast,
        }
        # أوامر الميزات الإسلامية الجديدة
        if ISLAMIC_FEATURES_ENABLED:
            cmd_map.update({
                "recitation": islamic_features.cmd_recitation,
                "tilawa":     islamic_features.cmd_recitation,
                "friday":     islamic_features.cmd_friday,
                "jumua":      islamic_features.cmd_friday,
                "tasbeeh":    islamic_features.cmd_tasbeeh,
                "radio":      islamic_features.cmd_radio,
            })
        # الميزات الجديدة
        if NEW_FEATURES_ENABLED:
            cmd_map.update({
                "quiz":        new_features.cmd_quiz,
                "scores":      new_features.cmd_scores,
                "leaderboard": new_features.cmd_scores,
                "seerah":      new_features.cmd_seerah,
                "sira":        new_features.cmd_seerah,
            })
        # أوامر البث
        try:
            from voice_commands import cmd_play, cmd_stop, cmd_pause, cmd_resume, cmd_nowplaying
            cmd_map.update({"play": cmd_play, "stop": cmd_stop, "pause": cmd_pause,
                            "resume": cmd_resume, "nowplaying": cmd_nowplaying})
        except ImportError:
            pass

        # أوامر نشر الصور
        try:
            from image_broadcast import cmd_sendimage, cmd_deletemedia, cmd_media
            cmd_map["sendimage"]   = cmd_sendimage
            cmd_map["deletemedia"] = cmd_deletemedia
            cmd_map["media"]       = cmd_media
        except ImportError:
            pass

        # أمر تيك توك
        try:
            import tiktok_downloader as _tt
            cmd_map["tiktok"] = _tt.cmd_tiktok
        except ImportError:
            pass

        # أوامر مدير الملفات (للمدير الرئيسي)
        try:
            import file_manager as fm
            cmd_map.update({"files": fm.cmd_files, "getfile": fm.cmd_getfile,
                            "delfile": fm.cmd_delfile, "mkdir": fm.cmd_mkdir,
                            "reload": fm.cmd_reload})
        except ImportError:
            pass

        # أوامر إعادة التشغيل والإدارة (للمدير الرئيسي)
        try:
            import restart_manager as rm
            cmd_map.update({"restart": rm.cmd_restart, "update": rm.cmd_update,
                            "logs": rm.cmd_logs, "shell": rm.cmd_shell})
        except ImportError:
            pass

        # أوامر إعدادات الدردشة
        try:
            import chat_settings as _cs
            cmd_map["settings"] = _cs.cmd_settings
        except ImportError:
            pass

        handler_fn = cmd_map.get(cmd_part)
        if handler_fn:
            await handler_fn(update, context)

    app.add_handler(MessageHandler(
        filters.UpdateType.CHANNEL_POSTS & filters.TEXT,
        channel_command_router,
    ))

    await app.initialize()
    await app.start()
    await app.updater.start_polling(allowed_updates=["message", "callback_query", "my_chat_member", "channel_post", "edited_channel_post"])

    me = await bot.get_me()
    logger.info(f"البوت: @{me.username} ({me.full_name})")

    scheduler = AsyncIOScheduler(timezone=TZ)
    scheduler.add_job(job_random_content, CronTrigger(minute="0,30", timezone=TZ), args=[bot], id="random_content", misfire_grace_time=600, coalesce=True)
    scheduler.add_job(job_quiz, CronTrigger(minute=0, hour="*/2", timezone=TZ), args=[bot], id="auto_quiz", misfire_grace_time=1800, coalesce=True)
    scheduler.add_job(job_tasbih_reminder, CronTrigger(hour=9, minute=0, timezone=TZ), args=[bot], id="tasbih_reminder", misfire_grace_time=3600, coalesce=True)
    scheduler.add_job(job_word_of_day, CronTrigger(hour=12, minute=0, timezone=TZ), args=[bot], id="word_of_day", misfire_grace_time=3600, coalesce=True)
    scheduler.add_job(job_name_of_day, CronTrigger(hour=19, minute=0, timezone=TZ), args=[bot], id="name_of_day", misfire_grace_time=3600, coalesce=True)
    scheduler.add_job(job_good_deed, CronTrigger(hour=8, minute=0, timezone=TZ), args=[bot], id="good_deed", misfire_grace_time=3600, coalesce=True)
    await schedule_adhan(scheduler, bot)
    scheduler.add_job(schedule_adhan, CronTrigger(hour=0, minute=1, timezone=TZ), args=[scheduler, bot], id="daily_adhan_refresh")

    # ── نشر الصور/الفيديوهات: مرتين يومياً بأوقات عشوائية (نظام مستقل) ──────
    await schedule_daily_media(scheduler, bot)
    scheduler.add_job(schedule_daily_media, CronTrigger(hour=0, minute=2, timezone=TZ), args=[scheduler, bot], id="daily_media_refresh")

    # ── تذكير ساعة الاستجابة يوم الجمعة ─────────────────────────────────────
    if ISLAMIC_FEATURES_ENABLED:
        scheduler.add_job(
            islamic_features.job_friday_reminder,
            CronTrigger(day_of_week="fri", hour=15, minute=15, timezone=TZ),
            args=[bot],
            id="friday_reminder",
            name="تذكير ساعة الاستجابة — الجمعة",
        )
        logger.info("جدول: تذكير ساعة الاستجابة كل جمعة 15:15")

    # ── مهام الميزات الجديدة ─────────────────────────────────────────────────
    if NEW_FEATURES_ENABLED:
        new_features.register_jobs(scheduler, bot)
        logger.info("✅ مهام الميزات الجديدة مجدولة (مسابقات / جمعة / صيام)")
    scheduler.start()
    logger.info(f"المجدول يعمل - {len(scheduler.get_jobs())} مهمة")


    logger.info("البوت يعمل. اضغط Ctrl+C للإيقاف.")

    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        logger.info("ايقاف البوت...")
        scheduler.shutdown()
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        if _session and not _session.closed:
            await _session.close()
        logger.info("وداعا. جزاك الله خيرا.")


if __name__ == "__main__":
    asyncio.run(main())