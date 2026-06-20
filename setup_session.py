#!/usr/bin/env python3
"""
setup_session.py — إنشاء جلسة الحساب المساعد (مرة واحدة فقط)
شغّل هذا الملف قبل تشغيل البوت لأول مرة:
    python setup_session.py
"""

import asyncio
import sys
from pathlib import Path

# التحقق من وجود المكتبات
try:
    from pyrogram import Client
except ImportError:
    print("❌ مكتبة pyrogram غير مثبّتة!")
    print("   شغّل: pip install pyrogram tgcrypto")
    sys.exit(1)

try:
    import config
except ImportError:
    print("❌ ملف config.py غير موجود!")
    sys.exit(1)


SESSION_DIR = Path(__file__).parent / "sessions"
SESSION_DIR.mkdir(exist_ok=True)


async def create_session():
    print("=" * 55)
    print("  إنشاء جلسة الحساب المساعد (Userbot Session)")
    print("=" * 55)
    print()

    # التحقق من الإعدادات
    if not config.API_ID or config.API_ID == 0:
        print("❌ API_ID غير مُعيَّن في config.py")
        print("   احصل عليه من: https://my.telegram.org → API development tools")
        return

    if not config.API_HASH:
        print("❌ API_HASH غير مُعيَّن في config.py")
        return

    print(f"✅ API_ID: {config.API_ID}")
    print(f"✅ API_HASH: {config.API_HASH[:8]}...")
    print()
    print("📱 ستحتاج إلى إدخال رقم هاتف الحساب الذي سيُستخدم كحساب مساعد.")
    print("   يُفضّل استخدام حساب ثانٍ وليس حسابك الرئيسي.")
    print()

    session_file = SESSION_DIR / "userbot.session"

    try:
        client = Client(
            name=str(SESSION_DIR / "userbot"),
            api_id=config.API_ID,
            api_hash=config.API_HASH,
        )

        await client.start()
        me = await client.get_me()
        await client.stop()

        print()
        print("=" * 55)
        print(f"✅ تم إنشاء الجلسة بنجاح!")
        print(f"   الحساب: {me.first_name} (@{me.username or 'بدون username'})")
        print(f"   الملف:  {session_file}")
        print()
        print("⚠️  تأكد من إضافة هذا الحساب كعضو في قناتك/مجموعتك")
        print("    حتى يتمكن من الانضمام للمكالمات الصوتية.")
        print()
        print("🚀 يمكنك الآن تشغيل البوت بـ: python run_all.py")
        print("=" * 55)

    except Exception as e:
        print(f"❌ فشل إنشاء الجلسة: {e}")
        print()
        if "PHONE_NUMBER_INVALID" in str(e):
            print("   تأكد من كتابة رقم الهاتف بالصيغة الدولية: +213...")
        elif "API_ID_INVALID" in str(e):
            print("   تأكد من صحة API_ID و API_HASH في config.py")
        elif "PHONE_CODE_INVALID" in str(e):
            print("   الكود الذي أدخلته غير صحيح، حاول مرة أخرى.")


if __name__ == "__main__":
    asyncio.run(create_session())
