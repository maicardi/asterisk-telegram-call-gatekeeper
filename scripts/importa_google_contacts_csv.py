#!/usr/bin/env python3

import csv
import re
import sys
from pathlib import Path

CSV_PATH = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/contacts.csv")
OUT_PATH = Path("/opt/asterisk-phonebook/contacts.tsv")


def normalize_number(raw: str) -> str:
    if not raw:
        return ""

    n = raw.strip()

    if "@" in n:
        return ""

    n = n.split(":::")[0].strip()
    n = re.sub(r"[^\d+]", "", n)

    if not n:
        return ""

    if n.startswith("+39"):
        n = n[3:]
    elif n.startswith("0039"):
        n = n[4:]
    elif n.startswith("39") and len(n) >= 11:
        n = n[2:]

    if len(n) < 7:
        return ""

    if set(n) == {"0"}:
        return ""

    return n


def clean_part(value: str) -> str:
    return (value or "").strip().strip('"').strip()


def build_name(row: dict) -> str:
    first = clean_part(row.get("First Name", ""))
    middle = clean_part(row.get("Middle Name", ""))
    last = clean_part(row.get("Last Name", ""))
    nickname = clean_part(row.get("Nickname", ""))
    file_as = clean_part(row.get("File As", ""))
    org = clean_part(row.get("Organization Name", ""))

    person = " ".join(x for x in [first, middle, last] if x).strip()

    if person:
        return person
    if nickname:
        return nickname
    if file_as:
        return file_as
    if org:
        return org

    return ""


def main():
    if not CSV_PATH.exists():
        print(f"File non trovato: {CSV_PATH}", file=sys.stderr)
        sys.exit(1)

    contacts = {}

    with CSV_PATH.open("r", encoding="utf-8-sig", errors="ignore", newline="") as f:
        sample = f.read(8192)
        f.seek(0)

        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel

        reader = csv.DictReader(f, dialect=dialect)

        if not reader.fieldnames:
            print("CSV senza intestazioni valide.", file=sys.stderr)
            sys.exit(1)

        phone_value_cols = [
            col for col in reader.fieldnames
            if re.match(r"^Phone \d+ - Value$", col or "", re.IGNORECASE)
        ]

        if not phone_value_cols:
            print("Non ho trovato colonne 'Phone X - Value'.", file=sys.stderr)
            sys.exit(1)

        for row in reader:
            name = build_name(row)

            for col in phone_value_cols:
                number = normalize_number(row.get(col, ""))

                if not number:
                    continue

                contacts[number] = name or number

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUT_PATH.open("w", encoding="utf-8") as out:
        for number in sorted(contacts):
            out.write(f"{number}\t{contacts[number]}\n")

    print(f"Importati {len(contacts)} numeri in {OUT_PATH}")


if __name__ == "__main__":
    main()
