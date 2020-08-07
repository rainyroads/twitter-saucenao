import io
import logging
import os
from typing import *

import typing

import aiohttp
from pysaucenao import GenericSource, SauceNao, AnimeSource

from twsaucenao.config import config
from twsaucenao.models.database import TweetCache, TweetSauceCache
from twsaucenao.tracemoe import tracemoe
from twsaucenao.twitter import TweetManager


class SauceManager:
    def __init__(self, media_tweet: TweetCache):
        self._log = logging.getLogger(__name__)
        self.tweet = media_tweet
        self.media = TweetManager.extract_media(media_tweet) or []

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

        self._sauce_cache = []

        self._file_handler = None

    def _get_sauce(self, index: int) -> Optional[GenericSource]:
        cache = TweetSauceCache.fetch(self.tweet.tweet_id, index)
        if not cache.sauce:
            return None, None

    async def _download_media(self, media_url: str) -> typing.Optional[typing.BinaryIO]:
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

            return io.BytesIO(image)
        except aiohttp.ClientTimeout:
            self._log.warning("Connection timed out while trying to download image from twitter")
        except aiohttp.ClientError:
            self._log.exception("An error occurred while trying to download an image from Twitter")

    async def _video_preview(self, sauce: AnimeSource, path_or_fh: Union[str, typing.BinaryIO], is_url: bool) -> Optional[dict]:
        if not tracemoe:
            return None

        try:
            tracemoe_sauce = await tracemoe.search(path_or_fh, is_url=is_url)
        except Exception:
            self._log.warning("Tracemoe returned an exception, aborting search query")
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

    def __index__(self):
        pass

    def __getitem__(self, item):
        try:
            return self._sauce_cache[item]
        except IndexError:
            self._sauce_cache[item] = self._get_sauce(item)
            return self._sauce_cache[item]