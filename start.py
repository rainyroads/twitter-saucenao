import asyncio

from twsaucenao.config import config
from twsaucenao.log import log
from twsaucenao.models.database import TweetCache, TweetSauceCache
from twsaucenao.server import TwitterSauce

# Get our polling intervals
mentioned_interval = float(config.get('Twitter', 'mentioned_interval', fallback=15.0))
monitored_interval = float(config.get('Twitter', 'monitored_interval', fallback=60.0))
search_interval = float(config.get('Twitter', 'search_interval', fallback=60.0))

twitter = TwitterSauce()


# noinspection PyBroadException
async def self() -> None:
    """
    Respond to any mentions requesting sauce lookups
    Returns:
        None
    """
    while True:
        try:
            # Mentions
            await twitter.check_self()
            await asyncio.sleep(monitored_interval)
        except Exception:
            log.exception("An unknown error occurred while checking mentions")
            await asyncio.sleep(60.0)


# noinspection PyBroadException
async def mentions() -> None:
    """
    Respond to any mentions requesting sauce lookups
    Returns:
        None
    """
    while True:
        try:
            # Mentions
            await twitter.check_mentions()
            await asyncio.sleep(mentioned_interval)
        except Exception:
            log.exception("An unknown error occurred while checking mentions")
            await asyncio.sleep(60.0)


# noinspection PyBroadException
async def monitored() -> None:
    """
    Query monitored accounts for sauce lookups
    Returns:
        None
    """
    while True:
        try:
            # Monitored accounts
            await twitter.check_monitored()
            await asyncio.sleep(monitored_interval)
        except Exception:
            log.exception("An unknown error occurred while checking monitored accounts")
            await asyncio.sleep(60.0)


# noinspection PyBroadException
async def cleanup() -> None:
    """
    Purge stale cache entries from the database and display some general analytics
    Returns:
        None
    """
    while True:
        try:
            # Cache purging
            stale_count = TweetCache.purge()
            print(f"\nPurging {stale_count:,} stale cache entries from the database")

            # Sauce analytics
            sauce_count = TweetSauceCache.sauce_count(900)
            print(f"We've processed {sauce_count:,} new sauce queries!")

            await asyncio.sleep(900.0)
        except Exception:
            log.exception("An unknown error occurred while performing cleanup tasks")
            await asyncio.sleep(300.0)


async def main() -> None:
    """
    Initialize / gather the methods to run in concurrent loops
    Returns:
        None
    """
    tasks = []
    if config.getboolean('Twitter', 'monitor_self', fallback=False):
        tasks.append(self())

    if not config.getboolean('Twitter', 'disable_mentions', fallback=False):
        tasks.append(mentions())

    tasks.append(monitored())
    tasks.append(cleanup())

    await asyncio.gather(*tasks)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
