import requests
import json
import re
import time
import sys
import random
import os
import traceback

default_hdrs = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.72 Safari/537.36',
    'Origin': 'https://www.zhihu.com',
    'Referer': 'https://www.zhihu.com',
}

def send_msg_v4_old(uid, co, cookie):
    m = re.search(r'(?<=z_c0=)\w+\|\d+\|\w+', cookie)
    token = m.group() if m else ''
    hdrs = default_hdrs.copy()
    hdrs.update({
        'Authorization': 'Bearer ' + token,
        'Cookie': cookie.strip(),
    })
    url = 'https://www.zhihu.com/api/v4/messages'
    data = {
        'type': 'common',
        'receiver_hash': uid,
        'content': co,
    }
    try:
        r = requests.post(url, json=data, headers=hdrs)
    except Exception as ex:
        return [1, str(ex)]
    if r.status_code == 200:
        return [0, '']
    else:
        return [r.status_code, f'HTTP {r.status_code}: {r.text}']

def send_msg_handle(args):
    uid_fname = args.uid_fname
    co, cookies = args.content, args.cookies
    uids = open(uid_fname, encoding='utf8').read()
    uids = filter(None, [u.strip() for u in uids.split('\n')])
    ci = 0
    for uid in uids:
        print(f'uid: {uid}')
        cookie = cookies[ci]
        ci = (ci + 1) % len(cookies)
        r = (
            send_msg_v4_old(uid, co, cookie) 
            if not args.new
            else send_msg_v4(uid, co, cookie)
        )
        if r[0] == 0:
            print(f'{uid} 发送成功')
            sleep_with_print(args.wait_succ)
        else:
            print(f'{uid} 发送失败：{r[1]}')
            if r[0] == 403:
                sleep_with_print(args.wait_403)
            else:
                sleep_with_print(args.wait_fail)

def send_msg_v4(uid, co, cookie):
    m = re.search(r'(?<=_xsrf=)\w{8}-\w{4}-\w{4}-\w{4}-\w{12}', cookie)
    token = m.group() if m else ''
    hdrs = default_hdrs.copy()
    hdrs.update({
        'Cookie': cookie.strip(),
        'X-Xsrftoken': token,
    })
    url = 'https://www.zhihu.com/api/v4//chat'
    data = {
        'content_type': 0,
        'receiver_id': uid,
        'text': co,
    }
    try:
        r = requests.post(url, json=data, headers=hdrs)
    except Exception as ex:
        return [1, str(ex)]
    if r.status_code == 200:
        return [0, '']
    else:
        return [r.status_code, f'HTTP {r.status_code}: {r.text}']

def get_qid_by_tid(tid):
    res = []
    url = f'https://www.zhihu.com/api/v4/topics/{tid}/feeds/top_activity'
    while True:
        print(url)
        r = requests.get(url, headers=default_hdrs)
        if r.status_code != 200:
            print(f'HTTP{r.status_code}: {r.text}')
            return res
        j = r.json()
        res += [
            it['target']['question']['id']
            for it in j['data']
            if it['target']['type'] == 'answer'
        ]
        if j['paging']['is_end']:
            break
        url = j['paging']['next']
    return res

def get_ans_uid_by_qid(qid):
    res = []
    url = f'https://www.zhihu.com/api/v4/questions/{qid}/answers?limit=20'
    while True:
        try:
            print(url)
            j = requests.get(url, headers=default_hdrs).json()
            res += [                
                it['author']['id'] 
                for it in j['data']
                if it['author']['id'] != "0"
            ]
            if j['paging']['is_end']:
                break
            url = j['paging']['next']
        except:
            traceback.print_exc()
            break
    return res

def get_follow_uid_by_qid(qid):
    res = []
    url = f'https://www.zhihu.com/api/v4/questions/{qid}//followers?limit=20'
    while True:
        try:
            print(url)
            j = requests.get(url, headers=default_hdrs).json()
            res += [                
                it['id'] 
                for it in j['data']
                if it['id'] != "0"
            ]
            if j['paging']['is_end']:
                break
            url = j['paging']['next']
        except:
            traceback.print_exc()
            break
    return res

def get_aid_by_qid(qid):
    res = []
    url = 'https://www.zhihu.com/api/v4/questions/{qid}//answers?limit=20'
    while True:
        try:
            print(url)
            j = requests.get(url, headers=default_hdrs).json()
            res += [            
                it['id'] for it in j['data']
            ]
            if j['paging']['is_end']:
                break
            url = j['paging']['next']
        except:
            traceback.print_exc()
            break
    return res
        
def sleep_with_print(sec, dur=60):
    times = sec // dur
    rem = sec % dur
    for i in range(times):
        print(f'sleep: #{i + 1}')
        time.sleep(dur)
    if rem != 0:
        print(f'sleep: #{times + 1}')
        time.sleep(rem)

def crawl_uids_handle(args):
    tid_fname = args.tid_fname
    uid_fname = args.uid_fname
    tids = open(tid_fname, encoding='utf8').read()
    tids = filter(None, [t.strip() for t in tids.split('\n')])
    f = open(uid_fname, 'a', encoding='utf8')
    for tid in tids:
        print(f'tid: {tid}')
        qids = get_qid_by_tid(tid)
        for qid in qids:
            print(f'qid: {qid}')
            uids = get_ans_uid_by_qid(qid)
            uids += get_follow_uid_by_qid(qid)
            f.write('\n'.join(uids) + '\n')
    f.close()
    print('done...')

def reg_subparser(subparsers):
    parser = subparsers.add_parser("zhihu-msg", help="send zhihu messages")
    parser.add_argument("uid_fname", help="file name including uids")
    parser.add_argument(
        "-m", "--content",
        default='布客社区\n\n您永远在线的两性情感和技术变现专家\n\n🔗https://docs.apachecn.org',
        help="message content",
    )
    parser.add_argument("-c", "--cookies", default=os.environ.get('ZHIHU_COOKIES', ''), help="zhihu cookies splited with ';;'")
    parser.add_argument("-n", "--new", action='store_true', help="whether to use new API")
    parser.add_argument("-s", "--wait-succ", type=float, default=60, help="how long to wait after success")
    parser.add_argument("-f", "--wait-fail", type=float, default=0, help="how long to wait after failure except HTTP403")
    parser.add_argument("-b", "--wait-403", type=float, default=0, help="how long to wait after HTTP403")
    parser.set_defaults(func=send_msg_handle)

    parser = subparsers.add_parser("zhihu-crawl-uid", help="crawl zhihu uids from topics")
    parser.add_argument("tid_fname", help="file name including tids")
    parser.add_argument("-u", "--uid-fname", default='uid.txt', help="output file name including uids")
    parser.set_defaults(func=crawl_uids_handle)
        

