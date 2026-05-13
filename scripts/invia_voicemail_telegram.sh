#!/bin/bash

CALLER="$1"
AUDIO="$2"

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
  TITLE="Messaggio da ${CALLER}"
else
  FROM_LINE="Da: <b>${CONTACT_ESCAPED}</b> (${CALLER_ESCAPED})"
  TITLE="Messaggio da ${CONTACT_NAME}"
fi

TEXT="📞 <b>Nuovo messaggio in segreteria</b>

${FROM_LINE}
Ora: ${DATE}"

curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
  -d chat_id="${CHAT_ID}" \
  -d parse_mode="HTML" \
  --data-urlencode text="${TEXT}" >/dev/null

if [ -f "$AUDIO" ]; then
  NORMALIZED="/tmp/voicemail-normalized-$(basename "$AUDIO")"

  if command -v sox >/dev/null 2>&1; then
    sox "$AUDIO" "$NORMALIZED" gain -n -1 >/dev/null 2>&1 || cp "$AUDIO" "$NORMALIZED"
  else
    cp "$AUDIO" "$NORMALIZED"
  fi

  curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendAudio" \
    -F chat_id="${CHAT_ID}" \
    -F audio=@"${NORMALIZED}" \
    -F title="${TITLE}" >/dev/null

  rm -f "$NORMALIZED"
fi

exit 0
