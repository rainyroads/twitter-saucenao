import logging

import tweepy

from twsaucenao.config import config

logger = logging.getLogger(__name__)


def twitter_api():
    consumer_key        = config.get('Twitter', 'consumer_key')
    consumer_secret     = config.get('Twitter', 'consumer_secret')
    access_token        = config.get('Twitter', 'access_token')
    access_token_secret = config.get('Twitter', 'access_secret')

    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)
    api = tweepy.API(auth, wait_on_rate_limit=True, wait_on_rate_limit_notify=True)

    try:
        api.verify_credentials()
    except Exception as e:
        logger.critical("Error loading API", exc_info=True)
        raise e
    logger.info("Twitter API ready")
    return api


def twitter_readonly_api():
    consumer_key        = config.get('TwitterReadOnly', 'consumer_key')
    consumer_secret     = config.get('TwitterReadOnly', 'consumer_secret')
    access_token        = config.get('TwitterReadOnly', 'access_token')
    access_token_secret = config.get('TwitterReadOnly', 'access_secret')

    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)
    api = tweepy.API(auth, wait_on_rate_limit=True, wait_on_rate_limit_notify=True)

    try:
        api.verify_credentials()
    except Exception as e:
        logger.critical("Error loading API", exc_info=True)
        raise e
    logger.info("Twitter API ready")
    return api
