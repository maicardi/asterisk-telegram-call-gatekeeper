# Asterisk Telegram Call Gatekeeper

**Asterisk Telegram Call Gatekeeper** è un progetto per Raspberry Pi / Asterisk che permette di gestire le chiamate deviate verso un numero SIP/VoIP, inviando notifiche Telegram e applicando comportamenti diversi in base al chiamante.

Può:

- ricevere una chiamata deviata su un trunk SIP gestito da Asterisk;
- inviare notifiche Telegram con risoluzione numero → nome contatto;
- riprodurre messaggi audio in early media senza `Answer()`;
- rispondere selettivamente e registrare messaggi in segreteria;
- normalizzare il volume dei messaggi vocali prima dell’invio a Telegram;
- gestire liste VIP, amore, famiglia e blacklist;
- salvare contatti condivisi da Telegram nella rubrica locale;
- classificare i contatti condivisi tramite bottoni inline Telegram: normale, VIP, amore, famiglia o blacklist;
- mostrare nelle liste il nome del contatto accanto al numero;
- usare prompt audio diversi per ogni categoria;
- caricare nuovi prompt audio direttamente tramite Telegram;
- controllare il comportamento del sistema tramite un bot Telegram con menu e bottoni.

Il progetto è nato su Raspberry Pi con Raspberry Pi OS / Debian 12 e un trunk SIP raggiungibile via IPv6, ma non è legato a un singolo provider.

---

## Avvertenze importanti

Il comportamento telefonico dipende molto dal provider SIP e dall’operatore mobile.

- `Answer()` risponde alla chiamata e può generare costi.
- `Progress()` + `Playback(...,noanswer)` usa early media SIP; alcuni operatori lo inoltrano correttamente, altri no.
- `Hangup(17)` normalmente corrisponde a occupato / `486 Busy Here`.
- `Hangup(21)` normalmente corrisponde a rifiuto / forbidden.
- Alcuni provider non inoltrano header come `Diversion` o `History-Info`, quindi Asterisk potrebbe non sapere quale linea originaria ha deviato la chiamata né il motivo della deviazione.
- Non pubblicare token Telegram reali, password SIP, chat ID, numeri privati o rubriche personali.

---

## Struttura del repository

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

---

## 1. Installazione di Asterisk su Raspberry Pi OS / Debian 12

Su Raspberry Pi OS Bookworm / Debian 12 il pacchetto `asterisk` potrebbe non essere disponibile tramite `apt`, a seconda dell’architettura e dei repository configurati. Questa guida usa quindi l’installazione da sorgente.

### Installare le dipendenze

```bash
sudo apt update
sudo apt install -y \
  build-essential wget curl git subversion pkg-config \
  libedit-dev libjansson-dev libxml2-dev uuid-dev \
  libsqlite3-dev libssl-dev libncurses-dev libnewt-dev \
  libcurl4-openssl-dev libspeexdsp-dev libogg-dev libvorbis-dev \
  libasound2-dev sox ffmpeg jq tcpdump
```

### Scaricare e compilare Asterisk

```bash
cd /usr/src
sudo wget https://downloads.asterisk.org/pub/telephony/asterisk/asterisk-22-current.tar.gz
sudo tar xzf asterisk-22-current.tar.gz
cd asterisk-22.*/
```

Eseguire lo script dei prerequisiti e configurare:

```bash
sudo contrib/scripts/install_prereq install
sudo ./configure
sudo make menuselect
```

In `menuselect`, verificare che siano abilitati almeno:

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

Per questo progetto non serve `format_mp3`. Se `make install` dovesse fallire cercando `format_mp3.so`, disabilitare `format_mp3` in `menuselect`.

Compilare e installare:

```bash
sudo make -j"$(nproc)"
sudo make install
sudo make samples
sudo make config
sudo ldconfig
```

Avviare Asterisk:

```bash
sudo systemctl enable --now asterisk
sudo systemctl status asterisk --no-pager
sudo asterisk -rvvv
```

Se systemd mostra un messaggio tipo:

```text
asterisk.service is not a native service
```

non è necessariamente un errore: è normale per un’installazione da sorgente che usa compatibilità SysV.

---

## 2. Verifica IPv6 e raggiungibilità SIP

Per trunk SIP IPv6, verificare prima che IPv6 funzioni:

```bash
ip -6 addr
ip -6 route
ping -6 -c 3 2606:4700:4700::1111
```

Per il proprio provider SIP:

```bash
getent ahostsv6 SIP_PROXY_HOSTNAME
ping -6 -c 3 SIP_PROXY_HOSTNAME
```

---

## 3. Configurazione PJSIP

Usare `etc/pjsip.conf.example` come base.

Copiare o integrare il contenuto in:

```bash
sudo nano /etc/asterisk/pjsip.conf
```

Poi riavviare o ricaricare Asterisk:

```bash
sudo systemctl restart asterisk
sudo asterisk -rx "pjsip show registrations"
sudo asterisk -rx "pjsip show endpoints"
sudo asterisk -rx "pjsip show transports"
```

La registrazione deve risultare:

```text
Registered
```

---

## 4. Configurazione del dialplan

Aggiungere il contenuto di `etc/extensions.conf.example` a:

```bash
sudo nano /etc/asterisk/extensions.conf
```

Poi ricaricare:

```bash
sudo asterisk -rx "dialplan reload"
sudo asterisk -rx "dialplan show from-iliad"
```

Il contesto si chiama `from-iliad` perché il progetto è nato da una configurazione Iliad. Può essere rinominato, purché il relativo endpoint PJSIP usi lo stesso `context`.

Nota importante: nel dialplan non filtrare la variabile `PROMPT`. I nomi dei file prompt possono contenere trattini, ad esempio:

```text
segreteria-famiglia
```

Filtrare `PROMPT` può trasformarlo in:

```text
segreteriafamiglia
```

e rompere la riproduzione del file.

---

## 5. Installazione del bot e degli script

Copiare il repository sul Raspberry, poi dalla directory del progetto:

```bash
sudo ./install.sh
```

Poi modificare questi file inserendo i valori reali:

```bash
sudo nano /usr/local/bin/telegram_asterisk_control.py
sudo nano /usr/local/bin/notifica_chiamata_telegram.sh
sudo nano /usr/local/bin/invia_voicemail_telegram.sh
```

Impostare:

```text
BOT_TOKEN
CHAT_ID
ALLOWED_CHAT_ID
```

Nel file Python:

```python
ALLOWED_CHAT_ID = 123456789
```

deve essere un intero, senza virgolette.

### Test del token Telegram

```bash
BOT_TOKEN="1234567890:ABC..."
curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getMe"
```

Se il token è corretto, la risposta deve contenere:

```json
{"ok":true,...}
```

Scrivere `/start` al bot e poi recuperare il proprio chat ID:

```bash
curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getUpdates"
```

---

## 6. Abilitare il bot Telegram

```bash
sudo systemctl enable --now telegram-asterisk-control.service
sudo systemctl status telegram-asterisk-control.service --no-pager
journalctl -u telegram-asterisk-control.service -f
```

Da Telegram:

```text
/menu
/status
/help
```

---

## 7. Comandi del bot

### Stato e modalità

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

Significato:

```text
notifica    → notifica Telegram + prompt early media + occupato
segreteria  → Answer(), prompt, beep, registrazione, invio audio Telegram
occupato    → prompt early media + occupato
rifiuta     → prompt early media + rifiuto
muto        → solo notifica + hangup, senza prompt audio
```

### Liste

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

Quando si mostra una lista, il bot visualizza il numero e, se presente in rubrica, anche il nome del contatto:

```text
32123455678 — Mario Rossi
```

---

## 8. Contatti condivisi da Telegram

Da smartphone è possibile condividere un contatto Telegram direttamente al bot.

Il bot:

1. normalizza il numero;
2. salva o aggiorna il contatto in:

```text
/opt/asterisk-phonebook/contacts.tsv
```

3. mostra bottoni inline per classificarlo come:

```text
Normale
VIP
Amore
Famiglia
Blacklist
```

Se si sceglie **Normale**, il contatto resta in rubrica ma viene rimosso da tutte le liste speciali.

---

## 9. Prompt audio

Comandi:

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

Per caricare un prompt audio tramite Telegram, inviare un vocale/audio/documento al bot con caption:

```text
/prompt upload amore segreteria-amore
```

Il bot converte il file in:

```text
/var/lib/asterisk/sounds/custom/segreteria-amore.wav
```

e internamente lo salva come:

```text
custom/segreteria-amore
```

Nei messaggi del bot il prefisso `custom/` viene nascosto per leggibilità.

---

## 10. Logica del comportamento

Priorità delle categorie:

```text
1. blacklist
2. amore
3. famiglia
4. VIP
5. normale
```

La blacklist ha sempre priorità assoluta:

```text
BLACKLIST → prompt blacklist / occupato / mai segreteria
```

Se `VIP_MODE=on`:

```text
VIP, amore, famiglia → segreteria
normale              → notifica / early media / occupato
blacklist            → occupato
```

Se `VIP_MODE=off`, la modalità globale `MODE` vale per tutti, tranne blacklist.

---

## 11. Creare prompt audio manualmente

Installare gli strumenti:

```bash
sudo apt install -y sox ffmpeg espeak-ng
```

### Creare un prompt TTS

```bash
espeak-ng -v it -s 140 -p 45 -w /tmp/non-raggiungibile-raw.wav \
"Il numero chiamato non è al momento raggiungibile."

sudo mkdir -p /var/lib/asterisk/sounds/custom
sudo sox /tmp/non-raggiungibile-raw.wav \
  -r 8000 -c 1 -b 16 \
  /var/lib/asterisk/sounds/custom/non-raggiungibile.wav
```

### Convertire un MP3 in WAV per Asterisk

```bash
sudo ffmpeg -y -i prompt.mp3 \
  -ar 8000 -ac 1 -sample_fmt s16 \
  /var/lib/asterisk/sounds/custom/non-raggiungibile.wav
```

Permessi:

```bash
sudo chmod 644 /var/lib/asterisk/sounds/custom/*.wav
```

---

## 12. Rubrica locale / numero → nome

La rubrica locale è:

```text
/opt/asterisk-phonebook/contacts.tsv
```

Formato:

```text
NUMERO<TAB>Nome visualizzato
```

Esempio:

```text
32123455678	Mario Rossi
```

Importare un CSV esportato da Google Contacts:

```bash
sudo /usr/local/bin/importa_google_contacts_csv.py /tmp/contacts.csv
```

Lo script importa solo le colonne Google del tipo:

```text
Phone X - Value
```

e ignora campi email o simili.

---

## 13. Debug

Console Asterisk:

```bash
sudo asterisk -rvvv
```

Comandi utili:

```asterisk
core set verbose 5
pjsip set logger on
pjsip show registrations
pjsip show endpoints
dialplan show from-iliad
```

Test dello script decisionale:

```bash
/usr/local/bin/asterisk_decidi_azione.sh 32123455678
```

Esempi di output attesi:

```text
NOTIFICA|custom/non-raggiungibile|NORMALE
SEGRETERIA|custom/segreteria-amore|AMORE
BLACKLIST|custom/occupato|BLACKLIST
```

Log del bot:

```bash
journalctl -u telegram-asterisk-control.service -f
```

Controllo sintassi Python:

```bash
python3 -m py_compile /usr/local/bin/telegram_asterisk_control.py
```

---

## 14. Note di sicurezza

- Non esporre le porte SIP di Asterisk su Internet se non sai esattamente cosa stai facendo.
- Se possibile, tieni il Raspberry dietro router/firewall.
- Non committare token Telegram reali.
- Non committare password SIP.
- Non committare rubriche personali.
- Aggiorna regolarmente il sistema operativo.
- Limita l’accesso SSH.

---

## 15. Licenza

MIT.
