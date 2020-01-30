import asyncio

from twsaucenao.server import TwitterSauce
from twsaucenao.log import log


async def main():
    twitter = TwitterSauce()
    while True:
        try:
            await twitter.check_mentions()
            twitter.log.info("Waiting...")
            await asyncio.sleep(15.0)
        except:
            log.exception("An unknown error occurred while checking mentions")
            await asyncio.sleep(45.0)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
