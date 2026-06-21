<div dir="rtl">

# 🕌 البوت الإسلامي — Islamic Bot

بوت تيليغرام إسلامي متكامل يرسل محتوى دينياً تلقائياً، ويدعم البث الصوتي في المكالمات، والمسابقات، وأوقات الصلاة، وعشرات الميزات الأخرى — مع واجهة إعدادات لكل مجموعة وأدوات إدارة متقدمة.

---

## 📋 جدول المحتويات

- [الميزات](#-الميزات)
- [هيكل الملفات](#-هيكل-الملفات)
- [المتطلبات](#-المتطلبات)
- [دليل تثبيت المتطلبات للمبتدئين](#-دليل-تثبيت-المتطلبات-للمبتدئين)
- [التثبيت](#-التثبيت)
- [الإعداد — خطوة واحدة فقط](#-الإعداد)
- [إعداد البث الصوتي](#-إعداد-البث-الصوتي-اختياري)
- [تشغيل البوت](#-تشغيل-البوت)
- [حل المشاكل الشائعة](#-حل-المشاكل-الشائعة-windows-خصوصاً)
- [قائمة الأوامر](#-قائمة-الأوامر)
- [الجدول الزمني التلقائي](#-الجدول-الزمني-التلقائي)
- [إضافة المحتوى المحلي](#-إضافة-المحتوى-المحلي)
- [الأسئلة الشائعة](#-الأسئلة-الشائعة)

---

## ✨ الميزات

### 📖 المحتوى الديني التلقائي
- آيات قرآنية كريمة مع التفسير
- أحاديث نبوية شريفة من 6 كتب (32,000+ حديث)
- أذكار الصباح والمساء مجدولة مع الأذان
- أذكار وأدعية مأثورة
- اسم الله الحسنى يومياً (99 اسماً)
- كلمة قرآنية يومية مع التفسير
- عمل صالح يومي
- تذكير يومي بالتسبيح
- تذكير صلاة الجمعة وساعة الاستجابة
- تذكير صيام الاثنين والخميس
- مقتطف يومي من السيرة النبوية (مولّد بالذكاء الاصطناعي)

### 🕌 ميزات تفاعلية
- أوقات الصلاة الحية لأي مدينة (aladhan.com)
- صور وفيديوهات إسلامية تُنشر تلقائياً (مرتين يومياً بأوقات عشوائية)
- سبحة إلكترونية تفاعلية مع عداد
- مسابقات إسلامية كل ساعتين مع نظام نقاط ولوحة شرف
- تلاوات قرآنية صوتية mp3 بأصوات قراء متعددين
- راديو القرآن المباشر 24 ساعة
- مكتبة كتب إسلامية PDF
- ردود تلقائية على العبارات الإسلامية (جزاك الله، ماشاء الله...)

### 🎵 البث الصوتي
- بث يوتيوب في مكالمات المجموعات والقنوات
- راديو القرآن مباشرة في المكالمة
- أوامر تحكم كاملة (إيقاف، تعليق، استئناف)

### 🎬 تيك توك
- تحميل فيديوهات TikTok بدون علامة مائية عبر `/tiktok`
- خيار حفظ الفيديوهات في مكتبة `videos/` للنشر التلقائي

### ⚙️ إعدادات كل دردشة على حدة
- أمر `/settings` لكل مجموعة يتيح تفعيل أو تعطيل أي ميزة مستقلة
- واجهة أزرار تفاعلية — لا حاجة لتعديل ملفات
- تفعيل/تعطيل الكل بضغطة واحدة

### 🛠️ أدوات إدارة متقدمة (للمدير الرئيسي)
- `/files` — تصفح ملفات البوت عن بُعد
- `/restart` — إعادة تشغيل البوت
- `/update` — سحب آخر تحديث من git
- `/logs` — عرض آخر سطور السجل
- `/shell` — تنفيذ أوامر shell مباشرة

### 📡 إدارة ذكية
- ينضم ويغادر المجموعات تلقائياً
- يحفظ المجموعات في `channels.json`
- أمر `/broadcast` لإرسال رسائل مخصصة لكل الدردشات
- دعم كامل للقنوات وأوامرها

---

## 📁 هيكل الملفات

```
islamic-bot/
│
├── bot.py                    # الملف الرئيسي — المنطق والجدولة
├── config.py                 # ⚙️ الإعدادات — الملف الوحيد الذي تعدّله
├── run_all.py                # نقطة التشغيل الموحدة
│
├── islamic_features.py       # تلاوات، جمعة، سبحة، راديو صوتي
├── new_features.py           # مسابقات، سيرة نبوية، ردود إسلامية
├── image_broadcast.py        # نشر الصور والفيديوهات الإسلامية
├── tiktok_downloader.py      # تحميل فيديوهات TikTok
├── chat_settings.py          # إعدادات كل دردشة (/settings)
├── file_manager.py           # إدارة ملفات البوت عن بُعد
├── restart_manager.py        # إعادة التشغيل والتحديث عن بُعد
│
├── voice_player.py           # محرك البث الصوتي (py-tgcalls)
├── voice_commands.py         # أوامر /play /stop /pause /resume
│
├── setup_session.py          # إنشاء جلسة الـ Userbot (مرة واحدة)
├── export_session_string.py  # تصدير String Session للـ config.py
├── setup_privacy.py          # ضبط خصوصية الـ Userbot (مرة واحدة)
├── setup_telethon.py         # إنشاء جلسة Telethon (بديل اختياري)
│
├── .gitignore                # ✅ يحمي بياناتك من الرفع على GitHub
│
├── channels.json             # قائمة المجموعات/القنوات (يُنشأ تلقائياً)
├── quiz_scores.json          # نقاط المسابقة (يُنشأ تلقائياً)
├── chat_settings.json        # إعدادات الدردشات (يُنشأ تلقائياً)
│
├── books/                    # كتب PDF تُضاف يدوياً
├── images/                   # صور إسلامية
├── videos/                   # فيديوهات إسلامية
├── sessions/                 # ملفات جلسات الـ Userbot — لا ترفعها لـ GitHub
│
└── content/                  # محتوى JSON محلي
    ├── stories.json
    ├── duas.json
    ├── facts.json
    ├── good_deeds.json
    └── adhan_messages.json
```

---

## 📦 المتطلبات

### متطلبات النظام
- Python **3.11.9** تحديداً — تجنّب 3.12/3.13 حالياً، فبعض النسخ المُجمَّعة مسبقاً لمكتبات `pyrogram`/`py-tgcalls`/`tgcrypto` على Windows غير متوافقة معها وتسبب أخطاء تثبيت أو تشغيل
- ffmpeg (مطلوب فقط للبث الصوتي)

### المكتبات الأساسية (مطلوبة دائماً)

| المكتبة | الوظيفة |
|---------|---------|
| `python-telegram-bot[job-queue]` | التفاعل مع Telegram Bot API |
| `aiohttp` | طلبات HTTP غير متزامنة |
| `apscheduler` | جدولة المهام التلقائية |

### المكتبات الاختيارية

| المكتبة | الوظيفة | يحتاجها |
|---------|---------|---------|
| `kurigram` + `tgcrypto` | الحساب المساعد (Userbot) | /play, /sendimage |
| `py-tgcalls` | الانضمام لمكالمات تيليغرام | /play, /radio |
| `yt-dlp` | جلب روابط يوتيوب وتيك توك | /play, /tiktok |
| `telethon` | جلب صور القنوات | image_broadcast |

> ⚠️ **استخدم `kurigram` وليس `pyrogram`.** حزمة `pyrogram` الأصلية على PyPI متوقفة عن الصيانة الفعلية ولا تحتوي على فئات أخطاء جديدة تحتاجها النسخة الحديثة من `py-tgcalls`، ما يسبب خطأ `ImportError: cannot import name 'GroupcallForbidden'` عند تشغيل البث الصوتي. `kurigram` بديل محدّث يُستورد بنفس الاسم (`import pyrogram`) فلا حاجة لتعديل أي كود — فقط استبدل اسم الحزمة عند التثبيت. التفاصيل والحل الكامل في [حل المشاكل الشائعة](#-حل-المشاكل-الشائعة-windows-خصوصاً).

---

## 🆕 دليل تثبيت المتطلبات للمبتدئين

> إذا كانت هذه أول مرة تتعامل فيها مع Python أو سطر الأوامر، اتبع هذا الدليل بالكامل أولاً، ثم انتقل إلى قسم [🚀 التثبيت](#-التثبيت) لإكمال إعداد المشروع نفسه. الدليل يغطي **Windows** بالتفصيل (عبر `winget`)، مع خطوات مختصرة لـ macOS و Linux في الأسفل.

### الخطوة 0 — التأكد من وجود winget

`winget` هو مدير الحزم الرسمي من Microsoft، ويُستخدم لتثبيت كل البرامج التالية بأمر واحد بدل البحث والتحميل يدوياً. يأتي مثبتاً مسبقاً على Windows 11 وأغلب نسخ Windows 10 المحدّثة.

افتح **PowerShell**: اضغط زر Windows، اكتب `PowerShell`، ثم اضغط Enter. اكتب داخله:

```powershell
winget --version
```

- ظهر رقم إصدار؟ → ممتاز، تابع للخطوة التالية.
- ظهرت رسالة خطأ بأن الأمر غير معروف؟ → افتح **Microsoft Store**، ابحث عن **App Installer**، وثبّته/حدّثه، ثم أعد فتح PowerShell وجرّب من جديد.

### الخطوة 1 — تثبيت Python و pip

> ⚠️ **مهم:** ثبّت **3.11.9 تحديداً**، وليس آخر إصدار متوفر. بعض المكتبات (`pyrogram`/`kurigram`، `tgcrypto`، `py-tgcalls`) تعتمد على نسخ مُجمَّعة مسبقاً (wheels) قد لا تكون متوفرة بعد لإصدارات أحدث مثل 3.12 أو 3.13 على Windows، ما يسبب أخطاء تثبيت غريبة لاحقاً.

```powershell
winget install --id Python.Python.3.11 -v 3.11.9
```

بعد انتهاء التثبيت، **أغلق نافذة PowerShell وافتحها من جديد** (ضروري حتى تتحدّث متغيرات PATH)، ثم تحقق من التثبيت:

```powershell
python --version
pip --version
```

يجب أن يظهر بالضبط `Python 3.11.9`. إذا ظهر إصدار مختلف (مثلاً كان عندك Python آخر مثبتاً مسبقاً)، استخدم `py -3.11 --version` للتأكد من وجود 3.11.9 بين الإصدارات المثبتة، واستبدل `python` بـ `py -3.11` في باقي الأوامر.

`pip` (مدير مكتبات Python) يأتي مدمجاً مع Python تلقائياً ولا يحتاج تثبيتاً منفصلاً، لكن يُفضّل تحديثه دائماً لآخر إصدار:

```powershell
python -m pip install --upgrade pip
```

> 💡 بديل يدوي: يمكنك أيضاً تحميل المثبت مباشرة من [نسخة 3.11.9 على python.org](https://www.python.org/downloads/release/python-3119/) — لا تستخدم رابط التحميل العام لأنه يعطيك آخر إصدار. في أول شاشة بالمثبت، **تأكد من تفعيل خيار "Add python.exe to PATH"** أسفل النافذة — هذا الخيار ضروري جداً وكثيراً ما يُنسى، وبدونه لن يتعرف سطر الأوامر على `python`.

### الخطوة 2 — تثبيت Git

Git ضروري لاستنساخ (clone) المشروع من GitHub، ولاحقاً لتحديثه عبر أمر البوت `/update`.

```powershell
winget install Git.Git
```

أعد فتح PowerShell، ثم تحقق:

```powershell
git --version
```

### الخطوة 3 — تثبيت ffmpeg (فقط إذا أردت استخدام /play و /radio)

```powershell
winget install Gyan.FFmpeg
```

أعد فتح PowerShell، ثم تحقق:

```powershell
ffmpeg -version
ffprobe -version
```

> ⚠️ **علّة معروفة:** حزمة `Gyan.FFmpeg` على winget لديها خلل قديم وما يزال غير مُصلَح — تضيف إلى PATH مجلد التثبيت الجذري بدل مجلد `bin` الذي يحتوي فعلياً على `ffmpeg.exe` و `ffprobe.exe`. النتيجة: يبقى الأمر "غير معروف" حتى بعد إعادة تشغيل الجهاز بالكامل، لأن PATH نفسه مضبوط خطأ من الأساس وليست مجرد مشكلة تحديث. إذا واجهت هذا، راجع [حل المشاكل الشائعة](#-حل-المشاكل-الشائعة-windows-خصوصاً) أدناه للحل الكامل.

### الخطوة 4 — تثبيت VS Code (محرر الأكواد)

```powershell
winget install Microsoft.VisualStudioCode
```

بعد التثبيت، افتح VS Code وثبّت إضافة Python الرسمية من Microsoft (تمنحك تلوين الأكواد، الإكمال التلقائي، وتشغيل/تصحيح الأخطاء بسهولة):

1. اضغط على أيقونة الإضافات (Extensions) في الشريط الجانبي، أو اختصار `Ctrl+Shift+X`
2. ابحث عن **Python** (الناشر: Microsoft) واضغط **Install**

أو ثبّتها مباشرة من سطر الأوامر (بعد فتح VS Code مرة واحدة على الأقل ليُسجَّل أمر `code`):

```powershell
code --install-extension ms-python.python
```

### الخطوة 5 — استنساخ المشروع وفتحه في VS Code

```powershell
git clone https://github.com/kyooamine/Islamic-Telegram-Bot.git
cd Islamic-Telegram-Bot
code .
```

الأمر الأخير `code .` يفتح مجلد المشروع مباشرة داخل VS Code.

### الخطوة 6 — فتح Terminal داخل VS Code

من القائمة العلوية في VS Code اختر **Terminal → New Terminal**، أو استخدم الاختصار:

```
Ctrl + `
```

من هذا الـ Terminal تابع مباشرة خطوات [🚀 التثبيت](#-التثبيت) أدناه: إنشاء البيئة الافتراضية، تثبيت المكتبات، تعديل `config.py`، وتشغيل البوت.

### 🍎 macOS

استخدم [Homebrew](https://brew.sh) بدل winget:

```bash
brew install python git ffmpeg
brew install --cask visual-studio-code
```

### 🐧 Linux (Ubuntu / Debian)

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv git ffmpeg -y
sudo snap install --classic code   # أو حمّله من code.visualstudio.com
```

### ملخص سريع — ماذا ثبّتنا ولماذا؟

| الأداة | لماذا تحتاجها |
|--------|----------------|
| **winget** | لتثبيت كل ما يلي بأمر واحد بدون بحث أو تحميل يدوي (Windows فقط) |
| **Python + pip** | لتشغيل البوت وتثبيت مكتباته |
| **Git** | لاستنساخ المشروع، ولاحقاً تحديثه عبر `/update` |
| **ffmpeg** | لتشغيل ميزات البث الصوتي `/play` و `/radio` فقط — اختياري |
| **VS Code** | لفتح المشروع وتعديل `config.py` وقراءة الكود بسهولة |

---

## 🚀 التثبيت

> إذا اتبعت [دليل تثبيت المتطلبات للمبتدئين](#-دليل-تثبيت-المتطلبات-للمبتدئين) أعلاه، يكون المشروع مستنسخاً بالفعل ومفتوحاً في VS Code — انتقل مباشرة للخطوة 2.

### 1. استنساخ المشروع

```bash
git clone https://github.com/kyooamine/Islamic-Telegram-Bot.git
cd Islamic-Telegram-Bot
```

### 2. إنشاء بيئة افتراضية (موصى به)

```bash
python -m venv venv

# Linux / macOS
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. تثبيت المكتبات

**التثبيت الأساسي (بدون بث صوتي أو تيك توك):**
```bash
pip install python-telegram-bot[job-queue] aiohttp apscheduler
```

**التثبيت الكامل (كل الميزات):**
```bash
pip install python-telegram-bot[job-queue] aiohttp apscheduler \
            kurigram tgcrypto py-tgcalls yt-dlp telethon
```

> لا تثبّت `pyrogram` العادية — استخدم `kurigram` كما هو موضح أعلاه. إذا ثبّت `pyrogram` بالخطأ سابقاً: `pip uninstall pyrogram -y` قبل تنفيذ الأمر أعلاه.

### 4. تثبيت ffmpeg (للبث الصوتي فقط)

```bash
# Ubuntu / Debian
sudo apt update && sudo apt install ffmpeg -y

# macOS
brew install ffmpeg

# Windows — winget install Gyan.FFmpeg
# أو حمّل يدوياً من: https://ffmpeg.org/download.html وأضفه لـ PATH
```

---

## ⚙️ الإعداد

> **الإعداد كله في ملف واحد فقط: `config.py`**

افتح `config.py` وأكمل هذه الحقول:

### [1] توكن البوت ✅ مطلوب

```python
BOT_TOKEN = "1234567890:AAF..."
```
احصل عليه من [@BotFather](https://t.me/BotFather).

### [2] Anthropic API Key ⚡ لـ /quiz و /seerah

```python
ANTHROPIC_API_KEY = "sk-ant-api03-..."
```
احصل عليه من [console.anthropic.com](https://console.anthropic.com). إذا تركته فارغاً، تعمل `/quiz` بأسئلة احتياطية مدمجة.

### [3] إعدادات أوقات الصلاة ✅ مطلوب

```python
PRAYER_CITY    = "Riyadh"        # اسم مدينتك بالإنجليزية
PRAYER_COUNTRY = "Saudi Arabia"  # اسم دولتك بالإنجليزية
PRAYER_METHOD  = 4               # طريقة الحساب — راجع aladhan.com
TIMEZONE       = "Asia/Riyadh"   # منطقتك الزمنية
```

### [4] معرفات المشرفين 🔒 اختياري

```python
BROADCAST_ADMIN_IDS = [123456789]  # من يمكنه /broadcast
UPLOAD_ADMIN_IDS    = [123456789]  # من يمكنه رفع صور
ALLOWED_USER_IDS    = [123456789]  # من يمكنه أوامر الإدارة المتقدمة
```
احصل على معرفك من [@userinfobot](https://t.me/userinfobot).

---

## 🎵 إعداد البث الصوتي (اختياري)

> البوت يعمل بالكامل بدون هذه الخطوات. تحتاجها فقط لأوامر `/play` و `/radio`.

### الخطوة 1 — الحصول على API credentials

1. اذهب إلى [my.telegram.org](https://my.telegram.org)
2. سجّل الدخول واضغط **API development tools**
3. أنشئ تطبيقاً واحصل على `API_ID` و `API_HASH`

```python
API_ID   = 12345678
API_HASH = "abcdef1234567890abcdef1234567890"
```

### الخطوة 2 — إنشاء String Session (مرة واحدة فقط)

```bash
python setup_session.py
```

سيطلب رقم الهاتف وكود التحقق.

### الخطوة 3 — تصدير String Session إلى config.py

```bash
python export_session_string.py
```

انسخ الناتج إلى `config.py`:

```python
SESSION_STRING = "BQAXmj8AJk3n..."
```

### الخطوة 4 — ضبط الخصوصية (مرة واحدة فقط)

```bash
python setup_privacy.py
```

يجعل الحساب المساعد ينضم تلقائياً لأي مجموعة عند استخدام `/play`.

---

## ▶️ تشغيل البوت

```bash
python run_all.py
```

للتشغيل المستمر في الخلفية على Linux:

```bash
# باستخدام screen
screen -S islamic-bot
python run_all.py
# Ctrl+A ثم D للخروج مع إبقاء البوت يعمل

# باستخدام nohup
nohup python run_all.py > bot.log 2>&1 &

# باستخدام systemd (موصى به للإنتاج)
```

**مثال ملف systemd:**

```ini
[Unit]
Description=Islamic Telegram Bot
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/Islamic-Telegram-Bot
ExecStart=/path/to/Islamic-Telegram-Bot/venv/bin/python run_all.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable islamic-bot
sudo systemctl start islamic-bot
sudo systemctl status islamic-bot
```

---

## 🔧 حل المشاكل الشائعة (Windows خصوصاً)

> هذه مشاكل واجهناها فعلياً أثناء إعداد البث الصوتي على Windows. اقرأ هذا القسم قبل فتح issue جديد إذا كنت تستخدم `/play` أو `/radio`.

### ❌ `ImportError: cannot import name 'GroupcallForbidden' from 'pyrogram.errors'`

**السبب:** حزمة `pyrogram` الأصلية على PyPI متوقفة عن الصيانة الفعلية، ولا تحتوي على فئات أخطاء (error classes) جديدة تحتاجها النسخة الحديثة من `py-tgcalls`. النتيجة: فشل الاستيراد فور محاولة `voice_player.py` بدء تشغيل المكالمة الصوتية.

**الحل:** استبدل `pyrogram` بـ `kurigram`، وهو بديل محدّث يُستورد بنفس الاسم تماماً (`from pyrogram import ...`)، فلا حاجة لتعديل أي سطر كود — فقط استبدل الحزمة المثبَّتة:

```bash
pip uninstall pyrogram -y
pip install kurigram
```

(`pyrofork` بديل آخر يعمل بنفس الطريقة: `pip install pyrofork`)

إذا كان لديك ملف `requirements.txt` منفصل، استبدل سطر `pyrogram` فيه بـ `kurigram` أيضاً حتى لا تواجه نفس المشكلة عند تثبيت المشروع على جهاز آخر.

### ❌ `ntgcalls.FFmpegError: ffprobe not installed`

يظهر هذا الخطأ حتى لو كان ffmpeg مثبتاً فعلياً عبر winget، بسبب علّة معروفة وما تزال غير مُصلَحة في حزمة `Gyan.FFmpeg`: الحزمة تضيف إلى PATH مجلد التثبيت **الجذري** بدل مجلد **`bin`** الذي يحتوي فعلياً على `ffmpeg.exe` و `ffprobe.exe`. لهذا السبب، حتى إعادة تشغيل الجهاز بالكامل لا تحل المشكلة — PATH نفسه مضبوط خطأ من الأساس، وليست مجرد مشكلة تحديث لم تُطبَّق.

**الخطوة 1 — تحقق من المسار الصحيح:**

```powershell
Get-ChildItem -Recurse -Filter ffprobe.exe -Path $env:LOCALAPPDATA\Microsoft\WinGet\Packages -ErrorAction SilentlyContinue
```

سيظهر مساراً يشبه:
```
...\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.x-full_build\bin\ffprobe.exe
```

**الخطوة 2 — الحل الأسرع والأضمن:** أضف هذا في أعلى `run_all.py`، **قبل** أي استيراد آخر (خصوصاً قبل أي شيء يستورد `pytgcalls`):

```python
import os
FFMPEG_BIN = r"C:\Users\اسمك\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.x-full_build\bin"
os.environ["PATH"] = FFMPEG_BIN + os.pathsep + os.environ["PATH"]
```

عدّل المسار حسب نتيجة أمر `Get-ChildItem` أعلاه ورقم نسخة ffmpeg لديك. هذا الحل يعمل بغض النظر عن حالة PATH في نظام Windows نفسه، ولا يتأثر بإعادة تشغيل الجهاز أو إعدادات VS Code.

**الحل البديل (إصلاح PATH يدوياً بدل تعديل الكود):** افتح "Edit environment variables for your account" من قائمة ابدأ، ابحث عن المدخل الذي أضافه winget (مسار بدون `\bin` في النهاية)، احذفه، وأضف بدلاً منه المسار الصحيح المنتهي بـ `\bin`. ثم أغلق VS Code بالكامل وأعد فتحه.

### 💡 ملاحظة عامة حول مشاكل PATH على Windows

كثير من رسائل "البرنامج غير مثبت" رغم أنه مثبت فعلياً سببها أن العملية (terminal أو VS Code) التي تشغّل البوت بدأت قبل أن يتحدّث PATH على مستوى النظام. الترتيب الموصى به عند ظهور أي خطأ من نوع "command not found" أو "FileNotFoundError" بعد تثبيت أداة جديدة:

1. أغلق **نافذة VS Code بالكامل** (ليس فقط الـ Terminal) — تأكد عبر Task Manager أنه لا توجد عملية `Code.exe` متبقية.
2. أعد فتح VS Code وجرّب من جديد.
3. إذا استمرت المشكلة، أعد تشغيل الجهاز بالكامل.
4. إذا استمرت حتى بعد إعادة التشغيل (كما في حالة `Gyan.FFmpeg` أعلاه)، تحقق يدوياً من قيمة PATH الفعلية بدل افتراض أن المشكلة ستُحل تلقائياً.

---

## 📜 قائمة الأوامر

### أوامر المحتوى الديني

| الأمر | الوصف |
|-------|-------|
| `/start` أو `/help` | عرض قائمة الأوامر |
| `/aya` | آية قرآنية عشوائية مع التفسير |
| `/hadith` | حديث نبوي شريف |
| `/dua` | دعاء مأثور |
| `/story` | قصة إسلامية هادفة |
| `/fact` | معلومة إسلامية |
| `/adhan` | أوقات الصلاة الآن |
| `/morning` | أذكار الصباح |
| `/evening` | أذكار المساء |
| `/tasbih` | تذكير التسبيح |
| `/word` | كلمة قرآنية يومية |
| `/name` | اسم الله الحسنى اليومي |
| `/deed` | عمل صالح يومي |
| `/seerah` | مقتطف من السيرة النبوية |

### أوامر الميزات التفاعلية

| الأمر | الوصف |
|-------|-------|
| `/recitation` | تلاوات قرآنية صوتية mp3 |
| `/tasbeeh` | سبحة إلكترونية تفاعلية |
| `/friday` | ساعة الاستجابة يوم الجمعة |
| `/quiz` | مسابقة إسلامية عشوائية |
| `/scores` | لوحة الشرف والنقاط |
| `/radio` | راديو القرآن المباشر |
| `/books` | مكتبة الكتب الإسلامية PDF |
| `/tiktok [رابط]` | تحميل فيديو TikTok بدون علامة مائية |

### أوامر البث الصوتي

| الأمر | الوصف |
|-------|-------|
| `/play [رابط يوتيوب]` | بث صوت في المكالمة الصوتية |
| `/stop` | إيقاف البث ومغادرة المكالمة |
| `/pause` | تعليق البث مؤقتاً |
| `/resume` | استئناف البث |
| `/nowplaying` | عرض ما يُبَث حالياً |

### أوامر الإدارة

| الأمر | الوصف | متاح لـ |
|-------|-------|---------|
| `/settings` | إعدادات ميزات البوت في هذه الدردشة | مشرفو الدردشة |
| `/broadcast [نص]` | إرسال رسالة لكل الدردشات | BROADCAST_ADMIN_IDS |
| `/sendimage` | نشر صورة/فيديو عشوائي | UPLOAD_ADMIN_IDS |
| `/media` | عرض وإدارة مكتبة الوسائط | UPLOAD_ADMIN_IDS |
| `/leave` | مغادرة المجموعة الحالية | مشرفو الدردشة |
| `/files` | تصفح ملفات البوت عن بُعد | ALLOWED_USER_IDS |
| `/restart` | إعادة تشغيل البوت | ALLOWED_USER_IDS |
| `/update` | سحب آخر تحديث من git | ALLOWED_USER_IDS |
| `/logs` | عرض آخر سطور السجل | ALLOWED_USER_IDS |
| `/shell [أمر]` | تنفيذ أمر shell | ALLOWED_USER_IDS |

---

## 🕐 الجدول الزمني التلقائي

| الوقت | المهمة |
|-------|--------|
| عند الفجر | أذان الفجر + أذكار الصباح |
| عند الظهر | أذان الظهر |
| عند العصر | أذان العصر + أذكار المساء |
| عند المغرب | أذان المغرب |
| عند العشاء | أذان العشاء |
| 8:00 صباحاً | عمل صالح يومي |
| 9:00 صباحاً | تذكير التسبيح |
| 10:00 صباحاً | مقتطف من السيرة النبوية |
| 12:00 ظهراً | كلمة قرآنية يومية |
| 7:00 مساءً | اسم الله الحسنى |
| وقتان عشوائيان يومياً | صورة/فيديو إسلامي |
| كل 30 دقيقة (7 ص — 11 م) | محتوى عشوائي (قرآن / حديث / دعاء / صورة...) |
| كل ساعتين | مسابقة إسلامية |
| كل جمعة 8:00 ص | تذكير صلاة الجمعة |
| كل جمعة 15:15 | تذكير ساعة الاستجابة |
| كل اثنين 6:00 ص | تذكير صيام الاثنين |
| كل خميس 6:00 ص | تذكير صيام الخميس |

> يمكن تعطيل أي مهمة من هذه عبر `/settings` في كل دردشة على حدة.

---

## 📂 إضافة المحتوى المحلي

### الكتب الإسلامية (PDF)

ضع ملفات PDF في مجلد `books/` — يظهر كل كتاب تلقائياً في `/books`:

```
books/
├── رياض_الصالحين.pdf
└── الأذكار_النووي.pdf
```

### الصور والفيديوهات

**عبر البوت مباشرة:** أرسل أي صورة أو فيديو للبوت في الخاص أو عبر `/sendimage`.

**يدوياً:**
```
images/
├── morning_adhkar.jpg    # يُرسل مع أذكار الصباح
└── quran_verse.png

videos/
└── islamic_reminder.mp4
```

أسماء الملفات التي تحتوي على "morning" تُصنّف تلقائياً كأذكار صباح.

### ملفات JSON للمحتوى المحلي

**`content/duas.json`:**
```json
[
  {
    "title": "دعاء دخول المنزل",
    "arabic": "اللهم إني أسألك خير المولج وخير المخرج...",
    "source": "سنن أبي داود"
  }
]
```

**`content/good_deeds.json`:**
```json
[
  { "deed": "اتصل بأحد والديك اليوم وابدأ بالسلام" },
  { "deed": "تصدّق بشيء ولو قليل" }
]
```

---

## ❓ الأسئلة الشائعة

**س: البوت لا يرد في المجموعة**
← تأكد أن البوت مشرف أو مسموح له بإرسال الرسائل، وأن `channels.json` يحتوي ID المجموعة (يُنشأ تلقائياً عند إضافة البوت).

**س: أوقات الصلاة خاطئة**
← تحقق من `PRAYER_CITY` و `PRAYER_COUNTRY` و `PRAYER_METHOD` في `config.py`.

**س: /play لا يعمل**
← تأكد من: (1) وجود `SESSION_STRING` في `config.py`، (2) تثبيت `kurigram tgcrypto py-tgcalls yt-dlp` (وليس `pyrogram` العادية)، (3) وجود مكالمة صوتية نشطة في المجموعة. إذا واجهت خطأ `GroupcallForbidden` أو `ffprobe not installed`، راجع [حل المشاكل الشائعة](#-حل-المشاكل-الشائعة-windows-خصوصاً).

**س: /quiz و /seerah لا يعملان**
← أضف `ANTHROPIC_API_KEY` في `config.py`. بدونه تعمل `/quiz` بأسئلة احتياطية، لكن `/seerah` تحتاج المفتاح.

**س: /tiktok لا يعمل**
← شغّل `pip install yt-dlp` وتأكد من صحة رابط التيك توك.

**س: /settings لا يظهر**
← الأمر متاح للمشرفين فقط داخل المجموعات والقنوات.

**س: /restart أو /files لا تعمل**
← تأكد أن معرفك موجود في `ALLOWED_USER_IDS` في `config.py`.

**س: البوت يعمل لكن لا يرسل تلقائياً**
← تأكد أن البوت موجود في مجموعة وتم تفعيله عبر `/start`، وأن الميزة مفعّلة في `/settings`.

---

## 📊 المصادر المستخدمة

| المصدر | البيانات |
|--------|---------|
| [fawazahmed0/quran-api](https://github.com/fawazahmed0/quran-api) | نصوص القرآن الكريم |
| [fawazahmed0/hadith-api](https://github.com/fawazahmed0/hadith-api) | 32,000+ حديث |
| [nawafalqari/azkar-api](https://github.com/nawafalqari/azkar-api) | أذكار الصباح والمساء |
| [aladhan.com](https://aladhan.com) | أوقات الصلاة |
| [everyayah.com](https://everyayah.com) | تلاوات قرآنية mp3 |
| [mp3quran.net](https://mp3quran.net) | سور قرآنية كاملة |
| [Anthropic Claude](https://anthropic.com) | توليد أسئلة المسابقة ومقتطفات السيرة |

---

## 📄 الرخصة

هذا المشروع مفتوح المصدر — يمكنك استخدامه وتعديله وتوزيعه بحرية.

---

<div align="center">

**﴿فَاذْكُرُونِي أَذْكُرْكُمْ﴾**

جزاك الله خيراً على استخدام هذا البوت ونشر الخير 🌿

</div>

</div>
