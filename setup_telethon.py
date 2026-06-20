#!/usr/bin/env python3
"""
setup_telethon.py — إنشاء جلسة Telethon للحساب المساعد
شغّل هذا الملف مرة واحدة: python setup_telethon.py
"""

import asyncio
import sys
from pathlib import Path

# إضافة المجلد الحالي إلى المسار
sys.path.insert(0, str(Path(__file__).parent))

import config
from telethon import TelegramClient

async def main():
    print("=" * 55)
    print("  إنشاء جلسة Telethon للحساب المساعد")
    print("=" * 55)
    print()
    
    # تحديد مسار الجلسة (نستخدم نفس المتغير SESSION_NAME من config)
    session_path = config.SESSION_NAME
    print(f"سيتم حفظ الجلسة في: {session_path}.session")
    
    client = TelegramClient(session_path, config.API_ID, config.API_HASH)
    
    try:
        await client.start()
        me = await client.get_me()
        print()
        print("✅ تم إنشاء الجلسة بنجاح!")
        print(f"   الحساب: {me.first_name} (@{me.username}) — ID: {me.id}")
        print(f"   ملف الجلسة: {session_path}.session")
        await client.disconnect()
    except Exception as e:
        print(f"❌ فشل إنشاء الجلسة: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())