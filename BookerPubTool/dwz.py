# -*- coding: utf-8 -*-
"""新浪短网址（t.cn）生成子命令

调用新浪微博开放平台短网址接口，把长网址缩短为 http://t.cn/xxxx 形式。

接口文档: http://open.weibo.com/wiki/Short_url/shorten
    https://api.weibo.com/2/short_url/shorten.json
    参数: source (appkey), access_token, url_long（单次最多 20 个）

注意: 需先在微博开放平台注册应用并获取 access_token，未授权时接口返回 403。
      access_token 可通过 --access-token 传入，或设置环境变量 WEIBO_ACCESS_TOKEN；
      source (appkey) 可通过 --source 传入，或设置环境变量 WEIBO_SOURCE。
"""

import os
import requests
from .util import request_retry

SHORTEN_URL = 'https://api.weibo.com/2/short_url/shorten.json'

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')


def get_access_token(args):
    """优先 CLI 参数，其次环境变量 WEIBO_ACCESS_TOKEN。"""
    return getattr(args, 'access_token', '') or os.environ.get('WEIBO_ACCESS_TOKEN', '')


def get_source(args):
    """优先 CLI 参数，其次环境变量 WEIBO_SOURCE。"""
    return getattr(args, 'source', '') or os.environ.get('WEIBO_SOURCE', '')


def shorten_one(sess, source, access_token, url_long, retry=3):
    """对单条长网址申请短网址。

    返回 (短网址|None, 错误信息|None)。
    """
    params = {
        'source': source,
        'access_token': access_token,
        'url_long': url_long,
    }
    try:
        r = request_retry('GET', SHORTEN_URL, params=params, timeout=30, retry=retry)
        data = r.json()
    except Exception as ex:
        return None, '请求异常: %s' % ex

    # 成功返回列表: [{"url_short": "http://t.cn/...", "url_long": "...", "type": 0}]
    if isinstance(data, list) and data:
        item = data[0]
        short = item.get('url_short') or item.get('url_short')
        if short:
            return short, None
        return None, '接口返回: %s' % data

    # 失败返回错误对象: {"error_code": 21321, "error": "..."}
    if isinstance(data, dict):
        return None, '错误 %s: %s' % (
            data.get('error_code'), data.get('error') or data)

    return None, '未知返回: %s' % data


def dwz(args):
    source = get_source(args)
    access_token = get_access_token(args)
    if not access_token:
        print('错误: 未提供微博 access_token。')
        print('      请用 --access-token 传入，或设置环境变量 WEIBO_ACCESS_TOKEN。')
        print('      需先在微博开放平台注册应用并获取 access_token：')
        print('      https://open.weibo.com/')
        return 1

    sess = requests.Session()
    sess.headers.update({'User-Agent': UA})

    for url in args.urls:
        short, err = shorten_one(sess, source, access_token, url, retry=args.retry)
        if short:
            print('%s -> %s' % (url, short))
        else:
            print('%s => 失败: %s' % (url, err))
    return 0


def reg_subparser(subparsers):
    parser = subparsers.add_parser("dwz", help="新浪短网址(t.cn)生成")
    parser.add_argument("urls", nargs='+', help="要缩短的长网址（可传多个）")
    parser.add_argument(
        "-a", "--access-token", default='',
        help="微博开放平台 access_token；默认取环境变量 WEIBO_ACCESS_TOKEN")
    parser.add_argument(
        "-s", "--source", default='',
        help="应用 appkey (source)；默认取环境变量 WEIBO_SOURCE")
    parser.add_argument(
        "-r", "--retry", type=int, default=3, help="请求重试次数 (默认 3)")
    parser.set_defaults(func=dwz)
