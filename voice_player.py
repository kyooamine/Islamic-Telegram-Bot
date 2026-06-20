#!/usr/bin/env python3
"""
voice_player.py — بث الصوت في مكالمات تيليغرام
النهج: yt-dlp يجيب URL → ffmpeg pipe → py-tgcalls
"""

import asyncio
import logging
import re
import traceback

logger = logging.getLogger("VoicePlayer")

try:
    import config
    from pathlib import Path
    _BASE_DIR       = Path(config.__file__).parent
    _API_ID         = config.API_ID
    _API_HASH       = config.API_HASH
    _SESSION_STRING = getattr(config, "SESSION_STRING", "")
except Exception:
    from pathlib import Path
    _BASE_DIR       = Path(__file__).parent
    _API_ID         = 0
    _API_HASH       = ""
    _SESSION_STRING = ""

SESSION_DIR = _BASE_DIR / "sessions"
SESSION_DIR.mkdir(exist_ok=True)

_pyrogram_client  = None
_pytgcalls_client = None
_voice_started: bool = False
active_streams: dict[int, dict] = {}


# ══════════════════════════════════════════════════════════════════════════════
#  تهيئة العملاء
# ══════════════════════════════════════════════════════════════════════════════

def _get_pyrogram():
    global _pyrogram_client
    if _pyrogram_client is None:
        from pyrogram import Client
        if _SESSION_STRING:
            # ── String Session (مدمج في config.py — لا يحتاج ملف) ──────────
            _pyrogram_client = Client(
                name="userbot_string",
                api_id=_API_ID,
                api_hash=_API_HASH,
                session_string=_SESSION_STRING,
            )
        else:
            # ── ملف session محلي (الطريقة القديمة) ─────────────────────────
            _pyrogram_client = Client(
                name=str(SESSION_DIR / "userbot"),
                api_id=_API_ID,
                api_hash=_API_HASH,
            )
    return _pyrogram_client


def _get_pytgcalls():
    global _pytgcalls_client
    if _pytgcalls_client is None:
        from pytgcalls import PyTgCalls
        _pytgcalls_client = PyTgCalls(_get_pyrogram())
        _register_stream_end_handler(_pytgcalls_client)
    return _pytgcalls_client


def _register_stream_end_handler(client) -> None:
    """يسجّل معالج نهاية البث لتنظيف active_streams تلقائياً.

    بدون هذا المعالج تظل إدخالات البث القديمة عالقة في active_streams، فيُظهر
    /nowplaying مقطعاً توقف فعلاً، ويفشل /stop في مغادرة مكالمة لم تعد موجودة.
    py-tgcalls غيّر توقيع المعالج عبر الإصدارات، لذا نلفه بشكل دفاعي.
    """
    def _on_end(*args, **kwargs):
        # إصدارات مختلفة: (chat_id) أو (client, call) أو كائن حدث بـ .chat_id
        chat_id = None
        for a in args:
            if isinstance(a, int):
                chat_id = a
                break
            cid = getattr(a, "chat_id", None)
            if isinstance(cid, int):
                chat_id = cid
                break
        if "chat_id" in kwargs and isinstance(kwargs["chat_id"], int):
            chat_id = kwargs["chat_id"]
        if chat_id is not None:
            removed = active_streams.pop(chat_id, None)
            if removed:
                logger.info(f"🏁 انتهى البث في {chat_id} — تم تنظيف active_streams")
    try:
        client.on_stream_end()(_on_end)
    except Exception as e:
        logger.warning(f"تعذّر تسجيل معالج نهاية البث: {e}")


def is_voice_ready() -> bool:
    return _voice_started and _pyrogram_client is not None


# ══════════════════════════════════════════════════════════════════════════════
#  جلب معلومات يوتيوب
# ══════════════════════════════════════════════════════════════════════════════

def is_youtube_url(url: str) -> bool:
    return bool(re.search(
        r"(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/|youtube\.com/live/)",
        url
    ))


def _ensure_yt_dlp_updated():
    """يتحقق من نسخة yt-dlp ويحدّثها تلقائياً إذا كانت قديمة (مرة واحدة عند البدء)."""
    import subprocess, sys
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", "-U", "yt-dlp", "--break-system-packages"],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            logger.info("✅ yt-dlp محدَّث إلى آخر نسخة")
        else:
            logger.warning(f"⚠️ فشل تحديث yt-dlp: {result.stderr[:100]}")
    except Exception as e:
        logger.warning(f"⚠️ تعذّر تحديث yt-dlp: {e}")


def _clean_ansi(text: str) -> str:
    """إزالة رموز ANSI من رسائل الخطأ."""
    import re as _re
    return _re.sub(r'\x1b\[[0-9;]*m', '', text)


def _build_ydl_opts(cookies_file=None) -> dict:
    """يبني خيارات yt-dlp مع أفضل إعدادات لتجاوز حماية يوتيوب."""
    opts = {
        "format": "bestaudio/best[ext=m4a]/bestaudio/best/worst",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
        "nocheckcertificate": True,
        "socket_timeout": 30,
        "geo_bypass": True,
        "retries": 3,
        "fragment_retries": 3,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },
    }
    if cookies_file and Path(cookies_file).exists():
        opts["cookiefile"] = str(cookies_file)
        logger.info(f"✅ استخدام ملف الكوكيز: {cookies_file}")
    return opts


def _find_cookies_file():
    """يبحث عن ملف كوكيز في مجلد البوت."""
    for candidate in [
        _BASE_DIR / "cookies.txt",
        _BASE_DIR / "youtube_cookies.txt",
        _BASE_DIR / "cookies" / "youtube.txt",
    ]:
        if candidate.exists():
            return candidate
    return None


def _try_extract(url: str, client: str, cookies_file=None):
    """محاولة واحدة بـ player_client محدد — يجرب صيغتين عند الفشل."""
    import yt_dlp

    format_fallbacks = [
        "bestaudio/best[ext=m4a]/bestaudio/best/worst",
        "bestaudio",
        "worstaudio/worst",
    ]

    for fmt in format_fallbacks:
        opts = _build_ydl_opts(cookies_file)
        opts["format"] = fmt
        opts["extractor_args"] = {"youtube": {"player_client": [client]}}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            if info:
                return info
        except Exception as e:
            if "Requested format is not available" in str(e):
                logger.warning(f"⚠️ format={fmt} غير متاح، جاري تجربة الصيغة التالية...")
                continue
            raise
    return None


def _extract_audio_url(info: dict):
    """يستخرج أفضل رابط صوتي من معلومات الفيديو."""
    formats = info.get("formats") or []
    # audio-only أولاً
    candidates = [
        f for f in formats
        if f.get("acodec") not in (None, "none")
        and f.get("vcodec") in (None, "none", "")
        and f.get("url")
    ]
    if candidates:
        candidates.sort(key=lambda f: f.get("abr") or f.get("tbr") or 0, reverse=True)
        return candidates[0]["url"]
    # fallback: أي format فيه url
    for f in reversed(formats):
        if f.get("url"):
            return f["url"]
    return info.get("url")


def _extract_info(url: str) -> tuple[str | None, str]:
    """يجيب direct audio URL + العنوان.
    يجرب عدة player_clients تلقائياً للتغلب على حماية يوتيوب.
    """
    try:
        import yt_dlp
        cookies_file = _find_cookies_file()

        # الترتيب: android أفضل لتجاوز Sign-in ← web_creator ← tv_embedded
        clients = ["android", "web_creator", "tv_embedded", "web"]
        info = None
        last_err = ""

        for client in clients:
            try:
                info = _try_extract(url, client, cookies_file)
                if info:
                    logger.info(f"✅ نجح client={client}")
                    break
            except Exception as e:
                last_err = _clean_ansi(str(e))
                logger.warning(f"⚠️ client={client} فشل: {last_err[:80]}")

        if not info:
            if "Sign in" in last_err or "bot" in last_err.lower() or "confirm" in last_err.lower():
                return None, (
                    "⚠️ يوتيوب يطلب تسجيل الدخول.\n\n"
                    "الحل: ضع ملف <code>cookies.txt</code> في مجلد البوت.\n\n"
                    "طريقة التصدير:\n"
                    "1️⃣ ثبّت إضافة <b>Get cookies.txt LOCALLY</b> في Chrome\n"
                    "2️⃣ افتح youtube.com وأنت مسجّل الدخول\n"
                    "3️⃣ صدّر الكوكيز واحفظ الملف باسم <code>cookies.txt</code>\n"
                    "4️⃣ ارفعه لمجلد البوت عبر /files"
                )
            if "429" in last_err:
                return None, "يوتيوب يحظر الطلبات مؤقتاً — انتظر دقيقة ثم حاول"
            if "unavailable" in last_err.lower():
                return None, "الفيديو غير متاح أو محذوف"
            if "private" in last_err.lower():
                return None, "الفيديو خاص"
            if "not available" in last_err.lower() or "Requested format" in last_err:
                return None, "لا تتوفر صيغة صوتية لهذا الفيديو — جرّب رابطاً آخر"
            return None, last_err[:200] if last_err else "yt-dlp لم يُرجع بيانات"

        title = info.get("title", "بدون عنوان")
        audio_url = _extract_audio_url(info)

        if not audio_url:
            return None, "لا يوجد رابط بث صوتي متاح"

        return audio_url, title

    except Exception as e:
        err = _clean_ansi(str(e))
        return None, err[:200]


async def get_audio_info(url: str) -> tuple[str | None, str]:
    loop = asyncio.get_running_loop()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(None, _extract_info, url),
            timeout=25,
        )
    except asyncio.TimeoutError:
        return None, "انتهت المهلة (25ث)"
    except Exception as e:
        return None, str(e)


# ══════════════════════════════════════════════════════════════════════════════
#  بناء MediaStream — المشكلة كانت هنا
# ══════════════════════════════════════════════════════════════════════════════

def _build_stream(audio_url: str):
    """
    يبني MediaStream بالطريقة الصحيحة حسب نسخة py-tgcalls المثبتة.
    py-tgcalls يتطلب piped audio عبر ffmpeg لـ URLs الخارجية.
    """
    from pytgcalls.types import MediaStream, AudioQuality

    # نجرب أولاً مع ffmpeg_parameters لإجبار الـ pipe
    try:
        return MediaStream(
            audio_url,
            audio_parameters=AudioQuality.HIGH,
            video_flags=MediaStream.Flags.IGNORE,
            ffmpeg_parameters="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
        )
    except TypeError:
        # نسخة قديمة من pytgcalls لا تدعم ffmpeg_parameters
        pass

    # fallback: بدون ffmpeg_parameters
    return MediaStream(
        audio_url,
        audio_parameters=AudioQuality.HIGH,
        video_flags=MediaStream.Flags.IGNORE,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  الانضمام للدردشة
# ══════════════════════════════════════════════════════════════════════════════

def _make_aiohttp_session():
    """إنشاء aiohttp session بدون aiodns — يعمل مع ProactorEventLoop على Windows."""
    import aiohttp
    connector = aiohttp.TCPConnector(
        resolver=aiohttp.ThreadedResolver(),
        ssl=False,
    )
    return aiohttp.ClientSession(connector=connector)


async def _ensure_userbot_in_chat(bot_token: str, chat_id: int) -> dict:
    client = _get_pyrogram()
    try:
        await client.get_chat(chat_id)
        return {"ok": True}
    except Exception:
        pass

    try:
        async with _make_aiohttp_session() as s:
            async with s.get(
                f"https://api.telegram.org/bot{bot_token}/getChat",
                params={"chat_id": chat_id},
            ) as r:
                data = await r.json()
        username = data.get("result", {}).get("username")
        if username:
            try:
                from pyrogram.errors import UserAlreadyParticipant
                await client.join_chat(username)
                return {"ok": True}
            except UserAlreadyParticipant:
                return {"ok": True}
    except Exception as e:
        logger.debug(f"join public: {e}")

    try:
        async with _make_aiohttp_session() as s:
            async with s.post(
                f"https://api.telegram.org/bot{bot_token}/createChatInviteLink",
                json={"chat_id": chat_id, "member_limit": 1},
            ) as r:
                result = await r.json()
        if not result.get("ok"):
            return {"ok": False, "error": result.get("description", "فشل إنشاء رابط")}
        invite = result["result"]["invite_link"]
        try:
            from pyrogram.errors import UserAlreadyParticipant, UserPrivacyRestricted
            await client.join_chat(invite)
            return {"ok": True}
        except UserAlreadyParticipant:
            return {"ok": True}
        except UserPrivacyRestricted:
            return {"ok": False, "error": "خصوصية"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
#  واجهة البث
# ══════════════════════════════════════════════════════════════════════════════

async def play_in_chat(
    chat_id: int, url: str, requested_by: str = "", bot_token: str = ""
) -> dict:

    if not is_youtube_url(url):
        return {"ok": False, "error": "الرابط ليس رابط يوتيوب صحيح"}

    if bot_token:
        join = await _ensure_userbot_in_chat(bot_token, chat_id)
        if not join["ok"]:
            return {"ok": False, "error": join.get("error", "فشل الانضمام")}
        await asyncio.sleep(1)

    logger.info(f"🔍 جلب رابط البث: {url[:60]}...")
    audio_url, title = await get_audio_info(url)
    if not audio_url:
        return {"ok": False, "error": title}

    logger.info(f"✅ رابط جاهز: {title[:60]}")

    tg_calls = _get_pytgcalls()
    try:
        stream = _build_stream(audio_url)

        # py-tgcalls v2.x: play() تستبدل البث الحالي تلقائياً إذا كان نشطاً
        await tg_calls.play(chat_id, stream)

        active_streams[chat_id] = {
            "url": url,
            "title": title,
            "requested_by": requested_by,
        }
        return {"ok": True, "title": title}

    except Exception as e:
        full = traceback.format_exc()
        logger.error(f"pytgcalls exception:\n{full}")
        err = str(e).strip()
        err_lower = err.lower()
        if not err:
            # استخرج نوع الـ exception على الأقل
            err = type(e).__name__
        if "no active" in err_lower or "no_active" in err_lower:
            return {"ok": False, "error": "no_active_call"}
        if "chat_admin_required" in err_lower or "admin" in err_lower:
            return {"ok": False, "error": "admin_required"}
        return {"ok": False, "error": f"{type(e).__name__}: {err}\n\n{full[-400:]}"}


async def stop_in_chat(chat_id: int) -> dict:
    try:
        await _get_pytgcalls().leave_call(chat_id)
        active_streams.pop(chat_id, None)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def pause_in_chat(chat_id: int) -> dict:
    try:
        await _get_pytgcalls().pause(chat_id)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def resume_in_chat(chat_id: int) -> dict:
    try:
        await _get_pytgcalls().resume(chat_id)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_now_playing(chat_id: int) -> dict | None:
    return active_streams.get(chat_id)


# ══════════════════════════════════════════════════════════════════════════════
#  دورة حياة
# ══════════════════════════════════════════════════════════════════════════════

async def start_voice_player() -> bool:
    global _voice_started

    # ── تحديث yt-dlp تلقائياً ──────────────────────────────────────────────
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _ensure_yt_dlp_updated)

    # ── فحص مصدر الجلسة ────────────────────────────────────────────────────
    if _SESSION_STRING:
        logger.info("✅ استخدام String Session من config.py")
    else:
        session_file = SESSION_DIR / "userbot.session"
        if not session_file.exists():
            logger.error(f"❌ ملف الجلسة غير موجود: {session_file}")
            logger.error("   شغّل setup_session.py أو أضف SESSION_STRING في config.py")
            return False

    try:
        client = _get_pyrogram()
        calls  = _get_pytgcalls()
        await client.start()
        await calls.start()
        me = await client.get_me()
        _voice_started = True
        logger.info(f"✅ Userbot جاهز: @{me.username} (ID: {me.id})")
        return True
    except Exception as e:
        logger.error(f"❌ فشل تشغيل Voice Player: {e}", exc_info=True)
        _voice_started = False
        return False


async def stop_voice_player():
    global _voice_started
    for cid in list(active_streams):
        try:
            await stop_in_chat(cid)
        except Exception:
            pass
    try:
        await _get_pytgcalls().stop()
    except Exception:
        pass
    try:
        await _get_pyrogram().stop()
    except Exception:
        pass
    _voice_started = False
