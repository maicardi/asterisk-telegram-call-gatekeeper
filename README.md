# Asterisk Telegram Call Gatekeeper

Asterisk Telegram Call Gatekeeper is a small Raspberry Pi / Asterisk project for calls forwarded to a SIP/VoIP number.

It can:

- receive a forwarded call on an Asterisk SIP trunk;
- send Telegram notifications with caller name resolution;
- play early-media prompts without `Answer()`;
- selectively answer and record voicemail;
- normalize voicemail volume before sending it to Telegram;
- manage VIP, amore, famiglia and blacklist lists;
- save shared Telegram contacts into a local phonebook;
- classify shared contacts using inline Telegram buttons: normal, VIP, amore, famiglia or blacklist;
- display contact names next to numbers in lists;
- use different audio prompts for each category;
- upload new prompt audio files through Telegram;
- control behaviour from a Telegram bot with inline buttons.

The project was built for a Raspberry Pi running Raspberry Pi OS / Debian 12 with a SIP trunk reachable over IPv6, but it is not tied to one provider.

## Important warnings

Telephony behaviour depends heavily on your SIP provider and mobile operator.

- `Answer()` answers the call and can generate call charges.
- `Progress()` + `Playback(...,noanswer)` uses SIP early media; some operators pass it, some do not.
- `Hangup(17)` usually maps to busy / `486 Busy Here`.
- `Hangup(21)` usually maps to rejected / forbidden.
- Some providers do not pass `Diversion` or `History-Info`, so Asterisk may not know which original line forwarded the call or why the call was forwarded.
- Do not publish real bot tokens, SIP passwords, chat IDs, private phone numbers or contact lists.

## Repository layout

```text
.
├── README.md
├── LICENSE
├── install.sh
├── bot/
│   └── telegram_asterisk_control.py
├── scripts/
│   ├── asterisk_decidi_azione.sh
│   ├── notifica_chiamata_telegram.sh
│   ├── invia_voicemail_telegram.sh
│   ├── lookup_contatto.sh
│   └── importa_google_contacts_csv.py
├── etc/
│   ├── extensions.conf.example
│   └── pjsip.conf.example
├── config/
│   ├── state.env.example
│   ├── contacts.tsv.example
│   ├── vip.txt.example
│   ├── amore.txt.example
│   ├── famiglia.txt.example
│   └── blacklist.txt.example
├── systemd/
│   └── telegram-asterisk-control.service
└── docs/
    └── dialplan-notes.md
```

## 1. Install Asterisk on Raspberry Pi OS / Debian 12

Raspberry Pi OS Bookworm / Debian 12 may not always provide an installable `asterisk` package through `apt`, depending on architecture and repositories. This guide uses Asterisk from source.

### Install build dependencies

```bash
sudo apt update
sudo apt install -y \
  build-essential wget curl git subversion pkg-config \
  libedit-dev libjansson-dev libxml2-dev uuid-dev \
  libsqlite3-dev libssl-dev libncurses-dev libnewt-dev \
  libcurl4-openssl-dev libspeexdsp-dev libogg-dev libvorbis-dev \
  libasound2-dev sox ffmpeg jq tcpdump
```

### Download and build Asterisk

```bash
cd /usr/src
sudo wget https://downloads.asterisk.org/pub/telephony/asterisk/asterisk-22-current.tar.gz
sudo tar xzf asterisk-22-current.tar.gz
cd asterisk-22.*/
```

Run prerequisite script and configure:

```bash
sudo contrib/scripts/install_prereq install
sudo ./configure
sudo make menuselect
```

In `menuselect`, make sure these are enabled:

```text
res_pjsip
res_pjsip_outbound_registration
res_pjsip_endpoint_identifier_ip
chan_pjsip
codec_alaw
codec_ulaw
app_playback
app_record
app_system
```

You do not need `format_mp3` for this project. If `make install` later fails on `format_mp3.so`, disable `format_mp3` in `menuselect`.

Compile and install:

```bash
sudo make -j"$(nproc)"
sudo make install
sudo make samples
sudo make config
sudo ldconfig
```

Start Asterisk:

```bash
sudo systemctl enable --now asterisk
sudo systemctl status asterisk --no-pager
sudo asterisk -rvvv
```

If systemd says `asterisk.service is not a native service`, that is normal for an Asterisk source install using SysV compatibility.

## 2. Verify IPv6 and SIP reachability

For IPv6 SIP trunks, verify IPv6 before configuring Asterisk:

```bash
ip -6 addr
ip -6 route
ping -6 -c 3 2606:4700:4700::1111
```

For your SIP provider, verify DNS and reachability:

```bash
getent ahostsv6 SIP_PROXY_HOSTNAME
ping -6 -c 3 SIP_PROXY_HOSTNAME
```

## 3. Configure PJSIP

Use `etc/pjsip.conf.example` as a template.

Copy or merge it into:

```bash
sudo nano /etc/asterisk/pjsip.conf
```

Then reload or restart Asterisk:

```bash
sudo systemctl restart asterisk
sudo asterisk -rx "pjsip show registrations"
sudo asterisk -rx "pjsip show endpoints"
sudo asterisk -rx "pjsip show transports"
```

You want the registration to show `Registered`.

## 4. Configure the dialplan

Append `etc/extensions.conf.example` to:

```bash
sudo nano /etc/asterisk/extensions.conf
```

Reload:

```bash
sudo asterisk -rx "dialplan reload"
sudo asterisk -rx "dialplan show from-iliad"
```

The context name is `from-iliad` because this project was born from an Iliad setup. You can rename it if your PJSIP endpoint uses a different context.

Important: do not filter the `PROMPT` variable in the dialplan. Prompt filenames may contain dashes, such as `segreteria-famiglia`.

## 5. Install the bot and helper scripts

Clone/copy the repository onto the Raspberry, then from the repository directory:

```bash
sudo ./install.sh
```

Then edit these files and insert real values:

```bash
sudo nano /usr/local/bin/telegram_asterisk_control.py
sudo nano /usr/local/bin/notifica_chiamata_telegram.sh
sudo nano /usr/local/bin/invia_voicemail_telegram.sh
```

Set:

```text
BOT_TOKEN
CHAT_ID
ALLOWED_CHAT_ID
```

`ALLOWED_CHAT_ID` in the Python bot must be an integer, without quotes.

### Test your Telegram token

```bash
BOT_TOKEN="1234567890:ABC..."
curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getMe"
```

Send `/start` to the bot and get your chat ID:

```bash
curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getUpdates"
```

## 6. Enable the Telegram control bot

```bash
sudo systemctl enable --now telegram-asterisk-control.service
sudo systemctl status telegram-asterisk-control.service --no-pager
journalctl -u telegram-asterisk-control.service -f
```

In Telegram:

```text
/menu
/status
/help
```

## 7. Control commands

Main commands:

```text
/menu
/status
/help

/modo notifica
/modo segreteria
/modo occupato
/modo rifiuta
/modo muto
```

Lists:

```text
/vip
/vip add 32123455678
/vip del 32123455678
/vip on
/vip off

/amore
/amore add 32123455678
/amore del 32123455678

/famiglia
/famiglia add 32123455678
/famiglia del 32123455678

/blacklist
/blacklist add 32123455678
/blacklist del 32123455678
```

List output shows the phone number plus the contact name, if present in `/opt/asterisk-phonebook/contacts.tsv`.

## 8. Shared Telegram contacts

From a smartphone, share a Telegram contact with the bot.

The bot will:

1. normalize the phone number;
2. save/update it in `/opt/asterisk-phonebook/contacts.tsv`;
3. show inline buttons to classify it as:
   - normal;
   - VIP;
   - amore;
   - famiglia;
   - blacklist.

Choosing `normal` removes the number from all special lists but keeps it in the phonebook.

## 9. Prompts

```text
/prompt
/prompt list
/prompt set normal non-raggiungibile
/prompt set vip segreteria-vip
/prompt set amore segreteria-amore
/prompt set famiglia segreteria-famiglia
/prompt set blacklist occupato
/prompt set blacklist none
```

Upload prompt audio through Telegram by sending a voice/audio/document with a caption:

```text
/prompt upload amore segreteria-amore
```

The bot converts it to:

```text
/var/lib/asterisk/sounds/custom/segreteria-amore.wav
```

and internally stores it as:

```text
custom/segreteria-amore
```

The bot output hides the `custom/` prefix for readability.

## 10. Behaviour logic

Priority order:

```text
1. blacklist
2. amore
3. famiglia
4. VIP
5. normal
```

Blacklist always wins:

```text
BLACKLIST → prompt blacklist / busy / never voicemail
```

If `VIP_MODE=on`:

```text
VIP, amore, famiglia → voicemail
normal → notification / early media / busy
blacklist → busy
```

If `VIP_MODE=off`, the global `MODE` applies to everyone except blacklist.

## 11. Create audio prompts manually

Install tools:

```bash
sudo apt install -y sox ffmpeg espeak-ng
```

TTS prompt:

```bash
espeak-ng -v it -s 140 -p 45 -w /tmp/non-raggiungibile-raw.wav \
"Il numero chiamato non è al momento raggiungibile."

sudo mkdir -p /var/lib/asterisk/sounds/custom
sudo sox /tmp/non-raggiungibile-raw.wav \
  -r 8000 -c 1 -b 16 \
  /var/lib/asterisk/sounds/custom/non-raggiungibile.wav
```

MP3 to Asterisk WAV:

```bash
sudo ffmpeg -y -i prompt.mp3 \
  -ar 8000 -ac 1 -sample_fmt s16 \
  /var/lib/asterisk/sounds/custom/non-raggiungibile.wav
```

Permissions:

```bash
sudo chmod 644 /var/lib/asterisk/sounds/custom/*.wav
```

## 12. Phonebook / contact name lookup

The phonebook file is:

```text
/opt/asterisk-phonebook/contacts.tsv
```

Format:

```text
NUMBER<TAB>Display Name
```

Example:

```text
32123455678	Mario Rossi
```

You can import a Google Contacts CSV export:

```bash
sudo /usr/local/bin/importa_google_contacts_csv.py /tmp/contacts.csv
```

The importer only reads Google-style `Phone X - Value` columns and ignores email-like fields.

## 13. Debugging

Asterisk console:

```bash
sudo asterisk -rvvv
```

Useful commands:

```asterisk
core set verbose 5
pjsip set logger on
pjsip show registrations
pjsip show endpoints
dialplan show from-iliad
```

Test decision script:

```bash
/usr/local/bin/asterisk_decidi_azione.sh 32123455678
```

Expected examples:

```text
NOTIFICA|custom/non-raggiungibile|NORMALE
SEGRETERIA|custom/segreteria-amore|AMORE
BLACKLIST|custom/occupato|BLACKLIST
```

Bot logs:

```bash
journalctl -u telegram-asterisk-control.service -f
```

Syntax check:

```bash
python3 -m py_compile /usr/local/bin/telegram_asterisk_control.py
```

## 14. Security notes

- Do not expose Asterisk SIP ports to the Internet unless you know what you are doing.
- Keep this Raspberry behind your router if possible.
- Do not commit real Telegram tokens or SIP passwords.
- Do not commit real contact lists.
- Consider restricting SSH access and keeping the OS updated.

## 15. License

MIT.
