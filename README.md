# Report Builder

Skladá technické správy (DOCX) a podklady k nim (CSV tabuľky, PNG grafy) zo strojovo
čitateľných výstupov nástrojov Codes4Rail. Text komentárov píše autor, všetko ostatné
vznikne jedným kliknutím.

- **Jeden profil = jeden typ správy = jeden DOCX.** Profily o sebe nevedia.
- **Správa vzniká na firemnej šablóne**: titulná strana, hlavička, päta a obsah.
- **Každá tabuľka a graf sa uloží aj samostatne**, takže výstup slúži aj ako podklad
  pre ručne písaný dokument.

Verzia 0.3.1.

## Profily

| Profil | Správa | Vstup |
|---|---|---|
| `pipeline_campaign` | Odhad bezpečnej rýchlosti – spracovanie kampane pipeline | priečinok kampane (obsahuje `TXT/`) |
| `anomaly_mapper` | Analýza anomálií senzorov | `<kampaň>_protocol.json` alebo jeho priečinok |

## Požiadavky

- Python 3.9 alebo novší (overené na 3.11 až 3.13)
- `python-docx`, `matplotlib` 3.5 alebo novší
- Tkinter (len pre okno; na Debiane balík `python3-tk`)

```bash
pip install python-docx "matplotlib>=3.5"
```

Na Debiane inštaluj do virtuálneho prostredia, nie do systémového Pythonu.

## Spustenie

Príkazy sa spúšťajú z priečinka, v ktorom leží adresár `report_builder/`.

```bash
python -m report_builder                 # okno
python -m report_builder list --input <vstup>
python -m report_builder build <profil> --input <vstup> \
    --template <šablóna.docx> --out <priečinok> --author "Meno Priezvisko"
```

Okno sa dá spustiť aj dvojklikom na `report_builder_gui.pyw`.

## Výstup

```
<out>/<profil>_<kampaň>/
├── report_<profil>_<kampaň>.docx
├── tables/     každá tabuľka zo správy ako CSV (UTF-8 s BOM, oddeľovač ;)
└── figures/    každý graf zo správy ako PNG (200 dpi)
```

## Štruktúra kódu

```
report_builder/
├── __main__.py          príkazový riadok
├── gui.py               okno (Tkinter)
├── core/
│   ├── build.py         stavba správy – spoločná pre okno aj príkazový riadok
│   ├── sources.py       načítanie JSON, výber najnovšieho súboru
│   ├── document.py      DOCX: šablóna, nadpisy, tabuľky, obrázky, obsah, zdroje
│   ├── charts.py        statické grafy (matplotlib)
│   └── fmt.py           formát čísel
└── profiles/            jeden súbor = jeden typ správy
report_builder_gui.pyw   spúšťač okna
```

## Dokumentácia

- [MANUAL.md](MANUAL.md) – použitie, obsah správ, šablóna, pridanie profilu
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) – riešenie problémov

Autor: MEL
