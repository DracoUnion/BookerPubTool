"""xhs-art — 发布 MD 文章到小红书（纯文本笔记）。

迁移自 BookerMediaTool；cookie 改为 BookerPubTool 惯例
（ext_cookie 从浏览器提取 + -c 显式 cookie 字符串）。
"""

from __future__ import annotations

import logging
import os
import re
from os import path

from .util import cookie_str_to_dict
from .ext_cookie import extract_cookies_multi_browsers
from .xhs_api import publish_text_note, NoCookieError, XhsApiError

logger = logging.getLogger(__name__)

NL = chr(10)

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


def _strip_md(md):
    """从 MD 提取标题（首个 H1/H2）和正文。"""
    lines = md.splitlines()
    title = ""
    body_parts = []
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if s.startswith("# ") and not title:
            title = s[2:].strip()
        elif s.startswith("## "):
            if not title:
                title = s[3:].strip()
            continue
        elif s.startswith("# "):
            continue
        # 去掉加粗/斜体标记
        s = s.replace("**", "").replace("__", "")
        # 去掉 Markdown 链接 [text](url) -> text
        s = re.sub(r"\[([^\]]+)\]\([^)]*\)", "", s)
        # 去掉表格行
        if s.count("|") >= 2:
            continue
        body_parts.append(s)
    body = NL.join(body_parts).strip()
    return title, body


def xhs_art_handle(args):
    fpath = args.article
    if not os.path.isfile(fpath):
        print(f"文章文件不存在: {fpath}")
        return
    md = open(fpath, encoding="utf-8").read()
    if not md.strip():
        print("文章内容为空")
        return

    default_title, body = _strip_md(md)
    title = args.title or default_title or path.splitext(path.basename(fpath))[0]
    desc = args.desc or body
    logger.info("发布文章笔记: title=%r, 正文长度=%d", title, len(desc))

    try:
        result = publish_text_note(title=title, desc=desc, cookies=get_cookies(args.cookie))
        print(f"✓ 发布成功: {result}")
    except NoCookieError as exc:
        print(f"✗ {exc}")
    except XhsApiError as exc:
        print(f"✗ 发布失败: {exc}")


def reg_subparser(subparsers):
    p = subparsers.add_parser("xhs-art", help="发布 MD 文章到小红书")
    p.add_argument("article", help="文章 Markdown 文件路径")
    p.add_argument("-tt", "--title", help="笔记标题（默认取 MD 首个标题）")
    p.add_argument("-d", "--desc", help="笔记正文（默认取 MD 正文）")
    p.add_argument("-c", "--cookie", default="", help="cookie 字符串 (name=v; ...)；默认 browser_cookie3 从浏览器提取")
    p.set_defaults(func=xhs_art_handle)
    return p
