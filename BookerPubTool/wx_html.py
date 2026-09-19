# -*- coding: utf-8 -*-
"""
Markdown → 微信公众号 HTML 排版（vendored 自 BookerMarkdownTool/wx_html.py）。

提供可编程接口 render_markdown_file() / render_markdown_text()。
"""

import html as html_module
import os
import re
from argparse import RawTextHelpFormatter

try:
    import markdown as md_lib
    HAS_MARKDOWN = True
except ImportError:
    HAS_MARKDOWN = False

try:
    from pygments import highlight as pyg_highlight
    from pygments.lexers import get_lexer_by_name, guess_lexer, TextLexer
    from pygments.formatters import HtmlFormatter
    HAS_PYGMENTS = True
except ImportError:
    HAS_PYGMENTS = False

try:
    from premailer import transform as premailer_transform
    HAS_PREMAILER = True
except ImportError:
    HAS_PREMAILER = False

THEMES = {
    '01fish': {
        'bg':               '#F2EDE3',
        'text':             '#333333',
        'heading':          '#1A3328',
        'accent':           '#C44536',
        'link':             '#C44536',
        'code_bg':          '#f0ece4',
        'code_border':      '#ddd8ce',
        'code_text':        '#1A3328',
        'pre_bg':           '#1A3328',
        'pre_border':       'rgba(196,69,54,0.15)',
        'pre_text':         '#F2EDE3',
        'syntax': {
            'keyword':  '#C44536', 'string': '#A8C97F', 'comment': '#7A8C80',
            'number':   '#D4A76A', 'func':   '#8FBCBB', 'type':   '#B48EAD',
            'operator': '#7A8C80',
        },
        'blockquote_border': '#1A3328',
        'blockquote_bg':     '#f0ece4',
        'table_header_bg':   '#1A3328',
        'table_header_text': '#F2EDE3',
        'table_stripe':      '#f0ece4',
        'table_border':      '#D4DDD7',
        'hr_color':          '#C44536',
    },
    'chinese': {
        'bg': '#F9F5F1', 'text': '#333333', 'heading': '#8B0000', 'accent': '#C41E3A',
        'link': '#C41E3A', 'code_bg': '#FFF8F0', 'code_border': '#E8D5C4',
        'code_text': '#8B0000', 'blockquote_border': '#8B0000', 'blockquote_bg': '#FFF8F0',
        'table_header_bg': '#8B0000', 'table_header_text': '#FFFFFF',
        'table_stripe': '#FFF8F0', 'table_border': '#E8D5C4', 'hr_color': '#C41E3A',
    },
    'apple': {
        'bg': '#FFFFFF', 'text': '#1D1D1F', 'heading': '#1D1D1F', 'accent': '#0066CC',
        'link': '#0066CC', 'code_bg': '#F5F5F7', 'code_border': '#E5E5E5',
        'code_text': '#1D1D1F', 'blockquote_border': '#0066CC', 'blockquote_bg': '#F5F5F7',
        'table_header_bg': '#1D1D1F', 'table_header_text': '#FFFFFF',
        'table_stripe': '#F5F5F7', 'table_border': '#E5E5E5', 'hr_color': '#D2D2D7',
    },
}

FONT_SIZES = {'small': '14px', 'medium': '15px', 'large': '16px'}


def build_css(theme_name, font_size_name):
    t = THEMES[theme_name]
    fs = FONT_SIZES[font_size_name]
    lh = '1.8' if font_size_name == 'large' else '1.75'
    return f"""
/* md2wechat_formatter — {theme_name} theme */
* {{ margin: 0; padding: 0; }}
body {{ background: {t['bg']}; padding: 0; margin: 0; }}
.tip {{ background: #eee; padding: 10px; text-align: center; font-size: 13px; color: #999; margin-bottom: 0; font-family: -apple-system, 'PingFang SC', sans-serif; }}
.content {{ max-width: 100%; margin: 0 auto; padding: 24px 16px 40px; font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', 'Helvetica Neue', sans-serif; font-size: {fs}; line-height: {lh}; color: {t['text']}; word-wrap: break-word; overflow-wrap: break-word; letter-spacing: 0.5px; }}
.content h1 {{ font-size: 24px; font-weight: 700; color: {t['heading']}; margin: 36px 0 16px; padding-bottom: 8px; border-bottom: 2px solid {t['accent']}; letter-spacing: 1px; }}
.content h2 {{ font-size: 20px; font-weight: 700; color: {t['heading']}; margin: 32px 0 14px; padding-bottom: 6px; border-bottom: 1px solid {t['accent']}; }}
.content h3 {{ font-size: 17px; font-weight: 600; color: {t['heading']}; margin: 24px 0 10px; }}
.content h4, .content h5, .content h6 {{ font-size: {fs}; font-weight: 600; color: {t['heading']}; margin: 20px 0 8px; }}
.content p {{ margin: 0 0 16px; text-align: justify; }}
.content a {{ color: {t['link']}; text-decoration: none; border-bottom: 1px solid {t['link']}; word-break: break-all; }}
.content strong {{ color: {t['accent']}; font-weight: 600; }}
.content em {{ font-style: italic; }}
.content code {{ font-family: 'SF Mono', Menlo, Consolas, monospace; font-size: 0.88em; background: {t['code_bg']}; border: 1px solid {t['code_border']}; border-radius: 3px; padding: 2px 5px; color: {t['code_text']}; word-break: break-all; }}
.content pre {{ background: {t.get('pre_bg', t['code_bg'])}; border: 1px solid {t.get('pre_border', t['code_border'])}; border-radius: 6px; padding: 14px 16px; overflow-x: auto; margin: 0 0 16px; }}
.content pre code {{ background: none; border: none; padding: 0; border-radius: 0; font-size: 13px; line-height: 1.6; color: {t.get('pre_text', t['text'])}; }}
.content blockquote {{ margin: 0 0 16px; padding: 12px 16px; border-left: 4px solid {t['blockquote_border']}; background: {t['blockquote_bg']}; color: #666; border-radius: 0 4px 4px 0; }}
.content blockquote p {{ margin: 0; }}
.content blockquote p + p {{ margin-top: 8px; }}
.content ul, .content ol {{ margin: 0 0 16px; padding-left: 24px; }}
.content li {{ margin-bottom: 6px; }}
.content li > ul, .content li > ol {{ margin: 4px 0 4px; padding-left: 20px; }}
.content ul ul {{ list-style-type: circle; }}
.content ul ul ul {{ list-style-type: square; }}
.content li p {{ margin: 0; }}
.content table {{ width: 100%; border-collapse: collapse; margin: 0 0 16px; font-size: 14px; table-layout: auto; }}
.content thead th {{ background: {t['table_header_bg']}; color: {t['table_header_text']}; font-weight: 600; padding: 10px 12px; text-align: left; border: 1px solid {t['table_border']}; }}
.content tbody td {{ padding: 10px 12px; border: 1px solid {t['table_border']}; vertical-align: top; }}
.content tbody tr:nth-child(even) td {{ background: {t['table_stripe']}; }}
.content hr {{ border: none; height: 2px; background: {t['hr_color']}; margin: 28px 0; opacity: 0.3; }}
.content img {{ max-width: 100%; height: auto; border-radius: 4px; margin: 8px 0; }}
"""


def build_pygments_style(theme):
    if not HAS_PYGMENTS or 'syntax' not in theme:
        return None
    s = theme['syntax']
    return {
        'Keyword': s['keyword'], 'Keyword.Constant': s['keyword'],
        'Keyword.Declaration': s['keyword'], 'Keyword.Namespace': s['keyword'],
        'Keyword.Type': s['type'], 'Name.Builtin': s['func'], 'Name.Function': s['func'],
        'Name.Function.Magic': s['func'], 'Name.Class': s['type'],
        'Name.Decorator': s['func'], 'Literal.String': s['string'],
        'Literal.String.Backtick': s['string'], 'Literal.String.Double': s['string'],
        'Literal.String.Single': s['string'], 'Literal.String.Escape': s['number'],
        'Literal.Number': s['number'], 'Literal.Number.Integer': s['number'],
        'Literal.Number.Float': s['number'], 'Comment': s['comment'],
        'Comment.Single': s['comment'], 'Comment.Multiline': s['comment'],
        'Comment.Hashbang': s['comment'], 'Operator': s['operator'],
        'Operator.Word': s['keyword'], 'Punctuation': s.get('operator', '#7A8C80'),
    }


def highlight_code(code_text, lang, theme):
    if not HAS_PYGMENTS or 'syntax' not in theme:
        return html_module.escape(code_text)
    style_map = build_pygments_style(theme)
    try:
        lexer = get_lexer_by_name(lang) if lang else guess_lexer(code_text)
    except Exception:
        lexer = TextLexer()
    from pygments import lex
    result = []
    for token_type, token_value in lex(code_text, lexer):
        escaped = html_module.escape(token_value)
        color = None
        tt = token_type
        while tt:
            key = str(tt)
            if key.startswith('Token.'):
                key = key[6:]
            if key in style_map:
                color = style_map[key]
                break
            tt = tt.parent
        result.append(f'<span style="color:{color}">{escaped}</span>' if color else escaped)
    return ''.join(result)


def strip_frontmatter(text):
    if text.startswith('---'):
        end = text.find('---', 3)
        if end != -1:
            return text[end + 3:].lstrip('\n')
    return text


def _ensure_blank_line_before_list(text):
    lines = text.split('\n')
    result = []
    in_fenced_code = False
    list_marker_re = re.compile(r'^(\s*)([-*+]|\d+\.)\s+')
    for i, line in enumerate(lines):
        stripped = line.strip()
        if re.match(r'^`{3,}', stripped):
            in_fenced_code = not in_fenced_code
            result.append(line)
            continue
        if in_fenced_code:
            result.append(line)
            continue
        if list_marker_re.match(line) and i > 0:
            prev_idx = i - 1
            while prev_idx >= 0 and lines[prev_idx].strip() == '':
                prev_idx -= 1
            if prev_idx >= 0:
                prev_line = lines[prev_idx]
                if (not list_marker_re.match(prev_line)
                        and not prev_line.strip().startswith('#')
                        and not re.match(r'^`{3,}', prev_line.strip())
                        and lines[i - 1].strip() != ''):
                    result.append('')
        result.append(line)
    return '\n'.join(result)


def _normalize_list_indent(text):
    lines = text.split('\n')
    result = []
    in_fenced_code = False
    for line in lines:
        if re.match(r'^`{3,}', line.strip()):
            in_fenced_code = not in_fenced_code
            result.append(line)
            continue
        if in_fenced_code:
            result.append(line)
            continue
        m = re.match(r'^(\s+)([-*+]|\d+\.)\s+(.*)', line)
        if m:
            indent = len(m.group(1))
            marker = m.group(2)
            content = m.group(3)
            level = 1 if indent <= 4 else max(1, indent // (2 if indent % 2 == 0 else 3))
            result.append(f"{'    ' * level}{marker} {content}")
        else:
            result.append(line)
    return '\n'.join(result)


def convert_with_markdown_lib(md_text, theme=None):
    from markdown import markdown as _md
    md_text = _ensure_blank_line_before_list(md_text)
    md_text = _normalize_list_indent(md_text)
    extensions = ['tables', 'fenced_code', 'sane_lists', 'smarty']
    html_out = _md(md_text, extensions=extensions)
    if theme and HAS_PYGMENTS and 'syntax' in theme:
        def _highlight_block(m):
            cls = m.group(1) or ''
            code_html = m.group(2)
            lang = (re.search(r'language-(\w+)', cls) or [None, ''])[1]
            raw = html_module.unescape(code_html)
            return f'<pre><code>{highlight_code(raw, lang, theme)}</code></pre>'
        html_out = re.sub(
            r'<pre><code(?:\s+class="([^"]*)")?>(.*?)</code></pre>', _highlight_block,
            html_out, flags=re.DOTALL)
    return html_out


def inline_format(text):
    text = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', r'<img src="\2" alt="\1" />', text)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'__(.+?)__', r'<strong>\1</strong>', text)
    text = re.sub(r'(?<!\w)\*([^*]+?)\*(?!\w)', r'<em>\1</em>', text)
    text = re.sub(r'`([^`]+?)`', lambda m: '<code>' + html_module.escape(m.group(1)) + '</code>', text)
    return text


def parse_table(lines):
    if len(lines) < 2:
        return ''

    def split_cells(row):
        cells = row.split('|')
        if cells and cells[0].strip() == '':
            cells = cells[1:]
        if cells and cells[-1].strip() == '':
            cells = cells[:-1]
        return [c.strip() for c in cells]

    header_cells = split_cells(lines[0])
    data_start = 2 if (1 < len(lines) and re.match(r'^[\s|:-]+$', lines[1])) else 1
    html = '<table><thead><tr>'
    for cell in header_cells:
        html += f'<th>{inline_format(cell)}</th>'
    html += '</tr></thead><tbody>'
    for row_line in lines[data_start:]:
        html += '<tr>' + ''.join(f'<td>{inline_format(c)}</td>' for c in split_cells(row_line)) + '</tr>'
    html += '</tbody></table>'
    return html


def convert_basic(text, theme=None):
    lines = text.split('\n')
    out = []
    i, n = 0, len(lines)
    para_buf = []

    def flush_paragraph(buf):
        if buf:
            out.append('<p>' + inline_format(' '.join(buf)) + '</p>')
        return []

    while i < n:
        line = lines[i]
        stripped = line.strip()
        code_match = re.match(r'^```(\w*)', stripped)
        if code_match:
            para_buf = flush_paragraph(para_buf)
            lang = code_match.group(1)
            i += 1
            code_lines = []
            while i < n and not lines[i].strip().startswith('```'):
                code_lines.append(lines[i])
                i += 1
            if i < n:
                i += 1
            code_raw = '\n'.join(code_lines)
            highlighted = highlight_code(code_raw, lang, theme) if theme else html_module.escape(code_raw)
            out.append(f'<pre><code>{highlighted}</code></pre>')
            continue
        if '|' in stripped and stripped.startswith('|') and stripped.endswith('|'):
            para_buf = flush_paragraph(para_buf)
            table_lines = []
            while i < n and lines[i].strip().startswith('|') and '|' in lines[i].strip():
                table_lines.append(lines[i].strip())
                i += 1
            out.append(parse_table(table_lines))
            continue
        h_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
        if h_match:
            para_buf = flush_paragraph(para_buf)
            out.append(f'<h{len(h_match.group(1))}>{inline_format(h_match.group(2))}</h{len(h_match.group(1))}>')
            i += 1
            continue
        if re.match(r'^(-{3,}|\*{3,}|_{3,})$', stripped):
            para_buf = flush_paragraph(para_buf)
            out.append('<hr />')
            i += 1
            continue
        if stripped.startswith('>'):
            para_buf = flush_paragraph(para_buf)
            bq_lines = []
            while i < n and lines[i].strip().startswith('>'):
                bq_lines.append(lines[i].strip()[1:].strip())
                i += 1
            bq_html = '<br/>'.join(inline_format(l) for l in bq_lines if l)
            out.append(f'<blockquote><p>{bq_html}</p></blockquote>')
            continue
        for marker_re, tag in [(re.compile(r'^[-*+]\s+(.+)$'), 'ul'),
                               (re.compile(r'^\d+\.\s+(.+)$'), 'ol')]:
            m = marker_re.match(stripped)
            if m:
                para_buf = flush_paragraph(para_buf)
                items = []
                while i < n:
                    mm = marker_re.match(lines[i].strip())
                    if mm:
                        items.append(inline_format(mm.group(1)))
                        i += 1
                    elif lines[i].strip() == '':
                        j = i + 1
                        while j < n and lines[j].strip() == '':
                            j += 1
                        if j < n and marker_re.match(lines[j].strip()):
                            i = j
                            continue
                        break
                    else:
                        break
                out.append(f'<{tag}>' + ''.join(f'<li>{it}</li>' for it in items) + f'</{tag}>')
                break
        else:
            if stripped == '':
                para_buf = flush_paragraph(para_buf)
                i += 1
                continue
            para_buf.append(stripped)
            i += 1
            continue
        continue
    flush_paragraph(para_buf)
    return '\n'.join(out)


def convert_md_to_html(md_text, theme=None):
    if HAS_MARKDOWN:
        return convert_with_markdown_lib(md_text, theme)
    return convert_basic(md_text, theme)


def _rgba_to_hex(rgba_str):
    from colorsys import rgb_to_hls
    m = re.match(r'rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+))?\s*\)', rgba_str)
    if not m:
        return rgba_str
    r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
    a = float(m.group(4)) if m.group(4) else 1.0
    r2 = int(r * a + 255 * (1 - a))
    g2 = int(g * a + 255 * (1 - a))
    b2 = int(b * a + 255 * (1 - a))
    return f'#{r2:02x}{g2:02x}{b2:02x}'


def sanitize_for_wechat(html_str, theme=None):
    result = html_str
    result = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', result)
    result = result.replace('<div ', '<section ')
    result = result.replace('<div>', '<section>')
    result = result.replace('</div>', '</section>')
    unsupported_props = [
        r'overflow-x\s*:\s*[^;]+;?\s*', r'-webkit-overflow-scrolling\s*:\s*[^;]+;?\s*',
        r'overflow-wrap\s*:\s*[^;]+;?\s*', r'word-wrap\s*:\s*[^;]+;?\s*',
        r'table-layout\s*:\s*[^;]+;?\s*', r'border-collapse\s*:\s*[^;]+;?\s*',
        r'letter-spacing\s*:\s*[^;]+;?\s*', r'border-radius\s*:\s*[^;]+;?\s*',
    ]
    for prop_re in unsupported_props:
        result = re.sub(prop_re, '', result)
    result = re.sub(r'rgba?\([^)]+\)', lambda m: _rgba_to_hex(m.group(0)), result)
    if theme:
        stripe_bg = theme.get('table_stripe', '#f0ece4')
        def add_stripe_to_tbody(tb):
            tbody_html = tb.group(0)
            row_index = [0]
            def process_tr(tr):
                row_index[0] += 1
                tr_html = tr.group(0)
                if row_index[0] % 2 == 0:
                    def add_bg(td):
                        tag = td.group(0)
                        if 'background' in tag:
                            return tag
                        if 'style="' in tag:
                            return tag.replace('style="', f'style="background:{stripe_bg}; ')
                        return tag.replace('<td', f'<td style="background:{stripe_bg}"', 1)
                    tr_html = re.sub(r'<td[^>]*>', add_bg, tr_html)
                return tr_html
            return re.sub(r'<tr[\s\S]*?</tr>', process_tr, tbody_html)
        result = re.sub(r'<tbody[\s\S]*?</tbody>', add_stripe_to_tbody, result)
    result = re.sub(r'\s*style="\s*"', '', result)
    return result


def build_html(content_html, css, title=''):
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html_module.escape(title)}</title>
<style>
{css}
</style>
</head>
<body>
<div class="tip">全选下方内容 → 复制 → 粘贴到公众号编辑器（此行不会被复制）</div>
<div class="content">
{content_html}
</div>
</body>
</html>"""


def extract_title(raw, md_text):
    title = ''
    fm_title = re.search(r'^title:\s*(.+)$', raw, re.MULTILINE)
    if fm_title:
        title = fm_title.group(1).strip()
    if not title:
        h1 = re.search(r'^#\s+(.+)$', md_text, re.MULTILINE)
        if h1:
            title = h1.group(1).strip()
    return title


def render_markdown_text(md_text, theme='01fish', font_size='medium', inline=False):
    """将 Markdown 文本渲染为 HTML（完整文档字符串）。"""
    raw = md_text
    md_text = strip_frontmatter(raw)
    title = extract_title(raw, md_text)
    theme_dict = THEMES[theme]
    content_html = convert_md_to_html(md_text, theme_dict)
    css = build_css(theme, font_size)
    full_html = build_html(content_html, css, title)
    if inline:
        if not HAS_PREMAILER:
            raise RuntimeError('--inline 需要 premailer 包：pip install premailer')
        from premailer import transform as _pmt
        full_html = _pmt(full_html, remove_classes=False, strip_important=True,
                         keep_style_tags=False, cssutils_logging_level='CRITICAL')
        full_html = re.sub(
            r'<pre[^>]*>\s*<code([^>]*)>([\s\S]*?)</code>\s*</pre>',
            lambda m: f'<pre{m.group(0).split("<pre")[1].split(">")[0]}><code{m.group(1)}>'
                      f'{m.group(2).replace(chr(10), "<br>")}</code></pre>',
            full_html)
    return full_html


def render_markdown_file(input_path, theme='01fish', font_size='medium',
                         output=None, inline=False):
    """渲染 md 文件为 HTML 并写到 output（默认 [input]_preview.html）。返回输出路径。"""
    with open(input_path, 'r', encoding='utf-8') as f:
        raw = f.read()
    full_html = render_markdown_text(raw, theme=theme, font_size=font_size, inline=inline)
    out_path = output or os.path.splitext(input_path)[0] + '_preview.html'
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(full_html)
    return out_path
