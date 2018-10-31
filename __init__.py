# -*- coding: UTF-8 -*-
# This file is part of electronic_mail module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import Pool
from . import electronic_mail
from . import configuration
from . import user


def register():
    Pool.register(
        electronic_mail.Mailbox,
        configuration.ElectronicMailConfiguration,
        configuration.ElectronicMailConfigurationCompany,
        electronic_mail.ElectronicMail,
        user.User,
        module='electronic_mail', type_='model')
