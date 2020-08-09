![sauce-chan](https://i.imgur.com/9L4zCM7.png)

# twitter-saucenao
[![Twitter Follow](https://img.shields.io/twitter/follow/saucenaopls)](https://twitter.com/saucenaopls) [![GitHub](https://img.shields.io/github/license/FujiMakoto/twitter-saucenao)](https://github.com/FujiMakoto/twitter-saucenao/blob/master/LICENSE) [![GitHub release (latest by date)](https://img.shields.io/github/v/release/fujimakoto/twitter-saucenao)](https://github.com/FujiMakoto/twitter-saucenao/releases) [![GitHub commits since latest release (by date)](https://img.shields.io/github/commits-since/fujimakoto/twitter-saucenao/latest)](https://github.com/FujiMakoto/twitter-saucenao/releases)

An open-source Twitter bot that utilizes the SauceNao API to find the source of images or anime screencaps.
https://saucenao.com/

# Official @saucenaopls account
The official account for this Twitter bot can be found here: [@SauceNaoPls](https://twitter.com/saucenaopls)

## Officially monitored accounts
These accounts are currently monitored by saucenaopls on Twitter. If you’d like to have your account monitored so I can provide automatic sauce lookups for you, just open an issue here and I’ll add you! No compensation is required, but a shoutout to the bot project is appreciated!

* [@MeguminBot_](https://twitter.com/MeguminBot_) (Officially endorsed)
* [@WaifuAesthetic](https://twitter.com/WaifuAesthetic) (Officially endorsed)
* [@DDOAnime](https://twitter.com/DDOAnime) (Officially endorsed)

# Documentation
Setting up your own instance of the Twitter SauceNao bot is pretty straightforward. All you need to do is copy the example configuration file, [**config.example.ini**](https://github.com/FujiMakoto/twitter-saucenao/blob/master/config.example.ini), to **config.ini**, then set the configuration variables accordingly.

## Configuration
The first and more important thing you need to do is to set up a dedicated Twitter account and application for your bot.

### Registering an application
Once you’ve registered an account for the bot, you can register an application here:

https://developer.twitter.com/en/apps

Keep in mind you may need to go through an application reviewal process with Twitter first, which could take a few days.

Once you’ve got this set up, you can find all the keys and tokens needed in the config.ini file from your application page.

This is all you really need to get started, assuming you just want to function as a standard bot that replies to mentions.

### Registering a SauceNAO API key
This is not required to get the bot up and running, but if you do not specify an API key, the bot will be limited to 100 API queries per-day.

Freely registered accounts have a limit of 200 per day, and SauceNAO supporters have a limit of 5000 queries per day.

You can register for an API key here:

https://saucenao.com/user.php?page=search-api

Then add the following to your config.ini,

```ini
[SauceNao]
api_key: YOUR_API_KEY_HERE
```

### Additional configuration
Want to customize the bot further? Refer to the Configuration page in the Wiki for a detailed overview of the bots configuration settings!

https://github.com/FujiMakoto/twitter-saucenao/wiki/Configuration

# Closing remarks
That’s about it! I hope you have found this project useful. All the major credit really goes to the SauceNao website and service, which allows the bot to operate.

### Supporters

Thank you so much to all of our supporters on [Patreon](https://www.patreon.com/saucebot)! It means a lot to me that you believe in this project enough to help fund it.

#### Waifus / Husbandos ($15+)

* Spina97

#### Main Characters ($6)

* James P Harris
* Karter
* Part
* Patrick Swasey

#### Supporting Characters ($3)

* Caleb Dron
* Edward Simmons
* Izu
* JL
* Josiah Wolf
* Justin Whang
* Migi
* NeonTaeh
* Nyabe
* Russel
* SUZUSHIIRO
* Sergio Juarez
* Tamschi
* Ulysses Duckler
* jclc
