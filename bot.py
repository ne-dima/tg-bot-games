import os
import asyncio
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import Conflict, NetworkError, RetryAfter
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from games import CrocodileGame

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Экземпляр игры
crocodile_game = CrocodileGame()


def get_game_keyboard(chat_id: int, user_id: int = None) -> InlineKeyboardMarkup:
    """Создает клавиатуру для игры с учетом роли пользователя"""
    keyboard = []
    
    if crocodile_game.is_game_active(chat_id):
        current_host = crocodile_game.get_host(chat_id)
        is_guessed = crocodile_game.is_guessed(chat_id)
        
        # Если есть ведущий и он запрашивает клавиатуру
        if current_host is not None and user_id == current_host and not is_guessed:
            # Для ведущего: кнопки "Посмотреть слово" и "Новое слово"
            keyboard.append([InlineKeyboardButton("👁️ Посмотреть слово", callback_data='show_word')])
            keyboard.append([InlineKeyboardButton("🔄 Новое слово", callback_data='become_host')])
        else:
            # Для остальных: кнопка "Стать ведущим" (будет неактивна, если ведущий уже есть)
            keyboard.append([InlineKeyboardButton("🐊 Стать ведущим", callback_data='become_host')])
    else:
        # Если игра не активна, показываем только кнопку "Стать ведущим"
        keyboard.append([InlineKeyboardButton("🐊 Стать ведущим", callback_data='become_host')])
    
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    keyboard = [
        [InlineKeyboardButton("🎮 Выбрать игру", callback_data='choose_game')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        "👋 Привет! Я бот для игр в чатах.\n\n"
        "Выбери игру из списка и начни играть!"
    )
    
    await update.message.reply_text(text, reply_markup=reply_markup)


async def choose_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора игры"""
    query = update.callback_query
    await query.answer()
    
    # Проверяем, что команда вызвана в группе
    if update.effective_chat.type not in ['group', 'supergroup']:
        await query.edit_message_text(
            "⚠️ Эта команда работает только в групповых чатах!"
        )
        return
    
    chat_id = update.effective_chat.id
    
    keyboard = [
        [InlineKeyboardButton("🐊 Крокодил", callback_data='game_crocodile')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🎮 Выбери игру:",
        reply_markup=reply_markup
    )


async def start_crocodile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает игру Крокодил"""
    query = update.callback_query
    
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if crocodile_game.is_game_active(chat_id):
        reply_markup = get_game_keyboard(chat_id, user_id)
        
        await query.answer()
        await query.edit_message_text(
            "🐊 Игра Крокодил уже идет!\n\n"
            "Нажми кнопку, чтобы стать ведущим и получить слово для объяснения.",
            reply_markup=reply_markup
        )
        return
    
    # Запускаем игру
    crocodile_game.start_game(chat_id)
    
    # Устанавливаем первого ведущего
    word = crocodile_game.set_host(chat_id, user_id)
    
    reply_markup = get_game_keyboard(chat_id, user_id)
    
    # Показываем слово во всплывающем окне
    await query.answer(
        text=f"📝 Твое слово: {word}\n\nОбъясни его, не называя!",
        show_alert=True
    )
    
    await query.edit_message_text(
        f"🐊 Игра Крокодил началась!\n\n"
        f"@{update.effective_user.username or update.effective_user.first_name} - ты ведущий!\n\n"
        f"Слово показано во всплывающем окне. Объясни его, не называя! Остальные должны отгадать.",
        reply_markup=reply_markup
    )


async def show_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает слово ведущему во всплывающем окне"""
    query = update.callback_query
    
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if not crocodile_game.is_game_active(chat_id):
        await query.answer("❌ Игра не активна.", show_alert=True)
        return
    
    # Проверяем, является ли пользователь ведущим
    current_host = crocodile_game.get_host(chat_id)
    if current_host != user_id:
        await query.answer("⚠️ Только ведущий может посмотреть слово!", show_alert=True)
        return
    
    # Получаем слово
    word = crocodile_game.get_host_word(chat_id, user_id)
    if word:
        await query.answer(
            text=f"📝 Твое слово: {word}\n\nОбъясни его, не называя!",
            show_alert=True
        )
    else:
        await query.answer("❌ Слово не найдено.", show_alert=True)


async def become_host(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Делает пользователя ведущим или дает новое слово текущему ведущему"""
    query = update.callback_query
    
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if not crocodile_game.is_game_active(chat_id):
        await query.answer("❌ Игра не активна. Начни новую игру!", show_alert=True)
        return
    
    # Проверяем, есть ли уже ведущий и слово еще не отгадано
    current_host = crocodile_game.get_host(chat_id)
    is_guessed = crocodile_game.is_guessed(chat_id)
    
    # Если текущий ведущий нажимает кнопку - даем новое слово
    is_new_word = current_host is not None and current_host == user_id and not is_guessed
    
    # Если есть ведущий и слово еще не отгадано, не позволяем другому стать ведущим
    if current_host is not None and current_host != user_id and not is_guessed:
        await query.answer("⏳ Сейчас уже есть ведущий! Дождись, пока слово отгадают или станет ведущим другой игрок.", show_alert=True)
        return
    
    # Даем новое слово (новому ведущему или текущему)
    word = crocodile_game.set_host(chat_id, user_id)
    
    reply_markup = get_game_keyboard(chat_id, user_id)
    
    # Показываем слово во всплывающем окне
    await query.answer(
        text=f"📝 Твое слово: {word}\n\nОбъясни его, не называя!",
        show_alert=True
    )
    
    if is_new_word:
        # Если это новое слово для текущего ведущего
        await query.edit_message_text(
            f"🔄 Ведущий получил новое слово!\n\n"
            f"@{update.effective_user.username or update.effective_user.first_name} продолжает быть ведущим.\n\n"
            f"Слово показано во всплывающем окне. Объясни его, не называя! Остальные должны отгадать.",
            reply_markup=reply_markup
        )
    else:
        # Если это новый ведущий
        await query.edit_message_text(
            f"🐊 @{update.effective_user.username or update.effective_user.first_name} стал ведущим!\n\n"
            f"Слово показано во всплывающем окне. Объясни его, не называя! Остальные должны отгадать.",
            reply_markup=reply_markup
        )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает текстовые сообщения для проверки отгадок"""
    if update.effective_chat.type not in ['group', 'supergroup']:
        return
    
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # Проверяем наличие текста
    if not update.message or not update.message.text:
        return
    
    text = update.message.text
    
    # Пропускаем команды бота
    if text.startswith('/'):
        return
    
    # Проверяем, активна ли игра
    if not crocodile_game.is_game_active(chat_id):
        return
    
    # Проверяем, не отгадано ли уже слово
    if crocodile_game.is_guessed(chat_id):
        return
    
    # Проверяем отгадку
    is_correct, is_host = crocodile_game.check_guess(chat_id, user_id, text)
    
    if is_correct:
        # Слово отгадано!
        guesser_name = update.effective_user.username or update.effective_user.first_name
        current_score = crocodile_game.get_score(chat_id, user_id)
        
        reply_markup = get_game_keyboard(chat_id, user_id)
        
        await update.message.reply_text(
            f"🎉 Ты отгадал, @{guesser_name}!\n\n"
            f"💯 Твои очки: <b>{current_score}</b>\n"
            f"Посмотреть статистику: /stats",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        
        # Удаляем сообщение с отгадкой (опционально, можно закомментировать)
        # try:
        #     await update.message.delete()
        # except Exception as e:
        #     logger.warning(f"Не удалось удалить сообщение: {e}")


async def stop_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Останавливает игру (только для админов или в личке)"""
    chat_id = update.effective_chat.id
    
    if crocodile_game.is_game_active(chat_id):
        crocodile_game.stop_game(chat_id)
        await update.message.reply_text("🛑 Игра остановлена.")
    else:
        await update.message.reply_text("❌ Игра не активна.")


async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статистику по очкам в группе"""
    chat_id = update.effective_chat.id
    scores = crocodile_game.get_all_scores(chat_id)
    
    if not scores:
        await update.message.reply_text("📊 Статистика пуста. Начните играть, чтобы заработать очки!")
        return
    
    # Сортируем по очкам (от большего к меньшему)
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    
    # Формируем текст статистики
    stats_text = "📊 <b>Таблица лидеров:</b>\n\n"
    
    for rank, (user_id, score) in enumerate(sorted_scores, 1):
        try:
            # Получаем информацию о пользователе
            user = await context.bot.get_chat_member(chat_id, user_id)
            username = user.user.username
            first_name = user.user.first_name
            
            # Формируем имя для отображения
            display_name = f"@{username}" if username else first_name
            
            # Меди и эмодзи для топ-3
            medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"{rank}."
            
            stats_text += f"{medal} {display_name}: <b>{score}</b> очков\n"
        except Exception as e:
            # Если не удалось получить информацию о пользователе, используем ID
            logger.warning(f"Не удалось получить информацию о пользователе {user_id}: {e}")
            medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"{rank}."
            stats_text += f"{medal} ID{user_id}: <b>{score}</b> очков\n"
    
    await update.message.reply_text(stats_text, parse_mode='HTML')


async def check_game_timeouts(context: ContextTypes.DEFAULT_TYPE):
    """Проверяет таймеры всех активных игр"""
    try:
        # Получаем список всех активных чатов
        active_chats = list(crocodile_game.active_games.keys())
        
        for chat_id in active_chats:
            # Проверяем, не истекло ли время
            if crocodile_game.check_timeout(chat_id):
                # Время истекло, завершаем игру
                game = crocodile_game.active_games.get(chat_id)
                if game is None:
                    continue
                    
                word = game.get('current_word', 'неизвестное')
                host_id = game.get('host_user_id')
                
                # Отправляем сообщение в чат о завершении игры
                try:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=(
                            f"⏰ <b>Время истекло!</b>\n\n"
                            f"Никто не отгадал слово за 10 минут.\n"
                            f"Загаданное слово было: <b>{word}</b>\n\n"
                            f"Игра завершена. Чтобы начать новую игру, отправьте /start"
                        ),
                        parse_mode='HTML'
                    )
                except Exception as e:
                    logger.warning(f"Не удалось отправить сообщение о таймауте в чат {chat_id}: {e}")
                
                # Завершаем игру
                crocodile_game.stop_game(chat_id)
                logger.info(f"Игра завершена по таймауту в чате {chat_id}")
                
    except Exception as e:
        logger.error(f"Ошибка при проверке таймеров: {e}")


def main():
    """Запуск бота"""
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN не установлен! Создайте файл .env и добавьте токен.")
        return
    
    # Инициализация после запуска приложения
    async def post_init(app: Application) -> None:
        """Инициализация после запуска приложения"""
        # Запускаем проверку таймеров как периодическую задачу
        app.job_queue.run_repeating(
            check_game_timeouts,
            interval=30,  # Проверяем каждые 30 секунд
            first=10  # Первая проверка через 10 секунд после запуска
        )
        logger.info("Периодические задачи запущены")
    
    # Создаем приложение с post_init
    # job_queue создается автоматически при установленном пакете [job-queue]
    application = Application.builder().token(token).post_init(post_init).build()
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop_game))
    application.add_handler(CommandHandler("stats", show_stats))
    application.add_handler(CallbackQueryHandler(choose_game, pattern='^choose_game$'))
    application.add_handler(CallbackQueryHandler(start_crocodile, pattern='^game_crocodile$'))
    application.add_handler(CallbackQueryHandler(become_host, pattern='^become_host$'))
    application.add_handler(CallbackQueryHandler(show_word, pattern='^show_word$'))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Обработчик ошибок
    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик ошибок"""
        error = context.error
        
        # Игнорируем конфликты (несколько экземпляров бота)
        if isinstance(error, Conflict):
            logger.warning("Конфликт: возможно запущен другой экземпляр бота. Ошибка игнорируется.")
            return
        
        # Игнорируем сетевые ошибки (они обрабатываются автоматически)
        if isinstance(error, NetworkError):
            logger.warning(f"Сетевая ошибка: {error}. Повторная попытка...")
            return
        
        # Обрабатываем RateLimit
        if isinstance(error, RetryAfter):
            logger.warning(f"Rate limit: {error.retry_after} секунд")
            return
        
        # Логируем остальные ошибки
        logger.error(f"Ошибка при обработке обновления: {error}", exc_info=error)
    
    # Регистрируем обработчик ошибок
    application.add_error_handler(error_handler)
    
    # Запускаем бота
    logger.info("Бот запущен!")
    
    # Запускаем polling с обработкой ошибок
    try:
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True  # Удаляем ожидающие обновления при запуске
        )
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=e)


if __name__ == '__main__':
    main()

