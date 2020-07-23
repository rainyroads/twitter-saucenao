import logging
import re
import typing

from pixivpy3 import AppPixivAPI

from twsaucenao.config import config


class Pixiv:
    def __init__(self):
        self.enabled  = config.getboolean('Pixiv', 'enabled', fallback=False)
        self.username = config.get('Pixiv', 'username', fallback=None)
        self._password = config.get('Pixiv', 'password', fallback=None)
        self._log = logging.getLogger(__name__)

        self._pixiv = AppPixivAPI()
        self._pixiv.set_accept_language(config.get('Pixiv', 'language', fallback='en-US'))

        self._re_twitter = re.compile(r'^https?://(www.)?twitter.com/(?P<username>.+)$')

        if self.enabled:
            self._login()

    def _login(self) -> None:
        """
        Authenticate to Pixiv
        Returns:
            None
        """
        self._log.info(f'[PIXIV] Authenticating to Pixiv with the username {self.username}')
        try:
            self._pixiv.login(self.username, self._password)
        except Exception as error:
            self._log.exception("[PIXIV] Failed to authenticate to Pixiv", exc_info=error)

    def get_illust(self, illust_id: int) -> typing.Optional[dict]:
        """
        Look up the provided illustration ID from SauceNao
        Args:
            illust_id (int):

        Returns:
            typing.Optional[dict]
        """
        if not self.enabled:
            return None

        illust = self._pixiv.illust_detail(illust_id)
        if 'error' in illust and 'invalid_grant' in illust['error']['message']:
            self._log.info(f'Re-Authenticating to Pixiv with the username {self.username}')
            self._login()
            illust = self._pixiv.illust_detail(illust_id)

        return illust['illust'] if illust and 'illust' in illust else None

    def get_author(self, author_id: int) -> typing.Optional[dict]:
        """
        Get the author for the specified illustration
        Args:
            author_id (int):

        Returns:
            typing.Optional[dict]
        """
        if not self.enabled:
            return None

        user = self._pixiv.user_detail(author_id)
        if 'error' in user and 'invalid_grant' in user['error']['message']:
            self._log.info(f'Re-Authenticating to Pixiv with the username {self.username}')
            self._login()
            user = self._pixiv.user_detail(author_id)

        return user

    def get_author_twitter(self, author_id: int) -> typing.Optional[str]:
        """
        Get the Pixiv artists Twitter page, if available
        Args:
            author_id (int):

        Returns:
            typing.Optional[str]
        """
        if not self.enabled:
            return None

        user = self.get_author(author_id)

        twitter_url = user['profile']['twitter_url'] if (user and 'profile' in user) else None
        if twitter_url:
            match = self._re_twitter.match(twitter_url)
            if match and match.group('username'):
                return f"@{match.group('username')}"

