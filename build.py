#!/usr/bin/env python3
"""
Static site generator for audiodestrukt.com blog.
Reads posts/*.md, generates blog/index.html, blog/page-N.html, blog/posts/*.html
"""

import os
import re
import shutil
from datetime import datetime

POSTS_DIR = "posts"
OUT_DIR = "blog"
POSTS_OUT_DIR = os.path.join(OUT_DIR, "posts")
PER_PAGE = 10
SITE_URL = "https://audiodestrukt.com"

# ---------------------------------------------------------------------------
# Minimal markdown -> HTML converter (handles what these posts use)
# ---------------------------------------------------------------------------

def md_to_html(text):
    # Escape HTML special chars in text nodes only — do links first
    # Process block by block
    lines = text.split('\n')
    html_blocks = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # Headings
        m = re.match(r'^(#{1,6})\s+(.*)', line)
        if m:
            level = len(m.group(1))
            content = inline_md(m.group(2))
            html_blocks.append(f'<h{level}>{content}</h{level}>')
            i += 1
            continue

        # Fenced code block
        if line.startswith('```'):
            i += 1
            code_lines = []
            while i < len(lines) and not lines[i].startswith('```'):
                code_lines.append(lines[i])
                i += 1
            if i < len(lines):
                i += 1  # consume closing ```
            code = '\n'.join(code_lines).strip('\n')
            # Escape HTML entities inside code
            code = code.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            html_blocks.append(f'<pre><code>{code}</code></pre>')
            continue

        # Blank line
        if line.strip() == '':
            i += 1
            continue

        # Lists: consecutive "- item" / "* item" or "1. item" lines; a line that
        # continues the previous item is indented
        lm = re.match(r'^(\s*)([-*]|\d+\.)\s+(.*)', line)
        if lm:
            ordered = lm.group(2)[0].isdigit()
            items = []
            while i < len(lines):
                m2 = re.match(r'^(\s*)([-*]|\d+\.)\s+(.*)', lines[i])
                if m2 and m2.group(2)[0].isdigit() == ordered:
                    items.append(m2.group(3))
                    i += 1
                elif items and lines[i].startswith((' ', '\t')) and lines[i].strip():
                    items[-1] += ' ' + lines[i].strip()
                    i += 1
                else:
                    break
            tag = 'ol' if ordered else 'ul'
            html_blocks.append(f'<{tag}>' + ''.join(f'<li>{inline_md(it)}</li>' for it in items) + f'</{tag}>')
            continue

        # Collect paragraph lines
        para_lines = []
        while i < len(lines) and lines[i].strip() != '' and not re.match(r'^#{1,6}\s', lines[i]) and not lines[i].startswith('```') \
                and not re.match(r'^\s*([-*]|\d+\.)\s+', lines[i]):
            para_lines.append(lines[i])
            i += 1
        if para_lines:
            content = inline_md(' '.join(para_lines))
            html_blocks.append(f'<p>{content}</p>')

    return '\n'.join(html_blocks)


def inline_md(text):
    # Extract images and inline code into placeholders to protect from italic/bold
    placeholders = {}
    def extract_img(m):
        alt, src = m.group(1), m.group(2)
        if src.startswith('images/'):
            src = '/images/' + src[len('images/'):]   # absolute: /blog is served without a trailing slash
        tag = f'<img src="{src}" alt="{alt}" loading="lazy">'
        key = f'\x00IMG{len(placeholders)}\x00'
        placeholders[key] = tag
        return key
    def extract_code(m):
        content = m.group(1).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        tag = f'<code>{content}</code>'
        key = f'\x00CODE{len(placeholders)}\x00'
        placeholders[key] = tag
        return key
    text = re.sub(r'`([^`]+)`', extract_code, text)
    text = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', extract_img, text)
    # Bold
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'__(.+?)__', r'<strong>\1</strong>', text)
    # Italic
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    text = re.sub(r'_(.+?)_', r'<em>\1</em>', text)
    # Links
    text = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', text)
    # Auto-link bare URLs
    text = re.sub(
        r'(?<!["\'])(https?://[^\s<>"\']+)',
        r'<a href="\1">\1</a>',
        text
    )
    # Restore image placeholders
    for key, tag in placeholders.items():
        text = text.replace(key, tag)
    return text


def excerpt(html, words=60):
    # Strip tags, take first N words
    plain = re.sub(r'<[^>]+>', '', html)
    parts = plain.split()
    if len(parts) <= words:
        return plain
    return ' '.join(parts[:words]) + '…'


# ---------------------------------------------------------------------------
# Frontmatter parser
# ---------------------------------------------------------------------------

def parse_post(path):
    with open(path, encoding='utf-8') as f:
        raw = f.read()

    # Split frontmatter
    m = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', raw, re.DOTALL)
    if not m:
        return None

    fm_raw, body = m.group(1), m.group(2)

    meta = {}
    for line in fm_raw.splitlines():
        kv = re.match(r'^(\w+):\s*(.*)', line)
        if kv:
            meta[kv.group(1)] = kv.group(2).strip().strip('"')

    # Parse date
    date_str = meta.get('date', '')
    try:
        date = datetime.fromisoformat(date_str)
    except Exception:
        date = datetime.min

    title = meta.get('title', 'Untitled')
    tags = [t.strip() for t in meta.get('tags', '').split(',') if t.strip()]

    # Slug from filename
    fname = os.path.basename(path)
    slug = re.sub(r'^\d{4}-\d{2}-\d{2}_', '', fname).replace('.md', '')

    body_html = md_to_html(body.strip())

    return {
        'title': title,
        'date': date,
        'date_str': date.strftime('%B %-d, %Y'),
        'tags': tags,
        'slug': slug,
        'body_html': body_html,
        'excerpt': excerpt(body_html),
        'image': meta.get('image', ''),   # optional: social preview image (path under the site root)
        'path': f'posts/{slug}.html',
    }


# ---------------------------------------------------------------------------
# Shared HTML chrome
# ---------------------------------------------------------------------------

CSS = """
    :root {
      --bg: #0d0d0d;
      --surface: #161616;
      --surface2: #1e1e1e;
      --border: #2a2a2a;
      --accent: #c8ff00;
      --accent2: #ff3c00;
      --text: #e8e8e8;
      --muted: #777;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: 'Courier New', Courier, monospace;
      background: var(--bg);
      color: var(--text);
      line-height: 1.7;
    }

    a { color: var(--accent); text-decoration: none; }
    a:hover { text-decoration: underline; }

    nav {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 1rem 2rem;
      border-bottom: 1px solid var(--border);
      position: sticky;
      top: 0;
      background: rgba(13,13,13,0.95);
      backdrop-filter: blur(8px);
      z-index: 100;
    }

    .logo {
      font-size: 1.3rem;
      font-weight: 700;
      letter-spacing: 0.05em;
      color: var(--text);
      text-decoration: none;
    }

    .logo span { color: var(--accent); }

    nav ul {
      list-style: none;
      display: flex;
      gap: 2rem;
    }

    nav ul li a {
      color: var(--muted);
      font-size: 0.85rem;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }

    nav ul li a:hover { color: var(--text); text-decoration: none; }
    nav ul li a.active { color: var(--accent); }

    .container {
      max-width: 780px;
      margin: 0 auto;
      padding: 4rem 2rem;
    }

    .page-title {
      font-size: 0.7rem;
      letter-spacing: 0.2em;
      text-transform: uppercase;
      color: var(--accent);
      margin-bottom: 3rem;
    }

    /* POST LIST */
    .post-list { list-style: none; }

    .post-item {
      border-bottom: 1px solid var(--border);
      padding: 2rem 0;
    }

    .post-item:first-child { padding-top: 0; }

    .post-meta {
      font-size: 0.7rem;
      letter-spacing: 0.1em;
      color: var(--muted);
      text-transform: uppercase;
      margin-bottom: 0.5rem;
    }

    .post-title {
      font-size: 1.3rem;
      font-weight: 700;
      color: #fff;
      margin-bottom: 0.75rem;
      line-height: 1.2;
    }

    .post-title a { color: #fff; }
    .post-title a:hover { color: var(--accent); text-decoration: none; }

    .post-excerpt {
      font-size: 0.85rem;
      color: var(--text);
      margin-bottom: 0.75rem;
    }

    .post-tags {
      display: flex;
      flex-wrap: wrap;
      gap: 0.4rem;
    }

    .tag {
      font-size: 0.6rem;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      padding: 0.15rem 0.45rem;
      border: 1px solid var(--border);
      color: var(--muted);
    }

    /* PAGINATION */
    .pagination {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-top: 3rem;
      font-size: 0.8rem;
    }

    .pagination a {
      border: 1px solid var(--border);
      padding: 0.5rem 1rem;
      color: var(--text);
      letter-spacing: 0.08em;
      text-transform: uppercase;
      font-size: 0.75rem;
    }

    .pagination a:hover { border-color: var(--text); text-decoration: none; }
    .pagination .page-info { color: var(--muted); font-size: 0.7rem; letter-spacing: 0.1em; }
    .pagination .spacer { flex: 1; }

    /* SINGLE POST */
    .post-header { margin-bottom: 3rem; }

    .post-header h1 {
      font-size: 2rem;
      font-weight: 700;
      color: #fff;
      line-height: 1.2;
      margin-bottom: 0.75rem;
    }

    .post-body { font-size: 0.92rem; }

    .post-body h1, .post-body h2, .post-body h3 {
      color: #fff;
      font-weight: 700;
      margin: 2rem 0 0.75rem;
    }

    .post-body h1 { font-size: 1.4rem; }
    .post-body h2 { font-size: 1.2rem; }
    .post-body h3 { font-size: 1rem; }

    .post-body p {
      color: var(--text);
      margin-bottom: 1.25rem;
      line-height: 1.8;
    }

    .post-body a { color: var(--accent); }

    .post-body strong { color: var(--text); }

    .post-body pre {
      background: var(--surface2);
      border: 1px solid var(--border);
      padding: 1rem;
      overflow-x: auto;
      margin: 1.25rem 0;
      font-size: 0.8rem;
      line-height: 1.6;
    }

    .post-body code {
      font-family: 'Courier New', Courier, monospace;
      color: var(--accent);
    }

    .post-body pre code {
      color: var(--text);
    }

    .post-body ul, .post-body ol {
      margin: 0 0 1.25rem 1.5rem;
      line-height: 1.8;
    }

    .post-body li { margin-bottom: 0.4rem; }

    .post-body img {
      max-width: 100%;
      height: auto;
      display: block;
      margin: 1.5rem 0;
      border: 1px solid var(--border);
    }

    .post-nav {
      display: flex;
      justify-content: space-between;
      padding-top: 3rem;
      margin-top: 3rem;
      border-top: 1px solid var(--border);
      font-size: 0.75rem;
      gap: 1rem;
    }

    .post-nav a {
      color: var(--muted);
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }

    .post-nav a:hover { color: var(--text); text-decoration: none; }

    footer {
      border-top: 1px solid var(--border);
      padding: 2rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 1rem;
      max-width: 780px;
      margin: 0 auto;
      font-size: 0.75rem;
      color: var(--muted);
    }

    @media (max-width: 600px) {
      nav ul { display: none; }
      .post-header h1 { font-size: 1.5rem; }
    }
"""


# All links are absolute: the host serves /blog and /blog/ alike without a
# redirect, so relative links from /blog resolved one level too high (/posts/...).
def nav_html(active='blog', depth=''):
    return f"""  <nav>
    <a href="/index.html" class="logo">audio<span>destrukt</span></a>
    <ul>
      <li><a href="/index.html#plugin">Plugin</a></li>
      <li><a href="/index.html#features">Features</a></li>
      <li><a href="/index.html#download">Download</a></li>
      <li><a href="/index.html#about">About</a></li>
      <li><a href="/blog/index.html" class="{'active' if active == 'blog' else ''}">Blog</a></li>
    </ul>
  </nav>"""


def footer_html():
    return """  <footer>
    <span>audio<span style="color:var(--accent)">destrukt</span></span>
    <span>&copy; 2025 AudioDestrukt</span>
  </footer>"""


# Cloudflare Web Analytics beacon (cookie-free); also in index.html
ANALYTICS = '''<!-- Cloudflare Web Analytics --><script type='module' src='https://static.cloudflareinsights.com/beacon.min.js' data-cf-beacon='{"token": "f393b960e25f42828910e441d26fa18c"}'></script><!-- End Cloudflare Web Analytics -->'''


def page_shell(title, body, depth='', head_extra=''):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — AudioDestrukt</title>
  <link rel="icon" type="image/svg+xml" href="/favicon.svg">
{head_extra}  <link rel="alternate" type="application/rss+xml" title="AudioDestrukt Blog" href="{SITE_URL}/blog/feed.xml">
  <style>{CSS}</style>
</head>
<body>
{nav_html(depth=depth)}
{body}
{footer_html()}
{ANALYTICS}
</body>
</html>"""


# ---------------------------------------------------------------------------
# Page generators
# ---------------------------------------------------------------------------

def page_href(n):
    return 'index.html' if n == 1 else f'page-{n}.html'


def build_index_page(posts, page_num, total_pages):
    items = []
    for p in posts:
        tags_html = ''.join(f'<span class="tag">{t}</span>' for t in p['tags']) if p['tags'] else ''
        tag_block = f'<div class="post-tags">{tags_html}</div>' if tags_html else ''
        items.append(f"""    <li class="post-item">
      <div class="post-meta">{p['date_str']}</div>
      <div class="post-title"><a href="/blog/posts/{p['slug']}.html">{p['title']}</a></div>
      <div class="post-excerpt">{p['excerpt']}</div>
      {tag_block}
    </li>""")

    prev_link = ''
    next_link = ''
    if page_num > 1:
        prev_link = f'<a href="/blog/{page_href(page_num - 1)}">&larr; Newer</a>'
    if page_num < total_pages:
        next_link = f'<a href="/blog/{page_href(page_num + 1)}">Older &rarr;</a>'

    pagination = f"""    <div class="pagination">
      {prev_link}
      <span class="spacer"></span>
      <span class="page-info">Page {page_num} of {total_pages}</span>
      <span class="spacer"></span>
      {next_link}
    </div>"""

    body = f"""  <div class="container">
    <div class="page-title">Blog</div>
    <ul class="post-list">
{''.join(items)}
    </ul>
{pagination}
  </div>"""

    return page_shell(f'Blog — Page {page_num}', body, depth='')


def social_meta(post):
    """Open Graph / Twitter card tags for a post that names an `image:` in its frontmatter."""
    if not post['image']:
        return ''
    esc = lambda s: s.replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;')
    # Description: the opening words of the body, without the repeated H1
    desc = excerpt(re.sub(r'<h1>.*?</h1>', '', post['body_html'], count=1, flags=re.DOTALL), words=40)
    image = f"{SITE_URL}/{post['image'].lstrip('/')}"
    url = f"{SITE_URL}/blog/posts/{post['slug']}.html"
    tags = [
        ('property', 'og:type', 'article'),
        ('property', 'og:site_name', 'AudioDestrukt'),
        ('property', 'og:title', post['title']),
        ('property', 'og:description', desc),
        ('property', 'og:url', url),
        ('property', 'og:image', image),
        ('name', 'twitter:card', 'summary_large_image'),
        ('name', 'twitter:image', image),
        ('name', 'description', desc),
    ]
    return ''.join(f'  <meta {k}="{n}" content="{esc(v)}">\n' for k, n, v in tags)


def build_post_page(post, prev_post, next_post):
    prev_link = ''
    next_link = ''
    if prev_post:
        prev_link = f'<a href="/blog/posts/{prev_post["slug"]}.html">&larr; {prev_post["title"]}</a>'
    if next_post:
        next_link = f'<a href="/blog/posts/{next_post["slug"]}.html">{next_post["title"]} &rarr;</a>'

    post_nav = f"""    <div class="post-nav">
      <div>{prev_link}</div>
      <div>{next_link}</div>
    </div>"""

    tags_html = ''.join(f'<span class="tag">{t}</span>' for t in post['tags'])
    tag_block = f'<div class="post-tags" style="margin-top:0.75rem">{tags_html}</div>' if tags_html else ''

    body = f"""  <div class="container">
    <div class="post-header">
      <div class="post-meta"><a href="/blog/index.html">Blog</a> &mdash; {post['date_str']}</div>
      <h1>{post['title']}</h1>
      {tag_block}
    </div>
    <div class="post-body">
{post['body_html']}
    </div>
{post_nav}
  </div>"""

    return page_shell(post['title'], body, depth='posts/', head_extra=social_meta(post))


# ---------------------------------------------------------------------------
# RSS feed
# ---------------------------------------------------------------------------

def rss_date(dt):
    """Format datetime as RFC 822 for RSS pubDate."""
    return dt.strftime('%a, %d %b %Y %H:%M:%S +0000')


def xml_escape(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def build_rss(posts, limit=20):
    items = []
    for p in posts[:limit]:
        url = f'{SITE_URL}/blog/posts/{p["slug"]}.html'
        plain_excerpt = re.sub(r'<[^>]+>', '', p['excerpt'])
        items.append(f"""    <item>
      <title>{xml_escape(p['title'])}</title>
      <link>{url}</link>
      <guid isPermaLink="true">{url}</guid>
      <pubDate>{rss_date(p['date'])}</pubDate>
      <description>{xml_escape(plain_excerpt)}</description>
    </item>""")

    build_date = rss_date(datetime.utcnow())
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>AudioDestrukt</title>
    <link>{SITE_URL}</link>
    <description>A poke in the ear with a sharp stick.</description>
    <language>en-us</language>
    <lastBuildDate>{build_date}</lastBuildDate>
    <atom:link href="{SITE_URL}/blog/feed.xml" rel="self" type="application/rss+xml"/>
{''.join(items)}
  </channel>
</rss>"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # Load posts
    posts = []
    for fname in os.listdir(POSTS_DIR):
        if not fname.endswith('.md'):
            continue
        p = parse_post(os.path.join(POSTS_DIR, fname))
        if p:
            posts.append(p)

    # Sort newest first
    posts.sort(key=lambda p: p['date'], reverse=True)

    # Create output dirs
    os.makedirs(POSTS_OUT_DIR, exist_ok=True)

    # Build index pages
    total_pages = (len(posts) + PER_PAGE - 1) // PER_PAGE
    for page_num in range(1, total_pages + 1):
        slice_ = posts[(page_num - 1) * PER_PAGE : page_num * PER_PAGE]
        html = build_index_page(slice_, page_num, total_pages)
        out_path = os.path.join(OUT_DIR, page_href(page_num))
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f'  wrote {out_path}')

    # Build individual post pages
    for i, post in enumerate(posts):
        prev_post = posts[i - 1] if i > 0 else None        # newer
        next_post = posts[i + 1] if i < len(posts) - 1 else None  # older
        html = build_post_page(post, prev_post, next_post)
        out_path = os.path.join(POSTS_OUT_DIR, f'{post["slug"]}.html')
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(html)

    # Build RSS feed (last 20 posts)
    rss = build_rss(posts, limit=20)
    rss_path = os.path.join(OUT_DIR, 'feed.xml')
    with open(rss_path, 'w', encoding='utf-8') as f:
        f.write(rss)
    print(f'  wrote {rss_path}')

    print(f'\nDone. {len(posts)} posts across {total_pages} index pages.')


if __name__ == '__main__':
    main()
