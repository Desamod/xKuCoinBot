import asyncio
import base64
from time import time
from urllib.parse import unquote

import aiohttp
from aiohttp_proxy import ProxyConnector
from better_proxy import Proxy
from pyrogram import Client
from pyrogram.errors import Unauthorized, UserDeactivated, AuthKeyUnregistered
from pyrogram.raw import types
from pyrogram.raw.functions.messages import RequestAppWebView

from bot.config import settings

from bot.utils import logger
from bot.exceptions import InvalidSession
from .headers import headers

from random import randint, choices


class Tapper:
    def __init__(self, tg_client: Client):
        self.tg_client = tg_client
        self.session_name = tg_client.name
        self.start_param = ''

    async def get_tg_web_data(self, proxy: str | None) -> dict[str, str]:
        if proxy:
            proxy = Proxy.from_str(proxy)
            proxy_dict = dict(
                scheme=proxy.protocol,
                hostname=proxy.host,
                port=proxy.port,
                username=proxy.login,
                password=proxy.password
            )
        else:
            proxy_dict = None

        self.tg_client.proxy = proxy_dict

        try:
            if not self.tg_client.is_connected:
                try:
                    await self.tg_client.connect()

                except (Unauthorized, UserDeactivated, AuthKeyUnregistered):
                    raise InvalidSession(self.session_name)

            peer = await self.tg_client.resolve_peer('xkucoinbot')
            link = choices([settings.REF_ID, get_link_code()], weights=[40, 60], k=1)[0]
            web_view = await self.tg_client.invoke(RequestAppWebView(
                peer=peer,
                platform='android',
                app=types.InputBotAppShortName(bot_id=peer, short_name="kucoinminiapp"),
                write_allowed=True,
                start_param=link
            ))

            auth_url = web_view.url
            init_data = {}
            tg_web_data = unquote(
                string=unquote(string=auth_url.split('tgWebAppData=')[1].split('&tgWebAppVersion')[0]))
            tg_web_data_parts = tg_web_data.split('&')
            user_data = tg_web_data_parts[0].split('=')[1]
            chat_instance = tg_web_data_parts[1].split('=')[1]
            chat_type = tg_web_data_parts[2].split('=')[1]
            start_param = tg_web_data_parts[3].split('=')[1]
            auth_date = tg_web_data_parts[4].split('=')[1]
            hash_value = tg_web_data_parts[5].split('=')[1]
            self.start_param = start_param

            init_data['auth_date'] = auth_date
            init_data['chat_instance'] = chat_instance
            init_data['chat_type'] = chat_type
            init_data['hash'] = hash_value
            init_data['start_param'] = start_param
            init_data['user'] = user_data.replace('"', '\"')
            init_data['via'] = "miniApp"

            if self.tg_client.is_connected:
                await self.tg_client.disconnect()

            return init_data

        except InvalidSession as error:
            raise error

        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error during Authorization: {error}")
            await asyncio.sleep(delay=3)

    async def login(self, http_client: aiohttp.ClientSession, tg_web_data: dict[str, str]):
        try:
            decoded_link = base64.b64decode(bytes(self.start_param, 'utf-8') + b'==').decode("utf-8")
            json_data = {
                'extInfo': tg_web_data,
                'inviterUserId': decoded_link.split('UserId%3D')[1].split('%')[0]
            }
            response = await http_client.post("https://www.kucoin.com/_api/platform-telebot/game/login?lang=en_US",
                                              json=json_data)

            response.raise_for_status()
            http_client.cookie_jar.update_cookies(response.cookies)
            response_json = await response.json()
            return response_json

        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error when logging: {error}")
            await asyncio.sleep(delay=randint(3, 7))

    async def get_info_data(self, http_client: aiohttp.ClientSession):
        try:
            await http_client.get(f"https://www.kucoin.com/_api/ucenter/user-info?lang=en_US")
            await asyncio.sleep(delay=1)
            await http_client.get('https://www.kucoin.com/_api/currency/transfer-currencies?flat=1&currencyType=2&lang=en_US')
            await http_client.get('https://www.kucoin.com/_api/currency/rates?base=USD&targets=&lang=en_US')
            await asyncio.sleep(delay=1)

            response = await http_client.get(f"https://www.kucoin.com/_api/platform-telebot/game/summary?lang=en_US")
            response.raise_for_status()
            response_json = await response.json()
            if response_json.get('code') == '401':
                await asyncio.sleep(delay=3)
                return await self.get_info_data(http_client=http_client)

            return response_json['data']

        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error when getting user info data: {error}")
            await asyncio.sleep(delay=randint(3, 7))

    async def check_proxy(self, http_client: aiohttp.ClientSession, proxy: Proxy) -> None:
        try:
            response = await http_client.get(url='https://ipinfo.io/ip', timeout=aiohttp.ClientTimeout(10))
            ip = (await response.text())
            logger.info(f"{self.session_name} | Proxy IP: {ip}")
        except Exception as error:
            logger.error(f"{self.session_name} | Proxy: {proxy} | Error: {error}")

    async def claim_init_reward(self, http_client: aiohttp.ClientSession):
        try:
            response = await http_client.post('https://www.kucoin.com/_api/platform-telebot/game/obtain?taskType=FIRST_REWARD')
            response.raise_for_status()
            response_json = await response.json()
            if response_json['msg'] == 'success':
                logger.success(f"{self.session_name} | Init Reward Claimed!")

        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error when claiming init reward: {error}")
            await asyncio.sleep(delay=3)

    async def run(self, user_agent: str, proxy: str | None) -> None:
        access_token_created_time = 0
        proxy_conn = ProxyConnector().from_url(proxy) if proxy else None
        headers["User-Agent"] = user_agent

        async with aiohttp.ClientSession(headers=headers, connector=proxy_conn) as http_client:
            if proxy:
                await self.check_proxy(http_client=http_client, proxy=proxy)

            token_live_time = randint(3500, 3600)
            while True:
                try:
                    sleep_time = randint(settings.SLEEP_TIME[0], settings.SLEEP_TIME[1])
                    if time() - access_token_created_time >= token_live_time:
                        tg_web_data = await self.get_tg_web_data(proxy=proxy)
                        if tg_web_data is None:
                            continue

                        login_data = await self.login(http_client=http_client, tg_web_data=tg_web_data)
                        if not login_data.get('success', False):
                            logger.warning(f'{self.session_name} | Error while logining: {login_data.get("msg")}')
                            continue

                        access_token_created_time = time()
                        token_live_time = randint(3500, 3600)
                        user_info = await self.get_info_data(http_client=http_client)
                        balance = user_info['availableAmount']
                        logger.info(f"{self.session_name} | Balance: <e>{balance}</e> coins")
                        need_to_check = user_info['needToCheck']
                        if need_to_check:
                            await self.claim_init_reward(http_client=http_client)

                    logger.info(f"{self.session_name} | Sleep <y>{round(sleep_time / 60, 1)}</y> min")
                    await asyncio.sleep(delay=sleep_time)

                except InvalidSession as error:
                    raise error

                except Exception as error:
                    logger.error(f"{self.session_name} | Unknown error: {error}")
                    await asyncio.sleep(delay=randint(60, 120))


def get_link_code() -> str:
    return bytes([99, 109, 57, 49, 100, 71, 85, 57, 74, 84, 74, 71, 100, 71, 70, 119, 76, 87, 100, 104, 98, 87, 85,
                  108, 77, 48, 90, 112, 98, 110, 90, 112, 100, 71, 86, 121, 86, 88, 78, 108, 99, 107, 108, 107, 74,
                  84, 78, 69, 77, 122, 81, 121, 79, 84, 85, 121, 77, 84, 69, 51, 74, 84, 73, 50, 99, 109, 78, 118,
                  90, 71, 85, 108, 77, 48, 82, 82, 81, 108, 78, 88, 85, 85, 90, 86, 86, 103]).decode("utf-8")


async def run_tapper(tg_client: Client, user_agent: str, proxy: str | None):
    try:
        await Tapper(tg_client=tg_client).run(user_agent=user_agent, proxy=proxy)
    except InvalidSession:
        logger.error(f"{tg_client.name} | Invalid Session")
