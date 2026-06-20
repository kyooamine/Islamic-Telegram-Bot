#!/usr/bin/env python3
"""
chat_settings.py — نظام إعدادات كل دردشة على حدة
===================================================
يسمح لمشرفي كل مجموعة/قناة بتفعيل/تعطيل أي ميزة من ميزات البوت
عبر واجهة أزرار تفاعلية بالأمر /settings
"""

import json
import logging
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler
from telegram.constants import ParseMode

logger = logging.getLogger("ChatSettings")

# ── مسار ملف الإعدادات ────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).parent
SETTINGS_FILE = BASE_DIR / "chat_settings.json"

# ══════════════════════════════════════════════════════════════════════════════
#  تعريف كل الميزات القابلة للتفعيل/التعطيل
# ══════════════════════════════════════════════════════════════════════════════
# الصيغة: "مفتاح": ("الاسم للعرض", "الإيموجي")
FEATURES: dict[str, tuple[str, str]] = {
    # ── محتوى تلقائي كل 30 دقيقة ───────────────────────────────────────────
    "auto_quran":       ("القرآن الكريم (تلقائي)",       "📖"),
    "auto_hadith":      ("الحديث النبوي (تلقائي)",       "📜"),
    "auto_dua":         ("الأدعية (تلقائية)",            "🤲"),
    "auto_story":       ("القصص الإسلامية (تلقائية)",    "📚"),
    "auto_fact":        ("المعلومات الإسلامية (تلقائية)","💡"),
    "auto_image":       ("الصور الإسلامية (تلقائية)",    "🖼️"),

    # ── مهام يومية مجدولة ──────────────────────────────────────────────────
    "adhan":            ("أذان أوقات الصلاة",            "🕌"),
    "morning_adhkar":   ("أذكار الصباح",                 "🌅"),
    "evening_adhkar":   ("أذكار المساء",                 "🌆"),
    "tasbih":           ("تذكير التسبيح اليومي",         "📿"),
    "word_of_day":      ("الكلمة القرآنية اليومية",      "🔤"),
    "name_of_day":      ("اسم الله الحسنى اليومي",       "🌟"),
    "good_deed":        ("العمل الصالح اليومي",          "🌱"),

    # ── ميزات إسلامية إضافية ───────────────────────────────────────────────
    "friday_reminder":  ("تذكير صلاة الجمعة",           "🕋"),
    "fasting_reminder": ("تذكير صيام الاثنين والخميس",  "🌙"),
    "seerah":           ("مقتطف السيرة النبوية اليومي",  "📕"),
    "quiz":             ("المسابقة الإسلامية",           "🏆"),

    # ── البث الصوتي ────────────────────────────────────────────────────────
    "voice_play":       ("بث يوتيوب (/play)",            "🎵"),
    "voice_radio":      ("راديو القرآن (/radio)",        "📻"),

    # ── تيك توك ────────────────────────────────────────────────────────────
    "tiktok":           ("تحميل تيك توك (/tiktok)",      "🎬"),
}

# الميزات المفعّلة افتراضياً لأي دردشة جديدة (كل شيء مفعّل)
DEFAULT_SETTINGS: dict[str, bool] = {key: True for key in FEATURES}


# ══════════════════════════════════════════════════════════════════════════════
#  قراءة وكتابة الإعدادات
# ══════════════════════════════════════════════════════════════════════════════

def _load_all() -> dict:
    if not SETTINGS_FILE.exists():
        return {}
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_all(data: dict) -> None:
    SETTINGS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_chat_settings(chat_id: int) -> dict[str, bool]:
    """يُرجع إعدادات الدردشة — يستخدم الافتراضي لأي مفتاح مفقود."""
    all_data = _load_all()
    saved = all_data.get(str(chat_id), {})
    # دمج: ما هو محفوظ + الافتراضي لأي ميزة جديدة لم تكن موجودة سابقاً
    return {**DEFAULT_SETTINGS, **saved}


def set_feature(chat_id: int, feature: str, enabled: bool) -> None:
    """يحفظ إعداد ميزة واحدة لدردشة محددة."""
    all_data = _load_all()
    key = str(chat_id)
    if key not in all_data:
        all_data[key] = dict(DEFAULT_SETTINGS)
    all_data[key][feature] = enabled
    _save_all(all_data)


def is_enabled(chat_id: int, feature: str) -> bool:
    """يتحقق إذا كانت ميزة معينة مفعّلة في دردشة معينة."""
    return get_chat_settings(chat_id).get(feature, True)


# ══════════════════════════════════════════════════════════════════════════════
#  بناء لوحة الأزرار
# ══════════════════════════════════════════════════════════════════════════════

def _build_keyboard(chat_id: int, page: int = 0) -> InlineKeyboardMarkup:
    settings  = get_chat_settings(chat_id)
    features  = list(FEATURES.items())

    # ── تقسيم الميزات إلى صفحات (7 ميزات لكل صفحة) ─────────────────────────
    page_size = 7
    total_pages = (len(features) + page_size - 1) // page_size
    page = max(0, min(page, total_pages - 1))
    page_features = features[page * page_size : (page + 1) * page_size]

    rows = []
    for key, (label, emoji) in page_features:
        enabled = settings.get(key, True)
        status  = "✅" if enabled else "❌"
        btn_label = f"{status} {emoji} {label}"
        rows.append([InlineKeyboardButton(
            btn_label,
            callback_data=f"cfg:{chat_id}:{key}:{page}",
        )])

    # ── أزرار التنقل بين الصفحات ─────────────────────────────────────────────
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ السابق", callback_data=f"cfg_page:{chat_id}:{page-1}"))
    nav.append(InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data="cfg_noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("▶️ التالي", callback_data=f"cfg_page:{chat_id}:{page+1}"))
    rows.append(nav)

    # ── أزرار تفعيل/تعطيل الكل ───────────────────────────────────────────────
    rows.append([
        InlineKeyboardButton("✅ تفعيل الكل",  callback_data=f"cfg_all:{chat_id}:1:{page}"),
        InlineKeyboardButton("❌ تعطيل الكل", callback_data=f"cfg_all:{chat_id}:0:{page}"),
    ])
    rows.append([InlineKeyboardButton("🔒 إغلاق", callback_data="cfg_close")])

    return InlineKeyboardMarkup(rows)


def _settings_header(chat_id: int) -> str:
    settings = get_chat_settings(chat_id)
    active   = sum(1 for v in settings.values() if v)
    total    = len(FEATURES)
    return (
        f"⚙️ <b>إعدادات البوت لهذه الدردشة</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ مفعّل: <b>{active}</b> من <b>{total}</b> ميزة\n\n"
        f"اضغط على أي ميزة لتفعيلها أو تعطيلها:"
    )


# ══════════════════════════════════════════════════════════════════════════════
#  معالج الأمر /settings
# ══════════════════════════════════════════════════════════════════════════════

async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user = update.effective_user

    # ── التحقق من صلاحية المشرف ──────────────────────────────────────────────
    if chat.type == "private":
        await update.effective_message.reply_text(
            "⚙️ الإعدادات متاحة فقط داخل المجموعات والقنوات."
        )
        return

    if chat.type in ("group", "supergroup"):
        try:
            member = await chat.get_member(user.id)
            if member.status not in ("administrator", "creator"):
                await update.effective_message.reply_text(
                    "⛔ هذا الأمر متاح للمشرفين فقط."
                )
                return
        except Exception:
            pass

    await update.effective_message.reply_text(
        _settings_header(chat.id),
        parse_mode=ParseMode.HTML,
        reply_markup=_build_keyboard(chat.id, page=0),
    )


# ══════════════════════════════════════════════════════════════════════════════
#  معالج ضغط الأزرار
# ══════════════════════════════════════════════════════════════════════════════

async def callback_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    data = query.data

    # ── إغلاق ────────────────────────────────────────────────────────────────
    if data == "cfg_close":
        await query.message.delete()
        return

    # ── زر بلا فعل ───────────────────────────────────────────────────────────
    if data == "cfg_noop":
        return

    # ── تغيير صفحة ───────────────────────────────────────────────────────────
    if data.startswith("cfg_page:"):
        _, chat_id, page = data.split(":")
        chat_id, page = int(chat_id), int(page)
        await query.edit_message_text(
            _settings_header(chat_id),
            parse_mode=ParseMode.HTML,
            reply_markup=_build_keyboard(chat_id, page),
        )
        return

    # ── تفعيل/تعطيل الكل ─────────────────────────────────────────────────────
    if data.startswith("cfg_all:"):
        _, chat_id, val, page = data.split(":")
        chat_id, val, page = int(chat_id), bool(int(val)), int(page)
        all_data = _load_all()
        all_data[str(chat_id)] = {key: val for key in FEATURES}
        _save_all(all_data)
        label = "تم تفعيل جميع الميزات ✅" if val else "تم تعطيل جميع الميزات ❌"
        await query.answer(label, show_alert=True)
        await query.edit_message_text(
            _settings_header(chat_id),
            parse_mode=ParseMode.HTML,
            reply_markup=_build_keyboard(chat_id, page),
        )
        return

    # ── تبديل ميزة واحدة ─────────────────────────────────────────────────────
    if data.startswith("cfg:"):
        _, chat_id, feature, page = data.split(":", 3)
        chat_id, page = int(chat_id), int(page)
        current = is_enabled(chat_id, feature)
        set_feature(chat_id, feature, not current)
        feat_label = FEATURES.get(feature, (feature, ""))[0]
        status_label = "مفعّلة ✅" if not current else "معطّلة ❌"
        await query.answer(f"{feat_label} — {status_label}")
        await query.edit_message_text(
            _settings_header(chat_id),
            parse_mode=ParseMode.HTML,
            reply_markup=_build_keyboard(chat_id, page),
        )
        return


# ══════════════════════════════════════════════════════════════════════════════
#  تسجيل الـ handlers — يُستدعى من bot.py
# ══════════════════════════════════════════════════════════════════════════════

def register_handlers(app) -> None:
    from telegram.ext import CommandHandler
    app.add_handler(CommandHandler("settings", cmd_settings))
    app.add_handler(CallbackQueryHandler(
        callback_settings,
        pattern=r"^(cfg:|cfg_page:|cfg_all:|cfg_close|cfg_noop)",
    ))
    logger.info("✅ chat_settings: handlers مسجّلون")
