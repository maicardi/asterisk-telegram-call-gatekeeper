#!/bin/bash

STATE="/opt/asterisk-control/state.env"
VIP_FILE="/opt/asterisk-control/vip.txt"
AMORE_FILE="/opt/asterisk-control/amore.txt"
FAMIGLIA_FILE="/opt/asterisk-control/famiglia.txt"
BLACKLIST_FILE="/opt/asterisk-control/blacklist.txt"

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

in_list() {
  local num="$1"
  local file="$2"

  [ -f "$file" ] && grep -qxF "$num" "$file"
}

safe_prompt() {
  local p="$1"
  local fallback="$2"

  if [ -z "$p" ]; then
    echo "$fallback"
    return
  fi

  case "$p" in
    custom/*|none)
      echo "$p"
      ;;
    *)
      echo "$fallback"
      ;;
  esac
}

NUM="$(normalize_number "$RAW")"

MODE="notifica"
VIP_MODE="off"

PROMPT_NORMAL="custom/non-raggiungibile"
PROMPT_VIP="custom/non-raggiungibile-vip"
PROMPT_AMORE="custom/non-raggiungibile-amore"
PROMPT_FAMIGLIA="custom/non-raggiungibile-famiglia"
PROMPT_BLACKLIST="custom/occupato"

if [ -f "$STATE" ]; then
  # shellcheck disable=SC1090
  . "$STATE"
fi

PROMPT_NORMAL="$(safe_prompt "$PROMPT_NORMAL" "custom/non-raggiungibile")"
PROMPT_VIP="$(safe_prompt "$PROMPT_VIP" "$PROMPT_NORMAL")"
PROMPT_AMORE="$(safe_prompt "$PROMPT_AMORE" "$PROMPT_VIP")"
PROMPT_FAMIGLIA="$(safe_prompt "$PROMPT_FAMIGLIA" "$PROMPT_AMORE")"
PROMPT_BLACKLIST="$(safe_prompt "$PROMPT_BLACKLIST" "$PROMPT_NORMAL")"

# Priorità assoluta: blacklist
if in_list "$NUM" "$BLACKLIST_FILE"; then
  echo "BLACKLIST|${PROMPT_BLACKLIST}|BLACKLIST"
  exit 0
fi

CATEGORY="NORMALE"
PROMPT="$PROMPT_NORMAL"

# Priorità categorie positive: amore > famiglia > VIP > normale
if in_list "$NUM" "$AMORE_FILE"; then
  CATEGORY="AMORE"
  PROMPT="$PROMPT_AMORE"
elif in_list "$NUM" "$FAMIGLIA_FILE"; then
  CATEGORY="FAMIGLIA"
  PROMPT="$PROMPT_FAMIGLIA"
elif in_list "$NUM" "$VIP_FILE"; then
  CATEGORY="VIP"
  PROMPT="$PROMPT_VIP"
fi

# Se VIP_MODE è on, solo VIP/AMORE/FAMIGLIA possono andare in segreteria.
if [ "$VIP_MODE" = "on" ]; then
  if [ "$CATEGORY" = "VIP" ] || [ "$CATEGORY" = "AMORE" ] || [ "$CATEGORY" = "FAMIGLIA" ]; then
    echo "SEGRETERIA|${PROMPT}|${CATEGORY}"
  else
    echo "NOTIFICA|${PROMPT}|${CATEGORY}"
  fi
  exit 0
fi

case "$MODE" in
  segreteria)
    echo "SEGRETERIA|${PROMPT}|${CATEGORY}"
    ;;
  occupato)
    echo "OCCUPATO|${PROMPT}|${CATEGORY}"
    ;;
  rifiuta)
    echo "RIFIUTA|${PROMPT}|${CATEGORY}"
    ;;
  muto)
    echo "MUTO|${PROMPT}|${CATEGORY}"
    ;;
  notifica|*)
    echo "NOTIFICA|${PROMPT}|${CATEGORY}"
    ;;
esac

exit 0
