import base64
import unittest
from email.message import EmailMessage
from unittest.mock import patch

from lxml import html
from proteus import Model
from trytond.pool import Pool
from trytond.tests.test_tryton import drop_db
from trytond.tests.tools import activate_modules
from trytond.transaction import Transaction


class TestMailRendering(unittest.TestCase):
    def setUp(self):
        drop_db()
        super().setUp()

    def tearDown(self):
        drop_db()
        super().tearDown()

    def test(self):
        config = activate_modules('electronic_mail')
        Mailbox = Model.get('electronic.mail.mailbox')
        mailbox = Mailbox(name='Rendering')
        mailbox.save()
        png = base64.b64decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8'
            '/x8AAwMCAO+aX1cAAAAASUVORK5CYII=')
        content = '''<html><head><head>
<style><!--
@import url("https://example.invalid/styles.css");
@font-face {font-family: Private; src: url("https://example.invalid/font");}
p.MsoNormal {margin:0cm; font-size:12pt; color:#123456;}
.signature td {padding:5px; vertical-align:middle;}
--></style>
<link rel="stylesheet" href="file:///private.css">
</head><body style="font-family:Arial;font-size:11pt">
<script>UNWANTED_SCRIPT_TEXT</script>
<p class="MsoNormal">First paragraph: cafè</p>
<p class="MsoNormal">&nbsp;</p>
<p class="MsoNormal">Second paragraph</p>
<p><img src="cid:image1" width="1061" height="431"
    style="width:11.05in;height:4.4916in" onerror="alert(1)"></p>
<p><img src="cid:image10" alt="Second screenshot"></p>
<p><img src="cid:missing" alt="Unavailable image"></p>
<table class="signature" width="380" cellspacing="0" cellpadding="0"
    style="border-collapse:collapse;table-layout:fixed">
<tr><td><img src="cid:image1" width="177" height="62"></td>
<td style="text-align:center;color:red">Support<br>Telephone</td></tr>
<tr><td colspan="2">Legal notice</td></tr></table>
<blockquote style="border-left:2px solid blue;padding-left:1em">
<p>Earlier message</p></blockquote>
<div style="position:absolute;z-index:999;background:url(https://example.invalid/pixel)">
Normal flow</div><a href="javascript:alert(1)">Unsafe link</a>
</body></html>'''
        message = EmailMessage()
        message['From'] = 'Sender <sender@example.com>'
        message['To'] = 'Recipient <recipient@example.com>'
        message['Subject'] = 'Invoice <img src=x onerror=alert(1)> & details'
        message.set_content('Plain alternative')
        message.add_alternative(content, subtype='html', charset='iso-8859-1')
        body = message.get_payload()[-1]
        body.add_related(png, maintype='image', subtype='png', cid='<image1>')
        body.add_related(png + b'second', maintype='image', subtype='png',
            cid='<image10>', cte='quoted-printable')
        with Transaction().start(config.database_name, config.user,
                context=config.context):
            Mail = Pool().get('electronic.mail')
            with (patch('urllib.request.urlopen', side_effect=AssertionError(
                        'Rendering must not fetch stylesheets')),
                    patch('requests.sessions.Session.request',
                        side_effect=AssertionError('Unexpected HTTP request'))):
                mail = Mail.create_from_mail(message, mailbox.id)
                preview = html.document_fromstring(mail.preview)
                body_html = html.document_fromstring(bytes(mail.body_html))
            self.assertEqual(preview.find('.//h1').text, str(message['Subject']))
            self.assertIn('Sender <sender@example.com>',
                preview.find('.//header').text_content())
            self.assertNotIn('None', preview.find('.//header').text_content())
            rendered, = preview.xpath('//div[@class="mail-body"]')
            self.assertEqual(len(rendered.findall('.//table')), 1)
            self.assertEqual(len(rendered.findall('.//td')), 3)
            self.assertEqual(rendered.findall('.//td')[-1].get('colspan'), '2')
            paragraphs = rendered.findall('.//p')
            self.assertEqual(paragraphs[0].text_content(), 'First paragraph: cafè')
            self.assertEqual(paragraphs[1].text_content(), '\xa0')
            self.assertEqual(paragraphs[2].text_content(), 'Second paragraph')
            self.assertIn('font-size:12pt',
                paragraphs[0].get('style').replace(' ', ''))
            self.assertIn('padding:5px',
                rendered.find('.//td').get('style').replace(' ', ''))
            self.assertIn('border-left:',
                rendered.find('.//blockquote').get('style'))
            images = rendered.findall('.//img')
            self.assertEqual(len(images), 4)
            self.assertEqual(base64.b64decode(images[0].get('src').split(',')[1]),
                png)
            self.assertEqual(base64.b64decode(images[1].get('src').split(',')[1]),
                png + b'second')
            self.assertIsNone(images[2].get('src'))
            for image in images:
                self.assertIn('max-width:100%', image.get('style'))
                self.assertIn('height:auto', image.get('style'))
            self.assertFalse(rendered.xpath('.//script | .//style | .//link'))
            self.assertFalse(rendered.xpath('.//*[@onerror]'))
            self.assertFalse(rendered.xpath('.//a[@href]'))
            self.assertNotIn('UNWANTED_SCRIPT_TEXT', rendered.text_content())
            self.assertNotIn('MsoNormal', rendered.text_content())
            styles = ''.join(rendered.xpath('.//@style'))
            self.assertNotIn('position:', styles)
            self.assertNotIn('url(', styles)
            self.assertFalse(body_html.xpath('//header'))
            self.assertEqual(len(body_html.xpath('//html')), 1)
            self.assertIn('First paragraph: cafè', mail.body)

            plain = EmailMessage()
            plain['From'] = 'sender@example.com'
            plain['To'] = 'recipient@example.com'
            plain['Subject'] = 'Plain text'
            plain.set_content('First line\n\n  Indented <literal>\nhttps://example.com')
            mail = Mail.create_from_mail(plain, mailbox.id)
            preview = html.document_fromstring(mail.preview)
            pre, = preview.xpath('//pre')
            self.assertIn('First line\n\n  Indented <literal>', pre.text_content())
            self.assertIn('white-space:pre-wrap', pre.get('style'))
            self.assertFalse(pre.xpath('.//literal'))
            self.assertEqual(pre.find('.//a').get('href'), 'https://example.com')
