#!/usr/bin/env python3
"""
export_session_string.py — تصدير String Session من ملف الجلسة الحالي
=====================================================================
شغّله مرة واحدة على سيرفرك الحالي حيث الجلسة موجودة:
    python export_session_string.py

سيطبع SESSION_STRING جاهزاً للنسخ في config.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

try:
    from pyrogram import Client
except ImportError:
    print("❌ pyrogram غير مثبّت — شغّل: pip install pyrogram tgcrypto")
    sys.exit(1)

try:
    import config
except ImportError:
    print("❌ ملف config.py غير موجود!")
    sys.exit(1)


async def export_string_session():
    print("=" * 60)
    print("  تصدير String Session للحساب المساعد")
    print("=" * 60)
    print()

    session_file = Path(__file__).parent / "sessions" / "userbot.session"
    if not session_file.exists():
        print("❌ ملف الجلسة غير موجود في sessions/userbot.session")
        print("   شغّل setup_session.py أولاً لإنشاء الجلسة")
        sys.exit(1)

    # نفتح الجلسة الموجودة ونصدر string منها
    client = Client(
        name=str(Path(__file__).parent / "sessions" / "userbot"),
        api_id=config.API_ID,
        api_hash=config.API_HASH,
    )

    try:
        await client.start()
        me = await client.get_me()
        session_string = await client.export_session_string()
        await client.stop()

        print(f"✅ الحساب: {me.first_name} (@{me.username}) — ID: {me.id}")
        print()
        print("=" * 60)
        print("📋 انسخ هذا السطر وضعه في config.py :")
        print("=" * 60)
        print()
        print(f'SESSION_STRING = "{session_string}"')
        print()
        print("=" * 60)
        print("⚠️  تحذير أمني:")
        print("   هذا الـ string = دخول كامل لحساب تيليغرام")
        print("   لا تشاركه مع أي أحد خارج فريقك")
        print("   ضعه في config.py فقط إذا كان المشروع open source")
        print("   وأنت مقتنع بمشاركة هذا الحساب مع جميع المستخدمين")
        print("=" * 60)

    except Exception as e:
        print(f"❌ خطأ: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(export_string_session())
