from datetime import timedelta

from sqlalchemy import select
from telebot.util import quick_markup

from stories_generator.database import Session
from stories_generator.models import Plan
from stories_generator.utils import get_plans_reply_markup


def init_bot(bot, start):
    @bot.callback_query_handler(func=lambda c: c.data == 'edit_test_plan')
    def edit_test_plan(callback_query):
        bot.send_message(
            callback_query.message.chat.id,
            'Digite quantos dias vai ter o plano teste (digite 0 para desativar o plano)',
        )
        bot.register_next_step_handler(
            callback_query.message, on_test_plan_days
        )

    def on_test_plan_days(message):
        try:
            with Session() as session:
                query = select(Plan).where(Plan.value == None)
                plan = session.scalars(query).first()
                plan.days = int(message.text)
                for signature_model in plan.signatures:
                    signature_model.due_date = (
                        signature_model.create_date
                        + timedelta(int(message.text))
                    )
                session.commit()
                bot.send_message(message.chat.id, 'Plano Teste Alterado!')
                start(message)
        except ValueError:
            bot.register_next_step_handler(
                message, 'Valor inválido, digite como no exemplo: 10 ou 15'
            )

    @bot.callback_query_handler(func=lambda c: c.data == 'add_plan')
    def add_plan(callback_query):
        bot.send_message(
            callback_query.message.chat.id, 'Digite nome para o plano'
        )
        bot.register_next_step_handler(callback_query.message, on_plan_name)

    def on_plan_name(message):
        bot.send_message(message.chat.id, 'Digite o valor para o plano')
        bot.register_next_step_handler(
            message, lambda m: on_plan_value(m, message.text)
        )

    def on_plan_value(message, plan_name):
        try:
            plan_value = float(message.text.replace(',', '.'))
            bot.send_message(
                message.chat.id, 'Digite a quantidade de dias do plano'
            )
            bot.register_next_step_handler(
                message,
                lambda m: on_plan_days(m, plan_name, plan_value),
            )
        except ValueError:
            bot.send_message(
                message.chat.id,
                'Valor inválido, digite como no exemplo: 10 ou 19,99',
            )
            start(message)

    def on_plan_days(message, plan_name, plan_value):
        try:
            with Session() as session:
                plan_model = Plan(
                    value=plan_value,
                    name=plan_name,
                    days=int(message.text),
                )
                session.add(plan_model)
                session.commit()
                bot.send_message(message.chat.id, 'Plano Adicionado!')
        except ValueError:
            bot.send_message(
                message.chat.id,
                'Valor inválido, digite como no exemplo: 10 ou 15',
            )
        start(message)

    @bot.callback_query_handler(func=lambda c: c.data == 'show_plans')
    def show_plans(callback_query):
        bot.send_message(
            callback_query.message.chat.id,
            'Planos',
            reply_markup=quick_markup(
                get_plans_reply_markup('show_plan'), row_width=1
            ),
        )

    @bot.callback_query_handler(func=lambda c: 'show_plan:' in c.data)
    def show_plan_action(callback_query):
        plan_id = callback_query.data.split(':')[-1]
        bot.send_message(
            callback_query.message.chat.id,
            'Escolha uma opção',
            reply_markup=quick_markup(
                {
                    'Editar Plano': {'callback_data': f'edit_plan:{plan_id}'},
                    'Remover Plano': {
                        'callback_data': f'remove_plan:{plan_id}'
                    },
                    'Voltar': {'callback_data': 'return_to_main_menu'},
                },
                row_width=1,
            ),
        )

    @bot.callback_query_handler(func=lambda c: 'remove_plan:' in c.data)
    def remove_plan(callback_query):
        with Session() as session:
            plan_id = int(callback_query.data.split(':')[-1])
            plan_model = session.get(Plan, plan_id)
            session.delete(plan_model)
            session.commit()
            bot.send_message(callback_query.message.chat.id, 'Plano Removido!')
            start(callback_query.message)

    @bot.callback_query_handler(func=lambda c: 'edit_plan:' in c.data)
    def edit_plan(callback_query):
        plan_id = int(callback_query.data.split(':')[-1])
        bot.send_message(
            callback_query.message.chat.id, 'Digite o nome para o plano'
        )
        bot.register_next_step_handler(
            callback_query.message,
            lambda m: on_edit_plan_name(m, plan_id),
        )

    def on_edit_plan_name(message, plan_id):
        with Session() as session:
            plan_model = session.get(Plan, plan_id)
            plan_model.name = message.text
            session.commit()
            bot.send_message(message.chat.id, 'Digite o valor do plano')
            bot.register_next_step_handler(
                message, lambda m: on_edit_plan_value(m, plan_id)
            )

    def on_edit_plan_value(message, plan_id):
        try:
            with Session() as session:
                plan_model = session.get(Plan, plan_id)
                plan_model.value = float(message.text.replace(',', '.'))
                session.commit()
                bot.send_message(message.chat.id, 'Plano Editado!')
                start(message)
        except ValueError:
            bot.register_next_step_handler(
                message, lambda m: on_edit_plan_value(m, plan_id)
            )
