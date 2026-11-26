<!-- mcp-name: io.github.zhouxiaoka/autoclip-mcp -->

<div align="center">

<img src="../../src-tauri/icons/128x128.png" alt="AutoClip" width="76" height="76">

# AutoClip

### حوّل أي فيديو أو رابط أو بث مباشر إلى مقاطع جاهزة للنشر.

**البديل مفتوح المصدر لـ OpusClip** — قصّ بالذكاء الاصطناعي يعمل محليًا أولًا **للبودكاست والمقابلات وبثوث الألعاب** مع إعادة تأطير ذكية، وترجمات مدمجة، وأغلفة، وعناوين، ودعم مدمج لـ **MCP لوكلاء الذكاء الاصطناعي**. دون اشتراكات ودون قيود دفع.

<br>

<p>
  <a href="https://github.com/zhouxiaoka/autoclip/releases/latest"><img src="https://img.shields.io/github/v/release/zhouxiaoka/autoclip?style=flat-square&color=4F46E5" alt="GitHub release" height="20"></a>&nbsp;
  <a href="https://github.com/zhouxiaoka/autoclip/stargazers"><img src="https://img.shields.io/github/stars/zhouxiaoka/autoclip?style=flat-square&color=FFD700&logo=github&logoColor=white&label=Stars" alt="GitHub stars" height="20"></a>&nbsp;
  <a href="https://github.com/zhouxiaoka/autoclip/releases"><img src="https://img.shields.io/github/downloads/zhouxiaoka/autoclip/total?style=flat-square&color=10B981" alt="Downloads" height="20"></a>&nbsp;
  <img src="https://img.shields.io/badge/Languages-20-0EA5E9?style=flat-square" alt="20 Languages" height="20">&nbsp;
  <a href="../../LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue?style=flat-square" alt="License: MIT" height="20"></a>
</p>

<br>

<!-- hero-cta:start -->
<p>
  <a href="https://zhouxiaoka.github.io/autoclip_intro/"><img src="../../docs/images/download-button.svg" alt="Download AutoClip" width="248" height="55"></a>&nbsp;&nbsp;
  <a href="https://trendshift.io/repositories/25801"><img src="https://trendshift.io/api/badge/repositories/25801" alt="AutoClip — GitHub Trending" width="250" height="55"></a>
</p>
<!-- hero-cta:end -->

<br>

<p>
  <a href="https://zhouxiaoka.github.io/autoclip_intro/"><strong>الموقع الرسمي</strong></a>
  &nbsp;&middot;&nbsp;
  <a href="https://github.com/zhouxiaoka/autoclip/releases/latest"><strong>التنزيل</strong></a>
  &nbsp;&middot;&nbsp;
  <a href="https://zhouxiaoka.github.io/autoclip_intro/features/game-streams/"><strong>إعادات البث المباشر (v1.6)</strong></a>
  &nbsp;&middot;&nbsp;
  <a href="https://zhouxiaoka.github.io/autoclip_intro/cases/?lang=en"><strong>معرض النماذج</strong></a>
  &nbsp;&middot;&nbsp;
  <a href="#quick-start"><strong>البدء السريع</strong></a>
  &nbsp;&middot;&nbsp;
  <a href="#documentation"><strong>التوثيق</strong></a>
  &nbsp;&middot;&nbsp;
  <a href="https://github.com/zhouxiaoka/autoclip/issues/new/choose"><strong>المشكلات</strong></a>
</p>

<p>
  <a href="../../README.md">English</a> · <a href="README-ZH.md">简体中文</a> · <a href="README-ZH-TW.md">繁體中文</a> · <a href="README-JA.md">日本語</a> · <a href="README-KO.md">한국어</a> · <a href="README-ES.md">Español</a> · <a href="README-PT.md">Português</a> · <a href="README-RU.md">Русский</a> · <a href="README-FR.md">Français</a> · <a href="README-ID.md">Bahasa Indonesia</a> · <a href="README-TR.md">Türkçe</a> · <a href="README-VI.md">Tiếng Việt</a> · <a href="README-DE.md">Deutsch</a> · <a href="README-IT.md">Italiano</a> · <a href="README-PL.md">Polski</a> · <a href="README-TH.md">ไทย</a> · <a href="README-NL.md">Nederlands</a> · <a href="README-UK.md">Українська</a> · <a href="README-HI.md">हिन्दी</a> · <strong>العربية</strong>
</p>

<br>

<p>
  ⭐ <em>مجاني ومرخّص بـ MIT ودون اشتراكات — يتم القصّ والتصيير بالكامل على جهازك. امنح المستودع نجمة إذا وجدته مفيدًا!</em>
</p>

<!-- top-sponsors:start -->
<table width="100%">
  <tr>
    <td align="center" width="50%">
      <a href="https://go.apimart.ai/tw-autoclip"><img src="../../docs/sponsors/apimart.png" alt="APIMart" width="64"></a><br>
      <a href="https://go.apimart.ai/tw-autoclip"><strong>APIMart</strong></a><br>
      <sub>Low-cost AI image &amp; video API · GPT-Image-2 from $0.006/img</sub>
    </td>
    <td align="center" width="50%">
      <a href="mailto:christine_zhouye@163.com?subject=AutoClip%20Sponsor%20%2F%20Provider%20Partnership"><strong>Sponsor / Partner with AutoClip</strong></a><br>
      <sub>Put your AI API or creator tool in front of AutoClip users worldwide (cloud dynamic provider listing supported, zero client release needed).<br><a href="mailto:christine_zhouye@163.com">christine_zhouye@163.com</a></sub>
    </td>
  </tr>
</table>
<!-- top-sponsors:end -->

</div>

---

## نظرة عامة

أضف رابطًا أو فيديو محليًا أو **إعادة بث مباشر** — يعثر AutoClip على أفضل اللحظات، ويتتبع المتحدث، ويدمج الترجمات، وينشئ الأغلفة، ويصدّر مقاطع جاهزة للنشر على TikTok وShorts وReels وYouTube وDouyin وXiaohongshu وBilibili.

**محلي أولًا بالتصميم:** يعمل القصّ والتصيير مباشرةً على حاسوبك دون طوابير رفع ودون رسوم شهرية. استخدم مفتاح API الخاص بك أو شغّله دون إنترنت بنسبة 100% عبر **Ollama / LM Studio + Whisper / SenseVoice**.

![AutoClip v1.6 Live Stream Replays Walkthrough](../images/v1.6/autoclip-v1.6-demo.gif)

<p align="center"><em>الرئيسية ← 6 مصادر لإعادات البث المباشر ← إعداد OBS WebSocket ← الاستيراد من Twitch ← مقطع جاهز بالترجمة والنشر بنقرة واحدة.</em></p>

---

## الجديد في v1.6

| الميزة | التفاصيل |
| :--- | :--- |
| **6 مصادر لإعادات البث** | تبويب مخصص **لإعادة البث المباشر** يدعم **OBS Studio وTwitch وYouTube وKick وDiscord والتسجيلات المحلية**. |
| **التقاط تلقائي عبر OBS** | اربط OBS WebSocket (`4455`)، واقصص دون فقدان جودة (`-c copy`)، وأدرج المقاطع تلقائيًا فور إنهاء البث. |
| **لقطات الألعاب المميزة** | كشف معمّم للّقطات المميزة يدعم مقاطع مستقلة بطول **8 ثوانٍ فأكثر** مع ميزانيات أدق للرؤية وOCR. |
| **إعادة التكييف بنقرة واحدة** | بطاقات مقاطع موحّدة قابلة للتشغيل — بدّل المنصات المستهدفة بنقرة واحدة دون فقدان التصديرات السابقة. |
| **13 لغة** | واجهة سطح مكتب كاملة، وقوائم شريط النظام، وتوثيق بـ 13 لغة (`+ zh-TW, de, id, tr, vi`) إضافةً إلى دعم ترجمات العربية من اليمين لليسار (RTL). |

<details>
<summary>📸 من داخل التطبيق (5 لقطات شاشة)</summary>

<table width="100%">
<tr>
<td align="center" valign="top" width="50%">
<img src="../images/v1.6/en-01-home.jpg" alt="الشاشة الرئيسية مع تبويبات الرابط والملف وإعادة البث المباشر"><br>
<em>الشاشة الرئيسية — الرابط والملف وإعادة البث المباشر</em>
</td>
<td align="center" valign="top" width="50%">
<img src="../images/v1.6/en-02-replays-obs.jpg" alt="منتقي مصادر إعادة البث المباشر الستة"><br>
<em>إعادة البث المباشر — 6 مصادر للإعادة</em>
</td>
</tr>
<tr>
<td align="center" valign="top" width="50%">
<img src="../images/v1.6/en-03-replays-obs-settings.jpg" alt="إعدادات اتصال OBS Studio WebSocket المضمنة"><br>
<em>إعدادات OBS Studio WebSocket المضمنة</em>
</td>
<td align="center" valign="top" width="50%">
<img src="../images/v1.6/en-04-replays-twitch.jpg" alt="استيراد إعادة Twitch"><br>
<em>الاستيراد من Twitch ومنتقي التسجيلات المحلية</em>
</td>
</tr>
<tr>
<td align="center" valign="top" colspan="2">
<img src="../images/v1.6/en-05-result-card.jpg" width="75%" alt="مقطع مكتمل مع نسبة المصدر إلى Twitch"><br>
<em>مقطع مكتمل — نسبة المصدر، قصّ 9:16، ترجمات، وتنزيل / نشر / إعادة صنع بنقرة واحدة</em>
</td>
</tr>
</table>

</details>

---

## أمثلة

انقر على أي صورة مصغّرة أو على **▶ تشغيل** لمشاهدة المقاطع الكاملة المصيّرة عبر AutoClip. تشير تسميات اللغة إلى لغة الترجمة المدمجة في الفيديو.

### رأسي · المقابلات والبودكاست

<table width="100%">
<tr>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/gates-ezra/01.mp4?v=2026-10-01g"><img src="../images/demos/gates-ezra-01.jpg" width="180" alt="Bill Gates"></a><br>
<strong>Bill Gates</strong><br>
مقابلة · Douyin · ZH<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/gates-ezra/01.mp4?v=2026-10-01g">▶ تشغيل 1:01</a> · <a href="https://www.youtube.com/watch?v=A_156w0aYtU">المصدر</a>
</td>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/ai-labs-debate/01.mp4?v=2026-10-01g"><img src="../images/demos/ai-labs-debate-01.jpg" width="180" alt="AI Experts Debate"></a><br>
<strong>AI Experts Debate</strong><br>
مقابلة · Shorts · EN<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/ai-labs-debate/01.mp4?v=2026-10-01g">▶ تشغيل 1:25</a> · <a href="https://www.youtube.com/watch?v=OhOmLqR5nN4">المصدر</a>
</td>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/robbins-36months/01.mp4?v=2026-10-01g"><img src="../images/demos/robbins-36months-01.jpg" width="180" alt="Tony Robbins"></a><br>
<strong>Tony Robbins</strong><br>
بودكاست · Douyin · ZH<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/robbins-36months/01.mp4?v=2026-10-01g">▶ تشغيل 1:45</a> · <a href="https://www.youtube.com/watch?v=DuRcrbP3kag">المصدر</a>
</td>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/garfield-poehler/01.mp4?v=2026-10-01g"><img src="../images/demos/garfield-poehler-01.jpg" width="180" alt="Andrew Garfield × Amy Poehler"></a><br>
<strong>Garfield × Poehler</strong><br>
بودكاست · Shorts · EN<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/garfield-poehler/01.mp4?v=2026-10-01g">▶ تشغيل 1:01</a> · <a href="https://www.youtube.com/watch?v=OJV8AaWCxQQ">المصدر</a>
</td>
</tr>
</table>

### أفقي · نسبة العرض الأصلية

<table width="100%">
<tr>
<td align="center" valign="top" width="50%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/luyu-tongliya/01.mp4?v=2026-10-01g"><img src="../images/demos/luyu-tongliya-01.jpg" width="360" alt="Tong Liya × Lu Yu"></a><br>
<strong>佟丽娅 × 鲁豫</strong> · 16:9 · Bilibili · ZH<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/luyu-tongliya/01.mp4?v=2026-10-01g">▶ تشغيل 1:41</a> · <a href="https://www.bilibili.com/video/BV1qheu6kEFV/">المصدر</a>
</td>
<td align="center" valign="top" width="50%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/altman-uses-ai/01.mp4?v=2026-10-01g"><img src="../images/demos/altman-uses-ai-01.jpg" width="360" alt="Sam Altman"></a><br>
<strong>Sam Altman</strong> · 16:9 · Bilibili · ZH<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/altman-uses-ai/01.mp4?v=2026-10-01g">▶ تشغيل 2:02</a> · <a href="https://www.youtube.com/watch?v=jZh55CQwSh8">المصدر</a>
</td>
</tr>
</table>

<details>
<summary>عرض 10 مقاطع إضافية</summary>

<table width="100%">
<tr>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/neumann-doac/01.mp4?v=2026-10-01g"><img src="../images/demos/neumann-doac-01.jpg" width="180" alt="Adam Neumann"></a><br>
<strong>Adam Neumann</strong><br>
بودكاست · TikTok · EN<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/neumann-doac/01.mp4?v=2026-10-01g">▶ تشغيل 0:59</a> · <a href="https://www.youtube.com/watch?v=IQ4JVWdj4Q0">المصدر</a>
</td>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/luyu-xiaoqi/02.mp4?v=2026-10-01g"><img src="../images/demos/luyu-xiaoqi-02.jpg" width="180" alt="Xiao Qi × Lu Yu"></a><br>
<strong>小奇 × 鲁豫</strong><br>
مقابلة · Douyin · ZH<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/luyu-xiaoqi/02.mp4?v=2026-10-01g">▶ تشغيل 0:50</a> · <a href="https://www.bilibili.com/video/BV1ighy6AEPz/">المصدر</a>
</td>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/luyu-guokeyu/01.mp4?v=2026-10-01g"><img src="../images/demos/luyu-guokeyu-01.jpg" width="180" alt="Guo Keyu × Lu Yu"></a><br>
<strong>郭柯宇 × 鲁豫</strong><br>
مقابلة · Douyin · ZH<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/luyu-guokeyu/01.mp4?v=2026-10-01g">▶ تشغيل 1:11</a> · <a href="https://www.bilibili.com/video/BV1LDYV6HEXR/">المصدر</a>
</td>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/dafoe-hot-ones/01.mp4?v=2026-10-01g"><img src="../images/demos/dafoe-hot-ones-01.jpg" width="180" alt="Willem Dafoe"></a><br>
<strong>Willem Dafoe</strong><br>
بودكاست · TikTok · EN<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/dafoe-hot-ones/01.mp4?v=2026-10-01g">▶ تشغيل 1:07</a> · <a href="https://www.youtube.com/watch?v=YqugY2zTIoI">المصدر</a>
</td>
</tr>
<tr>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/tim-luoyonghao/01.mp4?v=2026-10-01g"><img src="../images/demos/tim-luoyonghao-01.jpg" width="180" alt="TIM × Luo Yonghao"></a><br>
<strong>TIM × 罗永浩</strong><br>
مقابلة · Douyin · ZH<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/tim-luoyonghao/01.mp4?v=2026-10-01g">▶ تشغيل 1:05</a> · <a href="https://www.bilibili.com/video/BV1B5xkzPEhx/">المصدر</a>
</td>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/jensen-dwarkesh/01.mp4?v=2026-10-01g"><img src="../images/demos/jensen-dwarkesh-01.jpg" width="180" alt="Jensen Huang"></a><br>
<strong>Jensen Huang</strong><br>
مقابلة · Xiaohongshu · ZH<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/jensen-dwarkesh/01.mp4?v=2026-10-01g">▶ تشغيل 1:17</a> · <a href="https://www.youtube.com/watch?v=Hrbq66XqtCo">المصدر</a>
</td>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/karpathy-dwarkesh/01.mp4?v=2026-10-01g"><img src="../images/demos/karpathy-dwarkesh-01.jpg" width="180" alt="Andrej Karpathy"></a><br>
<strong>Andrej Karpathy</strong><br>
مقابلة · Douyin · ZH<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/karpathy-dwarkesh/01.mp4?v=2026-10-01g">▶ تشغيل 0:43</a> · <a href="https://www.youtube.com/watch?v=lXUZvyajciY">المصدر</a>
</td>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/apple-a20/01.mp4?v=2026-10-01g"><img src="../images/demos/apple-a20-01.jpg" width="180" alt="A20 Pro"></a><br>
<strong>A20 Pro</strong><br>
مقابلة · Xiaohongshu · ZH<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/apple-a20/01.mp4?v=2026-10-01g">▶ تشغيل 2:00</a> · <a href="https://www.bilibili.com/video/BV1e4Y96FEaJ/">المصدر</a>
</td>
</tr>
<tr>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/stallone-nyt/01.mp4?v=2026-10-01g"><img src="../images/demos/stallone-nyt-01.jpg" width="180" alt="Sylvester Stallone"></a><br>
<strong>Sylvester Stallone</strong><br>
مقابلة · Douyin · ZH<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/stallone-nyt/01.mp4?v=2026-10-01g">▶ تشغيل 1:39</a> · <a href="https://www.youtube.com/watch?v=ccs-B_nTfZs">المصدر</a>
</td>
<td align="center" valign="top" width="25%">
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/mrbeast-colin-samir/01.mp4?v=2026-10-01g"><img src="../images/demos/mrbeast-colin-samir-01.jpg" width="180" alt="MrBeast"></a><br>
<strong>MrBeast</strong><br>
بودكاست · TikTok · EN<br>
<a href="https://pub-3fb92949b9c2480b89feec5ec03f3540.r2.dev/cases/mrbeast-colin-samir/01.mp4?v=2026-10-01g">▶ تشغيل 1:42</a> · <a href="https://www.youtube.com/watch?v=9IQ_ldV9z_A">المصدر</a>
</td>
<td></td>
<td></td>
</tr>
</table>

</details>

تصفّح أكثر من 16 مقطعًا وغلافًا ونص نشر في **[معرض النماذج ←](https://zhouxiaoka.github.io/autoclip_intro/cases/?lang=en)**، أو [شارك مقاطعك الخاصة](https://github.com/zhouxiaoka/autoclip/discussions/new?category=show-and-tell). تبقى حقوق الفيديوهات المصدرية لمبدعيها الأصليين.

---

<a id="quick-start"></a>

## البدء السريع

| حالة الاستخدام | الإعداد الموصى به | المتطلبات |
| :--- | :--- | :--- |
| **تطبيق سطح المكتب (الأسهل)** | نزّل `.dmg` / `-setup.exe` من [Releases](https://github.com/zhouxiaoka/autoclip/releases/latest) | macOS على Apple Silicon أو Windows 10/11 x64 (Python وFFmpeg مدمجان) |
| **وكلاء الذكاء الاصطناعي / CLI / MCP** | `uvx autoclip-mcp` أو `npx skills add zhouxiaoka/autoclip` | Python 3.10+ (يُوصى بـ 3.11) وFFmpeg |
| **استضافة ذاتية / Linux / Intel Mac** | `docker compose up -d --build` | Docker وCompose v2 |

### 1. تطبيق سطح المكتب

1. نزّل أحدث مثبّت من **[GitHub Releases](https://github.com/zhouxiaoka/autoclip/releases/latest)** (`aarch64.dmg` لأجهزة macOS بـ Apple Silicon، و`x64-setup.exe` لنظام Windows). حزمتا Python وFFmpeg المحمولتان مدمجتان.
2. افتح **الإعدادات**، واختر مزوّدًا سحابيًا (أو شغّل Ollama / LM Studio)، واختبر الاتصال، واحفظ — أو انقر **جرّب المثال المدمج** دون مفتاح API.
3. الصق رابط فيديو، أو أسقط ملفًا، أو بدّل إلى **إعادة البث المباشر** لربط OBS أو استيراد تسجيل بث. اختر منصاتك وانقر **إنشاء**.

> تُبنى المثبّتات علنًا على GitHub Actions (`Desktop Build`) مع التحقق عبر `build-provenance.json` بصمة SHA-256. عند التشغيل الأول على بناء غير موقّع: على **macOS** نفّذ `xattr -dr com.apple.quarantine "/Applications/AutoClip Desktop.app"` (أو *إعدادات النظام ← الخصوصية والأمان ← الفتح على أي حال*)؛ وعلى **Windows** انقر **معلومات إضافية ← التشغيل على أي حال** في SmartScreen. راجع **[سياسة توقيع الشيفرة والتحقق](../../CODE_SIGNING.md)** (توثيق Apple متابَع في [#119](https://github.com/zhouxiaoka/autoclip/issues/119)).

### 2. CLI وMCP (Claude Code وCursor وCodex وOpenCode والسكربتات)

اسمح لوكلاء البرمجة بالذكاء الاصطناعي بقصّ الفيديوهات مباشرةً من الطرفية (`claude mcp add autoclip -- uvx autoclip-mcp`). أدلة إعداد MCP الكاملة: **[English](../MCP.en.md)** · [简体中文](../CLI_AND_MCP.md) · [日本語](../MCP.ja.md) · [한국어](../MCP.ko.md) · [Español](../MCP.es.md) · [Deutsch](../MCP.de.md).

```bash
uvx autoclip-mcp
npx skills add zhouxiaoka/autoclip

autoclip --version
autoclip produce talk.mp4 --srt talk.srt --platform tiktok --portrait-style podcast --json
autoclip outputs PROJECT_ID --export-kits
```

<details>
<summary>تثبيت Wheel دون اتصال، التثبيت من المصدر وحزم MCPB</summary>

```bash
# Install from a downloaded CLI/MCP release ZIP wheel
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install --force-reinstall --no-deps autoclip_mcp-*-py3-none-any.whl

# Or install from source
python -m pip install --no-deps .
```

لبناء حزمة MCPB محليًا دون نشرها، شغّل `python scripts/pack_mcpb.py` (لا تشغّل `smithery mcp publish` تلقائيًا أبدًا).

</details>


### 3. Docker / الويب

```bash
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip
cp env.example .env
mkdir -p data logs uploads
docker compose up -d --build
```

افتح واجهة الويب على `http://localhost:3000` (وتوثيق API على `http://localhost:8000/docs`). راجع [دليل Docker](../DOCKER.en.md) لأذونات الربط والنطاقات المخصصة.

---

## قياسات الأداء والتكلفة

قِيست على جهاز Apple Silicon Mac (تُقدَّر تكلفة النموذج اللغوي باستخدام `qwen-plus`؛ ولا تشمل التعرّف السحابي على الكلام أو توليد الصور بالذكاء الاصطناعي؛ راجع فاتورة مزوّدك للاستخدام الدقيق):

| الإدخال | المصدر | الوقت والمخرج | التكلفة التقديرية للنموذج اللغوي |
| :--- | :--- | ---: | ---: |
| **مع ترجمة موجودة** | Jensen Huang · 1س 43د (EN ← Xiaohongshu) | **7.5 دقيقة / 10 مقاطع** | **¥0.09** |
| **بدون ترجمة (Whisper محلي)** | TIM × Luo Yonghao · 2س 52د (ZH ← Douyin) | 29.5 دقيقة / 10 مقاطع | ¥0.20 |

---

## الراعي ❤️

<table>
  <tr>
    <td align="center" width="140">
      <a href="https://go.apimart.ai/tw-autoclip"><img src="../sponsors/apimart.png" alt="APIMart" width="88"></a><br>
      <a href="https://go.apimart.ai/tw-autoclip"><strong>APIMart</strong></a>
    </td>
    <td>
      شكرًا لـ <strong>APIMart</strong> على رعاية AutoClip! تُعد <strong>APIMart</strong> منصة API منخفضة التكلفة لتوليد الصور والفيديو بالذكاء الاصطناعي — GPT-Image-2 بدءًا من <strong>$0.006/صورة</strong> (<strong>160+</strong> صورة لكل دولار). واجهة API غير متزامنة واحدة تغطي الصور والفيديو معًا: أرسل مهمة، واحصل على معرّف، واسحب النتائج عبر الاستطلاع أو callback. نفّذ دفعات من عشرات الآلاف من الصور دون انقطاع المهلة وبدّل النماذج دون تغيير الشيفرة. الدفع حسب الاستخدام دون رسوم شهرية — <a href="https://go.apimart.ai/tw-autoclip">سجّل من هنا</a>.
    </td>
  </tr>
</table>

## التفريغ السحابي (Alibaba Cloud)

*رابط تسويق بالعمولة (منفصل عن الراعي أعلاه):* سجّل في Alibaba Cloud، وأنشئ API Key في لوحة تحكم Bailian، وفعّل التعرّف السحابي على الكلام من Bailian ضمن **الإعدادات ← النماذج الافتراضية ← تحويل الكلام إلى ترجمة**.

1. [التسجيل في Alibaba Cloud](https://www.aliyun.com/benefit?userCode=qmyj6jch) (رابط عمولة)
2. [لوحة تحكم Bailian](https://bailian.console.aliyun.com/) — أنشئ API Key الخاص بك

---

## الأسئلة الشائعة

<details>
<summary>هل AutoClip مجاني؟ وهل أحتاج إلى API Key؟</summary>

نعم — AutoClip مجاني ومرخّص بـ MIT. يستخدم التحليل السحابي والتفريغ السحابي والأغلفة بالذكاء الاصطناعي مفاتيح API الخاصة بك وفق أسعار المزوّد (تخطيط الغلاف المحلي مجاني افتراضيًا). ولا يتطلب Ollama وLM Studio أي مفتاح سحابي. ويستخدم النشر المباشر حسابك الخاص في Bilibili أو [Upload-Post](https://www.upload-post.com).

</details>

<details>
<summary>هل يُرفع الفيديو الخاص بي إلى السحابة؟</summary>

يعمل القصّ والتصيير محليًا. يرسل التحليل السحابي نص الترجمة فقط؛ وتستقبل نماذج الرؤية إطارات مأخوذة كعينات فقط؛ ويرفع التفريغ السحابي الصوت. ويُبقي تشغيل النماذج اللغوية المحلية + Whisper / SenseVoice كل شيء دون اتصال بالإنترنت. ويمكن إيقاف التحليلات وتقارير الأعطال من الإعدادات. راجع [الخصوصية](../PRIVACY.en.md).

</details>

<details>
<summary>ما أنواع الفيديوهات التي تعطي أفضل النتائج؟</summary>

البودكاست والمقابلات والمحاضرات والدورات وإعادات بثوث الألعاب المباشرة (OBS / Twitch / YouTube / Kick / Discord). وتكون المصادر المزوّدة بترجمة جاهزة هي الأسرع؛ وإلا استخدم Whisper / SenseVoice المحلي أو التفريغ السحابي. وبالنسبة للّعب أو البثوث قليلة الحوار، فعّل نموذجًا يدعم الرؤية.

</details>

<details>
<summary>لماذا لم يتم إنشاء أي مقاطع؟</summary>

تحقّق من المرحلة التي فشلت: الترجمة/التفريغ، أو اتصال النموذج، أو FFmpeg، أو مساحة القرص، أو حدود الطول الخاصة بالمنصة (يتطلب YouTube الطويل ≥180 ثانية؛ استخدم Shorts أو TikTok أو Bilibili للمقاطع الأقصر). وإذا استمر الفشل، افتح Issue مرفقًا بـ `autoclip --version` ونظام التشغيل والنموذج والسجلات المنقّحة، أو راجع [المشكلات المعروفة (#96)](https://github.com/zhouxiaoka/autoclip/issues/96).

</details>

[استكشاف الأخطاء وإصلاحها](../FAQ.en.md) · [المشكلات المعروفة](https://github.com/zhouxiaoka/autoclip/issues/96)

---

<a id="documentation"></a>

## التوثيق

| الموضوع | الدليل |
| :--- | :--- |
| التثبيت وأول المقاطع | [دليل التثبيت](../USER_INSTALLATION_GUIDE.en.md) |
| الاستضافة الذاتية والوكلاء | [Docker](../DOCKER.en.md) · [MCP ووكلاء الذكاء الاصطناعي](../MCP.en.md) ([ZH](../CLI_AND_MCP.md) · [JA](../MCP.ja.md) · [KO](../MCP.ko.md) · [ES](../MCP.es.md) · [DE](../MCP.de.md)) · [مهارة الوكيل](../../skills/autoclip/SKILL.md) (ZH) · [OpenCode](../OPENCODE.en.md) |
| النماذج واستكشاف الأخطاء | [إعداد النماذج المتعددة](../MULTI_LLM_PROVIDER_GUIDE.md) (ZH) · [الأسئلة الشائعة](../FAQ.en.md) |
| الإصدارات والخصوصية | [سجل التغييرات](../../CHANGELOG.md) · [توقيع الشيفرة](../../CODE_SIGNING.md) · [خارطة الطريق](../ROADMAP.md) (ZH) · [لوحة المجتمع](../COMMUNITY_BOARD.md) (ZH) · [الخصوصية](../PRIVACY.en.md) |
| الأبحاث | [اختر اللحظة لا المؤثر](../research/2026-10-what-drives-views/article-en.md) · [中文](../research/2026-10-what-drives-views/article-zh.md) |
| المساهمة والتدويل | [المساهمة](../../CONTRIBUTING.md) (ZH) · [ترجمة AutoClip](../../TRANSLATING.md) · [دليل الترجمة](../i18n.md) (ZH) |

## المساهمة

نرحّب بطلبات السحب (PRs) وتقارير الأخطاء ونماذج المقاطع والترجمات. إذا وفّر لك AutoClip الوقت، فإن نجمة ⭐ تساعد كثيرًا!

- **المجتمع:** [GitHub Discussions](https://github.com/zhouxiaoka/autoclip/discussions) · [أسئلة المقطع الأول](https://github.com/zhouxiaoka/autoclip/discussions/128) · [أفكار الميزات](https://github.com/zhouxiaoka/autoclip/discussions/129)
- **تقارير الأخطاء:** استخدم [قالب الـ Issue](https://github.com/zhouxiaoka/autoclip/issues/new/choose) مع نظام التشغيل والإصدار والنموذج وخطوات إعادة الإنتاج والسجلات المنقّحة
- **الشراكات:** [christine_zhouye@163.com](mailto:christine_zhouye@163.com)

تُصان أداة AutoClip بشكل فردي — يُرجى توقّع ردود غير متزامنة (لا يتوفر دعم فوري أو إعداد فردي مباشر).

![Star History](https://api.star-history.com/svg?repos=zhouxiaoka/autoclip&type=Date)

مبني باستخدام FastAPI وReact وTauri وFFmpeg وyt-dlp وWhisper وFunASR. [رخصة MIT](../../LICENSE).
