# report_builder

Skladá správy (DOCX + podklady) zo strojovo čitateľných výstupov nástrojov C4R.
Jeden profil = jeden typ správy = jeden DOCX. Profily o sebe nevedia.

## Inštalácia

    pip install python-docx "matplotlib>=3.5"

## Okno (GUI)

    python -m report_builder          # alebo dvojklik na report_builder_gui.pyw

Vyber vstup (priečinok kampane alebo `*_protocol.json`), okno ukáže, ktoré profily našli dáta.
Nastavenia sa pamätajú v `~/.report_builder.json`.

## Príkazový riadok

Spúšťa sa z priečinka, v ktorom leží adresár `report_builder/`:

    python -m report_builder list --input <priečinok>
    python -m report_builder build anomaly_mapper --input <priečinok alebo *_protocol.json> \
        --template technicka_sprava_sablona.docx --out report_out --author "Meno Priezvisko"

Výstup v `report_out/<profil>_<kampaň>/`:

- `report_<profil>_<kampaň>.docx` – správa so slotmi `[Komentár: …]` na vlastný text
- `tables/*.csv` – každá tabuľka zo správy (UTF-8 BOM, oddeľovač `;`)
- `figures/*.png` – každý graf zo správy

Obsah a čísla strán sú živé odkazy, netreba ich ručne aktualizovať.

## Profily

| Profil | Vstup (`--input`) | Čo číta |
|---|---|---|
| `anomaly_mapper` | `*_protocol.json` alebo jeho priečinok | protokol anomaly_mapper |
| `pipeline_campaign` | priečinok kampane (obsahuje `TXT/`) | JSON z `TextReport` v `TXT/<BOX>/combined` a `TXT/<BOX>/<jazda>`; SIL4 podľa jazdy zatiaľ z `gnss_validation.txt` |

## Štruktúra

    core/sources.py    načítanie JSON (aj TextReport sidecar z LIB/report_writer.py), výber najnovšieho súboru
    core/document.py   DOCX: šablóna, nadpisy, tabuľky, obrázky, komentáre, zdroje
    core/charts.py     statické grafy (matplotlib)
    core/fmt.py        formát čísel (DECIMAL_COMMA)
    profiles/          jeden súbor = jeden typ správy

## Nový profil

Pridaj `profiles/<meno>.py` s `NAME`, `TITLE`, `SUBTITLE`, `DESCRIPTION`,
`find_inputs(path)` a `build(inputs, doc)`. Nič iné sa nemení.
