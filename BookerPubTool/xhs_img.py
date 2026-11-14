"""xhs-img — 发布图片系列到小红书。

迁移自 BookerMediaTool；cookie 改为 BookerPubTool 惯例
（ext_cookie 从浏览器提取 + -c 显式 cookie 字符串）。
"""

from __future__ import annotations

import logging
import os
from os import path

from .util import cookie_str_to_dict
from .ext_cookie import extract_cookies_multi_browsers
from .xhs_api import publish_image_note, NoCookieError, XhsApiError

logger = logging.getLogger(__name__)

IMG_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}

REQUIRED_COOKIES = {"a1", "web_session"}


def get_cookies(cookie: str = "") -> dict:
    """cookie 来源：显式字符串 > 默认 browser_cookie3 提取。"""
    if cookie:
        cookies = cookie_str_to_dict(cookie)
    else:
        cookies = extract_cookies_multi_browsers("xiaohongshu.com")
        print(f"提取到 {len(cookies)} 个 cookie")
    missing = REQUIRED_COOKIES - cookies.keys()
    if missing:
        raise SystemError(f"cookie 缺少必需字段: {', '.join(sorted(missing))}")
    return cookies


def _validate_images(paths: list[str]) -> list[str]:
    valid = []
    for p in paths:
        if not os.path.isfile(p):
            raise FileNotFoundError(f"图片文件不存在: {p}")
        if os.path.splitext(p)[1].lower() not in IMG_EXTS:
            logger.warning("未知图片格式: %s", p)
        valid.append(p)
    return valid


def xhs_img_handle(args):
    images = _validate_images(list(args.images))
    if not images:
        print("未提供任何图片")
        return

    # 标题：默认取第一张图片文件名（无扩展名），可被 -t 覆盖
    default_title = path.splitext(path.basename(images[0]))[0]
    title = args.title or default_title
    desc = args.desc or ""

    logger.info("发布图片笔记: title=%r, %d 张图片", title, len(images))

    try:
        result = publish_image_note(title=title, desc=desc, paths=images, cookies=get_cookies(args.cookie))
        print(f"✓ 发布成功: {result}")
    except NoCookieError as exc:
        print(f"✗ {exc}")
    except XhsApiError as exc:
        print(f"✗ 发布失败: {exc}")


def reg_subparser(subparsers):
    p = subparsers.add_parser("xhs-img", help="发布图片系列到小红书")
    p.add_argument("images", nargs="+", help="图片文件路径（按顺序）")
    p.add_argument("-tt", "--title", help="笔记标题（默认取第一张图片文件名）")
    p.add_argument("-d", "--desc", default="", help="笔记正文（默认空）")
    p.add_argument("-c", "--cookie", default="", help="cookie 字符串 (name=v; ...)；默认 browser_cookie3 从浏览器提取")
    p.set_defaults(func=xhs_img_handle)
    return p
