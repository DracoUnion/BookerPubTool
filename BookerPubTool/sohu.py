# -*- coding: utf-8 -*-
"""搜狐号文章发布（requests 版，结构参照 csdn.py / toutiao.py）

接口与签名逆向自搜狐号编辑器微前端（mp_micro_contentmanager）：

  * 基础域名: https://mp.sohu.com
  * 发布文章: POST /mpbp/bp/news/v4/news/publish/v2?accountId=<id>
  * 保存草稿: POST /mpbp/bp/news/v4/news/draft/v2?accountId=<id>
  * 账号信息: GET  /mpbp/bp/account/info?accountId=<id>   （取 channelId）

  请求头:
    Content-Type: application/json
    X-Requested-With: XMLHttpRequest          （缺失会返回 code=1301 获取客户端失败）
    sp-cm: <mp-cv cookie 值>                  （前端 ClientSignIns.tools.setHeader 注入）
    Cookie: 浏览器 .sohu.com 会话（ppinf / mp-cv / mpCreatorId 等）

  accountId 从 cookie mpCreatorId（URL 编码的 JSON {"id":...,"status":...}）解析。
  成功返回: {"code":2000000,"data":<文章id>,"success":true}

依赖: requests browser_cookie3 markdown
"""
import os
import re
import json
import time
import traceback
import urllib.parse
from os import path

import requests
import markdown as md_lib

from .ext_cookie import extract_cookies_multi_browsers
from .util import cookie_str_to_dict, cookie_dict_to_str, parse_md

API_HOST = 'https://mp.sohu.com'
PUBLISH_URL = API_HOST + '/mpbp/bp/news/v4/news/publish/v2'
DRAFT_URL = API_HOST + '/mpbp/bp/news/v4/news/draft/v2'
ACCOUNT_INFO_URL = API_HOST + '/mpbp/bp/account/info'

EDITOR_REF = 'https://mp.sohu.com/mpfe/v4/contentManagement/news/addarticle?contentStatus=1'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')

TITLE_MAX = 72
OK_CODE = 2000000


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


def parse_account_id(cookies):
    """从 mpCreatorId cookie 解析 accountId。"""
    raw = cookies.get('mpCreatorId', '')
    if raw:
        try:
            return str(json.loads(urllib.parse.unquote(raw))['id'])
        except Exception:
            pass
    return ''


def make_session(args):
    cookies = get_cookies(args)
    if not cookies:
        raise SystemExit(
            '未获取到搜狐号 cookie，请先在浏览器登录 '
            'https://mp.sohu.com/mpfe/v4/contentManagement/news/addarticle?contentStatus=1')

    account_id = args.account_id or parse_account_id(cookies)
    if not account_id:
        raise SystemExit(
            'cookie 中缺少 mpCreatorId，无法确定 accountId；'
            '请登录搜狐号编辑器后重新导出 cookie，或用 -a 指定 accountId')

    mp_cv = cookies.get('mp-cv', '')
    if not mp_cv:
        print('警告: cookie 中缺少 mp-cv，sp-cm 签名头将为空，发布可能失败')

    sess = requests.Session()
    sess.headers.update({
        'User-Agent': UA,
        'Cookie': cookie_dict_to_str(cookies),
        'Referer': EDITOR_REF,
        'Origin': 'https://mp.sohu.com',
        'Accept': 'application/json, text/plain, */*',
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
    })
    if mp_cv:
        # sp-cm 签名头部等于 mp-cv cookie 值
        sess.headers['sp-cm'] = mp_cv

    sess.account_id = account_id
    sess.channel_id = None
    return sess


# ---------------------------------------------------------------------------
# 账号信息
# ---------------------------------------------------------------------------

def get_channel_id(sess, retry=3):
    """获取账号自身 channelId（发布时必填）。"""
    last = None
    for i in range(retry):
        try:
            r = sess.get(ACCOUNT_INFO_URL, params={'accountId': sess.account_id}, timeout=30)
            data = r.json().get('data') or {}
            cid = data.get('channelId')
            if cid:
                return cid
            last = data
        except Exception as ex:
            last = ex
        time.sleep(2)
    raise SystemError('获取账号 channelId 失败: %s' % last)


# ---------------------------------------------------------------------------
# Markdown -> 待发布 HTML
# ---------------------------------------------------------------------------

def md_to_html(md):
    """将 Markdown 正文转为 HTML（搜狐号编辑器使用富文本 HTML）。"""
    return md_lib.markdown(md, extensions=['extra', 'sane_lists'])


# ---------------------------------------------------------------------------
# 发布 / 草稿
# ---------------------------------------------------------------------------

def build_body(title, content, channel_id, account_id, brief=''):
    """按前端 baseParams 结构构造请求体。"""
    return {
        'title': title,
        'brief': brief,
        'content': content,
        'channelId': channel_id,
        'categoryId': -1,
        'id': 0,
        'userColumnId': 0,
        'columnNewsIds': [],
        'businessCode': 0,
        'declareOriginal': False,
        'cover': '',
        'topicIds': [],
        'isAd': 0,
        'userLabels': '[]',
        'reprint': False,
        'customTags': '',
        'creationStatement': None,
        'additionalStatement': None,
        'sourceUrl': '',
        'visibleToLoginedUsers': 0,
        'attrIds': [],
        'accountId': int(account_id),
    }


def submit_article(sess, title, content, draft=False, retry=5):
    """发布或存草稿，返回文章 id。"""
    if not sess.channel_id:
        sess.channel_id = get_channel_id(sess)
    body = build_body(title, content, sess.channel_id, sess.account_id)
    url = DRAFT_URL if draft else PUBLISH_URL

    last = None
    for i in range(retry):
        try:
            r = sess.post(url, params={'accountId': sess.account_id},
                          json=body, timeout=60)
            try:
                res = r.json()
            except ValueError:
                raise SystemError('返回非 JSON（登录态可能失效）: %s' % r.text[:200])
            if res.get('code') == OK_CODE:
                return res.get('data')
            last = res
            print('发布失败 retry %d: %s' % (i, res.get('msg') or res))
        except SystemError:
            raise
        except Exception as ex:
            last = ex
            print('发布异常 retry %d: %s' % (i, ex))
        time.sleep(2 + i * 2)
    raise SystemError('发布失败: %s' % last)


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
    title = title[:TITLE_MAX]

    content = md_to_html(body)

    action = '存草稿' if args.draft else '发布'
    print('%s: %s' % (action, title))
    try:
        aid = submit_article(sess, title, content, draft=args.draft, retry=args.retry)
        print('成功: 文章ID:', aid)
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
        "-a", "--account-id", dest="account_id", default='',
        help="搜狐号 accountId；默认从 cookie mpCreatorId 解析")
    parser.add_argument(
        "-d", "--draft", action='store_true', help="存草稿而不发布")
    parser.add_argument(
        "-r", "--retry", type=int, default=5, help="发布重试次数 (默认 5)")
    parser.add_argument(
        "-n", "--num", type=int, default=20, help="一次连续发布文章数")
    parser.set_defaults(func=publish_sohu)
