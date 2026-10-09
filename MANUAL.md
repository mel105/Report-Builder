# Report Builder – manuál

Verzia 0.3.1

## 1. Na čo to je

Report Builder zoberie výsledky spracovania (JSON súbory) a zloží z nich správu vo Worde:
tabuľky, grafy, obsah a miesta na komentár. Komentáre dopíše autor.

Dve zásady:

- **Profil určuje typ správy.** `pipeline_campaign` a `anomaly_mapper` sú dve samostatné
  správy. Výsledky jedného sa nikdy samy nedostanú do správy druhého.
- **Správa sa vždy stavia nanovo zo zdrojov.** DOCX je výsledok, nie pracovný dokument.

## 2. Inštalácia

### Linux (Debian)

```bash
cd ~/Dev/Projects/Personal/"Report Builder"
/home/xxx/Work/xxx/xxx/.venv/bin/pip install python-docx "matplotlib>=3.5"
/home/xxx/Work/xxx/xxx/.venv/bin/python -c "import docx, matplotlib, tkinter; print('OK')"
/home/xxx/Work/xxx/xxx/.venv/bin/python -m report_builder
```

Ak chýba Tkinter: `sudo apt install python3-tk`.

### Windows

```
pip install python-docx "matplotlib>=3.5"
```

Potom dvojklik na `report_builder_gui.pyw`, prípadne odkaz na plochu.

### Ikona na ploche (Linux, Xfce)

```bash
mkdir -p ~/.local/bin
cat > ~/.local/bin/report-builder <<'END'
#!/bin/bash
cd "/home/xxx/Dev/Projects/Personal/Report Builder" || exit 1
exec /home/xxx/Work/xxx/xxx/.venv/bin/python -m report_builder >"$HOME/.report_builder.log" 2>&1
END
chmod +x ~/.local/bin/report-builder

cat > ~/.local/share/applications/report-builder.desktop <<'END'
[Desktop Entry]
Type=Application
Name=Report Builder
Exec=/home/azd/.local/bin/report-builder
Icon=x-office-document
Terminal=false
Categories=Development;
END
cp ~/.local/share/applications/report-builder.desktop "$(xdg-user-dir DESKTOP)/"
chmod +x "$(xdg-user-dir DESKTOP)/report-builder.desktop"
```

Pri prvom dvojkliku potvrď, že spúšťaču dôveruješ.

## 3. Príprava zdrojov

### pipeline_campaign

Správa číta JSON súbory, ktoré `LIB/report_writer.py` (trieda `TextReport`) zapisuje
vedľa každého `.txt` reportu. Staršie behy pipeline ich nemajú, preto:

1. `LIB/report_writer.py` musí obsahovať zápis JSON (metóda `write()`).
2. Kampaň treba prepočítať, aby JSON vznikli vo všetkých boxoch.

Očakávaná štruktúra:

```
<kampaň>/TXT/<BOX>/combined/*.json      súhrny za kampaň
<kampaň>/TXT/<BOX>/<jazda>/*.json       reporty za jazdu
```

### anomaly_mapper

Stačí protokol `<kampaň>_protocol.json`, ktorý mapper zapisuje sám. Ak vedľa neho leží
`<kampaň>_events.csv`, uvedie sa v zdrojoch správy.

## 4. Okno

| Prvok | Význam |
|---|---|
| **Input** | priečinok kampane (obsahuje `TXT/`) alebo `*_protocol.json` |
| **Report type** | zoznam profilov; stĺpec *Data* ukazuje `found`, ak profil vo vstupe našiel dáta |
| **Template** | šablóna DOCX; bez nej správa nemá titulnú stranu, hlavičku ani obsah |
| **Output folder** | kam sa uloží výstup (predvolene `~/report_out`) |
| **Author**, **Status** | vyplnia sa na titulnej strane (`Draft` / `Final`) |
| **Build report** | postaví správu; aktívne len pri profile s dátami |
| **Open report**, **Open output folder** | otvorí výsledok v systémovej aplikácii |

Zoznam profilov sa obnoví sám po zmene vstupu. Profil bez dát je sivý.

Po skončení okno vypíše počet tabuliek a grafov, cesty a **upozornenia k dátam**.
Tie isté upozornenia sú aj v kapitole Zhrnutie.

Nastavenia okna sa ukladajú do `~/.report_builder.json`.

## 5. Príkazový riadok

```bash
python -m report_builder list --input <vstup>
python -m report_builder build <profil> --input <vstup> [voľby]
```

| Voľba | Význam | Predvolené |
|---|---|---|
| `--input` | súbor alebo priečinok so zdrojmi | povinné |
| `--out` | výstupný priečinok | `report_out` |
| `--template` | šablóna DOCX | bez šablóny |
| `--author` | autor na titulnej strane | prázdne |
| `--status` | stav dokumentu | `Draft` |

Príkaz musí bežať z priečinka, v ktorom leží adresár `report_builder/`.

## 6. Výstup

```
<out>/<profil>_<kampaň>/
├── report_<profil>_<kampaň>.docx
├── tables/     CSV, UTF-8 s BOM, oddeľovač ; (Excel otvorí priamo)
└── figures/    PNG, 200 dpi
```

**Pri opätovnom spustení sa celý výstup prepíše, vrátane DOCX.** Komentáre dopísané
do správy sa stratia. Pred písaním si správu skopíruj pod iným názvom.

V správe sú sivé kurzívou písané riadky `[Komentár: …]`. Označujú miesto, kde sa čaká
text autora, a napovedajú, čo tam patrí.

## 7. Správa pipeline_campaign

| Kapitola | Obsah | Zdroj (`TXT/…`) |
|---|---|---|
| Zhrnutie | kľúčové čísla kampane, upozornenia k dátam | zo všetkých kapitol |
| 1 Vstupné dáta | charakteristiky kampane, tabuľka jázd, import GNSS | `BIN2ODO/combined`, `ODO/<jazda>/*_data_intake_report`, `*_time_reconstruction_report`, `GNSS_IMPORTER/combined`, `RESAMPLER/combined` |
| 2 Kvalita dát | anomálie v ms dátach, validácia senzorov, prevzorkovanie | `ODO/<jazda>/*_anomaly_detection_report`, `*_sensor_processing_report`, `SENSOR_VALIDATION/combined`, `RESAMPLER/combined` |
| 3 Kalibrácia senzorov | blind modely; pre každý senzor súhrn, tabuľka podľa jazdy, graf RMS, rezíduá, čistenie dát | `SAFE_SPEED/combined/blind_model_summary`, `CALIBRATOR/<senzor>/combined/calibration_results`, `data_cleaning` |
| 4 Bezpečná rýchlosť | súhrn kampane, SIL4 podľa jazdy | `SAFE_SPEED/combined/batch_summary_*`, `campaign_compliance_*`, `SAFE_SPEED/<jazda>/gnss_validation.txt` |
| 5 Chyby voči GNSS | štatistiky kampane, chyby a bias pri státí podľa jazdy, robustné σ, korelácie | `ERRORS/combined/*` |
| Zdroje správy | každý použitý súbor a čas jeho vzniku | – |

Pravidlá:

- **Pri viacerých súboroch s časom v názve sa berie najnovší** (`batch_summary_*`,
  `cross_run_summary_*` a pod.).
- **Chýbajúci zdroj nezhodí stavbu.** Príslušná časť sa vynechá a pribudne upozornenie.
- **Chýbajúca hodnota sa zobrazí ako pomlčka**, nikdy ako nula.
- **Grafy podľa jazdy sa kreslia až od dvoch jázd.**
- **Druhý otáčkomer (WIG2) je simulovaný**: má tabuľky, graf nie.
- **SIL4 podľa jazdy sa číta z textového súboru** `gnss_validation.txt`, lebo tento
  report zatiaľ nemá JSON.

### Upozornenia k dátam

Vzniknú automaticky v týchto prípadoch:

| Upozornenie | Kedy |
|---|---|
| chýba zdroj | očakávaný súbor v `combined` neexistuje |
| chýbajúce sekundy | súčet chýbajúcich sekúnd v časovej osi je väčší než 0 |
| chyba v `sensor_validation` | report obsahuje sekciu *Errors Encountered* |
| jazda nevyhovuje SIL4 | `SIL4 ASSESSMENT: FAIL` v `gnss_validation.txt` |
| zdroje z rôznych behov | najstarší a najnovší zdroj delí viac než 12 hodín |

## 8. Správa anomaly_mapper

| Kapitola | Obsah | Kľúč v protokole |
|---|---|---|
| 1 Dáta a nastavenie | rozsah dát, prahy a profily detektorov | `data`, `settings` |
| 2 Mierka senzorov voči GNSS | model mierky, rozdelenie podľa orientácie vozidla | `scale_vs_gnss`, `scale_by_vehicle_direction` |
| 3 Príznaky anomálií | tabuľka všetkých príznakov, graf podielu sekúnd | `flags` |
| 4 Radar: potvrdené vs. ohlásené | rozdelenie podľa stavového slova, orientácie a smeru | `radar_confirmed_split`, `vehicle_direction`, `direction`, `runs_by_vehicle_direction` |
| 5–9 Jednotlivé príznaky | `R_CONF`, `R_SILENT`, `W_CONF`, `W_SLIP`, `W_SLIDE`: členenie podľa rýchlosti, zrýchlenia, smeru a vibrácií, objekty pri trati, hotspoty | `sensors` |
| 10 Vývoj v čase, počasie a IMU | mesiace, mokro/sucho, otrasy pred udalosťou | `by_month`, `by_weather`, `imu_events` |
| 11 Jazdy | graf potvrdených anomálií radaru podľa jazdy | `runs` |
| Príloha A | zoznam jázd (na šírku) | `runs` |

Pravidlá:

- **Príznak bez výskytu** dostane vetu „Žiadna sekunda s týmto príznakom."
- **Príznak s menej než 100 sekundami** dostane len súhrnnú vetu, bez členenia.
- **V tabuľke hotspotov je prvých 20**, v grafe pozdĺž trate všetky, ktoré protokol obsahuje.
- **Názvy príznakov a objektov sú po anglicky**, tak ako v protokole.

## 9. Šablóna

Report Builder šablónu nemení, pracuje s jej kópiou. Urobí s ňou toto:

1. **Titulná strana:** druhý neprázdny odsek pred prvým nadpisom nahradí podnadpisom správy.
2. **Zástupné texty** nahradí v celom dokumente:

   | V šablóne | Nahradí sa |
   |---|---|
   | `[NAZOV KAMPANE]`, `[NAZOV]` | názov kampane |
   | `[DD.MM.RRRR]` | dnešný dátum |
   | `[Meno Priezvisko]`, `[Meno]` | autor |
   | `Draft / Final` | stav |

3. **Hlavička:** odsek obsahujúci `Kampaň:` prepíše na „Technická správa – názov správy | Kampaň: …".
4. **Päta:** text `PAGE` na konci odseku zmení na skutočné číslo strany.
5. **Obsah:** pôvodný obsah odstráni a vloží vlastný (úrovne 1 a 2) so živými odkazmi na strany.
6. **Vzorové kapitoly** za obsahom odstráni a na ich miesto vloží kapitoly správy.

Požiadavky na vlastnú šablónu:

- štýly `Heading 1` a `Heading 2`,
- automatický obsah vložený cez Word (Referencie → Obsah); bez neho sa vzorový text
  šablóny neodstráni a správa sa pripojí na koniec bez obsahu,
- štýl `List Paragraph` pre zoznam upozornení (voliteľné).

Vzhľad tabuliek (rámik, podfarbenie hlavičky) je daný v `core/document.py`
konštantami `HEADER_FILL` a `BORDER`.

## 10. Formát čísel

Správy používajú desatinnú čiarku a medzeru ako oddeľovač tisícov. Prepína sa to
v `core/fmt.py`:

```python
DECIMAL_COMMA = True    # False = desatinná bodka
```

Čísla prevzaté zo zdrojov sa prepisujú automaticky (`10,337,673` → `10 337 673`,
`0.3050` → `0,3050`). Celé čísla bez oddeľovača tisícov, napríklad identifikátory jázd,
ostávajú bez zmeny.

## 11. Pridanie nového profilu

Vytvor `report_builder/profiles/<meno>.py`. Nič iné sa nemení, okno aj príkazový
riadok profil nájdu samy.

```python
from pathlib import Path
from typing import List, Optional

from ..core.document import DocBuilder
from ..core.sources import Source, load_json

NAME = "moj_profil"
TITLE = "Krátky názov správy"            # do hlavičky
SUBTITLE = "Podnadpis na titulnú stranu"
DESCRIPTION = "Jedna veta do zoznamu profilov."


def find_inputs(path: Path) -> Optional[dict]:
    """Vráti slovník so zdrojmi, alebo None, ak v `path` nie sú použiteľné dáta."""
    src = Path(path) / "vysledky.json"
    if not src.exists():
        return None
    data = load_json(src)
    return {"file": src, "data": data, "campaign": data.get("campaign", ""),
            "warnings": []}               # "warnings" je voliteľné


def build(inputs: dict, doc: DocBuilder) -> List[Source]:
    doc.heading("Prvá kapitola")
    doc.table("Popis tabuľky", ["Stĺpec A", "Stĺpec B"], [["x", "1"], ["y", "2"]])
    doc.comment("čo sem má autor napísať")
    return [Source(inputs["file"], inputs["data"].get("generated", ""))]
```

Kľúč `campaign` sa použije v názve výstupu a na titulnej strane. Zoznam `warnings`
sa po stavbe vypíše v okne.

Čo ponúka `DocBuilder`:

| Metóda | Účel |
|---|---|
| `heading(text, level=1, numbered=True)` | nadpis, číslovaný automaticky |
| `para(text, italic=False)` | odsek |
| `comment(hint)` | miesto na komentár autora |
| `table(caption, columns, rows, align=None, name=None)` | tabuľka; uloží aj CSV |
| `key_value(caption, pairs)` | tabuľka Parameter / Hodnota |
| `figure(caption, png)` | obrázok s popisom |
| `fig_path(name)` | cesta, kam uložiť PNG grafu |
| `landscape(True / False)` | strany na šírku pre široké tabuľky |
| `page_break()` | zlom strany |

Grafy sú v `core/charts.py`: `hbar`, `grouped_bars`, `panels`, `category_bars`,
`along_track`. Čísla formátuj cez `core/fmt.py`: `num(hodnota, desatinné)` pre čísla,
`loc(text)` pre text prevzatý zo zdroja.

Číslovanie tabuliek a obrázkov a obsah vzniknú pri uložení, netreba ich riešiť.
