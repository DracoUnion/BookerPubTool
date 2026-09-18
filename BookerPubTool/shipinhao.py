# -*- coding: utf-8 -*-

"""shipinhao — Publish to 视频号 (WeChat Channels).

Python port of content-pipeline's platforms/shipinhao.ts.
视频号 has no web creator backend; we only print a manual upload guide.
"""

import os
from os import path
from .util import timestr
from .distribute import load_manifest, get_outputs, status_print


def publish_shipinhao(args):
    manifest = load_manifest(args.manifest)
    outputs = get_outputs(manifest)
    video_data = outputs.get('video') or outputs.get('shipinhao')
    if not video_data:
        status_print('skipped', 'No video content in manifest')
        return

    lines = []
    if video_data.get('intro'):
        lines.append(f'Intro: {video_data["intro"]}')
    if video_data.get('outro'):
        lines.append(f'Outro: {video_data["outro"]}')
    if video_data.get('prompts'):
        lines.append(f'Prompts: {video_data["prompts"]}')

    status_print(
        'manual',
        '视频号 has no web creator backend. Upload via mobile app.\n  ' + '\n  '.join(lines)
    )


def reg_subparser(subparsers):
    parser = subparsers.add_parser("shipinhao", help="video号: manual upload guide (视频号)")
    from .distribute import add_common_args
    add_common_args(parser)
    parser.set_defaults(func=publish_shipinhao)