# -*- coding: utf-8 -*-

"""douyin — Publish to Douyin (抖音) via Playwright.

Python port of content-pipeline's platforms/douyin.ts.
EXPERIMENTAL: Douyin has aggressive anti-automation.
"""

import os
from os import path
from .util import timestr, plrt_create_driver
from .distribute import load_manifest, get_outputs, status_print, hold_browser

DOUYIN_URL = 'https://creator.douyin.com/creator-micro/content/upload'

SELECTORS = {
    'videoUpload': 'input[type="file"][accept*="video"]',
    'titleInput': 'input[placeholder*="标题"], input[class*="title"]',
    'descriptionEditor': '[contenteditable="true"], textarea[placeholder*="描述"], div[class*="editor"]',
    'tagInput': 'input[placeholder*="话题"], input[class*="topic"]',
    'publishBtn': 'button:has-text("发布"), button[class*="publish"]',
}


def publish_douyin(args):
    manifest = load_manifest(args.manifest)
    douyin_data = get_outputs(manifest).get('douyin')
    if not douyin_data:
        status_print('skipped', 'No Douyin content in manifest')
        return

    video = douyin_data.get('video')
    if not video or not path.exists(video):
        status_print('manual', f'Video file not found: {video}. Upload manually.')
        return

    copy = douyin_data.get('copy') or {}
    title = copy.get('title') or ''
    description = copy.get('description') or ''
    tags = copy.get('tags') or []

    with plrt_create_driver(headless=args.headless) as (browser, context, page):
        page.goto(DOUYIN_URL, wait_until='domcontentloaded')
        page.wait_for_timeout(5000)  # Douyin loads slowly

        if 'login' in page.url:
            status_print('assisted',
                         'Login required. Please scan QR to log in to Douyin, then re-run the command.')
            if not args.headless:
                hold_browser('请在弹出的浏览器中扫码登录，完成后回车关闭。')
            return

        # Upload video
        try:
            page.wait_for_selector(SELECTORS['videoUpload'], timeout=8000)
            page.set_input_files(SELECTORS['videoUpload'], video)
            print(f'{timestr()}  视频已上传: {video}')
            page.wait_for_timeout(10000)  # Video processing takes time
        except Exception:
            status_print('assisted', 'Video upload element not found. Upload video manually.')
            if not args.headless:
                hold_browser('请在浏览器中手动上传视频，完成后回车关闭。')
            return

        # Title
        try:
            page.wait_for_selector(SELECTORS['titleInput'], timeout=5000)
            page.fill(SELECTORS['titleInput'], title)
        except Exception:
            pass
        page.wait_for_timeout(300)

        # Description
        try:
            page.wait_for_selector(SELECTORS['descriptionEditor'], timeout=5000)
            page.click(SELECTORS['descriptionEditor'])
            page.wait_for_timeout(200)
            page.keyboard.insert_text(description)
        except Exception:
            pass

        # Tags
        for tag in tags:
            clean = tag.lstrip('#')
            try:
                page.wait_for_selector(SELECTORS['tagInput'], timeout=3000)
                page.click(SELECTORS['tagInput'])
                page.wait_for_timeout(200)
                page.keyboard.type(clean)
                page.wait_for_timeout(500)
                page.keyboard.press('Enter')
                page.wait_for_timeout(400)
            except Exception:
                break

        if args.preview:
            status_print('assisted', 'Content pre-filled in Douyin editor.')
            if not args.headless:
                hold_browser('内容已预填。请在浏览器中审阅/手动发布，完成后回车关闭。')
            return

        try:
            page.wait_for_selector(SELECTORS['publishBtn'], timeout=5000)
            page.wait_for_timeout(500)
            page.click(SELECTORS['publishBtn'])
            page.wait_for_timeout(5000)
            status_print('success', 'Published to Douyin')
        except Exception:
            status_print('assisted', 'Content filled, publish manually.')
            if not args.headless:
                hold_browser('发布按钮未找到，请在浏览器中手动发布，完成后回车关闭。')


def reg_subparser(subparsers):
    parser = subparsers.add_parser("douyin", help="publish to Douyin (抖音)")
    from .distribute import add_common_args
    add_common_args(parser)
    parser.set_defaults(func=publish_douyin)