import logging
from typing import List, Optional

import tweepy

from twsaucenao import SAUCENAOPLS_TWITTER_ID
from twsaucenao.api import api, readonly_api
from twsaucenao.errors import TwSauceNoMediaException


class TweetParser:
    def __init__(self, tweet):
        self.log = logging.getLogger(__name__)
        self.my = api.me()

        # The tweet to look up
        self.tweet = tweet
        
        # Has the bot been blocked by this account?
        self.blocked = False

        # HTTPS Url to the tweet media
        self._tweet_media = None

    @property
    def media(self):
        if self._tweet_media:
            return self._tweet_media

        self._tweet_media = [m['media_url_https'] for m in self.find_closest_media()]
        return self._tweet_media

    # noinspection PyUnresolvedReferences
    def find_closest_media(self) -> List[dict]:
        """
        Determine whether this is a direct tweet or a reply, then parse the media accordingly
        """
        if self.tweet.in_reply_to_status_id:
            return self._parse_reply(self.tweet)

        return self._parse_direct(self.tweet)

    def _parse_direct(self, tweet) -> List[dict]:
        """
        Direct tweet (someone tweeting at us directly, not as a reply to another tweet)
        Should have media attached, otherwise it's invalid and we ignore it
        """
        try:
            media = tweet.extended_entities['media']  # type: List[dict]
        except AttributeError:
            try:
                media = tweet.entities['media']  # type: List[dict]
            except KeyError:
                self.log.info(f"Tweet {tweet.id} does not have any downloadable media")
                raise TwSauceNoMediaException

        return media

    def _parse_reply(self, tweet) -> List[dict]:
        """
        If we were mentioned in a reply, we want to get the sauce to the message we replied to
        """
        # First, check and see if this is a reply to a post made by us
        if tweet.in_reply_to_status_id:
            parent = self._get_status(tweet.in_reply_to_status_id)
            if parent.author.id == self.my.id:
                self.log.info("This is a comment on our own post; ignoring")
                raise TwSauceNoMediaException

            if parent.author.id == SAUCENAOPLS_TWITTER_ID:
                self.log.info("The official SauceNaoPls account has already responded to this post; ignoring")
                raise TwSauceNoMediaException

        while tweet.in_reply_to_status_id:
            # If this is a post by the SauceNao bot, abort, as it means we've already responded to this thread
            if tweet.author.id == self.my.id:
                self.log.info(f"We've already responded to this comment thread; ignoring")
                raise TwSauceNoMediaException

            if tweet.author.id == SAUCENAOPLS_TWITTER_ID:
                self.log.info("The official SauceNaoPls account has already responded to this post; ignoring")
                raise TwSauceNoMediaException

            # Get the parent comment / tweet
            self.log.info(f"Looking up parent tweet ID ( {tweet.id} => {tweet.in_reply_to_status_id} )")
            tweet = self._get_status(tweet.in_reply_to_status_id)

            # When someone mentions us to get the sauce of an item, we need to make sure that when others comment
            # on that reply, we don't take that as them also requesting the sauce to the same item.
            # This is due to the weird way Twitter's API works. The only sane way to do this is to look up the
            # parent tweet ID and see if we're mentioned anywhere in it. If we are, don't reply again.
            if f'@{self.my.screen_name}' in tweet.full_text:
                self.log.info("This is a reply to a mention, not the original mention; ignoring")
                raise TwSauceNoMediaException

            # Any media content in this tweet?
            if 'media' in tweet.entities:
                self.log.info(f"Media content found in tweet {tweet.id}")
                break

            if hasattr(tweet, 'extended_entities') and 'media' in tweet.extended_entities:
                self.log.info(f"Media content found in tweet {tweet.id}")
                break

        # Now we have a direct tweet to parse!
        return self._parse_direct(tweet)

    def _get_status(self, tweet_id):
        """
        Get the specified tweet
        Args:
            tweet_id (int): The twitter tweet ID

        Returns:
            tweepy.Status
        """
        try:
            self.blocked = False  # Reset the blocked status in-case it's just someone in a chain that has blocked us
            tweet = api.get_status(tweet_id, tweet_mode='extended')
        except tweepy.TweepError as error:
            if error.api_code == 136:
                self.blocked = True
                if readonly_api:
                    self.log.warning(f"User has blocked the main account; falling back to read-only API for media parsing tweet {tweet_id}")
                    tweet = readonly_api.get_status(tweet_id, tweet_mode='extended')
                else:
                    self.log.warning(f"User that submitted tweet {tweet_id} has blocked the bots account, unable to perform lookup")
                    raise error
            else:
                raise error

        return tweet
