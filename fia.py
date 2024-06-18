import asyncio
import logging
import os
import re
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from rave_python import Rave, RaveExceptions
from aiogram.utils.chat_action import ChatActionSender
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton

)
import keyboards
import creds
import paramiko
import sqlite3

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv('BOT_KEYS')
ADMIN_CHAT_ID = int(os.getenv('ADMIN_CHAT_ID'))  # Assuming ADMIN_CHAT_ID is provided as an environment variable

# Initialize bot and dispatcher
dp = Dispatcher()
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
#Flutter
SECRET = os.getenv('RAVE_SECRET_KEY')
rave = Rave("FLWPUBK-1ab67f97ba59d47b65d67001eb794a05-X", SECRET, production=True)



# Establish a connection to the SQLite database
def get_db_connection():
    return sqlite3.connect('user_data.db')



# Initialize the database
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bot_user_id INTEGER NOT NULL,
        username TEXT NOT NULL,
        server TEXT NOT NULL,
        days INTEGER NOT NULL,
        password TEXT DEFAULT '',  -- Provide a default value or NULL if appropriate
        config TEXT DEFAULT '',  -- Provide a default value or NULL if appropriate
        date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        role TEXT DEFAULT 'user'
    )
    ''')
    cursor.execute('SELECT * FROM users WHERE bot_user_id = ?', (ADMIN_CHAT_ID,))
    admin_user = cursor.fetchone()
    if not admin_user:
        cursor.execute('INSERT INTO users (bot_user_id, username, server, days, password, config, role) VALUES (?, ?, ?, ?, ?, ?, ?)',
                       (ADMIN_CHAT_ID, 'admin', 'global', 0, 'freak', '', 'admin'))
        conn.commit()
        # Check if the column exists in the table
        cursor.execute("PRAGMA table_info(users);")
        columns = cursor.fetchall()
        column_names = [column[1] for column in columns]

        if 'balance' not in column_names:
            # Alter table to add 'balance' column if it doesn't exist
            cursor.execute("ALTER TABLE users ADD COLUMN balance DECIMAL(10, 2) DEFAULT 0.00;")
            conn.commit()
    conn.close()


init_db()

# User states
user_states = {}
STATE_NONE = 'none'
STATE_TO_BUY_VPS = 'awaiting_phone_number_vps'
STATE_TO_BUY_FILE = 'awaiting_phone_number_file'
STATE_TO_BUY_ACCOUNT = 'awaiting_phone_number_account'


# Function to get user role from the database
def get_user_role(bot_user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT role FROM users WHERE bot_user_id = ?', (bot_user_id,))
    role = cursor.fetchone()
    conn.close()
    return role[0] if role else None
def remove_user_from_database(username, server):
    conn = sqlite3.connect('user_data.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM users WHERE username = ? AND server = ?', (username, server))
    conn.commit()
    conn.close()

async def generate_custom_code(a, b):
    if not (0 <= a <= 9) or not (0 <= b <= 9):
        raise ValueError("Both 'a' and 'b' must be single digits between 0 and 9.")

    # Generate the first part of the code
    first_part = str(a) + ''.join(str(random.randint(0, 9)) for _ in range(4))

    # Generate the second part of the code
    second_part = str(b) + ''.join(str(random.randint(0, 9)) for _ in range(6))

    # Combine both parts
    code = first_part + second_part

    return code


# Establish SSH connection
async def establish_ssh_connection(server):
    try:
        credentials = creds.SERVER_CREDENTIALS[server]
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(credentials['host'], username=credentials['username'], password=credentials['password'])
        return ssh
    except Exception as e:
        logging.error(f"Error establishing SSH connection to {server}: {e}")
        return None

async def handle_seller_command(message: types.Message):
    user_id = message.from_user.id
    if get_user_role(user_id) == 'admin':
        try:
            # Extract the chat_id from the command message
            chat_id = int(message.text.split()[1])
            # Establish a new connection to the SQLite database
            conn = get_db_connection()
            cursor = conn.cursor()

            # Check if the user already exists in the database
            cursor.execute('SELECT * FROM users WHERE bot_user_id = ?', (chat_id,))
            existing_user = cursor.fetchone()

            if existing_user:
                await message.reply(f'The seller with chat ID <code>{chat_id}</code> is already registered.')
            else:
                # Insert the new user into the database with role='user'
                cursor.execute('INSERT INTO users (bot_user_id, username, server, days, role) VALUES (?, ?, ?, ?, ?)',
                               (chat_id, 'user', 'global', 0, 'user'))
                conn.commit()
                conn.close()
                await message.reply(f'A new seller with chat ID <code>{chat_id}</code> has been registered.')
                await bot.send_message(chat_id, 'You are now a Reseller!\n'
                                                'You now have the permission to create your clients on any of our servers. Keep in mind that for every user you will add, you will be charged $0.40.\n\n'
                                                'Check your balance: use the button', reply_markup=keyboards.keyb)


        except Exception as e:
            logging.error(f"Error in handle_seller_command: {e}")
            await message.reply(f'Error: {str(e)}')

    else:
        await message.reply('🙊Oh ooh... Only admins can do that. \n\n'
                            '<i>👋 Please contact @teslassh to start doing business with me.</i>')

async def send_payment_note(message: types.Message):
    requester_id = message.from_user.id
    builder = InlineKeyboardBuilder()
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='I 100% agree', callback_data=f"make_the_payment_{requester_id}")]
    ])
    builder.attach(InlineKeyboardBuilder.from_markup(markup))
    msg = (f'Hello dear {message.from_user.first_name}, you are about to recharge your account.\n<b><a href="https://t.me/udp_tools/6" >Do you agree to our terms and conditions</a></b>?')
    await message.answer(msg, disable_web_page_preview=True, reply_markup=builder.as_markup())

# Send country selection for adding a user
async def send_country_selection(chat_id):
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='🇺🇸 USA', callback_data=f"add_to_usa"),
         InlineKeyboardButton(text='🇧🇷 Brazil', callback_data=f"add_to_brazil"),
         InlineKeyboardButton(text='🇿🇦 South Af', callback_data=f"add_to_za")],
        [InlineKeyboardButton(text='🇩🇪 Germany', callback_data=f"add_to_germany"),
         InlineKeyboardButton(text='🇸🇬 Singap..', callback_data=f"add_to_sg"),
         InlineKeyboardButton(text='🇳🇱 Netherl..', callback_data=f"add_to_nl")]
    ])
    await bot.send_message(chat_id, '⚡️Where do you want to add your client? ⛈', reply_markup=markup)

async def send_server_selection_for_users(chat_id):
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='🇺🇸 USA', callback_data=f"view_users_usa"),
         InlineKeyboardButton(text='🇧🇷 Brazil', callback_data=f"view_users_brazil"),
         InlineKeyboardButton(text='🇿🇦 South Af', callback_data=f"view_users_za")],
        [InlineKeyboardButton(text='🇩🇪 Germany', callback_data=f"view_users_germany"),
         InlineKeyboardButton(text='🇸🇬 Singap..', callback_data=f"view_users_sg"),
         InlineKeyboardButton(text='🇳🇱 Netherl..', callback_data=f"view_users_nl")]
    ])
    await bot.send_message(chat_id, 'Users of which server exactly?🤷‍♂️', reply_markup=markup)

# Send country selection for removing a user
async def sendx_country_selection(chat_id):
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='🇺🇸 USA', callback_data=f"user_del_usa"),
         InlineKeyboardButton(text='🇧🇷 Brazil', callback_data=f"user_del_brazil"),
         InlineKeyboardButton(text='🇿🇦 South Af', callback_data=f"user_del_za")],
        [InlineKeyboardButton(text='🇩🇪 Germany', callback_data=f"user_del_germany"),
         InlineKeyboardButton(text='🇸🇬 Singap..', callback_data=f"user_del_sg"),
         InlineKeyboardButton(text='🇳🇱 Netherl..', callback_data=f"user_del_nl")]
    ])
    await bot.send_message(chat_id, '🤷‍♂️ Removing from which server: 😳', reply_markup=markup)


# Add user to server
async def add_user_to_server(server, username, password, days, bot_user_id):
    ssh = await establish_ssh_connection(server)
    if ssh:
        try:
            current_date = datetime.now()
            expiration_date = current_date + timedelta(days=int(days))
            expiration_date_str = expiration_date.strftime('%Y-%m-%d')
            useradd_command = (f'sudo useradd -m -s /bin/false -e {expiration_date_str} '
                               f'-K PASS_MAX_DAYS={days} -c "GG, {password}" {username} && '
                               f'echo "{username}:{password}" | sudo chpasswd')

            stdin, stdout, stderr = ssh.exec_command(useradd_command)
            output = stdout.read().decode('utf-8')
            logging.info(f"Added user {username} to {server}: {output}")

            # Insert the user into the database with user role
            conn = get_db_connection()
            cursor = conn.cursor()

            # Calculate config
            IP = creds.SERVER_CREDENTIALS[server]['host']
            config = f"{IP}:1-65535@{username}:{password}"
            # Insert user into the database
            cursor.execute(
                'INSERT INTO users (bot_user_id, username, server, days, password, config) VALUES (?, ?, ?, ?, ?, ?)',
                (bot_user_id, username, server, days, password, config))
            conn.commit()
            conn.close()

            return output
        except Exception as e:
            logging.error(f"User addition failed: {e}")
            return f"User addition failed: {e}"
        finally:
            ssh.close()
    else:
        return "SSH connection error"


# Get users added by a specific bot user
def get_users_for_bot_user(bot_user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT username, server, days, password, config, date_added FROM users WHERE bot_user_id = ?', (bot_user_id,))
    users = cursor.fetchall()
    conn.close()
    return users


async def remove_seller(chat_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM users WHERE bot_user_id = ?', (chat_id,))
        conn.commit()
        conn.close()
        await bot.send_message(chat_id, 'Your reseller account has been removed after 30 days.')
        await bot.send_message(ADMIN_CHAT_ID, f'You have removed a seller with chat ID {chat_id}')
    except Exception as e:
        logging.error(f"Error in remove_seller: {e}")
        await bot.send_message(ADMIN_CHAT_ID, F'I GOT THE ERROR BELOW:\n\n'
                                              F'{e}')
async def rem_user(server, username):
    ssh = await establish_ssh_connection(server)
    if isinstance(ssh, paramiko.SSHClient):
        try:
            user_del = f'sudo userdel {username}'
            stdin, stdout, stderr = ssh.exec_command(user_del)
            output = stdout.read().decode('utf-8')

            # Remove user from the database
            remove_user_from_database(username, server)

            return output
        except Exception as e:
            return f"User deletion failed: {e}"
        finally:
            ssh.close()
    else:
        return ssh

@dp.message(Command('👩‍👩‍👧my clients'))
async def handle_users(message: types.Message):
    user_id = message.from_user.id
    if get_user_role(user_id) == 'user':
        await send_server_selection_for_users(message.chat.id)
        user_states[user_id] = "awaiting_server_selection_for_users"
    else:
        await message.reply('🙊Oh ooh... it seems you are not registered as a reseller yet. \n\n'
                            '<i>👋 Please contact @teslassh to start doing business with me.</i>')


async def handle_delete_user(message: types.Message):
    user_id = message.from_user.id
    if get_user_role(user_id) == 'user':
        await sendx_country_selection(message.chat.id)
        user_states[user_id] = "awaiting_server_selection_del"
    else:
        await message.reply('🙊Oh ooh... it seems you are not registered as a reseller yet. \n\n'
                            '<i>👋 Please contact @teslassh to start doing business with me.</i>')


async def get_all_bot_user_ids():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT bot_user_id FROM users')
    bot_user_ids = cursor.fetchall()
    conn.close()
    return [user_id[0] for user_id in bot_user_ids]
async def broadcater(bot_chat_id, msg):
    await bot.send_message(bot_chat_id, msg)
async def handle_add_user(message: types.Message):
    user_id = message.from_user.id
    if get_user_role(user_id) == 'user':
        await send_country_selection(message.chat.id)
        user_states[user_id] = "awaiting_server_selection"
    else:
        await message.reply('🙊Oh ooh... it seems you are not registered as a reseller yet. \n\n'
                            '<i>👋 Please contact @teslassh to start doing business with me.</i>')


@dp.message(F.text.lower() == "👨‍👦 create user")
async def handle_add(message: types.Message):
    await handle_add_user(message)


@dp.message(F.text.lower() == "🙅 kick user")
async def handle_del(message: types.Message):
    await handle_delete_user(message)


@dp.message(F.text.lower() == "👩‍👩‍👧 my clients")
async def handle_users_command(message: types.Message):
    await handle_users(message)


@dp.message(Command('start'))
async def handle_start(message: types.Message):
    user_id = message.from_user.id
    if get_user_role(user_id) == 'admin':
        await message.reply('Welcome again, admin! You can add or remove users using the respective commands.',
                            reply_markup=keyboards.admin_keyb)
    else:
        await message.reply(f'Welcome on board, {message.from_user.first_name}! You can use the buttons below to start adding or removing your users.\n\nEverything we own, you now own it too🥳',
                            reply_markup=keyboards.keyb)

@dp.message(Command('seller'))
async def handle_seller(message: types.Message):
    await handle_seller_command(message)
@dp.message(F.text.lower() == '🆘 help')
async def help_msg(message: Message):

    msg = (f'✈️<b>OCTOPAS PANEL V1.0</b>😐🤩\n\n'
           f'To refresh this bot, send /start\n➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n\n'
           f'To get started as our UDP/VPN reseller, visit @chatIDrobot and claim your <b>chat ID</b>.\n➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n\n'
           f'Inbox @teslassh with your Chat ID to get registered instantly and become a reseller.\n'
           f'➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n\n'
           f'Resellers Have the right to sell server accounts or files from any of our premium servers. We give a huge bundle of servers at a very small price, starting with $5.\n\n<i><b>We only charge you a small set up fee $0.4 for each user you create</b></i>')

    msg1 = (f'✈️<b>OCTOPAS ADMIN V1.0</b>😐🤩\n\n'
           f'To refresh this bot, send /start\n➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n\n'
           f'To register a new seller, send /seller [chat_id]\n➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n\n'
           f'To Dismiss/Remove a seller, send /dismiss [chat_id].\n'
           f'➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n\n'
           f'To send a message to all resellers, send <code>updates~</code> followed by a message')

    if message.from_user.id == ADMIN_CHAT_ID:
        await message.reply(msg1)
    else:
        await message.reply(msg)

@dp.message(F.text.lower() == '🏧 top up')
async def topup(message: Message):
    await send_payment_note(message)

def get_user_balance(bot_user_id):
      conn = sqlite3.connect('user_data.db')
      cursor = conn.cursor()
      cursor.execute("SELECT balance FROM users WHERE bot_user_id = ?", (bot_user_id,))
      result = cursor.fetchone()
      return result[0] if result else 0.0

@dp.message(F.text.lower() == '🏧 pin gen..')
async def generate_pin(message: Message):
    a = 1
    b = 5
    amount = int(a) * int(b)
    pin = await generate_custom_code(a, b)
    await message.reply(f'Amount: ${amount}'
                        f'\n\n<code>p{pin}</code>')

# Command handler for /balance
@dp.message(F.text.lower() == '💰 check bal')
async def cmd_balance(message: types.Message):
    bot_user_id = message.from_user.id
    conn = sqlite3.connect('user_data.db')
    cursor = conn.cursor()

    # Fetch balance from database
    cursor.execute("SELECT balance FROM users WHERE bot_user_id=?", (bot_user_id,))
    balance = cursor.fetchone()

    if balance:
        await message.reply(f"Your current balance is: ${balance[0]}")
    else:
        await message.reply("You don't have a balance set yet.\nReason: You are not registered as a reseller yet.\n\nContact @teslassh for the Reseller Recharge Token(RRT)")


@dp.callback_query(lambda query: query.data.startswith('make_the_payment_'))
async def handle_accept_ad_callback(query: types.CallbackQuery):
    parts = query.data.split('_')
    requester_id = int(parts[3])
    builder = InlineKeyboardBuilder()
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='⭕️ AIRTEL UG', callback_data=f"pay_airtel_{requester_id}"),
         InlineKeyboardButton(text='🟡 MTN GH', callback_data=f"pay_mtn_{requester_id}")],
        [InlineKeyboardButton(text='How it works🤔?', callback_data=f"how_it_works_{requester_id}")]
    ])
    builder.attach(InlineKeyboardBuilder.from_markup(markup))
    await query.message.reply("<b>PAYMENT METHOD</b>\n───────────────────────\n\n"
                              "<i>This payment window is managed by the owners of @UDPCUSTOM</i>",
                              parse_mode=ParseMode.HTML, disable_web_page_preview=True, reply_markup=builder.as_markup())
@dp.callback_query(lambda query: query.data.startswith('pay_'))
async def handle_buy_callback(query: types.CallbackQuery):
    parts = query.data.split('_')
    requester_id = int(parts[2])
    product = parts[1]

    if product == 'airtel':
        amount = 18500
        state = STATE_TO_BUY_VPS
    elif product == 'mtn':
        amount = 18500
        state = STATE_TO_BUY_FILE
    else:
        await query.answer('Invalid product selected.')
        return

    await query.answer('Please Enter Your Phone number (no country code)')
    user_states[requester_id] = state
    await bot.send_message(requester_id, 'Please enter your phone number in the format:\n\n <i>07XXXXXX or 02XXXXXX or 03XXXXXX</i>:',
                           parse_mode=ParseMode.HTML)
@dp.message(lambda message: user_states.get(message.chat.id) in [STATE_TO_BUY_VPS, STATE_TO_BUY_FILE, STATE_TO_BUY_ACCOUNT])
async def handle_phone_number(message: types.Message):
    phone_number = message.text
    user_id = message.chat.id
    state = user_states.get(user_id)
    amount = 0

    if state == STATE_TO_BUY_VPS:
        amount = 18500
    elif state == STATE_TO_BUY_FILE:
        amount = 18500
    elif state == STATE_TO_BUY_ACCOUNT:
        amount = 18500

    if (phone_number.startswith('07') or phone_number.startswith('02') or phone_number.startswith('03')) and len(phone_number) == 10:
        user_states[user_id] = STATE_NONE
        suga = await message.reply('Obtaining your OTP...')

        payload = {
            "amount": amount,
            "phonenumber": phone_number,
            "email": "resellers@udpcustom.com",
            "redirect_url": "https://rave-webhook.herokuapp.com/receivepayment",
            "IP": ""
        }

        try:
            res = rave.UGMobile.charge(payload)
            pay_link = res['link']
            builder = InlineKeyboardBuilder()
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text='Pay Now', url=pay_link)]
            ])
            builder.attach(InlineKeyboardBuilder.from_markup(markup))
            rio = await bot.send_message(user_id, f"Use the <u>Flutterwave OTP</u> You just received.\n\n"
                                           f"<i><b>OTP</b> expires in 5 minutes</i>\n"
                                           f" Click the <b><i>Pay Now</i></b> Button below.", parse_mode=ParseMode.HTML, reply_markup=builder.as_markup())
            await asyncio.sleep(2)
            await suga.delete()
            await asyncio.sleep(300)
            await rio.delete()
        except RaveExceptions.TransactionChargeError as e:
            await bot.send_message(user_id, f"Transaction Charge Error: {e.err}")
        except RaveExceptions.TransactionVerificationError as e:
            await bot.send_message(user_id, f"Transaction Verification Error: {e.err['errMsg']}")
    else:
        await bot.send_message(user_id, 'Invalid phone number format. Please enter the phone number in the format 07XXXXXX:')

@dp.callback_query(lambda query: query.data.startswith('how_it_works_'))
async def handle_accept_ad_callback(query: types.CallbackQuery):
    parts = query.data.split('_')
    requester_id = int(parts[3])
    async with ChatActionSender.typing(bot=bot, chat_id=requester_id):
        await asyncio.sleep(3)
        msg_reply = ('<b>Dear valued Reseller, We appreciate your interest in our services. To facilitate a seamless payment process, please follow these steps:</b>\n──────────────────────────\n\n'
                     '<i>1. Select the payment method you want to use (Airtel UG or MTN GH)\n\n'
                     '2. You will be asked to enter phone number you want to pay with.\n\n'
                     '3. We will generate the OTP through Flutterwave and send it to you via SMS and WhatsApp.\n\n'
                     '4. Click the "Pay Now" button and enter the received OTP to confirm the payment.\n\n'
                     '5. The exact amount you have paid will then be added to your balances and can be viewed by using the "💰 Check Bal" button</i>\n\n──────────────────────────\n\n'
                     'Thanks for doing business with us. Should you have any questions or concerns, please feel free to reach out to us @teslassh or @hackwell101.\n'
                     '\n<b><i>Best regards, Nic </i> </b>')
        await bot.send_message(chat_id=requester_id, text=msg_reply)
@dp.callback_query()
async def handle_callback(query: types.CallbackQuery):
    user_id = query.from_user.id
    user_state = user_states.get(user_id)

    if user_state == "awaiting_server_selection_for_users":
        if query.data.startswith("view_users_"):
            server = query.data.split("_")[-1].upper()
            users = get_users_for_bot_user(user_id)

            valid_users = []
            for user in users:
                username, server_db, days, password, config, date_added = user
                if not (username == "user" and server_db == "global" or server_db != server):
                    valid_users.append(user)

            if not valid_users:
                response = f"<b><i>You have no Clients on this {server} server yet.</i></b>"
            else:
                response = f"<i>Users on <b>{server}</b> server</i>\n\n"
                for user in valid_users:
                    username, server_db, days, password, config, date_added = user

                    date_added = datetime.strptime(date_added, '%Y-%m-%d %H:%M:%S')
                    expiration_date = date_added + timedelta(days=days)
                    remaining_days = (expiration_date - datetime.now()).days

                    if remaining_days <= 0:
                        remaining_days = "<i><b>Already Expired</b></i>"
                    else:
                        remaining_days = f"{remaining_days} days"

                    response += (f"<b>Username:</b> {username}\n"
                                 f"<b>Expires in:</b> {remaining_days}\n"
                                 f"<b>Date Added:</b> {date_added.strftime('%Y-%m-%d')}\n"
                                 f"Config: <code>{config}</code>\n\n"
                                 )
            await query.message.reply(response)
        else:
            await query.message.reply("Invalid server selection. Please try again.")
            user_states[user_id] = None
    elif user_state == "awaiting_server_selection":
        if query.data.startswith("add_to_"):
            server = query.data.split("_")[-1].upper()
            await bot.send_message(query.message.chat.id, '<b>Enter user details in the format:</b> \n─────────────────────\n[username] [password] [days]\n\n<b>Example:</b>\n─────────────\n\n<code>John p@sswd! 30</code>')
            user_states[user_id] = f"awaiting_user_details_{server}"

    elif user_state == "awaiting_server_selection_del":
        if query.data.startswith("user_del_"):
            server = query.data.split("_")[-1].upper()
            await bot.send_message(query.message.chat.id, 'Enter username to delete:')
            user_states[user_id] = f"awaiting_user_deletion_{server}"

# Example function to update user's balance in database
def update_balance(bot_user_id, amount):
    # Replace with your database update logic
      conn = sqlite3.connect('user_data.db')
      cursor = conn.cursor()
    # Example pseudo-code:
      cursor.execute("UPDATE users SET balance = balance + ? WHERE bot_user_id = ?", (amount, bot_user_id))
      conn.commit()
      conn.close()

# Function to handle /pin command
async def handle_pin(message):
    # Extracting PIN code from message
    match = re.match(r'p(\d{12})', message.text)
    if not match:
        await message.reply("Invalid PIN format. Please use /pin {code}.")
        return

    pin_code = match.group(1)

    try:
        # Calculate amount based on first and sixth digits
        first_digit = int(pin_code[0])
        sixth_digit = int(pin_code[5])
        amount = first_digit * sixth_digit
        bot_user_id = message.from_user.id

        with open('rrt.txt', 'r+') as f:
            content = f.read()
            if pin_code in content:
                await message.reply('This pin was used already')
                return
            else:
                f.write(pin_code + '\n')
              # Update user's balance (assuming you have a function for this)
                update_balance(bot_user_id, amount)

                # Inform user about the top-up
                await message.reply(f"Your account has been topped up with ${amount}.")
                await bot.send_message(ADMIN_CHAT_ID, f'The user with chat ID <code>{message.from_user.id}</code> has topped up with this pin <code>{message.text}</code>')

    except Exception as e:
        await message.reply(f"Error processing PIN: {e}")

@dp.message()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    text = message.text.split()
    admin_msg = message.text.split('~')
    user_state = user_states.get(user_id)


    if text[0].lower() == '/dismiss':
        # Handle dismissing a seller.
        chat_id = int(text[1])
        await remove_seller(chat_id)
        return
    if user_id == ADMIN_CHAT_ID:

        if admin_msg[0].lower() == 'updates':
            msg = admin_msg[1]
            bot_user_id = await get_all_bot_user_ids()
            for seller_id in bot_user_id:
                try:
                    if seller_id == ADMIN_CHAT_ID:
                        continue
                    await bot.send_message(seller_id, msg)
                    await bot.send_message(ADMIN_CHAT_ID, 'Operation complete!')
                except Exception as e:
                    await message.answer(f'This chat ID: {user_id} cant be reached')
            return

    if message.text.startswith('p'):
        # Handle PIN command separately
        await handle_pin(message)
        return

    if user_state and user_state.startswith("awaiting_user_details_"):
        server = user_state.split("_")[-1]
        if len(text) == 3:
            # Check user's balance before proceeding
            bot_user_id = message.from_user.id
            current_balance = get_user_balance(bot_user_id)
            if current_balance >= 0.4:
                # Proceed with adding the user to the server
                username, password, days = text
                output = await add_user_to_server(server, username, password, days, user_id)
                IP = creds.SERVER_CREDENTIALS[server]['host']
                UDPl = f"<code>{IP}:1-65535@{username}:{password}</code>"
                if not output:
                    await message.reply(f"{username} has been added successfully to {server}\n\n"
                                    f"<b>Server Details:</b>\n"
                                    f"{UDPl}\n\n"
                                        f"Expires in {days}")
                    # Deduct the amount and update balance
                    update_balance(bot_user_id, -0.4)
                    user_states[user_id] = None
                else:
                    await message.reply('This server is currently under close maintenance. Try again later!')
            else:
                await message.reply("Insufficient balance. Please top up your account.")
        else:
            await message.reply("Invalid format. Please enter details in the format: username password days")

    elif user_state and user_state.startswith("awaiting_user_deletion_"):
        server = user_state.split("_")[-1]
        if len(text) == 1:
            username = text[0]
            output = await rem_user(server, username)
            if not output:
                await message.reply(f"Operation on {server} Server is complete!")
                user_states[user_id] = None

            else:
                await message.reply(f'The user does not exist or this {server} server is currently under maintenance')
        else:
            await message.reply("Invalid format. Please enter the username to delete")
    else:
            await message.reply("Unknown command or invalid input.")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(dp.start_polling(bot))
