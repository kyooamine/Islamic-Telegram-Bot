#!/usr/bin/env python3
"""
tiktok_downloader.py — تحميل فيديوهات تيك توك بدون علامة مائية
================================================================
الميزات:
  - إرسال رابط تيك توك مباشرة في الدردشة (بدون أي أمر) — يكتشفه البوت
    تلقائياً ويحمّله ويرسله بأعلى جودة بدون watermark
  - /tiktok <رابط> — لا يزال يعمل أيضاً لمن يفضّل استخدام الأمر صراحة
  - بعد الإرسال، يُعطى المشرف خيار حفظ الفيديو في مجلد videos/
    ليُدرج في النشر التلقائي العشوائي للمجموعات والقنوات

المتطلبات:
    pip install yt-dlp aiohttp

التفعيل في bot.py — أضف هذه الأسطر في دالة main() بجانب باقي register_handlers:
    try:
        import tiktok_downloader
        tiktok_downloader.register_handlers(app)
    except ImportError:
        logger.info("ℹ️  tiktok_downloader.py غير موجود")
"""

import asyncio
import logging
import os
import re
import tempfile
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters,
)
from telegram.constants import ParseMode

logger = logging.getLogger("TikTokDownloader")

# ══════════════════════════════════════════════════════════════════════════════
#  الإعدادات
# ══════════════════════════════════════════════════════════════════════════════

try:
    import config as _cfg
    ADMIN_IDS: set[int] = set(getattr(_cfg, "ALLOWED_USER_IDS", []) or [])
    BOT_BRAND_NAME: str = getattr(_cfg, "BOT_BRAND_NAME", "البوت الإسلامي")
except Exception:
    ADMIN_IDS = set()
    BOT_BRAND_NAME = "البوت الإسلامي"

# مجلد حفظ الفيديوهات (نفس المجلد الذي يستخدمه image_broadcast.py)
VIDEOS_DIR = Path(__file__).parent / "videos"
VIDEOS_DIR.mkdir(exist_ok=True)

# الحد الأقصى لحجم الفيديو قبل الرفع لتيليغرام (50 MB — حد Telegram Bot API)
MAX_VIDEO_MB = 50

# نمط روابط تيك توك المقبولة
TIKTOK_PATTERN = re.compile(
    r"https?://(www\.|vm\.|vt\.|m\.)?tiktok\.com/[@\w/.?\-=&%]+",
    re.IGNORECASE,
)


# ══════════════════════════════════════════════════════════════════════════════
#  دوال مساعدة
# ══════════════════════════════════════════════════════════════════════════════

def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def _is_tiktok_url(text: str) -> bool:
    return bool(TIKTOK_PATTERN.search(text))


def _clean_filename(title: str) -> str:
    """تنظيف عنوان الفيديو ليصلح اسماً للملف."""
    cleaned = re.sub(r'[^\w\u0600-\u06FF\s-]', '', title)
    cleaned = re.sub(r'\s+', '_', cleaned.strip())
    return cleaned[:60] or "tiktok_video"


async def _download_tiktok(url: str, output_dir: Path) -> dict:
    """
    يحمّل الفيديو باستخدام yt-dlp بأعلى جودة بدون watermark.
    يعيد dict: {ok, path, title, error}
    """
    try:
        import yt_dlp
    except ImportError:
        return {"ok": False, "error": "yt-dlp غير مثبّت — شغّل: pip install yt-dlp"}

    output_template = str(output_dir / "%(title).50s.%(ext)s")

    ydl_opts = {
        # أفضل جودة mp4 بدون watermark (TikTok يقدمه عبر API المباشر)
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": output_template,
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        # إعدادات تتجاوز الحماية وتجلب النسخة بدون watermark
        "extractor_args": {
            "tiktok": {
                "app_name": "trill",
                "app_version": "34.1.2",
            }
        },
        # User-Agent حديث
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        },
        # حجم أقصى 50 MB
        "max_filesize": MAX_VIDEO_MB * 1024 * 1024,
    }

    loop = asyncio.get_event_loop()

    def _do_download():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info is None:
                return None, "فشل استخراج معلومات الفيديو"
            # البحث عن الملف الذي تم تحميله
            filename = ydl.prepare_filename(info)
            # قد يكون mp4 بعد الدمج
            path = Path(filename)
            if not path.exists():
                path = path.with_suffix(".mp4")
            title = info.get("title", "TikTok Video")
            return path, title

    try:
        path, title = await loop.run_in_executor(None, _do_download)
        if path is None:
            return {"ok": False, "error": title}  # title هنا رسالة الخطأ
        if not path.exists():
            # البحث عن أي ملف mp4 تم إنشاؤه في المجلد
            mp4_files = list(output_dir.glob("*.mp4"))
            if mp4_files:
                # أحدث ملف
                path = max(mp4_files, key=lambda f: f.stat().st_mtime)
            else:
                return {"ok": False, "error": "الملف غير موجود بعد التحميل"}
        return {"ok": True, "path": path, "title": title}
    except Exception as e:
        err = str(e)
        logger.error(f"yt-dlp خطأ: {err}")
        return {"ok": False, "error": err[:300]}


# ══════════════════════════════════════════════════════════════════════════════
#  حالة مؤقتة لتتبع الفيديوهات المنتظرة (video_path لكل admin)
# ══════════════════════════════════════════════════════════════════════════════
# {message_id: {"path": Path, "title": str, "user_id": int}}
_pending: dict[int, dict] = {}


def _save_keyboard(msg_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "✅ حفظ في مجلد الفيديوهات",
            callback_data=f"tt_save:{msg_id}",
        ),
        InlineKeyboardButton(
            "❌ تجاهل",
            callback_data=f"tt_discard:{msg_id}",
        ),
    ]])


async def _handle_tiktok_url(update: Update, url: str) -> None:
    """
    المنطق المشترك: يحمّل رابط تيك توك بدون watermark ويرسله.
    تستدعيه كل من /tiktok وكاشف الروابط المباشرة في الرسائل.
    إذا كان المرسل مشرفاً يظهر خيار الحفظ في مجلد videos/.
    """
    user = update.effective_user
    msg  = update.effective_message

    status_msg = await msg.reply_text(
        "⏳ <b>جاري تحميل الفيديو...</b>\n"
        "قد يستغرق بضع ثوانٍ ⌛",
        parse_mode=ParseMode.HTML,
    )

    # التحميل في مجلد مؤقت أولاً
    with tempfile.TemporaryDirectory() as tmp_dir:
        result = await _download_tiktok(url, Path(tmp_dir))

        if not result["ok"]:
            err = result.get("error", "خطأ غير معروف")
            await status_msg.edit_text(
                f"❌ <b>فشل التحميل</b>\n\n"
                f"<code>{err}</code>\n\n"
                f"💡 تأكد من صحة الرابط أو حاول مرة أخرى.",
                parse_mode=ParseMode.HTML,
            )
            return

        video_path: Path = result["path"]
        title: str       = result["title"]

        # فحص الحجم
        size_bytes = video_path.stat().st_size
        size_mb    = size_bytes / (1024 * 1024)

        if size_mb > MAX_VIDEO_MB:
            await status_msg.edit_text(
                f"❌ الفيديو كبير جداً ({size_mb:.1f} MB)\n"
                f"الحد الأقصى المدعوم: {MAX_VIDEO_MB} MB."
            )
            return

        await status_msg.edit_text("📤 <b>جاري الإرسال...</b>", parse_mode=ParseMode.HTML)

        # هل المرسل مشرف؟
        is_admin = user and _is_admin(user.id)

        caption = (
            f"🎬 <b>{title}</b>\n\n"
            f"⬇️ تحميل بدون علامة مائية\n"
            f"🤖 {BOT_BRAND_NAME}"
        )

        try:
            with open(video_path, "rb") as vf:
                sent = await msg.reply_video(
                    video=vf,
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                    supports_streaming=True,
                )
        except Exception as e:
            await status_msg.edit_text(
                f"❌ فشل إرسال الفيديو: <code>{e}</code>",
                parse_mode=ParseMode.HTML,
            )
            return

        await status_msg.delete()

        # ── للمشرفين فقط: خيار الحفظ في مجلد الفيديوهات ──────────────────
        if is_admin:
            # نسخ الفيديو إلى مجلد مؤقت داخل مجلد البوت (خارج tmp الذي سيُحذف)
            safe_name = _clean_filename(title) + ".mp4"
            dest_path = VIDEOS_DIR / safe_name
            # إذا موجود نضيف رقماً
            counter = 1
            while dest_path.exists():
                dest_path = VIDEOS_DIR / f"{_clean_filename(title)}_{counter}.mp4"
                counter += 1

            # نسخ الملف لمجلد videos قبل أن يُحذف tmp
            import shutil
            shutil.copy2(video_path, dest_path)

            # نحفظ المسار في _pending
            msg_id = sent.message_id
            _pending[msg_id] = {
                "path":    dest_path,
                "title":   title,
                "user_id": user.id,
                # الملف نُسخ مسبقاً — save = إبقاء، discard = حذفه
            }

            await msg.reply_text(
                f"👤 <b>خيار المشرف</b>\n\n"
                f"هل تريد إضافة هذا الفيديو لمجلد الفيديوهات\n"
                f"ليُنشر تلقائياً في المجموعات والقنوات؟\n\n"
                f"🎬 <i>{title[:80]}</i>",
                parse_mode=ParseMode.HTML,
                reply_markup=_save_keyboard(msg_id),
            )
        # للمستخدمين العاديين لا يظهر خيار الحفظ — الفيديو يُرسل فقط


# ══════════════════════════════════════════════════════════════════════════════
#  معالج الأمر /tiktok
# ══════════════════════════════════════════════════════════════════════════════

async def cmd_tiktok(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /tiktok <رابط تيك توك>
    يحمّل الفيديو بدون watermark ويرسله.
    إذا كان المرسل مشرفاً يظهر خيار الحفظ في مجلد videos/.
    """
    msg = update.effective_message

    if not context.args:
        await msg.reply_text(
            "📌 <b>الاستخدام:</b>\n"
            "<code>/tiktok https://www.tiktok.com/@user/video/...</code>\n\n"
            "💡 أو فقط أرسل رابط تيك توك مباشرة بدون أي أمر.\n"
            "⬇️ يحمّل الفيديو بأعلى جودة بدون علامة مائية.",
            parse_mode=ParseMode.HTML,
        )
        return

    url = context.args[0].strip()

    if not _is_tiktok_url(url):
        await msg.reply_text(
            "❌ الرابط غير صحيح.\n"
            "تأكد أنه رابط تيك توك صحيح مثل:\n"
            "<code>https://www.tiktok.com/@user/video/123456</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    await _handle_tiktok_url(update, url)


# ══════════════════════════════════════════════════════════════════════════════
#  معالج اكتشاف رابط تيك توك المُرسَل مباشرة (بدون أمر)
# ══════════════════════════════════════════════════════════════════════════════

async def handle_tiktok_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    يعمل على أي رسالة نصية عادية تحتوي رابط تيك توك (بدون /tiktok).
    يتجاهل الرسائل التي هي أوامر فعلاً حتى لا يتعارض مع cmd_tiktok.
    """
    msg = update.effective_message
    if not msg or not msg.text:
        return

    text = msg.text.strip()
    if text.startswith("/"):
        return  # الأوامر تُعالَج عبر cmd_tiktok

    if not _is_tiktok_url(text):
        return

    # احترام إعدادات الدردشة (/settings) إن كانت ميزة tiktok معطّلة
    chat = update.effective_chat
    if chat is not None:
        try:
            import chat_settings as _cs
            if not _cs.is_enabled(chat.id, "tiktok"):
                return
        except ImportError:
            pass

    match = TIKTOK_PATTERN.search(text)
    url = match.group(0) if match else text

    await _handle_tiktok_url(update, url)


# ══════════════════════════════════════════════════════════════════════════════
#  معالج أزرار الحفظ / التجاهل
# ══════════════════════════════════════════════════════════════════════════════

async def callback_tiktok(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user  = query.from_user
    await query.answer()

    if not _is_admin(user.id):
        await query.answer("⛔ هذا الخيار للمشرفين فقط.", show_alert=True)
        return

    data = query.data  # tt_save:<msg_id>  أو  tt_discard:<msg_id>
    action, msg_id_str = data.split(":", 1)
    msg_id = int(msg_id_str)

    pending = _pending.pop(msg_id, None)
    if pending is None:
        await query.edit_message_text("⚠️ انتهت صلاحية هذا الخيار.")
        return

    dest_path: Path = pending["path"]
    title: str      = pending["title"]

    if action == "tt_save":
        # الملف موجود فعلاً في videos/ — لا نحتاج نسخ مجدداً
        if dest_path.exists():
            await query.edit_message_text(
                f"✅ <b>تم الحفظ في مجلد الفيديوهات</b>\n\n"
                f"🎬 <i>{title[:80]}</i>\n"
                f"📁 <code>videos/{dest_path.name}</code>\n\n"
                f"سيُنشر هذا الفيديو تلقائياً عند الدور القادم.",
                parse_mode=ParseMode.HTML,
            )
            logger.info(f"✅ تيك توك محفوظ: {dest_path.name} بواسطة {user.id}")
        else:
            await query.edit_message_text("❌ الملف غير موجود — ربما حُذف.")

    elif action == "tt_discard":
        # حذف الملف الذي نُسخ مسبقاً
        try:
            if dest_path.exists():
                dest_path.unlink()
        except Exception as e:
            logger.warning(f"تعذّر حذف الملف المؤقت: {e}")
        await query.edit_message_text(
            "🗑️ تم تجاهل الفيديو — لن يُضاف لمجلد الفيديوهات.",
        )


# ══════════════════════════════════════════════════════════════════════════════
#  تسجيل المعالجات — يُستدعى من bot.py
# ══════════════════════════════════════════════════════════════════════════════

def register_handlers(app) -> None:
    app.add_handler(CommandHandler("tiktok", cmd_tiktok))
    app.add_handler(CallbackQueryHandler(
        callback_tiktok,
        pattern=r"^tt_(save|discard):\d+$",
    ))
    # اكتشاف رابط تيك توك المُرسَل مباشرة بدون /tiktok.
    # نسجّله في group منفصلة (group=5) حتى لا يتعارض مع أي MessageHandler
    # نصي آخر مسجَّل بنفس group الافتراضية (مثل الردود الإسلامية التلقائية
    # في new_features.py) — فكل المعالجات هنا تعمل بشكل مستقل عن بعضها.
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_tiktok_link,
    ), group=5)
    logger.info("✅ tiktok_downloader: handlers مسجّلون — /tiktok + اكتشاف الروابط المباشرة")
