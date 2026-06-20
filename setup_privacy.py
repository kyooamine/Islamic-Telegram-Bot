#!/usr/bin/env python3
"""
setup_privacy.py — ضبط إعدادات الخصوصية للحساب المساعد
شغّله مرة واحدة بعد setup_session.py:
    python setup_privacy.py

يجعل الحساب المساعد قابلاً للإضافة في أي مجموعة/قناة تلقائياً.
"""

import asyncio
import sys
from pathlib import Path

try:
    from pyrogram import Client
    from pyrogram.raw import functions, types
except ImportError:
    print("❌ pyrogram غير مثبّت — شغّل: pip install pyrogram tgcrypto")
    sys.exit(1)

try:
    import config
except ImportError:
    print("❌ ملف config.py غير موجود!")
    sys.exit(1)

SESSION_DIR = Path(__file__).parent / "sessions"


async def setup_privacy():
    print("=" * 55)
    print("  ضبط إعدادات الخصوصية للحساب المساعد")
    print("=" * 55)
    print()

    session_file = SESSION_DIR / "userbot.session"
    if not session_file.exists():
        print("❌ ملف الجلسة غير موجود — شغّل setup_session.py أولاً")
        return

    client = Client(
        name=str(SESSION_DIR / "userbot"),
        api_id=config.API_ID,
        api_hash=config.API_HASH,
    )

    try:
        await client.start()
        me = await client.get_me()
        print(f"✅ الحساب: {me.first_name} (@{me.username})")
        print()

        # ── ضبط إعداد "من يمكنه إضافتي للمجموعات" → الجميع ──────────────────
        # هذا هو الإعداد الحاسم الذي يسمح بالانضمام التلقائي
        await client.invoke(
            functions.account.SetPrivacy(
                key=types.InputPrivacyKeyChatInvite(),
                rules=[types.InputPrivacyValueAllowAll()],
            )
        )
        print("✅ تم ضبط: 'من يمكنه إضافتي للمجموعات' → الجميع")

        # ── اختياري: السماح برؤية الهاتف (ليس ضرورياً لكن يساعد) ──────────
        # (نتركه كما هو لحماية خصوصية الهاتف)

        print()
        print("=" * 55)
        print("🎉 تم الضبط بنجاح!")
        print()
        print("الآن الحساب المساعد سينضم تلقائياً لأي مجموعة/قناة")
        print("عند استخدام أمر /play — دون تدخل يدوي.")
        print()
        print("🚀 شغّل البوت: python run_all.py")
        print("=" * 55)

    except Exception as e:
        print(f"❌ خطأ: {e}")
        print()
        print("إذا فشل الأمر، يمكنك ضبطه يدوياً:")
        print("تيليغرام → الإعدادات → الخصوصية والأمان")
        print("→ المجموعات والقنوات → الجميع")
    finally:
        await client.stop()


if __name__ == "__main__":
    asyncio.run(setup_privacy())
