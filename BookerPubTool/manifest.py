# -*- coding: utf-8 -*-

"""manifest — 汇总产出物 → manifest.json。

Port of content-pipeline's app/content_pipeline/__main__.py `_cmd_manifest` +
app/content_pipeline/manifest.py.

按约定文件名自动发现输出目录里的产物，汇总成供分发用的 manifest.json。
"""

import glob
from os import path
from .util import timestr
from .distribute import (
    build_manifest, write_manifest, resolve_out_dir, infer_outputs,
    PLATFORM_NAMES,
)


def _cmd_manifest(args):
    """Scan out_dir for known output filenames and write manifest.json."""
    out_dir = resolve_out_dir(args.output)
    outputs = {}

    # 小红书轮播图
    xhs_html = glob.glob(path.join(out_dir, '*小红书版.html'))
    if xhs_html:
        outputs['xiaohongshu'] = {'html': xhs_html[0]}

    # 即刻文案
    jike_txt = glob.glob(path.join(out_dir, '*即刻文案.txt'))
    if jike_txt:
        with open(jike_txt[0], encoding='utf-8') as f:
            outputs['jike'] = {'copy': {'body': f.read()}}

    # 播客（脚本 + 音频）
    script = glob.glob(path.join(out_dir, '*播客脚本.md'))
    audio = glob.glob(path.join(out_dir, '*.mp3'))
    if script:
        outputs['xiaoyuzhou'] = {
            'script': script[0],
            'audio': audio[0] if audio else '',
        }

    # 公众号文章（Markdown + 排版预览 + 封面）
    md_files = [f for f in glob.glob(path.join(out_dir, '*.md'))
                if '播客脚本' not in path.basename(f)]
    previews = glob.glob(path.join(out_dir, '*_preview.html'))
    covers = glob.glob(path.join(out_dir, '*封面.html'))
    if md_files:
        outputs['wechat'] = {
            'markdown': md_files[0],
            'html': previews[0] if previews else '',
            'title': args.title,
        }
        if covers:
            outputs['wechat']['cover_image'] = covers[0]

    manifest = build_manifest(args.title, source=getattr(args, 'source', ''),
                              outputs=outputs)
    p = write_manifest(manifest, out_dir)
    print(f'{timestr()} ✓ {p}')
    if outputs:
        names = ', '.join(PLATFORM_NAMES.get(k, k) for k in outputs)
        print(f'  输出: {names}')
    else:
        print('  输出: （未发现任何已知产物）')


def reg_subparser(subparsers):
    parser = subparsers.add_parser(
        "manifest", help="汇总产出物 → manifest.json（供 gzh/xhs/jike/douyin/xiaoyuzhou/shipinhao 分发）")
    parser.add_argument("title", help="文章标题")
    parser.add_argument("--source", default='', help="来源（如微信链接）")
    parser.add_argument("-o", "--output", default='', help="输出目录")
    parser.set_defaults(func=_cmd_manifest)