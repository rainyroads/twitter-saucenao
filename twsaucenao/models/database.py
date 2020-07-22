import time
import typing

import pysaucenao
import tweepy
from pony.orm import *
from pysaucenao import GenericSource
from pysaucenao.containers import PixivSource, SauceNaoResults, VideoSource

from twsaucenao.api import api
from twsaucenao.config import config
from twsaucenao.log import log

db = Database()

if config.has_section('MySQL'):
    db.bind(provider='mysql', host=config.get('MySQL', 'hostname'), user=config.get('MySQL', 'username'),
            passwd=config.get('MySQL', 'password'), db=config.get('MySQL', 'database'))
else:
    db.bind(provider='sqlite', filename='database.sqlite', create_db=True)


TRIGGER_MENTION = 'mentioned'
TRIGGER_MONITORED = 'monitored'
TRIGGER_SEARCH = 'searching'


# noinspection PyMethodParameters
class TweetCache(db.Entity):
    tweet_id        = PrimaryKey(int, size=64)
    data            = Required(Json)
    blocked         = Optional(bool, sql_default=False)
    has_media       = Optional(bool, sql_default=False)
    created_at      = Required(int, size=64, index=True)

    @staticmethod
    @db_session
    def fetch(tweet_id: int) -> 'TweetCache':
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
    trigger         = Optional(str, 50)
    created_at      = Required(int, size=64, index=True)

    @staticmethod
    @db_session
    def fetch(tweet_id: int, index_no: int = 0) -> 'TweetSauceCache':
        """
        Attempt to load a cached saucenao lookup
        Args:
            tweet_id(int): Tweet ID to look up
            index_no (int): The media indice for tweets with multiple media uploads
        Returns:
            typing.Optional[TweetSauceCache]
        """
        sauce = TweetSauceCache.get(tweet_id=tweet_id, index_no=index_no)
        if sauce:
            log.debug(f'[SYSTEM] Sauce cache hit on index {index_no} for tweet {tweet_id}')
        return sauce

    @staticmethod
    @db_session
    def filter_and_set(tweet: TweetCache, sauce_results: typing.Optional[SauceNaoResults], index_no: int = 0,
                       trigger: str = TRIGGER_MENTION) -> 'TweetSauceCache':
        """
        Cache a SauceNao query
        Args:
            tweet (TweetCache): Cached Tweet entry
            sauce_results (Optional[SauceNaoResults]): Results to filter and process
            index_no (int): The media indice for tweets with multiple media uploads
            trigger (str): The event that triggered the sauce lookup (purely for analytics)
        Returns:
            TweetSauceCache
        """
        # Delete any existing cache entry. This is just for safety; it shouldn't actually be triggered.
        cache = TweetSauceCache.get(tweet_id=tweet.tweet_id, index_no=index_no)
        if cache:
            log.warning(f'[SYSTEM] Overwriting sauce cache entry for tweet {tweet.tweet_id} early')
            cache.delete()
            commit()

        # If there are no results, we log a cache entry anyways to prevent making additional queries
        def no_results():
            log.info(f'[SYSTEM] Logging a failed Sauce lookup for tweet {tweet.tweet_id} on indice {index_no}')
            _cache = TweetSauceCache(
                    tweet_id=tweet.tweet_id,
                    index_no=index_no,
                    trigger=trigger,
                    created_at=int(time.time())
            )
            return _cache

        if not sauce_results or not sauce_results.results:
            return no_results()

        # Filter the results, prioritizing anime first, then Pixiv, then anything else
        sauce = None

        # Do we have an anime?
        similarity_cutoff = int(config.getfloat('Twitter', f"min_similarity_{trigger}", fallback=50.0))
        for result in sauce_results.results:
            if (result.similarity >= max(similarity_cutoff, 75)) and isinstance(result, VideoSource):
                sauce = result
                break

        # No? Any relevant Pixiv entries?
        if not sauce:
            for result in sauce_results.results:
                if (result.similarity >= max(similarity_cutoff, 75)) and isinstance(result, PixivSource):
                    sauce = result
                    break

        # Still nothing? Just pick the best match then
        if not sauce:
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
                created_at=int(time.time())
        )
        return cache

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


db.generate_mapping(create_tables=True)