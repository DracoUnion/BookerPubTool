"""xhs-vid — 发布视频到小红书。

迁移自 BookerMediaTool；cookie 改为 BookerPubTool 惯例
（ext_cookie 从浏览器提取 + -c 显式 cookie 字符串）。
"""

from __future__ import annotations

import logging
import os
from os import path

from .util import cookie_str_to_dict
from .ext_cookie import extract_cookies_multi_browsers
from .xhs_api import publish_video_note, NoCookieError, XhsApiError

logger = logging.getLogger(__name__)

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


def xhs_vid_handle(args):
    video = args.video
    if not os.path.isfile(video):
        print(f"视频文件不存在: {video}")
        return

    # 标题：默认取文件名（无扩展名），可被 -t 覆盖
    default_title = path.splitext(path.basename(video))[0]
    title = args.title or default_title
    desc = args.desc or ""

    cover = getattr(args, "cover", None)
    logger.info("发布视频笔记: title=%r, video=%s", title, video)

    try:
        result = publish_video_note(
            title=title, desc=desc, vid_path=video, cover_path=cover,
            cookies=get_cookies(args.cookie),
        )
        print(f"✓ 发布成功: {result}")
    except NoCookieError as exc:
        print(f"✗ {exc}")
    except XhsApiError as exc:
        print(f"✗ 发布失败: {exc}")


def reg_subparser(subparsers):
    p = subparsers.add_parser("xhs-vid", help="发布视频到小红书")
    p.add_argument("video", help="视频文件路径")
    p.add_argument("-tt", "--title", help="笔记标题（默认取视频文件名）")
    p.add_argument("-d", "--desc", default="", help="笔记正文（默认空）")
    p.add_argument("-c", "--cover", help="封面图路径（可选）")
    p.add_argument("-ck", "--cookie", default="", help="cookie 字符串 (name=v; ...)；默认 browser_cookie3 从浏览器提取")
    p.set_defaults(func=xhs_vid_handle)
    return p
