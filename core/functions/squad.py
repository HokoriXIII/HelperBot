from telegram import Update, Bot, ParseMode

from core.functions.reply_markup import generate_squad_markup
from core.template import fill_char_template
from core.types import User, AdminType, Admin, admin_allowed, Group, Squad, SquadMember, user_allowed
from core.utils import send_async
from core.functions.inline_keyboard_handling import generate_squad_list, \
    generate_leave_squad, generate_squad_request, generate_squad_request_answer, generate_fire_up, \
    generate_squad_invite_answer
from core.texts import *


@user_allowed
def squad_about(bot: Bot, update: Update, session):
    markup = generate_squad_markup()
    send_async(bot,
               chat_id=update.message.chat.id,
               text=MSG_SQUAD_ABOUT,
               reply_markup=markup)


@admin_allowed()
def add_squad(bot: Bot, update: Update, session):
    if update.message.chat.type == 'supergroup':
        squad = session.query(Squad).filter_by(chat_id=update.message.chat.id).first()
        if squad is None:
            squad = Squad()
            squad.chat_id = update.message.chat.id
            squad.thorns_enabled = False
            msg = update.message.text.split(' ', 1)
            if len(msg) == 2:
                squad.squad_name = msg[1]
            else:
                group = session.query(Group).filter_by(id=update.message.chat.id).first()
                squad.squad_name = group.title
            session.add(squad)
            session.commit()
            send_async(bot, chat_id=update.message.chat.id, text=MSG_SQUAD_NEW.format(squad.squad_name),
                       parse_mode=ParseMode.HTML)


@admin_allowed()
def set_invite_link(bot: Bot, update: Update, session):
    squad = session.query(Squad).filter_by(chat_id=update.message.chat.id).first()
    if update.message.chat.type == 'supergroup' and squad is not None:
        msg = update.message.text.split(' ', 1)
        if len(msg) == 2:
            squad.invite_link = msg[1]
            session.add(squad)
            session.commit()
            send_async(bot, chat_id=update.message.chat.id, text=MSG_SQUAD_LINK_SAVED)


@admin_allowed()
def set_squad_name(bot: Bot, update: Update, session):
    squad = session.query(Squad).filter_by(chat_id=update.message.chat.id).first()
    if update.message.chat.type == 'supergroup' and squad is not None:
        msg = update.message.text.split(' ', 1)
        if len(msg) == 2:
            squad.squad_name = msg[1]
            session.add(squad)
            session.commit()
            send_async(bot, chat_id=update.message.chat.id, text=MSG_SQUAD_RENAMED.format(squad.squad_name),
                       parse_mode=ParseMode.HTML)


@admin_allowed()
def del_squad(bot: Bot, update: Update, session):
    squad = session.query(Squad).filter_by(chat_id=update.message.chat.id).first()
    if update.message.chat.type == 'supergroup' and squad is not None:
        for member in squad.members:
            session.delete(member)
        for order_group_item in squad.chat.group_items:
            session.delete(order_group_item)
        session.delete(squad)
        session.commit()
        send_async(bot, chat_id=update.message.chat.id, text=MSG_SQUAD_DELETE)


@admin_allowed(AdminType.GROUP)
def enable_thorns(bot: Bot, update: Update, session):
    group = session.query(Group).filter_by(id=update.message.chat.id).first()
    if update.message.chat.type == 'supergroup' and group is not None and len(group.squad) == 1:
        group.squad[0].thorns_enabled = True
        session.add(group.squad[0])
        session.commit()
        send_async(bot, chat_id=update.message.chat.id, text=MSG_SQUAD_THORNS_ENABLED)


@admin_allowed(AdminType.GROUP)
def disable_thorns(bot: Bot, update: Update, session):
    group = session.query(Group).filter_by(id=update.message.chat.id).first()
    if update.message.chat.type == 'supergroup' and group is not None and len(group.squad) == 1:
        group.squad[0].thorns_enabled = False
        session.add(group.squad[0])
        session.commit()
        send_async(bot, chat_id=update.message.chat.id, text=MSG_SQUAD_THORNS_DISABLED)


@admin_allowed(AdminType.GROUP)
def squad_list(bot: Bot, update: Update, session):
    admin = session.query(Admin).filter_by(user_id=update.message.from_user.id).all()
    global_adm = False
    for adm in admin:
        if adm.admin_type <= AdminType.FULL.value:
            global_adm = True
            break
    if global_adm:
        squads = session.query(Squad).all()
    else:
        group_ids = []
        for adm in admin:
            group_ids.append(adm.admin_group)
        squads = session.query(Squad).filter(Squad.chat_id.in_(group_ids)).all()
    markup = generate_squad_list(squads, session)
    send_async(bot, chat_id=update.message.chat.id, text=MSG_SQUAD_LIST, reply_markup=markup)


@user_allowed
def squad_request(bot: Bot, update: Update, session):
    user = session.query(User).filter_by(id=update.message.from_user.id).first()
    if user is not None:
        if user.character:
            if user.member:
                markup = generate_leave_squad(user.id)
                send_async(bot, chat_id=update.message.chat.id, text=MSG_SQUAD_REQUEST_EXISTS, reply_markup=markup)
            else:
                markup = generate_squad_request(session)
                send_async(bot, chat_id=update.message.chat.id, text=MSG_SQUAD_REQUEST, reply_markup=markup)
        else:
            send_async(bot, chat_id=update.message.chat.id, text=MSG_NO_PROFILE_IN_BOT)


@admin_allowed(AdminType.GROUP)
def list_squad_requests(bot: Bot, update: Update, session):
    admin = session.query(Admin).filter_by(user_id=update.message.from_user.id).all()
    group_admin = []
    for adm in admin:
        if adm.admin_type == AdminType.GROUP.value and adm.admin_group != 0:
            group_admin.append(adm)
    count = 0
    for adm in group_admin:
        members = session.query(SquadMember).filter_by(squad_id=adm.admin_group, approved=False)
        for member in members:
            count += 1
            markup = generate_squad_request_answer(member.user_id)
            send_async(bot, chat_id=update.message.chat.id,
                       text=fill_char_template(MSG_PROFILE_SHOW_FORMAT, member.user, member.user.character, True),
                       reply_markup=markup)
    if count == 0:
        send_async(bot, chat_id=update.message.chat.id,
                   text=MSG_SQUAD_REQUEST_EMPTY)


@admin_allowed(AdminType.GROUP)
def open_hiring(bot: Bot, update: Update, session):
    squad = session.query(Squad).filter_by(chat_id=update.message.chat.id).first()
    if squad is not None:
        squad.hiring = True
        session.add(squad)
        session.commit()
        send_async(bot, chat_id=update.message.chat.id, text=MSG_SQUAD_RECRUITING_ENABLED)


@admin_allowed(AdminType.GROUP)
def close_hiring(bot: Bot, update: Update, session):
    squad = session.query(Squad).filter_by(chat_id=update.message.chat.id).first()
    if squad is not None:
        squad.hiring = False
        session.add(squad)
        session.commit()
        send_async(bot, chat_id=update.message.chat.id, text=MSG_SQUAD_RECRUITING_DISABLED)


@admin_allowed(AdminType.GROUP)
def remove_from_squad(bot: Bot, update: Update, session):
    admin = session.query(Admin).filter_by(user_id=update.message.from_user.id).all()
    group_admin = []
    for adm in admin:
        squad = session.query(Squad).filter_by(chat_id=adm.admin_group).first()
        if squad is not None:
            group_admin.append(adm)
    for adm in group_admin:
        members = session.query(SquadMember).filter_by(squad_id=adm.admin_group)
        markup = generate_fire_up(members)
        squad = session.query(Squad).filter_by(chat_id=adm.admin_group).first()
        send_async(bot, chat_id=update.message.chat.id,
                   text=MSG_SQUAD_CLEAN.format(squad.squad_name),
                   reply_markup=markup, parse_mode=ParseMode.HTML)


@user_allowed
def leave_squad(bot: Bot, update: Update, session):
    member = session.query(SquadMember).filter_by(user_id=update.message.from_user.id).first()
    user = session.query(User).filter_by(id=update.message.from_user.id).first()
    if member:
        squad = member.squad
        session.delete(member)
        session.commit()
        admins = session.query(Admin).filter_by(admin_group=squad.chat_id).all()
        for adm in admins:
            if adm.user_id != update.message.from_user.id:
                send_async(bot, chat_id=adm.user_id,
                           text=MSG_SQUAD_LEAVED.format(user.character.name, squad.squad_name),
                           parse_mode=ParseMode.HTML)
        send_async(bot, chat_id=member.squad_id,
                   text=MSG_SQUAD_LEAVED.format(user.character.name, squad.squad_name), parse_mode=ParseMode.HTML)
        send_async(bot, chat_id=member.user_id,
                   text=MSG_SQUAD_LEAVED.format(user.character.name, squad.squad_name), parse_mode=ParseMode.HTML)
    else:
        send_async(bot, chat_id=user.id,
                   text=MSG_SQUAD_NONE, parse_mode=ParseMode.HTML)


@admin_allowed(AdminType.GROUP)
def add_to_squad(bot: Bot, update: Update, session):
    squad = session.query(Squad).filter_by(chat_id=update.message.chat.id).first()
    if squad is not None:
        username = update.message.text.split(' ', 1)
        if len(username) == 2:
            username = username[1].replace('@', '')
            user = session.query(User).filter_by(username=username).first()
            if user is not None and user.character is not None and user.member is None:
                markup = generate_squad_invite_answer(user.id)
                send_async(bot, chat_id=update.message.chat.id,
                           text=MSG_SQUAD_ADD.format('@' + username),
                           reply_markup=markup)
            elif user.member is not None:
                send_async(bot, chat_id=update.message.chat.id,
                           text=MSG_SQUAD_ADD_IN_SQUAD.format('@' + username))
            elif user.character is None:
                send_async(bot, chat_id=update.message.chat.id, text=MSG_SQUAD_NO_PROFILE)
