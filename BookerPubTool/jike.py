# -*- coding: utf-8 -*-

"""jike — Publish to Jike (即刻) via Playwright.

Python port of content-pipeline's platforms/jike.ts.
Opens web.okjike.com, fills in post content.
"""

from .util import timestr, plrt_create_driver
from .distribute import load_manifest, get_outputs, status_print, hold_browser

JIKE_URL = 'https://web.okjike.com/'

SELECTORS = {
    'composeBtn': 'button[class*="compose"], a[href*="compose"], div[class*="ComposeButton"]',
    'contentEditor': '[contenteditable="true"], textarea[placeholder*="分享"], .ql-editor',
    'publishBtn': 'button[class*="submit"], button[class*="publish"], button:has-text("发布")',
    'loginIndicator': 'img[class*="avatar"], div[class*="Avatar"]',
}


def publish_jike(args):
    manifest = load_manifest(args.manifest)
    jike_data = get_outputs(manifest).get('jike')
    if not jike_data:
        status_print('skipped', 'No Jike content in manifest')
        return

    copy = jike_data.get('copy') or {}
    body = copy.get('body') or ''

    with plrt_create_driver(headless=args.headless) as (browser, context, page):
        page.goto(JIKE_URL, wait_until='domcontentloaded')
        page.wait_for_timeout(4000)  # Jike loads slowly

        try:
            page.wait_for_selector(SELECTORS['loginIndicator'], timeout=5000)
        except Exception:
            pass
        if 'login' in page.url:
            status_print('assisted',
                         'Login required. Please log in to Jike, then re-run the command.')
            if not args.headless:
                hold_browser('请在弹出的浏览器中完成登录审阅，完成后回车关闭。')
            return

        # Open the compose editor
        try:
            page.wait_for_selector(SELECTORS['composeBtn'], timeout=5000)
            page.click(SELECTORS['composeBtn'])
            page.wait_for_timeout(1500)
        except Exception:
            pass

        # Fill content
        try:
            page.wait_for_selector(SELECTORS['contentEditor'], timeout=5000)
            page.click(SELECTORS['contentEditor'])
            page.wait_for_timeout(200)
            page.keyboard.insert_text(body)
            print(f'{timestr()}  正文 {len(body)} 字')
        except Exception:
            status_print('assisted', 'Editor not found. Jike is open, paste manually.')
            if not args.headless:
                hold_browser('请在浏览器中手动粘贴内容，完成后回车关闭。')
            return

        if args.preview:
            circles = '、'.join(copy.get('circles') or [])
            status_print('assisted',
                         f'Content pre-filled in Jike editor. Circles: {circles}')
            if not args.headless:
                hold_browser('内容已预填。请在浏览器中审阅/手动发布，完成后回车关闭。')
            return

        try:
            page.wait_for_selector(SELECTORS['publishBtn'], timeout=5000)
            page.wait_for_timeout(500)
            page.click(SELECTORS['publishBtn'])
            page.wait_for_timeout(3000)
            status_print('success', 'Published to Jike')
        except Exception:
            status_print('assisted', 'Content filled, publish button not found. Please publish manually.')
            if not args.headless:
                hold_browser('发布按钮未找到，请在浏览器中手动发布，完成后回车关闭。')


def reg_subparser(subparsers):
    parser = subparsers.add_parser("jike", help="publish to Jike (即刻)")
    from .distribute import add_common_args
    add_common_args(parser)
    parser.set_defaults(func=publish_jike)