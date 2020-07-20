import typing

import pysaucenao
import tweepy
from pony.orm import *
from pysaucenao import GenericSource

from twsaucenao.api import api
from twsaucenao.config import config
from twsaucenao.log import log

db = Database()

if config.has_section('MySQL'):
    db.bind(provider='mysql', host=config.get('MySQL', 'hostname'), user=config.get('MySQL', 'username'),
            passwd=config.get('MySQL', 'password'), db=config.get('MySQL', 'database'))
else:
    db.bind(provider='sqlite', filename='database.sqlite', create_db=True)


# noinspection PyMethodParameters
class TweetCache(db.Entity):
    tweet_id        = PrimaryKey(int, size=64)
    data            = Required(Json)
    blocked         = Required(bool)
    has_media       = Optional(bool, sql_default=False)

    @staticmethod
    @db_session
    def fetch(tweet_id: int) -> 'TweetCache':
        """
        Gets the SauceNao API key for the specified guild
        Args:
            tweet_id(int): Tweet ID to look up

        Returns:
            typing.Optional[TweetCache]
        """
        tweet = TweetCache.get(tweet_id=tweet_id)
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

        # noinspection PyProtectedMember
        cache = TweetCache(
                tweet_id=tweet.id,
                data=tweet._json,
                blocked=blocked,
                has_media=has_media
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


class TweetSauceCache(TweetCache):
    index_no        = Required(int, size=8, index=True)
    source_header   = Required(Json)
    source_data     = Optional(Json)
    sauce_class     = Optional(str, 255)

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
