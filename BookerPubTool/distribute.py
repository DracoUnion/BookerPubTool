# -*- coding: utf-8 -*-

"""Content distribution helpers shared by the publish subcommands.

Ports the manifest handling from content-pipeline's
scripts/distribute/distribute.ts + cdp-utils.ts.
"""

import json
import os
from os import path
from .util import timestr, read_file


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
