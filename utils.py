import bleach

def render_email(eml):
    body = eml.get_body(['html', 'plain'])

    html = ''
    if body:
        charset = body.get_content_charset('utf-8')
        try:
            payload = body.get_payload(decode=True)
        except:
            pass
        if payload:
            try:
                html = payload.decode(charset)
            except:
                try:
                    html = body.get_payload(decode=True).decode('utf-8')
                except:
                    pass

    images = {}
    for part in eml.walk():
        content_type = part.get_content_type()
        if content_type.startswith('image/'):
            cid = part.get('Content-ID')
            if cid:
                cid = cid[1:-1]
                images[cid] = ('data:' + content_type + ';base64,' +
                    part.get_payload())

    # support bleach 6.0.0
    allowed_tags = bleach.sanitizer.ALLOWED_TAGS
    if isinstance(allowed_tags, frozenset):
        tags = list(allowed_tags) + ['div', 'img', 'br']
    else:
        tags = allowed_tags + ['div', 'img', 'br']

    attributes = bleach.sanitizer.ALLOWED_ATTRIBUTES.copy()
    attributes.update({
            'div': ['dir'],
            'img': ['src', 'alt', 'width', 'height'],
            })

    # support bleach 6.0.0
    allowed_protocols = bleach.ALLOWED_PROTOCOLS
    if isinstance(allowed_tags, frozenset):
        protocols = list(allowed_protocols) + ['cid']
    else:
        protocols = allowed_protocols + ['cid']

    html = bleach.clean(html, tags=tags, attributes=attributes,
        protocols=protocols, strip=True, strip_comments=True)
    html = bleach.linkify(html)

    for cid, image in images.items():
        html = html.replace('cid:' + cid, image)
    return html
