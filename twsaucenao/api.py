import logging

import tweepy

from twsaucenao.config import config

logger = logging.getLogger(__name__)


def _twitter_api(key: str, secret: str, token: str, token_secret: str):
    """
    Establish a tweepy API instance
    Args:
        key (str): The consumer key
        secret (str): The consumer secret
        token (str): The access token
        token_secret (str): The access token secret

    Returns:
        tweepy.api.API
    """
    auth = tweepy.OAuthHandler(key, secret)
    auth.set_access_token(token, token_secret)
    _api = tweepy.API(auth, wait_on_rate_limit=True, wait_on_rate_limit_notify=True)

    try:
        _api.verify_credentials()
    except Exception as e:
        logger.critical("Error loading API", exc_info=True)
        raise e
    logger.info("Twitter API ready")
    return _api


api = _twitter_api(config.get('Twitter', 'consumer_key'), config.get('Twitter', 'consumer_secret'),
                   config.get('Twitter', 'access_token'), config.get('Twitter', 'access_secret'))


if config.has_section('TwitterReadOnly'):
    readonly_api = _twitter_api(config.get('TwitterReadOnly', 'consumer_key'),
                                config.get('TwitterReadOnly', 'consumer_secret'),
                                config.get('TwitterReadOnly', 'access_token'),
                                config.get('TwitterReadOnly', 'access_secret'))
else:
    readonly_api = None

