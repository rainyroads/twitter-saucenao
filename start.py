import asyncio

from twsaucenao.config import config
from twsaucenao.server import TwitterSauce
from twsaucenao.log import log

# Get our polling intervals
mentioned_interval = float(config.get('Twitter', 'mentioned_interval', fallback=15.0))
monitored_interval = float(config.get('Twitter', 'monitored_interval', fallback=60.0))
search_interval = float(config.get('Twitter', 'search_interval', fallback=60.0))

twitter = TwitterSauce()


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
        except:
            log.exception("An unknown error occurred while checking mentions")
            await asyncio.sleep(60.0)


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
        except:
            log.exception("An unknown error occurred while checking monitored accounts")
            await asyncio.sleep(60.0)


async def search() -> None:
    """
    Perform a search query for our monitored key-phrase and respond to any applicable posts
    Returns:
        None
    """
    while True:
        try:
            # Search query
            await twitter.check_query()
            await asyncio.sleep(search_interval)
        except:
            log.exception("An unknown error occurred while executing a search query")
            await asyncio.sleep(60.0)


async def main() -> None:
    """
    Initialize / gather the methods to run in concurrent loops
    Returns:
        None
    """
    await asyncio.gather(
            mentions(),
            monitored(),
            search()
    )


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
