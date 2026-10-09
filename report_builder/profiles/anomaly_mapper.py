"""Report from the anomaly_mapper protocol (<campaign>_protocol.json).

Standalone report: it reads nothing from the processing pipeline.
"""
from pathlib import Path
from typing import List, Optional

from ..core import charts
from ..core.document import DocBuilder
from ..core.fmt import num, pct
from ..core.sources import Source, load_json, newest

NAME = "anomaly_mapper"
TITLE = "Analýza anomálií senzorov"
SUBTITLE = "Mapovanie anomálií radaru a otáčkomera (anomaly_mapper)"
DESCRIPTION = "Samostatná správa z protokolu anomaly_mapper (*_protocol.json)."

# Sensor blocks of the protocol -> chapter titles
SENSOR_TITLES = {
    "radar": "Radar: potvrdené anomálie",
    "radar silent": "Radar: tiché anomálie (stavové slovo platné)",
    "wheel": "Otáčkomer: potvrdené anomálie",
    "wheel slip": "Otáčkomer: preklz (slip)",
    "wheel slide": "Otáčkomer: šmyk (slide)",
}
FLAG_GROUPS = [("R_", "Radar"), ("W_", "Otáčkomer"), ("X_", "Radar vs. otáčkomer"), ("Q_", "Kvalita dát")]
MAX_HOTSPOTS = 20
MIN_SECONDS = 100   # below this a flag gets one sentence, no breakdowns


def find_inputs(path: Path) -> Optional[dict]:
    path = Path(path)
    protocol = path if path.is_file() else newest(path, "*_protocol.json")
    if protocol is None or protocol.suffix != ".json":
        return None
    data = load_json(protocol)
    if "flags" not in data or "sensors" not in data:
        return None
    events = protocol.with_name(protocol.name.replace("_protocol.json", "_events.csv"))
    return {"protocol": protocol, "data": data, "events": events if events.exists() else None,
            "campaign": data.get("campaign", "")}


def build(inputs: dict, doc: DocBuilder) -> List[Source]:
    d = inputs["data"]
    _data(doc, d)
    _scale(doc, d)
    _flags(doc, d)
    _radar_split(doc, d)
    for key, title in SENSOR_TITLES.items():
        if key in d["sensors"]:
            _sensor(doc, d, key, title)
    _conditions(doc, d)
    _runs(doc, d)
    sources = [Source(inputs["protocol"], d.get("generated", ""),
                      f"anomaly_mapper {d.get('version', '')}, DB {Path(d.get('database', '')).name}")]
    if inputs["events"]:
        sources.append(Source(inputs["events"], "", "zoznam udalostí, v správe sa neuvádza"))
    return sources


# ---------------------------------------------------------------------- chapters
def _data(doc, d) -> None:
    x, s = d["data"], d["settings"]
    doc.heading("Dáta a nastavenie")
    failed = ", ".join(x["runs_failed"]) or "žiadne"
    doc.key_value("Rozsah spracovaných dát", [
        ["Jazdy spracované / celkom", f"{x['runs_ok']} / {x['runs_total']}"],
        ["Jazdy s chybou", failed],
        ["Obdobie (UTC, začiatky jázd)", f"{x['first_run_utc']} – {x['last_run_utc']}"],
        ["Sekundy celkom", num(x["seconds_total"])],
        ["Sekundy analyzované", num(x["seconds_analysed"])],
        ["GNSS rýchlosť dostupná [%]", num(x["pct_with_gnss_speed"], 1)],
        ["GNSS poloha dostupná [%]", num(x["pct_with_position"], 1)],
        ["GNSS fix [%]", num(x["pct_gnss_fix"], 1)],
        ["Trať [km]", f"{num(x['track_km_from'], 3)} – {num(x['track_km_to'], 3)}"],
        ["Úseky trate (biny)", f"{num(x['track_bins'])} po {num(s['bins']['size_m'])} m"],
        ["Objekty z OSM", num(x["osm_objects"])],
        ["Chýbajúci COUNTER", num(x["counter_missing_total"])],
        ["PPS intervaly ≠ 1000 vzoriek", num(x["pps_not_1000_total"])],
        ["Nesúlad NAV-TIMEUTC [s]", num(x["nav_mismatch_total"])],
    ])
    f = s["flags"]
    doc.key_value("Použité prahy a nastavenie detektorov", [
        ["Profil detektora radaru", s["radar_detector_profile"]],
        ["Profil detektora otáčkomera", s["wheel_detector_profile"]],
        ["Platné kódy stavového slova radaru", ", ".join(str(c) for c in s["radar_valid_sw_codes"])],
        ["Štatistiky od rýchlosti [km/h]", num(s["speed_filter_from_kmh"], 1)],
        ["conf_kmh", num(f["conf_kmh"], 1)],
        ["slip_kmh", num(f["slip_kmh"], 1)],
        ["raw_kmh", num(f["raw_kmh"], 1)],
        ["grad_kmh_s", num(f["grad_kmh_s"], 1)],
        ["gnss2_k_sigma", num(f["gnss2_k_sigma"], 1)],
        ["det_min_samples / wdet_min_samples / sw_min_samples",
         f"{f['det_min_samples']} / {f['wdet_min_samples']} / {f['sw_min_samples']}"],
        ["Hotspot: min. počet prejazdov binom", num(s["bins"]["min_passes"])],
    ])
    doc.comment("zhodnotenie úplnosti dát a voľby prahov")


def _scale(doc, d) -> None:
    doc.heading("Mierka senzorov voči GNSS (pred kalibráciou)")
    doc.para("Model: GNSS = a0 + a1·v + a_dvdt·dv/dt. Stĺpec „ukazuje“ udáva, o koľko percent "
             "senzor ukazuje viac (+) alebo menej (−) než GNSS.")
    rows = []
    for key, label in (("radar", "radar"), ("wheel", "otáčkomer")):
        m = d["scale_vs_gnss"][key]
        rows.append([label, num(m["a0_kmh"], 3), num(m["a1"], 4), num(m["a_dvdt"], 3),
                     num(m["sensor_reads_pct"], 2, sign=True),
                     " / ".join(num(v, 3) for v in m["sigma1_kmh"]), num(m["n_fit"])])
    doc.table("Mierka senzorov voči GNSS", ["Senzor", "a0 [km/h]", "a1", "a_dvdt", "Ukazuje [%]",
                                           "σ1 (MAD) [km/h]", "N"], rows)
    label = {"radar": "radar", "wheel": "otáčkomer"}
    rows = [[label[r["sensor"]], r["veh"], num(r["n"]), num(r["a1"], 4),
             num(r["sensor_reads_pct"], 2, sign=True), num(r["mean_diff_kmh"], 3, sign=True),
             num(r["sigma_mad_kmh"], 3)] for r in d["scale_by_vehicle_direction"]]
    doc.table("Mierka podľa orientácie vozidla", ["Senzor", "Orientácia", "Sekundy", "a1",
                                                 "Ukazuje [%]", "Senzor − GNSS [km/h]",
                                                 "σ (MAD) [km/h]"], rows, align="llrrrrr")
    doc.comment("interpretácia mierky a rozdielu medzi orientáciami vozidla")


def _flags(doc, d) -> None:
    doc.heading("Príznaky anomálií")
    doc.para("Percentá sú podiely zo sekúnd v pohybe pri rýchlosti aspoň "
             f"{num(d['settings']['speed_filter_from_kmh'], 1)} km/h.")
    flags = d["flags"]
    doc.table("Prehľad príznakov", ["Kľúč", "Príznak", "Sekundy", "% sekúnd", "Jazdy"],
              [[f["key"], f["label"], num(f["seconds"]), num(f["pct"], 3), f["runs"]] for f in flags],
              align="llrrr")
    shown = [f for f in flags if f["seconds"] > 0]
    colour = {prefix: charts.SERIES[i] for i, (prefix, _) in enumerate(FLAG_GROUPS)}
    png = charts.hbar([f["key"] for f in shown], [f["pct"] for f in shown], doc.fig_path("flags"),
                      "% sekúnd", colors=[colour[f["key"][:2]] for f in shown],
                      legend=[(name, colour[prefix]) for prefix, name in FLAG_GROUPS])
    doc.figure("Podiel sekúnd s jednotlivými príznakmi (príznaky bez výskytu sú vynechané)", png)
    doc.comment("ktoré príznaky dominujú a prečo")


def _radar_split(doc, d) -> None:
    s = d["radar_confirmed_split"]
    doc.heading("Radar: potvrdené anomálie a hlásenie stavovým slovom")
    doc.key_value("Potvrdené anomálie radaru podľa toho, či ich radar sám ohlásil", [
        ["Potvrdené anomálie [s]", num(s["confirmed_seconds"])],
        ["– ohlásené neplatným stavovým slovom [s]",
         f"{num(s['announced_by_status_word'])} ({num(s['announced_pct'], 1)} %)"],
        ["– tiché, stavové slovo platné [s]",
         f"{num(s['silent_status_word_valid'])} ({num(s['silent_pct'], 1)} %)"],
        ["Sekundy s neplatným stavovým slovom", num(s["invalid_sw_seconds"])],
        ["– z nich potvrdená odchýlka [%]", num(s["invalid_sw_confirmed_pct"], 1)],
        ["Sekundy označené ms detektorom", num(s["detector_seconds"])],
        ["– z nich potvrdená odchýlka [%]", num(s["detector_confirmed_pct"], 1)],
    ])
    doc.table("Radar podľa orientácie vozidla (znamienko impulzov otáčkomera)",
              ["Orientácia", "Sekundy", "Neplatné SW [%]", "Potvrdené [%]"],
              [[r["direction"], num(r["seconds"]), num(r["invalid_sw_pct"], 2),
                num(r["confirmed_pct"], 2)] for r in d["vehicle_direction"]])
    doc.table("Radar podľa smeru jazdy (znamienko GNSS rýchlosti)",
              ["Smer", "Sekundy", "Neplatné SW [%]", "Potvrdené [%]"],
              [[r["direction"], num(r["seconds"]), num(r["invalid_sw_pct"], 2),
                num(r["confirmed_pct"], 2)] for r in d["direction"]])
    rows = [[r["veh"], r["runs"], num(r["moving_s"]), num(r["r_conf_pct"], 2),
             num(r["r_conf_pct_min"], 2), num(r["r_conf_pct_max"], 2),
             num(r["bad_sw_samples_per_moving_s"], 2), num(r["detector_samples_per_moving_s"], 2)]
            for r in d["runs_by_vehicle_direction"]]
    doc.table("Jazdy zoskupené podľa orientácie vozidla",
              ["Orientácia", "Jazdy", "Pohyb [s]", "Potvrdené [%]", "Min. jazda [%]",
               "Max. jazda [%]", "Zlé SW vzorky / s", "Vzorky detektora / s"], rows)
    doc.comment("vplyv orientácie vozidla na radar")


def _sensor(doc, d, key: str, title: str) -> None:
    s = d["sensors"][key]
    doc.heading(f"{title} ({s['flag']})")
    total = next((f["seconds"] for f in d["flags"] if f["key"] == s["flag"]), 0)
    if total == 0:
        doc.para("Žiadna sekunda s týmto príznakom.")
        return
    text = (f"Príznak má {num(total)} s. Podiel prejazdov binmi s príznakom: "
            f"{pct(s['share_of_bin_passes'])} %, počet hotspotov: {s['n_hotspots']}.")
    c = s.get("concentration")
    if c:
        text += (f" Najhorších 5 % binov obsahuje {pct(c['top5_share'], 0)} % označených prejazdov "
                 f"(náhodné rozloženie by dalo {pct(c['top5_expected'], 0)} %); "
                 f"{pct(c['repeat_share'], 0)} % zasiahnutých binov sa opakuje v aspoň 2 jazdách.")
    doc.para(text)
    if total < MIN_SECONDS:
        # Too few seconds for shares and places to mean anything.
        doc.comment(f"príznak má len {num(total)} s, bez ďalšieho členenia")
        return
    slug = key.replace(" ", "_")
    breakdowns = [("Rýchlosť [km/h]", "by_speed"), ("Zrýchlenie", "by_acceleration"),
                  ("Smer jazdy", "by_direction"), ("Vibrácie", "by_vibration")]
    for name, field in breakdowns:
        doc.table(f"{s['flag']} podľa veličiny: {name}", [name, "Sekundy", "S príznakom", "%"],
                  [[_group(r["g"]), num(r["secs"]), num(r["flag"]), pct(r["rate"], 3)]
                   for r in s[field]], name=f"{slug}_{field}")
    png = charts.panels([(name, [_group(r["g"]) for r in s[field]],
                          [100 * r["rate"] for r in s[field]]) for name, field in breakdowns],
                        doc.fig_path(f"{slug}_breakdowns"), "% sekúnd")
    doc.figure(f"{s['flag']}: podiel sekúnd s príznakom podľa rýchlosti, zrýchlenia, smeru a vibrácií", png)

    cats = s["object_categories"]
    doc.table(f"{s['flag']} v okolí objektov (prejazdy binmi do 50 m od objektu)",
              ["Kategória", "Objekty", "Biny", "Prejazdy", "S príznakom", "%", "× voči bez objektu",
               "% voz. fwd", "% voz. rev"],
              [[r["label"], r["objects"], r["bins"], num(r["passes"]), num(r["flagged"]),
                pct(r["rate"]), num(r["ratio_vs_no_object"], 1), pct(r.get("rate_veh_fwd")),
                pct(r.get("rate_veh_rev"))] for r in cats], name=f"{slug}_objects")
    with_obj = [r for r in cats if r["cat"] != "_none"]
    base = next((r for r in cats if r["cat"] == "_none"), None)
    png = charts.hbar([r["label"] for r in with_obj], [100 * r["rate"] for r in with_obj],
                      doc.fig_path(f"{slug}_objects"), "% prejazdov s príznakom",
                      ref=(100 * base["rate"], "bez objektu do 50 m") if base else None)
    doc.figure(f"{s['flag']}: podiel označených prejazdov v okolí objektov", png)

    hot = s["hotspots"]
    if hot:
        shown = hot[:MAX_HOTSPOTS]
        doc.table(f"{s['flag']}: hotspoty (prvých {len(shown)} z {s['n_hotspots']}, zoradené podľa z)",
                  ["km od", "km do", "Prejazdy", "S príznakom", "%", "Jazdy", "z", "km/h",
                   "Objekty do 50 m"],
                  [[num(h["jok_from"] / 1000, 3), num(h["jok_to"] / 1000, 3), h["visits"],
                    h["flagged"], pct(h["rate"], 0), h["runs_f"], num(h["z"], 1),
                    num(h["speed"], 0), _objects(h["objects"])] for h in shown],
                  align="rrrrrrrrl", name=f"{slug}_hotspots")
        png = charts.along_track([(h["jok_from"] + h["jok_to"]) / 2000 for h in hot],
                                 [100 * h["rate"] for h in hot],
                                 doc.fig_path(f"{slug}_hotspots"), "% prejazdov s príznakom")
        doc.figure(f"{s['flag']}: poloha hotspotov pozdĺž trate "
                   f"({len(hot)} najsilnejších z {s['n_hotspots']})", png)
    doc.comment("kde a za akých podmienok sa anomálie sústreďujú")


def _conditions(doc, d) -> None:
    doc.heading("Vývoj v čase, počasie a IMU")
    doc.table("Podiel potvrdených anomálií po mesiacoch",
              ["Mesiac", "Jazdy", "Pohyb [s]", "Radar potvrdené [%]", "Otáčkomer potvrdené [%]"],
              [[r["month"], r["runs"], num(r["moving_s"]), num(r["r_conf_pct"], 3),
                num(r["w_conf_pct"], 3)] for r in d["by_month"]])
    doc.table("Podiel potvrdených anomálií podľa počasia",
              ["Skupina", "Jazdy", "Pohyb [s]", "Radar potvrdené [%]", "Otáčkomer potvrdené [%]"],
              [[_weather(r["group"]), r["runs"], num(r["moving_s"]), num(r["r_conf_pct"], 3),
                num(r["w_conf_pct"], 3)] for r in d["by_weather"]])
    imu = d.get("imu_events") or {}
    names = {"sw": "s neplatným stavovým slovom", "det": "len z detektora"}
    rows = [[names.get(k, k), num(v["n"]), pct(v["shock_share"], 1), num(v["dur_median_ms"])]
            for k, v in imu.items()]
    if rows:
        doc.table("IMU v okolí udalostí radaru",
                  ["Udalosti", "Počet", "S otrasom tesne pred [%]", "Medián trvania [ms]"], rows)
    doc.comment("trend, vplyv počasia a súvis s otrasmi")


def _runs(doc, d) -> None:
    runs = d["runs"]
    doc.heading("Jazdy")
    png = charts.category_bars([r["run"] for r in runs], [r["r_conf_pct"] for r in runs],
                               [f"vozidlo {r['veh']}" for r in runs], doc.fig_path("runs_radar_conf"),
                               "Radar potvrdené [% sekúnd]", "Jazda (chronologicky)")
    doc.figure("Podiel potvrdených anomálií radaru v jednotlivých jazdách podľa orientácie vozidla", png)
    doc.comment("rozdiely medzi jazdami")
    doc.landscape(True)
    doc.heading("Príloha A – Zoznam jázd", numbered=False)
    doc.table("Jazdy", ["Jazda", "Smer", "Voz.", "Začiatok UTC", "Pohyb [s]", "Radar any [%]",
                        "Radar conf [%]", "Otáč. any [%]", "Otáč. conf [%]", "Zlé SW vz.",
                        "Det. vz.", "GNSS [s]", "NAV nesúlad", "Zrážky 6 h [mm]", "Teplota [°C]",
                        "Vibr. p2p [g]"],
              [[r["run"], r["dir"], r["veh"], r["utc"], num(r["moving_s"]), num(r["r_any_pct"], 2),
                num(r["r_conf_pct"], 3), num(r["w_any_pct"], 2), num(r["w_conf_pct"], 3),
                num(r["bad_sw_samples"]), num(r["detector_samples"]), num(r["gnss_s"]),
                num(r["nav_mismatch"]), num(r["precip_6h_mm"], 1), num(r["temp_c"], 1),
                num(r["vib_p2p_g"], 4)] for r in runs],
              align="llll" + "r" * 12, name="runs")
    doc.landscape(False)


# ---------------------------------------------------------------------- helpers
def _group(value) -> str:
    if isinstance(value, (int, float)):
        return f"{int(value)}–{int(value) + 10}"   # speed bins are 10 km/h wide
    return {"hard braking": "prudké brzdenie", "braking": "brzdenie", "steady": "ustálená",
            "accelerating": "zrýchľovanie", "hard acceleration": "prudké zrýchl.",
            "direction +": "smer +", "direction −": "smer −", "low vibration": "nízke",
            "medium": "stredné", "high vibration": "vysoké"}.get(value, str(value))


def _weather(value: str) -> str:
    if value.startswith("wet"):
        return "mokro (zrážky > 0,2 mm počas jazdy alebo 6 h pred ňou)"
    return {"dry": "sucho"}.get(value, value)


def _objects(objects: list) -> str:
    if not objects:
        return "-"
    return " | ".join(f"{o['cat'].replace('_', ' ')}{' ' + o['name'] if o['name'] else ''} "
                      f"@km {num(o['jok'] / 1000, 3)}" for o in objects)
