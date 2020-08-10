import time
import typing

import pysaucenao
import tweepy
from pony.orm import commit, count, Database, delete, Json, Optional, PrimaryKey, Required, db_session
from pysaucenao import GenericSource
from pysaucenao.containers import SauceNaoResults

from twsaucenao.api import api
from twsaucenao.config import config
from twsaucenao.log import log

db = Database()

if config.has_section('MySQL'):
    db.bind(provider='mysql', host=config.get('MySQL', 'hostname'), user=config.get('MySQL', 'username'),
            passwd=config.get('MySQL', 'password'), db=config.get('MySQL', 'database'), charset='utf8mb4')
else:
    db.bind(provider='sqlite', filename='database.sqlite', create_db=True)


TRIGGER_MENTION = 'mentioned'
TRIGGER_MONITORED = 'monitored'
TRIGGER_SELF = 'self'


# noinspection PyMethodParameters
class TweetCache(db.Entity):
    tweet_id        = PrimaryKey(int, size=64)
    data            = Required(Json)
    blocked         = Optional(bool, sql_default=False)
    has_media       = Optional(bool, sql_default=False)
    created_at      = Required(int, size=64, index=True)

    @staticmethod
    @db_session
    def fetch(tweet_id: int) -> typing.Optional['TweetCache']:
        """
        Attempt to retrieve a tweet from our local cache
        Args:
            tweet_id(int): Tweet ID to look up

        Returns:
            typing.Optional[TweetCache]
        """
        tweet = TweetCache.get(tweet_id=tweet_id)
        if tweet:
            log.debug(f'[SYSTEM] Tweet {tweet_id} cache hit')
        return tweet

    # noinspection PyUnresolvedReferences
    @staticmethod
    @db_session
    def set(tweet: tweepy.models.Status, has_media: bool = False, blocked: bool = False) -> 'TweetCache':
        # Delete any existing entry for this server
        cache = TweetCache.get(tweet_id=tweet.id)
        if cache:
            log.warning(f'[SYSTEM] Overwriting cache entry for tweet {tweet.id} early')
            cache.delete()
            commit()

        # noinspection PyProtectedMember
        cache = TweetCache(
                tweet_id=tweet.id,
                data=tweet._json,
                blocked=blocked,
                has_media=has_media,
                created_at=int(time.time())
        )
        return cache

    # noinspection PyTypeChecker
    @staticmethod
    @db_session
    def purge(cutoff=86400):
        """
        Purge old entries from the tweet cache
        Args:
            cutoff (int): Purge cache entries older than `cutoff` seconds. (Default is 1-day)

        Returns:
            int: The number of cache entries that have been purged (for logging)
        """
        cutoff_ts = int(time.time()) - cutoff
        stale_count = count(c for c in TweetCache if c.created_at <= cutoff_ts)

        # No need to perform a delete query if there's nothing to delete
        if stale_count:
            delete(c for c in TweetCache if c.created_at <= cutoff_ts)

        return stale_count

    @property
    def tweet(self):
        """
        Loads a cached tweet back into a stateful object
        Returns:
            tweepy.models.Status
        """
        return tweepy.models.Status.parse(api, self.data)


class TweetSauceCache(db.Entity):
    tweet_id        = Required(int, size=64)
    index_no        = Required(int, size=8, index=True)
    sauce_header    = Optional(Json)
    sauce_data      = Optional(Json)
    sauce_class     = Optional(str, 255)
    sauce_index     = Optional(str, 255)
    media_id        = Optional(int, size=64)
    trigger         = Optional(str, 50)
    created_at      = Required(int, size=64, index=True)

    @staticmethod
    @db_session
    def fetch(tweet_id: int, index_no: int = 0, cutoff: int = 86400) -> typing.Optional['TweetSauceCache']:
        """
        Attempt to load a cached saucenao lookup
        Args:
            tweet_id(int): Tweet ID to look up
            index_no (int): The media indice for tweets with multiple media uploads
            cutoff (int): Only retrieve cache entries up to `cutoff` seconds old. (Default is 1-day)

        Returns:
            typing.Optional[TweetSauceCache]
        """
        now = int(time.time())
        cutoff_ts = 0 if not cutoff else (now - cutoff)

        sauce = TweetSauceCache.get(tweet_id=tweet_id, index_no=index_no)
        if sauce:
            log.debug(f'[SYSTEM] Sauce cache hit on index {index_no} for tweet {tweet_id}')

            if sauce.created_at < cutoff_ts:
                log.info(f'[SYSTEM] Sauce cache query on index {index_no} for tweet {tweet_id} has expired')
                return None

        return sauce

    @staticmethod
    @db_session
    def set(tweet: TweetCache, sauce_results: typing.Optional[SauceNaoResults] = None, index_no: int = 0,
            trigger: str = TRIGGER_MENTION, media_id: typing.Optional[int] = None) -> 'TweetSauceCache':
        """
        Cache a SauceNao query
        Args:
            tweet (TweetCache): Cached Tweet entry
            sauce_results (Optional[SauceNaoResults]): Results to filter and process
            index_no (int): The media indice for tweets with multiple media uploads
            trigger (str): The event that triggered the sauce lookup (purely for analytics)
            media_id (Optional[int]): Media ID if a video preview was uploaded with this tweet

        Returns:
            TweetSauceCache
        """
        # Delete any existing cache entry. This is just for safety; it shouldn't actually be triggered.
        cache = TweetSauceCache.get(tweet_id=tweet.tweet_id, index_no=index_no)
        if cache:
            log.info(f'[SYSTEM] Overwriting sauce cache entry for tweet {tweet.tweet_id}')
            cache.delete()
            commit()

        # If there are no results, we log a cache entry anyways to prevent making additional queries
        def no_results():
            log.info(f'[SYSTEM] Logging a failed Sauce lookup for tweet {tweet.tweet_id} on indice {index_no}')
            _cache = TweetSauceCache(
                    tweet_id=tweet.tweet_id,
                    index_no=index_no,
                    trigger=trigger,
                    media_id=media_id or 0,
                    created_at=int(time.time())
            )
            return _cache

        if not sauce_results:
            return no_results()

        # Get the first result and make sure it meets our minimum similarity requirement
        similarity_cutoff = int(config.getfloat('Twitter', f"min_similarity_{trigger}", fallback=50.0))
        sauce = sauce_results.results[0]

        # Finally, make sure the sauce result actually meets our minimum similarity requirements
        if (sauce.similarity < similarity_cutoff):
            log.debug(f"[SYSTEM] Sauce potentially found for tweet {tweet.tweet_id}, but it didn't meet the minimum {trigger} similarity requirements")
            return no_results()

        log.info(f'[SYSTEM] Caching a successful sauce lookup query for tweet {tweet.tweet_id} on indice {index_no}')
        cache = TweetSauceCache(
                tweet_id=tweet.tweet_id,
                index_no=index_no,
                sauce_header=sauce.header,
                sauce_data=sauce.data,
                sauce_class=type(sauce).__name__,
                sauce_index=sauce.index,
                trigger=trigger,
                media_id=media_id or 0,
                created_at=int(time.time())
        )
        return cache

    # noinspection PyTypeChecker
    @staticmethod
    @db_session
    def sauce_count(cutoff: typing.Optional[int] = None, found_only: bool = True) -> int:
        """
        Return a count of how many sauce lookups we've performed
        Args:
            cutoff (typing.Optional[int]): An optional cutoff. When defined, only count results logged in the last
                `cutoff` seconds.
            found_only (bool): Only count sauce queries that actually returned results.

        Returns:
            int
        """
        now = int(time.time())
        cutoff_ts = 0 if not cutoff else (now - cutoff)

        if found_only:
            sauce_count = count(s for s in TweetSauceCache if s.sauce_class and s.created_at >= cutoff_ts)
        else:
            sauce_count = count(s for s in TweetSauceCache if s.created_at >= cutoff_ts)

        return sauce_count

    @property
    def sauce(self) -> typing.Optional[GenericSource]:
        """
        Loads a cached SauceNao result
        Returns:
            GenericSource
        """
        if not all([self.sauce_class, self.sauce_header, self.sauce_data]):
            return None

        container = getattr(pysaucenao.containers, self.sauce_class)
        sauce = container(self.sauce_header, self.sauce_data)
        return sauce


class TwitterBlocklist(db.Entity):
    account_id      = PrimaryKey(int, size=64)
    username        = Required(str, 255)
    display_name    = Required(str, 255)
    user_data       = Required(Json)
    blocked_on      = Required(int, size=64)

    @staticmethod
    @db_session
    def add(user) -> 'TwitterBlocklist':
        """
        Log accounts that have blocked the sauce bot
        Args:
            user: tweepy.models.User

        Returns:
            TwitterBlocklist
        """
        # Make sure an entry for this user doesn't already exist
        already_logged = TwitterBlocklist.get(account_id=user.id)
        if already_logged:
            return already_logged

        # noinspection PyProtectedMember
        return TwitterBlocklist(
                account_id=user.id,
                username=user.screen_name,
                display_name=user.name,
                user_data=user._json,
                blocked_on=int(time.time())
        )


db.generate_mapping(create_tables=True)
