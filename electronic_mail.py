# This file is part of electronic_mail module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
import chardet
import mimetypes
import re
from datetime import datetime
from email import message_from_bytes
from email.utils import parsedate, getaddresses
from email.header import decode_header, make_header
import email.policy
from sys import getsizeof
from time import mktime

from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import Pool
from trytond.i18n import gettext
from trytond.exceptions import UserError
from trytond.transaction import Transaction
from trytond.tools.email_ import validate_email, EmailNotValidError

from . import utils


EMAIL_DEFAULT_POLICY = email.policy.default

def _make_header(data, charset='utf-8'):
    return str(make_header([(data or "", charset)]))


def _decode_header(data):
    if data is None:
        return
    decoded_headers = decode_header(data)
    headers = []
    for decoded_str, charset in decoded_headers:
        if not isinstance(decoded_str, str):
            if charset and not charset.startswith('unknown'):
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
    company = fields.Many2One('company.company', 'Company')


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
    preview = fields.Function(fields.Text('Preview'), 'get_mail')
    deliveredto = fields.Char('Delivered-To')
    reference = fields.Char('References')
    reply_to = fields.Char('Reply-To')
    num_attach = fields.Function(fields.Integer('Number of attachments'),
        'get_mail')
    attachments = fields.Function(fields.Text('Attachments'), 'get_mail')
    message_id = fields.Char('Message-ID', help='Unique Message Identifier')
    in_reply_to = fields.Char('In-Reply-To')
    mail_file = fields.Binary('Mail File', file_id='mail_file_id',
        filename='mail_file_name')
    mail_file_id = fields.Char('Mail File ID')
    mail_file_name = fields.Function(fields.Char('Mail File Name'), 'get_mail')
    flag_send = fields.Boolean('Sent', readonly=True)
    flag_received = fields.Boolean('Received', readonly=True)
    flag_seen = fields.Boolean('Seen')
    flag_answered = fields.Boolean('Answered')
    flag_flagged = fields.Boolean('Flagged')
    flag_draft = fields.Boolean('Draft')
    flag_recent = fields.Boolean('Recent')
    size = fields.Integer('Size')
    resource = fields.Reference('Resource', selection='get_resource_models')
    parent = fields.Function(fields.Many2One('electronic.mail', 'Parent'),
            'get_parent')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('date', 'DESC'))

    def get_parent(self, name=None):
        ElectronicMail = Pool().get('electronic.mail')
        referenced_mails = None
        if self.in_reply_to:
            referenced_mails = ElectronicMail.search([
                ('message_id', '=', self.in_reply_to)
                ], order=[('date', 'DESC'), ('id', 'DESC')], limit=1)
        if not referenced_mails and self.reference:
            referenced_mails = ElectronicMail.search([
                ('message_id', 'in', self.reference)
                ], order=[('date', 'DESC'), ('id', 'DESC')], limit=1)
        if referenced_mails:
            return referenced_mails[0]

    @staticmethod
    def get_resource_models():
        pool = Pool()
        Model = pool.get('ir.model')
        ModelAccess = pool.get('ir.model.access')

        models = Model.get_name_items()
        if Transaction().check_access:
            access = ModelAccess.get_access([m for m, _ in models
                if not m.startswith('babi_execution_')])
            models = [(m, n) for m, n in models if access.get(m) and access[m]['read']]
        return [(None, '')] + models

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
                        filename_decoded = decode_header(filename)
                        filename = filename_decoded[0][0].decode(filename_decoded[0][1])
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

    @classmethod
    def get_mail(cls, mails, names):
        result = {}
        for fname in ['body', 'num_attach', 'mail_file_name', 'attachments',
                'preview']:
            result[fname] = {}
        with Transaction().set_context({'electronic.mail.mail_file': None}):
            # Ensure that mail_file returns a binary and not its size
            mails = cls.browse(mails)
        for mail in mails:
            if mail.mail_file:
                result['mail_file_name'][mail.id] = '%d.txt' % mail.id
                email = message_from_bytes(mail.mail_file, policy=EMAIL_DEFAULT_POLICY)
                body = mail.get_body(email)
                html = body.get('body_html').strip()
                # TODO: Find a better way to know if there's a real HTML body
                if html.startswith('<html') or html.startswith('<meta'):
                    result['body'][mail.id] = body.get('body_html')
                else:
                    result['body'][mail.id] = ('<pre>%s</pre>' %
                        body.get('body_plain'))
                body_html = utils.render_email(email)
                result['num_attach'][mail.id] = len(cls.get_attachments(email))
                result['attachments'][mail.id] = '\n'.join([x['filename'] for x
                        in cls.get_attachments(email)])
                result['preview'][mail.id] = '''
                    <!DOCTYPE html>
                    <html>
                    <head>
                    <meta charset="utf-8">
                    </head>
                    <body>
                    <div style="font-family: sans-serif">
                    <h1>%(subject)s</h1>
                    <b>Remitent:</b> %(remitent)s<br/>
                    <b>Destinatari:</b> %(destinatari)s<br/>
                    <b>CC:</b> %(cc)s<br/>
                    <b>Data:</b> %(data)s<br/>
                    <hr/>
                    <div>
                    %(body)s
                    </div>
                    </div>
                    </body>
                    </html>
                    ''' % {
                        'subject': email['Subject'],
                        'remitent': email['From'],
                        'destinatari': email['To'],
                        'cc': email['Cc'],
                        'data': email['Date'],
                        'body': body_html,
                    }
            else:
                result['mail_file_name'][mail.id] = None
                result['body'][mail.id] = None
                result['num_attach'][mail.id] = None
                result['attachments'][mail.id] = None
                result['preview'][mail.id] = None
        for fname in ['num_attach', 'preview']:
            if fname not in names:
                del result[fname]
        return result

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

        # email.message.replace_header may raise 'KeyError' if the header
        # 'content-transfer-encoding' is missing
        # FIXED at py3.8 https://bugs.python.org/issue27321
        try:
            mail_file = mail.as_bytes()
        except KeyError:
            return

        message_id = None
        if _decode_header(mail.get('message-id')):
            message_id = _decode_header(mail.get('message-id')).strip('\r\n\t')

        values = {
            'mailbox': mailbox,
            'from_': _decode_header(
                ",".join(mail.get('from', '').replace('\t', '').splitlines())),
            'sender': _decode_header(
                ",".join(mail.get('sender', '').replace(
                    '\t', '').splitlines())),
            'to': _decode_header(
                ",".join(mail.get('to', '').replace('\t', '').splitlines())),
            'cc': _decode_header(
                ",".join(mail.get('cc', '').replace('\t', '').splitlines())),
            'bcc': _decode_header(
                ",".join(mail.get('bcc', '').replace('\t', '').splitlines())),
            'subject': _decode_header(str(mail.get('subject'))).replace(
                '\n','').replace('\r', '').replace('\t', ''),
            'date': mail_date,
            'message_id': message_id,
            'in_reply_to': _decode_header(mail.get('in-reply-to', '')).strip(
                '\r\n\t'),
            'deliveredto': _decode_header(
                ",".join(mail.get('delivered-to', '').replace(
                    '\t', '').splitlines())),
            'reference': _decode_header(
                ",".join(mail.get('references', '').replace(
                    '\t', '').splitlines())),
            'reply_to': _decode_header(
                ",".join(mail.get('reply-to', '').replace(
                    '\t', '').splitlines())),
            'mail_file': mail_file,
            'size': getsizeof(mail.__bytes__()),
            'resource': ('%s,%s' % (record.__name__, record.id)
                if record else None),
            }

        mail = cls.create([values])[0]
        return mail

    @staticmethod
    def validate_emails(email, raise_exception=True):
        '''Validate if emails ara corect formated.
        :param emails: list strings
        Return only the correct mails.
        '''
        if isinstance(email, list):
            emails = email
        elif isinstance(email, set):
            emails = list(email)
        elif isinstance(email, str):
            emails = [e.strip() for e in re.split(r"[;,\s]+", email)
                if e.strip()]
        else:
            if raise_exception:
                raise UserError(
                    gettext('electronic_mail.not_validate_emails', email=email))
            else:
                return

        correct_mails = []
        for em in emails:
            try:
                if validate_email(em):
                    correct_mails.append(em)
            except EmailNotValidError:
                continue

        if isinstance(email, list):
            return correct_mails
        else:
            return ", ".join(correct_mails)
