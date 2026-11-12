# -*- coding: utf-8 -*-
"""掘金文章发布（requests 版，结构参照 csdn.py）

接口逆向自掘金编辑器 https://juejin.cn/editor/drafts/new?v=2 抓包：

  * 分类列表: GET  https://api.juejin.cn/tag_api/v1/query_category_briefs?aid=2608
  * 标签搜索: POST https://api.juejin.cn/tag_api/v1/query_tag_list?aid=2608
              body: {"key_word": "...", "cursor": "0", "sort_type": 0}
  * 创建草稿: POST https://api.juejin.cn/content_api/v1/article_draft/create?aid=2608
              返回 data.id（草稿 id）
  * 发布文章: POST https://api.juejin.cn/content_api/v1/article/publish?aid=2608
              body 含 draft_id / category_id / tag_ids([标签的数字 id 字符串]) / mark_content ...

  注意: tag_ids 必须传**字符串数组**，且元素是标签的 `id`（如 AI编程 = "11991910"），
        不是 `tag_id`（如 "7467857238494019610"），否则服务端报"至少添加一个标签"。

依赖: requests browser_cookie3
"""
import os
import re
import time
import json
import traceback
from os import path

import requests

from .ext_cookie import extract_cookies_multi_browsers
from .util import cookie_str_to_dict, cookie_dict_to_str, parse_md

API_HOST = 'https://api.juejin.cn'
AID = '2608'
CATEGORY_URL = API_HOST + '/tag_api/v1/query_category_briefs'
TAG_URL = API_HOST + '/tag_api/v1/query_tag_list'
DRAFT_CREATE_URL = API_HOST + '/content_api/v1/article_draft/create'
PUBLISH_URL = API_HOST + '/content_api/v1/article/publish'

EDITOR_REF = 'https://juejin.cn/'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')

DEFAULT_CATEGORY = '代码人生'
DEFAULT_TAG = 'AI编程'


# ---------------------------------------------------------------------------
# 会话 / 登录态
# ---------------------------------------------------------------------------

def get_cookies(args):
    """Cookie 来源：显式指定 > 浏览器提取。"""
    if args.cookie:
        return cookie_str_to_dict(args.cookie)
    cookies = extract_cookies_multi_browsers('juejin.cn')
    print('从浏览器提取到 %d 个 juejin.cn cookie' % len(cookies))
    return cookies


def make_session(args):
    cookies = get_cookies(args)
    if not cookies:
        raise SystemExit('未获取到掘金 cookie，请先在浏览器登录 https://juejin.cn/')

    sess = requests.Session()
    sess.headers.update({
        'User-Agent': UA,
        'Cookie': cookie_dict_to_str(cookies),
        'Referer': EDITOR_REF,
        'Origin': 'https://juejin.cn',
        'Accept': 'application/json, text/plain, */*',
        'Content-Type': 'application/json',
    })
    return sess


# ---------------------------------------------------------------------------
# 分类 / 标签
# ---------------------------------------------------------------------------

def get_category_id(sess, name, aid=AID):
    """根据分类名取 category_id；找不到返回 None。"""
    r = sess.get(CATEGORY_URL, params={'aid': aid}, timeout=30)
    data = r.json().get('data') or []
    for c in data:
        if c.get('category_name') == name:
            return c.get('category_id')
    return None


def search_tag_id(sess, key_word, aid=AID):
    """搜索标签，返回标签的数字 id 字符串（tag_ids 用）；找不到返回 None。"""
    body = {'key_word': key_word, 'cursor': '0', 'sort_type': 0}
    r = sess.post(TAG_URL, params={'aid': aid}, data=json.dumps(body), timeout=30)
    data = r.json().get('data') or []
    exact = None
    first = None
    for item in data:
        tag = item.get('tag') or {}
        tid = tag.get('id')
        if tid is None:
            continue
        if first is None:
            first = str(tid)
        if tag.get('tag_name') == key_word:
            exact = str(tid)
            break
    return exact or first


# ---------------------------------------------------------------------------
# Markdown / 摘要
# ---------------------------------------------------------------------------

def md_to_brief(md, limit=100):
    """从 Markdown 粗提取纯文本摘要（去标题/链接/图片语法）。"""
    text = re.sub(r'!\[[^\]]*\]\([^\)]*\)', '', md)      # 图片
    text = re.sub(r'\[([^\]]*)\]\([^\)]*\)', r'\1', text)  # 链接保留文字
    text = re.sub(r'[#>*`~\-]+', ' ', text)               # markdown 符号
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:limit]


# ---------------------------------------------------------------------------
# 草稿 / 发布
# ---------------------------------------------------------------------------

def build_draft_body(title, brief, mark_content, category_id, tag_id):
    return {
        'category_id': category_id,
        'tag_ids': [tag_id] if tag_id else [],
        'link_url': '',
        'cover_image': '',
        'title': title,
        'brief_content': brief,
        'edit_type': 10,
        'html_content': 'deprecated',
        'mark_content': mark_content,
        'theme_ids': [],
        'pics': [],
    }


def create_draft(sess, title, brief, mark_content, category_id, tag_id, retry=3):
    body = build_draft_body(title, brief, mark_content, category_id, tag_id)
    last = None
    for i in range(retry):
        try:
            r = sess.post(DRAFT_CREATE_URL, params={'aid': AID},
                          data=json.dumps(body), timeout=30)
            res = r.json()
            if res.get('err_no') == 0:
                return (res.get('data') or {}).get('id')
            last = res
            print('建草稿失败 retry %d: %s' % (i, res.get('err_msg') or res))
        except Exception as ex:
            last = ex
            print('建草稿异常 retry %d: %s' % (i, ex))
        time.sleep(2 + i * 2)
    raise SystemError('建草稿失败: %s' % last)


def publish_article(sess, draft_id, title, brief, mark_content,
                    category_id, tag_id, retry=3):
    body = build_draft_body(title, brief, mark_content, category_id, tag_id)
    body.update({
        'id': draft_id,
        'draft_id': draft_id,
        'column_ids': [],
        'sync_to_org': False,
    })
    last = None
    for i in range(retry):
        try:
            r = sess.post(PUBLISH_URL, params={'aid': AID},
                          data=json.dumps(body), timeout=30)
            res = r.json()
            if res.get('err_no') == 0:
                return res.get('data') or {}
            last = res
            print('发布失败 retry %d: %s' % (i, res.get('err_msg') or res))
        except Exception as ex:
            last = ex
            print('发布异常 retry %d: %s' % (i, ex))
        time.sleep(2 + i * 2)
    raise SystemError('发布失败: %s' % last)


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def publish_juejin(args):
    sess = make_session(args)

    category_id = get_category_id(sess, args.cate)
    if not category_id:
        raise SystemExit('未找到分类: %s' % args.cate)
    tag_id = search_tag_id(sess, args.tag)
    if not tag_id:
        raise SystemExit('未找到标签: %s' % args.tag)
    print('分类: %s (%s)  标签: %s (%s)' % (args.cate, category_id, args.tag, tag_id))

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
            post_one(sess, f, args, category_id, tag_id)
        except KeyboardInterrupt:
            raise
        except SystemExit:
            raise
        except Exception:
            traceback.print_exc()


def post_one(sess, f, args, category_id, tag_id):
    print(f)
    md = open(f, encoding='utf8').read()
    title, body = parse_md(md, f)
    title = title.strip()[:100]
    brief = md_to_brief(body)
    mark_content = body

    draft_id = create_draft(sess, title, brief, mark_content, category_id, tag_id)
    print('草稿 id:', draft_id)

    if args.draft:
        print('已存草稿:', title)
        return

    data = publish_article(sess, draft_id, title, brief, mark_content,
                           category_id, tag_id)
    aid = data.get('article_id') or data.get('id') or ''
    url = 'https://juejin.cn/post/%s' % aid if aid else ''
    print('发布成功: article_id:', aid, url)
    os.remove(f)


def reg_subparser(subparsers):
    parser = subparsers.add_parser("juejin", help="掘金文章发布")
    parser.add_argument("fname", help="MD 文件或目录")
    parser.add_argument(
        "-c", "--cookie", default='',
        help="cookie 字符串 (name=v; ...)；默认从 Firefox/Chrome/Edge 提取")
    parser.add_argument(
        "-ct", "--cate", default=DEFAULT_CATEGORY,
        help="分类名 (默认: %s)" % DEFAULT_CATEGORY)
    parser.add_argument(
        "-tg", "--tag", default=DEFAULT_TAG,
        help="标签名 (默认: %s)" % DEFAULT_TAG)
    parser.add_argument(
        "-d", "--draft", action='store_true', help="只存草稿而不发布")
    parser.add_argument(
        "-r", "--retry", type=int, default=3, help="重试次数 (默认 3)")
    parser.add_argument(
        "-n", "--num", type=int, default=20, help="一次连续发布文章数")
    parser.set_defaults(func=publish_juejin)
