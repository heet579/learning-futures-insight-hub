"""Account roles shared by the server and desktop interface."""
from typing import Literal

Role = Literal['member', 'admin', 'facilitator', 'client', 'superadmin']
ROLES = ('member', 'admin', 'facilitator', 'client', 'superadmin')
ROLE_LABELS = {'member': 'Member', 'admin': 'Administrator', 'facilitator': 'Facilitator',
               'client': 'Client', 'superadmin': 'Superadmin'}


def can_manage_users(role):
    return role == 'superadmin'


def can_review_reports(role):
    return role in ('admin', 'superadmin')
