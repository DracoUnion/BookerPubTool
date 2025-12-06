from .util import *
from .git import *
from .kan_util import *
from os import path
import os
import shutil
import tempfile
import uuid
import subprocess as subp

def pub_kancloud(args):
    args.dir = path.abspath(args.dir)
    if not path.isdir(args.dir):
        print('请提供文档目录！')
        return
    docrt = os.listdir(args.dir)
    if 'SUMMARY.md' not in docrt or \
       'README.md' not in docrt:
        print('请提供文档目录！')
        return

    doc_dir = path.join(tempfile.gettempdir, uuid.uuid4().hex)
    shutil.copytree(args.dir, doc_dir)
    # os.chdir(doc_dir)

    doc_id = path.basename(args.dir)
    if not kan_exists(args.un, doc_id):
        readme = open(path.join(doc_dir, 'README.md'), encoding='utf8').read()
        title, _ = get_md_title(readme)
        title = title or doc_id
        r = kan_create_repo(args.un, doc_id, args.cookie, title, title)
        if r['code']:
            print(f'{doc_id} 创建失败：{r["message"]}')
            return

    exec_cmd('git init', cwd=doc_dir)
    config_username_email(doc_dir, args.un, f'{args.un}@kancloud.cn')
    exec_cmd('git commit -am init', cwd=doc_dir)
    set_remote(doc_dir, 'origin', '')
    exec_cmd('git push orgin master', cwd=doc_dir)

    kan_toggle(args.un, doc_id, args.cookie, 'download', True)
    r = kan_release(args.un, doc_id, args.cookie)
    if r['code']:
        print(f'{doc_id} 发布失败:{r["message"]}')
        return
    else:
        print(f'{doc_id} 发布成功！')

    shutil.rmtree(doc_dir, True)