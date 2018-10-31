# This file is part electronic_mail module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
"Electronic Mail test suite"
import unittest
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate

import trytond.tests.test_tryton
from trytond.config import config
from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.transaction import Transaction

# Set a data path since the module stores email attachment content in data dir
config.set('database', 'path', '/tmp/')

USER_TYPES = ('owner_user_%s', 'read_user_%s', 'write_user_%s')


def create_user(name):
    """
    Creates a new user and returns it
    """
    pool = Pool()
    ModelData = pool.get('ir.model.data')
    User = pool.get('res.user')

    group_email_admin_id = ModelData.get_id(
        'electronic_mail', 'group_email_admin')
    group_email_user_id = ModelData.get_id(
        'electronic_mail', 'group_email_user')

    return User.create([{
                'login': name,
                'name': name,
                'groups': [
                    ('add', [group_email_admin_id, group_email_user_id]),
                    ],
                }])[0]


def create_users(no_of_sets=1):
    """
    A set of user is:
        1 Owner
        1 Read user
        1 Write User
    :return: List of tuple of three users
    """
    created_users = []
    for iteration in range(1, no_of_sets + 1):
        created_users.append(
            tuple(create_user(user_type % iteration)
                for user_type in USER_TYPES))
    return created_users


class ElectronicMailTestCase(ModuleTestCase):
    """
    Test Electronic Mail Module
    """
    module = 'electronic_mail'

    # def setUp(self):
    #     self.Mailbox = POOL.get('electronic.mail.mailbox')
    #     self.Mail = POOL.get('electronic.mail')
    #     self.ModelData = POOL.get('ir.model.data')
    #     self.User = POOL.get('res.user')

    @with_transaction()
    def test_mailbox_read_rights(self):
        '''
        Read access rights Test
        '''
        pool = Pool()
        Mailbox = pool.get('electronic.mail.mailbox')

        # Create Users for testing access
        user_set_1, user_set_2 = create_users(no_of_sets=2)

        # Create a mailbox with a user set
        Mailbox.create([{
                    'name': 'Parent Mailbox',
                    'user': user_set_1[0],
                    'read_users': [('add', [user_set_1[1]])],
                    'write_users': [('add', [user_set_1[2]])],
                    }])

        # Create a mailbox 2 with RW users of set 1 + set 2
        Mailbox.create([{
                    'name': 'Child Mailbox',
                    'user': user_set_2[0],
                    'read_users': [('add', [user_set_1[1], user_set_2[1]])],
                    'write_users': [('add', [user_set_1[2], user_set_2[2]])],
                    }])

        # Directly test the mailboxes each user has access to
        expected_results = {
            Transaction().user: 2,
            user_set_1[0].id: 2,  # 1,
            user_set_2[0].id: 2,  # 1,
            user_set_1[1].id: 2,
            user_set_2[1].id: 2,  # 1,
            user_set_1[2].id: 2,
            user_set_2[2].id: 2,  # 1,
            }
        for user_id, mailbox_count in list(expected_results.items()):
            with Transaction().set_user(user_id):
                mailboxes = Mailbox.search([], count=True)
                self.assertEqual(mailboxes, mailbox_count)

    @with_transaction()
    def test_mail_create_access_rights(self):
        """
        Create access rights Test

        Create Three Users
            user_r, user_w, user_o

        Create a mailbox with write access to user_w and read access
        to user_r and owner as user_o

        Try various security combinations for create
        """
        pool = Pool()
        Mail = pool.get('electronic.mail')
        Mailbox = pool.get('electronic.mail.mailbox')

        user_o, user_r, user_w = create_users(no_of_sets=1)[0]
        mailbox = Mailbox.create([{
                    'name': 'Mailbox',
                    'user': user_o,
                    'read_users': [('add', [user_r])],
                    'write_users': [('add', [user_w])],
                    }])[0]

        # Raise exception when writing a mail with the read user
        with Transaction().set_user(user_r):
            self.assertRaises(Exception, Mail.create, [{
                        'from_': 'Test',
                        'mailbox': mailbox,
                        }])

        # Creating mail with the write user
        with Transaction().set_user(user_w):
            self.assertTrue(Mail.create, [{
                        'from_': 'Test',
                        'mailbox': mailbox.id,
                        }])

        # Create an email as mailbox owner
        with Transaction().set_user(user_o):
            self.assertTrue(Mail.create, [{
                        'from_': 'Test',
                        'mailbox': mailbox.id,
                        }])

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

        current_user = Transaction().user
        mailbox = Mailbox.create([{
                    'name': 'Mailbox',
                    'user': current_user,
                    'read_users': [('add', [current_user])],
                    'write_users': [('add', [current_user])],
                    }])[0]
        mail = Mail.create_from_mail(message, mailbox)

        self.assertEqual(mail.subject, message['Subject'])
        self.assertEqual(mail.from_, message['From'])
        self.assertEqual(mail.to, message['To'])


def suite():
    "Electronic mail test suite"
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            ElectronicMailTestCase))
    return suite
