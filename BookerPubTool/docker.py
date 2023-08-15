from os import path
import re
import os
import sys
import subprocess as subp
import requests
from datetime import datetime
from .util import *
from .ebook2site import ebook2site

DOCKERFILE = '''
FROM httpd:2.4
COPY ./ /usr/local/apache2/htdocs/
'''

def get_docker_last_ver_date(name, org='apachecn0'):
    url = f'https://hub.docker.com/v2/repositories/{org}/{name}/tags/?page_size=100&page=1&ordering=last_updated'
    r = requests.get(url)
    if r.status_code == 404: return '00010101'
    try: j = r.json()
    except: return '00010101'
    if 'results' not in j:
        return '00010101'
    vers = [
        r['name'].split('.')[:-1]
        for r in j['results']
        if re.search(r'\d+\.\d+\.\d+\.\d+', r['name'])
    ]
    vers = [
        it[0].zfill(4) + it[1].zfill(2) + it[2].zfill(2)
        for it in vers
    ]
    return max(vers) if vers else '00010101'

def get_docker_latest_fix_ver(name, org='apachecn0', cur=None):
    now = datetime.now()
    cur = cur or \
        f'{now.year}.{now.month}.{now.day}.'
    url = f'https://hub.docker.com/v2/repositories/{org}/{name}/tags/?page_size=100&page=1&name={cur}&ordering=last_updated'
    r = requests.get(url)
    if r.status_code == 404: return 0
    try: j = r.json()
    except: return 0
    if 'results' not in j:
        return 0
    fix_vers = [
        int(r['name'].split('.')[-1])
        for r in j['results']
    ]
    if len(fix_vers) == 0:
        return 0
    else:
        return max(fix_vers) + 1

def publish_docker(args):
    dir = path.abspath(args.dir)
    # 预处理文件
    ext = extname(dir)
    need_rmdir = False
    if path.isfile(dir) and \
       ext in ['pdf', 'epub', 'mobi', 'azw3']:
        fname = dir
        dir = path.join(
            tempfile.gettempdir(), 
            gen_proj_name(path.basename(dir)),
        )
        ebook2site(fname, dir)
        need_rmdir = True
    if not path.exists(dir):
        print(f'{timestr()} 目录不存在')
        return
    
    fnames = os.listdir(dir)
    if 'README.md' not in fnames or \
       'index.html' not in fnames:
        print(f'{timestr()} 请提供文档目录')
        return
        
    if 'Dockerfile' not in fnames:
        open(path.join(dir, 'Dockerfile'), 'w').write(DOCKERFILE)
        
    name = path.basename(dir).lower()
    if args.expire:
        last_date = get_docker_last_ver_date(name)
        print(f'{timestr()} 最新：{last_date}，当前：{args.expire}')
        if last_date >= args.expire:
            print(f'{timestr()} 最新包未过期，无需发布')
            return
    now = datetime.now()
    ver = f'{now.year}.{now.month}.{now.day}.'
    fix_ver = get_docker_latest_fix_ver(name, cur=ver)
    ver += str(fix_ver)
    print(f'{timestr()} name: {name}, ver: {ver}')
    
    cmds = [
        f'docker build -t apachecn0/{name}:{ver} {dir}',
        f'docker push apachecn0/{name}:{ver}',
        f'docker tag apachecn0/{name}:{ver} apachecn0/{name}:latest',
        f'docker push apachecn0/{name}:latest',
    ]
    for cmd in cmds:
        subp.Popen(cmd, shell=True).communicate()
    if need_rmdir: rmtree(dir)

