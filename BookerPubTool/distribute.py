# -*- coding: utf-8 -*-

"""Shared helpers for the publish subcommands.

Ports the status-printing / browser-hold behaviour from content-pipeline's
distribute skill; the publish commands now take their content directly from
CLI arguments instead of a manifest.json.
"""

from .util import timestr


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


def hold_browser(msg="浏览器已打开。请在页面中审阅/手动完成后，回到终端按回车关闭。"):
    """Keep the (visible) browser open until the user presses Enter. No-op in headless."""
    print(f'\n{timestr()} {msg}')
    try:
        input()
    except EOFError:
        pass