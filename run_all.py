#!/usr/bin/env python3
"""
run_all.py — تشغيل البوت الإسلامي مع ميزة البث الصوتي
"""

import asyncio
import sys
import logging
from pathlib import Path

# ── Windows: ProactorEventLoop مطلوب لـ py-tgcalls + ffmpeg subprocess ──────
# WindowsSelectorEventLoopPolicy لا تدعم create_subprocess_exec
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("RunAll")


async def _auto_set_privacy(api_id, api_hash, sessions_dir: Path):
    privacy_flag = sessions_dir / ".privacy_set"
    if privacy_flag.exists():
        return
    logger.info("🔧 ضبط إعدادات الخصوصية للحساب المساعد (مرة واحدة)...")
    try:
        from pyrogram import Client
        from pyrogram.raw import functions, types as raw_types
        tmp = Client(name=str(sessions_dir / "userbot"), api_id=api_id, api_hash=api_hash)
        await tmp.start()
        await tmp.invoke(functions.account.SetPrivacy(
            key=raw_types.InputPrivacyKeyChatInvite(),
            rules=[raw_types.InputPrivacyValueAllowAll()],
        ))
        await tmp.stop()
        privacy_flag.touch()
        logger.info("✅ الخصوصية مضبوطة — الانضمام التلقائي مُفعَّل")
    except Exception as e:
        logger.warning(f"⚠️  فشل ضبط الخصوصية: {e}")


async def _try_start_voice(sessions_dir: Path) -> bool:
    missing = []
    for lib, pip_name in [
        ("pyrogram",  "pyrogram tgcrypto"),
        ("pytgcalls", "py-tgcalls"),
        ("yt_dlp",    "yt-dlp"),
    ]:
        try:
            __import__(lib)
        except ImportError:
            missing.append(pip_name)

    if missing:
        logger.error("❌ مكتبات مفقودة — شغّل الأمر التالي ثم أعد التشغيل:")
        logger.error(f"   pip install {' '.join(missing)}")
        return False

    # ── فحص مصدر الجلسة: String Session أولاً ثم ملف ──────────────────────
    import config as _cfg
    session_string = getattr(_cfg, "SESSION_STRING", "")

    if session_string:
        logger.info("✅ SESSION_STRING موجود في config.py — لا حاجة لملف جلسة")
    else:
        session_file = sessions_dir / "userbot.session"
        if not session_file.exists():
            logger.error(f"❌ لا يوجد SESSION_STRING في config.py ولا ملف جلسة في: {session_file.resolve()}")
            logger.error("   الخيار 1 (موصى به): أضف SESSION_STRING في config.py")
            logger.error("   الخيار 2: شغّل python setup_session.py لإنشاء ملف جلسة")
            return False
        logger.info(f"✅ ملف الجلسة موجود: {session_file.resolve()}")

    try:
        import voice_player
        result = await voice_player.start_voice_player()
        return result
    except Exception as e:
        logger.error(f"❌ استثناء غير متوقع في voice_player:", exc_info=True)
        return False


async def main():
    import config

    sessions_dir = Path(__file__).parent / "sessions"
    voice_enabled = False

    if not (config.API_ID and config.API_ID != 0 and config.API_HASH):
        logger.info("ℹ️  API_ID/API_HASH غير مُعيَّنَين — ميزة /play معطلة")
    else:
        await _auto_set_privacy(config.API_ID, config.API_HASH, sessions_dir)
        voice_enabled = await _try_start_voice(sessions_dir)
        if voice_enabled:
            logger.info("✅ Voice Player جاهز — ميزة /play متاحة لجميع المجموعات")
        else:
            logger.warning("⚠️  Voice Player لم يبدأ — راجع الأخطاء أعلاه")

    from bot import main as bot_main
    logger.info("✅ تشغيل البوت الإسلامي...")
    try:
        await bot_main()
    finally:
        if voice_enabled:
            import voice_player
            await voice_player.stop_voice_player()


if __name__ == "__main__":
    asyncio.run(main())
