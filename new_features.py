#!/usr/bin/env python3
"""
new_features.py — ميزات إسلامية جديدة
========================================
✅ مسابقات قرآنية كل ساعتين مع نظام نقاط
✅ قصص الأنبياء عبر Claude API
✅ ردود ممتعة (جزاك الله خيراً، ماشاء الله، ...)
✅ تذكير صلاة الجمعة كل جمعة صباحاً
✅ تذكير صيام الاثنين والخميس
"""

import asyncio
import json
import logging
import random
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import aiohttp
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, ContextTypes, CommandHandler,
    CallbackQueryHandler, MessageHandler, filters,
)
from telegram.constants import ParseMode
from telegram.error import TelegramError

logger = logging.getLogger("NewFeatures")

try:
    import config
    TZ = ZoneInfo(config.TIMEZONE)
    BOT_TOKEN         = config.BOT_TOKEN
    ANTHROPIC_API_KEY = getattr(config, "ANTHROPIC_API_KEY", "")
except Exception:
    TZ = ZoneInfo("Africa/Algiers")
    BOT_TOKEN         = ""
    ANTHROPIC_API_KEY = ""

try:
    import chat_settings as cs
    _CS_AVAILABLE = True
except ImportError:
    _CS_AVAILABLE = False

def _feature_enabled(chat_id: int, feature: str) -> bool:
    if _CS_AVAILABLE:
        return cs.is_enabled(chat_id, feature)
    return True

SEP = "〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️"
BASE_DIR = Path(__file__).parent

# ══════════════════════════════════════════════════════════════════════════════
#  مساعد الإرسال — يدعم الرسائل الطويلة تلقائياً
# ══════════════════════════════════════════════════════════════════════════════

_TG_LIMIT = 4096

def _split_message(text: str, limit: int = _TG_LIMIT) -> list[str]:
    """يقسّم النص الطويل على حدود الفقرات مع مؤشر (١/٣)."""
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
            if current:
                chunks.append(current)
                current = ""
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
    if len(chunks) > 1:
        ar = ["١","٢","٣","٤","٥","٦","٧","٨","٩","١٠"]
        t = len(chunks)
        chunks = [f"({ar[i]}/{ar[t-1]})\n\n{c}" for i, c in enumerate(chunks)]
    return chunks


async def _broadcast_long(bot: Bot, chats: list[int], text: str) -> None:
    """يبعث رسالة (طويلة أو قصيرة) لقائمة الدردشات مع تقسيم تلقائي."""
    parts = _split_message(text)
    for chat_id in chats:
        for part in parts:
            try:
                await bot.send_message(chat_id=chat_id, text=part, parse_mode=ParseMode.HTML)
                if len(parts) > 1:
                    await asyncio.sleep(0.3)
            except TelegramError as e:
                logger.error(f"فشل الإرسال إلى {chat_id}: {e}")
        await asyncio.sleep(0.5)


# ══════════════════════════════════════════════════════════════════════════════
#  نظام النقاط — حفظ في ملف JSON
# ══════════════════════════════════════════════════════════════════════════════

SCORES_FILE = BASE_DIR / "quiz_scores.json"


def load_scores() -> dict:
    if SCORES_FILE.exists():
        with open(SCORES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_scores(scores: dict):
    with open(SCORES_FILE, "w", encoding="utf-8") as f:
        json.dump(scores, f, ensure_ascii=False, indent=2)


def add_points(user_id: int, user_name: str, chat_id: int, points: int = 1):
    scores = load_scores()
    key = str(chat_id)
    if key not in scores:
        scores[key] = {}
    uid = str(user_id)
    if uid not in scores[key]:
        scores[key][uid] = {"name": user_name, "points": 0}
    scores[key][uid]["points"] += points
    scores[key][uid]["name"] = user_name  # تحديث الاسم دائماً
    save_scores(scores)
    return scores[key][uid]["points"]


def get_leaderboard(chat_id: int, top: int = 10) -> list[dict]:
    scores = load_scores()
    key = str(chat_id)
    if key not in scores:
        return []
    chat_scores = scores[key]
    sorted_users = sorted(chat_scores.values(), key=lambda x: x["points"], reverse=True)
    return sorted_users[:top]


# ══════════════════════════════════════════════════════════════════════════════
#  بنك أسئلة احتياطي (يُستخدم عند فشل API)
# ══════════════════════════════════════════════════════════════════════════════

QUIZ_QUESTIONS_FALLBACK = [
    {
        "question": "كم عدد سور القرآن الكريم؟",
        "options": ["112", "114", "116", "118"],
        "answer": 1,
        "explanation": "القرآن الكريم يحتوي على 114 سورة.",
    },
    {
        "question": "ما هي أطول سورة في القرآن الكريم؟",
        "options": ["آل عمران", "النساء", "البقرة", "الأنعام"],
        "answer": 2,
        "explanation": "سورة البقرة هي أطول سورة في القرآن بـ 286 آية.",
    },
    {
        "question": "ما هي أقصر سورة في القرآن الكريم؟",
        "options": ["الإخلاص", "الكوثر", "الفلق", "الناس"],
        "answer": 1,
        "explanation": "سورة الكوثر هي أقصر سورة في القرآن بـ 3 آيات فقط.",
    },
    {
        "question": "في أي شهر نزل القرآن الكريم؟",
        "options": ["رجب", "شعبان", "رمضان", "ذو الحجة"],
        "answer": 2,
        "explanation": "قال الله تعالى: ﴿شَهْرُ رَمَضَانَ الَّذِي أُنزِلَ فِيهِ الْقُرْآنُ﴾",
    },
    {
        "question": "كم عدد أركان الإسلام؟",
        "options": ["4", "5", "6", "7"],
        "answer": 1,
        "explanation": "أركان الإسلام خمسة: الشهادتان، الصلاة، الزكاة، الصوم، الحج.",
    },
    {
        "question": "كم عدد أركان الإيمان؟",
        "options": ["4", "5", "6", "7"],
        "answer": 2,
        "explanation": "أركان الإيمان ستة: الله، ملائكته، كتبه، رسله، اليوم الآخر، القدر.",
    },
    {
        "question": "ما اسم والدة سيدنا عيسى عليه السلام؟",
        "options": ["خديجة", "فاطمة", "مريم", "آسيا"],
        "answer": 2,
        "explanation": "والدة سيدنا عيسى عليه السلام هي السيدة مريم عليها السلام.",
    },
    {
        "question": "في أي مدينة وُلد النبي محمد ﷺ؟",
        "options": ["المدينة", "مكة المكرمة", "الطائف", "جدة"],
        "answer": 1,
        "explanation": "وُلد النبي محمد ﷺ في مكة المكرمة عام الفيل.",
    },
    {
        "question": "ما هي السورة التي تُعادل ثلث القرآن؟",
        "options": ["الفاتحة", "يس", "الإخلاص", "الكهف"],
        "answer": 2,
        "explanation": "سورة الإخلاص تعادل ثلث القرآن لاشتمالها على التوحيد الخالص.",
    },
    {
        "question": "كم عدد الأنبياء المذكورين في القرآن الكريم؟",
        "options": ["20", "25", "30", "35"],
        "answer": 1,
        "explanation": "ذُكر في القرآن الكريم 25 نبياً ورسولاً بالاسم.",
    },
    {
        "question": "ما هو اسم جبل نزول الوحي؟",
        "options": ["جبل عرفات", "جبل ثور", "جبل حراء", "جبل أحد"],
        "answer": 2,
        "explanation": "نزل الوحي على النبي ﷺ أول مرة في غار حراء بجبل النور.",
    },
    {
        "question": "كم عدد آيات سورة الفاتحة؟",
        "options": ["5", "6", "7", "8"],
        "answer": 2,
        "explanation": "تتكون سورة الفاتحة من 7 آيات كريمة.",
    },
    {
        "question": "ما اسم زوجة النبي ﷺ الأولى؟",
        "options": ["عائشة", "حفصة", "خديجة", "زينب"],
        "answer": 2,
        "explanation": "أم المؤمنين خديجة بنت خويلد رضي الله عنها كانت أول زوجات النبي ﷺ.",
    },
    {
        "question": "ما عدد ركعات صلاة الفجر؟",
        "options": ["2", "3", "4", "1"],
        "answer": 0,
        "explanation": "صلاة الفجر ركعتان فريضة، وقبلها ركعتا السنة.",
    },
    {
        "question": "أي الأنبياء لُقِّب بـ «خليل الله»؟",
        "options": ["موسى عليه السلام", "عيسى عليه السلام", "إبراهيم عليه السلام", "نوح عليه السلام"],
        "answer": 2,
        "explanation": "لُقِّب سيدنا إبراهيم عليه السلام بـ«خليل الله» لعظيم محبته لله.",
    },
    {
        "question": "في أي يوم تُقام صلاة الجمعة؟",
        "options": ["الخميس", "الجمعة", "السبت", "الأحد"],
        "answer": 1,
        "explanation": "صلاة الجمعة تُقام في يوم الجمعة وهو خير يوم طلعت عليه الشمس.",
    },
]

# ── ذاكرة تخزين مؤقت للأسئلة المولّدة بالـ API ─────────────────────────────
_api_question_cache: list[dict] = []
_api_cache_lock = asyncio.Lock()

QUIZ_CATEGORIES = [
    "القرآن الكريم وعلومه",
    "الحديث النبوي الشريف",
    "السيرة النبوية",
    "الفقه والعبادات",
    "العقيدة الإسلامية",
    "التاريخ الإسلامي",
    "أخلاق الإسلام وآدابه",
    "أسماء الله الحسنى",
    "أركان الإسلام والإيمان",
    "الأنبياء والمرسلون",
]


def _make_aiohttp_session() -> aiohttp.ClientSession:
    """
    ينشئ aiohttp session مع ThreadedResolver بدل aiodns.
    aiodns يحتاج SelectorEventLoop وهو غير متوافق مع ProactorEventLoop (Windows).
    نفس النهج المستخدم في voice_player.py.
    """
    connector = aiohttp.TCPConnector(
        resolver=aiohttp.ThreadedResolver(),
        ssl=False,
    )
    return aiohttp.ClientSession(connector=connector)


async def _fetch_quiz_question_from_api() -> dict | None:
    """
    توليد سؤال مسابقة إسلامي جديد عبر Claude API.
    يعيد dict بنفس بنية QUIZ_QUESTIONS_FALLBACK أو None عند الفشل.
    """
    category = random.choice(QUIZ_CATEGORIES)
    prompt = (
        f"أنت مسابقة إسلامية. أنشئ سؤالاً واحداً فريداً من فئة: «{category}».\n\n"
        "أجب فقط بـ JSON صالح بهذا الشكل الحرفي بدون أي نص إضافي:\n"
        '{"question":"نص السؤال","options":["أ","ب","ج","د"],"answer":0,"explanation":"شرح مختصر"}\n\n'
        "القواعد:\n"
        "- answer هو رقم (0-3) يمثل فهرس الإجابة الصحيحة في options\n"
        "- أربعة خيارات دائماً\n"
        "- السؤال واضح ودقيق شرعياً\n"
        "- الشرح مرجعه القرآن أو السنة الصحيحة\n"
        "- لا تكرر الأسئلة الشائعة جداً\n"
        "- لا تضف أي نص قبل أو بعد JSON"
    )
    try:
        async with _make_aiohttp_session() as session:
            payload = {
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 400,
                "messages": [{"role": "user", "content": prompt}],
            }
            async with session.post(
                "https://api.anthropic.com/v1/messages",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"Quiz API returned {resp.status}")
                    return None
                data = await resp.json()
                text = ""
                for block in data.get("content", []):
                    if block.get("type") == "text":
                        text = block["text"].strip()
                        break
                # تنظيف markdown إن وجد
                text = text.replace("```json", "").replace("```", "").strip()
                q = json.loads(text)
                # التحقق من البنية
                assert isinstance(q["question"], str)
                assert isinstance(q["options"], list) and len(q["options"]) == 4
                assert isinstance(q["answer"], int) and 0 <= q["answer"] <= 3
                assert isinstance(q["explanation"], str)
                return q
    except Exception as e:
        logger.error(f"خطأ في توليد سؤال المسابقة من API: {e}")
        return None


async def _get_quiz_question() -> dict:
    """
    يجلب سؤالاً من الكاش أو يولّد واحداً جديداً من API.
    يرجع سؤالاً احتياطياً عند الفشل.
    """
    async with _api_cache_lock:
        if _api_question_cache:
            return _api_question_cache.pop()

    # توليد سؤال جديد
    q = await _fetch_quiz_question_from_api()
    if q:
        # توليد 2 إضافيين في الخلفية للكاش
        asyncio.create_task(_prefetch_quiz_questions(2))
        return q

    # Fallback
    return random.choice(QUIZ_QUESTIONS_FALLBACK)


async def _prefetch_quiz_questions(count: int = 3):
    """تحميل أسئلة مسبقاً في الكاش."""
    for _ in range(count):
        q = await _fetch_quiz_question_from_api()
        if q:
            async with _api_cache_lock:
                _api_question_cache.append(q)
        await asyncio.sleep(1)

# ── حالة المسابقة النشطة لكل دردشة ─────────────────────────────────────────
# { chat_id: { "question": {...}, "message_id": int, "answered_by": set(), "timer_task": Task } }
active_quizzes: dict[int, dict] = {}


# ══════════════════════════════════════════════════════════════════════════════
#  إرسال المسابقة
# ══════════════════════════════════════════════════════════════════════════════

def _load_target_chats() -> list[int]:
    channels_file = BASE_DIR / "channels.json"
    if channels_file.exists():
        with open(channels_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("chats", [])
    return []


async def send_quiz_to_chat(bot: Bot, chat_id: int):
    """
    إرسال سؤال مسابقة إلى دردشة معينة.
    - المجموعات/المحادثات الخاصة: inline keyboard تفاعلية
    - القنوات: Telegram Quiz Poll أصلي يتيح لجميع المشتركين المشاركة
    """
    if chat_id in active_quizzes:
        return  # يوجد سؤال نشط بالفعل

    q = await _get_quiz_question()

    # ── تحديد نوع الدردشة ───────────────────────────────────────────────────
    try:
        chat_info = await bot.get_chat(chat_id)
        is_channel = chat_info.type == "channel"
    except Exception:
        is_channel = False

    # ── القنوات: استخدام Telegram Quiz Poll الأصلي ──────────────────────────
    if is_channel:
        try:
            msg = await bot.send_poll(
                chat_id=chat_id,
                question=f"🏆 مسابقة إسلامية:\n{q['question']}",
                options=q["options"],
                type="quiz",
                correct_option_id=q["answer"],
                explanation=q.get("explanation", ""),
                explanation_parse_mode=ParseMode.HTML,
                is_anonymous=True,   # إجباري في القنوات — تيليغرام لا يسمح بغير ذلك
                # بدون open_period — نغلقها يدوياً بعد 23 ساعة و59 دقيقة
            )
            # جدولة إغلاق Poll بعد 23:59
            QUIZ_OPEN_SECONDS = 23 * 3600 + 59 * 60  # 86340 ثانية
            timer_task = asyncio.create_task(
                _close_poll_after_timeout(bot, chat_id, msg.message_id, QUIZ_OPEN_SECONDS)
            )
            active_quizzes[chat_id] = {
                "question": q,
                "message_id": msg.message_id,
                "poll_id": msg.poll.id,   # لربط poll_answer بالمسابقة
                "answered_by": set(),
                "timer_task": timer_task,
                "is_poll": True,
            }
        except TelegramError as e:
            logger.error(f"فشل إرسال Poll للقناة {chat_id}: {e}")
        return

    # ── المجموعات: inline keyboard تفاعلية مع نظام نقاط ───────────────────
    options = q["options"]
    keyboard = []
    for i, opt in enumerate(options):
        keyboard.append([InlineKeyboardButton(
            f"🔘 {opt}",
            callback_data=f"quiz|{chat_id}|{i}"
        )])
    keyboard.append([InlineKeyboardButton("🏆 لوحة الشرف", callback_data=f"quiz_scores|{chat_id}")])

    text = (
        f"🏆 <b>مسابقة إسلامية</b>\n"
        f"{SEP}\n\n"
        f"❓ <b>{q['question']}</b>\n\n"
        f"⏳ <i>لديك دقيقتان للإجابة!</i>\n\n"
        f"👇 اختر الإجابة الصحيحة:"
    )

    try:
        msg = await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        # جدولة انتهاء المسابقة بعد دقيقتين
        timer_task = asyncio.create_task(
            _end_quiz_after_timeout(bot, chat_id, msg.message_id, 120)
        )
        active_quizzes[chat_id] = {
            "question": q,
            "message_id": msg.message_id,
            "answered_by": set(),
            "timer_task": timer_task,
            "is_poll": False,
        }
    except TelegramError as e:
        logger.error(f"فشل إرسال المسابقة إلى {chat_id}: {e}")


async def _close_poll_after_timeout(bot: Bot, chat_id: int, message_id: int, delay: int):
    """إغلاق Poll القناة بعد 23:59 ساعة وتنظيف الحالة."""
    await asyncio.sleep(delay)
    active_quizzes.pop(chat_id, None)
    try:
        await bot.stop_poll(chat_id=chat_id, message_id=message_id)
        logger.info(f"✅ تم إغلاق Poll المسابقة في القناة {chat_id} بعد انتهاء المدة")
    except TelegramError as e:
        logger.warning(f"تعذّر إغلاق Poll {chat_id}: {e}")


async def _end_quiz_after_timeout(bot: Bot, chat_id: int, message_id: int, delay: int):
    """إنهاء المسابقة بعد المهلة وعرض الإجابة الصحيحة."""
    await asyncio.sleep(delay)
    await _close_quiz(bot, chat_id, message_id, winner=None, timeout=True)


async def _close_quiz(bot: Bot, chat_id: int, message_id: int, winner: dict | None, timeout: bool = False):
    """إغلاق المسابقة وعرض الإجابة (للمجموعات فقط — القنوات تستخدم Poll أصلي)."""
    quiz_data = active_quizzes.pop(chat_id, None)
    if not quiz_data:
        return

    # إلغاء المهلة إن وُجدت
    task = quiz_data.get("timer_task")
    if task and not task.done():
        task.cancel()

    # القنوات تستخدم Poll أصلي — تيليغرام يتولى الإغلاق تلقائياً
    if quiz_data.get("is_poll"):
        return

    q = quiz_data["question"]
    correct_idx = q["answer"]
    correct_option = q["options"][correct_idx]
    explanation = q.get("explanation", "")

    if timeout:
        result_header = "⏰ <b>انتهى الوقت!</b> لم يجب أحد بشكل صحيح."
    elif winner:
        result_header = f"🎉 <b>أحسنت {winner['name']}!</b> أجبت بشكل صحيح وربحت نقطة! 🌟"
    else:
        result_header = "❌ <b>إجابة خاطئة!</b>"

    text = (
        f"📋 <b>نتيجة المسابقة</b>\n"
        f"{SEP}\n\n"
        f"{result_header}\n\n"
        f"❓ <b>السؤال:</b> {q['question']}\n\n"
        f"✅ <b>الإجابة الصحيحة:</b> {correct_option}\n\n"
        f"📖 <i>{explanation}</i>\n\n"
        f"{SEP}\n"
        f"🔔 <i>المسابقة القادمة بعد ساعتين — استعد!</i>"
    )

    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        try:
            await bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"فشل إغلاق المسابقة: {e}")


async def callback_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إجابة المستخدم على المسابقة."""
    query = update.callback_query

    data = query.data
    if data.startswith("quiz_scores|"):
        # لوحة الشرف: نُجيب الاستعلام هنا مرة واحدة فقط (توقف مؤشر التحميل)،
        # ثم نعرض النتيجة برسالة منفصلة — تجنباً للإجابة مرتين.
        await query.answer()
        chat_id = int(data.split("|")[1])
        await _show_leaderboard(query, chat_id)
        return

    if not data.startswith("quiz|"):
        await query.answer()
        return

    parts = data.split("|")
    if len(parts) < 3:
        await query.answer("⚠️ بيانات غير صالحة.", show_alert=True)
        return

    chat_id = int(parts[1])
    chosen_idx = int(parts[2])
    user = query.from_user

    # في القنوات، from_user قد يكون None (مستخدم مجهول/مشرف قناة)
    if user is None:
        await query.answer("⚠️ لا يمكن التعرف على هويتك في هذا السياق.", show_alert=True)
        return

    quiz_data = active_quizzes.get(chat_id)
    if not quiz_data:
        await query.answer("⏰ انتهت المسابقة بالفعل!", show_alert=True)
        return

    user_id = user.id
    if user_id in quiz_data["answered_by"]:
        await query.answer("⚠️ لقد أجبت بالفعل على هذا السؤال!", show_alert=True)
        return

    quiz_data["answered_by"].add(user_id)
    q = quiz_data["question"]
    correct_idx = q["answer"]
    user_name = user.full_name or user.username or "مجهول"

    if chosen_idx == correct_idx:
        total_pts = add_points(user_id, user_name, chat_id, points=1)
        await query.answer(f"✅ أحسنت! إجابة صحيحة! مجموع نقاطك: {total_pts} 🌟", show_alert=True)
        await _close_quiz(
            context.bot, chat_id, quiz_data["message_id"],
            winner={"name": user_name}, timeout=False
        )
    else:
        await query.answer("❌ إجابة خاطئة! حاول في المرة القادمة.", show_alert=True)


async def _show_leaderboard(query, chat_id: int):
    """عرض لوحة الشرف."""
    board = get_leaderboard(chat_id)
    if not board:
        # الاستعلام تمت الإجابة عليه مسبقاً في callback_quiz؛ نكفي برسالة نصية.
        try:
            await query.message.reply_text("لا توجد نقاط بعد!")
        except TelegramError:
            pass
        return

    medals = ["🥇", "🥈", "🥉"]
    lines = [f"🏆 <b>لوحة الشرف</b>\n{SEP}\n"]
    for i, entry in enumerate(board):
        medal = medals[i] if i < 3 else f"{i+1}."
        lines.append(f"{medal} <b>{entry['name']}</b> — {entry['points']} نقطة")

    lines.append(f"\n{SEP}\n🌟 <i>شارك في المسابقات لتحسين ترتيبك!</i>")
    text = "\n".join(lines)

    try:
        await query.message.reply_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"فشل عرض لوحة الشرف: {e}")


async def cmd_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /quiz — إطلاق مسابقة يدوية."""
    chat_id = update.effective_chat.id
    await send_quiz_to_chat(context.bot, chat_id)


async def cmd_scores(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /scores — عرض لوحة الشرف."""
    chat_id = update.effective_chat.id
    board = get_leaderboard(chat_id)
    if not board:
        await update.effective_message.reply_text(
            "📊 لا توجد نقاط بعد في هذه المجموعة.\n🎯 شارك في المسابقة القادمة!",
            parse_mode=ParseMode.HTML,
        )
        return

    medals = ["🥇", "🥈", "🥉"]
    lines = [f"🏆 <b>لوحة الشرف</b>\n{SEP}\n"]
    for i, entry in enumerate(board):
        medal = medals[i] if i < 3 else f"{i+1}."
        lines.append(f"{medal} <b>{entry['name']}</b> — {entry['points']} نقطة")

    lines.append(f"\n{SEP}\n🌟 <i>المسابقة القادمة بعد ساعتين — استعد!</i>")
    await update.effective_message.reply_text(
        "\n".join(lines), parse_mode=ParseMode.HTML
    )


async def job_quiz(bot: Bot):
    """مهمة جدولية — إرسال مسابقة كل ساعتين لكل الدردشات."""
    logger.info("🏆 إرسال المسابقة الإسلامية...")
    chats = [c for c in _load_target_chats() if _feature_enabled(c, "quiz")]
    for chat_id in chats:
        await send_quiz_to_chat(bot, chat_id)
        await asyncio.sleep(0.5)


# ══════════════════════════════════════════════════════════════════════════════
#  2. مقتطف يومي من السيرة النبوية — /seerah
# ══════════════════════════════════════════════════════════════════════════════

# مراحل السيرة التي يتناوبها البوت
SEERAH_TOPICS = [
    "مولد النبي ﷺ وطفولته في مكة وعند حليمة السعدية",
    "رحلة النبي ﷺ إلى الشام مع عمه أبي طالب ولقاء بحيرى الراهب",
    "حلف الفضول وزواج النبي ﷺ من السيدة خديجة رضي الله عنها",
    "أولى آيات الوحي في غار حراء وبدء الرسالة",
    "أول المسلمين وأساليب الدعوة السرية في مكة",
    "الهجرة إلى الحبشة وحكمة النجاشي العادل",
    "عام الحزن ووفاة أم المؤمنين خديجة وأبي طالب",
    "رحلة الإسراء والمعراج وفرض الصلوات الخمس",
    "بيعة العقبة الأولى والثانية وبداية التخطيط للهجرة",
    "هجرة النبي ﷺ من مكة إلى المدينة المنورة",
    "بناء المسجد النبوي والمؤاخاة بين المهاجرين والأنصار",
    "الميثاق المدني وبناء دولة الإسلام الأولى",
    "غزوة بدر الكبرى ونصر الله للمؤمنين",
    "غزوة أحد والدروس المستفادة من الابتلاء",
    "غزوة الخندق وتجمع الأحزاب حول المدينة",
    "صلح الحديبية وفتح الأفق أمام الإسلام",
    "فتح مكة المكرمة وعفو النبي ﷺ عن أهلها",
    "حجة الوداع وخطبة النبي ﷺ الأخيرة",
    "وفاة النبي ﷺ وحزن الصحابة الكرام",
    "أخلاق النبي ﷺ وصفاته كما وصفها الصحابة",
]


async def _fetch_seerah_snippet(topic: str) -> str | None:
    """توليد مقتطف من السيرة النبوية عبر Claude API."""
    prompt = (
        f"اكتب مقتطفاً يومياً قصيراً من السيرة النبوية عن موضوع: «{topic}»\n\n"
        "الشروط:\n"
        "- الطول: 150-200 كلمة\n"
        "- أسلوب أدبي مؤثر وسلس يناسب مجموعة تيليغرام إسلامية\n"
        "- ابدأ بجملة افتتاحية جذابة مباشرة دون «بسم الله» أو تمهيد\n"
        "- اذكر تفاصيل حقيقية موثوقة من المصادر الصحيحة\n"
        "- اختم بجملة تأمل أو دعاء قصير\n"
        "- لا تضف عناوين أو نقاط، فقط نص متصل\n"
        "- ابدأ مباشرة دون مقدمة"
    )
    try:
        async with _make_aiohttp_session() as session:
            payload = {
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 600,
                "messages": [{"role": "user", "content": prompt}],
            }
            async with session.post(
                "https://api.anthropic.com/v1/messages",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for block in data.get("content", []):
                        if block.get("type") == "text":
                            return block["text"].strip()
    except Exception as e:
        logger.error(f"خطأ في جلب مقتطف السيرة: {e}")
    return None


async def cmd_seerah(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /seerah — مقتطف يومي من السيرة النبوية."""
    # اختيار الموضوع بناءً على اليوم لضمان التنوع
    day_of_year = datetime.now(TZ).timetuple().tm_yday
    topic = SEERAH_TOPICS[day_of_year % len(SEERAH_TOPICS)]

    wait_msg = await update.effective_message.reply_text(
        "📜 <b>جاري جلب مقتطف من السيرة النبوية...</b>\n⏳ <i>انتظر لحظة...</i>",
        parse_mode=ParseMode.HTML,
    )

    snippet = await _fetch_seerah_snippet(topic)

    if snippet:
        full_msg = (
            f"📜 <b>من السيرة النبوية العطرة</b>\n"
            f"{SEP}\n\n"
            f"🕌 <i>{topic}</i>\n\n"
            f"{snippet}\n\n"
            f"{SEP}\n"
            f"🌹 <i>اللهم صلِّ وسلم وبارك على سيدنا محمد ﷺ</i>"
        )
    else:
        full_msg = (
            f"📜 <b>من السيرة النبوية العطرة</b>\n"
            f"{SEP}\n\n"
            f"🌹 قال ﷺ: «خيركم من تعلّم القرآن وعلّمه» — رواه البخاري\n\n"
            f"استمروا في قراءة سيرة النبي ﷺ ففيها النور والهداية.\n\n"
            f"{SEP}\n🌹 اللهم صلِّ وسلم وبارك على سيدنا محمد ﷺ"
        )

    try:
        await wait_msg.edit_text(full_msg, parse_mode=ParseMode.HTML)
    except Exception:
        await update.effective_message.reply_text(full_msg, parse_mode=ParseMode.HTML)


async def job_seerah_daily(bot: Bot):
    """مهمة جدولية — إرسال مقتطف السيرة يومياً."""
    logger.info("📜 إرسال مقتطف السيرة النبوية اليومي...")
    day_of_year = datetime.now(TZ).timetuple().tm_yday
    topic = SEERAH_TOPICS[day_of_year % len(SEERAH_TOPICS)]
    snippet = await _fetch_seerah_snippet(topic)

    if snippet:
        msg = (
            f"📜 <b>مقتطفك اليومي من السيرة النبوية</b>\n"
            f"{SEP}\n\n"
            f"🕌 <i>{topic}</i>\n\n"
            f"{snippet}\n\n"
            f"{SEP}\n"
            f"🌹 <i>اللهم صلِّ وسلم وبارك على سيدنا محمد ﷺ</i>\n\n"
            f"💡 <i>أرسل /seerah للمزيد</i>"
        )
    else:
        msg = (
            f"📜 <b>مقتطفك اليومي من السيرة النبوية</b>\n"
            f"{SEP}\n\n"
            f"🌹 قال ﷺ: «أنا أولى الناس بعيسى ابن مريم في الدنيا والآخرة»\n"
            f"— رواه البخاري\n\n"
            f"تأملوا عظمة النبي ﷺ وقربه من جميع الأنبياء.\n\n"
            f"{SEP}\n🌹 اللهم صلِّ وسلم وبارك على سيدنا محمد ﷺ"
        )

    chats = [c for c in _load_target_chats() if _feature_enabled(c, "seerah")]
    await _broadcast_long(bot, chats, msg)


# ══════════════════════════════════════════════════════════════════════════════
#  3. الردود الممتعة — الكشف عن العبارات الإسلامية
# ══════════════════════════════════════════════════════════════════════════════

ISLAMIC_REPLIES = {
    # جزاك الله خيراً
    "جزاك الله": [
        "وإياكم وبارك الله فيكم 🤲",
        "وإياك وجزاك الله خيراً 🌿",
        "اللهم آمين، وجزاك الله خيراً وأحسن إليك 🌟",
    ],
    "جزاكم الله": [
        "وإياكم وبارك الله فيكم 🤲",
        "اللهم آمين وجزاكم الله خيراً أجمعين 🌿",
    ],
    # ماشاء الله
    "ماشاء الله": [
        "ماشاء الله تبارك الله 🌟",
        "اللهم بارك 💚",
        "ماشاء الله لا قوة إلا بالله 🤲",
    ],
    # بارك الله فيك
    "بارك الله": [
        "وفيك بارك الله وزادك من فضله 🌿",
        "اللهم بارك لك وعليك 🤲",
        "وبارك الله فيك وفي أهلك 💚",
    ],
    # سبحان الله
    "سبحان الله": [
        "سبحان الله وبحمده سبحان الله العظيم ✨",
        "سبحانه وتعالى عما يصفون 🌟",
    ],
    # الحمد لله
    "الحمد لله": [
        "الحمد لله دائماً وأبداً 🌿",
        "نعمة من الله ولله الحمد 💚",
        "الحمد لله الذي بنعمته تتم الصالحات 🤲",
    ],
    # استغفر الله
    "استغفر الله": [
        "استغفر الله العظيم وأتوب إليه 🤲",
        "غفر الله لنا ولكم ولجميع المسلمين 💚",
    ],
    # إن شاء الله
    "إن شاء الله": [
        "إن شاء الله 🌟",
        "اللهم يسّر 🤲",
    ],
    # السلام عليكم
    "السلام عليكم": [
        "وعليكم السلام ورحمة الله وبركاته 🌿",
        "وعليكم السلام ورحمة الله وبركاته، أهلاً وسهلاً 💚",
    ],
    # آمين
    "آمين": [
        "اللهم آمين يا رب العالمين 🤲",
        "آمين آمين يا رب 🌟",
    ],
    # رمضان
    "رمضان مبارك": [
        "رمضان كريم، أحياكم الله لخير الأيام 🌙",
        "رمضان مبارك عليكم وعلى أهاليكم 🌙✨",
    ],
    "رمضان كريم": [
        "الله أكرم، رمضان مبارك عليكم 🌙",
        "رمضان كريم وأنتم بخير 🌙🌟",
    ],
}


async def handle_islamic_replies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل الإسلامية والرد عليها تلقائياً."""
    msg = update.effective_message
    if not msg or not msg.text:
        return

    text = msg.text.strip()

    for trigger, replies in ISLAMIC_REPLIES.items():
        if trigger in text:
            reply = random.choice(replies)
            try:
                await msg.reply_text(reply)
            except TelegramError as e:
                logger.debug(f"فشل الرد التلقائي: {e}")
            break  # رد واحد فقط لكل رسالة


# ══════════════════════════════════════════════════════════════════════════════
#  4. تذكير صلاة الجمعة كل جمعة صباحاً
# ══════════════════════════════════════════════════════════════════════════════

FRIDAY_MORNING_MESSAGES = [
    (
        "🕌 <b>جمعة مباركة</b>\n"
        f"{SEP}\n\n"
        "🌟 <b>اليوم يوم الجمعة</b> — خير يوم طلعت عليه الشمس!\n\n"
        "📋 <b>سنن يوم الجمعة:</b>\n"
        "🚿 الاغتسال والتطيّب والتبكير إلى المسجد\n"
        "📖 قراءة سورة الكهف\n"
        "🤲 الإكثار من الصلاة على النبي ﷺ\n"
        "⏰ التحرّي عن ساعة الاستجابة آخر ساعة قبل المغرب\n\n"
        "💬 <i>«خير يوم طلعت عليه الشمس يوم الجمعة» — صحيح مسلم</i>\n\n"
        f"{SEP}\n🤲 تقبّل الله طاعتكم وجمعة مباركة على الجميع"
    ),
    (
        "🕌 <b>جمعة مباركة عليكم</b>\n"
        f"{SEP}\n\n"
        "🌸 يوم الجمعة هو سيد الأيام وأفضلها عند الله.\n\n"
        "📖 لا تنسوا قراءة سورة الكهف اليوم\n"
        "🤲 وأكثروا من الصلاة والسلام على النبي ﷺ\n"
        "🕐 وتحرّوا ساعة الاستجابة في آخر ساعة قبل غروب الشمس\n\n"
        "💎 <i>«من صلّى عليّ يوم الجمعة ثمانين مرة غفر الله له ذنوب ثمانين سنة» — حديث شريف</i>\n\n"
        f"{SEP}\n💚 اللهم اجعل جمعتنا مقبولة وذنوبنا مغفورة"
    ),
]


async def job_friday_morning(bot: Bot):
    """إرسال تذكير الجمعة صباحاً."""
    logger.info("🕌 إرسال تذكير صلاة الجمعة...")
    msg = random.choice(FRIDAY_MORNING_MESSAGES)
    chats = [c for c in _load_target_chats() if _feature_enabled(c, "friday_reminder")]
    for chat_id in chats:
        try:
            await bot.send_message(chat_id=chat_id, text=msg, parse_mode=ParseMode.HTML)
            await asyncio.sleep(0.5)
        except TelegramError as e:
            logger.error(f"فشل إرسال تذكير الجمعة إلى {chat_id}: {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  5. تذكير صيام الاثنين والخميس
# ══════════════════════════════════════════════════════════════════════════════

FASTING_MONDAY_MESSAGES = [
    (
        "🌙 <b>تذكير بصيام الاثنين</b>\n"
        f"{SEP}\n\n"
        "💚 اليوم يوم الاثنين — يوم تُعرض فيه الأعمال على الله!\n\n"
        "🤲 <i>«تُعرض الأعمال يوم الاثنين والخميس، فأحبّ أن يُعرض عملي وأنا صائم»</i>\n"
        "📚 <i>رواه الترمذي وصحّحه الألباني</i>\n\n"
        "✨ من أراد الصيام فنية واحتساب، جزاه الله خيراً\n\n"
        f"{SEP}\n🌸 اللهم تقبّل صيامنا وقيامنا واجعله في ميزان حسناتنا"
    ),
]

FASTING_THURSDAY_MESSAGES = [
    (
        "🌙 <b>تذكير بصيام الخميس</b>\n"
        f"{SEP}\n\n"
        "💚 اليوم يوم الخميس — يوم تُعرض فيه الأعمال على الله!\n\n"
        "🤲 <i>«تُعرض الأعمال يوم الاثنين والخميس، فأحبّ أن يُعرض عملي وأنا صائم»</i>\n"
        "📚 <i>رواه الترمذي وصحّحه الألباني</i>\n\n"
        "✨ من أراد الصيام فنية واحتساب، بارك الله فيه\n\n"
        f"{SEP}\n🌸 اللهم تقبّل صيامنا ويسّر لنا كل أمر فيه خير"
    ),
]


async def job_fasting_monday(bot: Bot):
    """إرسال تذكير صيام الاثنين."""
    logger.info("🌙 إرسال تذكير صيام الاثنين...")
    msg = random.choice(FASTING_MONDAY_MESSAGES)
    chats = [c for c in _load_target_chats() if _feature_enabled(c, "fasting_reminder")]
    for chat_id in chats:
        try:
            await bot.send_message(chat_id=chat_id, text=msg, parse_mode=ParseMode.HTML)
            await asyncio.sleep(0.5)
        except TelegramError as e:
            logger.error(f"فشل إرسال تذكير الاثنين إلى {chat_id}: {e}")


async def job_fasting_thursday(bot: Bot):
    """إرسال تذكير صيام الخميس."""
    logger.info("🌙 إرسال تذكير صيام الخميس...")
    msg = random.choice(FASTING_THURSDAY_MESSAGES)
    chats = [c for c in _load_target_chats() if _feature_enabled(c, "fasting_reminder")]
    for chat_id in chats:
        try:
            await bot.send_message(chat_id=chat_id, text=msg, parse_mode=ParseMode.HTML)
            await asyncio.sleep(0.5)
        except TelegramError as e:
            logger.error(f"فشل إرسال تذكير الخميس إلى {chat_id}: {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  تسجيل المعالجات في التطبيق
# ══════════════════════════════════════════════════════════════════════════════

async def handle_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يُستدعى عندما يجيب مشترك على Quiz Poll.
    ملاحظة: في القنوات يكون is_anonymous=True (إجباري من تيليغرام)،
    لذا poll_answer لن يُرسل للبوت من القنوات.
    هذا المعالج مفيد فقط إذا أُرسل Poll في مجموعة بـ is_anonymous=False.
    """
    poll_answer = update.poll_answer
    if not poll_answer:
        return

    user = poll_answer.user
    if not user:
        return  # مجهول — لا يمكن تسجيل النقاط

    matched_chat_id = None
    matched_quiz = None
    for cid, qdata in active_quizzes.items():
        if qdata.get("is_poll") and qdata.get("poll_id") == poll_answer.poll_id:
            matched_chat_id = cid
            matched_quiz = qdata
            break

    if not matched_quiz:
        return

    user_id = user.id
    if user_id in matched_quiz["answered_by"]:
        return

    matched_quiz["answered_by"].add(user_id)

    if not poll_answer.option_ids:
        return

    chosen_idx = poll_answer.option_ids[0]
    correct_idx = matched_quiz["question"]["answer"]
    user_name = user.full_name or user.username or "مجهول"

    if chosen_idx == correct_idx:
        add_points(user_id, user_name, matched_chat_id, points=1)
        logger.info(f"✅ {user_name} أجاب صحيحاً في Quiz Poll — {matched_chat_id}")


def register_handlers(app: Application):
    """تسجيل جميع معالجات الميزات الجديدة."""

    # أوامر المسابقة
    app.add_handler(CommandHandler("quiz", cmd_quiz))
    app.add_handler(CommandHandler("scores", cmd_scores))
    app.add_handler(CommandHandler("leaderboard", cmd_scores))

    # مقتطف السيرة النبوية
    app.add_handler(CommandHandler("seerah", cmd_seerah))
    app.add_handler(CommandHandler("sira", cmd_seerah))  # اسم بديل

    # معالج الردود الإسلامية (يُنفَّذ على الرسائل العادية)
    # ملاحظة: يجب تسجيله بعد جميع CommandHandlers
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_islamic_replies,
    ))

    # معالج أزرار المسابقة
    app.add_handler(CallbackQueryHandler(callback_quiz, pattern=r"^quiz"))

    # معالج إجابات Quiz Poll في القنوات (لتسجيل نقاط المشتركين)
    from telegram.ext import PollAnswerHandler
    app.add_handler(PollAnswerHandler(handle_poll_answer))

    logger.info("✅ تم تسجيل الميزات الجديدة (مسابقات ديناميكية، سيرة نبوية، ردود إسلامية)")


def register_jobs(scheduler, bot: Bot):
    """
    تسجيل المهام الجدولية.
    يجب استدعاؤها من main() في bot.py بعد إنشاء scheduler.
    """
    from apscheduler.triggers.cron import CronTrigger

    # مسابقة كل ساعتين
    scheduler.add_job(
        job_quiz,
        CronTrigger(hour="*/2", minute=0, timezone=TZ),
        args=[bot],
        id="islamic_quiz",
        name="مسابقة إسلامية كل ساعتين",
        misfire_grace_time=300,
        coalesce=True,
    )
    logger.info("جدول: مسابقة إسلامية كل ساعتين")

    # مقتطف السيرة النبوية يومياً الساعة 10:00
    scheduler.add_job(
        job_seerah_daily,
        CronTrigger(hour=10, minute=0, timezone=TZ),
        args=[bot],
        id="seerah_daily",
        name="مقتطف السيرة النبوية اليومي",
        misfire_grace_time=600,
        coalesce=True,
    )
    logger.info("جدول: مقتطف السيرة النبوية يومياً 10:00")

    # تذكير الجمعة صباحاً الساعة 8:00
    scheduler.add_job(
        job_friday_morning,
        CronTrigger(day_of_week="fri", hour=8, minute=0, timezone=TZ),
        args=[bot],
        id="friday_morning_reminder",
        name="تذكير صلاة الجمعة صباحاً",
    )
    logger.info("جدول: تذكير الجمعة كل جمعة 8:00")

    # تذكير صيام الاثنين الساعة 6:00
    scheduler.add_job(
        job_fasting_monday,
        CronTrigger(day_of_week="mon", hour=6, minute=0, timezone=TZ),
        args=[bot],
        id="fasting_monday_reminder",
        name="تذكير صيام الاثنين",
    )
    logger.info("جدول: تذكير صيام الاثنين 6:00")

    # تذكير صيام الخميس الساعة 6:00
    scheduler.add_job(
        job_fasting_thursday,
        CronTrigger(day_of_week="thu", hour=6, minute=0, timezone=TZ),
        args=[bot],
        id="fasting_thursday_reminder",
        name="تذكير صيام الخميس",
    )
    logger.info("جدول: تذكير صيام الخميس 6:00")
