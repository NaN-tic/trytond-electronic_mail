"""Render MIME messages while preserving their email layout."""

import base64
import logging
from html import escape
from urllib.parse import unquote

import bleach
import tinycss2
from bleach.css_sanitizer import ALLOWED_CSS_PROPERTIES, CSSSanitizer
from cssselect import SelectorError
from lxml import etree, html
from premailer import Premailer


logger = logging.getLogger(__name__)

CSS_PROPERTIES = ALLOWED_CSS_PROPERTIES | {
    'background', 'border', 'border-top', 'border-right', 'border-bottom',
    'border-left', 'border-radius', 'border-collapse', 'border-spacing',
    'box-sizing', 'clear',
    'display', 'height', 'line-height', 'list-style-type', 'margin',
    'margin-top', 'margin-right', 'margin-bottom', 'margin-left',
    'max-width', 'min-width', 'overflow', 'overflow-wrap', 'padding',
    'padding-top', 'padding-right', 'padding-bottom', 'padding-left',
    'table-layout', 'text-indent', 'white-space', 'word-break', 'word-wrap',
    }
IMAGE_TYPES = {
    'image/png', 'image/jpeg', 'image/gif', 'image/webp', 'image/bmp',
    'image/avif', 'image/x-icon', 'image/vnd.microsoft.icon',
    }
TAGS = set(bleach.sanitizer.ALLOWED_TAGS) | {
    'p', 'div', 'span', 'br', 'hr', 'img', 'pre', 'blockquote',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'u', 's', 'strike', 'sub', 'sup',
    'font', 'table', 'caption', 'colgroup', 'col', 'thead', 'tbody', 'tfoot',
    'tr', 'td', 'th',
    }
ATTRIBUTES = {
    '*': ['style', 'dir', 'lang'],
    'a': ['href', 'title'],
    'img': ['src', 'alt', 'title', 'width', 'height', 'border', 'align'],
    'table': ['width', 'height', 'border', 'cellpadding', 'cellspacing',
        'align', 'bgcolor'],
    'tr': ['align', 'valign', 'bgcolor'],
    'td': ['width', 'height', 'colspan', 'rowspan', 'align', 'valign', 'bgcolor'],
    'th': ['width', 'height', 'colspan', 'rowspan', 'align', 'valign', 'bgcolor'],
    'col': ['width', 'span'],
    'colgroup': ['width', 'span'],
    'p': ['align'],
    'div': ['align'],
    'font': ['face', 'size', 'color'],
    'ol': ['start', 'type'],
    'li': ['value'],
    }


class EmailCSSSanitizer(CSSSanitizer):
    """Keep presentation CSS, without resource loads or active expressions."""

    def __init__(self):
        super().__init__(allowed_css_properties=CSS_PROPERTIES,
            allowed_svg_properties=frozenset())

    def sanitize_css(self, style):
        declarations = tinycss2.parse_declaration_list(
            super().sanitize_css(style), skip_comments=True, skip_whitespace=True)
        safe = []
        for declaration in declarations:
            if declaration.type != 'declaration':
                continue
            tokens = list(declaration.value)
            while tokens:
                token = tokens.pop()
                if token.type in {'url', 'bad-url', 'error'}:
                    break
                if token.type == 'function':
                    if token.lower_name in {'url', 'expression', 'var', 'attr'}:
                        break
                    tokens.extend(token.arguments)
                else:
                    tokens.extend(getattr(token, 'content', []))
            else:
                safe.append(declaration)
        return tinycss2.serialize(safe)


def render_email(eml):
    body = eml.get_body(['html', 'plain'])
    if body is None:
        return ''
    payload = body.get_payload(decode=True) or b''
    try:
        content = payload.decode(body.get_content_charset() or 'utf-8',
            errors='replace')
    except LookupError:
        content = payload.decode('utf-8', errors='replace')
    if body.get_content_type() == 'text/plain':
        return ('<div class="mail-body"><pre style="white-space:pre-wrap;'
            'overflow-wrap:anywhere;font-family:inherit">%s</pre></div>'
            % bleach.linkify(escape(content), parse_email=True))
    if not content.strip():
        return ''

    parser = html.HTMLParser(remove_comments=True, no_network=True)
    document = html.document_fromstring(content, parser=parser)
    for element in list(document.iter(
            'script', 'iframe', 'object', 'embed', 'form', 'input', 'button',
            'textarea', 'select', 'link', 'base', 'meta', 'title', 'svg', 'math')):
        if element.getparent() is not None:
            element.drop_tree()

    sanitizer = EmailCSSSanitizer()
    for element in document.iter('style'):
        # cssutils can otherwise fetch @import URLs while parsing a stylesheet,
        # even with Premailer's external stylesheet loading disabled.
        rules = []
        for rule in tinycss2.parse_stylesheet(element.text or '',
                skip_comments=True, skip_whitespace=True):
            if rule.type != 'qualified-rule':
                continue
            declarations = sanitizer.sanitize_css(tinycss2.serialize(rule.content))
            if declarations:
                rules.append('%s {%s}' % (
                        tinycss2.serialize(rule.prelude), declarations))
        element.text = '\n'.join(rules)
    for element in document.xpath('//*[@style]'):
        element.set('style', sanitizer.sanitize_css(element.get('style')))

    normalized = html.tostring(document, encoding='unicode')
    try:
        normalized = Premailer(normalized, allow_network=False,
            allow_loading_external_files=False, disable_link_rewrites=True,
            disable_leftover_css=True, disable_validation=True,
            strip_important=False, include_star_selectors=True,
            align_floating_images=False).transform(pretty_print=False)
    except (ValueError, etree.LxmlError, SelectorError):
        logger.warning('Could not inline email stylesheet; keeping inline styles')
    document = html.document_fromstring(normalized, parser=parser)
    for element in list(document.iter('style', 'head')):
        if element.getparent() is not None:
            element.drop_tree()
    content_body = document.find('body')
    if content_body is None:
        return ''
    content_body.tag = 'div'
    # Keep inherited body presentation inside the message, not on the preview's
    # envelope headers. The result is a fragment, not a nested HTML document.
    content_body.set('style', ';'.join(filter(None, [
                    document.get('style'), content_body.get('style')])))
    rendered = bleach.clean(html.tostring(content_body, encoding='unicode'),
        tags=TAGS, attributes=ATTRIBUTES,
        protocols={'http', 'https', 'mailto', 'tel', 'cid'},
        css_sanitizer=sanitizer, strip=True, strip_comments=True)
    fragment = html.fragment_fromstring(rendered, create_parent='div')
    fragment.set('class', 'mail-body')

    # Prefer resources from the selected HTML body's multipart/related scope.
    related = eml
    for part in eml.walk():
        if part.get_content_type() == 'multipart/related' and body in part.walk():
            related = part
    images = {}
    for part in related.walk():
        content_type = part.get_content_type()
        cid = str(part.get('Content-ID', '')).strip().strip('<>')
        if cid and content_type in IMAGE_TYPES:
            data = part.get_payload(decode=True)
            if data:
                images.setdefault(cid, 'data:%s;base64,%s' % (
                        content_type, base64.b64encode(data).decode('ascii')))
    for image in fragment.iter('img'):
        source = image.get('src', '')
        if source.lower().startswith('cid:'):
            cid = unquote(source[4:]).strip('<>')
            if cid in images:
                image.set('src', images[cid])
            else:
                image.attrib.pop('src', None)
        style = image.get('style', '').rstrip(';')
        image.set('style', style + ';max-width:100% !important;'
            'height:auto !important')
    return html.tostring(fragment, encoding='unicode')


def render_document(body, headers=None):
    """Build a standalone document for the sandboxed mail viewer."""
    envelope = ''
    if headers is not None:
        subject = escape(str(headers.get('Subject') or ''))
        lines = []
        for field, label in [('From', 'Remitent'), ('To', 'Destinatari'),
                ('Cc', 'CC'), ('Date', 'Data')]:
            value = headers.get(field)
            if value:
                lines.append('<div><b>%s:</b> %s</div>' % (
                        label, escape(str(value))))
        envelope = '<header><h1>%s</h1>%s</header>' % (subject, ''.join(lines))
    return '''<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body { margin: 12px; font: 14px/1.4 sans-serif; color: #222; background: white; }
body > header { padding-bottom: 12px; margin-bottom: 16px;
    border-bottom: 1px solid #ddd; overflow-wrap: anywhere; }
body > header h1 { font-size: 20px; margin: 0 0 8px; }
.mail-body { display: flow-root; max-width: 100%%; overflow-x: auto;
    overflow-wrap: break-word; }
.mail-body table { max-width: 100%%; }
</style></head><body>%s%s</body></html>''' % (envelope, body)
