# twitter-saucenao
[![Twitter Follow](https://img.shields.io/twitter/follow/saucenaopls)](https://twitter.com/saucenaopls) [![GitHub](https://img.shields.io/github/license/FujiMakoto/twitter-saucenao)](https://github.com/FujiMakoto/twitter-saucenao/blob/master/LICENSE) [![GitHub release (latest by date)](https://img.shields.io/github/v/release/fujimakoto/twitter-saucenao)](https://github.com/FujiMakoto/twitter-saucenao/releases) [![GitHub commits since latest release (by date)](https://img.shields.io/github/commits-since/fujimakoto/twitter-saucenao/latest)](https://github.com/FujiMakoto/twitter-saucenao/releases)

An open-source Twitter bot that utilizes the SauceNao API to find the source of images or anime screencaps.
https://saucenao.com/

# Official @saucenaopls account
The official account for this Twitter bot can be found here:
https://twitter.com/saucenaopls

## Officially monitored accounts
These accounts are currently monitored by saucenaopls on Twitter. If you’d like to have your account monitored so I can provide automatic sauce lookups for you, just send me a DM on twitter or open an issue here and I’ll add you! No compensation is required, but a shoutout to the bot project is appreciated!

* [@MeguminBot_](https://twitter.com/MeguminBot_) (Officially endorsed)
* [@WaifuAesthetic](https://twitter.com/WaifuAesthetic) (Officially endorsed)
* @WaifuMenu (Unofficial)
* @Kawaii_TL (Unofficial)
* @TweetingWaifus (Unofficial)
* @Mangadoujins (Unofficial)
* @empire_hentai (Unofficial)
* @animesview (Unofficial)

## Blocked by
Unfortunately, despite my best efforts to keep the bot as unobtrusive and non-spammy as possible, some people on Twitter simply naturally hate the prospect of giving the original artists credit whatsoever.

Why? I honestly don’t know! I’m afraid I don’t understand the mindset of these people either.

Here is a list of Twitter accounts that have blocked the official @saucenaopls bot. Unfortunately, this means the official bot cannot respond to any inquiries on posts made by these accounts. You can still have your own bot track these accounts, but they’re likely to block you as well!

* @LewdRealm (Blocked 05/27/2020)
* @WaifuSupply (Blocked 05/28/2020)
* @WaifuMenu (Blocked 06/23/2020)
* @PinketteLoser (Blocked 06/20/2020)

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

### Monitoring accounts
If you want to use the bot to monitor your own account(s) and provide the sauce of things you post automatically, you can use the **monitored_accounts** configuration variable.

This is a comma-separated lists of accounts to monitor.

**Keep in mind you cannot monitor the bots own account.** If you want to monitor an account you operate, you will need to set up a separate bot account.

If you want to monitor another account on Twitter, please be sure someone else is not already actively doing the same. We don’t want to spam people with duplicate sauce lookups. Be courteous!

# Closing remarks
That’s about it! I hope you have found this project useful. All the major credit really goes to the SauceNao website and service, which allows the bot to operate.
