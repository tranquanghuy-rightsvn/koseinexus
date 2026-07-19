# Backend — data + build pipeline (koseinexus.com)

```
CMS (Google Apps Script, thư mục gas/ — KHÔNG có trên GitHub)
   │  commit qua GitHub Contents API
   ▼
backend/data/           ← nguồn dữ liệu bài viết (GAS ghi, KHÔNG sửa tay)
   │  push vào backend/data/posts.json (commit chốt) → trigger CI
   ▼
GitHub Actions (.github/workflows/build.yml) → python3 backend/scripts/build.py
   ▼
html/                   ← site tĩnh (trang news do CI ghi đè, KHÔNG sửa tay)
```

## Phân vai thư mục

| Đường dẫn | Ai ghi | Sửa tay được không |
|---|---|---|
| `backend/data/posts.json`, `backend/data/news/<slug>/post.json` | GAS (khi Lưu/Xoá bài) | **Không** |
| `backend/data/legacy-posts.json` | Người (danh sách bài placeholder, không có trang chi tiết) | Có |
| `backend/templates/*.html` | Người — **đây là design sống của trang news**, đổi design sửa ở đây | Có |
| `html/news/<slug>/index.html`, `html/news/index.html` | `build.py` (CI ghi đè mỗi lần build) | **Không** |
| `html/index.html` | Người; CI chỉ vá đúng khối `<ul class="news__list">` (3 tin mới nhất) | Có, ngoài khối đó |
| `html/news/<slug>/images/*`, `cover.*` | GAS đẩy ảnh thẳng vào đây | Không cần |
| Các trang còn lại trong `html/` (about-us, products...) | Người | Có |

**Mốc neo CI vá trang chủ**: `<ul class="news__list">...</ul>` — khi redesign trang chủ
PHẢI giữ nguyên class này, nếu không CI sẽ log WARN và bỏ qua (không vá được).

## Chạy build local

```
python3 backend/scripts/build.py
```

Không cần cài gì (chỉ dùng Python stdlib). Chạy 2 lần liên tiếp phải không sinh diff mới (idempotent).

## Cấu hình phía GitHub

- Workflow trigger **chỉ** ở `backend/data/posts.json` — file này luôn là commit cuối
  của mỗi thao tác Lưu/Xoá trên CMS, nên không bao giờ build trạng thái dở dang.
- Nhánh: `master`. Commit của CI chỉ đụng `html/` nên không tự trigger lại.

## Hosting

Deploy thư mục `html/` lên Vercel/Cloudflare Pages (root directory = `html`).
Domain: koseinexus.com. Form liên hệ trên site gọi thẳng URL `/exec` của GAS
(xem `gas/README.md` — thư mục gas/ chỉ có trên máy local, đã gitignore).
