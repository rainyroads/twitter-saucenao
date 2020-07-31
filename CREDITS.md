# Credits

SauceBot is only possible because of these awesome people and services, so if you've found the bot useful, be sure to send them your love and support!

## SauceNao

The primary powerhouse for the bot. Without SauceNao, SauceBot simply wouldn't exist.

* **Website:** https://saucenao.com/
* **Twitter:** https://twitter.com/SauceNAO
* **API:** https://saucenao.com/user.php?page=search-api

## trace.moe

A recent addition to SauceBot; trace.moe is the service that powers the new video previews the bot provides with anime sources. Service wise, it's a bit similar to SauceNAO, but runs off different algorithms and is explicitly for anime.

* **Website:** https://trace.moe/
* **Twitter:** https://twitter.com/soruly
* **API:** https://soruly.github.io/trace.moe/#/

## yuna.moe

Yuna is primarily a desktop application for managing your anime lists and watching anime all in one place, but they also provide a very useful API that allows us to map AniDB entries to other sources, such as AniList and MyAnimeList seamlessly. This is how we now provide links to AniList and MyAnimeList on sauce requests, instead of just being limited to AniDB.

* **Website:** https://yuna.moe/
* **API:** https://relations.yuna.moe/

## PixivPy

PixivPy is the library SauceBot uses to pull information from Pixiv artists as needed. In short, when SauceNao finds an artist on Pixiv, we use PixivPy to scrape their profile page and find out if they have a Twitter handle associated with it. If they do, we then link to their twitter page when crediting them as well!

* **Github:** https://github.com/upbit/pixivpy

## Other libraries

A list of any other libraries SauceBot uses can be found in our requirements.txt file,

https://github.com/FujiMakoto/twitter-saucenao/blob/master/requirements.txt
