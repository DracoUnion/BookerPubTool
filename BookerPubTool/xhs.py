# -*- coding: utf-8 -*-
"""小红书笔记发布（requests API 版，替代 xhs_post_sele.py）

直接调用小红书创作平台 HTTP API 发布笔记，无需启动浏览器。
API 与签名算法参考 xhs-workbench 项目（D:/src/xhs-workbench/src/adapters/xhs/）：
  - 发布接口: POST https://edith.xiaohongshu.com/web_api/sns/v2/note
  - 主站签名: xhshow 库生成 x-s / x-s-common / x-t / x-b3-traceid / x-xray-traceid
  - Cookie 通过 browser_cookie3 从本机浏览器（Firefox/Chrome/Edge/Brave）提取
"""
import re
import os
import sys
import json
import time
import argparse
from os import path
import requests
import browser_cookie3

try:  # Windows 控制台 UTF-8 输出（含 argparse help）
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

# ─── 域名常量（与 workbench constants.py 一致） ─────────────────────────────
EDITH_HOST = "https://edith.xiaohongshu.com"
CREATOR_HOST = "https://creator.xiaohongshu.com"
HOME_URL = "https://www.xiaohongshu.com"
POST_NOTE_URL = EDITH_HOST + "/web_api/sns/v2/note"

CHROME_VERSION = "145"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    f"Chrome/{CHROME_VERSION}.0.0.0 Safari/537.36"
)
SDK_VERSION = "4.2.6"
APP_ID = "xhs-pc-web"
PLATFORM = "macOS"

# 签名所需 cookie；a1 必须（参与签名），web_session 为登录态
REQUIRED_COOKIES = {"a1", "web_session"}


# ─── Cookie 提取（browser_cookie3） ────────────────────────────────────────
def cookie_str_to_dict(cookie_str: str) -> dict:
    """把 "k=v; k2=v2" cookie 头字符串解析为字典。"""
    result = {}
    for item in cookie_str.split(";"):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            result[k.strip()] = v.strip()
    return result


def extract_browser_cookies() -> tuple[str, dict]:
    """从本机浏览器提取小红书 cookie（browser-cookie3，仅读取不启动页面）。

    优先在当前进程内读取；失败（SQLite 被占用/解密异常）时回退到子进程，
    避免浏览器运行时数据库锁冲突。返回 (browser_name, cookies) 或抛错。
    """
    browsers = [("Chrome", browser_cookie3.chrome),
                ("Firefox", browser_cookie3.firefox),
                ("Edge", browser_cookie3.edge),
                ("Brave", browser_cookie3.brave)]

    for name, loader in browsers:
        try:
            jar = loader(domain_name=".xiaohongshu.com")
            cookies = {
                c.name: c.value
                for c in jar
                if "xiaohongshu.com" in (c.domain or "")
            }
            if "a1" in cookies and "web_session" in cookies:
                return name, cookies
        except Exception:
            continue

    # 子进程回退（browser_cookie3 读 Cookies 数据库需要解密，主进程可能被桌面浏览器锁住）
    extract_script = '''
import json, sys
try:
    import browser_cookie3 as bc3
except ImportError:
    print(json.dumps({"error": "not_installed"}))
    sys.exit(0)

browsers = [
    ("Chrome", bc3.chrome),
    ("Firefox", bc3.firefox),
    ("Edge", bc3.edge),
    ("Brave", bc3.brave),
]
for name, loader in browsers:
    try:
        cj = loader(domain_name=".xiaohongshu.com")
        cookies = {c.name: c.value for c in cj if "xiaohongshu.com" in (c.domain or "")}
        if "a1" in cookies and "web_session" in cookies:
            print(json.dumps({"browser": name, "cookies": cookies}))
            sys.exit(0)
    except Exception:
        pass
print(json.dumps({"error": "no_cookies"}))
'''
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, "-c", extract_script],
            capture_output=True, text=True, timeout=15,
        )
        data = json.loads(result.stdout.strip() or "{}")
        if data.get("cookies"):
            return data["browser"], data["cookies"]
    except Exception:
        pass
    raise SystemError(
        "未找到小红书登录 cookie：请先在浏览器登录 https://www.xiaohongshu.com "
        "并确保浏览器中能访问小红书（含 a1/web_session 两个关键 cookie）"
    )


def get_cookies(cookie: str = "") -> dict:
    """cookie 来源：显式字符串 > 默认 browser_cookie3 提取。返回 {name: value}。"""
    if cookie:
        cookies = cookie_str_to_dict(cookie)
    else:
        browser, cookies = extract_browser_cookies()
        print(f'从 {browser} 提取到 {len(cookies)} 个 cookie')
    missing = REQUIRED_COOKIES - cookies.keys()
    if missing:
        raise SystemError(f"cookie 缺少必需字段: {', '.join(sorted(missing))}")
    return cookies


# ─── 主站 API 签名（xhs-workbench signing.py / client.py） ──────────────────
from xhshow import CryptoConfig, SessionManager, Xhshow

_config = CryptoConfig().with_overrides(
    PUBLIC_USERAGENT=USER_AGENT,
    SIGNATURE_DATA_TEMPLATE={
        "x0": SDK_VERSION,
        "x1": APP_ID,
        "x2": PLATFORM,
        "x3": "",
        "x4": "",
    },
    SIGNATURE_XSCOMMON_TEMPLATE={
        "s0": 5,
        "s1": "",
        "x0": "1",
        "x1": SDK_VERSION,
        "x2": PLATFORM,
        "x3": APP_ID,
        "x4": "4.86.0",
        "x5": "",
        "x6": "",
        "x7": "",
        "x8": "",
        "x9": -596800761,
        "x10": 0,
        "x11": "normal",
    },
)
_xhshow = Xhshow(_config)
_session = SessionManager(_config)


def sign_main_api(method: str, uri: str, cookies: dict, payload: dict = None) -> dict:
    """生成主站 API 签名头（与 workbench signing.sign_main_api 一致）。"""
    if method.upper() == "GET":
        return _xhshow.sign_headers_get(uri, cookies, params=None, session=_session)
    return _xhshow.sign_headers_post(uri, cookies, payload=payload, session=_session)


def base_headers(cookies: dict) -> dict:
    """基础请求头（与 workbench client._base_headers 一致）。"""
    return {
        "user-agent": USER_AGENT,
        "content-type": "application/json;charset=UTF-8",
        "cookie": "; ".join(f"{k}={v}" for k, v in cookies.items()),
        "origin": HOME_URL,
        "referer": f"{HOME_URL}/",
        "sec-ch-ua": f'"Not:A-Brand";v="99", "Google Chrome";v="{CHROME_VERSION}", "Chromium";v="{CHROME_VERSION}"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "accept": "application/json, text/plain, */*",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
        "dnt": "1",
        "priority": "u=1, i",
    }


# ─── 发布 ───────────────────────────────────────────────────────────────────
def xhs_post(cookies: dict, title: str, body: str, retry: int = 20) -> dict:
    """发布图文/长文笔记；返回响应 JSON 的 data 字段。

    对应 workbench client_mixins.create_image_note：
      POST {EDITH_HOST}/web_api/sns/v2/note，主站签名，origin/referer 指向创作平台。
    纯文字笔记 image_file_ids 传空列表，正文放 common.desc。
    """
    business_binds = {
        "version": 1,
        "noteId": 0,
        "noteOrderBind": {},
        "notePostTiming": {"postTime": None},
        "noteCollectionBind": {"id": ""},
    }
    data = {
        "common": {
            "type": "normal",
            "title": title[:100],
            "note_id": "",
            "desc": body,
            "source": '{"type":"web","ids":"","extraInfo":"{\\"subType\\":\\"official\\"}"}',
            "business_binds": json.dumps(business_binds),
            "ats": [],
            "hash_tag": [],
            "post_loc": {},
            "privacy_info": {"op_type": 1, "type": 0},
        },
        "image_info": {"images": []},
        "video_info": None,
    }
    body_str = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    sign_headers = sign_main_api("POST", "/web_api/sns/v2/note", cookies, payload=data)
    headers = {
        **base_headers(cookies),
        **sign_headers,
        "origin": CREATOR_HOST,
        "referer": f"{CREATOR_HOST}/",
    }

    last_json = None
    for i in range(retry):
        try:
            resp = requests.post(POST_NOTE_URL, headers=headers, data=body_str, timeout=30)
            text = resp.text or ""
            if not text:
                print(f'POST retry #{i}: 空响应 (HTTP {resp.status_code})')
                time.sleep(2)
                continue
            try:
                last_json = resp.json()
            except json.JSONDecodeError:
                print(f'POST retry #{i}: 非 JSON 响应 (HTTP {resp.status_code}) {text[:200]}')
                time.sleep(2)
                continue
            if last_json.get("success"):
                return last_json.get("data", last_json.get("success"))
            code = last_json.get("code")
            if code == -100:
                raise SystemError("登录态过期（code=-100），请重新在浏览器登录小红书")
            if code == 300012:
                raise SystemError("IP 被风控（code=300012），请更换网络环境")
            if code == 300015:
                raise SystemError("签名校验失败（code=300015），请检查 cookie 与时间戳")
            print(f'POST retry #{i}: {json.dumps(last_json, ensure_ascii=False)[:300]}')
            time.sleep(2)
        except requests.RequestException as ex:
            print(f'POST retry #{i}: {ex}')
            time.sleep(2)
    raise SystemError(f"发布失败: {json.dumps(last_json, ensure_ascii=False) if last_json else '无响应'}")


# ─── 入口 ───────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        prog="xhs_post", description="小红书笔记发布 (requests API)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("fname", help="TXT/MD 文件或目录（首行当标题，其余为正文）")
    parser.add_argument("-c", "--cookie", default="", help="cookie 字符串 (name=v; ...)；默认 browser_cookie3 从浏览器提取")
    parser.add_argument("-r", "--retry", type=int, default=20, help="重试次数 (默认 20)")
    parser.add_argument("-R", "--keep", action="store_true", help="发布成功后不删除源文件")
    args = parser.parse_args()

    cookies = get_cookies(args.cookie)

    # 文件收集（沿用旧脚本：TXT/MD，首行作标题）
    if path.isfile(args.fname):
        fnames = [args.fname]
    else:
        fnames = [
            path.join(args.fname, f)
            for f in os.listdir(args.fname)
        ]
    fnames = [f for f in fnames if f.endswith(('.md', '.txt'))]
    if not fnames:
        print('请提供小红书 TXT/MD 文件或目录')
        return

    for f in fnames:
        try:
            print(f)
            txt = open(f, encoding='utf8').read()
            m = re.search(r'\A\s*^(.+?)$', txt, flags=re.M)
            if not m:
                print(f'{f} 文件无标题，跳过')
                continue
            title = m.group(1)
            pos = m.span()[1]
            body = txt[pos:].strip()
            print(f'发布: {title}')
            data = xhs_post(cookies, title, body, retry=args.retry)
            note = (data or {}).get('note') or {}
            note_id = note.get('noteId') or note.get('note_id') or ''
            print('发布成功:', json.dumps(data, ensure_ascii=False)[:500] if data is not None else 'ok')
            if note_id:
                print('笔记ID:', note_id, '访问:', f'https://www.xiaohongshu.com/explore/{note_id}')
            if not args.keep:
                os.remove(f)
        except KeyboardInterrupt:
            raise
        except SystemExit:
            raise
        except Exception as ex:
            print(f'{f} 发布异常: {ex}')


if __name__ == '__main__':
    main()