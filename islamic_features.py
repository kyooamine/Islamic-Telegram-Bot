#!/usr/bin/env python3
"""
islamic_features.py — ميزات إسلامية متقدمة
=============================================
✅ تلاوات صوتية mp3 للقرآن الكريم
✅ محتوى ديني مرئي (فيديوهات وصور)
✅ ساعة الاستجابة يوم الجمعة
✅ سبحة إلكترونية /tasbih_counter مع عداد
✅ بث مباشر للقرآن 24 ساعة /radio
"""

import asyncio
import logging
import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from telegram import (
    Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup,
    CallbackQuery,
)
from telegram.ext import ContextTypes, CallbackQueryHandler, CommandHandler
from telegram.constants import ParseMode
from telegram.error import TelegramError

logger = logging.getLogger("IslamicFeatures")

# ══════════════════════════════════════════════════════════════════════════════
#  إعدادات عامة
# ══════════════════════════════════════════════════════════════════════════════

try:
    import config
    TZ = ZoneInfo(config.TIMEZONE)
except Exception:
    TZ = ZoneInfo("Africa/Algiers")

SEP = "〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️"


# ══════════════════════════════════════════════════════════════════════════════
#  1. التلاوات الصوتية — /recitation
# ══════════════════════════════════════════════════════════════════════════════

# قراء متاحون عبر API everyayah.com + mp3quran.net
RECITERS = [
    {"id": "ar.alafasy",        "name": "مشاري راشد العفاسي",   "style": "مرتّل"},
    {"id": "ar.husary",         "name": "محمود خليل الحصري",    "style": "مرتّل"},
    {"id": "ar.minshawi",       "name": "محمد صديق المنشاوي",   "style": "مرتّل"},
    {"id": "ar.abdulbasit",     "name": "عبد الباسط عبد الصمد", "style": "مجوّد"},
    {"id": "ar.saoodshuraym",   "name": "سعود الشريم",           "style": "مرتّل"},
    {"id": "ar.mahermuaiqly",   "name": "ماهر المعيقلي",         "style": "مرتّل"},
]

# السور المختارة للتلاوات اليومية
FEATURED_SURAHS = [
    (1,   "الفاتحة",   7),
    (36,  "يس",       83),
    (55,  "الرحمن",   78),
    (67,  "الملك",    30),
    (56,  "الواقعة",  96),
    (18,  "الكهف",   110),
    (112, "الإخلاص",   4),
    (113, "الفلق",     5),
    (114, "الناس",     6),
    (78,  "النبأ",    40),
    (73,  "المزمل",   20),
    (99,  "الزلزلة",   8),
    (103, "العصر",     3),
]

def get_recitation_url(reciter_id: str, surah: int, ayah: int) -> str:
    """رابط mp3 مباشر من everyayah.com"""
    # تحويل معرف القارئ إلى رقم قارئ everyayah
    reciter_map = {
        "ar.alafasy":      "Alafasy_128kbps",
        "ar.husary":       "Husary_128kbps",
        "ar.minshawi":     "Minshawy_Murattal_128kbps",
        "ar.abdulbasit":   "AbdulSamad_128kbps",
        "ar.saoodshuraym": "Saood_ash-Shuraym_128kbps",
        "ar.mahermuaiqly": "Maher_AlMuaiqly_128kbps",
    }
    folder = reciter_map.get(reciter_id, "Alafasy_128kbps")
    return f"https://everyayah.com/data/{folder}/{surah:03d}{ayah:03d}.mp3"

def get_surah_audio_url(reciter_id: str, surah: int) -> str:
    """رابط mp3 للسورة كاملة من mp3quran.net"""
    server_map = {
        "ar.alafasy":      "https://server8.mp3quran.net/afs/",
        "ar.husary":       "https://server7.mp3quran.net/Hussin/",
        "ar.minshawi":     "https://server6.mp3quran.net/minsh/",
        "ar.abdulbasit":   "https://server7.mp3quran.net/basit/",
        "ar.saoodshuraym": "https://server7.mp3quran.net/shuraym/",
        "ar.mahermuaiqly": "https://server8.mp3quran.net/maher/",
    }
    base = server_map.get(reciter_id, "https://server8.mp3quran.net/afs/")
    return f"{base}{surah:03d}.mp3"


def make_recitation_keyboard(surah_idx: int = 0, reciter_idx: int = 0) -> InlineKeyboardMarkup:
    surah_num, surah_name, _ = FEATURED_SURAHS[surah_idx % len(FEATURED_SURAHS)]
    buttons = [
        [
            InlineKeyboardButton("◀️ سورة", callback_data=f"rec|surah|{(surah_idx-1)%len(FEATURED_SURAHS)}|{reciter_idx}"),
            InlineKeyboardButton(f"📖 {surah_name}", callback_data="rec|info"),
            InlineKeyboardButton("سورة ▶️", callback_data=f"rec|surah|{(surah_idx+1)%len(FEATURED_SURAHS)}|{reciter_idx}"),
        ],
        [
            InlineKeyboardButton("◀️ قارئ", callback_data=f"rec|reciter|{surah_idx}|{(reciter_idx-1)%len(RECITERS)}"),
            InlineKeyboardButton(f"🎙️ {RECITERS[reciter_idx]['name'].split()[0]}", callback_data="rec|info"),
            InlineKeyboardButton("قارئ ▶️", callback_data=f"rec|reciter|{surah_idx}|{(reciter_idx+1)%len(RECITERS)}"),
        ],
        [
            InlineKeyboardButton("🎧 استمع للسورة كاملة", callback_data=f"rec|play|{surah_idx}|{reciter_idx}"),
        ],
        [InlineKeyboardButton("❌ إغلاق", callback_data="rec|close")],
    ]
    return InlineKeyboardMarkup(buttons)


def format_recitation_message(surah_idx: int, reciter_idx: int) -> str:
    surah_num, surah_name, ayah_count = FEATURED_SURAHS[surah_idx % len(FEATURED_SURAHS)]
    reciter = RECITERS[reciter_idx % len(RECITERS)]
    return (
        f"🎙️ <b>تلاوة قرآنية كريمة</b>\n"
        f"{SEP}\n\n"
        f"📖 <b>السورة:</b> {surah_name} ({ayah_count} آية)\n"
        f"🎤 <b>القارئ:</b> {reciter['name']}\n"
        f"🎵 <b>الأسلوب:</b> {reciter['style']}\n\n"
        f"👇 <i>اضغط «استمع للسورة كاملة» لتحميل التلاوة</i>\n\n"
        f"{SEP}\n"
        f"﴿وَرَتِّلِ الْقُرْآنَ تَرْتِيلاً﴾"
    )


async def cmd_recitation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """أمر /recitation — اختيار التلاوة الصوتية"""
    surah_idx   = random.randint(0, len(FEATURED_SURAHS) - 1)
    reciter_idx = 0
    keyboard = make_recitation_keyboard(surah_idx, reciter_idx)
    await update.effective_message.reply_text(
        format_recitation_message(surah_idx, reciter_idx),
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard,
    )


async def callback_recitation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    parts = query.data.split("|")
    # حماية من بيانات callback ناقصة/ملوثة
    if len(parts) < 2:
        await query.answer("⚠️ بيانات غير صالحة.", show_alert=True)
        return
    action = parts[1]

    if action == "close":
        await query.answer()
        try:
            await query.message.delete()
        except Exception:
            await query.edit_message_reply_markup(reply_markup=None)
        return

    if action == "info":
        await query.answer()
        return

    if action == "surah":
        await query.answer()
        surah_idx, reciter_idx = int(parts[2]), int(parts[3])
        await query.edit_message_text(
            format_recitation_message(surah_idx, reciter_idx),
            parse_mode=ParseMode.HTML,
            reply_markup=make_recitation_keyboard(surah_idx, reciter_idx),
        )

    elif action == "reciter":
        await query.answer()
        surah_idx, reciter_idx = int(parts[2]), int(parts[3])
        await query.edit_message_text(
            format_recitation_message(surah_idx, reciter_idx),
            parse_mode=ParseMode.HTML,
            reply_markup=make_recitation_keyboard(surah_idx, reciter_idx),
        )

    elif action == "play":
        surah_idx   = int(parts[2])
        reciter_idx = int(parts[3])
        surah_num, surah_name, _ = FEATURED_SURAHS[surah_idx % len(FEATURED_SURAHS)]
        reciter     = RECITERS[reciter_idx % len(RECITERS)]
        audio_url   = get_surah_audio_url(reciter["id"], surah_num)

        await query.answer("⏳ جاري تحميل التلاوة...", show_alert=False)
        caption = (
            f"🎙️ <b>تلاوة سورة {surah_name}</b>\n"
            f"🎤 <b>القارئ:</b> {reciter['name']}\n\n"
            f"🤲 <i>اللهم اجعل القرآن ربيع قلوبنا</i>"
        )
        try:
            await query.message.reply_audio(
                audio=audio_url,
                caption=caption,
                parse_mode=ParseMode.HTML,
                title=f"سورة {surah_name}",
                performer=reciter["name"],
            )
        except TelegramError as e:
            logger.warning(f"فشل إرسال الصوت مباشرة: {e}")
            # Fallback: أرسل الرابط
            await query.message.reply_text(
                f"🎧 <b>تلاوة سورة {surah_name}</b>\n"
                f"🎤 {reciter['name']}\n\n"
                f"🔗 <a href='{audio_url}'>اضغط هنا للاستماع أو التحميل</a>",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=False,
            )



# ══════════════════════════════════════════════════════════════════════════════
#  3. ساعة الاستجابة يوم الجمعة — /friday
# ══════════════════════════════════════════════════════════════════════════════

FRIDAY_DUAS = [
    "اللهم إنا نسألك الجنة ونعوذ بك من النار",
    "اللهم اغفر لنا ذنوبنا وإسرافنا في أمرنا",
    "اللهم ثبّت قلوبنا على دينك",
    "اللهم اجعل القرآن ربيع قلوبنا ونور صدورنا",
    "اللهم اكفنا ما أهمّنا ولا تكلنا إلى أنفسنا طرفة عين",
    "اللهم تقبّل توبتنا واغسل حوبتنا وأجب دعوتنا",
    "ربنا آتنا في الدنيا حسنة وفي الآخرة حسنة وقنا عذاب النار",
    "اللهم إنا نسألك العافية في الدنيا والآخرة",
    "اللهم أصلح لنا ديننا الذي هو عصمة أمرنا",
    "اللهم اجعل أوسع رزقنا عند كبر سننا وانقطاع أعمارنا",
]


def get_friday_response_hour() -> tuple[int, int, int, int]:
    """
    يحسب ساعة الاستجابة المرجّحة: آخر ساعة قبل المغرب يوم الجمعة
    يعيد (start_hour, start_min, end_hour, end_min)
    """
    # الرأي الراجح: من بعد صلاة العصر حتى المغرب
    # نأخذ تقديراً: 15:30 - 18:00 (يتفاوت حسب الفصل)
    return (15, 30, 18, 0)


def format_friday_message() -> str:
    now = datetime.now(TZ)
    weekday = now.weekday()  # 4 = الجمعة

    if weekday != 4:
        days_until = (4 - weekday) % 7
        next_friday = now + timedelta(days=days_until)
        date_str = next_friday.strftime("%d/%m/%Y")
        return (
            f"🌙 <b>ساعة الاستجابة — يوم الجمعة</b>\n"
            f"{SEP}\n\n"
            f"⏰ <b>اليوم الجمعة القادمة:</b> {date_str}\n"
            f"<i>(بعد {days_until} {'أيام' if days_until > 2 else 'يوم'})</i>\n\n"
            f"📖 <b>عن ساعة الاستجابة:</b>\n"
            f"قال ﷺ: «في الجمعة ساعة لا يوافقها عبد مسلم وهو قائم يصلي "
            f"يسأل الله شيئاً إلا أعطاه إياه» — متفق عليه\n\n"
            f"⏱️ <b>وقتها المرجّح:</b> من بعد العصر حتى المغرب\n\n"
            f"💡 <b>أدعية مقترحة:</b>\n"
            f"{''.join(f'• {d}%0A' for d in random.sample(FRIDAY_DUAS, 3))}\n"
            f"{SEP}\n"
            f"🤲 <i>اللهم لا تحرمنا من ساعة الاستجابة</i>"
        ).replace("%0A", "\n")
    else:
        s_h, s_m, e_h, e_m = get_friday_response_hour()
        current_hour = now.hour
        current_min  = now.minute
        in_window = (
            (current_hour > s_h or (current_hour == s_h and current_min >= s_m)) and
            (current_hour < e_h or (current_hour == e_h and current_min < e_m))
        )

        duas_text = "\n".join(f"🤲 {d}" for d in random.sample(FRIDAY_DUAS, 5))

        if in_window:
            status = f"🟢 <b>أنت الآن في وقت ساعة الاستجابة!</b>\n<b>ادعُ الله الآن!</b>"
        else:
            status = (
                f"⏰ <b>ساعة الاستجابة المقدّرة:</b>\n"
                f"من الساعة {s_h}:{s_m:02d} حتى {e_h}:{e_m:02d}"
            )

        return (
            f"✨ <b>اليوم الجمعة — ساعة الاستجابة</b>\n"
            f"{SEP}\n\n"
            f"{status}\n\n"
            f"📖 قال ﷺ: «في الجمعة ساعة لا يوافقها عبد مسلم وهو قائم يصلي "
            f"يسأل الله شيئاً إلا أعطاه إياه» — متفق عليه\n\n"
            f"💬 <b>ادعُ بهذه الأدعية الآن:</b>\n\n"
            f"{duas_text}\n\n"
            f"{SEP}\n"
            f"🌹 <i>اللهم تقبّل دعاءنا وارحم ضعفنا</i>"
        )


async def cmd_friday(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """أمر /friday — معلومات ساعة الاستجابة"""
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 تحديث", callback_data="friday|refresh")],
        [InlineKeyboardButton("🤲 أدعية الجمعة", callback_data="friday|duas")],
    ])
    await update.effective_message.reply_text(
        format_friday_message(),
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard,
    )


async def callback_friday(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    action = query.data.split("|")[1]

    if action == "refresh":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 تحديث", callback_data="friday|refresh")],
            [InlineKeyboardButton("🤲 أدعية الجمعة", callback_data="friday|duas")],
        ])
        try:
            await query.edit_message_text(
                format_friday_message(),
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
            )
        except Exception:
            pass

    elif action == "duas":
        duas_text = "\n\n".join(f"🤲 {d}" for d in FRIDAY_DUAS)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 رجوع", callback_data="friday|refresh")],
        ])
        try:
            await query.edit_message_text(
                f"🤲 <b>أدعية يوم الجمعة</b>\n{SEP}\n\n{duas_text}\n\n{SEP}\n"
                f"<i>اللهم تقبّل دعاءنا</i>",
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
            )
        except Exception:
            pass


async def job_friday_reminder(bot: Bot) -> None:
    """
    يُرسَل يوم الجمعة قُبيل ساعة الاستجابة — جدولته في bot.py:
    كل جمعة الساعة 15:15
    """
    from bot import broadcast
    now = datetime.now(TZ)
    if now.weekday() != 4:
        return
    msg = (
        f"⏰ <b>تنبيه — ساعة الاستجابة تقترب</b>\n"
        f"{SEP}\n\n"
        f"🌟 يوم الجمعة المبارك — استعدّوا للدعاء!\n\n"
        f"⏱️ <b>الوقت المُقدَّر:</b> من بعد العصر حتى المغرب\n\n"
        f"💬 <b>ادعوا الله بهذه الأدعية:</b>\n\n"
        + "\n".join(f"🤲 {d}" for d in random.sample(FRIDAY_DUAS, 5)) +
        f"\n\n{SEP}\n"
        f"🌹 <i>اللهم لا تحرمنا بركة يوم الجمعة</i>\n\n"
        f"💡 <i>أرسل /friday لمزيد من المعلومات</i>"
    )
    await broadcast(bot, msg)


# ══════════════════════════════════════════════════════════════════════════════
#  4. السبحة الإلكترونية — /tasbeeh
# ══════════════════════════════════════════════════════════════════════════════

# تخزين عدادات المستخدمين في الذاكرة
# { (chat_id, message_id): {"count": 0, "tasbih": "سبحان الله", "target": 33} }
_tasbih_sessions: dict[str, dict] = {}

TASBIHAT = [
    {"text": "سبحان الله",         "target": 33,  "virtue": "من أحب الكلام إلى الله"},
    {"text": "الحمد لله",          "target": 33,  "virtue": "تملأ الميزان"},
    {"text": "الله أكبر",          "target": 34,  "virtue": "أكبر من كل شيء"},
    {"text": "لا إله إلا الله",    "target": 100, "virtue": "أفضل الذكر"},
    {"text": "سبحان الله وبحمده",  "target": 100, "virtue": "حبيبة إلى الرحمن"},
    {"text": "أستغفر الله",        "target": 100, "virtue": "تغسل الذنوب"},
    {"text": "اللهم صلِّ على محمد","target": 10,  "virtue": "عشر صلوات من الله"},
    {"text": "لا حول ولا قوة إلا بالله", "target": 33, "virtue": "كنز من كنوز الجنة"},
]


def make_tasbih_keyboard(session_key: str, count: int, target: int, tasbih_idx: int) -> InlineKeyboardMarkup:
    progress_filled = min(10, int(count / target * 10)) if target > 0 else 0
    progress_bar = "▓" * progress_filled + "░" * (10 - progress_filled)
    rounds = count // target
    remainder = count % target

    buttons = [
        # شريط التقدم
        [InlineKeyboardButton(
            f"{'🌟' if count >= target else '📿'} {count} | {progress_bar} | {target}",
            callback_data="tasbih|info"
        )],
        # أزرار التسبيح
        [
            InlineKeyboardButton("📿 × 1",  callback_data=f"tasbih|add|{session_key}|1"),
            InlineKeyboardButton("📿 × 10", callback_data=f"tasbih|add|{session_key}|10"),
            InlineKeyboardButton("📿 × 33", callback_data=f"tasbih|add|{session_key}|33"),
        ],
        # تغيير التسبيح
        [
            InlineKeyboardButton("◀️", callback_data=f"tasbih|change|{session_key}|{(tasbih_idx-1)%len(TASBIHAT)}"),
            InlineKeyboardButton(f"📿 {TASBIHAT[tasbih_idx]['text'][:12]}", callback_data="tasbih|info"),
            InlineKeyboardButton("▶️", callback_data=f"tasbih|change|{session_key}|{(tasbih_idx+1)%len(TASBIHAT)}"),
        ],
        # إعادة التعيين والإغلاق
        [
            InlineKeyboardButton("🔄 إعادة تعيين", callback_data=f"tasbih|reset|{session_key}"),
            InlineKeyboardButton("❌ إغلاق", callback_data=f"tasbih|close|{session_key}"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def format_tasbih_message(count: int, tasbih_idx: int, target: int) -> str:
    tasbih = TASBIHAT[tasbih_idx]
    rounds = count // target
    remainder = count % target

    # نجوم للإنجاز
    stars = "🌟" * min(rounds, 5) if rounds > 0 else ""

    rounds_text = f"\n✅ <b>دورات مكتملة:</b> {rounds} {stars}" if rounds > 0 else ""

    return (
        f"📿 <b>السبحة الإلكترونية</b>\n"
        f"{SEP}\n\n"
        f"✨ <b>« {tasbih['text']} »</b>\n\n"
        f"💎 <i>{tasbih['virtue']}</i>\n\n"
        f"🔢 <b>العدد:</b> {count} / {target}"
        f"{rounds_text}\n\n"
        f"👇 <i>اضغط الأزرار للتسبيح</i>\n"
        f"{SEP}"
    )


async def cmd_tasbeeh(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """أمر /tasbeeh — السبحة الإلكترونية"""
    tasbih_idx = 0
    tasbih = TASBIHAT[tasbih_idx]
    msg = await update.effective_message.reply_text(
        format_tasbih_message(0, tasbih_idx, tasbih["target"]),
        parse_mode=ParseMode.HTML,
        reply_markup=make_tasbih_keyboard("tmp", 0, tasbih["target"], tasbih_idx),
    )
    # حفظ الجلسة
    session_key = f"{update.effective_chat.id}_{msg.message_id}"
    _tasbih_sessions[session_key] = {
        "count":      0,
        "tasbih_idx": tasbih_idx,
        "target":     tasbih["target"],
    }
    # تحديث الأزرار بـ session_key الصحيح
    await msg.edit_reply_markup(
        reply_markup=make_tasbih_keyboard(session_key, 0, tasbih["target"], tasbih_idx)
    )


async def callback_tasbeeh(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    parts = query.data.split("|")
    # حماية من بيانات callback ناقصة/ملوثة (تجنّب IndexError)
    if len(parts) < 2:
        await query.answer("⚠️ بيانات غير صالحة.", show_alert=True)
        return
    action = parts[1]

    if action == "info":
        await query.answer()
        return

    session_key = parts[2] if len(parts) > 2 else ""
    session = _tasbih_sessions.get(session_key)

    if action == "close":
        await query.answer("جزاك الله خيراً 🌟")
        try:
            await query.message.delete()
        except Exception:
            await query.edit_message_reply_markup(reply_markup=None)
        if session_key in _tasbih_sessions:
            del _tasbih_sessions[session_key]
        return

    if not session:
        await query.answer("⚠️ انتهت الجلسة، ابدأ جلسة جديدة بـ /tasbeeh", show_alert=True)
        return

    if action == "add":
        amount = int(parts[3])
        session["count"] += amount
        count = session["count"]
        target = session["target"]
        tasbih_idx = session["tasbih_idx"]

        # تهنئة عند إكمال دورة
        if count > 0 and (count % target) < amount:
            rounds = count // target
            await query.answer(f"🌟 ما شاء الله! أكملت الدورة رقم {rounds}!", show_alert=False)
        else:
            await query.answer(f"📿 {count}")

        try:
            await query.edit_message_text(
                format_tasbih_message(count, tasbih_idx, target),
                parse_mode=ParseMode.HTML,
                reply_markup=make_tasbih_keyboard(session_key, count, target, tasbih_idx),
            )
        except Exception:
            pass

    elif action == "reset":
        session["count"] = 0
        await query.answer("🔄 تم إعادة التعيين")
        tasbih_idx = session["tasbih_idx"]
        target = session["target"]
        try:
            await query.edit_message_text(
                format_tasbih_message(0, tasbih_idx, target),
                parse_mode=ParseMode.HTML,
                reply_markup=make_tasbih_keyboard(session_key, 0, target, tasbih_idx),
            )
        except Exception:
            pass

    elif action == "change":
        new_idx = int(parts[3])
        session["tasbih_idx"] = new_idx
        session["count"]      = 0  # إعادة العداد عند تغيير التسبيح
        new_tasbih = TASBIHAT[new_idx]
        session["target"] = new_tasbih["target"]
        await query.answer(f"📿 {new_tasbih['text']}")
        try:
            await query.edit_message_text(
                format_tasbih_message(0, new_idx, new_tasbih["target"]),
                parse_mode=ParseMode.HTML,
                reply_markup=make_tasbih_keyboard(session_key, 0, new_tasbih["target"], new_idx),
            )
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
#  5. راديو القرآن المباشر — /radio  (يبث في المكالمة الصوتية)
# ══════════════════════════════════════════════════════════════════════════════

QURAN_RADIOS = [
    {
        "name":        "إذاعة القرآن الكريم — السعودية",
        "url":         "https://stream.radiojar.com/0tpy1h0kxtzuv",
        "description": "البث المباشر لإذاعة القرآن الكريم من المملكة العربية السعودية",
        "flag":        "🇸🇦",
    },
    {
        "name":        "أحاديث نبوية صحيحة",
        "url":         "https://www.youtube.com/watch?v=k0Le1nGIYc0",
        "description": "أحاديث نبوية صحيحة من السنة المطهرة",
        "flag":        "📖",
        "is_youtube":  True,
    },
]


def _get_voice_player():
    """يجلب voice_player إذا كان متاحاً."""
    try:
        import voice_player as vp
        return vp if vp.is_voice_ready() else None
    except ImportError:
        return None


def make_radio_keyboard(selected_idx: int = 0, in_call: bool = False) -> InlineKeyboardMarkup:
    buttons = []
    for i, radio in enumerate(QURAN_RADIOS):
        check = "✅ " if i == selected_idx else ""
        buttons.append([InlineKeyboardButton(
            f"{check}{radio['flag']} {radio['name']}",
            callback_data=f"radio|select|{i}"
        )])

    # زر البث في المكالمة (الرئيسي) + زر إيقاف
    if in_call:
        buttons.append([
            InlineKeyboardButton("📡 بث في المكالمة", callback_data=f"radio|call|{selected_idx}"),
            InlineKeyboardButton("⏹️ إيقاف البث",     callback_data=f"radio|stopcall|{selected_idx}"),
        ])
    else:
        buttons.append([
            InlineKeyboardButton("📡 بث في المكالمة الصوتية", callback_data=f"radio|call|{selected_idx}"),
        ])
    buttons.append([InlineKeyboardButton("❌ إغلاق", callback_data="radio|close|0")])
    return InlineKeyboardMarkup(buttons)


def format_radio_message(idx: int, streaming: bool = False) -> str:
    radio = QURAN_RADIOS[idx]
    status = "🔴 <b>يُبَث الآن في المكالمة</b>" if streaming else "⚪ جاهز للبث"
    return (
        f"📻 <b>راديو القرآن الكريم المباشر</b>\n"
        f"{SEP}\n\n"
        f"{radio['flag']} <b>{radio['name']}</b>\n\n"
        f"📡 {radio['description']}\n\n"
        f"🔊 <b>الحالة:</b> {status}\n\n"
        f"👇 <i>اضغط «بث في المكالمة» لتشغيل الراديو\n"
        f"في المكالمة الصوتية النشطة — متاح لجميع الأعضاء</i>\n\n"
        f"{SEP}\n"
        f"﴿إِنَّ الَّذِينَ يَتْلُونَ كِتَابَ اللَّهِ وَأَقَامُوا الصَّلَاةَ﴾"
    )


async def cmd_radio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """أمر /radio — راديو القرآن الكريم في المكالمة الصوتية"""
    vp = _get_voice_player()
    chat_id = update.effective_chat.id
    streaming = vp is not None and vp.get_now_playing(chat_id) is not None

    await update.effective_message.reply_text(
        format_radio_message(0, streaming=streaming),
        parse_mode=ParseMode.HTML,
        reply_markup=make_radio_keyboard(0, in_call=streaming),
        disable_web_page_preview=True,
    )


async def _is_admin_radio(update: Update) -> bool:
    """تحقق من صلاحية المشرف (نفس منطق voice_commands)."""
    chat = update.effective_chat
    user = update.effective_user
    if chat.type == "channel":
        return True
    if not user:
        return False
    if chat.type == "private":
        return True
    try:
        member = await chat.get_member(user.id)
        return member.status in ["administrator", "creator"]
    except Exception:
        return False


async def callback_radio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    parts = query.data.split("|")
    # حماية من بيانات callback ناقصة/ملوثة
    if len(parts) < 2:
        await query.answer("⚠️ بيانات غير صالحة.", show_alert=True)
        return
    action = parts[1]
    try:
        idx = int(parts[2]) if len(parts) > 2 else 0
    except ValueError:
        idx = 0
    chat_id = query.message.chat.id

    if action == "close":
        await query.answer()
        try:
            await query.message.delete()
        except Exception:
            await query.edit_message_reply_markup(reply_markup=None)
        return

    if action == "select":
        await query.answer(f"📻 {QURAN_RADIOS[idx]['flag']} {QURAN_RADIOS[idx]['name']}")
        vp = _get_voice_player()
        streaming = vp is not None and vp.get_now_playing(chat_id) is not None
        try:
            await query.edit_message_text(
                format_radio_message(idx, streaming=streaming),
                parse_mode=ParseMode.HTML,
                reply_markup=make_radio_keyboard(idx, in_call=streaming),
                disable_web_page_preview=True,
            )
        except Exception as e:
            # 400 MessageNotModified: نتجاهله — المحتوى لم يتغير
            if "not modified" not in str(e).lower():
                logger.debug(f"select edit error: {e}")

    elif action == "call":
        # ── البث في المكالمة الصوتية — متاح للجميع ───────────────────────
        await query.answer("⏳ جاري الاتصال بالمكالمة...")
        vp = _get_voice_player()
        if vp is None:
            await query.message.reply_text(
                "❌ <b>الحساب المساعد غير جاهز!</b>\n"
                "تأكد من تشغيل البوت عبر <code>run_all.py</code> وإنشاء جلسة <code>setup_session.py</code>.",
                parse_mode=ParseMode.HTML,
            )
            return

        radio = QURAN_RADIOS[idx]
        is_yt = radio.get("is_youtube", False)

        try:
            import config as _cfg
            if is_yt:
                # يوتيوب — نستخدم play_in_chat مع yt-dlp
                result = await vp.play_in_chat(
                    chat_id=chat_id,
                    url=radio["url"],
                    requested_by=f"📻 {radio['flag']} {radio['name']}",
                    bot_token=_cfg.BOT_TOKEN,
                )
            else:
                # stream مباشر — نستخدم _play_radio_stream
                result = await _play_radio_stream(
                    vp=vp,
                    chat_id=chat_id,
                    stream_url=radio["url"],
                    title=f"📻 {radio['flag']} {radio['name']}",
                    bot_token=_cfg.BOT_TOKEN,
                )
        except Exception as e:
            await query.message.reply_text(f"❌ خطأ غير متوقع: <code>{str(e)[:150]}</code>", parse_mode=ParseMode.HTML)
            return

        if result["ok"]:
            try:
                await query.edit_message_text(
                    format_radio_message(idx, streaming=True),
                    parse_mode=ParseMode.HTML,
                    reply_markup=make_radio_keyboard(idx, in_call=True),
                    disable_web_page_preview=True,
                )
            except Exception as e:
                if "not modified" not in str(e).lower():
                    logger.debug(f"call edit error: {e}")
        else:
            err = result.get("error", "")
            if err == "no_active_call":
                msg = (
                    "⚠️ <b>لا توجد مكالمة صوتية نشطة!</b>\n\n"
                    "1️⃣ افتح إعدادات المجموعة\n"
                    "2️⃣ ابدأ <b>Voice Chat</b> أو <b>Livestream</b>\n"
                    "3️⃣ اضغط «بث في المكالمة» مرة أخرى"
                )
                await query.message.reply_text(msg, parse_mode=ParseMode.HTML)
            else:
                await query.message.reply_text(f"❌ فشل البث:\n<code>{err[:200]}</code>", parse_mode=ParseMode.HTML)

    elif action == "stopcall":
        # ── إيقاف البث — متاح للجميع ──────────────────────────────────────
        await query.answer("⏹️ جاري إيقاف البث...")
        vp = _get_voice_player()
        if vp:
            await vp.stop_in_chat(chat_id)
        try:
            await query.edit_message_text(
                format_radio_message(idx, streaming=False),
                parse_mode=ParseMode.HTML,
                reply_markup=make_radio_keyboard(idx, in_call=False),
                disable_web_page_preview=True,
            )
        except Exception as e:
            if "not modified" not in str(e).lower():
                logger.debug(f"stopcall edit error: {e}")


async def _play_radio_stream(
    vp, chat_id: int, stream_url: str, title: str, bot_token: str
) -> dict:
    """
    يشغّل stream مباشر (radio) في المكالمة الصوتية.
    الفرق عن يوتيوب: الراديو الحي يحتاج:
      - NO -re flag (لأن ffmpeg يقرأ بالسرعة الحقيقية تلقائياً)
      - reconnect flags لإعادة الاتصال عند الانقطاع
      - audio_path منفصل بدل media_path الرئيسي (لتجنب video detection)
    """
    # تأكد أن الحساب المساعد موجود في الدردشة
    if bot_token:
        join = await vp._ensure_userbot_in_chat(bot_token, chat_id)
        if not join["ok"]:
            return {"ok": False, "error": join.get("error", "فشل الانضمام")}
        await asyncio.sleep(1)

    try:
        from pytgcalls.types import MediaStream, AudioQuality

        # نجرب بالترتيب: مع ffmpeg_parameters ← بدونها
        stream = None
        last_err = None

        for ffmpeg_params in [
            # المحاولة الأولى: reconnect فقط بدون -re (الأنسب للراديو الحي)
            "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 3",
            # المحاولة الثانية: بدون أي parameters إضافية
            None,
        ]:
            try:
                kwargs = dict(
                    audio_parameters=AudioQuality.HIGH,
                    video_flags=MediaStream.Flags.IGNORE,
                    audio_flags=MediaStream.Flags.REQUIRED,
                )
                if ffmpeg_params:
                    kwargs["ffmpeg_parameters"] = ffmpeg_params

                stream = MediaStream(stream_url, **kwargs)
                break  # نجح البناء
            except TypeError as e:
                last_err = e
                continue

        if stream is None:
            return {"ok": False, "error": f"فشل بناء MediaStream: {last_err}"}

        tg_calls = vp._get_pytgcalls()
        # py-tgcalls v2.x: play() تستبدل البث الحالي تلقائياً
        await tg_calls.play(chat_id, stream)

        vp.active_streams[chat_id] = {
            "url":          stream_url,
            "title":        title,
            "requested_by": "📻 راديو القرآن",
        }
        return {"ok": True, "title": title}

    except Exception as e:
        import traceback as _tb
        full = _tb.format_exc()
        err = str(e).strip() or type(e).__name__
        err_lower = err.lower()
        logger.error(f"radio stream error:\n{full}")
        if "no active" in err_lower or "no_active" in err_lower or "GroupCallNotFound" in err:
            return {"ok": False, "error": "no_active_call"}
        if "chat_admin_required" in err_lower or type(e).__name__ == "ChatAdminRequired":
            return {"ok": False, "error": "no_active_call"}
        return {"ok": False, "error": f"{type(e).__name__}: {err}"}


# ══════════════════════════════════════════════════════════════════════════════
#  تسجيل جميع المعالجات في التطبيق
# ══════════════════════════════════════════════════════════════════════════════

def register_handlers(app) -> None:
    """سجّل جميع معالجات الميزات الجديدة في التطبيق"""
    from telegram.ext import CommandHandler, CallbackQueryHandler

    # أوامر
    app.add_handler(CommandHandler("recitation",      cmd_recitation))
    app.add_handler(CommandHandler("tilawa",          cmd_recitation))  # اسم بديل
    app.add_handler(CommandHandler("friday",          cmd_friday))
    app.add_handler(CommandHandler("jumua",           cmd_friday))      # اسم بديل
    app.add_handler(CommandHandler("tasbeeh",         cmd_tasbeeh))
    app.add_handler(CommandHandler("tasbih_counter",  cmd_tasbeeh))
    app.add_handler(CommandHandler("radio",           cmd_radio))

    # Callbacks
    app.add_handler(CallbackQueryHandler(callback_recitation, pattern=r"^rec\|"))
    app.add_handler(CallbackQueryHandler(callback_friday,     pattern=r"^friday\|"))
    app.add_handler(CallbackQueryHandler(callback_tasbeeh,    pattern=r"^tasbih\|"))
    app.add_handler(CallbackQueryHandler(callback_radio,      pattern=r"^radio\|"))

    logger.info("✅ تم تسجيل معالجات الميزات الإسلامية الجديدة")
