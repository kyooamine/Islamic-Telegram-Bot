#!/usr/bin/env python3
"""
file_manager.py — إدارة ملفات البوت عبر تيليغرام
==================================================
الأوامر المتاحة (للمشرفين فقط — ALLOWED_USER_IDS في config.py):
  /files          — عرض ملفات المجلد الرئيسي
  /files <مجلد>  — عرض محتوى مجلد معين
  /getfile <اسم> — تنزيل ملف
  /delfile <اسم> — حذف ملف (يطلب تأكيداً)
  /mkdir <اسم>   — إنشاء مجلد جديد

رفع ملف: أرسل أي ملف للبوت في المحادثة الخاصة وسيُحفظ في المجلد الحالي.
"""

import logging
import os
import shutil
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters,
)
from telegram.constants import ParseMode

logger = logging.getLogger("FileManager")

try:
    import config
    ADMIN_IDS  = set(getattr(config, "ALLOWED_USER_IDS", []))
    BASE_DIR   = Path(config.__file__).parent
except Exception:
    ADMIN_IDS  = set()
    BASE_DIR   = Path(__file__).parent

# الامتدادات المحظورة (حماية من رفع ملفات خطرة)
BLOCKED_EXTENSIONS = {".exe", ".bat", ".sh", ".ps1", ".cmd", ".msi", ".dll"}

# الحجم الأقصى للرفع (20 ميجابايت)
MAX_UPLOAD_MB = 20

# ── حالة المستخدم (المجلد الحالي لكل مستخدم) ────────────────────────────────
_user_cwd: dict[int, Path] = {}

def _get_cwd(user_id: int) -> Path:
    p = _user_cwd.get(user_id, BASE_DIR)
    if not p.exists():
        p = BASE_DIR
    return p

def _set_cwd(user_id: int, path: Path):
    _user_cwd[user_id] = path


# ── التحقق من الصلاحية ───────────────────────────────────────────────────────

def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def _safe_path(base: Path, target: Path) -> bool:
    """يتأكد أن المسار داخل مجلد BASE_DIR فقط (منع path traversal)."""
    try:
        target.resolve().relative_to(BASE_DIR.resolve())
        return True
    except ValueError:
        return False


# ── بناء قائمة الملفات ───────────────────────────────────────────────────────

def _list_dir(path: Path) -> tuple[list[Path], list[Path]]:
    """يُرجع (المجلدات، الملفات) مرتبة."""
    dirs, files = [], []
    try:
        for item in sorted(path.iterdir()):
            if item.name.startswith("."):
                continue
            if item.is_dir():
                dirs.append(item)
            else:
                files.append(item)
    except PermissionError:
        pass
    return dirs, files


def _format_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def _build_file_list_text(path: Path, user_id: int) -> str:
    rel = path.relative_to(BASE_DIR) if path != BASE_DIR else Path(".")
    dirs, files = _list_dir(path)

    lines = [f"📁 <b>{rel}</b>\n"]

    if dirs:
        lines.append("📂 <b>المجلدات:</b>")
        for d in dirs:
            lines.append(f"  📂 {d.name}/")

    if files:
        lines.append("\n📄 <b>الملفات:</b>")
        for f in files:
            size = _format_size(f.stat().st_size)
            lines.append(f"  📄 {f.name}  <i>({size})</i>")

    if not dirs and not files:
        lines.append("⚠️ المجلد فارغ")

    lines.append(f"\n<i>المسار: {path.resolve()}</i>")
    return "\n".join(lines)


def _to_rel(path: Path) -> str:
    """يحوّل مسار مطلق إلى نسبي مختصر لاستخدامه في callback_data."""
    try:
        rel = path.resolve().relative_to(BASE_DIR.resolve())
        return str(rel) if str(rel) != "." else ""
    except ValueError:
        return ""


def _from_rel(rel: str) -> Path:
    """يحوّل مسار نسبي (من callback_data) إلى مسار مطلق."""
    if not rel or rel == ".":
        return BASE_DIR
    return (BASE_DIR / rel).resolve()


def _build_keyboard(path: Path, page: int = 0) -> InlineKeyboardMarkup:
    """لوحة أزرار للتنقل بين المجلدات وفتحها."""
    dirs, files = _list_dir(path)
    rows = []

    # ── أزرار المجلدات الفرعية ──────────────────────────────────────────────
    page_size = 8
    all_dirs = dirs
    total_pages = max(1, (len(all_dirs) + page_size - 1) // page_size)
    page = max(0, min(page, total_pages - 1))
    page_dirs = all_dirs[page * page_size:(page + 1) * page_size]

    path_rel = _to_rel(path)

    for d in page_dirs:
        d_rel = _to_rel(d)
        rows.append([InlineKeyboardButton(
            f"📂 {d.name}/",
            callback_data=f"fm_cd:{d_rel}",
        )])

    # ── التنقل بين الصفحات ──────────────────────────────────────────────────
    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton("◀️", callback_data=f"fm_pg:{path_rel}|{page-1}"))
        nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="fm_noop"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton("▶️", callback_data=f"fm_pg:{path_rel}|{page+1}"))
        rows.append(nav)

    # ── زر الرجوع للمجلد الأب ───────────────────────────────────────────────
    if path.resolve() != BASE_DIR.resolve():
        parent_rel = _to_rel(path.parent)
        rows.append([InlineKeyboardButton(
            "⬆️ رجوع للمجلد الأب",
            callback_data=f"fm_cd:{parent_rel}",
        )])

    rows.append([InlineKeyboardButton("🔄 تحديث", callback_data=f"fm_rf:{path_rel}")])
    rows.append([InlineKeyboardButton("❌ إغلاق", callback_data="fm_close")])
    return InlineKeyboardMarkup(rows)


# ══════════════════════════════════════════════════════════════════════════════
#  الأوامر
# ══════════════════════════════════════════════════════════════════════════════

async def cmd_files(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /files          — عرض المجلد الحالي
    /files <مجلد>  — فتح مجلد معين
    """
    user = update.effective_user
    if not user or not _is_admin(user.id):
        await update.effective_message.reply_text("⛔ هذا الأمر للمشرفين فقط.")
        return

    if context.args:
        target = BASE_DIR / " ".join(context.args)
        target = target.resolve()
        if not _safe_path(BASE_DIR, target) or not target.is_dir():
            await update.effective_message.reply_text("❌ المجلد غير موجود أو خارج نطاق البوت.")
            return
    else:
        target = _get_cwd(user.id)

    _set_cwd(user.id, target)
    text = _build_file_list_text(target, user.id)
    keyboard = _build_keyboard(target)

    await update.effective_message.reply_text(
        text, parse_mode=ParseMode.HTML, reply_markup=keyboard
    )


async def cmd_getfile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/getfile <اسم الملف> — تنزيل ملف"""
    user = update.effective_user
    if not user or not _is_admin(user.id):
        await update.effective_message.reply_text("⛔ هذا الأمر للمشرفين فقط.")
        return

    if not context.args:
        await update.effective_message.reply_text(
            "📌 الاستخدام: <code>/getfile اسم_الملف.py</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    filename = " ".join(context.args)
    cwd = _get_cwd(user.id)

    # نبحث أولاً في المجلد الحالي ثم في BASE_DIR
    for search_dir in [cwd, BASE_DIR]:
        file_path = (search_dir / filename).resolve()
        if _safe_path(BASE_DIR, file_path) and file_path.is_file():
            break
    else:
        await update.effective_message.reply_text(f"❌ الملف <code>{filename}</code> غير موجود.", parse_mode=ParseMode.HTML)
        return

    size = file_path.stat().st_size
    if size > MAX_UPLOAD_MB * 1024 * 1024:
        await update.effective_message.reply_text(
            f"❌ الملف كبير جداً ({_format_size(size)}) — الحد الأقصى {MAX_UPLOAD_MB} MB."
        )
        return

    await update.effective_message.reply_document(
        document=file_path.open("rb"),
        filename=file_path.name,
        caption=f"📄 <b>{file_path.name}</b>\n📏 الحجم: {_format_size(size)}\n📁 المسار: <code>{file_path.relative_to(BASE_DIR)}</code>",
        parse_mode=ParseMode.HTML,
    )


async def cmd_delfile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/delfile <اسم الملف> — حذف ملف مع تأكيد"""
    user = update.effective_user
    if not user or not _is_admin(user.id):
        await update.effective_message.reply_text("⛔ هذا الأمر للمشرفين فقط.")
        return

    if not context.args:
        await update.effective_message.reply_text(
            "📌 الاستخدام: <code>/delfile اسم_الملف.py</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    filename = " ".join(context.args)
    cwd = _get_cwd(user.id)

    for search_dir in [cwd, BASE_DIR]:
        file_path = (search_dir / filename).resolve()
        if _safe_path(BASE_DIR, file_path) and file_path.exists():
            break
    else:
        await update.effective_message.reply_text(f"❌ الملف/المجلد <code>{filename}</code> غير موجود.", parse_mode=ParseMode.HTML)
        return

    # منع حذف الملفات الأساسية
    protected = set()  # لا توجد ملفات محمية — المشرف يتحكم في كل شيء
    if file_path.name in protected:
        await update.effective_message.reply_text(f"🔒 الملف <code>{file_path.name}</code> محمي ولا يمكن حذفه.", parse_mode=ParseMode.HTML)
        return

    item_type = "مجلد" if file_path.is_dir() else "ملف"
    size_info = ""
    if file_path.is_file():
        size_info = f"\n📏 الحجم: {_format_size(file_path.stat().st_size)}"

    file_rel = _to_rel(file_path)
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ نعم، احذفه", callback_data=f"fm_del_confirm:{file_rel}"),
        InlineKeyboardButton("❌ إلغاء", callback_data="fm_close"),
    ]])

    await update.effective_message.reply_text(
        f"⚠️ <b>تأكيد الحذف</b>\n\n"
        f"هل تريد حذف هذا ال{item_type}؟\n"
        f"🗑️ <code>{file_path.relative_to(BASE_DIR)}</code>{size_info}\n\n"
        f"<b>هذا الإجراء لا يمكن التراجع عنه!</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard,
    )


async def cmd_mkdir(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/mkdir <اسم المجلد> — إنشاء مجلد جديد"""
    user = update.effective_user
    if not user or not _is_admin(user.id):
        await update.effective_message.reply_text("⛔ هذا الأمر للمشرفين فقط.")
        return

    if not context.args:
        await update.effective_message.reply_text(
            "📌 الاستخدام: <code>/mkdir اسم_المجلد</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    dirname = " ".join(context.args)
    # منع الأسماء الخطرة
    if any(c in dirname for c in r'/\:*?"<>|'):
        await update.effective_message.reply_text("❌ اسم المجلد يحتوي على رموز غير مسموح بها.")
        return

    cwd = _get_cwd(user.id)
    new_dir = (cwd / dirname).resolve()

    if not _safe_path(BASE_DIR, new_dir):
        await update.effective_message.reply_text("❌ خارج نطاق مجلد البوت.")
        return

    if new_dir.exists():
        await update.effective_message.reply_text(f"⚠️ المجلد <code>{dirname}</code> موجود مسبقاً.", parse_mode=ParseMode.HTML)
        return

    new_dir.mkdir(parents=True, exist_ok=True)
    await update.effective_message.reply_text(
        f"✅ تم إنشاء المجلد: <code>{new_dir.relative_to(BASE_DIR)}</code>",
        parse_mode=ParseMode.HTML,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  رفع الملفات (استقبال document من المشرف)
# ══════════════════════════════════════════════════════════════════════════════

async def handle_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """استقبال ملف مرفوع من المشرف وحفظه في المجلد الحالي."""
    user = update.effective_user
    if not user or not _is_admin(user.id):
        return  # نتجاهل الملفات من غير المشرفين بصمت

    # فقط في المحادثات الخاصة (حماية من رفع عشوائي في المجموعات)
    if update.effective_chat.type != "private":
        await update.effective_message.reply_text(
            "📌 لرفع الملفات، أرسلها للبوت في المحادثة الخاصة."
        )
        return

    doc = update.effective_message.document
    if not doc:
        return

    filename = doc.file_name or f"file_{doc.file_id}"
    ext = Path(filename).suffix.lower()

    if ext in BLOCKED_EXTENSIONS:
        await update.effective_message.reply_text(
            f"⛔ امتداد الملف <code>{ext}</code> محظور لأسباب أمنية.",
            parse_mode=ParseMode.HTML,
        )
        return

    if doc.file_size and doc.file_size > MAX_UPLOAD_MB * 1024 * 1024:
        await update.effective_message.reply_text(
            f"❌ الملف كبير جداً ({_format_size(doc.file_size)}) — الحد الأقصى {MAX_UPLOAD_MB} MB."
        )
        return

    cwd = _get_cwd(user.id)
    dest = cwd / filename

    # إذا الملف موجود نضيف رقماً
    if dest.exists():
        stem = Path(filename).stem
        counter = 1
        while dest.exists():
            dest = cwd / f"{stem}_{counter}{ext}"
            counter += 1

    msg = await update.effective_message.reply_text(f"⏳ جاري رفع <code>{filename}</code>...", parse_mode=ParseMode.HTML)

    try:
        tg_file = await doc.get_file()
        await tg_file.download_to_drive(dest)
        await msg.edit_text(
            f"✅ <b>تم رفع الملف بنجاح</b>\n\n"
            f"📄 الاسم: <code>{dest.name}</code>\n"
            f"📁 المسار: <code>{dest.relative_to(BASE_DIR)}</code>\n"
            f"📏 الحجم: {_format_size(dest.stat().st_size)}",
            parse_mode=ParseMode.HTML,
        )
        logger.info(f"✅ رفع ملف: {dest} بواسطة {user.id}")
    except Exception as e:
        logger.error(f"خطأ في رفع الملف: {e}")
        await msg.edit_text(f"❌ فشل رفع الملف: <code>{e}</code>", parse_mode=ParseMode.HTML)


# ══════════════════════════════════════════════════════════════════════════════
#  معالج الأزرار
# ══════════════════════════════════════════════════════════════════════════════

async def callback_fm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user  = query.from_user
    await query.answer()

    if not _is_admin(user.id):
        await query.answer("⛔ للمشرفين فقط.", show_alert=True)
        return

    data = query.data

    if data == "fm_close":
        try:
            await query.message.delete()
        except Exception:
            await query.edit_message_reply_markup(reply_markup=None)
        return

    if data == "fm_noop":
        return

    # ── فتح مجلد ────────────────────────────────────────────────────────────
    if data.startswith("fm_cd:"):
        rel = data[len("fm_cd:"):]
        target = _from_rel(rel)
        if not _safe_path(BASE_DIR, target) or not target.is_dir():
            await query.answer("❌ المجلد غير موجود.", show_alert=True)
            return
        _set_cwd(user.id, target)
        text = _build_file_list_text(target, user.id)
        await query.edit_message_text(
            text, parse_mode=ParseMode.HTML,
            reply_markup=_build_keyboard(target),
        )
        return

    # ── تغيير صفحة ──────────────────────────────────────────────────────────
    if data.startswith("fm_pg:"):
        rest = data[len("fm_pg:"):]
        path_rel, page_str = rest.rsplit("|", 1)
        target = _from_rel(path_rel)
        page = int(page_str)
        if not _safe_path(BASE_DIR, target) or not target.is_dir():
            await query.answer("❌ المجلد غير موجود.", show_alert=True)
            return
        text = _build_file_list_text(target, user.id)
        await query.edit_message_text(
            text, parse_mode=ParseMode.HTML,
            reply_markup=_build_keyboard(target, page),
        )
        return

    # ── تحديث ────────────────────────────────────────────────────────────────
    if data.startswith("fm_rf:"):
        rel = data[len("fm_rf:"):]
        target = _from_rel(rel)
        if not _safe_path(BASE_DIR, target):
            return
        if not target.is_dir():
            target = BASE_DIR
        _set_cwd(user.id, target)
        text = _build_file_list_text(target, user.id)
        try:
            await query.edit_message_text(
                text, parse_mode=ParseMode.HTML,
                reply_markup=_build_keyboard(target),
            )
        except Exception:
            pass
        return

    # ── تأكيد الحذف ─────────────────────────────────────────────────────────
    if data.startswith("fm_del_confirm:"):
        rel = data[len("fm_del_confirm:"):]
        file_path = _from_rel(rel)
        if not _safe_path(BASE_DIR, file_path) or not file_path.exists():
            await query.answer("❌ الملف غير موجود.", show_alert=True)
            return

        protected = set()  # لا توجد ملفات محمية — المشرف يتحكم في كل شيء
        if file_path.name in protected:
            await query.answer("🔒 هذا الملف محمي.", show_alert=True)
            return

        try:
            rel = file_path.relative_to(BASE_DIR)
            if file_path.is_dir():
                shutil.rmtree(file_path)
                msg = f"🗑️ تم حذف المجلد: <code>{rel}</code>"
            else:
                file_path.unlink()
                msg = f"🗑️ تم حذف الملف: <code>{rel}</code>"

            logger.warning(f"🗑️ حذف: {file_path} بواسطة {user.id}")
            await query.edit_message_text(msg, parse_mode=ParseMode.HTML)

            # تحديث المجلد الحالي بعد الحذف
            parent = file_path.parent if file_path.parent.exists() else BASE_DIR
            _set_cwd(user.id, parent)
        except Exception as e:
            await query.edit_message_text(f"❌ فشل الحذف: <code>{e}</code>", parse_mode=ParseMode.HTML)
        return


# ══════════════════════════════════════════════════════════════════════════════
#  Hot Reload — إعادة تحميل ملف بدون إعادة تشغيل البوت
# ══════════════════════════════════════════════════════════════════════════════

async def cmd_reload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /reload <اسم_الملف> — يعيد تحميل ملف Python بدون إعادة تشغيل البوت
    مثال: /reload voice_player
             /reload new_features
    """
    user = update.effective_user
    if not user or not _is_admin(user.id):
        await update.effective_message.reply_text("⛔ هذا الأمر للمشرفين فقط.")
        return

    if not context.args:
        await update.effective_message.reply_text(
            "📌 الاستخدام: <code>/reload اسم_الملف</code>\n"
            "مثال: <code>/reload voice_player</code>\n\n"
            "💡 بدون امتداد .py",
            parse_mode=ParseMode.HTML,
        )
        return

    module_name = context.args[0].replace(".py", "").strip()

    # تحقق أن الملف موجود فعلاً
    module_file = BASE_DIR / f"{module_name}.py"
    if not module_file.exists():
        await update.effective_message.reply_text(
            f"❌ الملف <code>{module_name}.py</code> غير موجود في مجلد البوت.",
            parse_mode=ParseMode.HTML,
        )
        return

    msg = await update.effective_message.reply_text(
        f"⏳ جاري إعادة تحميل <code>{module_name}</code>...",
        parse_mode=ParseMode.HTML,
    )

    try:
        import importlib
        import sys

        # إضافة مجلد البوت لمسار البحث إذا لم يكن موجوداً
        base_str = str(BASE_DIR)
        if base_str not in sys.path:
            sys.path.insert(0, base_str)

        if module_name in sys.modules:
            # الوحدة محمّلة مسبقاً — أعد تحميلها
            module = importlib.reload(sys.modules[module_name])
            action = "🔄 تم إعادة تحميل"
        else:
            # الوحدة جديدة — حمّلها لأول مرة
            module = importlib.import_module(module_name)
            action = "✅ تم تحميل"

        # إذا كان الملف يحتوي register_handlers — سجّله تلقائياً
        if hasattr(module, "register_handlers"):
            app = context.application
            module.register_handlers(app)
            extra = "\n📎 تم تسجيل الـ handlers تلقائياً."
        else:
            extra = ""

        await msg.edit_text(
            f"{action} <code>{module_name}.py</code> بنجاح!{extra}",
            parse_mode=ParseMode.HTML,
        )
        logger.info(f"✅ hot reload: {module_name} بواسطة {user.id}")

    except SyntaxError as e:
        await msg.edit_text(
            f"❌ <b>خطأ في الكود (SyntaxError):</b>\n"
            f"<code>السطر {e.lineno}: {e.msg}</code>\n"
            f"<code>{e.text or ''}</code>",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await msg.edit_text(
            f"❌ <b>فشل التحميل:</b>\n<code>{type(e).__name__}: {e}</code>",
            parse_mode=ParseMode.HTML,
        )


# ══════════════════════════════════════════════════════════════════════════════
#  تسجيل المعالجات
# ══════════════════════════════════════════════════════════════════════════════

def register_handlers(app) -> None:
    app.add_handler(CommandHandler("files",   cmd_files))
    app.add_handler(CommandHandler("reload",  cmd_reload))
    app.add_handler(CommandHandler("getfile", cmd_getfile))
    app.add_handler(CommandHandler("delfile", cmd_delfile))
    app.add_handler(CommandHandler("mkdir",   cmd_mkdir))

    # استقبال الملفات المرفوعة (في المحادثات الخاصة فقط)
    app.add_handler(MessageHandler(
        filters.Document.ALL & filters.ChatType.PRIVATE,
        handle_upload,
    ))

    # أزرار لوحة المدير
    app.add_handler(CallbackQueryHandler(
        callback_fm,
        pattern=r"^(fm_cd:|fm_pg:|fm_rf:|fm_del_confirm:|fm_close|fm_noop)",
    ))

    logger.info("✅ file_manager: handlers مسجّلون — /files /getfile /delfile /mkdir")
