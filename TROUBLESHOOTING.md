# Report Builder – riešenie problémov

Chyby sa ladia formou patchov: pošli text z okna (dolné pole) alebo výpis z konzoly
a dostaneš „nájdi → nahraď".

Ak okno spúšťaš z ikony na ploche, výpis chyby je v `~/.report_builder.log`.

## Inštalácia a spustenie

| Príznak | Príčina | Riešenie |
|---|---|---|
| `error: externally-managed-environment` pri `pip install` | Debian nedovolí inštalovať do systémového Pythonu | inštaluj do venv: `/home/azd/Work/MEL/AZD/.venv/bin/pip install python-docx "matplotlib>=3.5"`; `--break-system-packages` nepoužívaj |
| `No module named report_builder` | príkaz beží z nesprávneho priečinka | `cd` do priečinka, v ktorom leží adresár `report_builder/` (nie doň) |
| `No module named 'docx'` alebo `'matplotlib'` | knižnice sú v inom Pythone, než ktorým spúšťaš | spúšťaj tým istým Pythonom, do ktorého si inštaloval |
| `No module named 'tkinter'` | chýba Tkinter | Debian: `sudo apt install python3-tk`; príkazový riadok (`list`, `build`) funguje aj bez neho |
| `UserWarning: Unable to import Axes3D` | matplotlib je nainštalovaný dvakrát (systém aj venv) | neškodné, 3D grafy sa nepoužívajú |
| `A module that was compiled using NumPy 1.x cannot be run in NumPy 2…` | venv vidí systémové `numexpr` / `bottleneck` | neškodné; odstráni to `pip install -U numexpr bottleneck` vo venv |
| Ikona na ploche nič nerobí | spúšťač nie je označený ako dôveryhodný, alebo okno padlo pri štarte | potvrď dôveru pri dvojkliku; pozri `~/.report_builder.log`; over `~/.local/bin/report-builder` v termináli |
| Ikona je v menu, ale nie na ploche | `.desktop` súbor je len v `~/.local/share/applications/` | skopíruj ho do `$(xdg-user-dir DESKTOP)` a nastav `chmod +x` |

## Vstup a profily

| Príznak | Príčina | Riešenie |
|---|---|---|
| V stĺpci *Data* je pri všetkých profiloch `–` | cesta vo *Input* neexistuje alebo neobsahuje očakávané súbory | pre kampaň vyber priečinok, ktorý obsahuje `TXT/`; pre mapper `*_protocol.json` |
| `pipeline_campaign` nenájde dáta, hoci `TXT/` existuje | v `TXT/*/combined/` nie sú JSON súbory | kampaň bola spracovaná pred úpravou `LIB/report_writer.py`; prepočítaj ju |
| `Profile '…' found no usable data in /cesta/k/…` | v príkaze ostala vzorová cesta | nahraď ju skutočnou; nájdeš ju cez `find ~ -name "*_protocol.json"` |
| `anomaly_mapper` nenájde dáta v priečinku | súbor sa nevolá `*_protocol.json`, alebo v ňom chýbajú kľúče `flags` a `sensors` | vyber súbor priamo tlačidlom *File…* |
| Tlačidlo *Build report* je sivé | nie je vybraný profil s dátami | vyber riadok, ktorý má v stĺpci *Data* hodnotu `found` |
| Správa ukazuje menej jázd, než má kampaň | pre niektoré jazdy chýba JSON v `TXT/<BOX>/<jazda>/` | pozri posledný riadok tabuľky zdrojov (počet jázd); prepočítaj chýbajúce |

## Obsah správy

| Príznak | Príčina | Riešenie |
|---|---|---|
| Kapitola alebo tabuľka chýba | zdrojový súbor neexistuje | pozri *Upozornenia k dátam* v kapitole Zhrnutie; je tam názov chýbajúceho súboru |
| V tabuľke je pomlčka namiesto čísla | hodnota v zdroji chýba | zámer: chýbajúca hodnota sa nezobrazuje ako nula; skontroluj zdrojový report |
| Chýba tabuľka SIL4 podľa jazdy | v `TXT/SAFE_SPEED/<jazda>/` nie je `gnss_validation.txt` | spusti krok `safe_speed` |
| Upozornenie „Zdroje pochádzajú z rôznych behov" | reporty v kampani vznikli s odstupom väčším než 12 hodín | prepočítaj celú kampaň naraz; prah je `MIXED_RUNS_HOURS` v `profiles/pipeline_campaign.py` |
| Upozornenie `sensor_validation: Error processing run …` | krok `sensor_validation` pre danú jazdu spadol | chyba je v pipeline, nie v správe; oprav ju tam a prepočítaj |
| Chýbajú grafy podľa jazdy | kampaň má len jednu jazdu | zámer: graf s jedným stĺpcom nemá význam |
| Príznak mappera má len jednu vetu | má menej než 100 sekúnd | zámer; prah je `MIN_SECONDS` v `profiles/anomaly_mapper.py` |
| Hotspotov je v tabuľke len 20 | obmedzenie tabuľky | zmeň `MAX_HOTSPOTS` v `profiles/anomaly_mapper.py`; vzorový protokol HBZ ich obsahuje 40 zo 120 |
| Čísla majú desatinnú čiarku a chceš bodku | nastavenie formátu | `DECIMAL_COMMA = False` v `core/fmt.py` |

## Dokument a šablóna

| Príznak | Príčina | Riešenie |
|---|---|---|
| Dopísané komentáre zmizli | správa sa pri každej stavbe prepíše | pred písaním správu skopíruj pod iným názvom |
| `PermissionError` pri ukladaní | DOCX je otvorený vo Worde | zavri dokument a spusti stavbu znova |
| Word sa pri otvorení pýta na aktualizáciu polí | obsah má živé odkazy na strany | potvrď *Áno*; bez toho ostanú v obsahu otázniky |
| V obsahu sú otázniky namiesto strán | polia sa neaktualizovali | Ctrl+A, potom F9 |
| Správa nemá titulnú stranu ani hlavičku | nie je vybraná šablóna | vyplň *Template* |
| Za obsahom ostal vzorový text šablóny a správa je až na konci | šablóna nemá automatický obsah | vlož ho vo Worde: Referencie → Obsah → Automatická tabuľka |
| Na titulnej strane ostal text v hranatých zátvorkách | šablóna používa iný zástupný text | použi texty z manuálu, kapitola 9, alebo doplň slovník `fill` v `core/document.py` |
| V päte je „Strana PAGE" | text `PAGE` nie je na konci odseku päty | uprav pätu šablóny tak, aby `PAGE` bolo posledné slovo, alebo vlož pole čísla strany |
| Červené vlnovky pod anglickými slovami | kontrola pravopisu editora | v tlači ani v PDF nie sú |
| Široká tabuľka má zalomené bunky | priveľa stĺpcov na výšku strany | v profile ju obaľ do `doc.landscape(True)` … `doc.landscape(False)` |

## Overenie po zmene kódu

```bash
python -m report_builder list --input <priečinok kampane>
python -m report_builder build pipeline_campaign --input <priečinok kampane> --out /tmp/rb_test
python -m report_builder build anomaly_mapper --input <protokol.json> --out /tmp/rb_test
```

Oba príkazy `build` majú skončiť riadkom `Report : …` s počtom tabuliek a grafov.
