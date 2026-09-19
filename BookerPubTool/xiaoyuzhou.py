# -*- coding: utf-8 -*-

"""xiaoyuzhou — Publish to Xiaoyuzhou (小宇宙) via Playwright.

Python port of content-pipeline's platforms/xiaoyuzhou.ts.
Opens studio.xiaoyuzhoufm.com, uploads audio, fills show notes.
"""

import os
from os import path
from .util import timestr, plrt_create_driver
from .distribute import status_print, hold_browser

XIAOYUZHOU_URL = 'https://studio.xiaoyuzhoufm.com/'

SELECTORS = {
    'newEpisodeBtn': 'a[href*="episode/new"], button:has-text("新建节目"), a:has-text("新建")',
    'audioUpload': 'input[type="file"][accept*="audio"], input[type="file"][accept*="mp3"]',
    'titleInput': 'input[placeholder*="标题"], input[name="title"]',
    'descriptionEditor': 'textarea[placeholder*="简介"], [contenteditable="true"], textarea[name="description"]',
    'showNotesEditor': 'textarea[placeholder*="文稿"], textarea[name="shownotes"]',
    'publishBtn': 'button:has-text("发布"), button[type="submit"]',
}


def publish_xiaoyuzhou(args):
    audio = args.audio
    if not audio or not path.exists(audio):
        status_print('manual', f'Audio file not found: {audio}. Upload manually.')
        return

    title = args.title or ''
    description = args.description or ''
    show_notes = args.show_notes or ''

    with plrt_create_driver(headless=args.headless) as (browser, context, page):
        page.goto(XIAOYUZHOU_URL, wait_until='domcontentloaded')
        page.wait_for_timeout(8000)  # Wait for page load + potential redirects

        # Navigate to new episode
        try:
            page.wait_for_selector(SELECTORS['newEpisodeBtn'], timeout=5000)
            page.click(SELECTORS['newEpisodeBtn'])
            page.wait_for_timeout(2000)
        except Exception:
            pass

        # Upload audio
        try:
            page.wait_for_selector(SELECTORS['audioUpload'], timeout=5000)
            page.set_input_files(SELECTORS['audioUpload'], audio)
            print(f'{timestr()}  音频已上传: {audio}')
            page.wait_for_timeout(5000)  # Audio processing
        except Exception:
            status_print('assisted', 'Audio upload element not found. Upload audio manually.')
            if not args.headless:
                hold_browser('请在浏览器中手动上传音频，完成后回车关闭。')
            return

        # Title
        try:
            page.wait_for_selector(SELECTORS['titleInput'], timeout=5000)
            page.fill(SELECTORS['titleInput'], title)
            print(f'{timestr()}  标题: {title}')
        except Exception:
            pass
        page.wait_for_timeout(300)

        # Description
        try:
            page.wait_for_selector(SELECTORS['descriptionEditor'], timeout=3000)
            page.click(SELECTORS['descriptionEditor'])
            page.wait_for_timeout(200)
            page.keyboard.insert_text(description)
        except Exception:
            pass

        # Show notes
        try:
            page.wait_for_selector(SELECTORS['showNotesEditor'], timeout=3000)
            page.click(SELECTORS['showNotesEditor'])
            page.wait_for_timeout(200)
            page.keyboard.insert_text(show_notes)
            print(f'{timestr()}  文稿已填入')
        except Exception:
            pass

        if args.preview:
            status_print('assisted',
                         'Episode pre-filled in Xiaoyuzhou editor. Review and publish manually.')
            if not args.headless:
                hold_browser('内容已预填。请在浏览器中审阅/手动发布，完成后回车关闭。')
            return

        try:
            page.wait_for_selector(SELECTORS['publishBtn'], timeout=5000)
            page.wait_for_timeout(500)
            page.click(SELECTORS['publishBtn'])
            page.wait_for_timeout(5000)
            status_print('success', 'Episode published to Xiaoyuzhou')
        except Exception:
            status_print('assisted',
                         'Content filled, publish button not found. Publish manually.')
            if not args.headless:
                hold_browser('发布按钮未找到，请在浏览器中手动发布，完成后回车关闭。')


def reg_subparser(subparsers):
    parser = subparsers.add_parser("xiaoyuzhou", help="publish to Xiaoyuzhou (小宇宙)")
    parser.add_argument("--audio", help="音频文件路径")
    parser.add_argument("--title", help="播客标题")
    parser.add_argument("--description", help="播客简介")
    parser.add_argument("--show-notes", help="完整 show notes")
    parser.add_argument("-p", "--preview", action="store_true",
                        help="只预填不发布，留浏览器给人工审阅")
    parser.add_argument("-H", "--headless", action="store_true",
                        help="无头模式运行 Chromium")
    parser.set_defaults(func=publish_xiaoyuzhou)