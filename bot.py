import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from personalities import personalities
from gpt import ChatGptService
from util import (
    load_message,
    load_prompt,
    send_text_buttons,
    send_text,
    send_image,
    show_main_menu,
    Dialog,
    default_callback_handler,
)

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHATGPT_TOKEN = os.getenv("CHATGPT_TOKEN")

chat_gpt = ChatGptService(CHATGPT_TOKEN)
app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команду /start и отображает главное меню бота."""
    dialog.mode = 'main'
    dialog.correct_answers = 0
    text = load_message('main')
    await send_image(update, context, 'main')
    await send_text(update, context, text)
    await show_main_menu(update, context, {
        'start': 'Главное меню',
        'random': 'Узнать случайный интересный факт 🧠',
        'gpt': 'Задать вопрос чату GPT 🤖',
        'talk': 'Поговорить с известной личностью 👤',
        'quiz': 'Поучаствовать в квизе ❓',
        'truefalse': 'Игра "Правда или ложь" 🎲'
    })


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает входящие текстовые сообщения в зависимости от текущего режима."""
    if dialog.mode == "gpt" or dialog.mode == "talk":
        await gpt_dialog(update, context)
    elif dialog.mode == 'quiz':
        await quiz_answer(update, context)
    else:
        await start(update, context)


async def random_fact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет пользователю случайный интересный факт."""
    prompt = load_prompt("random")
    await send_image(update, context, "random")
    answer = await chat_gpt.send_question(prompt, "")
    await send_text_buttons(
        update, context, answer, {"random": "Узнать другой случайный факт 🧠"}
    )


async def gpt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Инициирует диалог с ChatGPT."""
    dialog.mode = "gpt"
    prompt = load_prompt("gpt")
    message = load_message("gpt")
    chat_gpt.set_prompt(prompt)
    await send_image(update, context, "gpt")
    await send_text(update, context, message)


async def talk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс выбора известной личности для беседы."""
    dialog.mode = "choose_personality"
    message = load_message("talk")
    await send_image(update, context, "talk")
    buttons = {}
    for key, value in personalities.items():
        buttons[key] = value["name"]
    await send_text_buttons(update, context, message, buttons)


async def talk_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор пользователя и устанавливает выбранную личность для разговора."""
    query = update.callback_query
    await query.answer()
    choice = query.data
    if choice in personalities:
        prompt_file = personalities[choice]['prompt_file']
        prompt = load_prompt(prompt_file)
        chat_gpt.set_prompt(prompt)
        dialog.mode = 'talk'
        dialog.person_name = personalities[choice]['name'].split(' - ')[0]
        await send_image(update, context, choice)
        await send_text(update, context, f"Вы выбрали: {personalities[choice]['name']}\nТеперь вы можете начать диалог.")
    else:
        await send_text(update, context, "Выбранная личность не найдена.")


async def gpt_dialog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает диалог с ChatGPT или выбранной известной личностью."""
    text = update.message.text
    if dialog.mode == 'talk' and dialog.person_name:
        thinking_message = f"{dialog.person_name} думает..."
    else:
        thinking_message = "Думаю над ответом..."
    message = await send_text(update, context, thinking_message)
    answer = await chat_gpt.add_message(text)
    await message.edit_text(answer)


async def random_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает нажатие кнопки для получения нового случайного факта."""
    await update.callback_query.answer()
    await random_fact(update, context)


async def quiz_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запускает викторину и предлагает пользователю выбрать тему."""
    dialog.mode = "choose_quiz_topic"
    dialog.correct_answers = 0
    message = load_message('quiz')
    await send_image(update, context, 'quiz')
    buttons = {
        'quiz_prog': 'Программирование на Python 🐍',
        'quiz_math': 'Математические теории 📐',
        'quiz_biology': 'Биология 🧬'
    }
    await send_text_buttons(update, context, message, buttons)


async def quiz_topic_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор темы викторины и начинает задавать вопросы."""
    query = update.callback_query
    await query.answer()
    choice = query.data
    if choice in ['quiz_prog', 'quiz_math', 'quiz_biology']:
        dialog.mode = 'quiz'
        dialog.quiz_topic = choice
        prompt = load_prompt('quiz')
        chat_gpt.set_prompt(prompt)
        question = await chat_gpt.add_message(choice)
        await send_text(update, context, question)
    else:
        await send_text(update, context, "Нет такой темы.")


async def quiz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ответ пользователя на вопрос викторины."""
    user_answer = update.message.text
    result = await chat_gpt.add_message(user_answer)
    if "Правильно!" in result:
        dialog.correct_answers += 1
    await send_text_buttons(update, context, f"{result}\n\nПравильных ответов: {dialog.correct_answers}", {
        'quiz_more': 'Следующий вопрос 🔄',
        'quiz_exit': 'Завершить викторину 🏁'
    })


async def quiz_next_or_exit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор пользователя продолжить викторину или завершить её."""
    query = update.callback_query
    await query.answer()
    choice = query.data
    if choice == 'quiz_more':
        question = await chat_gpt.add_message('quiz_more')
        await send_text(update, context, question)
    elif choice == 'quiz_exit':
        await send_text(update, context, f"Викторина завершена! Вы набрали {dialog.correct_answers} правильных ответов.")
        dialog.mode = None
        await start(update, context)
    else:
        await send_text(update, context, "Неверный выбор.")


async def truefalse_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запускает игру "Правда или ложь"."""
    dialog.mode = 'truefalse'
    dialog.truefalse_score = 0
    prompt = load_prompt('truefalse')
    message = load_message('truefalse')
    chat_gpt.reset_messages()
    chat_gpt.set_prompt(prompt)
    await send_image(update, context, 'truefalse')
    await send_text(update, context, message)
    await truefalse_next_statement(update, context)


async def truefalse_next_statement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает следующее утверждение для игры и отправляет его пользователю."""
    statement = await chat_gpt.add_message('next')
    dialog.truefalse_current_statement = statement
    await send_text_buttons(update, context, statement, {
        'truefalse_true': 'Правда ✅',
        'truefalse_false': 'Ложь ❌'
    })


async def truefalse_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ответ пользователя в игре "Правда или ложь"."""
    query = update.callback_query
    await query.answer()
    choice = query.data
    if choice == 'truefalse_true':
        user_answer = 'Правда'
    elif choice == 'truefalse_false':
        user_answer = 'Ложь'
    else:
        await send_text(update, context, "Неверный выбор.")
        return
    result = await chat_gpt.add_message(user_answer)
    if "Верно!" in result:
        dialog.truefalse_score += 1
    await send_text_buttons(update, context, f"{result}\n\nВаш счёт: {dialog.truefalse_score}", {
        'truefalse_next': 'Следующее утверждение ▶️',
        'truefalse_exit': 'Завершить игру 🛑'
    })


async def truefalse_next_or_exit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор пользователя продолжить игру или выйти в главное меню."""
    query = update.callback_query
    await query.answer()
    choice = query.data
    if choice == 'truefalse_next':
        await truefalse_next_statement(update, context)
    elif choice == 'truefalse_exit':
        await send_text(update, context, f"Игра окончена! Ваш итоговый счёт: {dialog.truefalse_score}.")
        dialog.mode = None
        await start(update, context)
    else:
        await send_text(update, context, "Неверный выбор.")


dialog = Dialog()
dialog.mode = None


app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("random", random_fact))
app.add_handler(CommandHandler("gpt", gpt))
app.add_handler(CommandHandler("talk", talk))
app.add_handler(CommandHandler("quiz", quiz_start))
app.add_handler(CommandHandler('truefalse', truefalse_start))


app.add_handler(MessageHandler(filters.TEXT, text_handler))

app.add_handler(CallbackQueryHandler(random_button, pattern="^random$"))
app.add_handler(CallbackQueryHandler(talk_choice, pattern="^talk_.*"))
app.add_handler(CallbackQueryHandler(quiz_topic_choice, pattern='^quiz_(prog|math|biology)$'))
app.add_handler(CallbackQueryHandler(quiz_next_or_exit, pattern='^(quiz_more|quiz_exit)$'))
app.add_handler(CallbackQueryHandler(truefalse_answer, pattern='^truefalse_(true|false)$'))
app.add_handler(CallbackQueryHandler(truefalse_next_or_exit, pattern='^truefalse_(next|exit)$'))
app.add_handler(CallbackQueryHandler(default_callback_handler))

app.run_polling()
