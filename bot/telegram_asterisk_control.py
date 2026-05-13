#!/usr/bin/env python3
import json
import os
import re
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path


# =========================
# CONFIGURAZIONE
# =========================

BOT_TOKEN = "INSERISCI_TOKEN_BOT"
ALLOWED_CHAT_ID = 123456789

STATE_PATH = Path("/opt/asterisk-control/state.env")
VIP_PATH = Path("/opt/asterisk-control/vip.txt")
AMORE_PATH = Path("/opt/asterisk-control/amore.txt")
FAMIGLIA_PATH = Path("/opt/asterisk-control/famiglia.txt")
BLACKLIST_PATH = Path("/opt/asterisk-control/blacklist.txt")
OFFSET_PATH = Path("/opt/asterisk-control/telegram.offset")

SOUNDS_CUSTOM_DIR = Path("/var/lib/asterisk/sounds/custom")
SUPPORTED_AUDIO_EXTS = {".wav", ".alaw", ".ulaw", ".gsm", ".sln", ".slin"}

API = f"https://api.telegram.org/bot{BOT_TOKEN}"


# =========================
# TELEGRAM API
# =========================

def api_call(method, data=None):
    url = f"{API}/{method}"
    encoded = None

    if data:
        encoded = urllib.parse.urlencode(data).encode()

    with urllib.request.urlopen(url, data=encoded, timeout=60) as r:
        return json.loads(r.read().decode())


def send_message(chat_id, text, parse_mode="HTML"):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": "true",
    }

    if parse_mode:
        payload["parse_mode"] = parse_mode

    api_call("sendMessage", payload)


def send_message_with_keyboard(chat_id, text, keyboard, parse_mode="HTML"):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": "true",
        "reply_markup": json.dumps({
            "inline_keyboard": keyboard
        }),
    }

    if parse_mode:
        payload["parse_mode"] = parse_mode

    api_call("sendMessage", payload)


def edit_message_with_keyboard(chat_id, message_id, text, keyboard, parse_mode="HTML"):
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "disable_web_page_preview": "true",
        "reply_markup": json.dumps({
            "inline_keyboard": keyboard
        }),
    }

    if parse_mode:
        payload["parse_mode"] = parse_mode

    api_call("editMessageText", payload)


def answer_callback_query(callback_query_id, text=None):
    data = {"callback_query_id": callback_query_id}

    if text:
        data["text"] = text

    api_call("answerCallbackQuery", data)


def telegram_get_file(file_id):
    return api_call("getFile", {"file_id": file_id})


def download_telegram_file(file_path, destination):
    url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

    with urllib.request.urlopen(url, timeout=120) as response:
        destination.write_bytes(response.read())


# =========================
# STATO
# =========================

def read_state():
    state = {
        "MODE": "notifica",
        "VIP_MODE": "off",
        "PROMPT_NORMAL": "custom/non-raggiungibile",
        "PROMPT_VIP": "custom/non-raggiungibile-vip",
        "PROMPT_AMORE": "custom/non-raggiungibile-amore",
        "PROMPT_FAMIGLIA": "custom/non-raggiungibile-famiglia",
        "PROMPT_BLACKLIST": "custom/occupato",
    }

    if STATE_PATH.exists():
        for line in STATE_PATH.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            state[key.strip()] = value.strip()

    return state


def write_state(state):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)

    tmp = STATE_PATH.with_suffix(".tmp")
    content = "\n".join([
        f"MODE={state.get('MODE', 'notifica')}",
        f"VIP_MODE={state.get('VIP_MODE', 'off')}",
        f"PROMPT_NORMAL={state.get('PROMPT_NORMAL', 'custom/non-raggiungibile')}",
        f"PROMPT_VIP={state.get('PROMPT_VIP', 'custom/non-raggiungibile-vip')}",
        f"PROMPT_AMORE={state.get('PROMPT_AMORE', 'custom/non-raggiungibile-amore')}",
        f"PROMPT_FAMIGLIA={state.get('PROMPT_FAMIGLIA', 'custom/non-raggiungibile-famiglia')}",
        f"PROMPT_BLACKLIST={state.get('PROMPT_BLACKLIST', 'custom/occupato')}",
        "",
    ])

    tmp.write_text(content)
    os.replace(tmp, STATE_PATH)


def get_offset():
    if OFFSET_PATH.exists():
        try:
            return int(OFFSET_PATH.read_text().strip())
        except Exception:
            return None

    return None


def save_offset(offset):
    OFFSET_PATH.parent.mkdir(parents=True, exist_ok=True)
    OFFSET_PATH.write_text(str(offset))


# =========================
# NORMALIZZAZIONE / DISPLAY
# =========================

def normalize_number(raw):
    n = (raw or "").strip()
    n = re.sub(r"[^0-9+]", "", n)

    if n.startswith("+39"):
        n = n[3:]
    elif n.startswith("0039"):
        n = n[4:]
    elif n.startswith("39") and len(n) >= 11:
        n = n[2:]

    return n


def display_prompt(prompt):
    prompt = prompt or ""
    if prompt == "none":
        return "none"
    if prompt.startswith("custom/"):
        return prompt[len("custom/"):]
    return prompt


# =========================
# LISTE NUMERI
# =========================

def read_number_list(path):
    if not path.exists():
        return []

    return [
        line.strip()
        for line in path.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def write_number_list(path, numbers):
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp = path.with_suffix(".tmp")
    tmp.write_text("\n".join(sorted(set(numbers))) + "\n")
    os.replace(tmp, path)


def vip_list():
    return read_number_list(VIP_PATH)


def amore_list():
    return read_number_list(AMORE_PATH)


def famiglia_list():
    return read_number_list(FAMIGLIA_PATH)


def blacklist_list():
    return read_number_list(BLACKLIST_PATH)


def handle_number_list_command(parts, label, path, emoji):
    numbers = read_number_list(path)

    if len(parts) == 1:
        if not numbers:
            return f"{emoji} Lista <b>{label}</b> vuota."

        return (
            f"{emoji} <b>Lista {label}</b>\n\n"
            + "\n".join(f"<code>{n}</code>" for n in numbers)
        )

    action = parts[1].lower()

    if action in ["add", "del"]:
        if len(parts) < 3:
            return f"Uso: <code>/{label} {action} NUMERO</code>"

        number = normalize_number(parts[2])

        if not number or len(number) < 7:
            return "Numero non valido."

        if action == "add":
            if number not in numbers:
                numbers.append(number)
                write_number_list(path, numbers)

            return f"✅ Aggiunto a <b>{label}</b>: <code>{number}</code>"

        if action == "del":
            numbers = [n for n in numbers if n != number]
            write_number_list(path, numbers)

            return f"✅ Rimosso da <b>{label}</b>: <code>{number}</code>"

    return (
        f"Comando non valido. Usa:\n"
        f"<code>/{label}</code>\n"
        f"<code>/{label} add NUMERO</code>\n"
        f"<code>/{label} del NUMERO</code>"
    )


# =========================
# PROMPT AUDIO
# =========================

def list_custom_prompts():
    if not SOUNDS_CUSTOM_DIR.exists():
        return []

    prompts = []

    for path in sorted(SOUNDS_CUSTOM_DIR.iterdir()):
        if not path.is_file():
            continue

        if path.suffix.lower() not in SUPPORTED_AUDIO_EXTS:
            continue

        prompts.append(path.stem)

    return sorted(set(prompts))


def normalize_prompt_name(raw):
    name = (raw or "").strip()

    if name.startswith("custom/"):
        name = name[len("custom/"):]

    name = Path(name).stem

    if not re.match(r"^[A-Za-z0-9_.-]+$", name):
        return ""

    return name


def prompt_exists(name):
    for ext in SUPPORTED_AUDIO_EXTS:
        if (SOUNDS_CUSTOM_DIR / f"{name}{ext}").exists():
            return True

    return False


def install_uploaded_prompt(file_id, prompt_name):
    name = normalize_prompt_name(prompt_name)

    if not name:
        return False, "Nome prompt non valido."

    SOUNDS_CUSTOM_DIR.mkdir(parents=True, exist_ok=True)

    info = telegram_get_file(file_id)

    if not info.get("ok"):
        return False, "Impossibile ottenere il file da Telegram."

    file_path = info["result"]["file_path"]

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        raw_path = tmpdir / "uploaded_audio"
        out_path = SOUNDS_CUSTOM_DIR / f"{name}.wav"

        download_telegram_file(file_path, raw_path)

        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(raw_path),
            "-ar", "8000",
            "-ac", "1",
            "-sample_fmt", "s16",
            str(out_path),
        ]

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if result.returncode != 0:
            return False, (
                "Conversione audio fallita.\n\n"
                f"<code>{result.stderr[-1500:]}</code>"
            )

        os.chmod(out_path, 0o644)

    return True, f"✅ Prompt caricato: <code>{name}</code>."


def handle_audio_upload(msg):
    caption = (msg.get("caption") or "").strip()

    if not caption.startswith("/prompt upload"):
        return None

    parts = caption.split(maxsplit=3)

    if len(parts) < 4:
        return (
            "Uso: invia audio con caption:\n"
            "<code>/prompt upload normal nome</code>\n"
            "<code>/prompt upload vip nome</code>\n"
            "<code>/prompt upload amore nome</code>\n"
            "<code>/prompt upload famiglia nome</code>\n"
            "<code>/prompt upload blacklist nome</code>"
        )

    target = parts[2].lower()
    prompt_name = parts[3].strip()

    prompt_keys = {
        "normal": "PROMPT_NORMAL",
        "normale": "PROMPT_NORMAL",
        "vip": "PROMPT_VIP",
        "amore": "PROMPT_AMORE",
        "love": "PROMPT_AMORE",
        "famiglia": "PROMPT_FAMIGLIA",
        "family": "PROMPT_FAMIGLIA",
        "blacklist": "PROMPT_BLACKLIST",
        "bloccati": "PROMPT_BLACKLIST",
    }

    if target not in prompt_keys:
        return "Categoria non valida. Usa: <code>normal</code>, <code>vip</code>, <code>amore</code>, <code>famiglia</code>, <code>blacklist</code>."

    file_id = None

    if "voice" in msg:
        file_id = msg["voice"]["file_id"]
    elif "audio" in msg:
        file_id = msg["audio"]["file_id"]
    elif "document" in msg:
        file_id = msg["document"]["file_id"]

    if not file_id:
        return "Non ho trovato un file audio nel messaggio."

    ok, message = install_uploaded_prompt(file_id, prompt_name)

    if not ok:
        return message

    name = normalize_prompt_name(prompt_name)

    state = read_state()
    state[prompt_keys[target]] = f"custom/{name}"
    write_state(state)

    return f"✅ Prompt caricato e impostato per <b>{target}</b>: <code>{name}</code>."


# =========================
# MENU INLINE
# =========================

def main_menu_keyboard():
    return [
        [
            {"text": "⚙️ Stato", "callback_data": "menu:status"},
            {"text": "🔁 Modalità", "callback_data": "menu:mode"},
        ],
        [
            {"text": "⭐ VIP", "callback_data": "menu:vip"},
            {"text": "❤️ Amore", "callback_data": "menu:amore"},
        ],
        [
            {"text": "👨‍👩‍👧 Famiglia", "callback_data": "menu:famiglia"},
            {"text": "⛔ Blacklist", "callback_data": "menu:blacklist"},
        ],
        [
            {"text": "🔊 Prompt", "callback_data": "menu:prompt"},
            {"text": "❓ Aiuto", "callback_data": "menu:help"},
        ],
    ]


def mode_menu_keyboard():
    return [
        [
            {"text": "📣 Notifica", "callback_data": "setmode:notifica"},
            {"text": "🎙 Segreteria", "callback_data": "setmode:segreteria"},
        ],
        [
            {"text": "📵 Occupato", "callback_data": "setmode:occupato"},
            {"text": "🚫 Rifiuta", "callback_data": "setmode:rifiuta"},
        ],
        [
            {"text": "🔕 Muto", "callback_data": "setmode:muto"},
        ],
        [
            {"text": "⬅️ Indietro", "callback_data": "menu:main"},
        ],
    ]


def lists_menu_keyboard(list_name):
    return [
        [
            {"text": "📋 Mostra lista", "callback_data": f"listshow:{list_name}"},
        ],
        [
            {"text": "➕ Aggiungi", "callback_data": f"listhelp:add:{list_name}"},
            {"text": "➖ Rimuovi", "callback_data": f"listhelp:del:{list_name}"},
        ],
        [
            {"text": "⬅️ Indietro", "callback_data": "menu:main"},
        ],
    ]


def prompt_menu_keyboard():
    return [
        [
            {"text": "📋 Prompt disponibili", "callback_data": "prompt:list"},
        ],
        [
            {"text": "Normale", "callback_data": "prompthelp:normal"},
            {"text": "VIP", "callback_data": "prompthelp:vip"},
        ],
        [
            {"text": "Amore", "callback_data": "prompthelp:amore"},
            {"text": "Famiglia", "callback_data": "prompthelp:famiglia"},
        ],
        [
            {"text": "Blacklist", "callback_data": "prompthelp:blacklist"},
        ],
        [
            {"text": "⬅️ Indietro", "callback_data": "menu:main"},
        ],
    ]


# =========================
# TESTI
# =========================

def status_text():
    state = read_state()
    vips = vip_list()
    amore = amore_list()
    famiglia = famiglia_list()
    blacklist = blacklist_list()

    return (
        "⚙️ <b>Stato Asterisk</b>\n\n"
        f"Modo: <b>{state.get('MODE')}</b>\n"
        f"VIP mode: <b>{state.get('VIP_MODE')}</b>\n\n"
        f"Prompt normale: <code>{display_prompt(state.get('PROMPT_NORMAL', 'custom/non-raggiungibile'))}</code>\n"
        f"Prompt VIP: <code>{display_prompt(state.get('PROMPT_VIP', 'custom/non-raggiungibile-vip'))}</code>\n"
        f"Prompt amore: <code>{display_prompt(state.get('PROMPT_AMORE', 'custom/non-raggiungibile-amore'))}</code>\n"
        f"Prompt famiglia: <code>{display_prompt(state.get('PROMPT_FAMIGLIA', 'custom/non-raggiungibile-famiglia'))}</code>\n"
        f"Prompt blacklist: <code>{display_prompt(state.get('PROMPT_BLACKLIST', 'custom/occupato'))}</code>\n\n"
        f"VIP: <b>{len(vips)}</b>\n"
        f"Amore: <b>{len(amore)}</b>\n"
        f"Famiglia: <b>{len(famiglia)}</b>\n"
        f"Blacklist: <b>{len(blacklist)}</b>"
    )


def help_text():
    return (
        "📟 <b>Comandi Asterisk</b>\n\n"

        "⚙️ <b>Stato e modalità</b>\n\n"
        "<code>/menu</code>\n"
        "Apre il menu interattivo con bottoni.\n\n"

        "<code>/status</code>\n"
        "Mostra configurazione attuale.\n\n"

        "<code>/modo notifica</code>\n"
        "Notifica Telegram + messaggio early media + occupato.\n\n"

        "<code>/modo segreteria</code>\n"
        "Risponde e registra messaggio vocale.\n\n"

        "<code>/modo occupato</code>\n"
        "Messaggio early media + occupato.\n\n"

        "<code>/modo rifiuta</code>\n"
        "Messaggio early media + rifiuto.\n\n"

        "<code>/modo muto</code>\n"
        "Solo notifica + hangup, senza messaggio audio.\n\n"

        "⭐ <b>VIP</b>\n\n"
        "<code>/vip</code>\n"
        "Mostra lista VIP.\n\n"

        "<code>/vip add 32123455678</code>\n"
        "Aggiunge numero alla lista VIP.\n\n"

        "<code>/vip del 32123455678</code>\n"
        "Rimuove numero dalla lista VIP.\n\n"

        "<code>/vip on</code> / <code>/vip off</code>\n"
        "Attiva/disattiva modalità VIP: se attiva, solo VIP, amore e famiglia possono andare in segreteria; gli altri fanno solo notifica/occupato.\n\n"

        "❤️ <b>Amore</b>\n\n"
        "<code>/amore</code>\n"
        "Mostra lista amore.\n\n"

        "<code>/amore add 32123455678</code>\n"
        "Aggiunge numero alla lista amore.\n\n"

        "<code>/amore del 32123455678</code>\n"
        "Rimuove numero dalla lista amore.\n\n"

        "👨‍👩‍👧 <b>Famiglia</b>\n\n"
        "<code>/famiglia</code>\n"
        "Mostra lista famiglia.\n\n"

        "<code>/famiglia add 32123455678</code>\n"
        "Aggiunge numero alla lista famiglia.\n\n"

        "<code>/famiglia del 32123455678</code>\n"
        "Rimuove numero dalla lista famiglia.\n\n"

        "⛔ <b>Blacklist</b>\n\n"
        "<code>/blacklist</code>\n"
        "Mostra lista blacklist.\n\n"

        "<code>/blacklist add 32123455678</code>\n"
        "Aggiunge numero alla blacklist: occupato immediato, mai segreteria.\n\n"

        "<code>/blacklist del 32123455678</code>\n"
        "Rimuove numero dalla blacklist.\n\n"

        "🔊 <b>Prompt audio</b>\n\n"
        "<code>/prompt</code>\n"
        "Mostra i prompt attualmente configurati per chiamate normali, VIP, amore, famiglia e blacklist.\n\n"

        "<code>/prompt list</code>\n"
        "Mostra i prompt disponibili.\n\n"

        "<code>/prompt set normal nome</code>\n"
        "Imposta prompt per chiamate normali.\n\n"

        "<code>/prompt set vip nome</code>\n"
        "Imposta prompt per chiamate VIP.\n\n"

        "<code>/prompt set amore nome</code>\n"
        "Imposta prompt per chiamate amore.\n\n"

        "<code>/prompt set famiglia nome</code>\n"
        "Imposta prompt per chiamate famiglia.\n\n"

        "<code>/prompt set blacklist nome</code>\n"
        "Imposta prompt per chiamate blacklist.\n\n"

        "<code>/prompt set blacklist none</code>\n"
        "Disattiva il messaggio audio per la blacklist.\n\n"

        "🎙 <b>Upload prompt via Telegram</b>\n\n"
        "Invia un audio, un vocale o un file audio al bot usando una caption di questo tipo:\n\n"

        "<code>/prompt upload normal nome</code>\n"
        "Carica e imposta un prompt per chiamate normali.\n\n"

        "<code>/prompt upload vip nome</code>\n"
        "Carica e imposta un prompt per VIP.\n\n"

        "<code>/prompt upload amore nome</code>\n"
        "Carica e imposta un prompt per amore.\n\n"

        "<code>/prompt upload famiglia nome</code>\n"
        "Carica e imposta un prompt per famiglia.\n\n"

        "<code>/prompt upload blacklist nome</code>\n"
        "Carica e imposta un prompt per blacklist.\n\n"

        "Esempio:\n"
        "<code>/prompt upload amore messaggio-amore</code>\n\n"

        "📌 <b>Note</b>\n\n"
        "I numeri possono essere inseriti con o senza prefisso italiano: "
        "<code>32123455678</code>, <code>+3932123455678</code> o <code>003932123455678</code>.\n\n"

        "I prompt vanno indicati senza estensione: se il file è "
        "<code>non-raggiungibile.wav</code>, usa "
        "<code>non-raggiungibile</code>."
    )


# =========================
# COMANDI TESTUALI
# =========================

def handle_command(text):
    parts = text.strip().split()
    if not parts:
        return ""

    cmd = parts[0].lower()
    state = read_state()

    if cmd in ["/help", "/start"]:
        return help_text()

    if cmd == "/menu":
        return "__MENU__"

    if cmd == "/status":
        return status_text()

    if cmd == "/modo":
        if len(parts) < 2:
            return "Uso: <code>/modo notifica|segreteria|occupato|rifiuta|muto</code>"

        mode = parts[1].lower()
        allowed = {"notifica", "segreteria", "occupato", "rifiuta", "muto"}

        if mode not in allowed:
            return (
                "Modo non valido. Usa: <code>notifica</code>, <code>segreteria</code>, "
                "<code>occupato</code>, <code>rifiuta</code>, <code>muto</code>."
            )

        state["MODE"] = mode
        write_state(state)
        return f"✅ Modo impostato su <b>{mode}</b>."

    if cmd == "/vip":
        if len(parts) >= 2 and parts[1].lower() in ["on", "off"]:
            state["VIP_MODE"] = parts[1].lower()
            write_state(state)
            return f"✅ VIP mode impostato su <b>{parts[1].lower()}</b>."

        return handle_number_list_command(parts, "vip", VIP_PATH, "⭐")

    if cmd == "/amore":
        return handle_number_list_command(parts, "amore", AMORE_PATH, "❤️")

    if cmd == "/famiglia":
        return handle_number_list_command(parts, "famiglia", FAMIGLIA_PATH, "👨‍👩‍👧")

    if cmd == "/blacklist":
        return handle_number_list_command(parts, "blacklist", BLACKLIST_PATH, "⛔")

    if cmd == "/prompt":
        prompt_keys = {
            "normal": "PROMPT_NORMAL",
            "normale": "PROMPT_NORMAL",
            "vip": "PROMPT_VIP",
            "amore": "PROMPT_AMORE",
            "love": "PROMPT_AMORE",
            "famiglia": "PROMPT_FAMIGLIA",
            "family": "PROMPT_FAMIGLIA",
            "blacklist": "PROMPT_BLACKLIST",
            "bloccati": "PROMPT_BLACKLIST",
        }

        if len(parts) == 1:
            return (
                "🔊 <b>Prompt attuali</b>\n\n"
                f"Normale: <code>{display_prompt(state.get('PROMPT_NORMAL'))}</code>\n"
                f"VIP: <code>{display_prompt(state.get('PROMPT_VIP'))}</code>\n"
                f"Amore: <code>{display_prompt(state.get('PROMPT_AMORE'))}</code>\n"
                f"Famiglia: <code>{display_prompt(state.get('PROMPT_FAMIGLIA'))}</code>\n"
                f"Blacklist: <code>{display_prompt(state.get('PROMPT_BLACKLIST'))}</code>\n\n"
                "Usa <code>/prompt list</code> per vedere quelli disponibili."
            )

        action = parts[1].lower()

        if action == "list":
            prompts = list_custom_prompts()

            if not prompts:
                return "Nessun prompt trovato."

            lines = "\n".join(f"• <code>{p}</code>" for p in prompts)

            return (
                "🔊 <b>Prompt disponibili</b>\n\n"
                f"{lines}\n\n"
                "Per impostarne uno:\n"
                "<code>/prompt set normal nome</code>\n"
                "<code>/prompt set vip nome</code>\n"
                "<code>/prompt set amore nome</code>\n"
                "<code>/prompt set famiglia nome</code>\n"
                "<code>/prompt set blacklist nome</code>"
            )

        if action == "set":
            if len(parts) < 4:
                return (
                    "Uso:\n"
                    "<code>/prompt set normal nome</code>\n"
                    "<code>/prompt set vip nome</code>\n"
                    "<code>/prompt set amore nome</code>\n"
                    "<code>/prompt set famiglia nome</code>\n"
                    "<code>/prompt set blacklist nome</code>\n\n"
                    "Per disattivare il messaggio per una categoria:\n"
                    "<code>/prompt set blacklist none</code>"
                )

            target = parts[2].lower()
            name_raw = parts[3].strip()

            if target not in prompt_keys:
                return "Categoria non valida. Usa: <code>normal</code>, <code>vip</code>, <code>amore</code>, <code>famiglia</code>, <code>blacklist</code>."

            if name_raw == "none":
                state[prompt_keys[target]] = "none"
                write_state(state)
                return f"✅ Prompt per <b>{target}</b> disattivato."

            name = normalize_prompt_name(name_raw)

            if not name:
                return "Nome prompt non valido."

            if not prompt_exists(name):
                return (
                    "Prompt non trovato.\n\n"
                    f"Cercavo un file tipo <code>{name}.wav</code>, <code>{name}.alaw</code> "
                    f"o <code>{name}.slin</code>.\n\n"
                    "Usa <code>/prompt list</code>."
                )

            state[prompt_keys[target]] = f"custom/{name}"
            write_state(state)

            return f"✅ Prompt per <b>{target}</b> impostato su <code>{name}</code>."

        return "Comando prompt non valido. Usa <code>/prompt</code>, <code>/prompt list</code> o <code>/prompt set categoria nome</code>."

    return "Comando non riconosciuto. Usa <code>/help</code> o <code>/menu</code>."


# =========================
# CALLBACK INLINE KEYBOARD
# =========================

def handle_callback_query(callback):
    callback_id = callback["id"]
    data = callback.get("data", "")
    msg = callback.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    message_id = msg.get("message_id")

    if chat_id != ALLOWED_CHAT_ID:
        answer_callback_query(callback_id, "Non autorizzato.")
        return

    answer_callback_query(callback_id)

    if data == "menu:main":
        edit_message_with_keyboard(
            chat_id,
            message_id,
            "📟 <b>Menu controllo Asterisk</b>\n\nScegli cosa vuoi fare:",
            main_menu_keyboard(),
        )
        return

    if data == "menu:status":
        edit_message_with_keyboard(
            chat_id,
            message_id,
            status_text(),
            [[{"text": "⬅️ Indietro", "callback_data": "menu:main"}]],
        )
        return

    if data == "menu:help":
        edit_message_with_keyboard(
            chat_id,
            message_id,
            help_text(),
            [[{"text": "⬅️ Indietro", "callback_data": "menu:main"}]],
        )
        return

    if data == "menu:mode":
        edit_message_with_keyboard(
            chat_id,
            message_id,
            "🔁 <b>Modalità Asterisk</b>\n\nScegli il comportamento globale:",
            mode_menu_keyboard(),
        )
        return

    if data.startswith("setmode:"):
        mode = data.split(":", 1)[1]
        allowed = {"notifica", "segreteria", "occupato", "rifiuta", "muto"}

        if mode not in allowed:
            edit_message_with_keyboard(
                chat_id,
                message_id,
                "Modo non valido.",
                [[{"text": "⬅️ Indietro", "callback_data": "menu:mode"}]],
            )
            return

        state = read_state()
        state["MODE"] = mode
        write_state(state)

        edit_message_with_keyboard(
            chat_id,
            message_id,
            f"✅ Modo impostato su <b>{mode}</b>.",
            [
                [{"text": "🔁 Cambia ancora", "callback_data": "menu:mode"}],
                [{"text": "⬅️ Menu", "callback_data": "menu:main"}],
            ],
        )
        return

    if data == "menu:vip":
        edit_message_with_keyboard(
            chat_id,
            message_id,
            "⭐ <b>VIP</b>\n\nGestisci lista VIP o usa <code>/vip on</code> / <code>/vip off</code>.",
            lists_menu_keyboard("vip"),
        )
        return

    if data == "menu:amore":
        edit_message_with_keyboard(
            chat_id,
            message_id,
            "❤️ <b>Amore</b>\n\nGestisci lista amore.",
            lists_menu_keyboard("amore"),
        )
        return

    if data == "menu:famiglia":
        edit_message_with_keyboard(
            chat_id,
            message_id,
            "👨‍👩‍👧 <b>Famiglia</b>\n\nGestisci lista famiglia.",
            lists_menu_keyboard("famiglia"),
        )
        return

    if data == "menu:blacklist":
        edit_message_with_keyboard(
            chat_id,
            message_id,
            "⛔ <b>Blacklist</b>\n\nI numeri in blacklist ricevono occupato immediato e non vanno mai in segreteria.",
            lists_menu_keyboard("blacklist"),
        )
        return

    if data.startswith("listshow:"):
        list_name = data.split(":", 1)[1]

        if list_name == "vip":
            numbers = read_number_list(VIP_PATH)
            title = "⭐ VIP"
        elif list_name == "amore":
            numbers = read_number_list(AMORE_PATH)
            title = "❤️ Amore"
        elif list_name == "famiglia":
            numbers = read_number_list(FAMIGLIA_PATH)
            title = "👨‍👩‍👧 Famiglia"
        elif list_name == "blacklist":
            numbers = read_number_list(BLACKLIST_PATH)
            title = "⛔ Blacklist"
        else:
            numbers = []
            title = "Lista"

        if numbers:
            body = "\n".join(f"<code>{n}</code>" for n in numbers)
        else:
            body = "Lista vuota."

        edit_message_with_keyboard(
            chat_id,
            message_id,
            f"{title}\n\n{body}",
            [[{"text": "⬅️ Indietro", "callback_data": f"menu:{list_name}"}]],
        )
        return

    if data.startswith("listhelp:"):
        _, action, list_name = data.split(":", 2)

        if action == "add":
            cmd_text = f"/{list_name} add NUMERO"
            desc = "Per aggiungere un numero, scrivi:"
        else:
            cmd_text = f"/{list_name} del NUMERO"
            desc = "Per rimuovere un numero, scrivi:"

        edit_message_with_keyboard(
            chat_id,
            message_id,
            f"{desc}\n\n<code>{cmd_text}</code>\n\nEsempio:\n<code>/{list_name} {action} 32123455678</code>",
            [[{"text": "⬅️ Indietro", "callback_data": f"menu:{list_name}"}]],
        )
        return

    if data == "menu:prompt":
        edit_message_with_keyboard(
            chat_id,
            message_id,
            "🔊 <b>Prompt audio</b>\n\nGestisci i messaggi per chiamate normali, VIP, amore, famiglia e blacklist.",
            prompt_menu_keyboard(),
        )
        return

    if data == "prompt:list":
        prompts = list_custom_prompts()

        if prompts:
            body = "\n".join(f"• <code>{p}</code>" for p in prompts)
        else:
            body = "Nessun prompt trovato."

        edit_message_with_keyboard(
            chat_id,
            message_id,
            f"🔊 <b>Prompt disponibili</b>\n\n{body}",
            [[{"text": "⬅️ Indietro", "callback_data": "menu:prompt"}]],
        )
        return

    if data.startswith("prompthelp:"):
        target = data.split(":", 1)[1]

        edit_message_with_keyboard(
            chat_id,
            message_id,
            (
                f"🔊 <b>Prompt {target}</b>\n\n"
                f"Per impostarlo, scrivi:\n"
                f"<code>/prompt set {target} nome-prompt</code>\n\n"
                f"Per caricare un audio, invialo con caption:\n"
                f"<code>/prompt upload {target} nome-prompt</code>\n\n"
                f"Per disattivarlo:\n"
                f"<code>/prompt set {target} none</code>"
            ),
            [[{"text": "⬅️ Indietro", "callback_data": "menu:prompt"}]],
        )
        return


# =========================
# MAIN LOOP
# =========================

def main():
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    VIP_PATH.touch(exist_ok=True)
    AMORE_PATH.touch(exist_ok=True)
    FAMIGLIA_PATH.touch(exist_ok=True)
    BLACKLIST_PATH.touch(exist_ok=True)

    while True:
        try:
            offset = get_offset()
            data = {"timeout": 30}

            if offset is not None:
                data["offset"] = offset

            updates = api_call("getUpdates", data)

            for update in updates.get("result", []):
                save_offset(update["update_id"] + 1)

                if "callback_query" in update:
                    handle_callback_query(update["callback_query"])
                    continue

                msg = update.get("message") or update.get("edited_message")
                if not msg:
                    continue

                chat = msg.get("chat", {})
                chat_id = chat.get("id")

                if chat_id != ALLOWED_CHAT_ID:
                    send_message(chat_id, "⛔ Non autorizzato.", parse_mode=None)
                    continue

                upload_reply = handle_audio_upload(msg)

                if upload_reply:
                    send_message(chat_id, upload_reply)
                    continue

                text = msg.get("text", "")

                if not text.startswith("/"):
                    continue

                reply = handle_command(text)

                if reply == "__MENU__":
                    send_message_with_keyboard(
                        chat_id,
                        "📟 <b>Menu controllo Asterisk</b>\n\nScegli cosa vuoi fare:",
                        main_menu_keyboard(),
                    )
                else:
                    send_message(chat_id, reply)

        except Exception as e:
            import traceback
            print("ERRORE NEL BOT:", repr(e), flush=True)
            traceback.print_exc()
            time.sleep(5)


if __name__ == "__main__":
    main()
