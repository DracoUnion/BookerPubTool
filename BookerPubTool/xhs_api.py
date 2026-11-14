"""XHS HTTP publish client (ported from xhs-workbench adapters/xhs)."""
from __future__ import annotations
import json, logging, mimetypes, os, random, time
from typing import Any
from urllib.parse import urlencode
import httpx
logger = logging.getLogger(__name__)
EDITH_HOST = "https://edith.xiaohongshu.com"
CREATOR_HOST = "https://creator.xiaohongshu.com"
HOME_URL = "https://www.xiaohongshu.com"
UPLOAD_HOST = "https://ros-upload.xiaohongshu.com"
CHROME_VERSION = "145"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
SDK_VERSION = "4.2.6"
APP_ID = "xhs-pc-web"
PLATFORM = "macOS"
REQUIRED_COOKIES = {"a1", "web_session"}

class XhsApiError(Exception):
    def __init__(self, message, code=None, response=None):
        super().__init__(message); self.code = code; self.response = response

class NeedVerifyError(XhsApiError):
    def __init__(self, verify_type, verify_uuid):
        super().__init__("Need verify: %s/%s" % (verify_type, verify_uuid))

class SessionExpiredError(XhsApiError):
    def __init__(self): super().__init__("Session expired", code=-100)

class IpBlockedError(XhsApiError):
    def __init__(self): super().__init__("IP blocked", code=300012)

class SignatureError(XhsApiError):
    def __init__(self): super().__init__("Signature error", code=300015)

class NoCookieError(XhsApiError):
    def __init__(self): super().__init__("No valid XHS cookie. Set XHS_COOKIES env or ~/.xhs-cli/cookies.json")

def cookies_to_string(cookies): return "; ".join("%s=%s" % (k, v) for k, v in cookies.items())

def cookie_str_to_dict(cs):
    r = {}
    for item in cs.split(";"):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1); r[k.strip()] = v.strip()
    return r

def load_cookies():
    env = os.environ.get("XHS_COOKIES", "").strip()
    if env: cookies = cookie_str_to_dict(env)
    else:
        cookies = {}
        cf = os.path.join(os.path.expanduser("~"), ".xhs-cli", "cookies.json")
        if os.path.exists(cf):
            try:
                d = json.loads(open(cf, encoding="utf-8").read()); cookies = d.get("cookies", {})
            except Exception as exc: logger.warning("cookie file read failed: %s", exc)
    missing = sorted(REQUIRED_COOKIES - cookies.keys())
    if missing: raise NoCookieError("Missing cookies: %s" % ", ".join(missing))
    return cookies

def sign_creator(api, data, a1):
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad
    import base64, hashlib
    key = b"7cc4adla5ay0701v"; iv = b"4uzjr7mbsibcaldp"
    content = api
    if data is not None: content += json.dumps(data, separators=(",",":"), ensure_ascii=False)
    x1 = hashlib.md5(content.encode()).hexdigest()
    x2 = "0|0|0|1|0|0|1|0|0|0|1|0|0|0|0|1|0|0|0"
    x3 = a1; x4 = int(time.time() * 1000)
    pt = "x1=%s;x2=%s;x3=%s;x4=%s;" % (x1, x2, x3, x4)
    c = AES.new(key, AES.MODE_CBC, iv)
    payload = c.encrypt(pad(pt.encode(), AES.block_size)).hex()
    env = {"signSvn":"56","signType":"x2","appId":"ugc","signVersion":"1","payload":payload}
    xs = "XYW_" + base64.b64encode(json.dumps(env,separators=(",",":")).encode()).decode()
    return {"x-s": xs, "x-t": str(x4)}

_xh = None; _xs = None

def _get_xhshow():
    global _xh, _xs
    if _xh is None:
        from xhshow import CryptoConfig, Xhshow, SessionManager
        cfg = CryptoConfig().with_overrides(
            PUBLIC_USERAGENT=USER_AGENT,
            SIGNATURE_DATA_TEMPLATE={"x0":SDK_VERSION,"x1":APP_ID,"x2":PLATFORM,"x3":"","x4":""},
            SIGNATURE_XSCOMMON_TEMPLATE={"s0":5,"s1":"","x0":"1","x1":SDK_VERSION,"x2":PLATFORM,
            "x3":APP_ID,"x4":"4.86.0","x5":"","x6":"","x7":"","x8":"","x9":-596800761,"x10":0,"x11":"normal"},
        )
        _xh = Xhshow(cfg); _xs = SessionManager(cfg)
    return _xh, _xs

def sign_main_api(method, uri, cookies, params=None, payload=None):
    xh, sess = _get_xhshow()
    if method.upper() == "GET": return xh.sign_headers_get(uri, cookies, params=params, session=sess)
    return xh.sign_headers_post(uri, cookies, payload=payload, session=sess)

class XhsClient:
    def __init__(self, cookies, timeout=30.0, request_delay=1.0, max_retries=3):
        self.cookies = cookies
        self._http = httpx.Client(timeout=timeout, follow_redirects=True)
        self._request_delay = request_delay; self._max_retries = max_retries; self._last = 0.0
    def close(self): self._http.close()
    def __enter__(self): return self
    def __exit__(self, *a): self.close()
    def _rl(self):
        if self._request_delay <= 0: return
        el = time.time() - self._last
        if el < self._request_delay:
            j = max(0, random.gauss(0.3,0.15))
            if random.random() < 0.05: j += random.uniform(2,5)
            time.sleep(self._request_delay - el + j)
    def _mk(self): self._last = time.time()
    def _hdrs(self):
        q = chr(34)
        scua = q+"Not:A-Brand"+q+";v="+q+"99"+q+", "+q+"Google Chrome"+q+";v="+q+CHROME_VERSION+q+", "+q+"Chromium"+q+";v="+q+CHROME_VERSION+q
        return {
            "user-agent":USER_AGENT,"content-type":"application/json;charset=UTF-8",
            "cookie":cookies_to_string(self.cookies),"origin":HOME_URL,"referer":HOME_URL+"/",
            "sec-ch-ua":scua,"sec-ch-ua-mobile":"?0","sec-ch-ua-platform":q+"macOS"+q,
            "sec-fetch-dest":"empty","sec-fetch-mode":"cors","sec-fetch-site":"same-site",
            "accept":"application/json, text/plain, */*","accept-language":"zh-CN,zh;q=0.9,en;q=0.8",
            "dnt":"1","priority":"u=1, i",
        }
    def _resp(self, r):
        if r.status_code in (461,471):
            raise NeedVerifyError(r.headers.get("verifytype","?"), r.headers.get("verifyuuid","?"))
        t = r.text
        if not t: return None
        try: d = json.loads(t)
        except Exception: raise XhsApiError("Non-JSON: %s" % t[:200])
        if d.get("success"): return d.get("data", d.get("success"))
        c = d.get("code")
        if c == 300012: raise IpBlockedError()
        if c == 300015: raise SignatureError()
        if c == -100: raise SessionExpiredError()
        raise XhsApiError("API error: %s" % json.dumps(d)[:300], code=c, response=d)
    def _req(self, method, url, **kw):
        self._rl(); last=None; resp=None
        for i in range(self._max_retries):
            try:
                resp = self._http.request(method, url, **kw)
                for n,v in resp.cookies.items():
                    if v: self.cookies[n] = v
                self._mk()
                if resp.status_code in (429,500,502,503,504):
                    w = 2**i + random.uniform(0,1); logger.warning("HTTP %d retry in %.1fs", resp.status_code, w)
                    time.sleep(w); continue
                return resp
            except (httpx.TimeoutException, httpx.NetworkError) as e:
                last=e; w = 2**i + random.uniform(0,1); logger.warning("Net error %s retry in %.1fs", e, w); time.sleep(w)
        if last: raise XhsApiError("Failed after %d retries: %s" % (self._max_retries, last)) from last
        raise XhsApiError("Failed: HTTP %s" % resp.status_code)
    def _post(self, uri, data, hdr=None):
        sh = sign_main_api("POST", uri, self.cookies, payload=data)
        h = {**self._hdrs(), **sh}
        if hdr: h.update(hdr)
        b = json.dumps(data, separators=(",",":"), ensure_ascii=False)
        r = self._req("POST", EDITH_HOST+uri, headers=h, content=b)
        return self._resp(r)
    def _cget(self, uri, params=None):
        if params: uri = uri + "?" + urlencode(params)
        s = sign_creator("url="+uri, None, self.cookies["a1"])
        h = {**self._hdrs(), "x-s":s["x-s"],"x-t":s["x-t"],"origin":CREATOR_HOST,"referer":CREATOR_HOST+"/"}
        r = self._req("GET", CREATOR_HOST+uri, headers=h)
        return self._resp(r)
    def get_upload_tokens(self, file_type, count):
        d = self._cget("/api/media/v1/upload/web/permit", {"biz_name":"spectrum","scene":file_type,"file_count":count,"version":1,"source":"web"})
        p = d["uploadTempPermits"][0]
        return p["fileIds"], [p["token"]]*len(p["fileIds"])
    def upload_file(self, fid, token, path, ct=None):
        with open(path,"rb") as f: fd = f.read()
        ct = ct or mimetypes.guess_type(path)[0] or "application/octet-stream"
        r = self._req("PUT", UPLOAD_HOST+"/"+fid, headers={"X-Cos-Security-Token":token,"Content-Type":ct}, content=fd)
        if r.status_code >= 400: raise XhsApiError("Upload failed: %d %s" % (r.status_code, r.reason_phrase))
    def _build_note(self, ntype, title, desc, img, vid, topics, priv):
        bb = {"version":1,"noteId":0,"noteOrderBind":{},"notePostTiming":{"postTime":None},"noteCollectionBind":{"id":""}}
        q = chr(34)
        src = json.dumps({"type":"web","ids":"","extraInfo":"{"+q+"subType"+q+":"+q+"official"+q+"}"}, ensure_ascii=False)
        return {
            "common":{"type":ntype,"title":title,"note_id":"","desc":desc,
                "source":src,"business_binds":json.dumps(bb),"ats":[],"hash_tag":topics or [],
                "post_loc":{},"privacy_info":{"op_type":1,"type":1 if priv else 0}},
            "image_info":img,"video_info":vid,
        }
    def create_image_note(self, title, desc, file_ids, topics=None, priv=False):
        imgs = [{"file_id":f,"metadata":{"source":-1}} for f in file_ids]
        d = self._build_note("normal",title,desc,{"images":imgs},None,topics,priv)
        return self._post("/web_api/sns/v2/note", d, {"origin":CREATOR_HOST,"referer":CREATOR_HOST+"/"})
    def create_video_note(self, title, desc, vid, cover=None, topics=None, priv=False):
        vi = {"video":{"file_id":vid,"metadata":{"source":-1}}}
        if cover: vi["cover"] = {"file_id":cover}
        d = self._build_note("video",title,desc,None,vi,topics,priv)
        return self._post("/web_api/sns/v2/note", d, {"origin":CREATOR_HOST,"referer":CREATOR_HOST+"/"})
    def create_text_note(self, title, desc, topics=None, priv=False):
        """发布纯文本笔记（无图片/视频）。"""
        d = self._build_note("normal", title, desc, None, None, topics, priv)
        return self._post("/web_api/sns/v2/note", d, {"origin":CREATOR_HOST,"referer":CREATOR_HOST+"/"})
    def create_text_note(self, title, desc, topics=None, priv=False):
        """发布纯文本笔记（无图片/视频）。"""
        d = self._build_note("normal", title, desc, None, None, topics, priv)
        return self._post("/web_api/sns/v2/note", d, {"origin":CREATOR_HOST,"referer":CREATOR_HOST+"/"})

def open_client(cookies=None): return XhsClient(cookies if cookies is not None else load_cookies())

def publish_image_note(title, desc, paths, topics=None, priv=False, cookies=None):
    c = open_client(cookies)
    try:
        fids, toks = c.get_upload_tokens("image", len(paths))
        for f,t,p in zip(fids,toks,paths): logger.info("Upload img: %s", p); c.upload_file(f,t,p)
        logger.info("Publish image note: %s", title)
        return c.create_image_note(title, desc, fids, topics, priv)
    finally: c.close()

def publish_video_note(title, desc, vid_path, cover_path=None, topics=None, priv=False, cookies=None):
    c = open_client(cookies)
    try:
        vids, vtoks = c.get_upload_tokens("video", 1)
        logger.info("Upload video: %s", vid_path); c.upload_file(vids[0], vtoks[0], vid_path)
        cover_id = None
        if cover_path and os.path.exists(cover_path):
            cids, ctoks = c.get_upload_tokens("image", 1)
            logger.info("Upload cover: %s", cover_path); c.upload_file(cids[0], ctoks[0], cover_path)
            cover_id = cids[0]
        logger.info("Publish video note: %s", title)
        return c.create_video_note(title, desc, vids[0], cover_id, topics, priv)
    finally: c.close()

def publish_text_note(title, desc, topics=None, priv=False, cookies=None):
    c = open_client(cookies)
    try:
        logger.info("Publish text note: %s", title)
        return c.create_text_note(title, desc, topics, priv)
    finally:
        c.close()
