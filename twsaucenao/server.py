import asyncio
import io
import logging
import os
import reprlib
import tempfile
from typing import *

import aiohttp
import tweepy
from pysaucenao import BooruSource, DailyLimitReachedException, MangaSource, PixivSource, SauceNao, SauceNaoException, \
    ShortLimitReachedException, \
    VideoSource
from tracemoe import ATraceMoe
from twython import Twython

from twsaucenao.api import api
from twsaucenao.config import config
from twsaucenao.errors import *
from twsaucenao.models.database import TRIGGER_MENTION, TRIGGER_MONITORED, TRIGGER_SEARCH, TweetCache, TweetSauceCache
from twsaucenao.pixiv import Pixiv
from twsaucenao.twitter import TweetManager


class TwitterSauce:
    def __init__(self):
        self.log = logging.getLogger(__name__)

        # Tweet Cache Manager
        self.twitter = TweetManager()
        self.twython = Twython(config.get('Twitter', 'consumer_key'), config.get('Twitter', 'consumer_secret'),
                               config.get('Twitter', 'access_token'), config.get('Twitter', 'access_secret'))

        # SauceNao
        self.minsim_mentioned = float(config.get('SauceNao', 'min_similarity_mentioned', fallback=50.0))
        self.minsim_monitored = float(config.get('SauceNao', 'min_similarity_monitored', fallback=65.0))
        self.minsim_searching = float(config.get('SauceNao', 'min_similarity_searching', fallback=70.0))
        self.persistent = config.getboolean('Twitter', 'enable_persistence', fallback=False)
        self.sauce = SauceNao(
                api_key=config.get('SauceNao', 'api_key', fallback=None),
                min_similarity=min(self.minsim_mentioned, self.minsim_monitored, self.minsim_searching),
                priority=[21, 22, 5]
        )

        # Trace.moe
        self.tracemoe = None  # type: Optional[ATraceMoe]
        if config.getboolean('TraceMoe', 'enabled', fallback=False):
            self.tracemoe = ATraceMoe(config.get('TraceMoe', 'token', fallback=None))

        self._anime_link = config.get('TraceMoe', 'source_link', fallback='anidb').lower()
        self._nsfw_previews = config.getboolean('TraceMoe', 'nsfw_previews', fallback=False)

        # Pixiv
        self.pixiv = Pixiv()

        # Cache some information about ourselves
        self.my = api.me()
        self.log.info(f"Connected as: {self.my.screen_name}")

        # Image URL's are md5 hashed and cached here to prevent duplicate API queries. This is cleared every 24-hours.
        # I'll update this in the future to use a real caching mechanism (database or redis)
        self._cached_results = {}

        # A cached list of ID's for parent posts we've already processed
        # Used in the check_monitored() method to prevent re-posting sauces when posts are re-tweeted
        self._posts_processed = []

        # Search queries (optional)
        self.search_queries = str(config.get('Twitter', 'monitored_keywords', fallback=''))
        self.search_queries = [k.strip() for k in self.search_queries.split(',') if k.strip()]
        self.search_charlimit = config.getint('Twitter', 'search_char_limit', fallback=120)

        # The ID cutoff, we populate this once via an initial query at startup
        try:
            self.since_id = tweepy.Cursor(api.mentions_timeline, tweet_mode='extended', count=1).items(1).next().id
        except StopIteration:
            self.since_id = 0
        self.query_since = {}
        self.monitored_since = {}

    # noinspection PyBroadException
    async def check_mentions(self) -> None:
        """
        Check for any new mentions we need to parse
        Returns:
            None
        """
        self.log.info(f"[{self.my.screen_name}] Retrieving mentions since tweet {self.since_id}")
        mentions = [*tweepy.Cursor(api.mentions_timeline, since_id=self.since_id, tweet_mode='extended').items()]

        # Filter tweets without a reply AND attachment
        for tweet in mentions:
            try:
                # Update the ID cutoff before attempting to parse the tweet
                self.since_id = max([self.since_id, tweet.id])
                self.log.debug(f"[{self.my.screen_name}] New max ID cutoff: {self.since_id}")

                # Make sure we aren't mentioning ourselves
                if tweet.author.id == self.my.id:
                    self.log.debug(f"[{self.my.screen_name}] Skipping a self-referencing tweet")
                    continue

                # Attempt to parse the tweets media content
                original_cache, media_cache, media = self.get_closest_media(tweet, self.my.screen_name)

                # Get the sauce!
                sauce_cache, tracemoe_sauce = await self.get_sauce(media_cache, log_index=self.my.screen_name)
                if not sauce_cache.sauce and len(media) > 1 and self.persistent:
                    sauce_cache, tracemoe_sauce = \
                        await self.get_sauce(media_cache, log_index=self.my.screen_name,
                                             trigger=TRIGGER_MONITORED, index_no=len(media) - 1)

                self.send_reply(tweet_cache=original_cache, media_cache=media_cache, sauce_cache=sauce_cache,
                                blocked=media_cache.blocked, tracemoe_sauce=tracemoe_sauce)
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
                tweet = next(tweepy.Cursor(api.user_timeline, account, page=1, tweet_mode='extended').items())
                self.monitored_since[account] = tweet.id
                self.log.info(f"[{account}] Monitoring tweets after {tweet.id}")
                continue

            # Get all tweets since our last check
            self.log.info(f"[{account}] Retrieving tweets since {self.monitored_since[account]}")
            tweets = [*tweepy.Cursor(api.user_timeline, account, since_id=self.monitored_since[account], tweet_mode='extended').items()]
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
                    if 'RT @' in tweet.full_text or hasattr(tweet, 'retweeted_status'):
                        self.log.info(f"[{account}] Retweeted post; ignoring")
                        continue

                    original_cache, media_cache, media = self.get_closest_media(tweet, account)
                    self.log.info(f"[{account}] Found new media post in tweet {tweet.id}: {media[0]}")

                    # Get the sauce
                    sauce_cache, tracemoe_sauce = await self.get_sauce(media_cache, log_index=account, trigger=TRIGGER_MONITORED)
                    sauce = sauce_cache.sauce

                    if not sauce and len(media) > 1 and self.persistent:
                        sauce_cache, tracemoe_sauce = \
                            await self.get_sauce(media_cache, log_index=account, trigger=TRIGGER_MONITORED,
                                                 index_no=len(media) - 1)
                        sauce = sauce_cache.sauce

                    self.log.info(f"[{account}] Found {sauce.index} sauce for tweet {tweet.id}" if sauce
                                  else f"[{account}] Failed to find sauce for tweet {tweet.id}")

                    self.send_reply(tweet_cache=original_cache, media_cache=media_cache, sauce_cache=sauce_cache,
                                    requested=False)
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
        if not self.search_queries:
            self.log.debug("[SEARCH] Search query monitoring disabled")
            return

        for query in self.search_queries:
            search_results = api.search(query, result_type='recent', count=10, include_entities=True,
                                        since_id=self.query_since.get(query, 0), tweet_mode='extended')

            # Populate the starting max ID
            if not self.query_since.get(query):
                self.query_since[query] = search_results[0].id
                self.log.info(f"[SEARCH] Monitoring tweets after {self.query_since[query]} for search query: {query}")
                continue

            # Iterate and process the search results
            for tweet in search_results:
                # Update the ID cutoff before continuing
                self.query_since[query] = max([self.query_since[query], tweet.id])

                # Make sure we aren't searching ourselves somehow
                if tweet.author.id == self.my.id:
                    self.log.debug(f"[SEARCH] Skip: Ignoring a self-tweet")
                    continue

                # Make sure we don't respond twice if the user used our trigger phrase AND mentioned us
                if f'@{self.my.screen_name}' in tweet.full_text:
                    self.log.info("[SEARCH] Skip: This query includes a bot mention")
                    continue

                # Make sure this post doesn't exceed the character limit
                if len(tweet.full_text) >= self.search_charlimit:
                    self.log.info(f"[SEARCH] Skip: Query matched but exceeded the {self.search_charlimit} character limit")
                    continue

                try:
                    # Process the tweet for media content
                    self.log.info(f"[SEARCH] Processing tweet {tweet.id}")
                    original_cache, media_cache, media = self.get_closest_media(tweet, 'SEARCH')
                    self.log.info(f"[SEARCH] Found media post in tweet {tweet.id}: {media[0]}")

                    # Get the sauce
                    sauce_cache, tracemoe_sauce = await self.get_sauce(media_cache, log_index='SEARCH', trigger=TRIGGER_SEARCH)
                    sauce = sauce_cache.sauce
                    if not sauce and len(media) > 1 and self.persistent:
                        sauce_cache, tracemoe_sauce = \
                            await self.get_sauce(media_cache, log_index='SEARCH', trigger=TRIGGER_MONITORED,
                                                 index_no=len(media) - 1)
                        sauce = sauce_cache.sauce

                    self.log.info(f"[SEARCH] Found {sauce.index} sauce for tweet {tweet.id}" if sauce
                                  else f"[SEARCH] Failed to find sauce for tweet {tweet.id}")

                    self.send_reply(tweet_cache=original_cache, media_cache=media_cache, sauce_cache=sauce_cache,
                                    requested=False)
                except TwSauceNoMediaException:
                    self.log.info(f"[SEARCH] No sauce found for tweet {tweet.id}")
                    continue

    async def get_sauce(self, tweet_cache: TweetCache, index_no: int = 0, log_index: Optional[str] = None,
                        trigger: str = TRIGGER_MENTION) -> Tuple[TweetSauceCache, Optional[bytes]]:
        """
        Get the sauce of a media tweet
        """
        log_index = log_index or 'SYSTEM'

        # Have we cached the sauce already?
        cache = TweetSauceCache.fetch(tweet_cache.tweet_id, index_no)
        if cache:
            return cache, None

        media = TweetManager.extract_media(tweet_cache.tweet)[index_no]

        # Execute a Tracemoe search query for anime results
        async def tracemoe_search(_sauce, is_url: bool) -> Optional[dict]:
            if not self.tracemoe:
                return None

            if _sauce.results and _sauce.results[0].index_id in [21, 22]:
                # noinspection PyBroadException
                try:
                    _tracemoe_sauce = await self.tracemoe.search(path, is_url=is_url)
                except Exception:
                    self.log.warning(f"[{log_index}] Tracemoe returned an exception, aborting search query")
                    return None
                if not _tracemoe_sauce.get('docs'):
                    return None

                # Check for an exactly title match first, then fallback to a similarity check.
                # Obviously, this is not perfect. Titles don't always match, but sometimes tracemoe returns an accurate
                # result with a lower similarity, so we just.. try and guess the best we can for now.
                tm_english_title = _tracemoe_sauce['docs'][0]['title_english'].lower()
                tm_romaji_title  = _tracemoe_sauce['docs'][0]['title_romaji'].lower()
                sn_title         = sauce.results[0].title.lower()

                if tm_romaji_title != sn_title:
                    self.log.warning(f'[{log_index}] saucenao and trace.moe provided mismatched english titles: `{sn_title}` vs. `{tm_romaji_title}`')
                    if tm_english_title != sn_title:
                        self.log.warning(f'[{log_index}] saucenao and trace.moe provided mismatched romaji titles: `{sn_title}` vs. `{tm_english_title}`')
                        if _tracemoe_sauce['docs'][0]['similarity'] < 0.85:
                            self.log.warning(f'[{log_index}] Similarity check failed on trace.moe query for `{sn_title}`')
                            return None

                self.log.info(f'[{log_index}] Downloading video preview for `{tm_english_title}` from trace.moe')
                _tracemoe_preview = await self.tracemoe.video_preview_natural(_tracemoe_sauce)
                _tracemoe_sauce['docs'][0]['preview'] = _tracemoe_preview
                return _tracemoe_sauce['docs'][0]

            return None

        # Look up the sauce
        try:
            if config.getboolean('SauceNao', 'download_files', fallback=False):
                self.log.debug(f"[{log_index}] Downloading image from Twitter")
                fd, path = tempfile.mkstemp()
                try:
                    with os.fdopen(fd, 'wb') as tmp:
                        async with aiohttp.ClientSession(raise_for_status=True) as session:
                            try:
                                async with await session.get(media) as response:
                                    image = await response.read()
                                    tmp.write(image)
                                    if not image:
                                        self.log.error(f"[{log_index}] Empty file received from Twitter")
                                        sauce_cache = TweetSauceCache.set(tweet_cache, index_no=index_no,
                                                                          trigger=trigger)
                                        return sauce_cache
                            except aiohttp.ClientResponseError as error:
                                self.log.warning(f"[{log_index}] Twitter returned a {error.status} error when downloading from tweet {tweet_cache.tweet_id}")
                                sauce_cache = TweetSauceCache.set(tweet_cache, index_no=index_no, trigger=trigger)
                                return sauce_cache

                        sauce = await self.sauce.from_file(path)
                        tracemoe_sauce = await tracemoe_search(sauce, is_url=False)
                finally:
                    os.remove(path)
            else:
                self.log.debug(f"[{log_index}] Performing remote URL lookup")
                sauce = await self.sauce.from_url(media)
                tracemoe_sauce = await tracemoe_search(sauce, is_url=True)

            if not sauce.results:
                sauce_cache = TweetSauceCache.set(tweet_cache, sauce, index_no, trigger=trigger)
                return sauce_cache, None
        except ShortLimitReachedException:
            self.log.warning(f"[{log_index}] Short API limit reached, throttling for 30 seconds")
            await asyncio.sleep(30.0)
            return await self.get_sauce(tweet_cache, index_no, log_index)
        except DailyLimitReachedException:
            self.log.error(f"[{log_index}] Daily API limit reached, throttling for 15 minutes. Please consider upgrading your API key.")
            await asyncio.sleep(900.0)
            return await self.get_sauce(tweet_cache, index_no, log_index)
        except SauceNaoException as e:
            self.log.error(f"[{log_index}] SauceNao exception raised: {e}")
            sauce_cache = TweetSauceCache.set(tweet_cache, index_no=index_no, trigger=trigger)
            return sauce_cache, None

        sauce_cache = TweetSauceCache.set(tweet_cache, sauce, index_no, trigger=trigger)
        return sauce_cache, tracemoe_sauce

    def get_closest_media(self, tweet, log_index: Optional[str] = None) -> Optional[Tuple[TweetCache, TweetCache, List[str]]]:
        """
        Attempt to get the closest media element associated with this tweet and handle any errors if they occur
        Args:
            tweet: tweepy.models.Status
            log_index (Optional[str]): Index to use for system logs. Defaults to SYSTEM

        Returns:
            Optional[List]
        """
        log_index = log_index or 'SYSTEM'

        try:
            original_cache, media_cache, media = self.twitter.get_closest_media(tweet)
        except tweepy.error.TweepError as error:
            # Error 136 means we are blocked
            if error.api_code == 136:
                # noinspection PyBroadException
                try:
                    api.update_status(
                            f"@{tweet.author.screen_name} Sorry, it looks like the author of this post has blocked us. For more information, please refer to:\nhttps://github.com/FujiMakoto/twitter-saucenao/#blocked-by",
                            in_reply_to_status_id=tweet.id, auto_populate_reply_metadata=True
                    )
                except Exception as error:
                    self.log.exception(f"[{log_index}] An exception occurred while trying to inform a user that an account has blocked us")
                raise TwSauceNoMediaException
            # We attempted to process a tweet from a user that has restricted access to their account
            elif error.api_code in [179, 385]:
                self.log.info(f"[{log_index}] Skipping a tweet we don't have permission to view")
                raise TwSauceNoMediaException
            # Someone got impatient and deleted a tweet before we could get too it
            elif error.api_code == 144:
                self.log.info(f"[{log_index}] Skipping a tweet that no longer exists")
                raise TwSauceNoMediaException
            # Something unfamiliar happened, log an error for later review
            else:
                self.log.error(f"[{log_index}] Skipping due to unknown Twitter error: {error.api_code} - {error.reason}")
                raise TwSauceNoMediaException

        # Still here? Yay! We have something then.
        return original_cache, media_cache, media

    def send_reply(self, tweet_cache: TweetCache, media_cache: TweetCache, sauce_cache: TweetSauceCache,
                   tracemoe_sauce: Optional[dict] = None, requested: bool = True, blocked: bool = False) -> None:
        """
        Return the source of the image
        Args:
            tweet_cache (TweetCache): The tweet to reply to
            media_cache (TweetCache): The tweet containing media elements
            sauce_cache (Optional[GenericSource]): The sauce found (or None if nothing was found)
            tracemoe_sauce (Optional[dict]): Tracemoe sauce query, if enabled
            requested (bool): True if the lookup was requested, or False if this is a monitored user account
            blocked (bool): If True, the account posting this has blocked the SauceBot

        Returns:
            None
        """
        tweet = tweet_cache.tweet
        sauce = sauce_cache.sauce

        if sauce is None:
            if requested:
                media = TweetManager.extract_media(media_cache.tweet)
                if not media:
                    return

                yandex_url  = f"https://yandex.com/images/search?url={media[sauce_cache.index_no]}&rpt=imageview"
                tinyeye_url = f"https://www.tineye.com/search?url={media[sauce_cache.index_no]}"
                google_url  = f"https://www.google.com/searchbyimage?image_url={media[sauce_cache.index_no]}&safe=off"

                api.update_status(
                        f"@{tweet.author.screen_name} Sorry, I couldn't find anything (●´ω｀●)ゞ\nYour image may be cropped too much, or the artist may simply not exist in any of SauceNao's databases.\n\nTry checking one of these search engines!\n{yandex_url}\n{google_url}\n{tinyeye_url}",
                        in_reply_to_status_id=tweet.id
                )
            return

        # For limiting the length of the title/author
        repr = reprlib.Repr()
        repr.maxstring = 32

        # Add additional sauce URL's from trace.moe if available
        sauce_urls = []
        if tracemoe_sauce:
            if self._anime_link in ['anilist', 'animal', 'all']:
                sauce_urls.append(f"https://anilist.co/anime/{tracemoe_sauce['anilist_id']}/")

            if self._anime_link in ['myanimelist', 'animal', 'all'] and tracemoe_sauce.get('mal_id'):
                sauce_urls.append(f"https://myanimelist.net/anime/{tracemoe_sauce['mal_id']}/")

            if self._anime_link in ['anidb', 'all']:
                sauce_urls.append(sauce.url)

        # H-Misc doesn't have a source to link to, so we need to try and provide the full title
        if sauce.index not in ['H-Misc', 'E-Hentai']:
            title = repr.repr(sauce.title).strip("'")
        else:
            repr.maxstring = 128
            title = repr.repr(sauce.title).strip("'")

        # Format the similarity string
        similarity = f'𝗔𝗰𝗰𝘂𝗿𝗮𝗰𝘆: {sauce.similarity}% ( '
        if sauce.similarity >= 85.0:
            similarity = similarity + '🔵 High )'
        elif sauce.similarity >= 70.0:
            similarity = similarity + '🟡 Medium )'
        else:
            similarity = similarity + '🟠 Low )'

        if requested:
            reply = f"@{tweet.author.screen_name} I found this in the {sauce.index} database!\n"
        else:
            reply = f"Need the sauce? I found it in the {sauce.index} database!\n"

        # If it's a Pixiv source, try and get their Twitter handle (this is considered most important and displayed first)
        twitter_sauce = None
        if isinstance(sauce, PixivSource):
            twitter_sauce = self.pixiv.get_author_twitter(sauce.data['member_id'])
            if twitter_sauce:
                reply += f"\n𝗔𝗿𝘁𝗶𝘀𝘁𝘀 𝗧𝘄𝗶𝘁𝘁𝗲𝗿: {twitter_sauce}"

        # Print the author name if available
        if sauce.author_name:
            author = repr.repr(sauce.author_name).strip("'")
            reply += f"\n𝗔𝘂𝘁𝗵𝗼𝗿: {author}"

        # Omit the title for Pixiv results since it's usually always non-romanized Japanese and not very helpful
        if not isinstance(sauce, PixivSource):
            reply += f"\n𝗧𝗶𝘁𝗹𝗲: {title}"

        # Add the episode number and timestamp for video sources
        if isinstance(sauce, VideoSource):
            if sauce.episode:
                reply += f"\n𝗘𝗽𝗶𝘀𝗼𝗱𝗲: {sauce.episode}"
            if sauce.timestamp:
                reply += f" ( ⏱️ {sauce.timestamp} )"

        # Add the chapter for manga sources
        if isinstance(sauce, MangaSource):
            if sauce.chapter:
                reply += f"\n𝗖𝗵𝗮𝗽𝘁𝗲𝗿: {sauce.chapter}"

        # Display our confidence rating
        reply += f"\n{similarity}"

        # Source URL's are not available in some indexes
        if sauce_urls:
            reply += "\n\n"
            reply += "\n".join(sauce_urls)
        elif sauce.source_url:
            reply += f"\n\n{sauce.source_url}"

        # Some Booru posts have bad source links cited, so we should always provide a Booru link with the source URL
        if isinstance(sauce, BooruSource) and sauce.source_url != sauce.url:
            reply += f"\n{sauce.url}"

        # Try and append bot instructions with monitored posts. This might make our post too long, though.
        if not requested:
            _reply = reply
            reply += f"\n\nNeed sauce elsewhere? Just follow and (@)mention me in a reply and I'll be right over!"

        try:
            if tracemoe_sauce and tracemoe_sauce['is_adult'] and not self._nsfw_previews:
                self.log.warning(f'NSFW video previews are disabled, skipping preview of `{sauce.title}`')
            elif tracemoe_sauce:
                try:
                    tw_response = self.twython.upload_video(media=io.BytesIO(tracemoe_sauce['preview']), media_type='video/mp4')
                    comment = api.update_status(reply, in_reply_to_status_id=tweet.id, auto_populate_reply_metadata=True,
                                                media_ids=[tw_response['media_id']], possibly_sensitive=tracemoe_sauce['is_adult'])
                except tweepy.error.TweepError as error:
                    if error.api_code == 324:
                        self.log.warning(f"Video preview for `{sauce.title}` was too short to upload to Twitter")
                        comment = api.update_status(reply, in_reply_to_status_id=tweet.id,
                                                    auto_populate_reply_metadata=True)
                    else:
                        raise error
            else:
                comment = api.update_status(reply, in_reply_to_status_id=tweet.id, auto_populate_reply_metadata=True)
        except tweepy.TweepError as error:
            if error.api_code == 186 and not requested:
                self.log.info("Post is too long; scrubbing bot instructions from message")
                # noinspection PyUnboundLocalVariable
                comment = api.update_status(_reply, in_reply_to_status_id=tweet.id, auto_populate_reply_metadata=True)
            else:
                raise error

        # If we've been blocked by this user and have the artists Twitter handle, send the artist a DMCA guide
        if blocked:
            if twitter_sauce:
                self.log.warning(f"Sending {twitter_sauce} DMCA takedown advice")
                api.update_status(f"""{twitter_sauce} This account has stolen your artwork and blocked me for crediting you. このアカウントはあなたの絵を盗んで、私があなたを明記したらブロックされちゃいました
    https://github.com/FujiMakoto/twitter-saucenao/blob/master/DMCA.md
    https://help.twitter.com/forms/dmca""", in_reply_to_status_id=comment.id, auto_populate_reply_metadata=True)
            else:
                api.update_status(f"This account has blocked {self.my.name} for helping people like you. Be wary; they may block you as well for sharing the source or for requesting me!\n"
                                  f"\nFor more information, please refer to:\n"
                                  "https://github.com/FujiMakoto/twitter-saucenao#art-thieves-saucebot-has-been-blocked-by",
                                  in_reply_to_status_id=comment.id, auto_populate_reply_metadata=True)
