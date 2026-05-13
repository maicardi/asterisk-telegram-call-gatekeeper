#!/bin/bash
set -euo pipefail

install -d /opt/asterisk-control
install -d /opt/asterisk-phonebook
install -d /var/lib/asterisk/sounds/custom

install -m 0755 scripts/asterisk_decidi_azione.sh /usr/local/bin/asterisk_decidi_azione.sh
install -m 0755 scripts/notifica_chiamata_telegram.sh /usr/local/bin/notifica_chiamata_telegram.sh
install -m 0755 scripts/invia_voicemail_telegram.sh /usr/local/bin/invia_voicemail_telegram.sh
install -m 0755 scripts/lookup_contatto.sh /usr/local/bin/lookup_contatto.sh
install -m 0755 scripts/importa_google_contacts_csv.py /usr/local/bin/importa_google_contacts_csv.py
install -m 0755 bot/telegram_asterisk_control.py /usr/local/bin/telegram_asterisk_control.py

if [ ! -f /opt/asterisk-control/state.env ]; then
  install -m 0644 config/state.env.example /opt/asterisk-control/state.env
fi

touch /opt/asterisk-control/vip.txt
touch /opt/asterisk-control/amore.txt
touch /opt/asterisk-control/famiglia.txt
touch /opt/asterisk-control/blacklist.txt
chmod 0644 /opt/asterisk-control/*.txt

if [ ! -f /opt/asterisk-phonebook/contacts.tsv ]; then
  install -m 0644 config/contacts.tsv.example /opt/asterisk-phonebook/contacts.tsv
fi

install -m 0644 systemd/telegram-asterisk-control.service /etc/systemd/system/telegram-asterisk-control.service

systemctl daemon-reload

echo
echo "Installed."
echo "Now edit:"
echo "  /usr/local/bin/telegram_asterisk_control.py"
echo "  /usr/local/bin/notifica_chiamata_telegram.sh"
echo "  /usr/local/bin/invia_voicemail_telegram.sh"
echo "and set BOT_TOKEN / CHAT_ID / ALLOWED_CHAT_ID."
echo
echo "Then enable the bot:"
echo "  systemctl enable --now telegram-asterisk-control.service"
