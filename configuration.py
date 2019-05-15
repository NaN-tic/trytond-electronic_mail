# This file is part of the electronic_mail_configuration module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.model import ModelView, ModelSingleton, ModelSQL, fields, Unique
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.i18n import gettext
from trytond.exceptions import UserError


__all__ = [
    'ElectronicMailConfiguration',
    'ElectronicMailConfigurationCompany',
    ]


class ElectronicMailConfiguration(ModelSingleton, ModelSQL, ModelView):
    'Electronic Mail Configuration'
    __name__ = 'electronic.mail.configuration'
    sent = fields.Function(fields.Many2One('electronic.mail.mailbox', 'Sent',
            required=True),
        'get_fields', setter='set_fields')
    draft = fields.Function(fields.Many2One('electronic.mail.mailbox',
            'Draft', required=True),
        'get_fields', setter='set_fields')
    error = fields.Function(fields.Many2One('electronic.mail.mailbox',
            'Error', required=True),
        'get_fields', setter='set_fields')
    outbox = fields.Function(fields.Many2One('electronic.mail.mailbox',
            'Outbox', required=True),
        'get_fields', setter='set_fields')

    @classmethod
    def get_fields(cls, configurations, names):
        res = {}
        ConfigurationCompany = Pool().get(
            'electronic.mail.configuration.company')
        company_id = Transaction().context.get('company')
        conf_id = configurations[0].id
        if company_id:
            confs = ConfigurationCompany.search([
                    ('company', '=', company_id),
                    ], limit=1)
            if confs:
                for conf in confs:
                    for field_name in names:
                        value = getattr(conf, field_name)
                        if (value and not isinstance(value, str)
                                and not isinstance(value, int)):
                            value = value.id
                        res[field_name] = {conf_id: value}
            else:
                for field_name in names:
                    res[field_name] = {conf_id: None}
        else:
            raise UserError(gettext('electronic_mail.not_company'))
        return res

    @classmethod
    def set_fields(cls, configurations, name, value):
        ConfigurationCompany = Pool().get(
            'electronic.mail.configuration.company')
        company_id = Transaction().context.get('company')
        if company_id:
            company_confs = ConfigurationCompany.search([
                ('company', '=', company_id),
                ], limit=1)
            if company_confs:
                for configuration in configurations:
                    if getattr(configuration, name) != value:
                        ConfigurationCompany.write(company_confs,
                            {name: value})
            else:
                ConfigurationCompany.create([{
                            'company': company_id,
                            name: value
                            }])

    @classmethod
    def delete(cls, configurations):
        ConfigurationCompany = Pool().get(
            'electronic.mail.configuration.company')
        company_id = Transaction().context.get('company')
        if company_id:
            company_confs = ConfigurationCompany.search([
                ('company', '=', company_id),
                ], limit=1)
            if company_confs:
                ConfigurationCompany.delete(company_confs)
        return super(ElectronicMailConfiguration, cls).delete(configurations)


class ElectronicMailConfigurationCompany(ModelSQL, ModelView):
    'Electronic Mail Configuration Company'
    __name__ = 'electronic.mail.configuration.company'
    company = fields.Many2One('company.company', 'Company',
        required=True, readonly=True)
    sent = fields.Many2One('electronic.mail.mailbox', 'Sent')
    draft = fields.Many2One('electronic.mail.mailbox', 'Draft')
    error = fields.Many2One('electronic.mail.mailbox', 'Error')
    outbox = fields.Many2One('electronic.mail.mailbox', 'Outbox')

    @classmethod
    def __setup__(cls):
        super(ElectronicMailConfigurationCompany, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            ('company_uniq', Unique(t, t.company),
                'There is already one configuration for this company.'),
            ]
