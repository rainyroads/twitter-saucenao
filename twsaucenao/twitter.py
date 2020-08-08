import logging
from typing import List, Optional, Tuple

import tweepy

from twsaucenao import SAUCENAOPLS_TWITTER_ID
from twsaucenao.api import api, readonly_api
from twsaucenao.errors import TwSauceNoMediaException
from twsaucenao.models.database import TweetCache, TwitterBlocklist


class TweetManager:
    def __init__(self):
        """
        Handles performing cache and API queries on tweepy objects
        """
        self.log = logging.getLogger(__name__)
        self.my = api.me()

    def get_tweet(self, tweet_id: int) -> TweetCache:
        """
        Performs a lookup on the given tweet ID.
        Attempts to load the tweet from database cache first, and if that fails, executes a Twitter API query.
        Args:
            tweet_id (int): The tweet ID

        Returns:
            TweetCache
        """
        # Attempt to load from cache first
        tweet = TweetCache.fetch(tweet_id)
        if tweet:
            return tweet

        # If it's not cached yet, fetch the tweet from the API
        blocked = False
        try:
            _tweet = api.get_status(tweet_id, tweet_mode='extended')
        except tweepy.TweepError as error:
            # If we're blocked, use readonly parsing if configured, otherwise log an error and re-throw the exception
            if error.api_code == 136:
                blocked = True
                if readonly_api:
                    self.log.warning(f"User has blocked the main account; falling back to read-only API for media parsing on tweet {tweet_id}")
                    _tweet = readonly_api.get_status(tweet_id, tweet_mode='extended')

                    # Add this account to our blocklist
                    TwitterBlocklist.add(_tweet.author)
                else:
                    self.log.warning(f"Skipping tweet {tweet_id} as we have been blocked by the authors account")
                    raise error
            else:
                raise error

        # Cache and return
        return TweetCache.set(_tweet, bool(self.extract_media(_tweet)), blocked=blocked)

    def get_closest_media(self, tweet) -> Tuple[TweetCache, TweetCache, List[str]]:
        """
        Find the closet media post associated with this tweet.
        This could be this tweet itself if someone has mentioned us with an upload.
        This could be a comment where the direct parent is the media we need to look up.
        This could also be a comment further down a chain of comments on a parent post, in which case we will need to
        traverse several tweets to find something to look up.
        Args:
            tweet: tweepy.models.Status object. Not type hinted because type hinting doesn't work with tweepy.

        Raises:
            TwSauceNoMediaException: Raised if no media entities can be found associated with this tweet

        Returns:
            Tuple[TweetCache, TweetCache, List[str]]: First entry is the original tweet that triggered the lookup,
            the second entry is the tweet we pulled media from. Third item is the actual list of media.
        """
        # Check if this is a reply to one of our posts first
        if self._is_bot_reply(tweet):
            self.log.info('Skipping a tweet that is a comment on a post by the bot account')
            raise TwSauceNoMediaException

        # If the tweet itself has media to search for, return it now
        if self.extract_media(tweet):
            cache = TweetCache.set(tweet, True)
            return cache, cache, self.extract_media(tweet)
        else:
            _cache = TweetCache.set(tweet)

        # The tweet itself doesn't have any media entities. Time to traverse and look for one
        while tweet.in_reply_to_status_id:
            self.log.info(f'Looking up parent tweet ID ( {tweet.id} => {tweet.in_reply_to_status_id} )')
            cache = self.get_tweet(tweet.in_reply_to_status_id)
            tweet = cache.tweet

            # If this is our own post, that means we've already responded to this thread and need to abort, as all
            # replies after this point will forcibly include a mention to us.
            if (tweet.author.id == self.my.id) or (tweet.author.id == SAUCENAOPLS_TWITTER_ID):
                self.log.info(f"Skipping a comment thread we've already responded to via tweet {tweet.id}")
                raise TwSauceNoMediaException

            # Any media content?
            if self.extract_media(tweet):
                self.log.debug('Media found; breaking traversal')
                break

            # Nothing yet? Continue until we hit the top of the chain
        else:
            raise TwSauceNoMediaException

        return _cache, cache, self.extract_media(tweet)

    def _is_bot_reply(self, tweet) -> bool:
        """
        Check and see if this tweet is a reply to a post made by the bots account.
        We can't support queries for the sauce on our own posts, so we just assume we're responsible enough to supply
        this info manually.
        The reason we can't support this is because all replies to our own tweets will have `@botaccount` in their reply
        text, meaning there's no way to differentiate a direct mention and a normal reply to anything.
        If we didn't do this, we'd be responding to every single comment trying to provide the sauce of the original post.
        Returns:
            bool
        """
        if tweet.in_reply_to_status_id:
            parent = self.get_tweet(tweet.in_reply_to_status_id)
            if (parent.tweet.author.id == self.my.id) or (parent.tweet.author.id == SAUCENAOPLS_TWITTER_ID):
                return True

            # Standard ID check
            if tweet.author.id == self.my.id:
                self.log.info(f"Skipping a reply to a bot mention via tweet {tweet.id}")
                return True

            # When someone mentions us to get the sauce of an item, we need to make sure that when others comment
            # on that reply, we don't take that as them also requesting the sauce to the same item.
            # This is due to the weird way Twitter's API works. The only best way I know to do this is to look up the
            # parent tweet ID and see if we're mentioned anywhere in it. If we are, don't reply again.
            if f'@{self.my.screen_name}' in parent.tweet.full_text:
                self.log.info(f"Skipping a reply to a bot mention via tweet {tweet.id}")
                return True

        return False

    @staticmethod
    def extract_media(tweet) -> Optional[List]:
        """
        Extracts the media attribute from a Tweet
        Technically, we should only ever need to check for extended_entities since we migrated to using extended tweet
        lookups. But I'm leaving the old check here just in-case.
        Args:
            tweet:  tweepy.models.Status

        Returns:
            Optional[List[dict]]
        """
        try:
            media = tweet.extended_entities['media']  # type: List[dict]
        except AttributeError:
            try:
                media = tweet.entities['media']  # type: List[dict]
            except KeyError:
                return None

        return [m['media_url_https'] for m in media]


class ReplyLine:
    def __init__(self, message: str, priority: Optional[int] = 100, newlines: int = 0):
        self.message = message
        self.priority = priority
        self.newlines = newlines

    def __str__(self):
        return ("\n" * self.newlines) + self.message
