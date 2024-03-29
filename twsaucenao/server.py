import asyncio
import logging
import reprlib
import typing

import tweepy
from pysaucenao import AnimeSource, BooruSource, DailyLimitReachedException, MangaSource, PixivSource, \
    SauceNaoException, \
    ShortLimitReachedException, \
    VideoSource
from twython import Twython

from twsaucenao.api import api
from twsaucenao.config import config
from twsaucenao.errors import TwSauceNoMediaException
from twsaucenao.lang import lang
from twsaucenao.models.database import TRIGGER_MENTION, TRIGGER_MONITORED, TweetCache, TweetSauceCache
from twsaucenao.pixiv import Pixiv
from twsaucenao.sauce import SauceManager
from twsaucenao.twitter import ReplyLine, TweetManager


class TwitterSauce:
    def __init__(self):
        self.log = logging.getLogger(__name__)

        # Tweet Cache Manager
        self.twitter = TweetManager()
        self.twython = Twython(config.get('Twitter', 'consumer_key'), config.get('Twitter', 'consumer_secret'),
                               config.get('Twitter', 'access_token'), config.get('Twitter', 'access_secret'))

        self.anime_link = config.get('SauceNao', 'source_link', fallback='anidb').lower()

        self.nsfw_previews = config.getboolean('TraceMoe', 'nsfw_previews', fallback=False)
        self.failed_responses = config.getboolean('SauceNao', 'respond_to_failed', fallback=True)
        self.ignored_indexes = [int(i) for i in config.get('SauceNao', 'ignored_indexes', fallback='').split(',')]

        # Pixiv
        self.pixiv = Pixiv()

        # Cache some information about ourselves
        self.my = api.me()
        self.log.info(f"Connected as: {self.my.screen_name}")

        # A cached list of ID's for parent posts we've already processed
        # Used in the check_monitored() method to prevent re-posting sauces when posts are re-tweeted
        self._posts_processed = []

        # The ID cutoff, we populate this once via an initial query at startup
        try:
            self.mention_id = tweepy.Cursor(api.mentions_timeline, tweet_mode='extended', count=1).items(1).next().id
        except StopIteration:
            self.mention_id = 0

        try:
            self.self_id = tweepy.Cursor(api.user_timeline, tweet_mode='extended', count=1).items(1).next().id
        except StopIteration:
            self.self_id = 0

        self.monitored_since = {}

    # noinspection PyBroadException
    async def check_self(self) -> None:
        """
        Check for new posts from our own account to process
        Returns:
            None
        """
        self.log.info(f"[{self.my.screen_name}] Retrieving posts since tweet {self.self_id}")
        posts = [*tweepy.Cursor(api.user_timeline, since_id=self.self_id, tweet_mode='extended').items()]

        # Filter tweets without a reply AND attachment
        for tweet in posts:
            try:
                # Update the ID cutoff before attempting to parse the tweet
                self.self_id = max([self.self_id, tweet.id])
                self.log.debug(f"[{self.my.screen_name}] New self-post max ID cutoff: {self.self_id}")

                # Make sure this isn't a retweet
                if tweet.full_text.startswith('RT @'):
                    self.log.debug(f"[{self.my.screen_name}] Skipping a re-tweet")
                    continue

                # Attempt to parse the tweets media content
                original_cache, media_cache, media = self.get_closest_media(tweet, self.my.screen_name)

                # Get the sauce!
                sauce_cache = await self.get_sauce(media_cache, log_index=self.my.screen_name)
                await self.send_reply(tweet_cache=original_cache, media_cache=media_cache, sauce_cache=sauce_cache,
                                      blocked=media_cache.blocked)
            except TwSauceNoMediaException:
                self.log.debug(f"[{self.my.screen_name}] Tweet {tweet.id} has no media to process, ignoring")
                continue
            except Exception as e:
                self.log.exception(f"[{self.my.screen_name}] An unknown error occurred while processing tweet {tweet.id}: {e}")
                continue

    # noinspection PyBroadException
    async def check_mentions(self) -> None:
        """
        Check for any new mentions we need to parse
        Returns:
            None
        """
        self.log.info(f"[{self.my.screen_name}] Retrieving mentions since tweet {self.mention_id}")
        mentions = [*tweepy.Cursor(api.mentions_timeline, since_id=self.mention_id, tweet_mode='extended').items()]

        # Filter tweets without a reply AND attachment
        for tweet in mentions:
            try:
                # Update the ID cutoff before attempting to parse the tweet
                self.mention_id = max([self.mention_id, tweet.id])
                self.log.debug(f"[{self.my.screen_name}] New max ID cutoff: {self.mention_id}")

                # Make sure we aren't mentioning ourselves
                if tweet.author.id == self.my.id:
                    self.log.debug(f"[{self.my.screen_name}] Skipping a self-referencing tweet")
                    continue

                # Attempt to parse the tweets media content
                original_cache, media_cache, media = self.get_closest_media(tweet, self.my.screen_name)
                if media_cache.tweet.author.id == self.my.id:
                    self.log.info("Not performing a sauce lookup to our own tweet")
                    continue

                # Did we request a specific index?
                index = self._determine_requested_index(tweet, media_cache)

                # Get the sauce!
                sauce_cache = await self.get_sauce(media_cache, index_no=index, log_index=self.my.screen_name)
                await self.send_reply(tweet_cache=original_cache, media_cache=media_cache, sauce_cache=sauce_cache,
                                      blocked=media_cache.blocked)
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
                    sauce_cache = await self.get_sauce(media_cache, log_index=account, trigger=TRIGGER_MONITORED)
                    sauce = sauce_cache.sauce

                    self.log.info(f"[{account}] Found {sauce.index} sauce for tweet {tweet.id}" if sauce
                                  else f"[{account}] Failed to find sauce for tweet {tweet.id}")

                    await self.send_reply(tweet_cache=original_cache, media_cache=media_cache, sauce_cache=sauce_cache,
                                          requested=False)
                except TwSauceNoMediaException:
                    self.log.info(f"[{account}] No sauce found for tweet {tweet.id}")
                    continue
                except Exception as e:
                    self.log.exception(f"[{account}] An unknown error occurred while processing tweet {tweet.id}: {e}")
                    continue

    async def get_sauce(self, tweet_cache: TweetCache, index_no: int = 0, log_index: typing.Optional[str] = None,
                        trigger: str = TRIGGER_MENTION) -> TweetSauceCache:
        """
        Get the sauce of a media tweet
        """
        log_index = log_index or 'SYSTEM'

        # Have we cached the sauce already?
        try:
            sauce_manager = SauceManager(tweet_cache, trigger)
            return await sauce_manager.get(index_no)
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
            return sauce_cache

    def get_closest_media(self, tweet, log_index: typing.Optional[str] = None) -> typing.Optional[typing.Tuple[TweetCache, TweetCache, typing.List[str]]]:
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
                    message = lang('Errors', 'blocked', user=tweet.author)
                    self._post(msg=message, to=tweet.id)
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

    async def send_reply(self, tweet_cache: TweetCache, media_cache: TweetCache, sauce_cache: TweetSauceCache,
                         requested: bool = True, blocked: bool = False) -> None:
        """
        Return the source of the image
        Args:
            tweet_cache (TweetCache): The tweet to reply to
            media_cache (TweetCache): The tweet containing media elements
            sauce_cache (Optional[GenericSource]): The sauce found (or None if nothing was found)
            requested (bool): True if the lookup was requested, or False if this is a monitored user account
            blocked (bool): If True, the account posting this has blocked the SauceBot

        Returns:
            None
        """
        tweet = tweet_cache.tweet
        sauce = sauce_cache.sauce

        if sauce and self.ignored_indexes and (int(sauce.index_id) in self.ignored_indexes):
            self.log.info(f"Ignoring result from ignored index ID {sauce.index_id}")
            sauce = None

        if sauce is None:
            if self.failed_responses and requested:
                media = TweetManager.extract_media(media_cache.tweet)
                if not media:
                    return

                yandex_url  = f"https://yandex.com/images/search?url={media[sauce_cache.index_no]}&rpt=imageview"
                ascii_url   = f"https://ascii2d.net/search/url/{media[sauce_cache.index_no]}"
                google_url  = f"https://www.google.com/searchbyimage?image_url={media[sauce_cache.index_no]}&safe=off"

                message = lang('Errors', 'no_results',
                               {'yandex_url': yandex_url, 'ascii_url': ascii_url, 'google_url': google_url},
                               user=tweet.author)
                self._post(msg=message, to=tweet.id)
            return

        # Get the artists Twitter handle if possible
        twitter_sauce = None
        if isinstance(sauce, PixivSource):
            twitter_sauce = self.pixiv.get_author_twitter(sauce.data['member_id'])

        # If we're requesting sauce from the original artist, just say so
        if twitter_sauce and twitter_sauce.lstrip('@').lower() == media_cache.tweet.author.screen_name.lower():
            self.log.info("User requested sauce from a post by the original artist")
            message = lang('Errors', 'sauced_the_artist')
            self._post(message, to=tweet.id)
            return

        # Lines with priority attributes incase we need to shorten them
        lines = []

        # Add additional sauce URL's if available
        sauce_urls = []
        if isinstance(sauce, AnimeSource):
            await sauce.load_ids()

            if self.anime_link in ['myanimelist', 'animal', 'all'] and sauce.mal_url:
                sauce_urls.append(sauce.mal_url)

            if self.anime_link in ['anilist', 'animal', 'all'] and sauce.anilist_url:
                sauce_urls.append(sauce.anilist_url)

            if self.anime_link in ['anidb', 'all']:
                sauce_urls.append(sauce.url)

        # Only add Twitter source URL's for booru's, otherwise we may link to something that angers the Twitter gods
        if isinstance(sauce, BooruSource):
            for url in sauce.urls:
                if 'twitter.com' in url:
                    sauce_urls.append(url)

            if 'twitter.com' in sauce.source_url:
                sauce_urls.append(sauce.source_url)

        # For limiting the length of the title/author
        _repr = reprlib.Repr()
        _repr.maxstring = 32

        # H-Misc doesn't have a source to link to, so we need to try and provide the full title
        if sauce.index not in ['H-Misc', 'E-Hentai', 'H-Anime', 'Mangadex']:
            title = _repr.repr(sauce.title).strip("'")
        else:
            _repr.maxstring = 128
            title = _repr.repr(sauce.title).strip("'")

        # Format the similarity string
        similarity = lang('Accuracy', 'prefix', {'similarity': sauce.similarity})
        if sauce.similarity >= 95:
            similarity = similarity + " " + lang('Accuracy', 'exact')
        elif sauce.similarity >= 85.0:
            similarity = similarity + " " + lang('Accuracy', 'high')
        elif sauce.similarity >= 70.0:
            similarity = similarity + " " + lang('Accuracy', 'medium')
        elif sauce.similarity >= 60.0:
            similarity = similarity + " " + lang('Accuracy', 'low')
        else:
            similarity = similarity + " " + lang('Accuracy', 'very_low')

        if requested:
            if sauce.similarity >= 60.0:
                reply = lang('Results', 'requested_found', {'index': sauce.index}, user=tweet.author) + "\n"
                lines.append(ReplyLine(reply, 1))
            else:
                reply = lang('Results', 'requested_found_low_accuracy', {'index': sauce.index}, user=tweet.author) + "\n"
                lines.append(ReplyLine(reply, 1))
        else:
            if sauce.similarity >= 60.0:
                reply = lang('Results', 'other_found', {'index': sauce.index}, user=tweet.author) + "\n"
                lines.append(ReplyLine(reply, 1))
            else:
                reply = lang('Results', 'other_found_low_accuracy', {'index': sauce.index}, user=tweet.author)
                lines.append(ReplyLine(reply, 1))

        # If it's a Pixiv source, try and get their Twitter handle (this is considered most important and displayed first)
        if twitter_sauce:
            reply = lang('Results', 'twitter', {'twitter': twitter_sauce})
            lines.append(ReplyLine(reply, newlines=1))

        # Print the author name if available
        if sauce.author_name:
            author = _repr.repr(sauce.author_name).strip("'")
            reply = lang('Results', 'author', {'author': author})
            lines.append(ReplyLine(reply, newlines=1))

        # Omit the title for Pixiv results since it's usually always non-romanized Japanese and not very helpful
        if not isinstance(sauce, PixivSource):
            reply = lang('Results', 'title', {'title': title})
            lines.append(ReplyLine(reply, 10, newlines=1))

        # Add the episode number and timestamp for video sources
        if isinstance(sauce, VideoSource) and sauce.episode:
            reply = lang('Results', 'episode', {'episode': sauce.episode})
            if sauce.timestamp:
                reply += " " + lang('Results', 'timestamp', {'timestamp': sauce.timestamp})

            lines.append(ReplyLine(reply, 5, newlines=1))

        # Add character and material info for booru results
        if isinstance(sauce, BooruSource):
            if sauce.material:
                reply = lang('Results', 'material', {'material': sauce.material[0].title()})
                lines.append(ReplyLine(reply, 5, newlines=1))

            if sauce.characters:
                reply = lang('Results', 'character', {'character': sauce.characters[0].title()})
                lines.append(ReplyLine(reply, 4, newlines=1))

        # Add the chapter for manga sources
        if isinstance(sauce, MangaSource) and sauce.chapter:
            reply = lang('Results', 'chapter', {'chapter': sauce.chapter})
            lines.append(ReplyLine(reply, 5, newlines=1))

        # Display our confidence rating
        lines.append(ReplyLine(similarity, 2, newlines=1))

        # Source URL's are not available in some indexes
        if sauce.index not in ['H-Misc', 'H-Anime', 'H-Magazines', 'H-Game CG', 'Mangadex', 'E-Hentai']:
            if sauce_urls:
                reply = "\n".join(sauce_urls)
                lines.append(ReplyLine(reply, newlines=2))
            elif sauce.source_url and not isinstance(sauce, BooruSource):
                lines.append(ReplyLine(sauce.source_url, newlines=2))

        # Try and append bot instructions with monitored posts. This might make our post too long, though.
        if not requested and config.getboolean('Twitter', 'promo_footer', fallback=False):
            promo_footer = lang('Results', 'other_footer')
            if promo_footer:
                lines.append(ReplyLine(promo_footer, 0, newlines=2))
        elif config.getboolean('System', 'display_patreon'):
            lines.append(ReplyLine("Support SauceBot!\nhttps://www.patreon.com/saucebot", 3, newlines=2))

        # trace.moe time! Let's get a video preview if we can
        if sauce_cache.media_id:
            self._post(msg=lines, to=tweet.id, media_ids=[sauce_cache.media_id])
        else:
            self._post(msg=lines, to=tweet.id)

    def _post(self, msg: typing.Union[str, typing.List[ReplyLine]], to: typing.Optional[int], media_ids: typing.Optional[typing.List[int]] = None,
              sensitive: bool = False):
        """
        Perform a twitter API status update
        Args:
            msg (Union[str, List[ReplyLine]]): Message to send
            to (typing.Optional[int]): Status ID we are replying to
            media_ids (typing.Optional[List[int]]): List of media ID's
            sensitive (bool): Whether or not this tweet contains NSFW media

        Returns:

        """
        kwargs = {'possibly_sensitive': sensitive}

        if to:
            kwargs['in_reply_to_status_id'] = to
            kwargs['auto_populate_reply_metadata'] = True

        if media_ids:
            kwargs['media_ids'] = media_ids

        lines = msg if isinstance(msg, list) else None
        if lines:
            msg = ''.join(map(str, lines))

        try:
            return api.update_status(msg, **kwargs)
        except tweepy.error.TweepError as error:
            if error.api_code == 136:
                self.log.warning("A user requested our presence, then blocked us before we could respond. Wow.")
            # We attempted to process a tweet from a user that has restricted access to their account
            elif error.api_code in [179, 385]:
                self.log.info(f"Attempted to reply to a deleted tweet or a tweet we don't have permission to view")
                raise TwSauceNoMediaException
            # Someone got impatient and deleted a tweet before we could get too it
            elif error.api_code == 144:
                self.log.info(f"Not replying to a tweet that no longer exists")
                raise TwSauceNoMediaException
            # Video was too short. Can happen if we're using natural previews. Repost without the video clip
            elif error.api_code == 324:
                self.log.info(f"Video preview for was too short to upload to Twitter")
                return self._post(msg=msg, to=to, sensitive=sensitive)
            # Something unfamiliar happened, log an error for later review
            elif error.api_code == 186 and lines:
                self.log.debug("Post is too long; scrubbing message length")

                def _retry(_lines):
                    _lines = self._shorten_reply(_lines)
                    try:
                        _msg = ''.join(map(str, _lines))
                        return api.update_status(_msg, **kwargs)
                    except tweepy.TweepError as error:
                        if error.api_code != 186:
                            raise error

                        return False

                # Shorten the post as much as we can until it fits
                while True:
                    try:
                        success = _retry(lines)
                    except IndexError:
                        self.log.warning(f"Failed to shorten response message to tweet {to} enough")
                        break

                    if not success:
                        self.log.debug(f"Tweet to {to} still not short enough; running another pass")
                        continue

                    self.log.debug(f"Tweet for {to} shortened successfully")
                    break
            else:
                self.log.error(f"Unable to post due to an unknown Twitter error: {error.api_code} - {error.reason}")

    def _shorten_reply(self, reply_lines: typing.List[ReplyLine]):
        """
        Dynamically shorten a response until it fits within Twitter's 240 character limit
        Args:
            reply_lines (List[ReplyLine]):

        Returns:
            List[ReplyLine]

        Raises:
            IndexError: Impossible to shorten this tweet any further; give up
        """
        min_index, min_value = min(enumerate(reply_lines), key=lambda x: x[1].priority)

        # Nothing else to remove. Should virtually never reach this point.
        if min_value.priority == 100:
            raise IndexError

        reply_lines.pop(min_index)
        return reply_lines

    def _determine_requested_index(self, tweet, media_cache: TweetSauceCache) -> int:
        """
        Determined the requested sauce lookup for multi-image tweets
        """
        media = TweetManager.extract_media(media_cache.tweet)
        request_text = tweet.full_text.lower().strip()

        # If there's only one item, that's all we can return
        if len(media) == 1:
            return 0

        # Right / Left image parsing
        if len(media) == 2:
            if 'right' in request_text:
                self.log.debug("User requested the right image")
                return 1

            if 'left' in request_text:
                self.log.debug("User requested the left image")
                return 0

        if len(media) == 4:
            if 'top left' in request_text:
                self.log.debug("User requested the top left image")
                return 0
            if 'top right' in request_text:
                self.log.debug("User requested the top right image")
                return 1
            if 'bottom left' in request_text:
                self.log.debug("User requested the bottom left image")
                return 2
            if 'bottom right' in request_text:
                self.log.debug("User requested the bottom right image")
                return 3

        # First / last image parsing
        if 'first' in request_text:
            self.log.debug("User requested the first image")
            return 0
        if 'last' in request_text:
            self.log.debug("User requested the last image")
            return len(media) - 1

        # Otherwise, try parsing specific ordinals
        if request_text[-2:] == ' 1':
            self.log.debug("User explicitly requested index 0")
            return 0
        if (request_text[-2:] == ' 2' or 'second' in request_text) and len(media) >= 2:
            self.log.debug("User explicitly requested index 1")
            return 1
        if (request_text[-2:] == ' 3' or 'third' in request_text) and len(media) >= 3:
            self.log.debug("User explicitly requested index 2")
            return 2
        if (request_text[-2:] == ' 4' or 'fourth' in request_text) and len(media) == 4:
            self.log.debug("User explicitly requested index 3")
            return 3

        # Try the last image on 3-image tweets, as the first one is often vertically cropped and not usable
        if len(media) == 3:
            return 2

        return 0
