# -*- coding: utf-8 -*-

"""gzh — Publish to WeChat Official Account (公众号).

Python port of content-pipeline's scripts/distribute/wechat-api.ts + platforms/wechat.ts.

Strategy:
  L0: WeChat API → push to drafts directly (no browser)
  L3: Manual → print the HTML/markdown file path for copy-paste
"""

import os
import re
import json
from urllib.parse import unquote
from datetime import datetime
from os import path
from .util import timestr, request_retry, read_file
from .distribute import load_manifest, get_outputs, status_print

WECHAT_API_BASE = 'https://api.weixin.qq.com'
MAX_RETRIES = 2
RETRY_DELAY_MS = 3000
CONFIG_DIR = path.join(path.expanduser('~'), '.config', 'wechat-api')
CONFIG_FILE = path.join(CONFIG_DIR, 'config.json')
TOKEN_CACHE_FILE = path.join(CONFIG_DIR, 'token-cache.json')
TOKEN_LIFETIME_MS = 2 * 60 * 60 * 1000      # 2 hours
TOKEN_REFRESH_BUFFER_MS = 5 * 60 * 1000     # refresh 5 min early


def _reset_verify(path_):
    # 图片/素材 POST multipart 上传时微信证书校验在多数环境下失败，关闭校验（对应 TS 的 BUN_FETCH_OPTS）
    return {'verify': False}


# ─── Credentials ───

def load_credentials():
    app_id = os.environ.get('WECHAT_APPID', '').strip()
    app_secret = os.environ.get('WECHAT_APPSECRET', '').strip()
    if app_id and app_secret:
        return {'appId': app_id, 'appSecret': app_secret}

    if path.exists(CONFIG_FILE):
        try:
            cfg = json.loads(read_file(CONFIG_FILE, 'utf-8'))
            if cfg.get('appId') and cfg.get('appSecret'):
                return {'appId': cfg['appId'], 'appSecret': cfg['appSecret']}
        except Exception:
            pass

    return None


# ─── Access Token ───

def _read_token_cache():
    if not path.exists(TOKEN_CACHE_FILE):
        return None
    try:
        cache = json.loads(read_file(TOKEN_CACHE_FILE, 'utf-8'))
        now_ms = datetime.now().timestamp() * 1000
        if cache.get('accessToken') and cache.get('expiresAt', 0) > now_ms + TOKEN_REFRESH_BUFFER_MS:
            return cache
    except Exception:
        pass
    return None


def _write_token_cache(token, expires_in):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    cache = {
        'accessToken': token,
        'expiresAt': (datetime.now().timestamp() + expires_in) * 1000,
    }
    with open(TOKEN_CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False)


def get_access_token(creds, _retry=3):
    cached = _read_token_cache()
    if cached:
        return cached['accessToken']

    url = (f'{WECHAT_API_BASE}/cgi-bin/token?grant_type=client_credential'
           f'&appid={creds["appId"]}&secret={creds["appSecret"]}')
    r = request_retry('GET', url, retry=_retry)
    r.raise_for_status()
    data = r.json()
    if data.get('errcode'):
        raise RuntimeError(f"WeChat API error {data['errcode']}: {data.get('errmsg')}")
    if not data.get('access_token') or not data.get('expires_in'):
        raise RuntimeError('Invalid access_token response')

    _write_token_cache(data['access_token'], data['expires_in'])
    print(f'{timestr()}  [wechat-api] Access token obtained')
    return data['access_token']


# ─── Image Upload ───

def _mime_for(image_path):
    ext = path.splitext(image_path)[1].lstrip('.') or 'png'
    return 'image/jpeg' if ext == 'jpg' else f'image/{ext}'


def upload_content_image(token, image_path):
    url = f'{WECHAT_API_BASE}/cgi-bin/media/uploadimg?access_token={token}'
    with open(image_path, 'rb') as f:
        files = {'media': (path.basename(image_path), f, _mime_for(image_path))}
        r = request_retry('POST', url, files=files, **_reset_verify('upload'))
    data = r.json()
    if data.get('errcode'):
        raise RuntimeError(f"uploadimg error {data['errcode']}: {data.get('errmsg')}")
    if not data.get('url'):
        raise RuntimeError('uploadimg: no URL returned')
    return data['url']


def upload_cover_image(token, image_path):
    url = f'{WECHAT_API_BASE}/cgi-bin/material/add_material?access_token={token}&type=image'
    with open(image_path, 'rb') as f:
        files = {'media': (path.basename(image_path), f, _mime_for(image_path))}
        r = request_retry('POST', url, files=files, **_reset_verify('cover'))
    data = r.json()
    if data.get('errcode'):
        raise RuntimeError(f"add_material error {data['errcode']}: {data.get('errmsg')}")
    if not data.get('media_id'):
        raise RuntimeError('add_material: no media_id returned')
    return data['media_id']


# ─── HTML Processing ───

def fix_html_for_wechat(html):
    """Fix HTML structures WeChat cannot render properly (port of fixHtmlForWechat)."""
    fixed = html

    # Fix <p><figure>...</figure></p> nesting — extract <figure> out of <p>, convert to <section>
    def _fig2section(m):
        content = m.group(1)
        return re.sub(r'<figure', '<section',
                      re.sub(r'</figure>', '</section>', content))

    fixed = re.sub(
        r'<p[^>]*>\s*(<figure[\s\S]*?</figure>)\s*</p>', _fig2section, fixed, flags=re.IGNORECASE)
    fixed = re.sub(r'<figure([^>]*)>', r'<section\1>', fixed, flags=re.IGNORECASE)
    fixed = re.sub(r'</figure>', '</section>', fixed, flags=re.IGNORECASE)

    # Normalize <img> styles for WeChat compatibility
    def _img_style(m):
        attrs = m.group(1)
        attrs = re.sub(r'\s*style="[^"]*"', '', attrs, flags=re.IGNORECASE)
        attrs = re.sub(r"\s*style='[^']*'", '', attrs, flags=re.IGNORECASE)
        wechat_style = 'style="max-width:100%;height:auto;display:block;margin:0 auto;border-radius:8px;"'
        return f'<img{attrs} {wechat_style}>'

    fixed = re.sub(r'<img([^>]*?)>', _img_style, fixed, flags=re.IGNORECASE)
    return fixed


def _strip_tip_elements(html):
    return re.sub(
        r'<div[^>]*class=["\'][^"\']*\btip\b[^"\']*["\'][^>]*>[\s\S]*?</div>', '', html,
        flags=re.IGNORECASE).strip()


def extract_article_content(html):
    """Extract {content, styles} from a WeChat-formatted HTML file."""
    style_matches = re.findall(r'<style[^>]*>([\s\S]*?)</style>', html, flags=re.IGNORECASE)
    styles = '\n'.join(s.strip() for s in style_matches)

    # Priority: #output → .content → <body>
    m = re.search(r'<div[^>]*id=["\']output["\'][^>]*>([\s\S]*?)</div>\s*(?:</body>|<script|$)', html,
                  flags=re.IGNORECASE)
    if not m:
        m = re.search(
            r'<div[^>]*class=["\'][^"\']*\bcontent\b[^"\']*["\'][^>]*>([\s\S]*?)</div>\s*(?:</body>|<script|$)',
            html, flags=re.IGNORECASE)
    if not m:
        m = re.search(r'<body[^>]*>([\s\S]*?)</body>', html, flags=re.IGNORECASE)
    if not m:
        raise RuntimeError('Could not extract article content from HTML')

    return {'content': _strip_tip_elements(m.group(1).strip()), 'styles': styles}


LOCAL_IMG_RE = re.compile(r'src=["\'](/(?:Users|home|tmp|var)[^"\']+\.(?:png|jpg|jpeg|gif|webp|bmp))["\']',
                          re.IGNORECASE)


def upload_local_images_in_html(html, token):
    """Upload local image paths (src=/Users/...) to WeChat CDN; replace with CDN urls."""
    matches = list(LOCAL_IMG_RE.finditer(html))
    if not matches:
        return html

    print(f'  [wechat-api] Found {len(matches)} local image(s) to upload...')
    processed = html
    uploaded, failed = 0, 0

    for m in matches:
        full, local_path = m.group(0), m.group(1)
        try:
            decoded = unquote(local_path)
        except Exception:
            decoded = local_path

        if not path.exists(decoded):
            print(f'  [wechat-api]   ✗ Not found: {decoded}')
            failed += 1
            continue
        try:
            cdn_url = upload_content_image(token, decoded)
            processed = processed.replace(full, f'src="{cdn_url}"')
            uploaded += 1
            print(f'  [wechat-api]   ✓ {path.basename(decoded)}')
        except Exception as e:
            print(f'  [wechat-api]   ✗ {path.basename(decoded)}: {e}')
            failed += 1

    print(f'  [wechat-api] Local images: {uploaded} uploaded, {failed} failed')
    return processed


def process_html_with_images(content, styles, image_map):
    """Fix HTML then replace [[IMAGE_PLACEHOLDER_N]] tokens (port of processHtmlWithImages)."""
    processed = fix_html_for_wechat(content)
    for placeholder, cdn_url in image_map.items():
        processed = processed.replace(
            placeholder, f'<img src="{cdn_url}" style="max-width: 100%; height: auto;" />')
    if styles:
        return f'<style>{styles}</style>\n{processed}'
    return processed


# ─── Draft Creation ───

def create_draft(token, article):
    url = f'{WECHAT_API_BASE}/cgi-bin/draft/add?access_token={token}'
    body = {
        'articles': [{
            'title': article['title'],
            'author': article.get('author', ''),
            'digest': article.get('digest', ''),
            'content': article['content'],
            'thumb_media_id': article['thumb_media_id'],
            'content_source_url': '',
            'need_open_comment': 0,
            'only_fans_can_comment': 0,
        }],
    }
    r = request_retry('POST', url, headers={'Content-Type': 'application/json'},
                      data=json.dumps(body, ensure_ascii=False))
    data = r.json()
    if data.get('errcode'):
        raise RuntimeError(f"draft/add error {data['errcode']}: {data.get('errmsg')}")
    if not data.get('media_id'):
        raise RuntimeError('draft/add: no media_id returned')
    return {'media_id': data['media_id']}


# ─── Main Orchestrator ───

def publish_via_api(manifest):
    wechat_data = manifest['outputs'].get('wechat')
    if not wechat_data:
        raise RuntimeError('No wechat data in manifest')

    has_html = wechat_data.get('html') and path.exists(wechat_data['html'])
    has_markdown = wechat_data.get('markdown') and path.exists(wechat_data['markdown'])

    if not has_html and has_markdown:
        raise RuntimeError(
            'Markdown-only mode is no longer supported.\n'
            'Please convert markdown to HTML first using content-pipeline md2wechat_formatter.py, '
            'then set wechat.html in the manifest to the generated _preview.html path.')
    if not has_html:
        raise RuntimeError('No wechat HTML file in manifest. Provide wechat.html '
                           'pointing to a _preview.html file.')

    creds = load_credentials()
    if not creds:
        raise RuntimeError('No WeChat API credentials configured')

    print(f'{timestr()}  [wechat-api] Starting API publish flow...')
    token = get_access_token(creds)

    print(f'{timestr()}  [wechat-api] Using pre-rendered HTML')
    extracted = extract_article_content(wechat_data['html'])
    html_content = extracted['content']  # pre-rendered HTML needs no <style> wrapper
    title = wechat_data.get('title') or manifest.get('title')
    author = wechat_data.get('author')
    digest = wechat_data.get('digest')

    image_map = {}
    content = process_html_with_images(html_content, '', image_map)

    content = upload_local_images_in_html(content, token)

    # Upload manifest.images and insert into article content
    images = wechat_data.get('images') or []
    if images:
        print(f'  [wechat-api] Uploading {len(images)} article image(s)...')
        uploaded = []
        for img in images:
            if not path.exists(img):
                print(f'  [wechat-api]   ✗ Image not found: {img}')
                continue
            try:
                cdn = upload_content_image(token, img)
                uploaded.append((cdn, path.basename(img)))
                print(f'  [wechat-api]   ✓ {path.basename(img)}')
            except Exception as e:
                print(f'  [wechat-api]   ✗ {path.basename(img)}: {e}')

        def _img_tag(url):
            return (f'<section style="text-align:center;margin:20px 0;">'
                    f'<img src="{url}" style="max-width:100%;height:auto;display:block;'
                    f'margin:0 auto;border-radius:8px;" /></section>')

        if uploaded:
            inserted = 0
            for url, fname in uploaded:
                tag = _img_tag(url)
                base = re.sub(r'\.[^.]+$', '', fname)
                for ph in (f'<!-- IMAGE:{fname} -->', f'<!-- IMAGE:{base} -->'):
                    if ph in content:
                        content = content.replace(ph, tag)
                        inserted += 1
                        break
            if inserted == 0:
                print(f'  [wechat-api] No image placeholders found, appending {len(uploaded)} image(s) at end')
                content += '\n' + '\n'.join(_img_tag(url) for url, _ in uploaded)
            else:
                print(f'  [wechat-api] Inserted {inserted}/{len(uploaded)} image(s) at placeholders')

    # Cover image (required for draft)
    cover = wechat_data.get('cover_image')
    thumb_media_id = None
    if cover and path.exists(cover):
        print(f'{timestr()}  [wechat-api] Uploading cover image...')
        thumb_media_id = upload_cover_image(token, cover)
    elif images and path.exists(images[0]):
        print(f'{timestr()}  [wechat-api] No cover image specified, using first content image...')
        thumb_media_id = upload_cover_image(token, images[0])
    else:
        raise RuntimeError('No cover image available. Provide cover_image in manifest or '
                           'ensure article has images.')
    if not thumb_media_id:
        raise RuntimeError('Failed to obtain cover image media_id')

    print(f'{timestr()}  [wechat-api] Creating draft...')
    draft = create_draft(token, {
        'title': title, 'content': content, 'author': author, 'digest': digest,
        'thumb_media_id': thumb_media_id,
    })
    print(f'{timestr()}  [wechat-api] Draft created successfully (media_id: {draft["media_id"]})')
    return draft


def publish_gzh(args):
    manifest = load_manifest(args.manifest)
    wechat_data = get_outputs(manifest).get('wechat')
    if not wechat_data:
        status_print('skipped', 'No WeChat content in manifest')
        return

    has_html = wechat_data.get('html') and path.exists(wechat_data['html'])
    has_markdown = wechat_data.get('markdown') and path.exists(wechat_data['markdown'])
    if not has_html and not has_markdown:
        status_print('manual',
                     'No HTML or Markdown file found in manifest. Provide wechat.html (rendered '
                     '_preview.html) or wechat.markdown.')
        return

    # L0: primary draft via API (skipped in preview mode)
    if not getattr(args, 'preview', False):
        try:
            result = publish_via_api(manifest)
            status_print('success',
                         f'Article pushed to drafts via API (media_id: {result["media_id"]})')
            return
        except Exception as e:
            reason = str(e)
            print(f'  [gzh] API mode failed: {reason}')

    # L3: manual fallback
    file_path = wechat_data.get('html') if has_html else wechat_data.get('markdown')
    status_print('manual', f'API publish failed or preview mode. File: {file_path}')


def reg_subparser(subparsers):
    parser = subparsers.add_parser("gzh", help="publish article to WeChat Official Account (公众号)")
    from .distribute import add_common_args
    add_common_args(parser)
    parser.set_defaults(func=publish_gzh)