# -*- coding: utf-8 -*-
# authors: Ethosa, FujiMakoto
import io
from base64 import b64encode
from json import loads
from urllib.parse import urlencode

from aiohttp import ClientSession

from twsaucenao.config import config


class ATraceMoe:

    VIDEO_LARGE = 'l'
    VIDEO_MEDIUM = 'm'
    VIDEO_SMALL = 's'

    def __init__(self, token=""):
        """
        Initialize trace moe API.
        """
        self.api_url = "https://api.trace.moe"
        self.token = token
        self.session = ClientSession(
                headers={
                    "Content-Type": "application/json"
                },
                raise_for_status=True
        )

    async def me(self):
        """
        Gets limit for your IP.

        Returns:
            dict -- server response
        """
        url = f"{self.api_url}/me"

        if self.token:
            url += f"?token={self.token}"

        response = await self.session.get(url)
        return await response.json()

    async def video_preview(self, response, mute=False, size=None):
        video_url = response['result'][0]['video']

        # Append the video size
        size = size or self.VIDEO_LARGE
        video_url += f"&size={size}"

        if mute:
            video_url += "&mute"

        response = await self.session.get(video_url)
        return await response.content.read()

    async def search(self, path, search_filter=0, is_url=False, anilist_id=None):
        """
        Searchs anime by image.

        Arguments:
            path {typing.Union[str, typing.IO]} -- image path, url, or file-like object

        Keyword Arguments:
            is_url {bool} -- use url, if True. (default: {False})

        Returns:
            dict -- server response
        """
        url = f"{self.api_url}/search?"
        args = {}

        if self.token:
            args['token'] = self.token

        # Are we filtering by a specific anilist ID?
        if anilist_id:
            args['anilistID'] = anilist_id

        url += urlencode(args)

        if is_url:
            # # Discord URL's tend to break with trace.moe at the moment
            # if self.DISCORD_IMAGE_URL_RE.match(path):
            #     # Load the image
            #     response = await self.session.get(path, read_until_eof=False)
            #     data = io.BytesIO(await response.read())
            #
            #     # Verify it's a valid image first
            #     image = Image.open(data)
            #     image.verify()
            #     image = Image.open(data)
            #
            #     # If it's an animated gif, we need to extract a frame
            #     if image.is_animated:
            #         data = io.BytesIO()
            #         image.seek(0)
            #         image.save(data, format='PNG')
            #
            #     del image
            #     encoded = b64encode(data.getvalue()).decode("utf-8")
            #     response = await self.session.post(
            #             url, json={"image": encoded, "filter": search_filter}
            #     )
            # else:
            response = await self.session.get(
                url, params={"url": path}
            )
            return loads(await response.text())
        elif isinstance(path, io.BufferedIOBase):
            encoded = b64encode(path.read()).decode("utf-8")
            response = await self.session.post(
                url, json={"image": encoded, "filter": search_filter}
            )
            return loads(await response.text())
        else:
            with open(path, "rb") as f:
                encoded = b64encode(f.read()).decode("utf-8")
            response = await self.session.post(
                url, json={"image": encoded, "filter": search_filter}
            )
            return loads(await response.text())


tracemoe = ATraceMoe(config.get('TraceMoe', 'token', fallback=None))
