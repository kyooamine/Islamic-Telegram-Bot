#!/usr/bin/env python3
"""
voice_commands.py — أوامر بث الصوت في مكالمات التيليغرام
"""

import logging
import traceback
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
import config

logger = logging.getLogger("VoiceCommands")

_vp = None

def _get_vp():
    global _vp
    if _vp is None:
        import voice_player as vp
        _vp = vp
    return _vp


async def _is_admin(update: Update) -> bool:
    """يستخدم فقط لأوامر تحتاج صلاحيات (غير مستخدم حالياً — جميع أوامر البث للجميع)."""
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


async def cmd_play(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user = update.effective_user

    # /play متاح للجميع (مشرفون وأعضاء عاديون)
    if not context.args:
        await update.effective_message.reply_text(
            "📌 <b>الاستخدام:</b>\n<code>/play https://youtu.be/...</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    url = context.args[0].strip()
    vp = _get_vp()

    if not vp.is_youtube_url(url):
        await update.effective_message.reply_text("❌ الرابط غير صحيح، تأكد أنه رابط يوتيوب.")
        return

    if not vp.is_voice_ready():
        await update.effective_message.reply_text(
            "❌ <b>الحساب المساعد غير جاهز!</b>\n\n"
            "تحقق من سجل البوت للتأكد من أن Voice Player بدأ بنجاح.",
            parse_mode=ParseMode.HTML,
        )
        return

    username = (f"@{user.username}" if user and user.username else (user.first_name if user else "القناة"))

    msg = await update.effective_message.reply_text(
        "⏳ <b>جاري الانضمام للمكالمة وجلب رابط البث...</b>",
        parse_mode=ParseMode.HTML,
    )

    try:
        result = await vp.play_in_chat(
            chat_id=chat.id,
            url=url,
            requested_by=username,
            bot_token=config.BOT_TOKEN,
        )
    except Exception as exc:
        full_tb = traceback.format_exc()
        logger.error(f"استثناء في play_in_chat:\n{full_tb}")
        await msg.edit_text(
            f"❌ <b>استثناء غير متوقع:</b>\n<pre>{full_tb[-800:]}</pre>",
            parse_mode=ParseMode.HTML,
        )
        return

    if result["ok"]:
        await msg.edit_text(
            f"🎵 <b>يتم البث الآن</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎶 {result['title']}\n"
            f"👤 طُلب بواسطة: {username}\n\n"
            f"⏹️ /stop | ⏸️ /pause | ▶️ /resume",
            parse_mode=ParseMode.HTML,
        )
    else:
        error = result.get("error", "")
        logger.error(f"play_in_chat فشل: repr={repr(error)}")

        if error == "no_active_call":
            friendly = (
                "⚠️ <b>لا توجد مكالمة صوتية نشطة!</b>\n\n"
                "📋 <b>الخطوات:</b>\n"
                "1️⃣ افتح إعدادات المجموعة/القناة\n"
                "2️⃣ ابدأ <b>Voice Chat</b> أو <b>Livestream</b>\n"
                "3️⃣ أرسل /play مرة أخرى"
            )
        elif error == "admin_required":
            friendly = (
                "⚠️ <b>الحساب المساعد يحتاج صلاحية مشرف!</b>\n\n"
                "📋 <b>الخطوات:</b>\n"
                "1️⃣ افتح إعدادات المجموعة/القناة\n"
                "2️⃣ اذهب إلى <b>المشرفون</b>\n"
                "3️⃣ أضف الحساب المساعد كمشرف\n"
                "4️⃣ فعّل صلاحية <b>إدارة المكالمات الصوتية</b>\n"
                "5️⃣ أرسل /play مرة أخرى"
            )
        elif "خصوصية" in error or "privacy" in error.lower():
            friendly = (
                "⚠️ <b>مشكلة في إعدادات الخصوصية</b>\n\n"
                "في تيليغرام على هاتفك:\n"
                "الإعدادات ← الخصوصية والأمان ← المجموعات والقنوات ← <b>الجميع</b>"
            )
        else:
            friendly = (
                f"❌ <b>فشل البث</b>\n\n"
                f"<b>الخطأ:</b> <code>{error if error else '(فارغ)'}</code>\n\n"
                f"<b>repr:</b> <code>{repr(error)[:200]}</code>"
            )

        await msg.edit_text(friendly, parse_mode=ParseMode.HTML)


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # /stop متاح للجميع
    chat = update.effective_chat
    vp = _get_vp()
    if not vp.get_now_playing(chat.id):
        await update.effective_message.reply_text("📭 لا يوجد بث نشط حالياً.")
        return
    result = await vp.stop_in_chat(chat.id)
    if result["ok"]:
        await update.effective_message.reply_text("⏹️ <b>تم إيقاف البث.</b>", parse_mode=ParseMode.HTML)
    else:
        await update.effective_message.reply_text(f"❌ <code>{result.get('error')}</code>", parse_mode=ParseMode.HTML)


async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # /pause متاح للجميع
    result = await _get_vp().pause_in_chat(update.effective_chat.id)
    if result["ok"]:
        await update.effective_message.reply_text("⏸️ <b>تم تعليق البث.</b>", parse_mode=ParseMode.HTML)
    else:
        await update.effective_message.reply_text(f"❌ {result.get('error', 'لا يوجد بث نشط.')}")


async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # /resume متاح للجميع
    result = await _get_vp().resume_in_chat(update.effective_chat.id)
    if result["ok"]:
        await update.effective_message.reply_text("▶️ <b>تم استئناف البث.</b>", parse_mode=ParseMode.HTML)
    else:
        await update.effective_message.reply_text(f"❌ {result.get('error', 'لا يوجد بث معلق.')}")


async def cmd_nowplaying(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    info = _get_vp().get_now_playing(update.effective_chat.id)
    if not info:
        await update.effective_message.reply_text("📭 لا يوجد بث نشط حالياً.")
        return
    await update.effective_message.reply_text(
        f"🎵 <b>يُبَث الآن:</b>\n🎶 {info['title']}\n👤 {info.get('requested_by', '؟')}\n\n⏹️ /stop | ⏸️ /pause",
        parse_mode=ParseMode.HTML,
    )
