import email
import bleach 

def render_email(eml):
    charset = eml.get_body(['html', 'plain']).get_content_charset()
    html = eml.get_body(['html', 'plain']).get_payload(decode=True).decode(
        charset)
    images = {}

    for part in eml.walk():
        content_type = part.get_content_type()
        if content_type.startswith('image/'):
            cid = part.get('Content-ID')
            if cid:
                cid = cid[1:-1]
                images[cid] = 'data:' + content_type + ';base64,' + part.get_payload()

    tags = bleach.sanitizer.ALLOWED_TAGS + ['div', 'img', 'br']
    attributes = bleach.sanitizer.ALLOWED_ATTRIBUTES.copy()
    attributes.update({
            'div': ['dir'],
            'img': ['src', 'alt', 'width', 'height'],
            })
    protocols = bleach.ALLOWED_PROTOCOLS + ['cid']
    html = bleach.clean(html, tags=tags, attributes=attributes, protocols=protocols, strip=True, strip_comments=True)
    html = bleach.linkify(html)

    for cid, image in images.items():
        html = html.replace('cid:' + cid, image)
    return html
       