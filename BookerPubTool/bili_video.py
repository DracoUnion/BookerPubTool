# -*- coding: utf-8 -*-

"""bili-video — 通过 B 站创作中心接口发布视频（requests 版，结构参照 toutiao.py）。

接口通过浏览器访问
https://member.bilibili.com/platform/upload/video/frame
抓包整理：
  * 登录态：浏览器 cookie 中的 .bilibili.com 会话（browser_cookie3 直读），
    其中 bili_jct 用作 csrf token。
  * 预上传:  GET https://member.bilibili.com/preupload
             返回 auth / endpoint / upos_uri / biz_id / chunk_size。
  * 分片上传: POST {endpoint}/{upos_uri}?uploads&output=json   取 upload_id
              PUT  {endpoint}/{upos_uri}?partNumber=...&uploadId=...   传分片
              POST {endpoint}/{upos_uri}?output=json&...              结束上传
  * 推荐分区: POST https://member.bilibili.com/x/vupre/web/archive/types/predict
  * 推荐标签: GET  https://member.bilibili.com/x/vupre/web/tag/recommend
  * 提交稿件: POST https://member.bilibili.com/x/vu/web/add/v3

依赖: requests browser_cookie3
"""

import os
import time
import traceback
from os import path

import requests

from .util import timestr, cookie_str_to_dict, cookie_dict_to_str
from .ext_cookie import extract_cookies_multi_browsers

PREUPLOAD_URL = 'https://member.bilibili.com/preupload'
PREDICT_TYPES_URL = 'https://member.bilibili.com/x/vupre/web/archive/types/predict'
RECOMMEND_TAGS_URL = 'https://member.bilibili.com/x/vupre/web/tag/recommend'
ADD_URL = 'https://member.bilibili.com/x/vu/web/add/v3'
NAV_URL = 'https://api.bilibili.com/x/web-interface/nav'

EDITOR_REF = 'https://member.bilibili.com/platform/upload/video/frame'
UPLOAD_PROFILE = 'ugcupos/bup'
DEFAULT_CHUNK_SIZE = 10 * 1024 * 1024
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')

# 从命令行/目录中识别视频文件时使用的后缀
VIDEO_EXTS = ('.mp4', '.mkv', '.flv', '.avi', '.mov', '.webm', '.m4v', '.ts')


# ---------------------------------------------------------------------------
# 会话 / 登录态
# ---------------------------------------------------------------------------

def get_cookies(args):
    """Cookie 来源：显式指定 > 浏览器提取。"""
    if args.cookie:
        return cookie_str_to_dict(args.cookie)
    cookies = extract_cookies_multi_browsers('bilibili.com')
    print(f'{timestr()} 从浏览器提取到 {len(cookies)} 个 bilibili.com cookie')
    return cookies


def make_session(args):
    cookies = get_cookies(args)
    if not cookies:
        raise SystemExit('未获取到 B 站 cookie，请先在浏览器登录 bilibili.com')
    if not cookies.get('bili_jct'):
        raise SystemExit('cookie 中缺少 bili_jct（csrf token），请重新登录 B 站')

    sess = requests.Session()
    sess.headers.update({
        'User-Agent': UA,
        'Cookie': cookie_dict_to_str(cookies),
        'Referer': EDITOR_REF,
        'Origin': 'https://member.bilibili.com',
        'Accept': 'application/json, text/plain, */*',
    })
    sess.csrf = cookies['bili_jct']
    try:
        data = sess.get(NAV_URL, timeout=30).json()
        if data.get('code') != 0 or not data.get('data', {}).get('isLogin'):
            raise SystemExit('B 站登录态失效，请重新登录')
        print(f'{timestr()} 登录用户: {data["data"].get("uname", "")}')
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
    return sess


def get_csrf(sess):
    """取 bili_jct，用作 csrf token。"""
    return getattr(sess, 'csrf', '') or sess.cookies.get('bili_jct', '')


# ---------------------------------------------------------------------------
# 视频上传（UPOS）
# ---------------------------------------------------------------------------

def now_ms():
    return int(time.time() * 1000)


def _json_or_raise(resp, what):
    try:
        return resp.json()
    except ValueError:
        raise SystemError(
            f'{what} 返回非 JSON（登录态可能失效）: {resp.text[:200]}')


def preupload(sess, fname, size):
    """获取上传元数据。"""
    params = {
        'name': path.basename(fname),
        'size': size,
        'r': 'upos',
        'profile': UPLOAD_PROFILE,
        'ssl': 0,
        'version': '2.14.0',
        'build': 2140000,
    }
    data = _json_or_raise(sess.get(PREUPLOAD_URL, params=params, timeout=60),
                          '预上传')
    if data.get('OK') != 1 or not data.get('endpoint') or not data.get('upos_uri'):
        raise SystemError(f'预上传失败: {data}')
    return data


def _upos_url(bucket):
    path_ = bucket['upos_uri'].replace('upos://', '', 1).lstrip('/')
    return 'https:' + bucket['endpoint'].rstrip('/') + '/' + path_


def _upos_post(url, params, auth, **kw):
    """带重试的 UPOS 请求。"""
    last = None
    for i in range(5):
        try:
            resp = requests.post(url, params=params,
                                 headers={'X-Upos-Auth': auth}, **kw)
            resp.raise_for_status()
            return resp
        except Exception as ex:
            last = ex
            print(f'{timestr()} UPOS 请求失败 retry {i}: {ex}')
            time.sleep(1 + i * 2)
    raise SystemError(f'UPOS 请求失败: {last}')


def init_upload(bucket):
    url = _upos_url(bucket)
    data = _json_or_raise(_upos_post(
        url, {'uploads': '', 'output': 'json'}, bucket['auth'], timeout=60),
        '初始化上传')
    upload_id = data.get('upload_id')
    if not upload_id:
        raise SystemError(f'初始化上传失败: {data}')
    return url, upload_id


def upload_chunks(url, bucket, fname, upload_id, chunk_size):
    """按分块顺序上传视频，返回分块数。"""
    auth = bucket['auth']
    size = path.getsize(fname)
    chunk_size = chunk_size or DEFAULT_CHUNK_SIZE
    chunks = (size + chunk_size - 1) // chunk_size
    print(f'{timestr()} 开始上传 {path.basename(fname)}：'
          f'{size / 1024 / 1024:.1f} MB，{chunks} 块')

    with open(fname, 'rb') as f:
        for i in range(chunks):
            chunk = f.read(chunk_size)
            params = {
                'partNumber': i + 1,
                'uploadId': upload_id,
                'chunk': i,
                'chunks': chunks,
                'size': len(chunk),
                'start': i * chunk_size,
                'end': i * chunk_size + len(chunk),
                'total': size,
            }
            last = None
            for retry in range(5):
                try:
                    r = requests.put(
                        url, params=params,
                        headers={'X-Upos-Auth': auth,
                                 'Content-Type': 'application/octet-stream'},
                        data=chunk, timeout=240)
                    r.raise_for_status()
                    last = None
                    break
                except Exception as ex:
                    last = ex
                    print(f'{timestr()} 分块 {i + 1}/{chunks} 失败 retry '
                          f'{retry}: {ex}')
                    time.sleep(1 + retry * 2)
            if last is not None:
                raise SystemError(f'分块 {i + 1}/{chunks} 上传失败: {last}')
            print(f'{timestr()} 分块 {i + 1}/{chunks} 完成')
    return chunks


def finish_upload(url, bucket, fname, upload_id, chunks):
    params = {
        'output': 'json',
        'name': path.basename(fname),
        'profile': UPLOAD_PROFILE,
        'uploadId': upload_id,
        'biz_id': bucket['biz_id'],
    }
    body = {'parts': [{'partNumber': i + 1, 'eTag': 'etag'}
                      for i in range(chunks)]}
    data = _json_or_raise(_upos_post(
        url, params, bucket['auth'], json=body, timeout=60), '结束上传')
    if data.get('OK') != 1:
        raise SystemError(f'结束上传失败: {data}')
    return data


def upload_video(sess, fname):
    """上传视频文件，返回提交稿件所需的 filename / biz_id。"""
    bucket = preupload(sess, fname, path.getsize(fname))
    url, upload_id = init_upload(bucket)
    chunk_size = bucket.get('chunk_size') or DEFAULT_CHUNK_SIZE
    chunks = upload_chunks(url, bucket, fname, upload_id, chunk_size)
    finish_upload(url, bucket, fname, upload_id, chunks)

    key = bucket['upos_uri'].split('/')[-1]
    return {
        'filename': path.splitext(key)[0],
        'biz_id': bucket['biz_id'],
    }


# ---------------------------------------------------------------------------
# 推荐分区 / 标签
# ---------------------------------------------------------------------------

def predict_types(sess, csrf, filename, title):
    """预测稿件类型，返回推荐分区列表（第一个为最推荐）。"""
    resp = sess.post(
        PREDICT_TYPES_URL,
        params={'ts': now_ms(), 'csrf': csrf},
        files={'filename': (None, filename), 'title': (None, title)},
        timeout=30)
    data = _json_or_raise(resp, '预测分区')
    if data.get('code') != 0:
        print(f'{timestr()} 预测分区失败: {data.get("message")}')
        return []
    return data.get('data') or []


def recommend_tags(sess, subtype_id, title, filename, desc):
    """获取推荐标签。"""
    resp = sess.get(RECOMMEND_TAGS_URL, params={
        'upload_id': '',
        'subtype_id': subtype_id,
        'title': title,
        'filename': filename,
        'description': desc,
        't': now_ms(),
    }, timeout=30)
    data = _json_or_raise(resp, '推荐标签')
    if data.get('code') != 0:
        print(f'{timestr()} 推荐标签失败: {data.get("message")}')
        return []
    return [item.get('tag', '') for item in data.get('data') or []
            if item.get('tag')]


# ---------------------------------------------------------------------------
# 提交稿件
# ---------------------------------------------------------------------------

def submit_video(sess, csrf, video, title, desc, tid, tags):
    payload = {
        'videos': [{
            'filename': video['filename'],
            'title': title,
            'desc': '',
        }],
        'cover': '',
        'cover43': '',
        'title': title,
        'copyright': 1,
        'tid': tid,
        'tag': ','.join(tags[:10]),
        'desc_format_id': 9999,
        'desc': desc,
        'recreate': -1,
        'dynamic': '',
        'interactive': 0,
        'act_reserve_create': 0,
        'no_disturbance': 0,
        'no_reprint': 1,
        'subtitle': {'open': 0, 'lan': ''},
        'dolby': 0,
        'lossless_music': 0,
        'up_selection_reply': False,
        'up_close_reply': False,
        'up_close_danmu': False,
        'web_os': 3,
        'csrf': csrf,
    }
    resp = sess.post(ADD_URL, params={'ts': now_ms(), 'csrf': csrf},
                     json=payload, timeout=60)
    data = _json_or_raise(resp, '提交稿件')
    if data.get('code') != 0:
        raise SystemError(
            f'提交稿件失败: {data.get("code")} {data.get("message")}')
    return data.get('data') or {}


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def collect_videos(inputs, num):
    fnames = []
    for item in inputs:
        if path.isfile(item):
            fnames.append(item)
        elif path.isdir(item):
            for f in sorted(os.listdir(item)):
                fp = path.join(item, f)
                if path.isfile(fp) and f.lower().endswith(VIDEO_EXTS):
                    fnames.append(fp)
        else:
            print(f'{timestr()} 路径不存在: {item}')
    return fnames[:num]


def default_title(fname):
    """标题默认取文件名（不含后缀）。"""
    return path.splitext(path.basename(fname))[0]


def truncate_title(title, limit=80):
    if len(title) <= limit:
        return title
    return title[:limit - 3] + '...'


def publish_bili_video(args):
    fnames = collect_videos(args.fname, args.num)
    if not fnames:
        print(f'{timestr()} 请提供视频文件或包含视频的目录')
        return

    if args.title and len(fnames) > 1:
        print(f'{timestr()} 多个视频时忽略 --title，标题取各自文件名')

    sess = make_session(args)
    csrf = get_csrf(sess)

    for idx, f in enumerate(fnames, 1):
        print(f'\n{timestr()} [{idx}/{len(fnames)}] {f}')
        try:
            publish_one(sess, csrf, f, args, len(fnames))
        except KeyboardInterrupt:
            raise
        except SystemExit:
            raise
        except Exception:
            traceback.print_exc()


def publish_one(sess, csrf, f, args, total):
    title = truncate_title(
        args.title if args.title and total == 1 else default_title(f))
    desc = args.desc or ''

    print(f'{timestr()} 上传视频...')
    video = upload_video(sess, f)

    # 分区：命令行指定 > 预测接口推荐的第一个
    types = [] if args.tid else predict_types(sess, csrf, video['filename'], title)
    tid = args.tid or (types[0].get('id') if types else 0) or 21
    type_name = ''
    if types and types[0].get('id') == tid:
        type_name = (f'{types[0].get("parent_name", "")} / '
                     f'{types[0].get("name", "")}')
    print(f'{timestr()} 分区: {tid} {type_name}'.rstrip())

    # 标签：命令行指定 > 推荐接口（最多 10 个）
    if args.tag:
        tags = [t.strip() for t in args.tag.split(',') if t.strip()]
    else:
        tags = recommend_tags(sess, tid, title, video['filename'], desc)
        tags = [t for t in tags if t not in ('',)]
    if not tags:
        tags = ['生活']
    print(f'{timestr()} 标签: {", ".join(tags[:10])}')

    if args.dry_run:
        print(f'{timestr()} --dry-run：已上传视频但未提交稿件')
        return

    print(f'{timestr()} 提交稿件: {title}')
    data = submit_video(sess, csrf, video, title, desc, tid, tags)
    bvid = data.get('bvid', '')
    aid = data.get('aid', '')
    url = f'https://www.bilibili.com/video/{bvid}' if bvid else ''
    print(f'{timestr()} 成功: aid={aid} bvid={bvid} {url}')


def reg_subparser(subparsers):
    parser = subparsers.add_parser("bili-video", help="发布视频到 B 站")
    parser.add_argument(
        "fname", nargs='+', help="视频文件或包含视频的目录（可多个）")
    parser.add_argument(
        "-t", "--title", default='',
        help="视频标题；默认取文件名（不含后缀），多个视频时忽略")
    parser.add_argument(
        "-d", "--desc", default='', help="视频简介")
    parser.add_argument(
        "-c", "--cookie", default='',
        help="cookie 字符串 (name=v; ...)；默认从 Firefox/Chrome/Edge 提取")
    parser.add_argument(
        "--tid", type=int, default=0,
        help="手动指定分区 ID；默认使用预测接口推荐的第一个分区")
    parser.add_argument(
        "--tag", default='',
        help="手动指定标签（逗号分隔）；默认使用推荐标签接口")
    parser.add_argument(
        "-n", "--num", type=int, default=20, help="一次最多发布视频数")
    parser.add_argument(
        "--dry-run", action='store_true',
        help="只上传视频并展示推荐分区/标签，不提交稿件")
    parser.set_defaults(func=publish_bili_video)
