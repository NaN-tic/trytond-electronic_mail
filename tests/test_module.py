
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate

from trytond.config import config
from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction

# Set a data path since the module stores email attachment content in data dir
config.set('database', 'path', '/tmp/')


class ElectronicMailTestCase(ModuleTestCase):
    'Test ElectronicMail module'
    module = 'electronic_mail'

    @with_transaction()
    def test_email_message_extraction(self):
        """
        Create from email functionality extracts info from
        an email.message. Test the extraction for multiple types
        """
        pool = Pool()
        Mail = pool.get('electronic.mail')
        Mailbox = pool.get('electronic.mail.mailbox')

        # 1: multipart/alternative
        message = MIMEMultipart('alternative')

        message['date'] = formatdate()
        message['Subject'] = "Link"
        message['From'] = "pythonistas@example.com"
        message['To'] = "trytonistas@example.com"
        text = """Hi!\nHow are you?\nHere is the link you wanted:
        http://www.python.org/
        http://www.tryton.org/
        """
        html = """\
        <html>
          <head></head>
          <body>
            <p>Hi!<br>
               How are you?<br>
               Here is the <a href="http://www.python.org">link</a> you wanted.
            </p>
          </body>
        </html>
        """
        part1 = MIMEText(text, 'plain')
        part2 = MIMEText(html, 'html')
        message.attach(part1)
        message.attach(part2)

        mailbox = Mailbox.create([{
                    'name': 'Mailbox',
                    }])[0]
        mail = Mail.create_from_mail(message, mailbox)

        self.assertEqual(mail.subject, message['Subject'])
        self.assertEqual(mail.from_, message['From'])
        self.assertEqual(mail.to, message['To'])


del ModuleTestCase
