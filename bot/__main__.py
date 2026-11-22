"""AIcontent боты — кіру нүктесі. Іске қосу: python -m bot"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand
from dotenv import load_dotenv

from bot import admin, billing, catalog, config, handlers, store


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )

    load_dotenv()
    store.init_db(config.db_path())

    bot = Bot(config.bot_token(),
              default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await bot.set_my_commands([
        BotCommand(command="start", description="Басты мәзір"),
    ])

    dp = Dispatcher()
    dp.include_router(admin.router)
    dp.include_router(handlers.router)
    dp.include_router(catalog.router)

    # Бот өшіп тұрғанда өткен төлемдерді қуып жетеміз.
    recovered = await billing.recover_pending(bot)
    if recovered:
        logging.info("Қайта қосылғаннан кейін %s төлем өңделді", recovered)

    # drop_pending_updates=False: бот өшіп тұрғанда жіберілген /start жоғалмайды
    await bot.delete_webhook(drop_pending_updates=False)
    try:
        await dp.start_polling(bot)
    finally:
        await billing.shutdown()
        store.close()


if __name__ == "__main__":
    asyncio.run(main())
