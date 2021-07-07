![sauce-chan](https://i.imgur.com/9L4zCM7.png)

# twitter-saucenao

[![GitHub commits since latest release (by date)](https://img.shields.io/github/commits-since/fujimakoto/twitter-saucenao/latest)](https://github.com/FujiMakoto/twitter-saucenao/releases) [![Lines of Code](https://sonarcloud.io/api/project_badges/measure?project=FujiMakoto_twitter-saucenao&metric=ncloc)](https://sonarcloud.io/dashboard?id=FujiMakoto_twitter-saucenao) [![Maintainability Rating](https://sonarcloud.io/api/project_badges/measure?project=FujiMakoto_twitter-saucenao&metric=sqale_rating)](https://sonarcloud.io/dashboard?id=FujiMakoto_twitter-saucenao) [![Codacy Badge](https://app.codacy.com/project/badge/Grade/b544d5da65234268a434f05797bc5680)](https://www.codacy.com/manual/makoto-github/twitter-saucenao?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=FujiMakoto/twitter-saucenao&amp;utm_campaign=Badge_Grade)

An open-source Twitter bot that utilizes the SauceNao API to find the source of images or anime screencaps.
https://saucenao.com/

# Official Twitter account

Support for the official saucenaopls Twitter account has been discontinued. Twitter in general is a horrible platform and additionally provides no way to scale bots that need more than 2,400 tweets/day. I've tried to work around this repeatedly to no avail. Working on this bot has additionally netted me almost nothing but constant harassment, so I'm no longer interested in maintaining the public-facing Twitter bot.

## (05/11/2021) Shadowbans and DMCA abuse

Twitter has recently engaged in shadowbanning the SauceNaoPls account in response to us actively working to expose Twitter's broken and abusive copyright system.

It seems rather than deal with the rampant abuse, Twitter has decided it’s easier to silently censor the one bot on the platform that tries to credit artists.

At the moment, many legitimate artist accounts are being closed because of false/malicious copyright complaints by bad actors attempting to blackmail these people into paying them to regain access to their account.

Examples:

* https://twitter.com/yueko___/status/1391474502186377217
* https://twitter.com/RyaiArt/status/1364745241350316032
* https://twitter.com/JackaryDraws/status/1390374876205174789
* https://twitter.com/orangesekai1/status/1394725794413387777

Archives:

* https://archive.is/0WkQf
* https://archive.is/9p6Jq
* https://archive.is/jQIQm
* https://archive.is/ridon

Legitimate artist accounts are being closed with only a handful of false DMCA complaints being filed against them.

At the same time, Twitter is actively refusing to take action against accounts which only exist to steal other people’s
art and try to profit off it.

Our hands-on experience shows legitimate artists trying to protect their own intellectual property must file up to **30
or more** separate DMCA reports against actual bad actors to get any action taken.

On top of all this, as soon as we started offering a service to help these artists submit takedowns against art thieves,
Twitter placed a shadowban on our account in an attempt to prevent us from maintaining contact with these artists.

Lastly, I have recently been able to show Twitter's copyright department (a department dedicated entirely to enforcing U.S. laws) is actually outsourced to some unknown third-party in India. This can be shown by using a link tracking service when submitting a takedown notice to Twitter.

![Copyright IP](https://i.imgur.com/jon9ETa.png)

When you consider all the above, and also consider it was not long ago that some bad actors in Twitter managed to hijack a bunch of verified Twittter accounts in an attempt to push a Bitcoin scam, I wouldn't rule out the possibility of the current DMCA extortion scam being run by a group inside Twitter as well.

**If you are an artist and you have been falsely banned by Twitter over malicious DMCA strikes, please contact me on here. I will do everything in my power to help you recover your account without needing to expose your personal information to any nefarious parties attempting to extort you.**

A permanent archive of the original Tweet thread calling this out can be found below. If you can't see the full thread in the top link, that means Twitter has shadowbanned the account again.

* https://twitter.com/saucenaopls/status/1392138133735620608
* https://archive.is/koEIR (archive)


# Documentation

Setting up your own instance of the Twitter SauceNao bot is pretty straightforward. All you need to do is copy the
example configuration file, [**
config.example.ini**](https://github.com/FujiMakoto/twitter-saucenao/blob/master/config.example.ini), to **config.ini**,
then set the configuration variables accordingly.

### Getting started

* [Installation](https://github.com/FujiMakoto/twitter-saucenao/wiki/Installation)
* [Configuration](https://github.com/FujiMakoto/twitter-saucenao/wiki/Configuration)

### Additional information

For more information on the bot project, please refer to the GitHub's Wiki page here:

https://github.com/FujiMakoto/twitter-saucenao/wiki

# Closing remarks

I hope you have found this project useful. All the major credit really goes to the SauceNao website and service, which
allows the bot to operate.

### Supporters

![Sentry](./sentry.svg)

We happily utilize Sentry for all our production error logging and debugging needs as
a [sponsored](https://sentry.io/for/good/) open-source project!

### Patreons

Thank you so much to all of our supporters on [Patreon](https://www.patreon.com/saucebot)! It means a lot to me that you
believe in this project enough to help fund it.

#### Main Characters ($6)

* Part

#### Supporting Characters ($3)

* Tamschi
* Justin Whang
* Joe Young
* SUZUSHIIRO
* Compsense
* JL
* Migi
