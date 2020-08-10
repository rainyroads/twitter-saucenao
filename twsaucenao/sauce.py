import io
import logging
import typing

import aiohttp
import twython
from pysaucenao import AnimeSource, SauceNao
from twython import Twython

from twsaucenao.config import config
from twsaucenao.models.database import TRIGGER_SELF, TweetCache, TweetSauceCache
from twsaucenao.tracemoe import tracemoe
from twsaucenao.twitter import TweetManager


class SauceManager:
    def __init__(self, media_tweet: TweetCache, trigger: str = TRIGGER_SELF):
        self._log = logging.getLogger(__name__)
        self._trigger = trigger
        self.tweet_cache = media_tweet
        self.media = TweetManager.extract_media(media_tweet.tweet) or []
        self._downloads_enabled = config.getboolean('SauceNao', 'download_files', fallback=False)
        self._previews_enabled = config.getboolean('TraceMoe', 'enabled', fallback=False)

        # SauceNao
        self.minsim_mentioned = float(config.get('SauceNao', 'min_similarity_mentioned', fallback=50.0))
        self.minsim_monitored = float(config.get('SauceNao', 'min_similarity_monitored', fallback=65.0))
        self.minsim_searching = float(config.get('SauceNao', 'min_similarity_searching', fallback=70.0))
        self.persistent = config.getboolean('Twitter', 'enable_persistence', fallback=False)
        self.anime_link = config.get('SauceNao', 'source_link', fallback='anidb').lower()
        self.sauce = SauceNao(
                api_key=config.get('SauceNao', 'api_key', fallback=None),
                min_similarity=min(self.minsim_mentioned, self.minsim_monitored, self.minsim_searching),
                priority=[21, 22, 5]
        )

        # Twython
        self.twython = Twython(config.get('Twitter', 'consumer_key'), config.get('Twitter', 'consumer_secret'),
                               config.get('Twitter', 'access_token'), config.get('Twitter', 'access_secret'))

        self._sauce_cache = {}

    async def get(self, index: int):
        try:
            return self._sauce_cache[index]
        except KeyError:
            self._sauce_cache[index] = await self._get_sauce(index)
            return self._sauce_cache[index]

    async def _get_sauce(self, index: int) -> typing.Optional[TweetSauceCache]:
        cache = TweetSauceCache.fetch(self.tweet_cache.tweet_id, index)
        if cache:
            return cache

        media = TweetManager.extract_media(self.tweet_cache.tweet)[index]

        file = media
        if self._downloads_enabled:
            file = await self._download_media(media)

        if self._downloads_enabled:
            sauce_results = await self.sauce.from_file(io.BytesIO(file))
            self._log.info(f"Performing saucenao lookup via file upload")
        else:
            self._log.info(f"Performing saucenao lookup via URL {file}")
            sauce_results = await self.sauce.from_url(file)

        # No results?
        if not sauce_results:
            sauce_cache = TweetSauceCache.set(self.tweet_cache, sauce_results, index, self._trigger)
            return sauce_cache

        best_result = sauce_results[0]

        # Attempt to download a video preview, if it's an anime result
        video_preview = None
        if self._previews_enabled and isinstance(best_result, AnimeSource):
            file = io.BytesIO(file) if self._downloads_enabled else file
            is_url = not self._downloads_enabled
            video_preview = await self._video_preview(best_result, file, is_url)

        # If we have a video preview, upload it now!
        media_id = None
        if video_preview:
            video_preview = io.BytesIO(video_preview)
            media_id = await self._upload_video(video_preview)

        return TweetSauceCache.set(self.tweet_cache, sauce_results, index, self._trigger, media_id)

    async def _download_media(self, media_url: str) -> typing.Optional[bytes]:
        """
        Attempt to download an image from twitter and return a BytesIO object
        """
        try:
            self._log.debug(f"Downloading image from Twitter: " + media_url)
            async with aiohttp.ClientSession(raise_for_status=True) as session:
                try:
                    async with await session.get(media_url) as response:
                        image = await response.read()
                        if not image:
                            self._log.error(f"Empty file received from Twitter")
                            return None
                except aiohttp.ClientResponseError as error:
                    self._log.warning(f"Twitter returned a {error.status} error when downloading {media_url}")
                    return None

            return image
        except aiohttp.ClientTimeout:
            self._log.warning("Connection timed out while trying to download image from twitter")
        except aiohttp.ClientError:
            self._log.exception("An error occurred while trying to download an image from Twitter")

    async def _video_preview(self, sauce: AnimeSource, path_or_fh: typing.Union[str, typing.BinaryIO],
                             is_url: bool) -> typing.Optional[bytes]:
        if not tracemoe:
            return None

        try:
            tracemoe_sauce = await tracemoe.search(path_or_fh, is_url=is_url)
        except Exception:
            self._log.exception("Tracemoe returned an exception, aborting search query")
            return None
        if not tracemoe_sauce.get('docs'):
            self._log.info("Tracemoe returned no results")
            return None

        # Make sure our search results match
        if await sauce.load_ids():
            if sauce.anilist_id != tracemoe_sauce['docs'][0]['anilist_id']:
                self._log.info(f"saucenao and trace.moe provided mismatched anilist entries: `{sauce.anilist_id}` vs. `{tracemoe_sauce['docs'][0]['anilist_id']}`")
                return None

            self._log.info(f'Downloading video preview for AniList entry {sauce.anilist_id} from trace.moe')
            tracemoe_preview = await tracemoe.video_preview_natural(tracemoe_sauce)
            return tracemoe_preview

        return None

    async def _upload_video(self, media: io.BytesIO) -> typing.Optional[int]:
        """
        Upload a video to Twitter and return the media ID for embedding
        """
        try:
            tw_response = self.twython.upload_video(media=media, media_type='video/mp4')
            return int(tw_response['media_id'])
        except twython.exceptions.TwythonError as error:
            self._log.error(f"An error occurred while uploading a video preview: {error.msg}")
