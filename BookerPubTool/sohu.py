# -*- coding: utf-8 -*-
"""搜狐号文章发布（requests 版，结构参照 csdn.py / toutiao.py）

接口通过浏览器访问
https://mp.sohu.com/mpfe/v4/contentManagement/news/addarticle?contentStatus=1

抓包整理（逆向自搜狐号编辑器前端 bundle）：
  * 登录态：浏览器 cookie 中的 .sohu.com 会话（browser_cookie3 直读），
    需要 mpToken、mp-cv 等字段。
  * 签名头部 sp-cm：等于 mp-cv cookie 的值，通过
    window.ClientSignIns.tools.spcm.setHeader() 注入。
  * 发布文章:
      POST https://mp.sohu.com/mpfe/v4/contentManagement/news/addarticle?contentStatus=1
      body 为 JSON，包含 title / content 等字段。
      需要请求头：mpToken（cookie 中的 mpToken）、sp-cm（= mp-cv cookie 值）。

依赖: requests browser_cookie3 markdown
"""
import re
import os
import sys
import time
import json
import traceback
from os import path

import requests
import markdown as md_lib

from .ext_cookie import extract_cookies_multi_browsers
from .util import get_md_title, cookie_str_to_dict, cookie_dict_to_str, parse_md

API_BASE = 'https://mp.sohu.com/mpfe'
ADD_ARTICLE_URL = API_BASE + '/v4/contentManagement/news/addarticle?contentStatus=1'

EDITOR_REF = 'https://mp.sohu.com/mpfe/v4/article/edit'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')


# ---------------------------------------------------------------------------
# 会话 / 登录态
# ---------------------------------------------------------------------------

def get_cookies(args):
    """Cookie 来源：显式指定 > 浏览器提取。"""
    if args.cookie:
        return cookie_str_to_dict(args.cookie)
    cookies = extract_cookies_multi_browsers('sohu.com')
    print('从浏览器提取到 %d 个 sohu.com cookie' % len(cookies))
    return cookies


def make_session(args):
    cookies = get_cookies(args)
    if not cookies:
        raise SystemExit(
            '未获取到搜狐号 cookie，请先在浏览器登录 https://mp.sohu.com/mpfe/v4/article/edit'
            ' 并选择搜狐号账号')

    mp_token = cookies.get('mpToken', '')
    mp_cv = cookies.get('mp-cv', '')

    if not mp_token:
        print('警告: cookie 中缺少 mpToken，发布可能失败。'
              '请在浏览器编辑器页面选择搜狐号账号后重新导出 cookie')

    sess = requests.Session()
    sess.headers.update({
        'User-Agent': UA,
        'Cookie': cookie_dict_to_str(cookies),
        'Referer': EDITOR_REF,
        'Origin': 'https://mp.sohu.com',
        'Accept': 'application/json, text/plain, */*',
        'Content-Type': 'application/json',
    })
    if mp_token:
        sess.headers['mpToken'] = mp_token
    if mp_cv:
        sess.headers['mp-cv'] = mp_cv
        # sp-cm 签名头部等于 mp-cv cookie 值（逆向自 ClientSignIns.tools.spcm.setHeader）
        sess.headers['sp-cm'] = mp_cv

    return sess


# ---------------------------------------------------------------------------
# Markdown -> 待发布内容
# ---------------------------------------------------------------------------

def md_to_html(md):
    """将 Markdown 正文转为 HTML。"""
    return md_lib.markdown(md, extensions=['extra', 'sane_lists'])


# ---------------------------------------------------------------------------
# 发布
# ---------------------------------------------------------------------------

def publish_article(sess, title, content, status=1, retry=5):
    """发布文章到搜狐号。

    status: 1=发布, 2=草稿（根据 contentStatus 参数，见接口查询参数）
    返回 (code, data/msg)。
    """
    body = {
        'title': title,
        'content': content,
        # 其余字段根据实际接口要求补充，如：author, source, category, tags, cover 等
    }
    last = None
    for i in range(retry):
        try:
            r = sess.post(ADD_ARTICLE_URL, json=body, timeout=60)
            res = r.json()
            # 搜狐号接口返回约定：code 为 0 或 200 表示成功
            code = res.get('code', res.get('status', -1))
            if code in (0, 200):
                return code, res.get('data', res)
            last = res
            print(f'发布失败 retry {i}: {res.get("message") or res.get("msg") or res}')
        except Exception as ex:
            last = ex
            print(f'发布异常 retry {i}: {ex}')
        time.sleep(2 + i * 2)
    raise SystemError(f'发布失败: {last}')


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def publish_sohu(args):
    sess = make_session(args)

    if path.isfile(args.fname):
        fnames = [args.fname]
    else:
        fnames = [path.join(args.fname, f) for f in os.listdir(args.fname)]
    fnames = [f for f in fnames if f.endswith('.md')]
    if not fnames:
        print('请提供 MD 文件或目录')
        return

    for f in fnames[:args.num]:
        try:
            post_one(sess, f, args)
        except KeyboardInterrupt:
            raise
        except SystemExit:
            raise
        except Exception:
            traceback.print_exc()


def post_one(sess, f, args):
    print(f)
    md = open(f, encoding='utf8').read()
    title, body = parse_md(md, f)

    # 正文转 HTML（搜狐号编辑器期望 HTML 内容）
    content = md_to_html(body)

    action = '存草稿' if args.draft else '发布'
    print(f'{action}: {title}')
    try:
        code, data = publish_article(
            sess, title[:100], content,
            status=2 if args.draft else 1,
            retry=args.retry,
        )
        print('成功:', code, json.dumps(data, ensure_ascii=False)[:500])
    except SystemError as e:
        print('失败:', e)
        return
    if not args.draft:
        os.remove(f)


def reg_subparser(subparsers):
    parser = subparsers.add_parser("sohu", help="搜狐号文章发布")
    parser.add_argument("fname", help="MD 文件或目录")
    parser.add_argument(
        "-c", "--cookie", default='',
        help="cookie 字符串 (name=v; ...)；默认从 Firefox/Chrome/Edge 提取")
    parser.add_argument(
        "-d", "--draft", action='store_true', help="存草稿而不发布")
    parser.add_argument(
        "-r", "--retry", type=int, default=5, help="发布重试次数 (默认 5)")
    parser.add_argument(
        "-n", "--num", type=int, default=20, help="一次连续发布文章数")
    parser.set_defaults(func=publish_sohu)
