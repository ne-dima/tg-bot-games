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
    await query.answer()
    
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if crocodile_game.is_game_active(chat_id):
        keyboard = [
            [InlineKeyboardButton("🐊 Стать ведущим", callback_data='become_host')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
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
    
    keyboard = [
        [InlineKeyboardButton("🐊 Стать ведущим", callback_data='become_host')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"🐊 Игра Крокодил началась!\n\n"
        f"@{update.effective_user.username or update.effective_user.first_name} - ты ведущий!\n\n"
        f"📝 Твое слово: <b>{word}</b>\n\n"
        f"Объясни это слово, не называя его! Остальные должны отгадать.",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    
    # Отправляем слово в личку ведущему, если это возможно
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"🐊 Твое слово для объяснения: <b>{word}</b>",
            parse_mode='HTML'
        )
    except Exception as e:
        logger.warning(f"Не удалось отправить слово в личку: {e}")


async def become_host(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Делает пользователя ведущим"""
    query = update.callback_query
    await query.answer()
    
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if not crocodile_game.is_game_active(chat_id):
        await query.edit_message_text(
            "❌ Игра не активна. Начни новую игру!"
        )
        return
    
    # Даем новое слово новому ведущему
    word = crocodile_game.set_host(chat_id, user_id)
    
    keyboard = [
        [InlineKeyboardButton("🐊 Стать ведущим", callback_data='become_host')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"🐊 @{update.effective_user.username or update.effective_user.first_name} стал ведущим!\n\n"
        f"📝 Твое слово: <b>{word}</b>\n\n"
        f"Объясни это слово, не называя его! Остальные должны отгадать.",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    
    # Отправляем слово в личку ведущему
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"🐊 Твое слово для объяснения: <b>{word}</b>",
            parse_mode='HTML'
        )
    except Exception as e:
        logger.warning(f"Не удалось отправить слово в личку: {e}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает текстовые сообщения для проверки отгадок"""
    if update.effective_chat.type not in ['group', 'supergroup']:
        return
    
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    text = update.message.text
    
    if not text:
        return
    
    # Проверяем отгадку
    is_correct, is_host = crocodile_game.check_guess(chat_id, user_id, text)
    
    if is_correct:
        # Слово отгадано!
        guesser_name = update.effective_user.username or update.effective_user.first_name
        
        keyboard = [
            [InlineKeyboardButton("🐊 Стать ведущим", callback_data='become_host')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"🎉 Ты отгадал, @{guesser_name}!",
            reply_markup=reply_markup
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
    
    # Создаем приложение
    application = Application.builder().token(token).build()
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop_game))
    application.add_handler(CallbackQueryHandler(choose_game, pattern='^choose_game$'))
    application.add_handler(CallbackQueryHandler(start_crocodile, pattern='^game_crocodile$'))
    application.add_handler(CallbackQueryHandler(become_host, pattern='^become_host$'))
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
        # Инициализируем и запускаем приложение
        async def post_init(app: Application) -> None:
            """Инициализация после запуска приложения"""
            # Запускаем проверку таймеров как периодическую задачу
            app.job_queue.run_repeating(
                check_game_timeouts,
                interval=30,  # Проверяем каждые 30 секунд
                first=10  # Первая проверка через 10 секунд после запуска
            )
            logger.info("Периодические задачи запущены")
        
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,  # Удаляем ожидающие обновления при запуске
            post_init=post_init
        )
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=e)


if __name__ == '__main__':
    main()

