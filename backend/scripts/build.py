#!/usr/bin/env python3
"""
Build HTML tĩnh từ backend/data/ (chạy bởi GitHub Actions, chỉ dùng stdlib).

Input:
  backend/data/posts.json               # index bài viết do CMS quản lý (GAS ghi — commit chốt)
  backend/data/news/<slug>/post.json    # metadata + content HTML từng bài
  backend/data/legacy-posts.json        # metadata bài placeholder/tĩnh (không build trang chi tiết)
  backend/templates/post.html           # template trang bài viết (design sống, sửa tay ở đây)
  backend/templates/news-index.html     # template trang danh sách お知らせ
  html/news/<slug>/images/*             # ảnh đã được CMS đẩy thẳng vào đây

Output:
  html/news/<slug>/index.html           # trang bài viết (chỉ bài CMS)
  html/news/index.html                  # danh sách tất cả bài (CMS + legacy)
  html/index.html                       # trang chủ: chỉ vá khối <ul class="news__list"> (3 bài mới nhất)
  html/sitemap.xml                      # giữ URL tĩnh, thay toàn bộ URL bài viết

Chạy local để thử: python3 backend/scripts/build.py
"""
import html as htmllib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent   # repo root (koseinexus/)
HTML = ROOT / "html"
DATA = ROOT / "backend" / "data"
TEMPLATES = ROOT / "backend" / "templates"
SITE = "https://koseinexus.com"
ORG_ID = SITE + "/#org"

DATE_ICON = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.2 2"/></svg>'
)


def esc(s):
    return htmllib.escape(s or "", quote=True)


def load_json(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def parse_iso(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return datetime(2026, 1, 1, tzinfo=timezone.utc)


def date_display(iso):
    """Định dạng ngày kiểu Nhật đang dùng trên site: 2026.05.28"""
    return parse_iso(iso).strftime("%Y.%m.%d")


def cover_of(p):
    return ("/" + p["cover"]) if p.get("cover") else "/images/banner.jpeg"


def truncate(s, n=90):
    s = (s or "").strip()
    return s if len(s) <= n else s[:n] + "…"


# ---------- card renderers (markup khớp css .news-card của site) ----------

def news_card(p):
    """Card trong html/news/index.html và khối 関連記事 của trang bài viết.
    Bài legacy (không có slug) chỉ là placeholder -> href="#"."""
    href = ("/news/%s/" % p["slug"]) if p.get("slug") else "#"
    desc = ""
    if p.get("description"):
        desc = "\n        <p>%s</p>" % esc(truncate(p["description"]))
    return (
        '      <a class="news-card" href="%s">\n'
        '        <figure><img src="%s" alt="%s" loading="lazy"></figure>\n'
        '        <p class="news-card__date">%s%s</p>\n'
        "        <h3>%s</h3>%s\n"
        "      </a>"
    ) % (href, cover_of(p), esc(p["title"]), DATE_ICON, date_display(p["created_at"]), esc(p["title"]), desc)


def home_news_item(p):
    """1 dòng trong <ul class="news__list"> của trang chủ."""
    href = ("news/%s/" % p["slug"]) if p.get("slug") else "news/"
    return (
        "      <li>\n"
        '        <a href="%s">\n'
        '          <span class="news__date">%s</span>\n'
        '          <span class="news__title">%s</span>\n'
        "        </a>\n"
        "      </li>"
    ) % (href, date_display(p["created_at"]), esc(p["title"]))


# ---------- content transform ----------

def transform_content(content):
    # src tương đối news/<slug>/images/.. -> tuyệt đối /news/<slug>/images/..
    content = re.sub(r'src="news/', 'src="/news/', content)
    content = re.sub(r"src='news/", "src='/news/", content)
    # lazy-load ảnh trong thân bài
    content = re.sub(r"<img (?!loading)", '<img loading="lazy" ', content)
    return "\n".join("        " + line if line.strip() else line for line in content.splitlines())


def jsonld_for(post, url, cover_abs):
    data = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "NewsArticle",
                "headline": post["title"],
                "datePublished": parse_iso(post["created_at"]).strftime("%Y-%m-%d"),
                "dateModified": parse_iso(post.get("updated_at") or post["created_at"]).strftime("%Y-%m-%d"),
                "image": [cover_abs],
                "author": {"@id": ORG_ID},
                "publisher": {"@id": ORG_ID},
                "mainEntityOfPage": url,
                "inLanguage": "ja",
            },
            {
                "@type": "Organization",
                "@id": ORG_ID,
                "name": "興盛ネクサス株式会社",
                "url": SITE + "/",
                "logo": SITE + "/images/favicon.png",
                "telephone": "+81-594-42-5661",
                "address": {
                    "@type": "PostalAddress",
                    "postalCode": "511-0838",
                    "addressRegion": "三重県",
                    "addressLocality": "桑名市",
                    "streetAddress": "大字和泉283-2",
                    "addressCountry": "JP",
                },
            },
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "ホーム", "item": SITE + "/"},
                    {"@type": "ListItem", "position": 2, "name": "お知らせ", "item": SITE + "/news/"},
                    {"@type": "ListItem", "position": 3, "name": post["title"], "item": url},
                ],
            },
        ],
    }
    return '<script type="application/ld+json">%s</script>' % json.dumps(data, ensure_ascii=False, separators=(",", ":"))


# ---------- builders ----------

def build_post_page(post, merged, tpl):
    slug = post["slug"]
    url = "%s/news/%s/" % (SITE, slug)
    cover_abs = SITE + cover_of(post)
    related = [p for p in merged if p.get("slug") != slug][:3]

    page = (
        tpl.replace("{{TITLE}}", esc(post["title"]))
        .replace("{{DESCRIPTION}}", esc(post.get("description", "")))
        .replace("{{URL}}", url)
        .replace("{{COVER_ABS}}", cover_abs)
        .replace("{{COVER_SRC}}", cover_of(post))
        .replace("{{DATE_DISPLAY}}", date_display(post["created_at"]))
        .replace("{{JSONLD}}", jsonld_for(post, url, cover_abs))
        .replace("{{CONTENT}}", transform_content(post.get("content", "")))
        .replace("{{RELATED_CARDS}}", "\n\n".join(news_card(p) for p in related))
    )
    out = HTML / "news" / slug / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print("built", out.relative_to(ROOT))


def build_news_index(merged, tpl):
    page = tpl.replace("{{NEWS_CARDS}}", "\n\n".join(news_card(p) for p in merged))
    (HTML / "news" / "index.html").write_text(page, encoding="utf-8")
    print("built html/news/index.html (%d bài)" % len(merged))


def update_homepage(merged):
    """Chỉ vá khối <ul class="news__list"> (3 bài mới nhất); phần còn lại của trang chủ giữ nguyên."""
    path = HTML / "index.html"
    if not path.exists():
        return
    s = path.read_text(encoding="utf-8")
    items = "\n".join(home_news_item(p) for p in merged[:3])
    s, n = re.subn(
        r'<ul class="news__list">.*?</ul>',
        '<ul class="news__list">\n' + items + "\n    </ul>",
        s, count=1, flags=re.S,
    )
    if not n:
        print('WARN: không tìm thấy <ul class="news__list"> trong html/index.html — trang chủ KHÔNG được cập nhật')
        return
    path.write_text(s, encoding="utf-8")
    print("built html/index.html (vá 3 tin mới nhất)")


def build_sitemap(merged):
    """Giữ nguyên các URL tĩnh trong sitemap, thay toàn bộ URL bài viết /news/<slug>/.
    Gồm cả bài legacy có slug (trang chi tiết tĩnh vẫn tồn tại trên site)."""
    path = HTML / "sitemap.xml"
    s = path.read_text(encoding="utf-8")
    blocks = re.findall(r"[ \t]*<url>.*?</url>\n?", s, flags=re.S)
    kept = [b for b in blocks if not re.search(r"<loc>%s/news/.+</loc>" % re.escape(SITE), b)]
    post_blocks = [
        "  <url>\n    <loc>%s/news/%s/</loc>\n    <lastmod>%s</lastmod>\n    <changefreq>yearly</changefreq>\n    <priority>0.6</priority>\n  </url>\n"
        % (SITE, p["slug"], parse_iso(p.get("updated_at") or p["created_at"]).strftime("%Y-%m-%d"))
        for p in merged if p.get("slug")
    ]
    out = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    out += "".join(kept) + "".join(post_blocks) + "</urlset>\n"
    path.write_text(out, encoding="utf-8")
    print("built html/sitemap.xml (%d bài viết)" % len(post_blocks))


def merge_by_slug(legacy, cms):
    by_key = {}
    for i, p in enumerate(legacy + cms):  # CMS ghi đè legacy nếu trùng slug
        by_key[p.get("slug") or ("__legacy_%d" % i)] = p
    return sorted(by_key.values(), key=lambda p: str(p["created_at"]), reverse=True)


def main():
    cms = load_json(DATA / "posts.json", [])
    legacy = load_json(DATA / "legacy-posts.json", [])
    merged = merge_by_slug(legacy, cms)

    post_tpl = (TEMPLATES / "post.html").read_text(encoding="utf-8")
    index_tpl = (TEMPLATES / "news-index.html").read_text(encoding="utf-8")

    built = 0
    for p in cms:
        pj = DATA / "news" / p["slug"] / "post.json"
        if not pj.exists():
            print("WARN: thiếu", pj.relative_to(ROOT), "- bỏ qua")
            continue
        build_post_page(load_json(pj, {}), merged, post_tpl)
        built += 1

    build_news_index(merged, index_tpl)
    update_homepage(merged)
    build_sitemap(merged)
    print("Done: %d bài CMS | tổng %d bài (CMS + legacy)" % (built, len(merged)))


if __name__ == "__main__":
    main()
