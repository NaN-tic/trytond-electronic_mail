# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.model import fields

__all__ = ['User']


class User:
    __name__ = "res.user"
    __metaclass__ = PoolMeta
    signature_html = fields.Text('Signature')

    @classmethod
    def __setup__(cls):
        if not cls._preferences_fields:
            cls._preferences_fields = []
        cls._preferences_fields.append('signature_html')
