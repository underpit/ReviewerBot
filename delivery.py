from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

# Hardcode state numbers (no import from main to avoid cycle)
DELIVERY_LIKES = 10
DELIVERY_RATING = 11
DELIVERY_REVIEW_TEXT = 12
MORE_REVIEWS = 1  # Hardcode for return after review

async def delivery_likes(update_or_query, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Initial show of likes buttons for delivery (called after category selection)."""
    # Detect if first arg is CallbackQuery (manual call) or Update (normal handler)
    if hasattr(update_or_query, 'callback_query'):
        query = update_or_query.callback_query
    else:
        query = update_or_query  # It's the query itself from manual call

    # Answer if it's a query (safe for both)
    if hasattr(query, 'answer'):
        await query.answer()

    selected = set()
    context.user_data['current_likes'] = selected
    options = {'speed': 'СКОРОСТЬ', 'cost': 'СТОИМОСТЬ', 'courier': 'КУРЬЕР - ОГОНЬ'}

    keyboard = [
        [
            InlineKeyboardButton(f"{'✅ ' if 'speed' in selected else ''}{options['speed']}", callback_data="likes_speed"),
            InlineKeyboardButton(f"{'✅ ' if 'cost' in selected else ''}{options['cost']}", callback_data="likes_cost"),
        ],
        [
            InlineKeyboardButton(f"{'✅ ' if 'courier' in selected else ''}{options['courier']}", callback_data="likes_courier"),
            InlineKeyboardButton("ВСЁ", callback_data="likes_all"),
        ],
        [InlineKeyboardButton("Готово", callback_data="likes_done")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text("Что понравилось больше всего?", reply_markup=reply_markup)
    return DELIVERY_LIKES

async def delivery_likes_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles likes selection callbacks for delivery."""
    query = update.callback_query
    await query.answer()
    data = query.data
    selected = context.user_data['current_likes']
    options = ['speed', 'cost', 'courier']

    if data == 'likes_all':
        if len(selected) == len(options):
            selected.clear()
        else:
            selected.update(options)
    elif data.startswith('likes_') and data != 'likes_all' and data != 'likes_done':
        like = data.split('_')[1]
        if like in selected:
            selected.remove(like)
        else:
            if like in options:
                selected.add(like)
    elif data == 'likes_done':
        # Proceed to rating

        # Show rating buttons
        keyboard = [
            [
                InlineKeyboardButton("1", callback_data="rate_1"),
                InlineKeyboardButton("2", callback_data="rate_2"),
                InlineKeyboardButton("3", callback_data="rate_3"),
                InlineKeyboardButton("4", callback_data="rate_4"),
                InlineKeyboardButton("5 ", callback_data="rate_5"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.reply_text("Отлично! Оцените доставку по шкале", reply_markup=reply_markup)
        return DELIVERY_RATING

    # Update buttons
    all_selected = len(selected) == len(options)
    keyboard_options = {'speed': 'СКОРОСТЬ', 'cost': 'СТОИМОСТЬ', 'courier': 'КУРЬЕР - ОГОНЬ'}
    keyboard = [
        [
            InlineKeyboardButton(f"{'✅ ' if 'speed' in selected else ''}{keyboard_options['speed']}", callback_data="likes_speed"),
            InlineKeyboardButton(f"{'✅ ' if 'cost' in selected else ''}{keyboard_options['cost']}", callback_data="likes_cost"),
        ],
        [
            InlineKeyboardButton(f"{'✅ ' if 'courier' in selected else ''}{keyboard_options['courier']}", callback_data="likes_courier"),
            InlineKeyboardButton(f"{'✅ ' if all_selected else ''}ВСЁ", callback_data="likes_all"),
        ],
        [InlineKeyboardButton("Готово", callback_data="likes_done")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text("Что понравилось больше всего?", reply_markup=reply_markup)
    except Exception as e:
        if "Message is not modified" in str(e):
            pass
        else:
            logging.getLogger(__name__).error(f"Error editing likes message: {e}")

    return DELIVERY_LIKES

async def delivery_rating_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles rating selection for delivery."""
    query = update.callback_query
    await query.answer()
    rating = int(query.data.split('_')[1])
    context.user_data['current_rating'] = rating

    await query.edit_message_text(f"Оценка выбрана: {rating} ({'⭐' * rating})")

    await query.message.reply_text("Отлично! А теперь напишите пару строк о товаре в произвольной форме")
    return DELIVERY_REVIEW_TEXT

async def delivery_review_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the review text and appends the review to the list (Delivery category)."""
    context.user_data['current_review_text'] = update.message.text

    # Append current review to reviews list
    review = {
        'category': context.user_data['current_category'],
        'product': '',  # No product for delivery
        'photo': None,  # No photo for delivery
        'rating': context.user_data['current_rating'],
        'likes': list(context.user_data.get('current_likes', [])),
        'review_text': context.user_data['current_review_text'],
    }
    context.user_data['reviews'].append(review)

    # Clear current data
    context.user_data.pop('current_rating', None)
    context.user_data.pop('current_likes', None)
    context.user_data.pop('current_review_text', None)

    # Ask if want to add more
    keyboard = [
        [
            InlineKeyboardButton("ДА", callback_data="more_yes"),
            InlineKeyboardButton("НЕТ", callback_data="more_no"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("Ваш отзыв сохранен и будет опубликован. Хотите оценить еще что-то?	", reply_markup=reply_markup)
    return MORE_REVIEWS  # 1