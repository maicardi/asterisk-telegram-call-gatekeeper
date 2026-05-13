# Dialplan notes

`asterisk_decidi_azione.sh` returns:

```text
AZIONE|PROMPT|CATEGORIA
```

Example:

```text
SEGRETERIA|custom/segreteria-famiglia|FAMIGLIA
```

In the Asterisk dialplan, filter `AZIONE` and `CATEGORIA`, but do **not** filter `PROMPT`.

Bad:

```ini
Set(PROMPT=${FILTER(a-zA-Z0-9/_.,-,${PROMPT})})
```

This may remove `-` from filenames.

Good:

```ini
Set(AZIONE=${FILTER(A-Z,${AZIONE})})
Set(CATEGORIA=${FILTER(A-Z,${CATEGORIA})})
```
