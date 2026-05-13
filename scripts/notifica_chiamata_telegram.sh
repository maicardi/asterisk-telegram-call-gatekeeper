#!/bin/bash

CALLER="$1"
CATEGORY="$(echo "$2" | tr -d '\r\n' | xargs)"

BOT_TOKEN="INSERISCI_TOKEN_BOT"
CHAT_ID="INSERISCI_CHAT_ID"

DATE="$(date '+%d/%m/%Y %H:%M:%S')"

CONTACT_NAME="$(/usr/local/bin/lookup_contatto.sh "$CALLER" 2>/dev/null)"

html_escape() {
  echo "$1" | sed \
    -e 's/&/\&amp;/g' \
    -e 's/</\&lt;/g' \
    -e 's/>/\&gt;/g'
}

CALLER_ESCAPED="$(html_escape "$CALLER")"
CONTACT_ESCAPED="$(html_escape "$CONTACT_NAME")"

if [ -z "$CONTACT_NAME" ] || [ "$CONTACT_NAME" = "$CALLER" ]; then
  FROM_LINE="Da: <b>${CALLER_ESCAPED}</b>"
else
  FROM_LINE="Da: <b>${CONTACT_ESCAPED}</b> (${CALLER_ESCAPED})"
fi

case "$CATEGORY" in
  VIP)
    CATEGORY_LINE="Categoria: ⭐ <b>VIP</b>"
    ;;
  AMORE)
    CATEGORY_LINE="Categoria: ❤️ <b>Amore</b>"
    ;;
  FAMIGLIA)
    CATEGORY_LINE="Categoria: 👨‍👩‍👧 <b>Famiglia</b>"
    ;;
  BLACKLIST)
    CATEGORY_LINE="Categoria: ⛔ <b>Blacklist</b>"
    ;;
  *)
    CATEGORY_LINE="Categoria: normale"
    ;;
esac

TEXT="📞 <b>Chiamata ricevuta</b>

${FROM_LINE}
${CATEGORY_LINE}
Ora: ${DATE}"

curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
  -d chat_id="${CHAT_ID}" \
  -d parse_mode="HTML" \
  --data-urlencode text="${TEXT}" >/dev/null 2>&1

exit 0
