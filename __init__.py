# -*- coding: UTF-8 -*-
# This file is part of electronic_mail module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import Pool
from .electronic_mail import *
from .configuration import *
from .user import *


def register():
    Pool.register(
        ElectronicMail,
        ElectronicMailConfiguration,
        ElectronicMailConfigurationCompany,
        Mailbox,
        ReadUser,
        User,
        WriteUser,
        module='electronic_mail', type_='model')
