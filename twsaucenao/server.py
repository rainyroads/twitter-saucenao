import asyncio
import hashlib
import logging
import reprlib
from typing import *

import tweepy
from pysaucenao import GenericSource, SauceNao, ShortLimitReachedException, SauceNaoException, VideoSource

from twsaucenao.api import twitter_api
from twsaucenao.config import config
from twsaucenao.errors import *


class TwitterSauce:
    def __init__(self):
        self.log = logging.getLogger(__name__)
        self.api = twitter_api()
        self.sauce = SauceNao(api_key=config.get('SauceNao', 'api_key', fallback=None))

        # Cache some information about ourselves
        self.my = self.api.me()
        self.log.info(f"Connected as: {self.my.screen_name}")

        # Image URL's are md5 hashed and cached here to prevent duplicate API queries. This is cleared every 24-hours.
        # I'll update this in the future to use a real caching mechanism (database or redis)
        self._cached_results = {}

        # A cached list of ID's for parent posts we've already processed
        # Used in the check_monitored() method to prevent re-posting sauces when posts are re-tweeted
        self._posts_processed = []

        # Search query (optional)
        self.search_query = str(config.get('Twitter', 'monitored_keyword'))

        # The ID cutoff, we populate this once via an initial query at startup
        self.since_id = max([t.id for t in [*tweepy.Cursor(self.api.mentions_timeline).items()]]) or 1
        self.query_since = 0
        self.monitored_since = {}

    # noinspection PyBroadException
    async def check_mentions(self) -> None:
        """
        Check for any new mentions we need to parse
        Returns:
            None
        """
        self.log.info(f"[{self.my.screen_name}] Retrieving mentions since tweet {self.since_id}")

        mentions = [*tweepy.Cursor(self.api.mentions_timeline, since_id=self.since_id).items()]

        # Filter tweets without a reply AND attachment
        for tweet in mentions:
            try:
                # Update the ID cutoff before attempting to parse the tweet
                self.since_id = max([self.since_id, tweet.id])
                self.log.debug(f"[{self.my.screen_name}] New max ID cutoff: {self.since_id}")

                # Make sure we aren't mentioning ourselves
                if tweet.author.id == self.my.id:
                    self.log.debug(f"[{self.my.screen_name}] Ignoring a self-mentioning tweet")
                    continue

                media = self.parse_tweet_media(tweet)
                sauce = await self.get_sauce(media[0])
                self.send_reply(tweet, sauce)
            except TwSauceNoMediaException:
                self.log.debug(f"[{self.my.screen_name}] Tweet {tweet.id} has no media to process, ignoring")
                continue
            except Exception:
                self.log.exception(f"[{self.my.screen_name}] An unknown error occurred while processing tweet {tweet.id}")
                continue

    async def check_monitored(self) -> None:
        """
        Checks monitored accounts for any new tweets
        Returns:
            None
        """
        monitored_accounts = str(config.get('Twitter', 'monitored_accounts'))
        if not monitored_accounts:
            return

        monitored_accounts = [a.strip() for a in monitored_accounts.split(',')]

        for account in monitored_accounts:
            # Have we fetched a tweet for this account yet?
            if account not in self.monitored_since:
                # If not, get the last tweet ID from this account and wait for the next post
                tweet = next(tweepy.Cursor(self.api.user_timeline, account, page=1).items())
                self.monitored_since[account] = tweet.id
                self.log.info(f"[{account}] Monitoring tweets after {tweet.id}")
                continue

            # Get all tweets since our last check
            self.log.info(f"[{account}] Retrieving tweets since {self.monitored_since[account]}")
            tweets = [*tweepy.Cursor(self.api.user_timeline, account, since_id=self.monitored_since[account]).items()]  # type: List[tweepy.models.Status]
            self.log.info(f"[{account}] {len(tweets)} tweets found")
            for tweet in tweets:
                try:
                    # Update the ID cutoff before attempting to parse the tweet
                    self.monitored_since[account] = max([self.monitored_since[account], tweet.id])

                    # Make sure this isn't a comment / reply
                    if tweet.in_reply_to_status_id:
                        self.log.info(f"[{account}] Tweet is a reply/comment; ignoring")
                        continue

                    # Make sure we haven't already processed this post
                    if tweet.id in self._posts_processed:
                        self.log.info(f"[{account}] Post has already been processed; ignoring")
                        continue
                    self._posts_processed.append(tweet.id)

                    # Make sure this isn't a re-tweet
                    if 'RT @' in tweet.text or hasattr(tweet, 'retweeted_status'):
                        self.log.info(f"[{account}] Retweeted post; ignoring")
                        continue

                    media = self.parse_tweet_media(tweet)
                    self.log.info(f"[{account}] Found new media post in tweet {tweet.id}: {media[0]['media_url_https']}")

                    sauce = await self.get_sauce(media[0])
                    self.log.info(f"[{account}] Found {sauce.index} sauce for tweet {tweet.id}" if sauce
                                  else f"[{account}] Failed to find sauce for tweet {tweet.id}")

                    self.send_reply(tweet, sauce, False)
                except TwSauceNoMediaException:
                    self.log.info(f"[{account}] No sauce found for tweet {tweet.id}")
                    continue
                except Exception:
                    self.log.exception(f"[{account}] An unknown error occurred while processing tweet {tweet.id}")
                    continue

    async def check_query(self) -> None:
        """
        Performs a search query for a specific key-phrase (e.g. "sauce pls") and attempts to find the source of the
        image for someone. It's a really wild buckshot method of operating, but it could have potential use!
        Returns:
            None
        """
        if not self.search_query:
            self.log.debug("[SEARCH] Search query monitoring disabled")
            return

        search_results = self.api.search(self.search_query, result_type='recent', count=10, include_entities=True,
                                         since_id=self.query_since)

        # Populate the starting max ID
        if not self.query_since:
            self.query_since = search_results[0].id
            self.log.info(f"[SEARCH] Monitoring tweets after {self.query_since} for search query: {self.search_query}")
            return

        # Iterate and process the search results
        for tweet in search_results:
            # Make sure we aren't searching ourselves somehow
            if tweet.author.id == self.my.id:
                self.log.debug(f"[SEARCH] Ignoring a self-tweet")
                continue

            try:
                # Update the ID cutoff before attempting to parse the tweet
                self.query_since = max([self.query_since, tweet.id])

                self.log.info(f"[SEARCH] Processing tweet {tweet.id}")
                media = self.parse_tweet_media(tweet)
                self.log.info(f"[SEARCH] Found media post in tweet {tweet.id}: {media[0]['media_url_https']}")

                sauce = await self.get_sauce(media[0])
                self.log.info(f"[SEARCH] Found {sauce.index} sauce for tweet {tweet.id}" if sauce
                              else f"[SEARCH] Failed to find sauce for tweet {tweet.id}")

                self.send_reply(tweet, sauce, False)
            except TwSauceNoMediaException:
                self.log.info(f"[SEARCH] No sauce found for tweet {tweet.id}")
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
        try:
            sauce = await self.sauce.from_url(media['media_url_https'])
            if not sauce.results:
                self._cached_results[url_hash] = None
                return None
        except ShortLimitReachedException:
            self.log.warning("Short API limit reached, throttling for 30 seconds")
            await asyncio.sleep(30.0)
            return await self.get_sauce(media)
        except SauceNaoException as e:
            self.log.error(f"SauceNao exception raised: {e}")
            return None

        self._cached_results[url_hash] = sauce[0]
        return sauce[0]

    def send_reply(self, tweet: tweepy.models.Status, sauce: Optional[GenericSource], requested=True) -> None:
        """
        Return the source of the image
        Args:
            tweet (tweepy.models.Status): The tweet to reply to
            sauce (Optional[GenericSource]): The sauce found (or None if nothing was found)
            requested (bool): True if the lookup was requested, or False if this is a monitored user account

        Returns:
            None
        """
        if sauce is None:
            if requested:
                self.api.update_status(
                        f"@{tweet.author.screen_name} Sorry, I couldn't find anything for you 😔",
                        in_reply_to_status_id=tweet.id
                )
            return

        # For limiting the length of the title/author
        repr = reprlib.Repr()
        repr.maxstring = 32

        # H-Misc doesn't have a source to link to, so we need to try and provide the full title
        if sauce.index != 'H-Misc':
            title = repr.repr(sauce.title).strip("'")

        if requested:
            reply = f"@{tweet.author.screen_name} I found something for you on {sauce.index}!\n\nTitle: {title}"
        else:
            reply = f"I found the source of this on {sauce.index}!\n\nTitle: {title}"

        if sauce.author_name:
            author = repr.repr(sauce.author_name).strip("'")
            reply += f"\nAuthor: {author}"

        if isinstance(sauce, VideoSource):
            if sauce.episode:
                reply += f"\nEpisode: {sauce.episode}"
            if sauce.timestamp:
                reply += f"\nTimestamp: {sauce.timestamp}"

        reply += f"\n{sauce.source_url}"

        if not requested:
            reply += f"\n\nI can help you look up the sauce to images elsewhere too! Just mention me in a reply to an image you want to look up."
        self.api.update_status(reply, in_reply_to_status_id=tweet.id, auto_populate_reply_metadata=not requested)

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
            while tweet.in_reply_to_status_id:
                # If this is a post by the SauceNao bot, abort, as it means we've already responded to this thread
                if tweet.author.id == self.my.id:
                    self.log.info(f"We've already responded to this comment thread; ignoring")
                    raise TwSauceNoMediaException

                # Get the parent comment / tweet
                self.log.info(f"Looking up parent tweet ID ( {tweet.id} => {tweet.in_reply_to_status_id} )")
                tweet = self.api.get_status(tweet.in_reply_to_status_id)

                # When someone mentions us to get the sauce of an item, we need to make sure that when others comment
                # on that reply, we don't take that as them also requesting the sauce to the same item.
                # This is due to the weird way Twitter's API works. The only sane way to do this is to look up the
                # parent tweet ID and see if we're mentioned anywhere in it. If we are, don't reply again.
                if f'@{self.my.screen_name}' in tweet.text:
                    self.log.info("This is a reply to a mention, not the original mention; ignoring")
                    raise TwSauceNoMediaException

                # Any media content in this tweet?
                if 'media' in tweet.entities:
                    self.log.info(f"Media content found in tweet {tweet.id}")
                    break

                if hasattr(tweet, 'extended_entities') and 'media' in tweet.extended_entities:
                    self.log.info(f"Media content found in tweet {tweet.id}")
                    break

        except tweepy.TweepError:
            self.log.warning(f"Tweet {tweet.in_reply_to_status_id} no longer exists or we don't have permission to view it")
            raise TwSauceNoMediaException

        # Now we have a direct tweet to parse!
        return self._parse_direct(tweet)
