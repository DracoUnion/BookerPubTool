# -*- coding: utf-8 -*-

"""shipinhao — Publish to 视频号 (WeChat Channels).

Python port of content-pipeline's platforms/shipinhao.ts.
视频号 has no web creator backend; we only print a manual upload guide.
"""

from os import path
from .util import timestr
from .distribute import status_print


def publish_shipinhao(args):
    intro = args.intro
    outro = args.outro
    prompts = args.prompts

    if not intro and not outro and not prompts:
        status_print('skipped', 'No video content provided. Pass --intro/--outro/--prompts.')
        return

    lines = []
    if intro:
        lines.append(f'Intro: {intro}')
    if outro:
        lines.append(f'Outro: {outro}')
    if prompts:
        lines.append(f'Prompts: {prompts}')

    status_print(
        'manual',
        '视频号 has no web creator backend. Upload via mobile app.\n  ' + '\n  '.join(lines)
    )


def reg_subparser(subparsers):
    parser = subparsers.add_parser("shipinhao", help="视频号: manual upload guide")
    parser.add_argument("--intro", help="片头视频路径")
    parser.add_argument("--outro", help="片尾视频路径")
    parser.add_argument("--prompts", help="提词器文案路径")
    parser.set_defaults(func=publish_shipinhao)