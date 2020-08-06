import logging
import os
import random
import typing
from configparser import ConfigParser

import tweepy

from twsaucenao.config import config

# Set up localization for use elsewhere in the application
_language = config.get('System', 'Language', fallback='english')
_language_config = ConfigParser()
_language_config.read(os.path.join('lang', f'{_language}.ini'), 'utf-8')


def lang(category: str, key: str, replacements: typing.Optional[dict] = None, default=None,
         user: typing.Optional[tweepy.models.User] = None):
    """
    Provides easy to use application localization in the form of ini configuration files

    Language strings can be added or altered in the data/lang folder
    """
    string = _language_config.get(category, key, fallback=default)  # type: str
    if string:
        if replacements:
            for rkey, rvalue in replacements.items():
                string = string.replace(f"{{{rkey}}}", str(rvalue))

        if user:
            string = _member_replacements(string, user)

    else:
        logging.getLogger(__name__).warning(f"Missing {_language} language string: {key} ({category})")
        return '<Missing language string>'

    return string


def rand_lang(category: str, replacements: typing.Optional[dict] = None, default=None,
              user: typing.Optional[tweepy.models.User] = None):
    """
    An alternative to the regular lang() method that pulls a random language string from the specified category
    """
    strings = _language_config.items(category)
    if strings:
        key, string = random.choice(strings)
    else:
        if default:
            key, string = None, default
        else:
            logging.getLogger(__name__).warning(f"Missing {_language} language category: {category}")
            return '<Missing language string>'

    if replacements:
        for rkey, rvalue in replacements.items():
            string = string.replace(f"{{{rkey}}}", rvalue)

    if user:
        string = _member_replacements(string, user)

    return string


# noinspection PyUnresolvedReferences
def _member_replacements(string: str, user: tweepy.models.User) -> str:
    """
    Perform some standard replacements for language strings
    """
    string = string.replace('{display_name}', user.name)
    string = string.replace('{mention}', f'@{user.screen_name}')

    return string
