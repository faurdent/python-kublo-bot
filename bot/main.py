import logging
import asyncio
from aiohttp.web import Application, run_app
from dispatcher import dp, bot, redis, storage
from settings import WEBHOOK_PATH, WEBHOOK_DOMAIN, LOCAL_MODE, ADMIN_ID
from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
import constants as const
from db import save_user, get_user, add_star, minus_star, get_top_users
from aiogram.filters import Command
import random
from random_gif import get_random_gif

from db import init_database, stop_database

logging.basicConfig(level=logging.DEBUG)


@dp.update.outer_middleware()
async def random_message_middleware(handler, event, data):
    counter = int(await redis.get("counter"))
    if counter == 10:
        await event.message.answer(random.choice(const.RANDOM_ANSWERS))
        await redis.set("counter", 0)
        return
    else:
        await redis.set("counter", int(counter) + 1) if counter else await redis.set("counter", 1)
    return await handler(event, data)


@dp.update.outer_middleware()
async def save_user_middleware(handler, event, data):
    user = await save_user(event.message)
    data['user'] = user
    return await handler(event, data)


@dp.update.outer_middleware()
async def only_admin_commands(handler, event, data):
    if int(event.message.from_user.id) != int(
            ADMIN_ID) and event.message.text != "/gif" and event.message.text != "/gif@python_kublo_bot":
        commands = ["/start", "/top", "+", "-", "похвали"]
        if event.message.text in commands:
            await event.message.answer("Ви не адміністратор, пішов нахуй")
        return
    else:
        if event.message.text == "/gif" or event.message.text == "/gif@python_kublo_bot":
            pass
    return await handler(event, data)


@dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    await message.answer(
        const.START_MESSAGE, parse_mode="markdown"
    )
    user = await get_user(message)
    await message.answer(f"Привіт, {user.first_name} {user.last_name}!")


@dp.message(Command("gif"))
async def gif(message: types.Message, state: FSMContext):
    gif_url = await get_random_gif()
    await bot.send_animation(message.chat.id, gif_url)


@dp.message(Command("top"))
async def top(message: types.Message, state: FSMContext):
    top_users = await get_top_users(message)
    top_user_string = ""
    await message.answer("Топ в кублі:")
    for user in top_users:
        top_user_string += f"{user.first_name} {user.last_name} - {user.stars}⭐️\n"
    await message.answer(top_user_string)


@dp.message()
async def star_handler(message: types.Message, state: FSMContext):
    if message.text == "+":
        await add_star(message)
        await message.answer("Зірочка додана, сучка")
    elif message.text == "-":
        await minus_star(message)
        await message.answer("Зірочка віднята, чувак, не плач")
    elif message.text == "похвали":
        await message.answer(random.choice(const.ACCEPTABLE_ANSWERS))


# INITIALIZATION
# Prepare function for starting bot
async def _on_startup(app):
    await bot.set_webhook(WEBHOOK_DOMAIN + WEBHOOK_PATH)


async def _on_shutdown(app):
    await bot.delete_webhook()
    await storage.close()


async def _init(*_):
    print("Init database")
    await init_database()


async def _shutdown(*_):
    print("Shutdown database")
    await stop_database()


async def _start_polling():
    await _init()
    await dp.start_polling(bot, handle_as_tasks=False)
    await _shutdown()


if __name__ == "__main__":
    print("Start bot")
    if LOCAL_MODE:
        print("Start polling")
        asyncio.run(_start_polling())
    else:
        print("Start webhook")
        app = Application()
        setup_application(app, dp)
        app.on_startup.append(_on_startup)
        app.on_startup.append(_init)

        app.on_shutdown.append(_on_shutdown)
        app.on_shutdown.append(_shutdown)

        handler = SimpleRequestHandler(dp, bot)

        app.router.add_route("*", WEBHOOK_PATH, handler)

        run_app(app, port=8000)
