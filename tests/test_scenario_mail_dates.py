import datetime
import os
import time
import unittest
from email.message import Message
from unittest.mock import patch

from proteus import Model
from trytond.pool import Pool
from trytond.tests.test_tryton import drop_db
from trytond.tests.tools import activate_modules
from trytond.transaction import Transaction


class TestMailDates(unittest.TestCase):
    def setUp(self):
        drop_db()
        super().setUp()

    def tearDown(self):
        drop_db()
        super().tearDown()

    def test(self):
        config = activate_modules('electronic_mail')
        Mailbox = Model.get('electronic.mail.mailbox')
        mailbox = Mailbox(name='Dates')
        mailbox.save()
        cases = [
            ('Wed, 30 Sep 2026 09:47:43 +0200',
                datetime.datetime(2026, 9, 30, 7, 47, 43)),
            ('Wed, 30 Sep 2026 08:29:34 +0000',
                datetime.datetime(2026, 9, 30, 8, 29, 34)),
            ('Wed, 30 Sep 2026 00:15:00 +0530',
                datetime.datetime(2026, 9, 29, 18, 45)),
            ('Wed, 30 Sep 2026 23:30:00 -0400',
                datetime.datetime(2026, 10, 1, 3, 30)),
            ('Wed, 30 Sep 2026 08:29:34 -0000',
                datetime.datetime(2026, 9, 30, 8, 29, 34)),
            ('Wed, 30 Sep 2026 08:29:34',
                datetime.datetime(2026, 9, 30, 8, 29, 34)),
            ]
        try:
            for server_timezone in ['UTC', 'Europe/Madrid', 'America/New_York']:
                with patch.dict(os.environ, TZ=server_timezone):
                    time.tzset()
                    with Transaction().start(config.database_name, config.user,
                            context=config.context) as transaction:
                        Mail = Pool().get('electronic.mail')
                        mails = []
                        for date, expected in cases:
                            message = Message()
                            message['Date'] = date
                            message['From'] = 'sender@example.com'
                            message['To'] = 'recipient@example.com'
                            message['Subject'] = 'Date test'
                            message.set_payload('Message')
                            mail = Mail.create_from_mail(message, mailbox.id)
                            self.assertEqual(mail.date, expected)
                            mails.append(mail)
                        ordered = Mail.search([
                                ('id', 'in', [m.id for m in mails[:2]])],
                            order=[('date', 'ASC')])
                        self.assertEqual(ordered, mails[:2])
                        for date in [None, 'Invalid date']:
                            message = Message()
                            if date:
                                message['Date'] = date
                            message['From'] = 'sender@example.com'
                            message['To'] = 'recipient@example.com'
                            message['Subject'] = 'Undated message'
                            before = datetime.datetime.now(datetime.timezone.utc
                                ).replace(tzinfo=None, microsecond=0)
                            mail = Mail.create_from_mail(message, mailbox.id)
                            after = datetime.datetime.now(datetime.timezone.utc
                                ).replace(tzinfo=None)
                            self.assertLessEqual(before, mail.date)
                            self.assertLessEqual(mail.date, after)
                        transaction.commit()
        finally:
            time.tzset()
