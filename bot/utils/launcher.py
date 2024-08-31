import asyncio
import argparse
from random import randint
from typing import Any
from better_proxy import Proxy

from bot.config import settings
from bot.utils import logger
from bot.core.tapper import run_tapper
from bot.core.registrator import register_sessions, get_tg_client
from bot.utils.accounts import Accounts

start_text = """

██╗░░██╗██╗░░██╗██╗░░░██╗░█████╗░░█████╗░██╗███╗░░██╗██████╗░░█████╗░████████╗
╚██╗██╔╝██║░██╔╝██║░░░██║██╔══██╗██╔══██╗██║████╗░██║██╔══██╗██╔══██╗╚══██╔══╝
░╚███╔╝░█████═╝░██║░░░██║██║░░╚═╝██║░░██║██║██╔██╗██║██████╦╝██║░░██║░░░██║░░░
░██╔██╗░██╔═██╗░██║░░░██║██║░░██╗██║░░██║██║██║╚████║██╔══██╗██║░░██║░░░██║░░░
██╔╝╚██╗██║░╚██╗╚██████╔╝╚█████╔╝╚█████╔╝██║██║░╚███║██████╦╝╚█████╔╝░░░██║░░░
╚═╝░░╚═╝╚═╝░░╚═╝░╚═════╝░░╚════╝░░╚════╝░╚═╝╚═╝░░╚══╝╚═════╝░░╚════╝░░░░╚═╝░░░
                                                                    by Desamod                                                                                                                    
Select an action:

    1. Run bot
    2. Create session
"""


def get_proxy(raw_proxy: str) -> Proxy:
    return Proxy.from_str(proxy=raw_proxy).as_url if raw_proxy else None


async def process() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-a", "--action", type=int, help="Action to perform")
    action = parser.parse_args().action

    if not action:
        print(start_text)

        while True:
            action = input("> ")

            if not action.isdigit():
                logger.warning("Action must be number")
            elif action not in ["1", "2"]:
                logger.warning("Action must be 1 or 2")
            else:
                action = int(action)
                break

    if action == 2:
        await register_sessions()
    elif action == 1:
        accounts = await Accounts().get_accounts()
        await run_tasks(accounts=accounts)


async def run_tasks(accounts: [Any, Any, list]):
    tasks = []
    for account in accounts:
        session_name, user_agent, raw_proxy = account.values()
        tg_client = await get_tg_client(session_name=session_name, proxy=raw_proxy)
        proxy = get_proxy(raw_proxy=raw_proxy)
        tasks.append(asyncio.create_task(run_tapper(tg_client=tg_client, user_agent=user_agent, proxy=proxy)))
        await asyncio.sleep(delay=randint(settings.START_DELAY[0], settings.START_DELAY[1]))

    await asyncio.gather(*tasks)
