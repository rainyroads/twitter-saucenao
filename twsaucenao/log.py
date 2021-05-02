# Set up logging
import logging

import sentry_sdk

from twsaucenao.config import config

logLevel = getattr(logging, str(config.get('System', 'log_level', fallback='ERROR')).upper())
logFormat = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", "%Y-%m-%d %H:%M:%S")

log = logging.getLogger('twsaucenao')
log.setLevel(logLevel)

ch = logging.StreamHandler()
ch.setLevel(logLevel)
ch.setFormatter(logFormat)

log.addHandler(ch)


# Unless you're running your own custom fork of saucebot, you probably don't need this.
if config.has_option('System', 'sentry_logging') and config.getboolean('System', 'sentry_logging'):
    sentry_sdk.init(config.get('System', 'sentry_dsn'), traces_sample_rate=0.25)