import asyncio

from twsaucenao.config import config
from twsaucenao.server import TwitterSauce
from twsaucenao.log import log


async def main():
    twitter = TwitterSauce()

    # Get our polling intervals
    mentioned_interval  = float(config.get('Twitter', 'mentioned_interval', fallback=15.0))
    monitored_interval  = float(config.get('Twitter', 'monitored_interval', fallback=60.0))
    search_interval     = float(config.get('Twitter', 'search_interval', fallback=60.0))

    while True:
        try:
            # Mentions
            await asyncio.sleep(mentioned_interval)
            await twitter.check_mentions()

            # Monitored accounts
            await asyncio.sleep(monitored_interval)
            await twitter.check_monitored()

            # Search query
            await asyncio.sleep(search_interval)
            await twitter.check_query()
        except:
            log.exception("An unknown error occurred while checking mentions")
            await asyncio.sleep(45.0)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
