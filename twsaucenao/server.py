import hashlib
import logging
import reprlib
from typing import *

import tweepy
from pysaucenao import GenericSource, SauceNao

from twsaucenao.api import twitter_api
from twsaucenao.errors import *


class TwitterSauce:
    def __init__(self):
        self.log = logging.getLogger(__name__)
        self.api = twitter_api()
        self.sauce = SauceNao()

        # Image URL's are md5 hashed and cached here to prevent duplicate API queries. This is cleared every 24-hours.
        # I'll update this in the future to use a real caching mechanism (database or redis)
        self._cached_results = {}

        # The ID cutoff, we populate this once via an initial query at startup
        self.since_id = max([t.id for t in [*tweepy.Cursor(self.api.mentions_timeline).items()]]) or 1

    # noinspection PyBroadException
    async def check_mentions(self) -> None:
        self.log.info(f"Retrieving mentions since tweet {self.since_id}")

        mentions = [*tweepy.Cursor(self.api.mentions_timeline, since_id=self.since_id).items()]  # type: List[tweepy.models.Status]

        # Filter tweets without a reply AND attachment
        for tweet in mentions:
            try:
                # Update the ID cutoff before attempting to parse the tweet
                self.since_id = max([self.since_id, tweet.id])
                media = self.parse_tweet_media(tweet)
                sauce = await self.get_sauce(media[0])
                self.send_reply(tweet, sauce)
            except TwSauceNoMediaException:
                self.log.info(f"Skipping tweet {tweet.id}")
                continue
            except Exception:
                self.log.exception(f"An unknown error occurred while processing tweet {tweet.id}")
                continue

    async def get_sauce(self, media: dict) -> Optional[GenericSource]:
        """
        Get the sauce of a media tweet
        """
        # Have we cached this tweet already?
        url_hash = hashlib.md5(media['media_url_https'].encode()).hexdigest()
        if url_hash in self._cached_results:
            return self._cached_results[url_hash]

        # Look up the sauce
        sauce = await self.sauce.from_url(media['media_url_https'])
        if not sauce.results:
            self._cached_results[url_hash] = None
            return None

        self._cached_results[url_hash] = sauce[0]
        return sauce[0]

    def send_reply(self, tweet: tweepy.models.Status, sauce: Optional[GenericSource]) -> None:
        """
        Return the source of the image
        """
        if sauce is None:
            self.log.info(f"Failed to find sauce for tweet {tweet.id}")
            self.api.update_status(
                    f"@{tweet.author.screen_name} Sorry, I couldn't find anything for you 😔",
                    in_reply_to_status_id=tweet.id
            )
            return

        # For limiting the length of the title/author
        repr = reprlib.Repr()
        repr.maxstring = 32

        self.log.info(f"Found {sauce.index} sauce for tweet {tweet.id}")
        reply = f"@{tweet.author.screen_name} I found something for you on {sauce.index}!\n\nTitle: {repr.repr(sauce.title)}\nAuthor: {repr.repr(sauce.author_name)}\n{sauce.source_url}"
        self.api.update_status(reply, in_reply_to_status_id=tweet.id)

    # noinspection PyUnresolvedReferences
    def parse_tweet_media(self, tweet: tweepy.models.Status) -> List[dict]:
        """
        Determine whether this is a direct tweet or a reply, then parse the media accordingly
        """
        if tweet.in_reply_to_status_id:
            return self._parse_reply(tweet)

        return self._parse_direct(tweet)

    def _parse_direct(self, tweet: tweepy.models.Status) -> List[dict]:
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
                self.log.warning(f"Tweet {tweet.id} does not have any downloadable media")
                raise TwSauceNoMediaException

        return media

    def _parse_reply(self, tweet: tweepy.models.Status) -> List[dict]:
        """
        If we were mentioned in a reply, we want to get the sauce to the message we replied to
        """
        try:
            self.log.info(f"Looking up tweet ID {tweet.in_reply_to_status_id}")
            parent = self.api.get_status(tweet.in_reply_to_status_id)
        except tweepy.TweepError:
            self.log.warning(f"Tweet {tweet.in_reply_to_status_id} no longer exists or we don't have permission to view it")
            raise TwSauceNoMediaException

        # No we have a direct tweet to parse!
        return self._parse_direct(parent)
