"""Account roles shared by the server and desktop interface."""
from typing import Literal

Role = Literal['member', 'admin', 'superadmin']
ROLES = ('member', 'admin', 'superadmin')
ROLE_LABELS = {'member': 'Member', 'admin': 'Administrator', 'superadmin': 'Superadmin'}


def can_manage_users(role):
    return role == 'superadmin'


def can_review_reports(role):
    return role in ('admin', 'superadmin')
