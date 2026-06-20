#!/usr/bin/env python3
"""
image_broadcast.py — نظام نشر الصور والفيديوهات الإسلامية

المصادر المدعومة (بالأولوية):
  1. Local folder  : images/ و videos/ — ترفعها عبر التيليغرام أو يدوياً
  2. Telegram channel: يجلب الصور من قناة عامة عبر Telethon
  3. GitHub raw    : repos عامة تحتوي صور إسلامية

الميزات الجديدة:
  - رفع صور/فيديوهات مباشرة للبوت عبر التيليغرام → تُحفظ تلقائياً
  - /media لتصفح ما هو مخزّن مع عدادات
  - فيديوهات مدرجة في الروتاسيون العشوائي جنب الصور
"""

import asyncio
import logging
import random
from pathlib import Path

logger = logging.getLogger("ImageBroadcast")

# ══════════════════════════════════════════════════════════════════════════════
#  الإعدادات
# ══════════════════════════════════════════════════════════════════════════════

LOCAL_IMAGES_DIR = Path(__file__).parent / "images"
LOCAL_VIDEOS_DIR = Path(__file__).parent / "videos"
LOCAL_IMAGES_DIR.mkdir(exist_ok=True)
LOCAL_VIDEOS_DIR.mkdir(exist_ok=True)

# ══════════════════════════════════════════════════════════════════════════════
#  ربط الإعدادات بـ config.py (مع قيم احتياطية عند الغياب)
# ══════════════════════════════════════════════════════════════════════════════
try:
    import config as _cfg
    # معرفات المشرفين المسموح لهم برفع/حذف الميديا (فارغة = الكل)
    UPLOAD_ADMIN_IDS: list[int] = list(getattr(_cfg, "UPLOAD_ADMIN_IDS", []) or [])
    # قناة تيليغرام لسحب الصور منها (قناة عامة، بدون @)
    SOURCE_CHANNEL = getattr(_cfg, "IMAGE_SOURCE_CHANNEL", "") or "al3ilmelnafe3"
    # روابط GitHub raw للصور الإسلامية المباشرة
    GITHUB_IMAGE_URLS = list(getattr(_cfg, "GITHUB_IMAGE_URLS", []) or [])
    # اسم البوت الظاهر في caption الافتراضي
    BOT_BRAND_NAME = getattr(_cfg, "BOT_BRAND_NAME", "1001 Islam")
except Exception:
    UPLOAD_ADMIN_IDS   = []
    SOURCE_CHANNEL     = "al3ilmelnafe3"
    GITHUB_IMAGE_URLS  = []
    BOT_BRAND_NAME     = "1001 Islam"

# الامتدادات المقبولة
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}

# تسميات الفئات للـ caption (اسم البوت مأخوذ من config.BOT_BRAND_NAME)
CATEGORY_CAPTIONS = {
    "morning":  "🌅 أذكار الصباح",
    "evening":  "🌆 أذكار المساء",
    "sleep":    "🌙 أذكار النوم",
    "quran":    "📖 من كتاب الله الكريم",
    "hadith":   "📜 حديث نبوي شريف",
    "jumaa":    "🕌 فضائل يوم الجمعة",
    "dua":      "🤲 دعاء مأثور",
    "seerah":   "📜 من السيرة النبوية",
    "default":  f"🌿 <b>{BOT_BRAND_NAME}</b>",
}

# ══════════════════════════════════════════════════════════════════════════════
#  المصادر المحلية
# ══════════════════════════════════════════════════════════════════════════════

def get_local_images() -> list[Path]:
    return [f for f in LOCAL_IMAGES_DIR.iterdir()
            if f.suffix.lower() in IMAGE_EXTENSIONS]

def get_local_videos() -> list[Path]:
    return [f for f in LOCAL_VIDEOS_DIR.iterdir()
            if f.suffix.lower() in VIDEO_EXTENSIONS]

def get_all_local_media() -> list[tuple[Path, str]]:
    """يعيد قائمة (path, type) لكل الميديا المتاحة."""
    items = [(p, "image") for p in get_local_images()]
    items += [(p, "video") for p in get_local_videos()]
    return items

def _guess_caption(filename: str) -> str:
    name = filename.lower()
    for key, caption in CATEGORY_CAPTIONS.items():
        if key in name:
            return caption
    return CATEGORY_CAPTIONS["default"]

async def send_local_image(bot, chat_id: int, image_path: Path) -> bool:
    caption = _guess_caption(image_path.stem)
    try:
        with open(image_path, "rb") as f:
            await bot.send_photo(chat_id=chat_id, photo=f,
                                 caption=caption, parse_mode="HTML")
        return True
    except Exception as e:
        logger.error(f"فشل إرسال الصورة {image_path.name} إلى {chat_id}: {e}")
        return False

async def send_local_video(bot, chat_id: int, video_path: Path) -> bool:
    caption = _guess_caption(video_path.stem)
    try:
        with open(video_path, "rb") as f:
            await bot.send_video(chat_id=chat_id, video=f,
                                 caption=caption, parse_mode="HTML",
                                 supports_streaming=True)
        return True
    except Exception as e:
        logger.error(f"فشل إرسال الفيديو {video_path.name} إلى {chat_id}: {e}")
        return False

# ══════════════════════════════════════════════════════════════════════════════
#  المصدر 2: قناة تيليغرام عبر Telethon
# ══════════════════════════════════════════════════════════════════════════════

_channel_photo_cache: list[str] = []
_cache_loaded: bool = False

async def _load_channel_photos(api_id, api_hash, session_name, limit=50):
    global _channel_photo_cache, _cache_loaded
    if _cache_loaded:
        return
    try:
        from telethon import TelegramClient
        from telethon.tl.types import MessageMediaPhoto
        client = TelegramClient(session_name, api_id, api_hash)
        await client.start()
        collected = []
        async for msg in client.iter_messages(SOURCE_CHANNEL, limit=limit):
            if msg.media and isinstance(msg.media, MessageMediaPhoto):
                collected.append(msg.id)
        await client.disconnect()
        _channel_photo_cache = collected
        _cache_loaded = True
        logger.info(f"✅ تم سحب {len(collected)} صورة من @{SOURCE_CHANNEL}")
    except ImportError:
        logger.warning("Telethon غير مثبت — تخطي مصدر القناة")
    except Exception as e:
        logger.error(f"فشل سحب صور القناة: {e}")

async def send_channel_photo(bot, chat_id, api_id, api_hash, session_name) -> bool:
    global _channel_photo_cache
    if not _channel_photo_cache:
        await _load_channel_photos(api_id, api_hash, session_name)
    if not _channel_photo_cache:
        return False
    try:
        from telethon import TelegramClient
        msg_id = random.choice(_channel_photo_cache)
        client = TelegramClient(session_name, api_id, api_hash)
        await client.start()
        await client.forward_messages(entity=chat_id, messages=msg_id,
                                      from_peer=SOURCE_CHANNEL)
        await client.disconnect()
        return True
    except Exception as e:
        logger.error(f"فشل forward الصورة إلى {chat_id}: {e}")
        return False

# ══════════════════════════════════════════════════════════════════════════════
#  المصدر 3: GitHub raw URLs
# ══════════════════════════════════════════════════════════════════════════════

async def send_github_image(bot, chat_id, url, caption="") -> bool:
    if not caption:
        caption = CATEGORY_CAPTIONS["default"]
    try:
        await bot.send_photo(chat_id=chat_id, photo=url,
                             caption=caption, parse_mode="HTML")
        return True
    except Exception as e:
        logger.error(f"فشل إرسال صورة GitHub إلى {chat_id}: {e}")
        return False

# ══════════════════════════════════════════════════════════════════════════════
#  الواجهة الرئيسية — broadcast_image
# ══════════════════════════════════════════════════════════════════════════════

async def broadcast_image(bot, chats: list[int], api_id=0, api_hash="", session_name="") -> bool:
    """
    ينشر صورة أو فيديو عشوائي لجميع الدردشات.
    يجرب المصادر: Local (صور+فيديو) → GitHub → Telegram Channel
    """
    # ── ميديا محلية (صور + فيديوهات) ─────────────────────────────────────
    all_media = get_all_local_media()
    if all_media:
        media_path, media_type = random.choice(all_media)
        logger.info(f"📸 نشر {media_type} محلي: {media_path.name}")
        success = True
        for chat_id in chats:
            if media_type == "video":
                ok = await send_local_video(bot, chat_id, media_path)
            else:
                ok = await send_local_image(bot, chat_id, media_path)
            if not ok:
                success = False
            await asyncio.sleep(0.5)
        return success

    # ── GitHub raw ─────────────────────────────────────────────────────────
    if GITHUB_IMAGE_URLS:
        url = random.choice(GITHUB_IMAGE_URLS)
        logger.info(f"📸 نشر صورة GitHub: {url}")
        success = True
        for chat_id in chats:
            ok = await send_github_image(bot, chat_id, url)
            if not ok:
                success = False
            await asyncio.sleep(0.5)
        return success

    # ── قناة تيليغرام ─────────────────────────────────────────────────────
    if api_id and api_hash and session_name:
        logger.info(f"📸 نشر صورة من @{SOURCE_CHANNEL}")
        success = True
        for chat_id in chats:
            ok = await send_channel_photo(bot, chat_id, api_id, api_hash, session_name)
            if not ok:
                success = False
            await asyncio.sleep(0.5)
        return success

    logger.warning("⚠️  لا توجد ميديا متاحة — أرفع صوراً أو فيديوهات للبوت")
    return False

# ══════════════════════════════════════════════════════════════════════════════
#  رفع الميديا عبر التيليغرام — يحفظ الصور والفيديوهات تلقائياً
# ══════════════════════════════════════════════════════════════════════════════

async def handle_media_upload(update, context):
    """
    معالج الصور والفيديوهات المُرسلة للبوت مباشرة.
    يحفظها في images/ أو videos/ تلقائياً.
    أرسل أي صورة أو فيديو للبوت في الخاص وسيُحفظ تلقائياً.
    """
    user = update.effective_user
    msg = update.effective_message

    # فحص الصلاحية
    if UPLOAD_ADMIN_IDS and user.id not in UPLOAD_ADMIN_IDS:
        return  # تجاهل بدون رد

    # ── صورة ──────────────────────────────────────────────────────────────
    if msg.photo:
        photo = msg.photo[-1]  # أعلى جودة
        file = await context.bot.get_file(photo.file_id)
        # اسم الملف من caption أو تلقائي
        caption = (msg.caption or "").strip()
        filename = f"{caption[:30].replace(' ', '_') or photo.file_unique_id}.jpg"
        save_path = LOCAL_IMAGES_DIR / filename
        await file.download_to_drive(save_path)
        total = len(get_local_images())
        await msg.reply_text(
            f"✅ <b>تم حفظ الصورة</b>\n\n"
            f"📁 <code>images/{filename}</code>\n"
            f"🖼️ إجمالي الصور: <b>{total}</b>",
            parse_mode="HTML",
        )
        logger.info(f"📥 صورة جديدة محفوظة: {filename} (من {user.id})")

    # ── فيديو ──────────────────────────────────────────────────────────────
    elif msg.video or msg.document:
        media = msg.video or msg.document
        # تحقق من امتداد الـ document
        if msg.document:
            fname = msg.document.file_name or ""
            if Path(fname).suffix.lower() not in VIDEO_EXTENSIONS:
                return  # مش فيديو
        file = await context.bot.get_file(media.file_id)
        caption = (msg.caption or "").strip()
        ext = ".mp4"
        if msg.document and msg.document.file_name:
            ext = Path(msg.document.file_name).suffix.lower()
        filename = f"{caption[:30].replace(' ', '_') or media.file_unique_id}{ext}"
        save_path = LOCAL_VIDEOS_DIR / filename
        await file.download_to_drive(save_path)
        size_mb = save_path.stat().st_size / (1024 * 1024)
        total = len(get_local_videos())
        await msg.reply_text(
            f"✅ <b>تم حفظ الفيديو</b>\n\n"
            f"📁 <code>videos/{filename}</code>\n"
            f"📦 الحجم: <b>{size_mb:.1f} MB</b>\n"
            f"🎬 إجمالي الفيديوهات: <b>{total}</b>",
            parse_mode="HTML",
        )
        logger.info(f"📥 فيديو جديد محفوظ: {filename} ({size_mb:.1f} MB، من {user.id})")


# ══════════════════════════════════════════════════════════════════════════════
#  أمر /media — عرض الميديا المخزّنة
# ══════════════════════════════════════════════════════════════════════════════

async def cmd_media(update, context):
    """
    /media — يعرض ملخص الميديا المخزّنة مع أزرار للإرسال الفوري.
    """
    images = get_local_images()
    videos = get_local_videos()

    if not images and not videos:
        await update.effective_message.reply_text(
            "📂 <b>المكتبة فارغة</b>\n\n"
            "أرسل للبوت أي صورة أو فيديو في الخاص وسيُحفظ تلقائياً.\n"
            "أو استخدم /tiktok لتحميل فيديوهات تيك توك وإضافتها.\n"
            "يمكنك إرسال caption مع الملف كاسم له.",
            parse_mode="HTML",
        )
        return

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    # تمييز فيديوهات تيك توك عن الفيديوهات العادية
    tiktok_videos = [v for v in videos if v.stem.startswith("tiktok_") or "_tiktok" in v.stem.lower()]
    other_videos  = [v for v in videos if v not in tiktok_videos]

    # ملخص الملفات
    img_list = "\n".join(f"  • {p.name}" for p in images[:8])
    vid_list = "\n".join(f"  • {p.name}" for p in other_videos[:5])
    tt_list  = "\n".join(f"  • {p.name}" for p in tiktok_videos[:5])
    more_imgs = f"\n  <i>... و{len(images)-8} أخرى</i>" if len(images) > 8 else ""
    more_vids = f"\n  <i>... و{len(other_videos)-5} أخرى</i>" if len(other_videos) > 5 else ""
    more_tt   = f"\n  <i>... و{len(tiktok_videos)-5} أخرى</i>" if len(tiktok_videos) > 5 else ""

    tt_section = ""
    if tiktok_videos:
        tt_section = f"\n🎬 <b>فيديوهات تيك توك ({len(tiktok_videos)})</b>\n{tt_list}{more_tt}\n"

    text = (
        f"📂 <b>مكتبة الميديا — {BOT_BRAND_NAME}</b>\n\n"
        f"🖼️ <b>الصور ({len(images)})</b>\n{img_list}{more_imgs}\n\n"
        f"🎥 <b>فيديوهات أخرى ({len(other_videos)})</b>\n{vid_list or '  لا يوجد'}{more_vids}\n"
        f"{tt_section}\n"
        f"📊 <b>الإجمالي: {len(images) + len(videos)} ملف</b>\n\n"
        f"<i>لإضافة فيديو تيك توك: /tiktok [رابط] ثم اختر حفظه</i>"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📸 إرسال صورة عشوائية الآن", callback_data="media_send|image")],
        [InlineKeyboardButton("🎬 إرسال فيديو عشوائي الآن", callback_data="media_send|video")],
    ])

    await update.effective_message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)


async def callback_media(update, context):
    """معالج أزرار /media"""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    if UPLOAD_ADMIN_IDS and user.id not in UPLOAD_ADMIN_IDS:
        await query.answer("⛔ للمشرفين فقط", show_alert=True)
        return

    _, media_type = query.data.split("|")
    chat_id = query.message.chat_id

    try:
        import config
        if media_type == "image":
            images = get_local_images()
            if not images:
                await query.answer("لا توجد صور محفوظة", show_alert=True)
                return
            await send_local_image(context.bot, chat_id, random.choice(images))
        else:
            videos = get_local_videos()
            if not videos:
                await query.answer("لا توجد فيديوهات محفوظة", show_alert=True)
                return
            await send_local_video(context.bot, chat_id, random.choice(videos))
    except Exception as e:
        await query.answer(f"خطأ: {e}", show_alert=True)


# ══════════════════════════════════════════════════════════════════════════════
#  أمر /sendimage للمشرفين
# ══════════════════════════════════════════════════════════════════════════════

async def cmd_sendimage(update, context):
    """/sendimage — يُرسل ميديا عشوائية للدردشة الحالية فوراً."""
    chat = update.effective_chat
    user = update.effective_user

    if chat.type not in ["private"]:
        try:
            member = await chat.get_member(user.id)
            if member.status not in ["administrator", "creator"]:
                await update.effective_message.reply_text("⚠️ هذا الأمر للمشرفين فقط.")
                return
        except Exception:
            pass

    try:
        import config
        await update.effective_message.reply_text("⏳ جاري اختيار ميديا وإرسالها...")
        ok = await broadcast_image(
            bot=context.bot,
            chats=[chat.id],
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_name=config.SESSION_NAME,
        )
        if not ok:
            await update.effective_message.reply_text(
                "❌ لا توجد ميديا متاحة.\n\n"
                "📂 أرسل للبوت صورة أو فيديو في الخاص لإضافتها.",
                parse_mode="HTML",
            )
    except Exception as e:
        await update.effective_message.reply_text(f"❌ خطأ: <code>{e}</code>", parse_mode="HTML")


# ══════════════════════════════════════════════════════════════════════════════
#  تسجيل الـ handlers في bot.py
# ══════════════════════════════════════════════════════════════════════════════



# ══════════════════════════════════════════════════════════════════════════════
#  أمر /deletemedia — حذف الصور والفيديوهات عبر قائمة تفاعلية
# ══════════════════════════════════════════════════════════════════════════════

_DELETE_PAGE_SIZE = 8   # عدد الملفات في كل صفحة


def _build_delete_keyboard(media_type: str, page: int) -> "InlineKeyboardMarkup":
    """يبني لوحة أزرار قائمة الحذف."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    files = get_local_images() if media_type == "img" else get_local_videos()
    total = len(files)
    total_pages = max(1, (total + _DELETE_PAGE_SIZE - 1) // _DELETE_PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    page_files = files[page * _DELETE_PAGE_SIZE : (page + 1) * _DELETE_PAGE_SIZE]

    rows = []
    for f in page_files:
        size_kb = f.stat().st_size // 1024
        label = f"🗑 {f.name[:35]}  ({size_kb} KB)"
        rows.append([InlineKeyboardButton(
            label,
            callback_data=f"del_confirm|{media_type}|{f.name}|{page}",
        )])

    # أزرار التنقل
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"del_page|{media_type}|{page-1}"))
    nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}  ({total} ملف)", callback_data="del_noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"del_page|{media_type}|{page+1}"))
    if nav:
        rows.append(nav)

    # تبديل نوع الميديا
    switch_type  = "vid" if media_type == "img" else "img"
    switch_label = "🎬 عرض الفيديوهات" if media_type == "img" else "🖼️ عرض الصور"
    rows.append([
        InlineKeyboardButton(switch_label, callback_data=f"del_page|{switch_type}|0"),
        InlineKeyboardButton("🔒 إغلاق",   callback_data="del_close"),
    ])

    return InlineKeyboardMarkup(rows)


def _delete_header(media_type: str) -> str:
    imgs = get_local_images()
    vids = get_local_videos()
    kind = "الصور 🖼️" if media_type == "img" else "الفيديوهات 🎬"
    return (
        f"🗑️ <b>حذف الميديا — {kind}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🖼️ الصور: <b>{len(imgs)}</b>   🎬 الفيديوهات: <b>{len(vids)}</b>\n\n"
        f"اضغط على أي ملف لحذفه:"
    )


async def cmd_deletemedia(update, context):
    """/deletemedia — عرض قائمة الملفات مع زر حذف لكل ملف."""
    user = update.effective_user
    if UPLOAD_ADMIN_IDS and user.id not in UPLOAD_ADMIN_IDS:
        await update.effective_message.reply_text("⛔ هذا الأمر للمشرفين فقط.")
        return

    images = get_local_images()
    videos = get_local_videos()
    if not images and not videos:
        await update.effective_message.reply_text(
            "📂 المكتبة فارغة — لا توجد صور أو فيديوهات محفوظة."
        )
        return

    # ابدأ بالصور إذا موجودة، وإلا الفيديوهات
    start_type = "img" if images else "vid"
    await update.effective_message.reply_text(
        _delete_header(start_type),
        parse_mode="HTML",
        reply_markup=_build_delete_keyboard(start_type, 0),
    )


async def callback_deletemedia(update, context):
    """معالج أزرار /deletemedia."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    if UPLOAD_ADMIN_IDS and user.id not in UPLOAD_ADMIN_IDS:
        await query.answer("⛔ للمشرفين فقط", show_alert=True)
        return

    data = query.data

    if data == "del_close":
        await query.message.delete()
        return

    if data == "del_noop":
        return

    # ── تغيير الصفحة أو تبديل النوع ─────────────────────────────────────────
    if data.startswith("del_page|"):
        _, media_type, page = data.split("|")
        page = int(page)
        files = get_local_images() if media_type == "img" else get_local_videos()
        if not files:
            await query.answer("لا توجد ملفات من هذا النوع", show_alert=True)
            return
        await query.edit_message_text(
            _delete_header(media_type),
            parse_mode="HTML",
            reply_markup=_build_delete_keyboard(media_type, page),
        )
        return

    # ── طلب تأكيد الحذف ──────────────────────────────────────────────────────
    if data.startswith("del_confirm|"):
        _, media_type, filename, page = data.split("|", 3)
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "✅ نعم، احذفه",
                callback_data=f"del_do|{media_type}|{filename}|{page}",
            ),
            InlineKeyboardButton(
                "❌ إلغاء",
                callback_data=f"del_page|{media_type}|{page}",
            ),
        ]])
        await query.edit_message_text(
            f"⚠️ <b>تأكيد الحذف</b>\n\n"
            f"هل تريد حذف الملف:\n"
            f"<code>{filename}</code>\n\n"
            f"هذا الإجراء لا يمكن التراجع عنه.",
            parse_mode="HTML",
            reply_markup=keyboard,
        )
        return

    # ── تنفيذ الحذف ───────────────────────────────────────────────────────────
    if data.startswith("del_do|"):
        _, media_type, filename, page = data.split("|", 3)
        page = int(page)
        folder = LOCAL_IMAGES_DIR if media_type == "img" else LOCAL_VIDEOS_DIR
        file_path = folder / filename

        if not file_path.exists():
            await query.answer("⚠️ الملف غير موجود — ربما حُذف مسبقاً", show_alert=True)
        else:
            try:
                file_path.unlink()
                logger.info(f"🗑️ تم حذف: {file_path}")
                await query.answer(f"✅ تم حذف {filename}")
            except Exception as e:
                logger.error(f"فشل حذف {file_path}: {e}")
                await query.answer(f"❌ فشل الحذف: {e}", show_alert=True)
                return

        # إعادة تحميل القائمة بعد الحذف
        files = get_local_images() if media_type == "img" else get_local_videos()
        if not files:
            # تحقق من النوع الآخر
            other_type = "vid" if media_type == "img" else "img"
            other_files = get_local_images() if other_type == "img" else get_local_videos()
            if not other_files:
                await query.edit_message_text("📂 المكتبة فارغة الآن — تم حذف كل الملفات.")
                return
            # انتقل للنوع الآخر
            await query.edit_message_text(
                _delete_header(other_type),
                parse_mode="HTML",
                reply_markup=_build_delete_keyboard(other_type, 0),
            )
            return

        # اضبط الصفحة إذا صارت فارغة بعد الحذف
        total_pages = max(1, (len(files) + _DELETE_PAGE_SIZE - 1) // _DELETE_PAGE_SIZE)
        page = min(page, total_pages - 1)
        await query.edit_message_text(
            _delete_header(media_type),
            parse_mode="HTML",
            reply_markup=_build_delete_keyboard(media_type, page),
        )
        return

def register_handlers(app):
    from telegram.ext import CommandHandler, MessageHandler, CallbackQueryHandler, filters

    app.add_handler(CommandHandler("sendimage",    cmd_sendimage))
    app.add_handler(CommandHandler("media",        cmd_media))
    app.add_handler(CommandHandler("deletemedia",  cmd_deletemedia))
    app.add_handler(CallbackQueryHandler(callback_media,       pattern=r"^media_send\|"))
    app.add_handler(CallbackQueryHandler(callback_deletemedia, pattern=r"^del_(page|confirm|do|close|noop)"))

    # معالج رفع الميديا — يعمل فقط في المحادثات الخاصة
    app.add_handler(MessageHandler(
        filters.PHOTO & filters.ChatType.PRIVATE,
        handle_media_upload,
    ))
    app.add_handler(MessageHandler(
        (filters.VIDEO | filters.Document.VIDEO) & filters.ChatType.PRIVATE,
        handle_media_upload,
    ))

    logger.info("✅ image_broadcast: /sendimage + /media + /deletemedia + رفع الميديا مُفعَّل")
