#!/bin/bash

PHONEBOOK="/opt/asterisk-phonebook/contacts.tsv"
RAW="$1"

normalize_number() {
  local n="$1"

  n="${n#sip:}"
  n="${n%@*}"
  n="$(echo "$n" | sed 's/[^0-9+]//g')"

  case "$n" in
    +39*) n="${n:3}" ;;
    0039*) n="${n:4}" ;;
    39*)
      if [ ${#n} -ge 11 ]; then
        n="${n:2}"
      fi
      ;;
  esac

  echo "$n"
}

NUM="$(normalize_number "$RAW")"

if [ -z "$NUM" ] || [ ! -f "$PHONEBOOK" ]; then
  echo "$RAW"
  exit 0
fi

NAME="$(grep -m1 -F "${NUM}	" "$PHONEBOOK" | cut -f2-)"

if [ -n "$NAME" ]; then
  echo "$NAME"
else
  echo "$NUM"
fi

exit 0
