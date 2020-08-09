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

## Art thieves SauceBot has been blocked by
Unfortunately, despite my best efforts to keep the bot as unobtrusive and non-spammy as possible, some people on Twitter simply naturally hate the prospect of giving the original artists credit because they don't want to share the attention they receive.

This post offers some insight into the mindsets of people like this,

https://twitter.com/_kairy_draws_/status/1276653871448961028

Here is a list of Twitter accounts that have blocked the official @saucenaopls bot for crediting artwork they've reposted.

* @AnimeDeltaa (Blocked 08/03/2020) (NSFW)
* @AnimeHentaiFans (Blocked 07/08/2020) (NSFW)
* @LewdRealm (Re-blocked 07/28/2020) (NSFW)
* @WaifuSupply (Re-blocked 07/28/2020)
* @lfredohentai (Blocked 07/21/2020) (NSFW)
* @PrincessKeriana (Blocked 07/08/2020) (NSFW)
* @Yumi69x2 (Blocked 06/29/2020) (NSFW)
* @love_image__H (Blocked 06/30/2020) (NSFW)
* @Tomo_Yamanobe_ (Blocked 07/28/2020) (NSFW)
* @DreaMGGAMING (Blocked 07/03/2020) (NSFW)
* @iJaIter (Blocked 06/30/2020)

You can still mention me in the comments of these posts and I can reply to you regardless, this list is compiled more for transparency reasons and to call out are thieves who do not provide acceptable credit for the artwork their accounts repost.

**Additionally, please be aware that attempting to block SauceBot may result in the bot automatically contacting the original artists with DMCA takedown instructions for your posts.**

Providing artists with credit is not something we believe should be considered optional. Furthermore, attempting to deny original artists credit is toxic behavior we believe should be combated. We will always work to provide original artists the credit they are entitled to. If you try and deny users the right to know the source of artwork you are reposting, we will name and shame you.

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
