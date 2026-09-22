#!/usr/bin/env python3
"""把发布教程页装进 autoclip_intro，并在首页 FAQ / 页脚 / sitemap 留入口。可重复执行。"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GUIDE_SRC = HERE / "guides" / "publish" / "index.html"
SITEMAP_URL = "https://zhouxiaoka.github.io/autoclip_intro/guides/publish/"

FAQ_HTML = """        <details>
          <summary data-i18n="faq.7.q">怎么发布到 B 站和海外平台？</summary>
          <p data-i18n-html="faq.7.a">在设置里配 Upload-Post 密钥和 B 站 Cookie，切片页勾选平台，默认先发到「仅自己」。逐步说明见 <a class="link" href="guides/publish/">发布教程</a>。</p>
        </details>
"""

FOOTER_HTML = '      <a href="guides/publish/" data-i18n="footer.publish">发布教程</a>\n'

# 插在各语 faq.6.q 之前；顺序不影响运行，只要八语键齐全。
COMPACT_FAQ = {
    "zh": "'faq.7.q':'怎么发布到 B 站和海外平台？','faq.7.a':'在设置里配 Upload-Post 密钥和 B 站 Cookie，切片页勾选平台，默认先发到「仅自己」。逐步说明见 <a class=\"link\" href=\"guides/publish/\">发布教程</a>。',",
    "en": "'faq.7.q':'How do I publish to Bilibili and overseas platforms?','faq.7.a':'Add an Upload-Post key and a Bilibili cookie in Settings, pick platforms on a clip, and keep Only me for a first try. Step-by-step: <a class=\"link\" href=\"guides/publish/\">publish guide</a>.',",
    "ja": "'faq.7.q':'Bilibili と海外へはどう公開する？','faq.7.a':'設定で Upload-Post のキーと Bilibili の Cookie を入れ、切片ページで配信先を選び、最初は「自分のみ」のまま。手順は <a class=\"link\" href=\"guides/publish/\">公開ガイド</a>。',",
    "ko": "'faq.7.q':'빌리빌리와 해외에는 어떻게 올리나요?','faq.7.a':'설정에 Upload-Post 키와 빌리빌리 Cookie를 넣고, 클립에서 플랫폼을 고른 뒤 처음에는 「나만」으로 두세요. 단계는 <a class=\"link\" href=\"guides/publish/\">게시 가이드</a>에 있습니다.',",
}
COMPACT_FOOTER = {
    "zh": "'footer.publish':'发布教程',",
    "en": "'footer.publish':'Publish guide',",
    "ja": "'footer.publish':'公開ガイド',",
    "ko": "'footer.publish':'게시 가이드',",
}
COMPACT_FAQ_ANCHOR = {
    "zh": "'faq.6.q':'第一次怎么试？'",
    "en": "'faq.6.q':'How should I try it the first time?'",
    "ja": "'faq.6.q':'最初はどう試せばいい？'",
    "ko": "'faq.6.q':'처음에는 어떻게 시험해 보나요?'",
}
COMPACT_FOOTER_ANCHOR = {
    "zh": "'footer.podcast':'播客切片'",
    "en": "'footer.podcast':'Podcast clips'",
    "ja": "'footer.podcast':'ポッドキャスト'",
    "ko": "'footer.podcast':'팟캐스트'",
}

JSON_FAQ = {
    "es": '      "faq.7.q": "¿Cómo publico en Bilibili y en el extranjero?",\n      "faq.7.a": "Añade una clave de Upload-Post y una cookie de Bilibili en Ajustes, elige plataformas en un clip y deja Solo yo para la primera prueba. Pasos: <a class=\\"link\\" href=\\"guides/publish/\\">guía de publicación</a>.",\n',
    "pt": '      "faq.7.q": "Como publicar no Bilibili e no exterior?",\n      "faq.7.a": "Coloque a chave do Upload-Post e o cookie do Bilibili em Ajustes, escolha as plataformas no clipe e deixe Só eu na primeira tentativa. Passos: <a class=\\"link\\" href=\\"guides/publish/\\">guia de publicação</a>.",\n',
    "ru": '      "faq.7.q": "Как публиковать на Bilibili и за рубежом?",\n      "faq.7.a": "В настройках укажите ключ Upload-Post и cookie Bilibili, на клипе выберите площадки и оставьте «Только я» для первой пробы. Шаги: <a class=\\"link\\" href=\\"guides/publish/\\">как публиковать</a>.",\n',
    "fr": '      "faq.7.q": "Comment publier sur Bilibili et à l’étranger ?",\n      "faq.7.a": "Ajoutez une clé Upload-Post et un cookie Bilibili dans Réglages, choisissez les plateformes sur un extrait et laissez Moi seul pour le premier essai. Étapes : <a class=\\"link\\" href=\\"guides/publish/\\">guide de publication</a>.",\n',
}
JSON_FOOTER = {
    "es": '      "footer.publish": "Guía de publicación",\n',
    "pt": '      "footer.publish": "Guia de publicação",\n',
    "ru": '      "footer.publish": "Как публиковать",\n',
    "fr": '      "footer.publish": "Guide de publication",\n',
}
JSON_FAQ_ANCHOR = {
    "es": '      "faq.6.q": "¿Cómo probarlo la primera vez?"',
    "pt": '      "faq.6.q": "Como experimentar na primeira vez?"',
    "ru": '      "faq.6.q": "С чего начать в первый раз?"',
    "fr": '      "faq.6.q": "Comment essayer pour la première fois ?"',
}
JSON_FOOTER_ANCHOR = {
    "es": '      "footer.podcast": "Pódcast"',
    "pt": '      "footer.podcast": "Podcast",\n      "footer.course": "Curso"',
    "ru": '      "footer.podcast": "Подкаст"',
    "fr": '      "footer.podcast": "Podcast",\n      "footer.course": "Cours"',
}


def fail(msg: str) -> None:
    raise SystemExit(msg)


def insert_before(text: str, needle: str, insertion: str) -> str:
    idx = text.find(needle)
    if idx < 0:
        fail(f"找不到插入点：{needle[:80]}")
    return text[:idx] + insertion + text[idx:]


def patch_index(html: str) -> str:
    if 'data-i18n="faq.7.q"' not in html:
        html = insert_before(
            html,
            '        </details>\n      </div>\n    </div>\n  </div>\n</section>\n\n</main>',
            FAQ_HTML,
        )
    if 'data-i18n="footer.publish"' not in html:
        html = insert_before(
            html,
            '      <a href="https://github.com/zhouxiaoka/autoclip" target="_blank" rel="noopener">GitHub</a>',
            FOOTER_HTML,
        )

    for lang, blob in COMPACT_FAQ.items():
        if blob not in html:
            html = insert_before(html, COMPACT_FAQ_ANCHOR[lang], blob)
    for lang, blob in COMPACT_FOOTER.items():
        if blob not in html:
            html = insert_before(html, COMPACT_FOOTER_ANCHOR[lang], blob)
    for lang, blob in JSON_FAQ.items():
        if blob not in html:
            html = insert_before(html, JSON_FAQ_ANCHOR[lang], blob)
    for lang, blob in JSON_FOOTER.items():
        if blob not in html:
            html = insert_before(html, JSON_FOOTER_ANCHOR[lang], blob)

    # 双引号计数含 data-i18n="faq.7.q" / footer.publish 各一处。
    if html.count("'faq.7.q'") != 4:
        fail(f"zh/en/ja/ko 的 faq.7.q 数量异常：{html.count(chr(39) + 'faq.7.q' + chr(39))}")
    if html.count('"faq.7.q"') != 5:
        fail(f"es/pt/ru/fr 的 faq.7.q 数量异常：{html.count(chr(34) + 'faq.7.q' + chr(34))}")
    if html.count("'footer.publish'") != 4 or html.count('"footer.publish"') != 5:
        fail("footer.publish 八语键数量异常")
    return html


def patch_sitemap(xml: str) -> str:
    if SITEMAP_URL in xml:
        return xml
    if "</urlset>" not in xml:
        fail("sitemap.xml 缺少 </urlset>")
    entry = (
        f"  <url>\n    <loc>{SITEMAP_URL}</loc>\n    <lastmod>2026-09-22</lastmod>\n  </url>\n"
    )
    return xml.replace("</urlset>", entry + "</urlset>")


def patch_i18n_test(src: str) -> str:
    old = "['dl.alt','fb.alt','fb.stuck','faq.5.a','faq.6.a']"
    new = "['dl.alt','fb.alt','fb.stuck','faq.5.a','faq.6.a','faq.7.a']"
    if new in src:
        return src
    if old not in src:
        fail("scripts/i18n.test.cjs 里找不到 FAQ 链接检查列表")
    return src.replace(old, new)


def install(target: Path) -> None:
    index = target / "index.html"
    if not index.is_file():
        fail(f"{target} 下没有 index.html")
    if not GUIDE_SRC.is_file():
        fail(f"缺少 {GUIDE_SRC}")

    dest = target / "guides" / "publish" / "index.html"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(GUIDE_SRC.read_text(encoding="utf-8"), encoding="utf-8")
    index.write_text(patch_index(index.read_text(encoding="utf-8")), encoding="utf-8")

    sitemap = target / "sitemap.xml"
    if sitemap.is_file():
        sitemap.write_text(patch_sitemap(sitemap.read_text(encoding="utf-8")), encoding="utf-8")

    i18n_test = target / "scripts" / "i18n.test.cjs"
    if i18n_test.is_file():
        i18n_test.write_text(patch_i18n_test(i18n_test.read_text(encoding="utf-8")), encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 2:
        fail(f"用法: {sys.argv[0]} <autoclip_intro 仓库路径>")
    target = Path(sys.argv[1]).resolve()
    install(target)
    print(f"已写入 {target / 'guides' / 'publish' / 'index.html'}")
    print("已更新 index.html、sitemap.xml（若存在）和 scripts/i18n.test.cjs（若存在）")


if __name__ == "__main__":
    main()
