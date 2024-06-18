from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

keyb = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text='👨‍👦 Create User'),
            KeyboardButton(text='🙅 kick user'),
            KeyboardButton(text='👩‍👩‍👧 My Clients')
        ],
[
            KeyboardButton(text='💰 Check Bal'),
            KeyboardButton(text='🏧 Top Up'),
            KeyboardButton(text='🆘 Help')
        ]

    ],
    resize_keyboard=True
)

admin_keyb = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text='👨‍👦 Create User'),
            KeyboardButton(text='🙅 kick user'),
            KeyboardButton(text='👩‍👩‍👧 My Clients')
        ],
[
            KeyboardButton(text='💰 Check Bal'),
            KeyboardButton(text='🏧 Pin Gen..'),
            KeyboardButton(text='🆘 Help')
        ]

    ],
    resize_keyboard=True
)
