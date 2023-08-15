import subprocess as subp
from datetime import datetime
import requests
from pyquery import PyQuery as pq
import tempfile
import uuid
import sys
import shutil
import os
from os import path
import re
import stat
import json
from .util import *
from .ebook2site import ebook2site

def config_npm(args):
    subp.Popen(
        ['npm', 'config', 'set', '//registry.npmjs.org/:_authToken', args.token],
        shell=True,
        stdout=subp.PIPE,
        stderr=subp.PIPE
    ).communicate()
    
def get_npm_last_ver_date(name):
    r, err = subp.Popen(
        ['npm', 'view', name, 'versions', '--json'],
        stdout=subp.PIPE,
        stderr=subp.PIPE,
        shell=True
    ).communicate()
    if err: return '00010101'
    j = json.loads(r.decode('utf-8'))
    vers = [it.split('.')[:-1] for it in j]
    vers = [
        it[0].zfill(4) + it[1].zfill(4)
        for it in vers
    ]
    return max(vers)
    
def get_npm_fix_version(name, curr=None):
    now = datetime.now()
    curr = curr or \
        f'{now.year}.{now.month}{now.day:02d}'
    r, err = subp.Popen(
        ['npm', 'view', name, 'versions', '--json'],
        stdout=subp.PIPE,
        stderr=subp.PIPE,
        shell=True
    ).communicate()
    if err: return 0
    j = json.loads(r.decode('utf-8'))
    j = [it for it in j if it.startswith(curr + '.')]
    j = [int(it.split('.')[-1]) for it in j]
    return 0 if len(j) == 0 else max(j) + 1
    
def publish_npm(args):
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
    # 检查目录
    if not path.isdir(dir):
        print(f'{timestr()} 请提供目录')
        return
    files = os.listdir(dir)
    if not 'index.html' in files or \
       not 'README.md' in files:
        print(f'{timestr()} 请提供文档')
        return
    # 读取元信息
    name = path.basename(dir)
    pkg_name = npm_filter_name(name)
    if args.expire:
        last_date = get_npm_last_ver_date(pkg_name)
        print(f'{timestr()} 最新：{last_date}，当前：{args.expire}')
        if last_date >= args.expire:
            print(f'{timestr()} 最新包未过期，无需发布')
            return
    fix_ver = get_npm_fix_version(pkg_name)
    now = datetime.now()
    ver = f'{now.year}.{now.month}{now.day:02d}.{fix_ver}'
    readme = read_file(path.join(dir, 'README.md'), 'utf-8')
    desc = get_desc(readme)
    print(f'{timestr()} name: {name}, pkg: {pkg_name}, ver: {ver}, desc: {desc}')
    # 创建临时目录
    pkg_dir = path.join(tempfile.gettempdir(), uuid.uuid4().hex)
    os.mkdir(pkg_dir)
    # 填充文档
    shutil.copytree(dir, path.join(pkg_dir, 'doc'))
    shutil.copy(
        path.join(pkg_dir, 'doc/README.md'),
        path.join(pkg_dir, 'README.md')
    )
    # 主程序
    shutil.copy(
        d('asset/server.js'),
        path.join(pkg_dir, 'index.js')
    )
    # 配置
    pkg_json = json.loads(read_file(d('asset/package.tmpl'), 'utf-8'))
    pkg_json['name'] = pkg_name
    pkg_json['version'] = ver
    pkg_json['description'] = desc
    pkg_json['repository']['url'] = \
        f'git+https://github.com/apachecn/{name}.git'
    pkg_json['bin'] = {}
    pkg_json['bin'][pkg_name] = "index.js"
    pkg_json['bin'][name] = "index.js"
    write_file(
        path.join(pkg_dir, 'package.json'),
        json.dumps(pkg_json), 'utf-8'
    )
    # 发布
    os.chdir(pkg_dir)
    subp.Popen(
        ['npm', 'publish'],
        shell=True
    ).communicate()
    # 删除临时目录
    os.chdir('..')
    rmtree(pkg_dir)
    if need_rmdir: rmtree(dir)
