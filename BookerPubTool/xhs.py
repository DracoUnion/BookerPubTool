# -*- coding: utf-8 -*-

"""xhs — Publish to Xiaohongshu (小红书) via Playwright.

Python port of content-pipeline's platforms/xiaohongshu.ts.
Opens creator.xiaohongshu.com, uploads images, fills in copy.
"""

import os
import re
from os import path
from .util import timestr, plrt_create_driver
from .distribute import load_manifest, get_outputs, status_print, hold_browser

CREATOR_URL = 'https://creator.xiaohongshu.com/publish/publish'

# Selectors extracted for easy update when the UI changes (mirrors xiaohongshu.ts)
SELECTORS = {
    'uploadInput': 'input[type="file"]',
    'titleInput': '.titleInput input, input[placeholder*="标题"], .c-input_inner[placeholder*="标题"]',
    'contentEditor': '.ql-editor, [contenteditable="true"].content, div[data-placeholder*="正文"]',
    'tagInput': '.tag-input input, input[placeholder*="话题"]',
    'publishBtn': 'button.publishBtn, button.css-k0vba7, button[class*="publish"]',
    'loginIndicator': '.avatar, .user-avatar, img[class*="avatar"]',
}


def publish_xhs(args):
    manifest = load_manifest(args.manifest)
    xhs_data = get_outputs(manifest).get('xiaohongshu')
    if not xhs_data:
        status_print('skipped', 'No Xiaohongshu content in manifest')
        return

    copy = xhs_data.get('copy') or {}
    title = copy.get('title') or ''
    body = copy.get('body') or ''
    tags = copy.get('tags') or []

    with plrt_create_driver(headless=args.headless) as (browser, context, page):
        page.goto(CREATOR_URL, wait_until='domcontentloaded')
        page.wait_for_timeout(8000)  # Wait for page load + potential redirects

        # Login detection
        page_url = page.url
        try:
            page.wait_for_selector(SELECTORS['loginIndicator'], timeout=5000)
        except Exception:
            pass
        if 'login' in page_url:
            status_print('assisted',
                         'Login required. Please log in to Xiaohongshu, then re-run the command.')
            if not args.headless:
                hold_browser('请在弹出的浏览器中完成登录审阅，完成后回车关闭。')
            return

        # Upload images if available
        images_dir = xhs_data.get('images_dir')
        if images_dir and path.isdir(images_dir):
            files = sorted(
                path.join(images_dir, f) for f in os.listdir(images_dir)
                if re.search(r'\.(png|jpg|jpeg|webp)$', f, re.IGNORECASE))
            if files:
                try:
                    page.set_input_files(SELECTORS['uploadInput'], files)
                    print(f'{timestr()}  上传 {len(files)} 张图片')
                    page.wait_for_timeout(3000)  # Upload processing
                except Exception:
                    print(f'{timestr()}  Upload input not found: {SELECTORS["uploadInput"]}')

        # Title
        try:
            page.wait_for_selector(SELECTORS['titleInput'], timeout=5000)
            page.fill(SELECTORS['titleInput'], title)
            print(f'{timestr()}  标题: {title[:30]}...')
        except Exception:
            pass

        page.wait_for_timeout(300)

        # Body
        try:
            page.wait_for_selector(SELECTORS['contentEditor'], timeout=5000)
            page.click(SELECTORS['contentEditor'])
            page.wait_for_timeout(200)
            page.keyboard.insert_text(body)
            print(f'{timestr()}  正文 {len(body)} 字')
        except Exception:
            pass

        page.wait_for_timeout(300)

        # Tags
        for tag in tags:
            clean = tag.lstrip('#')
            try:
                page.wait_for_selector(SELECTORS['tagInput'], timeout=3000)
                page.click(SELECTORS['tagInput'])
                page.wait_for_timeout(200)
                page.keyboard.type(clean)
                page.wait_for_timeout(600)
                page.keyboard.press('Enter')
                page.wait_for_timeout(400)
            except Exception:
                break

        if args.preview:
            status_print('assisted',
                         'Content pre-filled in Xiaohongshu editor. Review and publish manually.')
            if not args.headless:
                hold_browser('内容已预填。请在浏览器中审阅/手动发布，完成后回车关闭。')
            return

        # Publish
        try:
            page.wait_for_selector(SELECTORS['publishBtn'], timeout=5000)
            page.wait_for_timeout(500)
            page.click(SELECTORS['publishBtn'])
            page.wait_for_timeout(3000)
            status_print('success', 'Published to Xiaohongshu')
        except Exception:
            status_print('assisted',
                         'Content filled, publish button not found. Please publish manually.')
            if not args.headless:
                hold_browser('发布按钮未找到，请在浏览器中手动发布，完成后回车关闭。')


def reg_subparser(subparsers):
    parser = subparsers.add_parser("xhs", help="publish to Xiaohongshu (小红书)")
    from .distribute import add_common_args
    add_common_args(parser)
    parser.set_defaults(func=publish_xhs)