#!/usr/bin/env python3
"""
restart_manager.py — إعادة تشغيل البوت عن بُعد عبر تيليغرام
=============================================================
الأوامر:
  /restart          — إعادة تشغيل البوت (للمشرفين فقط)
  /update           — تحديث yt-dlp ثم إعادة التشغيل
  /logs [n]         — عرض آخر n سطر من السجل (افتراضي 30)
  /shell <أمر>      — تنفيذ أمر shell (للمشرفين فقط - خطر!)

طريقة عمل /restart:
  - يرسل رسالة تأكيد
  - ينفذ os.execv لاستبدال العملية الحالية بنسخة جديدة
  - إذا فشل execv يلجأ لـ subprocess ثم sys.exit
"""

import asyncio
import logging
import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from telegram.constants import ParseMode

logger = logging.getLogger("RestartManager")

try:
    import config
    ADMIN_IDS = set(getattr(config, "ALLOWED_USER_IDS", []))
    BASE_DIR  = Path(config.__file__).parent
except Exception:
    ADMIN_IDS = set()
    BASE_DIR  = Path(__file__).parent

# ملف السجل (يبحث عن أي ملف .log في المجلد)
def _find_log_file() -> Path | None:
    for candidate in ["bot.log", "run.log", "app.log", "output.log"]:
        p = BASE_DIR / candidate
        if p.exists():
            return p
    # أي ملف log
    logs = list(BASE_DIR.glob("*.log"))
    return logs[0] if logs else None


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ══════════════════════════════════════════════════════════════════════════════
#  /restart
# ══════════════════════════════════════════════════════════════════════════════

async def cmd_restart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not _is_admin(user.id):
        await update.effective_message.reply_text("⛔ هذا الأمر للمشرفين فقط.")
        return

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ نعم، أعد التشغيل", callback_data="rst_confirm"),
        InlineKeyboardButton("❌ إلغاء", callback_data="rst_cancel"),
    ]])

    await update.effective_message.reply_text(
        "⚠️ <b>تأكيد إعادة التشغيل</b>\n\n"
        "سيتوقف البوت لثوانٍ قليلة ثم يعود تلقائياً.\n"
        "هل أنت متأكد؟",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard,
    )


async def cmd_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/update — تحديث yt-dlp ثم إعادة التشغيل"""
    user = update.effective_user
    if not user or not _is_admin(user.id):
        await update.effective_message.reply_text("⛔ هذا الأمر للمشرفين فقط.")
        return

    msg = await update.effective_message.reply_text(
        "⏳ <b>جاري تحديث yt-dlp...</b>",
        parse_mode=ParseMode.HTML,
    )

    try:
        result = await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: subprocess.run(
                [sys.executable, "-m", "pip", "install", "-U", "yt-dlp", "--break-system-packages"],
                capture_output=True, text=True, timeout=120
            )
        )

        if result.returncode == 0:
            # استخرج النسخة الجديدة
            ver_result = subprocess.run(
                [sys.executable, "-m", "yt_dlp", "--version"],
                capture_output=True, text=True
            )
            version = ver_result.stdout.strip() if ver_result.returncode == 0 else "غير معروفة"
            await msg.edit_text(
                f"✅ <b>تم تحديث yt-dlp</b>\n"
                f"📦 النسخة: <code>{version}</code>\n\n"
                f"⏳ جاري إعادة التشغيل...",
                parse_mode=ParseMode.HTML,
            )
        else:
            await msg.edit_text(
                f"⚠️ <b>التحديث انتهى بتحذير:</b>\n<code>{result.stderr[-300:]}</code>\n\n"
                f"⏳ جاري إعادة التشغيل...",
                parse_mode=ParseMode.HTML,
            )
    except Exception as e:
        await msg.edit_text(
            f"❌ <b>فشل التحديث:</b> <code>{e}</code>\n\n⏳ جاري إعادة التشغيل...",
            parse_mode=ParseMode.HTML,
        )

    await asyncio.sleep(2)
    await _do_restart(update.effective_message)


# ══════════════════════════════════════════════════════════════════════════════
#  /logs
# ══════════════════════════════════════════════════════════════════════════════

async def cmd_logs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/logs [n] — عرض آخر n سطر من السجل"""
    user = update.effective_user
    if not user or not _is_admin(user.id):
        await update.effective_message.reply_text("⛔ هذا الأمر للمشرفين فقط.")
        return

    lines = 30
    if context.args:
        try:
            lines = max(5, min(200, int(context.args[0])))
        except ValueError:
            pass

    log_file = _find_log_file()

    # أولاً: نحاول قراءة ملف السجل
    if log_file:
        try:
            all_lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
            tail = "\n".join(all_lines[-lines:])
            text = (
                f"📋 <b>آخر {lines} سطر من {log_file.name}</b>\n"
                f"━━━━━━━━━━━━━━━\n"
                f"<pre>{tail[-3500:]}</pre>"
            )
            await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)
            return
        except Exception as e:
            logger.warning(f"فشل قراءة ملف السجل: {e}")

    # ثانياً: journalctl أو /proc
    try:
        result = subprocess.run(
            ["journalctl", "-n", str(lines), "--no-pager", "-o", "short"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            await update.effective_message.reply_text(
                f"📋 <b>آخر {lines} سطر (journalctl)</b>\n<pre>{result.stdout[-3500:]}</pre>",
                parse_mode=ParseMode.HTML,
            )
            return
    except Exception:
        pass

    await update.effective_message.reply_text(
        "⚠️ لا يوجد ملف سجل متاح.\n\n"
        "💡 لتفعيل السجل، شغّل البوت هكذا:\n"
        "<code>python run_all.py 2>&1 | tee bot.log</code>",
        parse_mode=ParseMode.HTML,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  /shell — تنفيذ أمر shell (خطر - للمشرفين فقط)
# ══════════════════════════════════════════════════════════════════════════════

async def cmd_shell(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/shell <أمر> — تنفيذ أمر shell على السيرفر"""
    user = update.effective_user
    if not user or not _is_admin(user.id):
        await update.effective_message.reply_text("⛔ هذا الأمر للمشرفين فقط.")
        return

    if not context.args:
        await update.effective_message.reply_text(
            "📌 الاستخدام: <code>/shell أمر</code>\n"
            "مثال: <code>/shell pip show yt-dlp</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    cmd = " ".join(context.args)
    msg = await update.effective_message.reply_text(
        f"⏳ تنفيذ: <code>{cmd}</code>", parse_mode=ParseMode.HTML
    )

    try:
        result = await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: subprocess.run(
                cmd, shell=True, capture_output=True,
                text=True, timeout=30, cwd=str(BASE_DIR)
            )
        )
        output = (result.stdout + result.stderr).strip()
        if not output:
            output = "(لا يوجد مخرجات)"

        status = "✅" if result.returncode == 0 else "❌"
        await msg.edit_text(
            f"{status} <code>{cmd}</code>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"<pre>{output[-3500:]}</pre>",
            parse_mode=ParseMode.HTML,
        )
    except asyncio.TimeoutError:
        await msg.edit_text(f"⏱️ انتهت المهلة (30 ثانية) لتنفيذ: <code>{cmd}</code>", parse_mode=ParseMode.HTML)
    except Exception as e:
        await msg.edit_text(f"❌ خطأ: <code>{e}</code>", parse_mode=ParseMode.HTML)


# ══════════════════════════════════════════════════════════════════════════════
#  منطق إعادة التشغيل الفعلي
# ══════════════════════════════════════════════════════════════════════════════

async def _do_restart(message) -> None:
    """ينفذ إعادة التشغيل الفعلية بعدة طرق احتياطية."""
    try:
        await message.reply_text(
            "🔄 <b>جاري إعادة التشغيل...</b>\n"
            "⏳ سيعود البوت خلال ثوانٍ.",
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        pass

    await asyncio.sleep(1)

    main_script = BASE_DIR / "run_all.py"
    python = sys.executable

    # Windows: نستخدم ملف .bat مؤقت يعيد التشغيل بعد تأخير
    if sys.platform == "win32":
        try:
            logger.info("🔄 إعادة التشغيل عبر bat script (Windows)...")
            import ctypes
            def _short_path(p: str) -> str:
                """يحوّل المسار الطويل إلى 8.3 لتجنب مشكلة المسافات في bat."""
                buf = ctypes.create_unicode_buffer(512)
                ctypes.windll.kernel32.GetShortPathNameW(p, buf, 512)
                return buf.value or p
            short_base   = _short_path(str(BASE_DIR))
            short_python = _short_path(python)
            short_script = _short_path(str(main_script))
            bat = BASE_DIR / "_restart_tmp.bat"
            bat_content = (
                "@echo off\r\n"
                "timeout /t 2 /nobreak >nul\r\n"
                f"cd /d {short_base}\r\n"
                f'start "" {short_python} {short_script}\r\n'
                'del "%~f0"\r\n'
            )
            bat.write_text(bat_content, encoding="utf-8")
            subprocess.Popen(
                ["cmd", "/c", str(bat)],
                cwd=str(BASE_DIR),
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                close_fds=True,
            )
            logger.info(f"✅ bat script بدأ ({short_base}) — إنهاء العملية الحالية")
            await asyncio.sleep(1)
            os._exit(0)
        except Exception as e:
            logger.error(f"bat restart فشل: {e}")
            os._exit(1)

    # Linux/Mac: execv أفضل (تستبدل العملية الحالية)
    try:
        logger.info("🔄 إعادة التشغيل عبر os.execv...")
        os.execv(python, [python, str(main_script)])
    except Exception as e:
        logger.warning(f"execv فشل: {e} — جاري تجربة subprocess...")
        try:
            subprocess.Popen(
                [python, str(main_script)],
                cwd=str(BASE_DIR),
                start_new_session=True,
            )
            await asyncio.sleep(1)
            os._exit(0)
        except Exception as e2:
            logger.error(f"subprocess فشل أيضاً: {e2}")
            os._exit(1)


# ══════════════════════════════════════════════════════════════════════════════
#  معالج الأزرار
# ══════════════════════════════════════════════════════════════════════════════

async def callback_restart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user  = query.from_user
    await query.answer()

    if not _is_admin(user.id):
        await query.answer("⛔ للمشرفين فقط.", show_alert=True)
        return

    if query.data == "rst_cancel":
        await query.edit_message_text("❌ تم إلغاء إعادة التشغيل.")
        return

    if query.data == "rst_confirm":
        now = datetime.now().strftime("%H:%M:%S")
        await query.edit_message_text(
            f"🔄 <b>إعادة التشغيل...</b>\n"
            f"🕐 الوقت: <code>{now}</code>\n\n"
            f"⏳ سيعود البوت خلال ثوانٍ قليلة.",
            parse_mode=ParseMode.HTML,
        )
        await asyncio.sleep(1)
        await _do_restart(query.message)


# ══════════════════════════════════════════════════════════════════════════════
#  تسجيل المعالجات
# ══════════════════════════════════════════════════════════════════════════════

def register_handlers(app) -> None:
    app.add_handler(CommandHandler("restart", cmd_restart))
    app.add_handler(CommandHandler("update",  cmd_update))
    app.add_handler(CommandHandler("logs",    cmd_logs))
    app.add_handler(CommandHandler("shell",   cmd_shell))
    app.add_handler(CallbackQueryHandler(
        callback_restart,
        pattern=r"^rst_(confirm|cancel)$",
    ))
    logger.info("✅ restart_manager: /restart /update /logs /shell مسجّلون")
