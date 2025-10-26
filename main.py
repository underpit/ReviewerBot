import logging
import json
import sqlite3
from datetime import datetime
from enum import IntEnum
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
import telegram.error
import traceback
from tea import (
    tea_product, tea_photo, tea_photo_reprompt, tea_rating, tea_likes, tea_review_text
)
from service import (
    service_likes, service_likes_handler, service_rating_handler, service_review_text
)
from delivery import (
    delivery_likes, delivery_likes_handler, delivery_rating_handler, delivery_review_text
)
from form import (
    format_tea_review, format_service_review, format_delivery_review
)
# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)
# Initialize SQLite database
def init_db():
    conn = sqlite3.connect('reviews.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            product TEXT,
            photo_id TEXT,
            rating INTEGER NOT NULL,
            likes TEXT NOT NULL,
            review_text TEXT NOT NULL,
            is_anonymous BOOLEAN NOT NULL,
            timestamp TEXT NOT NULL,
            is_deleted BOOLEAN NOT NULL DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()
init_db()  # Create DB on startup
# Cached bot_config (load once)
try:
    with open("bot_config.json", "r", encoding="utf-8") as f:
        bot_config = json.load(f)
except (FileNotFoundError, json.JSONDecodeError) as e:
    logger.error(f"Bot config error: {e}")
    bot_config = {"telegram_bot_token": "fallback_token", "channel_id": "@fallback_channel"}
BOT_TOKEN = bot_config["telegram_bot_token"]
CHANNEL_ID = bot_config["channel_id"]
# States as IntEnum for readability and faster lookups
class States(IntEnum):
    CATEGORY = 0
    MORE_REVIEWS = 1
    TEA_PRODUCT = 2
    TEA_PHOTO = 3
    TEA_RATING = 4
    TEA_LIKES = 5
    TEA_REVIEW_TEXT = 6
    SERVICE_LIKES = 7
    SERVICE_RATING = 8
    SERVICE_REVIEW_TEXT = 9
    DELIVERY_LIKES = 10
    DELIVERY_RATING = 11
    DELIVERY_REVIEW_TEXT = 12
    PREVIEW = 13
    EDIT_MENU = 14
    EDIT_RATING = 15
    EDIT_LIKES = 16
    EDIT_PRODUCT = 17
    EDIT_REVIEW = 18
    FINAL_CONFIRM = 19
    NAME = 20
    HISTORY = 21
    DELETE_SPECIFIC = 22
    EDIT_PERSON = 23  # New state for editing person/name
# Common rating keyboard (optimized, used in all rating handlers)
def get_rating_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("1", callback_data="rate_1"),
            InlineKeyboardButton("2", callback_data="rate_2"),
            InlineKeyboardButton("3", callback_data="rate_3"),
            InlineKeyboardButton("4", callback_data="rate_4"),
            InlineKeyboardButton("5", callback_data="rate_5"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)
# Category routing dict (unchanged)
CATEGORY_ROUTING = {
    'чай': {'product': tea_product, 'likes_state': States.TEA_LIKES, 'rating_state': States.TEA_RATING, 'review_state': States.TEA_REVIEW_TEXT, 'format': format_tea_review, 'has_product': True},
    'сервис': {'product': None, 'likes_state': States.SERVICE_LIKES, 'rating_state': States.SERVICE_RATING, 'review_state': States.SERVICE_REVIEW_TEXT, 'format': format_service_review, 'has_product': False},
    'доставка': {'product': None, 'likes_state': States.DELIVERY_LIKES, 'rating_state': States.DELIVERY_RATING, 'review_state': States.DELIVERY_REVIEW_TEXT, 'format': format_delivery_review, 'has_product': False},
}
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /start command, shows buttons to start review or view history."""
    if update.message.chat.type != "private":
        await update.message.reply_text("Please use this bot in a private chat.")
        return
    keyboard = ReplyKeyboardMarkup([["История", "Оставить отзыв"]], resize_keyboard=True, one_time_keyboard=False)
    await update.message.reply_text("Приветствую! Выберите действие:", reply_markup=keyboard)
async def start_review(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the review process by asking for name."""
    if update.message.chat.type != "private":
        await update.message.reply_text("Please use this bot in a private chat.")
        return ConversationHandler.END
    # Initialize reviews list
    context.user_data['reviews'] = []
    user = update.message.from_user
    nickname = f"@{user.username}" if user.username else user.first_name
    keyboard = [
        [
            InlineKeyboardButton(f"Использовать {nickname}", callback_data="use_username"),
            InlineKeyboardButton("Анонимно", callback_data="anonymous"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Как к вам обращаться? (Можете написать свое имя)", reply_markup=reply_markup)
    return States.NAME
async def history_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles 'История' button, shows user's past reviews from DB in oldest-to-newest order."""
    if update.message.chat.type != "private":
        await update.message.reply_text("Please use this bot in a private chat.")
        return ConversationHandler.END
    user_id = update.effective_user.id
    conn = sqlite3.connect('reviews.db')
    c = conn.cursor()
    c.execute('SELECT * FROM reviews WHERE user_id = ? AND is_deleted = 0 ORDER BY timestamp ASC', (user_id,))
    reviews = c.fetchall()
    conn.close()
    if not reviews:
        await update.message.reply_text("У вас пока нет отзывов.")
        return ConversationHandler.END
    await update.message.reply_text("Ваши прошлые отзывы (от старых к новым):")
    for i, review in enumerate(reviews, 1):
        review_data = {
            'category': review[2],
            'product': review[3] or '',
            'photo': review[4],
            'rating': review[5],
            'likes': json.loads(review[6]),
            'review_text': review[7],
            'user_name': None if review[8] else context.user_data.get('user_name', None)
        }
        format_func = CATEGORY_ROUTING[review_data['category']]['format']
        formatted = format_func(review_data)
        preview = f"{review_data['category'].capitalize()}: {review_data.get('product', '') or review_data['review_text'][:20]}..."
        if review_data['photo']:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=review_data['photo'],
                caption=f"Отзыв {i} ({review[9]}): {preview}\n\n{formatted}",
                parse_mode="HTML"
            )
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Отзыв {i} ({review[9]}): {preview}\n\n{formatted}",
                parse_mode="HTML"
            )
    await update.message.reply_text("Это ваши прошлые отзывы. Хотите оставить новый?", reply_markup=ReplyKeyboardMarkup([["История", "Оставить отзыв"]], resize_keyboard=True))
    return ConversationHandler.END
async def name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles name selection or input."""
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == 'use_username':
        user = query.from_user
        user_name = f"@{user.username}" if user.username else user.first_name
        context.user_data['user_name'] = user_name
    elif data == 'anonymous':
        context.user_data['user_name'] = None
    # Proceed to category selection
    keyboard = [
        [
            InlineKeyboardButton("ЧАЙ", callback_data="чай"),
            InlineKeyboardButton("СЕРВИС", callback_data="сервис"),
            InlineKeyboardButton("ДОСТАВКА", callback_data="доставка"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text("На что пишем отзыв?", reply_markup=reply_markup)
    return States.CATEGORY
async def name_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles custom name text input."""
    context.user_data['user_name'] = update.message.text
    # Proceed to category
    keyboard = [
        [
            InlineKeyboardButton("ЧАЙ", callback_data="чай"),
            InlineKeyboardButton("СЕРВИС", callback_data="сервис"),
            InlineKeyboardButton("ДОСТАВКА", callback_data="доставка"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("На что пишем отзыв?", reply_markup=reply_markup)
    return States.CATEGORY
async def edit_person_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles editing person/name, shows selection step."""
    query = update.callback_query
    await query.answer()
    user = query.from_user
    nickname = f"@{user.username}" if user.username else user.first_name
    keyboard = [
        [
            InlineKeyboardButton(f"Использовать {nickname}", callback_data="use_username_edit"),
            InlineKeyboardButton("Анонимно", callback_data="anonymous_edit"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Измените, как к вам обращаться? (Можете написать свое имя)", reply_markup=reply_markup)
    return States.EDIT_PERSON
async def edit_person_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles callback for edited name."""
    query = update.callback_query
    await query.answer()
    data = query.data
    pending_data = context.user_data.get('pending_data', {})
    if data == 'use_username_edit':
        user = query.from_user
        user_name = f"@{user.username}" if user.username else user.first_name
        pending_data['user_name'] = user_name
    elif data == 'anonymous_edit':
        pending_data['user_name'] = None
    context.user_data['pending_data'] = pending_data
    category = pending_data['category']
    format_func = CATEGORY_ROUTING[category]['format']
    formatted = format_func(pending_data)
    keyboard = [
        [
            InlineKeyboardButton("Подтвердить", callback_data="confirm"),
            InlineKeyboardButton("Изменить", callback_data="edit"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(f"Вот ваш обновленный комментарий:\n\n{formatted}", reply_markup=reply_markup, parse_mode="HTML")
    context.user_data.pop('editing', None)
    return States.PREVIEW
async def edit_person_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles text input for edited name."""
    pending_data = context.user_data.get('pending_data', {})
    pending_data['user_name'] = update.message.text
    context.user_data['pending_data'] = pending_data
    category = pending_data['category']
    format_func = CATEGORY_ROUTING[category]['format']
    formatted = format_func(pending_data)
    keyboard = [
        [
            InlineKeyboardButton("Подтвердить", callback_data="confirm"),
            InlineKeyboardButton("Изменить", callback_data="edit"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(f"Вот ваш обновленный комментарий:\n\n{formatted}", reply_markup=reply_markup, parse_mode="HTML")
    context.user_data.pop('editing', None)
    return States.PREVIEW
async def category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles category selection and routes using dict."""
    query = update.callback_query
    await query.answer()
    selected_category = query.data
    context.user_data['current_category'] = selected_category
    routing = CATEGORY_ROUTING.get(selected_category, {})
    if not routing:
        await query.edit_message_text("Unknown category.")
        return ConversationHandler.END
    if routing['has_product']:
        await query.edit_message_text(f"Выбранная категория: {selected_category.upper()} \n\nВведите название продукта:")
        return States.TEA_PRODUCT
    else:
        await query.edit_message_text(f"Выбранная категория: {selected_category.capitalize()}")
        if routing.get('likes_state'):
            if selected_category == 'сервис':
                await service_likes(query, context)
            elif selected_category == 'доставка':
                await delivery_likes(query, context)
        return routing['likes_state']
async def more_reviews(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles 'more reviews' selection."""
    query = update.callback_query
    await query.answer()
    if query.data == 'more_yes':
        keyboard = [
            [
                InlineKeyboardButton("ЧАЙ", callback_data="чай"),
                InlineKeyboardButton("СЕРВИС", callback_data="сервис"),
                InlineKeyboardButton("ДОСТАВКА", callback_data="доставка"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("На что пишем отзыв?", reply_markup=reply_markup)
        return States.CATEGORY
    elif query.data == 'more_no':
        keyboard = [
            [InlineKeyboardButton("Опубликовать", callback_data="publish")],
            [
                InlineKeyboardButton("Удалить конкретный пост!", callback_data="delete_specific"),
                InlineKeyboardButton("Удалить всё!", callback_data="delete_all")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Подтвердите публикацию ваших отзывов:", reply_markup=reply_markup)
        return States.FINAL_CONFIRM
async def final_confirm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles final confirmation buttons for posting reviews."""
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == 'publish':
        await post_reviews(update, context)
        await query.edit_message_text("Отзывы опубликованы! Спасибо!")
        promo_text = ""
        try:
            with open('promo.json', 'r', encoding='utf-8') as f:
                promo = json.load(f)
                promo_text = f"{promo.get('text', '')} Промокод: {promo.get('code', '')}"
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Promo JSON error: {e}")
        if promo_text:
            await query.message.reply_text(promo_text)
        context.user_data.clear()
        return ConversationHandler.END
    elif data == 'delete_specific':
        reviews = context.user_data.get('reviews', [])
        if not reviews:
            await query.edit_message_text("Нет отзывов для удаления в текущей сессии.")
            return States.FINAL_CONFIRM
        await query.message.reply_text("Ваши отзывы в текущей сессии:")
        for i, review in enumerate(reviews, 1):
            format_func = CATEGORY_ROUTING[review['category']]['format']
            formatted = format_func(review)
            if review.get('photo'):
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=review['photo'],
                    caption=f"Отзыв №{i}:\n\n{formatted}",
                    parse_mode="HTML"
                )
            else:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"Отзыв №{i}:\n\n{formatted}",
                    parse_mode="HTML"
                )
        keyboard = []
        for i in range(len(reviews)):
            keyboard.append([InlineKeyboardButton(f"Отзыв №{i+1}", callback_data=f"delete_review_{i}")])
        keyboard.append([InlineKeyboardButton("Назад", callback_data="back_to_confirm")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Выберите отзыв для удаления:", reply_markup=reply_markup)
        return States.DELETE_SPECIFIC
    elif data == 'delete_all':
        context.user_data['reviews'] = []
        await query.edit_message_text("Все отзывы удалены.")
        keyboard = ReplyKeyboardMarkup([["История", "Оставить отзыв"]], resize_keyboard=True, one_time_keyboard=False)
        await query.message.reply_text("Приветствую! Выберите действие:", reply_markup=keyboard)
        return ConversationHandler.END
async def delete_specific_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles selection of a specific review to delete."""
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "back_to_confirm":
        keyboard = [
            [InlineKeyboardButton("Опубликовать", callback_data="publish")],
            [
                InlineKeyboardButton("Удалить конкретный пост!", callback_data="delete_specific"),
                InlineKeyboardButton("Удалить всё!", callback_data="delete_all")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Подтвердите публикацию ваших отзывов:", reply_markup=reply_markup)
        return States.FINAL_CONFIRM
    if data.startswith("delete_review_"):
        index = int(data.split("_")[-1])
        reviews = context.user_data.get('reviews', [])
        if 0 <= index < len(reviews):
            deleted_review = reviews.pop(index)
            await query.edit_message_text(f"Отзыв №{index + 1} удален.")
        else:
            await query.edit_message_text("Ошибка: Отзыв не найден.")
        keyboard = [
            [InlineKeyboardButton("Опубликовать", callback_data="publish")],
            [
                InlineKeyboardButton("Удалить конкретный пост!", callback_data="delete_specific"),
                InlineKeyboardButton("Удалить всё!", callback_data="delete_all")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Подтвердите публикацию ваших отзывов:", reply_markup=reply_markup)
        return States.FINAL_CONFIRM
async def preview_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles preview confirm/edit."""
    query = update.callback_query
    await query.answer()
    if query.data == 'confirm':
        pending_review = context.user_data.get('pending_review', {})
        if pending_review:
            context.user_data['reviews'].append(pending_review)
            context.user_data.pop('pending_review', None)
            context.user_data.pop('pending_data', None)
        keyboard = [
            [InlineKeyboardButton("Да", callback_data="more_yes")],
            [InlineKeyboardButton("Нет", callback_data="more_no")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Хотите оставить ещё один отзыв?", reply_markup=reply_markup)
        return States.MORE_REVIEWS
    elif query.data == 'edit':
        category = context.user_data.get('pending_data', {}).get('category', '')
        has_product = CATEGORY_ROUTING.get(category, {}).get('has_product', False)
        keyboard = [[InlineKeyboardButton("Лицо", callback_data="edit_person")]]
        if has_product:
            keyboard.append([InlineKeyboardButton("Продукт", callback_data="edit_product")])
        keyboard += [
            [InlineKeyboardButton("Рейтинг", callback_data="edit_rating")],
            [InlineKeyboardButton("Лучшие моменты", callback_data="edit_likes")],
            [InlineKeyboardButton("Отзыв", callback_data="edit_review")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Что хотите изменить?", reply_markup=reply_markup)
        return States.EDIT_MENU
async def edit_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles edit menu selection."""
    query = update.callback_query
    await query.answer()
    data = query.data
    context.user_data['editing'] = True
    if data == 'edit_person':
        return await edit_person_handler(update, context)
    elif data == 'edit_rating':
        reply_markup = get_rating_keyboard()
        await query.edit_message_text("Измените рейтинг:", reply_markup=reply_markup)
        return States.EDIT_RATING
    elif data == 'edit_likes':
        category = context.user_data.get('pending_data', {}).get('category', '')
        selected = set(context.user_data.get('pending_data', {}).get('likes', []))
        context.user_data['current_likes'] = selected
        if category == 'чай':
            options = {'taste': 'ВКУС', 'aroma': 'АРОМАТ', 'feeling': 'ОЩУЩЕНИЕ ОТ ЧАЯ'}
            all_selected = len(selected) == len(options)
            keyboard = [
                [
                    InlineKeyboardButton(f"{'✅ ' if 'taste' in selected else ''}{options['taste']}", callback_data="likes_taste"),
                    InlineKeyboardButton(f"{'✅ ' if 'aroma' in selected else ''}{options['aroma']}", callback_data="likes_aroma"),
                ],
                [
                    InlineKeyboardButton(f"{'✅ ' if 'feeling' in selected else ''}{options['feeling']}", callback_data="likes_feeling"),
                    InlineKeyboardButton(f"{'✅ ' if all_selected else ''}ВСЁ", callback_data="likes_all"),
                ],
                [InlineKeyboardButton("Готово", callback_data="likes_done")],
            ]
        elif category == 'сервис':
            options = {'quality': 'КАЧЕСТВО', 'speed': 'СКОРОСТЬ', 'professionalism': 'ПРОФЕССИОНАЛИЗМ'}
            all_selected = len(selected) == len(options)
            keyboard = [
                [
                    InlineKeyboardButton(f"{'✅ ' if 'quality' in selected else ''}{options['quality']}", callback_data="likes_quality"),
                    InlineKeyboardButton(f"{'✅ ' if 'speed' in selected else ''}{options['speed']}", callback_data="likes_speed"),
                ],
                [
                    InlineKeyboardButton(f"{'✅ ' if 'professionalism' in selected else ''}{options['professionalism']}", callback_data="likes_professionalism"),
                    InlineKeyboardButton(f"{'✅ ' if all_selected else ''}ВСЁ", callback_data="likes_all"),
                ],
                [InlineKeyboardButton("Готово", callback_data="likes_done")],
            ]
        elif category == 'доставка':
            options = {'speed': 'СКОРОСТЬ', 'cost': 'СТОИМОСТЬ', 'courier': 'КУРЬЕР - 🔥'}
            all_selected = len(selected) == len(options)
            keyboard = [
                [
                    InlineKeyboardButton(f"{'✅ ' if 'speed' in selected else ''}{options['speed']}", callback_data="likes_speed"),
                    InlineKeyboardButton(f"{'✅ ' if 'cost' in selected else ''}{options['cost']}", callback_data="likes_cost"),
                ],
                [
                    InlineKeyboardButton(f"{'✅ ' if 'courier' in selected else ''}{options['courier']}", callback_data="likes_courier"),
                    InlineKeyboardButton(f"{'✅ ' if all_selected else ''}ВСЁ", callback_data="likes_all"),
                ],
                [InlineKeyboardButton("Готово", callback_data="likes_done")],
            ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Измените, что понравилось больше всего:", reply_markup=reply_markup)
        return States.EDIT_LIKES
    elif data == 'edit_product':
        await query.edit_message_text("Измените название продукта:")
        return States.EDIT_PRODUCT
    elif data == 'edit_review':
        await query.edit_message_text("Измените текст отзыва:")
        return States.EDIT_REVIEW
async def edit_rating_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles edit rating."""
    query = update.callback_query
    await query.answer()
    rating = int(query.data.split('_')[1])
    pending_data = context.user_data.get('pending_data', {})
    pending_data['rating'] = rating
    context.user_data['pending_data'] = pending_data
    category = pending_data['category']
    format_func = CATEGORY_ROUTING[category]['format']
    formatted = format_func(pending_data)
    keyboard = [
        [
            InlineKeyboardButton("Подтвердить", callback_data="confirm"),
            InlineKeyboardButton("Изменить", callback_data="edit"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(f"Вот ваш обновленный комментарий:\n\n{formatted}", reply_markup=reply_markup, parse_mode="HTML")
    context.user_data.pop('editing', None)
    return States.PREVIEW
async def edit_likes_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles edit likes (route to category-specific handler)."""
    category = context.user_data.get('pending_data', {}).get('category', '')
    if category == 'чай':
        return await tea_likes(update, context)
    elif category == 'сервис':
        return await service_likes_handler(update, context)
    elif category == 'доставка':
        return await delivery_likes_handler(update, context)
async def edit_product_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles edit product."""
    pending_data = context.user_data.get('pending_data', {})
    pending_data['product'] = update.message.text
    context.user_data['pending_data'] = pending_data
    category = pending_data['category']
    format_func = CATEGORY_ROUTING[category]['format']
    formatted = format_func(pending_data)
    keyboard = [
        [
            InlineKeyboardButton("Подтвердить", callback_data="confirm"),
            InlineKeyboardButton("Изменить", callback_data="edit"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(f"Вот ваш обновленный комментарий:\n\n{formatted}", reply_markup=reply_markup, parse_mode="HTML")
    context.user_data.pop('editing', None)
    return States.PREVIEW
async def edit_review_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles edit review text."""
    pending_data = context.user_data.get('pending_data', {})
    pending_data['review_text'] = update.message.text
    context.user_data['pending_data'] = pending_data
    category = pending_data['category']
    format_func = CATEGORY_ROUTING[category]['format']
    formatted = format_func(pending_data)
    keyboard = [
        [
            InlineKeyboardButton("Подтвердить", callback_data="confirm"),
            InlineKeyboardButton("Изменить", callback_data="edit"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(f"Вот ваш обновленный комментарий:\n\n{formatted}", reply_markup=reply_markup, parse_mode="HTML")
    context.user_data.pop('editing', None)
    return States.PREVIEW
async def post_reviews(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Posts all collected reviews to the channel using category-specific formatting."""
    reviews = context.user_data.get('reviews', [])
    if not reviews:
        logger.warning("No reviews to post.")
        if hasattr(update, 'callback_query'):
            await update.callback_query.message.reply_text("Нет отзывов для публикации.")
        return
    conn = sqlite3.connect('reviews.db')
    c = conn.cursor()
    for review in reviews:
        category = review.get('category', 'unknown')
        photo = review.get('photo')
        user_name = review.get('user_name', 'None')
        try:
            if category == 'чай':
                message = format_tea_review(review)
            elif category == 'сервис':
                message = format_service_review(review)
            elif category == 'доставка':
                message = format_delivery_review(review)
            else:
                logger.error(f"Invalid category: {category}")
                message = "Неизвестная отзыва."
            if len(message) > (4096 if photo else 16384):
                logger.error(f"Message too long for category {category}: {len(message)} characters")
                if hasattr(update, 'callback_query'):
                    await update.callback_query.message.reply_text(f"Ошибка: Отзыв для {category} слишком длинный.")
                continue
            logger.info(f"Posting review for category: {category}, user: {user_name}, has_photo: {bool(photo)}")
            if photo:
                try:
                    await context.bot.send_photo(
                        chat_id=CHANNEL_ID,
                        photo=photo,
                        caption=message,
                        parse_mode="HTML"
                    )
                    c.execute('''
                        INSERT INTO reviews (user_id, category, product, photo_id, rating, likes, review_text, is_anonymous, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        update.effective_user.id,
                        review['category'],
                        review.get('product'),
                        review.get('photo'),
                        review['rating'],
                        json.dumps(review['likes']),
                        review['review_text'],
                        1 if review.get('user_name') is None else 0,
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    ))
                    conn.commit()
                except telegram.error.BadRequest as e:
                    logger.error(f"BadRequest in send_photo for {category}: {e}, photo: {photo}")
                    if hasattr(update, 'callback_query'):
                        await update.callback_query.message.reply_text(f"Ошибка: Неверный формат фото для отзыва {category}.")
                    continue
                except telegram.error.Unauthorized as e:
                    logger.error(f"Unauthorized in send_photo: {e}")
                    if hasattr(update, 'callback_query'):
                        await update.callback_query.message.reply_text("Ошибка: Бот не имеет прав для публикации в канал.")
                    return
            else:
                try:
                    await context.bot.send_message(
                        chat_id=CHANNEL_ID,
                        text=message,
                        parse_mode="HTML"
                    )
                    c.execute('''
                        INSERT INTO reviews (user_id, category, product, photo_id, rating, likes, review_text, is_anonymous, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        update.effective_user.id,
                        review['category'],
                        review.get('product'),
                        review.get('photo'),
                        review['rating'],
                        json.dumps(review['likes']),
                        review['review_text'],
                        1 if review.get('user_name') is None else 0,
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    ))
                    conn.commit()
                except telegram.error.BadRequest as e:
                    logger.error(f"BadRequest in send_message for {category}: {e}")
                    if hasattr(update, 'callback_query'):
                        await update.callback_query.message.reply_text(f"Ошибка: Неверный формат сообщения для отзыва {category}.")
                    continue
                except telegram.error.Unauthorized as e:
                    logger.error(f"Unauthorized in send_message: {e}")
                    if hasattr(update, 'callback_query'):
                        await update.callback_query.message.reply_text("Ошибка: Бот не имеет прав для публикации в канал.")
                    return
        except Exception as e:
            logger.error(f"Error posting review for {category}: {e}\n{traceback.format_exc()}")
            if hasattr(update, 'callback_query'):
                await update.callback_query.message.reply_text("Извините, произошла ошибка при публикации одного из отзывов.")
    conn.close()
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the review process."""
    await update.message.reply_text("Отзыв отменен.")
    context.user_data.clear()
    return ConversationHandler.END
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors."""
    logger.error(f"Update {update} caused error {context.error}")
def main() -> None:
    """Run the bot."""
    application = Application.builder().token(BOT_TOKEN).read_timeout(30).write_timeout(30).connect_timeout(30).pool_timeout(30).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.Regex("История"), history_handler))
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("Оставить отзыв"), start_review)],
        states={
            States.NAME: [
                CallbackQueryHandler(name_handler, pattern="^(use_username|anonymous)$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, name_text_handler),
            ],
            States.CATEGORY: [CallbackQueryHandler(category)],
            States.TEA_PRODUCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, tea_product)],
            States.TEA_PHOTO: [
                MessageHandler(filters.PHOTO, tea_photo),
                MessageHandler(filters.ALL & ~filters.PHOTO & ~filters.COMMAND, tea_photo_reprompt),
            ],
            States.TEA_RATING: [CallbackQueryHandler(tea_rating, pattern="^rate_")],
            States.TEA_LIKES: [CallbackQueryHandler(tea_likes, pattern="^likes_")],
            States.TEA_REVIEW_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, tea_review_text)],
            States.SERVICE_LIKES: [CallbackQueryHandler(service_likes_handler, pattern="^likes_")],
            States.SERVICE_RATING: [CallbackQueryHandler(service_rating_handler, pattern="^rate_")],
            States.SERVICE_REVIEW_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, service_review_text)],
            States.DELIVERY_LIKES: [CallbackQueryHandler(delivery_likes_handler, pattern="^likes_")],
            States.DELIVERY_RATING: [CallbackQueryHandler(delivery_rating_handler, pattern="^rate_")],
            States.DELIVERY_REVIEW_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, delivery_review_text)],
            States.PREVIEW: [CallbackQueryHandler(preview_handler, pattern="^(confirm|edit)$")],
            States.EDIT_MENU: [CallbackQueryHandler(edit_menu_handler, pattern="^(edit_)")],
            States.EDIT_RATING: [CallbackQueryHandler(edit_rating_handler, pattern="^rate_")],
            States.EDIT_LIKES: [CallbackQueryHandler(edit_likes_handler, pattern="^likes_")],
            States.EDIT_PRODUCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_product_handler)],
            States.EDIT_REVIEW: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_review_handler)],
            States.EDIT_PERSON: [
                CallbackQueryHandler(edit_person_callback, pattern="^(use_username_edit|anonymous_edit)$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_person_text),
            ],
            States.MORE_REVIEWS: [CallbackQueryHandler(more_reviews, pattern="^more_")],
            States.FINAL_CONFIRM: [CallbackQueryHandler(final_confirm_handler, pattern="^(publish|delete_specific|delete_all)$")],
            States.DELETE_SPECIFIC: [CallbackQueryHandler(delete_specific_handler, pattern="^(delete_review_|back_to_confirm)")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    )
    application.add_handler(conv_handler)
    application.add_error_handler(error_handler)
    application.run_polling(drop_pending_updates=True)
if __name__ == "__main__":
    main()