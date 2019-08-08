# -*- coding: utf-8 -*-

import telebot
import sqlite3
import urllib.request
import urllib.error
import os
import shutil
import git
import subprocess
import json

from telebot import types
from telebot import apihelper

# Load config
with open('config.json') as json_data_file:
    cfg = json.load(json_data_file)

#apihelper.proxy = {'https':'socks5://10.0.0.2:3128'}
os.environ["REMOTE_REPO"] = cfg["remote_repo"]
os.environ["REMOTE_REPO_PATH"] = cfg["remote_repo_path"]

bot = telebot.TeleBot(cfg["token"])

db = sqlite3.connect('sqlite/database.sqlite', check_same_thread=False)


# Get state by chat.id
def get_state(chat_id):
    cur = db.cursor()
    cur.execute("SELECT * FROM states WHERE id = ?;", (chat_id,))
    r = cur.fetchone()
    result = {"id": r[0],
              "user": r[1],
              "project": r[2],
              "branch": r[3],
              "commit": r[4],
              "url": "http://github.com/{}/{}".format(r[1], r[2]),
              "log_from": r[5],
              "log_to": r[6]}
    return result



# Write log message to db
def write_log(ctx, message):
    cur = db.cursor()
    cur.execute("INSERT INTO log (user_id, datetime, first_name, message) "
                "VALUES(?, strftime('%s'), ?, ?);", (ctx.chat.id, ctx.chat.first_name, message))
    db.commit()



# Set states for user
def set_state(id, field, data):
    cur = db.cursor()
    cur.execute("INSERT OR IGNORE INTO states (id, {}) VALUES(?, ?);".format(field), (id, data))
    cur.execute("UPDATE states SET {} = ? WHERE id = ?;".format(field), (data, id))
    db.commit()



# Handler for /start and /help
@bot.message_handler(commands=['start','help'])
def send_welcome(message):
    bot.send_message(message.chat.id, 'Привет!\n'
                                      'Могу собрать *RPM* из github репозитория\n'
                                      '/build — запуск процесса сборки пакета\n'
                                      '/log   — показать журнал действий за выбранный период\n', parse_mode=['Markdown'])
    write_log(message, "[INFO] Command /start")



# Handler for /build
@bot.message_handler(content_types=['text'], commands=['build'])
def start(message):
    write_log(message, "[INFO] Command /build")
    bot.send_message(message.chat.id, 'Имя пользователя github?')
    bot.register_next_step_handler(message, get_user)

def get_user(message):
    set_state(message.chat.id, 'gh_user', message.text)

    bot.send_message(message.chat.id, 'Название проекта пользователя *{}*?'.format(message.text), parse_mode=['Markdown'])
    bot.register_next_step_handler(message, get_project)

def get_project(message):
    set_state(message.chat.id, 'gh_project', message.text)

    # TODO: add some checks
    bot.send_message(message.chat.id, 'Из какой ветки собирать?')
    bot.register_next_step_handler(message, get_branch)

def get_branch(message):
    set_state(message.chat.id, 'gh_branch', message.text)

    # TODO: add some checks
    bot.send_message(message.chat.id, 'Коммит или тег?')
    bot.register_next_step_handler(message, get_commit)

def get_commit(message):
    set_state(message.chat.id, 'gh_commit', message.text)

    state = get_state(message.chat.id)
    kbd = types.InlineKeyboardMarkup()
    kbd.row_width = 2
    kbd.add(types.InlineKeyboardButton(text='Да', callback_data='yes'))
    question = "Проект: *{}*\nветка: *{}*\nкоммит: {}\n\n" \
               "Собираем RPM?".format(state["url"], state["branch"], state["commit"])

    write_log(message, "[INFO] Ready for build {}, branch: {}, commit: {}"
              .format(state["url"], state["branch"], state["commit"]))

    bot.send_message(message.chat.id, text=question, reply_markup=kbd, parse_mode=['Markdown'])


# Callback handler for "YES" button
@bot.callback_query_handler(func=lambda call: True)
def callback_worker(call):
    state = get_state(call.message.chat.id)
    if call.data == "yes":
        bot.answer_callback_query(call.id, text="Хорошо, попробую собрать {}".format(state["url"]))

        write_log(call.message, "[INFO] Start build for {}, branch: {}, commit: "
                                "{}".format(state["url"], state["branch"], state["commit"]))

        cur = db.cursor()
        cur.execute("SELECT count() as cnt FROM builds WHERE gh_user = ? AND gh_project = ? AND gh_branch = ? "
                    "AND gh_commit = ? AND result = 0;",
                    (state["user"], state["project"], state["branch"], state["commit"]))
        r = cur.fetchone()
        cur.fetchall()

        if r[0] >= 1:
            bot.send_message(call.message.chat.id, "Пакет уже был собран ранее, сборка не требуется: "
                                                   "{}{}".format(cfg["repo_url"], state["project"]))
            write_log(call.message, "[INFO] RPM for {} already build!".format(state["url"]))
            return

        repo_build_path = os.path.join(cfg["builddir"], str(state["id"]), state["user"], state["project"])

        try:
            urllib.request.urlopen(state["url"]) # Check if remote repo exist and available

            if os.path.exists(repo_build_path):
                shutil.rmtree(repo_build_path)
            try:
                repo = git.Repo.clone_from(state["url"], repo_build_path, branch=state["branch"])
                repo.git.checkout(state["commit"])
                os.environ['rpm_src'] = repo_build_path
                os.environ['rpm_project'] = state["project"]
                os.environ['rpm_commit'] = state["commit"]
                os.environ['rpm_branch'] = state["branch"]
                rc = subprocess.call(["./build-rpm"])
                if rc == 0:
                    bot.send_message(call.message.chat.id, "Пакет собран: {}{}".format(cfg["repo_url"], state["project"]))
                    write_log(call.message, "[INFO] Build success: {}, branch: {}, commit: {}"
                              .format(state["url"], state["branch"], state["commit"]))
                else:
                    bot.send_message(call.message.chat.id, "Сборка из репозитория {} не удалась.".format(state["url"]))
                    write_log(call.message, "[ERROR] Build FAIL: {}, "
                                            "branch: {}, commit: {}"
                              .format(state["url"], state["branch"], state["commit"]))

                cur.execute("INSERT INTO builds (user_id, datetime, gh_user, gh_project, gh_branch, gh_commit, result) "
                            "VALUES(?, strftime('%s'), ?, ?, ?, ?, ?);", (call.message.chat.id,
                                                                      state["user"], state["project"],
                                                                      state["branch"], state["commit"], rc))
                db.commit()

            except git.exc.GitCommandError as err:
                bot.send_message(call.message.chat.id, "Что-то пошло не так! \n\n{}".format(err))

        except urllib.error.HTTPError as err:
            bot.send_message(call.message.chat.id, 'HTTP Error: {}, {}'.format(err.code, err.reason))


# Handler for /log
@bot.message_handler(content_types=['text'], commands=['log'])
def log_start(message):
    write_log(message, "[INFO] Command /log")
    bot.send_message(message.chat.id, 'Показать лог начиная с какой даты/времени? (YYYY-MM-DD HH:MM:SS)')
    bot.register_next_step_handler(message, get_log_from)

def get_log_from(message):
    set_state(message.chat.id, 'log_from', message.text)

    bot.send_message(message.chat.id, 'По какую дату/время? (YYYY-MM-DD HH:MM:SS)')
    bot.register_next_step_handler(message, get_log_to)

def get_log_to(message):
    set_state(message.chat.id, 'log_to', message.text)

    state = get_state(message.chat.id)

    write_log(message, "[INFO] Request log from {} to {}".format(state['log_from'], state['log_to']))
    cur = db.cursor()
    cur.execute("SELECT id, user_id, datetime(datetime, 'unixepoch', 'localtime'), first_name, message "
                "FROM log WHERE datetime "
                "BETWEEN strftime('%s', ?, 'utc') AND strftime('%s', ?, 'utc');", (state["log_from"], state["log_to"]))
    msg = ""
    while 1:
        row = cur.fetchone()
        if row == None and len(msg) == 0:
            bot.send_message(message.chat.id, "Записи за указанное время не найдены")
            break
        elif row == None and len(msg) > 0:
            bot.send_message(message.chat.id, msg, disable_web_page_preview=True)
            break
        elif len(msg) > 3000:
            bot.send_message(message.chat.id, msg, disable_web_page_preview=True)
            msg = ""
        else:
            msg = msg + "{} {} ({}) {}\n\n".format(row[2], row[3], row[1], row[4])


# Run Telegram BOT
bot.polling()
