# This file is part of electronic_mail module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.

import chardet
import logging
import mimetypes
import os
import base64
try:
    import hashlib
except ImportError:
    hashlib = None
    import md5
from datetime import datetime
from email import message_from_bytes
from email.utils import parsedate, getaddresses
from email.header import decode_header, make_header
from sys import getsizeof
from time import mktime
from trytond.i18n import gettext
from trytond.exceptions import UserError

try:
    from emailvalid import check_email
    CHECK_EMAIL = True
except ImportError:
    CHECK_EMAIL = False
    msg = "Unable to import emailvalid. Email validation disabled."
    logging.getLogger('Electronic Mail').warning(msg)

from trytond.config import config
from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import Pool
from trytond.pyson import Bool, Eval
from trytond.transaction import Transaction

__all__ = ['Mailbox', 'ElectronicMail']


def _make_header(data, charset='utf-8'):
    return str(make_header([(data or "", charset)]))


def _decode_header(data):
    if data is None:
        return
    decoded_headers = decode_header(data)
    headers = []
    for decoded_str, charset in decoded_headers:
        if not isinstance(decoded_str, str):
            if charset:
                headers.append(str(decoded_str, charset))
            else:
                headers.append(str(decoded_str, 'utf8'))
        else:
            headers.append(decoded_str)
    return " ".join(headers)


def _decode_body(part):
    charset = str(part.get_content_charset())
    payload = part.get_payload(decode=True)
    if not payload:
        return ''
    if not charset or charset == 'None':
        charset = chardet.detect(payload).get('encoding')
    try:
        return payload.decode(charset or 'utf-8').strip()
    except UnicodeDecodeError:
        return ''


class Mailbox(ModelSQL, ModelView):
    "Mailbox"
    __name__ = "electronic.mail.mailbox"

    name = fields.Char('Name', required=True)

    @classmethod
    def __setup__(cls):
        super(Mailbox, cls).__setup__()
        cls._buttons.update({
                'create_menu': {
                    'invisible': Bool(Eval('menu')),
                    'icon': 'tryton-ok',
                    },
                })

    @classmethod
    def delete(cls, mailboxes):
        # TODO Add a wizard that pops up a window telling that menu is deleted
        # and that in order to see it, you must type ALT+T or refresh the menu
        # by clicking menu User > Refresh Menu
        pool = Pool()
        Menu = pool.get('ir.ui.menu')
        Action = pool.get('ir.action')
        ActWindow = pool.get('ir.action.act_window')
        ActionKeyword = pool.get('ir.action.keyword')
        ActWindowView = pool.get('ir.action.act_window.view')

        act_windows = []
        actions = []
        keywords = []
        menus = []
        act_window_views = []
        for mailbox in mailboxes:
            act_windows.extend(ActWindow.search([
                    ('res_model', '=', 'electronic.mail'),
                    ('domain', '=', '[["mailbox", "=", %d]]' % mailbox.id),
                    ]))
            actions.extend([a_w.action for a_w in act_windows])
            keywords.extend(ActionKeyword.search([('action', 'in', actions)]))
            menus.extend([k.model for k in keywords])
            act_window_views.extend(ActWindowView.search([
                    ('act_window', 'in', [a_w.id for a_w in act_windows]),
                    ]))

        ActWindowView.delete(act_window_views)
        ActWindow.delete(act_windows)
        ActionKeyword.delete(keywords)
        Action.delete(actions)
        Menu.delete(menus)
        return super(Mailbox, cls).delete(mailboxes)

    @classmethod
    def write(cls, *args):
        # TODO Add a wizard that pops up a window telling that menu is updated
        # and that in order to see it, you must type ALT+T or refresh the menu
        # by clicking menu User > Refresh Menu
        acts = iter(args)
        for mailboxes, values in zip(acts, acts):
            if 'name' in values:
                pool = Pool()
                ActWindow = pool.get('ir.action.act_window')
                Action = pool.get('ir.action')
                ActionKeyword = pool.get('ir.action.keyword')
                Menu = pool.get('ir.ui.menu')

                actions = []
                menus = []
                for mailbox in mailboxes:
                    act_windows = ActWindow.search([
                            ('res_model', '=', 'electronic.mail'),
                            ('domain', '=',
                                '[["mailbox", "=", %d]]' % mailbox.id),
                            ])
                    actions.extend([a_w.action for a_w in act_windows])
                    keywords = ActionKeyword.search([
                            ('action', 'in', actions)])
                    menus.extend([k.model for k in keywords])
                Action.write(actions, {'name': values['name']})
                Menu.write(menus, {'name': values['name']})
        super(Mailbox, cls).write(*args)

    @classmethod
    @ModelView.button
    def create_menu(cls, mailboxes):
        # TODO Add a wizard that pops up a window telling that menu is created
        # and that in order to see it, you must type ALT+T or refresh the menu
        # by clicking menu User > Refresh Menu
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        Menu = pool.get('ir.ui.menu')
        Action = pool.get('ir.action')
        ActWindow = pool.get('ir.action.act_window')
        ActionKeyword = pool.get('ir.action.keyword')
        ActWindowView = pool.get('ir.action.act_window.view')
        View = pool.get('ir.ui.view')

        for mailbox in mailboxes:
            act_windows = ActWindow.search([
                    ('res_model', '=', 'electronic.mail'),
                    ('domain', '=', '[["mailbox", "=", %d]]' % mailbox.id),
                    ])
            actions = [a_w.action for a_w in act_windows]
            keywords = ActionKeyword.search([('action', 'in', actions)])
            menus = [k.model for k in keywords]
        if menus:
            raise UserError(gettext('email_template.menu_exist'))
        data_menu_mailbox, = ModelData.search([
                ('module', '=', 'electronic_mail'),
                ('model', '=', 'ir.ui.menu'),
                ('fs_id', '=', 'menu_mail'),
                ])
        menu_mailbox, = Menu.search([
                ('id', '=', data_menu_mailbox.db_id)
                ])
        actions = Action.create([{
                    'name': mb.name,
                    'type': 'ir.action.act_window',
                    } for mb in mailboxes])
        act_windows = ActWindow.create([{
                    'res_model': 'electronic.mail',
                    'domain': '[["mailbox", "=", %d]]' % mailbox.id,
                    'action': a.id,
                    }
                for mb in mailboxes for a in actions if a.name == mb.name])
        menus = Menu.create([{
                    'parent': menu_mailbox.id,
                    'name': mb.name,
                    'icon': 'tryton-list',
                    'active': True,
                    'sequence': 10,
                    } for mb in mailboxes])
        ActionKeyword.create([{
                    'model': 'ir.ui.menu,%s' % m.id,
                    'action': a_w.id,
                    'keyword': 'tree_open',
                    }
                for mb in mailboxes
                for a_w in act_windows
                for m in menus
                if mb.id == eval(a_w.domain)[0][2] and m.name == mb.name
                ])
        data_views = ModelData.search([
                ('module', '=', 'electronic_mail'),
                ('model', '=', 'ir.ui.view'),
                ['OR',
                    ('fs_id', '=', 'mail_view_tree'),
                    ('fs_id', '=', 'mail_view_form'),
                    ],
                ])
        views = View.search([('id', 'in', [v.db_id for v in data_views])])
        ActWindowView.create([{
                    'act_window': a_w.id,
                    'view': v.id,
                    'sequence': 10 if v.type == 'tree' else 20,
                    } for a_w in act_windows for v in views])
        return 'reload menu'


class ElectronicMail(ModelSQL, ModelView):
    "E-mail"
    __name__ = 'electronic.mail'
    _order_name = 'date'

    mailbox = fields.Many2One('electronic.mail.mailbox', 'Mailbox',
        required=True)
    from_ = fields.Char('From')
    sender = fields.Char('Sender')
    to = fields.Char('To')
    cc = fields.Char('CC')
    bcc = fields.Char('BCC')
    date = fields.DateTime('Date')
    subject = fields.Char('Subject')
    body = fields.Function(fields.Text('Body'), 'get_mail')
    body_html = fields.Function(fields.Text('Body HTML'), 'get_mail')
    body_plain = fields.Function(fields.Text('Body Plain'), 'get_mail')
    deliveredto = fields.Char('Delivered-To')
    reference = fields.Char('References')
    reply_to = fields.Char('Reply-To')
    num_attach = fields.Function(fields.Integer('Number of attachments'),
        'get_mail')
    attachments = fields.Function(fields.Text('Attachments'), 'get_mail')
    message_id = fields.Char('Message-ID', help='Unique Message Identifier')
    in_reply_to = fields.Char('In-Reply-To')
    digest = fields.Char('MD5 Digest', size=32)
    collision = fields.Integer('Collision')
    mail_file = fields.Function(fields.Binary('Mail File',
            filename='mail_file_name'), 'get_mail', setter='set_mail')
    mail_file_name = fields.Function(fields.Char('Mail File Name'), 'get_mail')
    flag_send = fields.Boolean('Sent', readonly=True)
    flag_received = fields.Boolean('Received', readonly=True)
    flag_seen = fields.Boolean('Seen')
    flag_answered = fields.Boolean('Answered')
    flag_flagged = fields.Boolean('Flagged')
    flag_draft = fields.Boolean('Draft')
    flag_recent = fields.Boolean('Recent')
    size = fields.Integer('Size')
    resource = fields.Reference('Resource', selection='get_resource_models',
        select=True)

    @classmethod
    def __setup__(cls):
        super(ElectronicMail, cls).__setup__()
        cls._order.insert(0, ('date', 'DESC'))

    @staticmethod
    def get_resource_models():
        pool = Pool()
        Model = pool.get('ir.model')
        ModelAccess = pool.get('ir.model.access')
        models = Model.search([])
        access = ModelAccess.get_access([m.model for m in models])

        res = [(None, '')]
        for m in models:
            if not access[m.model]['read']:
                continue
            res.append((m.model, m.name))
        return res

    @property
    def all_to(self):
        mail = message_from_bytes(self.mail_file)
        parse_all_to = []
        if mail:
            all_to = getaddresses(mail.get_all('to', []))
            for to in all_to:
                parse_all_to.append((_decode_header(to[0]),
                        _decode_header(to[1])))
        return parse_all_to

    @property
    def all_cc(self):
        mail = message_from_bytes(self.mail_file)
        parse_all_cc = []
        if mail:
            all_cc = getaddresses(mail.get_all('cc', []))
            for cc in all_cc:
                parse_all_cc.append((_decode_header(cc[0]),
                        _decode_header(cc[1])))
        return parse_all_cc

    @property
    def all_bcc(self):
        mail = message_from_bytes(self.mail_file)
        parse_all_bcc = []
        if mail:
            all_bcc = getaddresses(mail.get_all('bcc', []))
            for bcc in all_bcc:
                parse_all_bcc.append(
                    (_decode_header(bcc[0]), _decode_header(bcc[1])))
        return parse_all_bcc

    @staticmethod
    def default_collision():
        return 0

    @staticmethod
    def default_flag_seen():
        return False

    @staticmethod
    def default_flag_answered():
        return False

    @staticmethod
    def default_flag_flagged():
        return False

    @staticmethod
    def default_flag_recent():
        return False

    @classmethod
    def get_rec_name(cls, records, name):
        if not records:
            return {}
        res = {}
        for mail in records:
            # remove \r and \n characters on the subject because SAO
            # detect that "reference" field is modified
            subject = mail.subject and mail.subject.replace( '\r', '') or ''
            subject = subject and subject.replace('\n', '')
            res[mail.id] = '%s (ID: %s)' % (subject, mail.id)
        return res

    def get_body(self, msg):
        """Returns the email body
        """
        maintype_text = {
            'body_plain': "",
            'body_html': ""
        }
        maintype_multipart = maintype_text.copy()
        if msg:
            if not msg.is_multipart():
                decode_body = _decode_body(msg)
                if msg.get_content_subtype() == "html":
                    maintype_text['body_html'] = decode_body
                else:
                    maintype_text['body_plain'] = decode_body
            else:
                for part in msg.walk():
                    maintype = part.get_content_maintype()
                    if maintype == 'text':
                        decode_body = _decode_body(part)
                        if part.get_content_subtype() == "html":
                            maintype_text['body_html'] = decode_body
                        else:
                            maintype_text['body_plain'] = decode_body
                    if (maintype_text['body_plain']
                            and maintype_text['body_html']):
                        break
                    if maintype == 'multipart':
                        for p in part.get_payload():
                            if p.get_content_maintype() == 'text':
                                decode_body = _decode_body(p)
                                if p.get_content_subtype() == 'html':
                                    maintype_multipart['body_html'] = (
                                        decode_body)
                                else:
                                    maintype_multipart['body_plain'] = (
                                        decode_body)
                    elif maintype != 'multipart' and not part.get_filename():
                        decode_body = _decode_body(part)
                        if not maintype_multipart['body_plain']:
                            maintype_multipart['body_plain'] = decode_body
                        if not maintype_multipart['body_html']:
                            maintype_multipart['body_html'] = decode_body
                if not maintype_text['body_plain']:
                    maintype_text['body_plain'] = (
                        maintype_multipart['body_plain'])
                if not maintype_text['body_html']:
                    maintype_text['body_html'] = (
                        maintype_multipart['body_html'])
        return maintype_text

    @staticmethod
    def get_attachments(msg):
        attachments = []
        if msg:
            counter = 1
            for part in msg.walk():
                if part.get_content_maintype() == 'multipart':
                    continue
                if part.get('Content-Disposition') is None:
                    continue
                if part.get_filename():
                    filename = part.get_filename()
                    if not filename:
                        ext = mimetypes.guess_extension(
                            part.get_content_type())
                        if not ext:
                            # Use a generic bag-of-bits extension
                            ext = '.bin'
                        filename = 'part-%03d%s' % (counter, ext)
                    if filename.startswith('=?'):
                        # Filename will be in the following format:
                        # =?utf-8?B?BASE 64 ENCODED NAME?=\n=?utf-8?Q?BASE 64 EXTENSION?=
                        # =?Windows-1252?Q?NAME WITH EXTENSION?=
                        # =?iso-8859-1?Q?NAME WITH EXTENSION?=
                        fparts = []
                        for fpart in filename.split('=?'):
                            if fpart == '':
                                continue
                            try:
                                encoding, bq, value, _ = fpart.split('?')
                            except ValueError:
                                continue
                            #The B represents base64 encoding (RFC 2045)
                            if bq == 'B':
                                bvalue = base64.b64decode(value)
                            #The Q represents an encoding similar to the
                            #“quoted-printable” (RFC 2045)
                            elif bq == 'Q':
                                bvalue = value.encode('ascii', errors='ignore')
                            value = bvalue.decode(encoding, errors='ignore')
                            fparts.append(value)
                        filename = ''.join(fparts)
                    counter += 1

                    data = part.get_payload(decode=True)
                    content_type = part.get_content_type()
                    if not data:
                        continue
                    attachments.append({
                            'filename': filename,
                            'data': data,
                            'content_type': content_type,
                            })
        return attachments

    @staticmethod
    def _get_mail(electronic_mail):
        """
        Returns the mail object from reading the FS
        :param electronic_mail: Browse Record of the mail
        """
        db_name = Transaction().database.name
        value = ''
        if electronic_mail.digest:
            filename = electronic_mail.digest
            if electronic_mail.collision:
                filename = filename + '-' + str(electronic_mail.collision)
            filename = os.path.join(config.get('database', 'path'),
                db_name, 'email', filename[0:2], filename)
            try:
                with open(filename, 'rb') as file_p:
                    value = file_p.read()
            except IOError:
                pass
        return value

    @classmethod
    def get_mail(cls, mails, names):
        result = {}
        for fname in ['body', 'body_plain', 'body_html', 'num_attach',
                'mail_file', 'mail_file_name', 'attachments']:
            result[fname] = {}
        for mail in mails:
            mail_file = cls._get_mail(mail)
            if mail_file:
                result['mail_file'][mail.id] = fields.Binary.cast(mail_file)
                result['mail_file_name'][mail.id] = '%d.txt' % mail.id
                email = message_from_bytes(mail_file)
                body = mail.get_body(email)
                html = body.get('body_html').strip()
                # TODO: Find a better way to know if there's a real HTML body
                if html.startswith('<html') or html.startswith('<meta'):
                    result['body'][mail.id] = body.get('body_html')
                else:
                    result['body'][mail.id] = ('<pre>%s</pre>' %
                        body.get('body_plain'))
                result['body_plain'][mail.id] = body.get('body_plain')
                result['body_html'][mail.id] = body.get('body_html')
                result['num_attach'][mail.id] = len(cls.get_attachments(email))
                result['attachments'][mail.id] = '\n'.join([x['filename'] for x
                        in cls.get_attachments(email)])
            else:
                result['mail_file'][mail.id] = None
                result['mail_file_name'][mail.id] = None
                result['body'][mail.id] = None
                result['body_plain'][mail.id] = None
                result['body_html'][mail.id] = None
                result['num_attach'][mail.id] = None
                result['attachments'][mail.id] = None
        for fname in ['body_plain', 'body_html', 'num_attach', 'mail_file']:
            if fname not in names:
                del result[fname]
        return result

    @classmethod
    def set_mail(cls, records, name, data):
        """Saves an mail to the data path

        :param data: Mail as string
        """
        if data is False or data is None:
            return
        db_name = Transaction().database.name
        # Prepare Directory <DATA PATH>/<DB NAME>/email
        directory = os.path.join(config.get('database', 'path'), db_name)
        if not os.path.isdir(directory):
            os.makedirs(directory, 0o770)
        digest = cls.make_digest(data)
        directory = os.path.join(directory, 'email', digest[0:2])
        if not os.path.isdir(directory):
            os.makedirs(directory, 0o770)
        # Filename <DIRECTORY>/<DIGEST>
        filename = os.path.join(directory, digest)
        collision = 0

        if not os.path.isfile(filename):
            # File doesnt exist already

            # When writing output to the stream, if newline is None, any '\n'
            # characters written are translated to the system default line separator,
            # os.linesep. If newline is '' or '\n', no translation takes place.
            # If newline is any of the other legal values, any '\n' characters
            # written are translated to the given string.
            # https://docs.python.org/3/library/functions.html?highlight=open#open

            with open(filename, 'w', newline='\r\n') as file_p:
                file_p.write(data)
        else:
            # File already exists, may be its the same email data
            # or maybe different.

            # Case 1: If different: we have to write file with updated
            # Collission index

            # Case 2: Same file: Leave it as such
            with open(filename, 'r') as file_p:
                data2 = file_p.read()
            if data != data2:
                cursor = Transaction().connection.cursor()
                cursor.execute(
                    'SELECT DISTINCT(collision) FROM electronic_mail '
                    'WHERE digest = %s AND collision !=0 '
                    'ORDER BY collision', (digest,))
                collision2 = 0
                for row in cursor.fetchall():
                    collision2 = row[0]
                    filename = os.path.join(
                        directory, digest + '-' + str(collision2))
                    if os.path.isfile(filename):
                        with open(filename, 'r') as file_p:
                            data2 = file_p.read()
                        if data == data2:
                            collision = collision2
                            break
                if collision == 0:
                    collision = collision2 + 1
                    filename = os.path.join(
                        directory, digest + '-' + str(collision))
                    with open(filename, 'w') as file_p:
                        file_p.write(data)
        cls.write(records, {'digest': digest, 'collision': collision})

    @staticmethod
    def make_digest(data):
        """
        Returns a digest from the mail

        :param data: Data String
        :return: Digest
        """
        if isinstance(data, str):
            data = data.encode('utf-8')
        if hashlib:
            digest = hashlib.md5(data).hexdigest()
        else:
            digest = md5.new(data).hexdigest()
        return digest

    @classmethod
    def create_from_mail(cls, mail, mailbox, record=None):
        """
        Creates a mail record from a given mail
        :param mail: email object
        :param mailbox: ID of the mailbox
        :param context: dict
        """

        mail_date = None
        if mail.get('date'):
            mail_date = (_decode_header(mail.get('date', "")) and
                datetime.fromtimestamp(mktime(parsedate(mail.get('date')))))

        values = {
            'mailbox': mailbox,
            'from_': _decode_header(mail.get('from')),
            'sender': _decode_header(mail.get('sender')),
            'to': _decode_header(mail.get('to')),
            'cc': _decode_header(mail.get('cc')),
            'bcc': _decode_header(mail.get('bcc')),
            'subject': _decode_header(mail.get('subject')),
            'date': mail_date,
            'message_id': _decode_header(mail.get('message-id')),
            'in_reply_to': _decode_header(mail.get('in-reply-to')),
            'deliveredto': _decode_header(mail.get('delivered-to')),
            'reference': _decode_header(mail.get('references')),
            'reply_to': _decode_header(mail.get('reply-to')),
            'mail_file': mail.as_string(),
            'size': getsizeof(mail.__str__()),
            'resource': ('%s,%s' % (record.__name__, record.id)
                if record else None),
            }

        mail = cls.create([values])[0]
        return mail

    @staticmethod
    def validate_emails(email):
        '''Validate if emails ara corect formated.
        :param emails: list strings
        Return only the correct mails.
        '''
        if isinstance(email, list):
            emails = email
        else:
            emails = [email]
        correct_mails = []
        if CHECK_EMAIL:
            for em in emails:
                if check_email(em):
                    correct_mails.append(em)
        else:
            return email

        if isinstance(email, list):
            return correct_mails
        else:
            return len(correct_mails) == 1 and correct_mails[0] or ""
