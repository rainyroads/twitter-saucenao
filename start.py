import asyncio

from twsaucenao.server import TwitterSauce


async def main():
    twitter = TwitterSauce()
    while True:
        await twitter.check_mentions()
        twitter.log.info("Waiting...")
        await asyncio.sleep(15.0)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
