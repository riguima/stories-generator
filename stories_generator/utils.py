from datetime import datetime, timedelta

from sqlalchemy import select

from stories_generator.database import Session
from stories_generator.models import Plan


def get_today_date():
    return (datetime.now() - timedelta(hours=3)).date()


def get_plans_reply_markup(action, *args):
    reply_markup = {}
    with Session() as session:
        for plan_model in session.scalars(select(Plan)).all():
            try:
                label = (
                    f'{plan_model.name} - '
                    f'{plan_model.days} Dias - '
                    f'R${plan_model.value:.2f}'.replace('.', ',')
                )
            except TypeError:
                label = f'{plan_model.name} - {plan_model.days} Dias - Plano Teste'
            reply_markup[label] = {
                'callback_data': ':'.join([action, str(plan_model.id), *args])
            }
    reply_markup['Voltar'] = {'callback_data': 'return_to_main_menu'}
    return reply_markup
