# -*- coding: utf-8 -*-

"""Content distribution helpers shared by the publish subcommands.

Ports the manifest handling from content-pipeline's
scripts/distribute/distribute.ts + cdp-utils.ts.
"""

import json
import os
import glob
from os import path
from datetime import datetime
from .util import timestr, read_file


MANIFEST_SCHEMA_VERSION = "1.0"

# 平台键 → 中文名（与 content-pipeline SKILL.md / manifest.py 一致）
PLATFORM_ORDER = ['wechat', 'xhs', 'jike', 'xiaoyuzhou', 'douyin', 'shipinhao']

PLATFORM_NAMES = {
    'wechat': '公众号',
    'xhs': '小红书',
    'jike': '即刻',
    'xiaoyuzhou': '小宇宙',
    'douyin': '抖音',
    'shipinhao': '视频号',
}


def load_manifest(manifest_path):
    """Read and return a manifest.json dict.

    Mirrors loadManifest() in cdp-utils.ts.
    """
    if not path.exists(manifest_path):
        raise RuntimeError(f'manifest.json not found: {manifest_path}')
    return json.loads(read_file(manifest_path, 'utf-8'))


def get_outputs(manifest):
    """Return manifest['outputs'] as a dict (empty if missing)."""
    outputs = manifest.get('outputs')
    return outputs if isinstance(outputs, dict) else {}


def file_exists(p):
    return bool(p) and path.exists(p)


def build_manifest(title, source='', outputs=None, *, author=''):
    """Build a manifest dict (port of content-pipeline manifest.build_manifest)."""
    return {
        'version': MANIFEST_SCHEMA_VERSION,
        'created': datetime.now().isoformat(timespec='seconds'),
        'source': source,
        'title': title,
        'author': author,
        'outputs': outputs or {},
    }


def write_manifest(manifest, out_dir):
    """Write manifest to out_dir/manifest.json, return the path."""
    os.makedirs(out_dir, exist_ok=True)
    p = path.join(out_dir, 'manifest.json')
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return p


def resolve_out_dir(given=None):
    """Resolve output dir: CLI > CONTENT_PIPELINE_OUTPUT env > 'output'."""
    d = given or os.environ.get('CONTENT_PIPELINE_OUTPUT', 'output').strip() or 'output'
    os.makedirs(d, exist_ok=True)
    return d


def infer_outputs(manifest):
    """Return list of non-empty outputs keys, in PLATFORM_ORDER."""
    outputs = get_outputs(manifest)
    keys = []
    for k in PLATFORM_ORDER:
        v = outputs.get(k)
        if isinstance(v, dict) and v:
            keys.append(k)
    return keys


def status_print(status, message, url=None):
    """Pretty-print a publish result line with a status icon."""
    icons = {
        'success': '✅', 'assisted': '🔵', 'manual': '📋',
        'skipped': '⏭️', 'error': '❌',
    }
    icon = icons.get(status, '❌')
    line = f'{icon} {message}'
    if url:
        line += f' → {url}'
    print(f'{timestr()} {line}')


def add_common_args(parser):
    """Add the manifest positional + --preview/--headless flags shared by all subcommands."""
    parser.add_argument("manifest", help="path to manifest.json")
    parser.add_argument(
        "-p", "--preview", action="store_true",
        help="fill content but do NOT click publish (keep browser open for review)",
    )
    parser.add_argument(
        "-H", "--headless", action="store_true",
        help="run Chromium in headless mode (default: visible browser for login/review)",
    )
    return parser


def hold_browser(msg="浏览器已打开。请在页面中审阅/手动完成后，回到终端按回车关闭。"):
    """Keep the (visible) browser open until the user presses Enter. No-op in headless."""
    print(f'\n{timestr()} {msg}')
    try:
        input()
    except EOFError:
        pass
