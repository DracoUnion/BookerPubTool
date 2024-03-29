import subprocess as subp
import re
from os import path
import uuid
import platform
import time
from multiprocessing import Process
from .util import *

def is_git_repo(dir):
    return path.isdir(dir) and \
        path.isdir(path.join(dir, '.git'))

def get_remote_names(dir):
    return exec_cmd(
        'git remote', cwd=dir,
        stdout=subp.PIPE,
        stderr=subp.PIPE,
    )[0].decode('utf8').split('\n')

def set_remote(dir, name, url):
    # 判断是否有远程库
    remotes = get_remote_names(dir)
    if name in remotes:
        exec_cmd(['git', 'remote', 'rm', name], cwd=dir)
    exec_cmd(['git', 'remote', 'add', name, url], cwd=dir)
    

def get_status(dir):
    lines = exec_cmd(
        'git status -s -u', cwd=dir,
        stdout=subp.PIPE,
        stderr=subp.PIPE,
    )[0].decode('utf8').split('\n')
    status_map = {}
    for l in lines:
        tp = l[:2].strip()
        f = l[3:]
        if f.startswith('"') and f.endswith('"'):
            f = f[1:-1]
        status_map.setdefault(tp, [])
        status_map[tp].append(f)
    return status_map

def get_untracked_files(dir):
    return get_status(dir).get('??', [])
            
def config_utf8_unquote():
    exec_cmd('git config --global core.quotepath false')
            
def config_username_email(dir, un, email):
    exec_cmd(['git', 'config', 'user.name', un], cwd=dir)
    exec_cmd(['git', 'config', 'user.email', email], cwd=dir)

# 初始化仓库
def git_init(args):
    dir = args.dir
    origin = args.origin
    if not path.isdir(dir):
        print(f'{timestr()} 请提供目录')
        return
    # 检查是否是 GIT 本地仓库，不是则初始化
    if not path.isdir(path.join(dir, '.git')):
        exec_cmd('git init', cwd=dir)
    # 配置用户名和邮箱
    config_username_email(dir, args.user, args.email)
    # 检查是否存在分支
    branches = get_all_branches(dir)
    if not branches:
        # 创建空提交来保证能够执行所有操作
        exec_cmd('git commit -m init --allow-empty', cwd=dir)
    # 如果提供了 Origin 远程地址则设置
    if origin: set_remote(dir, 'origin', origin)

def git_commit_handle(args):
    if not args.reset:
        git_commit_per_file(args)
        return
        
    p = Process(target=git_commit_per_file, args=[args])
    p.start()
    time0 = time.time()
    while p.is_alive():
        if time.time() - time0 >= args.reset:
            # 重置子进程
            p.terminate()
            p.join()
            p.close()
            p = Process(target=git_commit_per_file, args=[args])
            p.start
        time.sleep(1)
        
    p.close()

# 将未跟踪文件一个一个添加并提交
def git_commit_per_file(args):
    dir = args.dir
    if not is_git_repo(dir):
        print(f'{timestr()} 请提供 GIT 本地仓库')
        return
    # 配置 UTF8 不转义
    config_utf8_unquote()
    # 自动 GC
    exec_cmd(['git', 'gc', '--auto'], cwd=dir)
    # 配置用户名和邮箱
    config_username_email(dir, args.user, args.email)
    # 列出所有未跟踪的文件
    files = get_untracked_files(dir)
    # 对于所有未跟踪的文件，单独提交
    for f in files[:args.count]:
        print(f'{timestr()} {f}')
        cmds = [
            ['git', 'add', f],
            ['git', 'commit', '-m', f'add {f}'],
        ]
        for cmd in cmds:
            exec_cmd(cmd, cwd=dir)

def get_cur_branch(dir):
    return exec_cmd(
        'git branch --show-current', 
        cwd=dir,
        stdout=subp.PIPE,
        stderr=subp.PIPE,
    )[0].decode('utf8')

def get_all_branches(dir):
    branches = exec_cmd(
        ['git', 'branch', '-a'], 
        cwd=dir,
        stdout=subp.PIPE,
        stderr=subp.PIPE,
    )[0].decode('utf8').split('\n')
    branches = [b[2:] for b in branches]
    return list(filter(None, branches))

def get_branch_cids(dir, *branches):
    if platform.system().lower() == 'windows':
        branches = [b.replace('^', '^^') for b in branches]
    lines = exec_cmd(
        ['git', 'log', *branches, '--pretty=format:%H'], 
        cwd=dir,
        stdout=subp.PIPE,
        stderr=subp.PIPE,
    )[0].decode('utf8')
    # 记得过滤空行
    return [l for l in lines.split('\n') if l.strip()]

def git_push_handle(args):
    if not args.reset:
        git_push_per_commit(args)
        return
        
    p = Process(target=git_push_per_commit, args=[args])
    p.start()
    time0 = time.time()
    while p.is_alive():
        if time.time() - time0 >= args.reset:
            # 重置子进程
            p.terminate()
            p.join()
            p.close()
            p = Process(target=git_push_per_commit, args=[args])
            p.start
        time.sleep(1)
        
    p.close()

# 逐个推送提交
def git_push_per_commit(args):
    dir = args.dir
    work_branch = args.branch
    remote = args.remote
    print(f'{timestr()} branch: {work_branch}, remote: {remote}')
    if not is_git_repo(dir):
        print(f'{timestr()} 请提供 GIT 本地仓库')
        return
    # 检查分支是否存在
    branches = get_all_branches(dir)
    if work_branch not in branches:
        print(f'{timestr()} 分支 {work_branch} 不存在')
        return
    # 如果远程仓库名为地址，创建别名
    if remote.startswith('https://') or \
        remote.startswith('git@'):
            url, remote = remote, uuid.uuid4().hex
            exec_cmd(['git', 'remote', 'add', remote, url], cwd=dir)
    # 检查远程库是否存在
    remotes = get_remote_names(dir)
    if remote not in remotes:
        print(f'{timestr()} 远程仓库 {remote} 不存在')
        return
            
    # 检查远程库是否有该分支
    exec_cmd(['git', 'remote', 'update', remote], cwd=dir)
    branches = get_all_branches(dir)
    remote_branch = f'remotes/{remote}/{work_branch}'
    if remote_branch not in branches:
        # 如果远程分支不存在，推送本地分支所有提交
        cids = get_branch_cids(dir, work_branch)
    else:
        # 查看远程库是否有新提交
        cids = get_branch_cids(dir, remote_branch, '^' + work_branch)
        if cids:
            cid_str = ','.join(cids)
            print(f'{timestr()} 远程仓库有新的提交，需要手动 git pull：{cid_str}')
            print('\n'.join(cids))
            return
        # 查看本地库的新提交
        cids = get_branch_cids(dir, work_branch, '^' + remote_branch)
    for cid in cids[::-1][:args.count]:
        # 提交改动
        print(f'{timestr()} {cid}')
        cmd = ['git', 'push', remote, f'{cid}:refs/heads/{work_branch}']
        exec_cmd(cmd, cwd=dir)
            
