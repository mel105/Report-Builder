"""Report on processing one campaign with the C4R pipeline (safe speed estimation).

Reads the JSON sidecars written by LIB/report_writer.TextReport under
<campaign>/TXT/<BOX>/<run or 'combined'>/. Standalone report: it reads nothing
from anomaly_mapper.
"""
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from ..core import charts
from ..core.document import DocBuilder
from ..core.fmt import loc, num, to_number
from ..core.sources import Source, TextReportData, load_plain_kv, load_textreport, newest

NAME = "pipeline_campaign"
TITLE = "Odhad bezpečnej rýchlosti"
SUBTITLE = "Spracovanie senzorických dát a odhad bezpečnej rýchlosti vlaku"
DESCRIPTION = "Správa zo spracovania kampane pipeline C4R (<kampaň>/TXT/…/*.json)."

SENSORS = [("RADAR_SPEED", "radar"), ("WIG_SPEED", "otáčkomer"), ("WIG2_SPEED", "otáčkomer 2 (simulovaný)")]
CLEANING_COLUMNS = {
    "RUN_ID": "Jazda", "ORIGINAL": "Pôvodné", "CLEANED": "Po čistení", "RETENTION": "Ponechané",
    "TEMPORAL": "Gradient", "SYSTEMATIC": "Syst. bias", "DVDT_NAN": "dv/dt NaN", "GNSS_SEG_2": "GNSS 2. st.",
    "MAHALANOBIS_1": "Mahal. 1", "MAHALANOBIS_2": "Mahal. 2",
    "RMSE_ORIG": "RMSE pred", "RMSE_CLEAN": "RMSE po", "IMPROVEMENT": "Zlepšenie",
}
TARGET = {"ACHIEVED": "splnený", "NOT ACHIEVED": "nesplnený"}
MIXED_RUNS_HOURS = 12   # sources further apart than this are reported as a warning
SIL4_LIMIT_PCT = 0.1    # allowed share of violations (100 - SIL4 threshold of 99.9 %)


class Inputs:
    """Locates and loads reports; remembers what was used and what went wrong."""

    def __init__(self, txt: Path):
        self.txt = txt
        self.sources: List[Source] = []
        self.warnings: List[str] = []
        self.campaign = ""

    def combined(self, box: str, pattern: str, note: str = "") -> Optional[TextReportData]:
        path = newest(self.txt / box / "combined", pattern)
        if path is None:
            self.warnings.append(f"Chýba zdroj {box}/combined/{pattern} – príslušná časť správy je vynechaná.")
            return None
        data = load_textreport(path)
        self.campaign = self.campaign or (data.campaign or "")
        self.sources.append(Source(path, data.generated, note or box))
        return data

    def runs(self, box: str) -> List[str]:
        root = self.txt / box
        return sorted(p.name for p in root.iterdir() if p.is_dir() and p.name.isdigit()) if root.exists() else []

    def per_run(self, box: str, pattern: str) -> Dict[str, TextReportData]:
        """One report per run: {run_id: data}. Listed as a single line in the sources table."""
        found: Dict[str, TextReportData] = {}
        for run in self.runs(box):
            path = newest(self.txt / box / run, pattern)
            if path is not None:
                found[run] = load_textreport(path)
        if found:
            times = sorted(d.generated for d in found.values())
            span = times[0] if times[0] == times[-1] else f"{times[0]} – {times[-1]}"
            self.sources.append(Source(Path(f"{box}/<jazda>/{pattern}"), span, f"počet jázd: {len(found)}"))
        return found


def find_inputs(path: Path) -> Optional[dict]:
    path = Path(path)
    txt = path if path.name == "TXT" else path / "TXT"
    if not txt.is_dir() or not any(txt.glob("*/combined/*.json")):
        return None
    inputs = Inputs(txt)
    first = next(txt.glob("*/combined/*.json"))
    inputs.campaign = load_textreport(first).campaign or txt.parent.name
    return {"inputs": inputs, "campaign": inputs.campaign, "warnings": inputs.warnings}


def build(found: dict, doc: DocBuilder) -> List[Source]:
    inp: Inputs = found["inputs"]
    # Chapters are built first so that the opening summary can list every warning.
    body = doc.doc.element.body
    marker = len(list(body)) - 1   # index of the first element the chapters will add (before sectPr)
    summary: List[List[str]] = []

    _input_data(doc, inp, summary)
    _data_quality(doc, inp, summary)
    _calibration(doc, inp, summary)
    _safe_speed(doc, inp, summary)
    _errors(doc, inp, summary)
    _check_mixed_runs(inp)
    _summary_chapter(doc, inp, summary, marker)
    return inp.sources


# ---------------------------------------------------------------------- helpers
def _passthrough(doc, data: TextReportData, heading: str, caption: str,
                 rename: Optional[Dict[str, str]] = None, align: Optional[str] = None,
                 name: Optional[str] = None) -> bool:
    """Put a source table into the report as it is, with localised numbers."""
    try:
        table = data.table(heading)
    except KeyError:
        return False
    columns = [(rename or {}).get(c, c) for c in table["columns"]]
    doc.table(caption, columns, [[loc(v) for v in row] for row in table["rows"]], align=align, name=name)
    return True


def _values(doc, data: TextReportData, heading: str, caption: str,
            labels: Optional[Dict[str, str]] = None, name: Optional[str] = None) -> None:
    """Put the 'key: value' lines of a source section into a two-column table."""
    values = data.values.get(heading.strip().upper(), {})
    if not values:
        return
    rows = [[(labels or {}).get(k, k), loc(v)] for k, v in values.items()]
    doc.key_value(caption, rows, name=name)


def _rms(results: TextReportData) -> str:
    text = loc(results.value("Summary Statistics", "Overall RMS"))
    return text.replace("->", "→").replace("improvement:", "zlepšenie")


def _n(text) -> float:
    value = to_number(text)
    return 0.0 if value is None else value


# ---------------------------------------------------------------------- chapters
def _input_data(doc, inp, summary) -> None:
    doc.heading("Vstupné dáta")
    plan = inp.combined("BIN2ODO", "processing_plan.json")
    merge = inp.combined("BIN2ODO", "merge_results_*.json")
    intake = inp.per_run("ODO", "*_data_intake_report.json")
    time_rec = inp.per_run("ODO", "*_time_reconstruction_report.json")
    gnss = inp.combined("GNSS_IMPORTER", "*_import_summary_*.json")
    resampler = inp.combined("RESAMPLER", "cross_run_summary_*.json")

    rows = []
    total_ins = 0.0
    for run in sorted(intake):
        ins = _n(intake[run].value("Overview", "INS records"))
        total_ins += ins
        t = time_rec.get(run)
        rows.append([run, num(ins), loc(intake[run].value("Overview", "UBX records")),
                     num(ins / 60000.0, 1),   # 1 ms records
                     loc(t.value("NAV-TIMEUTC reconstruction", "Missing seconds")) if t else "-",
                     loc(t.value("NAV-TIMEUTC reconstruction", "Duplicates found")) if t else "-"])
    overview = [["Kampaň", inp.campaign]]
    if plan:
        overview.append(["Vstupné *.bin súbory", loc(plan.value("Overview", "Total input files"))])
    if merge:
        overview.append(["Jazdy zlúčené do *.odo (úspešne / chyba)",
                         f"{loc(merge.value('Summary', 'Successfully processed'))} / "
                         f"{loc(merge.value('Summary', 'Failed'))}"])
    if rows:
        overview += [["Počet jázd (ODO)", str(len(rows))],
                     ["INS záznamy spolu (1 ms)", num(total_ins)],
                     ["Dĺžka dát spolu [h]", num(total_ins / 3.6e6, 2)]]
        summary.append(["Počet jázd", str(len(rows))])
        summary.append(["Dĺžka dát spolu [h]", num(total_ins / 3.6e6, 2)])
    if gnss:
        overview.append(["GNSS riešenie", gnss.value("Run Info", "Solution") or "-"])
    if resampler:
        overview.append(["Záznamy po prevzorkovaní na 1 s",
                         loc(resampler.value("Overall Statistics", "Total output rows"))])
    doc.key_value("Základné charakteristiky kampane", overview)
    if rows:
        doc.table("Jazdy kampane", ["Jazda", "INS záznamy", "UBX záznamy", "Trvanie [min]",
                                    "Chýbajúce sekundy", "Duplicity času"], rows, name="runs")
        missing = sum(_n(r[4]) for r in rows)
        if missing:
            inp.warnings.append(f"V časovej osi chýba spolu {num(missing)} s (tabuľka jázd, stĺpec „Chýbajúce sekundy“).")
    if gnss:
        _passthrough(doc, gnss, "Per-Database Totals", "Import GNSS referencie do databáz",
                     {"database": "Databáza", "attempted": "Riadky", "inserted": "Vložené",
                      "duplicates": "Duplicity", "time_range": "Časový rozsah"}, align="lrrrl")
    doc.comment("opis merania, vozidla a trate")


def _data_quality(doc, inp, summary) -> None:
    doc.heading("Kvalita dát")
    anomalies = inp.per_run("ODO", "*_anomaly_detection_report.json")
    processing = inp.per_run("ODO", "*_sensor_processing_report.json")
    validation = inp.combined("SENSOR_VALIDATION", "cross_run_summary_*.json")
    resampler = inp.sources and next((s for s in inp.sources if "RESAMPLER" in str(s.path)), None)

    if anomalies:
        rows, radar = [], []
        for run in sorted(anomalies):
            a = anomalies[run]
            r = _n(a.value("RADAR", "total"))
            radar.append(r)
            retained = "-"
            if run in processing:
                retained = loc(processing[run].value("RADAR", "Records retained (of valid RADAR readings)") or "-")
            rows.append([run, loc(a.value("WIG", "total")), loc(a.value("WIG2", "total")), num(r),
                         loc(a.value("RADAR", "median_filter")), loc(a.value("RADAR", "velocity_change")),
                         retained])
        doc.heading("Anomálie v ms dátach (odo_processor)", 2)
        doc.table("Detegované a opravené anomálie podľa jazdy",
                  ["Jazda", "Otáčkomer", "Otáčkomer 2 (sim.)", "Radar", "Radar: mediánový filter",
                   "Radar: zmena rýchlosti", "Radar: ponechané platné vzorky"], rows, name="odo_anomalies")
        if len(radar) > 1:
            png = charts.hbar(sorted(anomalies), radar, doc.fig_path("odo_radar_anomalies"),
                              "počet opravených anomálií radaru", decimals=0)
            doc.figure("Anomálie radaru opravené v jednotlivých jazdách", png)
        summary.append(["Opravené anomálie radaru spolu", num(sum(radar))])

    if validation:
        doc.heading("Validácia senzorov (sensor_validation)", 2)
        _values(doc, validation, "Totals", "Validácia senzorov – súhrn",
                {"Runs processed": "Spracované jazdy", "Runs without data": "Jazdy bez dát",
                 "Total rows scanned": "Prejdené riadky",
                 "Total combined adhesion events": "Adhézne udalosti spolu"})
        _passthrough(doc, validation, "Per-Run Trends", "Validácia senzorov podľa jazdy",
                     {"run_id": "Jazda", "acc_norm_g": "ACC_NORM [g]", "events/h": "Udalosti / h",
                      "wheel_lock_%": "Blokovanie kolies [%]", "wig_radar_%total": "Otáč. vs radar [% všetkých]",
                      "wig_radar_%valid": "Otáč. vs radar [% platných]"})
        for line in validation.notes.get("ERRORS ENCOUNTERED", []) + [
                f"{k}: {v}" for k, v in validation.values.get("ERRORS ENCOUNTERED", {}).items()]:
            doc.para(f"Chyba pri spracovaní: {line}", italic=True)
            inp.warnings.append(f"sensor_validation: {line}")

    res = inp.combined("RESAMPLER", "cross_run_summary_*.json") if not resampler else None
    res = res or load_textreport(resampler.path) if resampler else res
    if res:
        doc.heading("Prevzorkovanie na 1 s (resampler)", 2)
        _passthrough(doc, res, "Per-Table Statistics", "Prevzorkovanie podľa tabuľky",
                     {"table": "Tabuľka", "epochs": "Jazdy", "input_rows": "Vstupné riadky",
                      "output_rows": "Výstupné riadky", "compression": "Pomer",
                      "total_time_s": "Čas spolu [s]", "avg_time_s": "Čas / jazda [s]"})
        doc.para("Pomer výstupných a vstupných riadkov zodpovedá prevzorkovaniu z 1 ms na 1 s.", italic=True)
    doc.comment("zhodnotenie kvality vstupných dát")


def _calibration(doc, inp, summary) -> None:
    doc.heading("Kalibrácia senzorov")
    models = inp.combined("SAFE_SPEED", "blind_model_summary.json", "blind modely použité v safe_speed")
    if models:
        _passthrough(doc, models, "Blind model parameters", "Kalibračné (blind) modely použité pri výpočte",
                     {"Sensor": "Senzor", "SDEV (moving)": "SDEV pohyb [km/h]", "V_DEAD": "V_DEAD [km/h]",
                      "SDEV_STANDSTILL": "SDEV státie [km/h]"}, align="lrrrrrl", name="blind_models")
    for key, label in SENSORS:
        results = inp.combined(f"CALIBRATOR/{key}", "calibration_results.json", f"kalibrácia – {label}")
        if results is None:
            continue
        cleaning = inp.combined(f"CALIBRATOR/{key}", "data_cleaning.json", f"čistenie dát – {label}")
        doc.heading(f"Senzor: {label}", 2)
        doc.key_value(f"Kalibrácia – súhrn ({label})", [
            ["RMS pred → po kalibrácii", _rms(results)],
            ["Priemerné zlepšenie", loc(results.value("Summary Statistics", "Average improvement"))],
            ["Odstránené odľahlé body", loc(results.value("Summary Statistics", "Total outliers removed"))],
            ["Kontrola voči GNSS (2. stupeň): vylúčené", loc((results.value("Second-stage GNSS check", "Excluded") or "-").split(" records")[0])],
            ["Rezíduum finálneho fitu: σ", loc(results.value(
                "FINAL FIT RESIDUAL (on the exact data used for the final fit)", "Std"))],
        ], name=f"calib_{key.lower()}_summary")
        _passthrough(doc, results, "Per-run calibration results", f"Kalibrácia podľa jazdy ({label}), hodnoty v km/h",
                     {"RUN_ID": "Jazda", "RMS_ORIG": "RMS pôvodné", "RMS_CLEAN": "RMS po čistení",
                      "RMS_CALIB": "RMS po kalibrácii", "BIAS_ORIG": "Bias pôvodný", "BIAS_CALIB": "Bias po kalibrácii",
                      "IMPROVEMENT": "Zlepšenie", "OUTLIERS": "Odľahlé", "RETENTION": "Ponechané"},
                     name=f"calib_{key.lower()}_runs")
        table = results.tables.get("PER-RUN CALIBRATION RESULTS")
        if table and "SIM" not in label.upper():
            col = table["columns"]
            png = charts.grouped_bars([r[0] for r in table["rows"]],
                                      [("pred kalibráciou", [_n(r[col.index("RMS_ORIG")]) for r in table["rows"]]),
                                       ("po kalibrácii", [_n(r[col.index("RMS_CALIB")]) for r in table["rows"]])],
                                      doc.fig_path(f"calib_{key.lower()}_rms"), "RMS voči GNSS [km/h]", "Jazda", 3)
            doc.figure(f"RMS odchýlky voči GNSS pred a po kalibrácii ({label})", png)
        _passthrough(doc, results, "Final fit residual by speed band",
                     f"Rezíduum finálneho fitu podľa rýchlosti ({label})",
                     {"Speed range [km/h]": "Rýchlosť [km/h]"}, name=f"calib_{key.lower()}_bands")
        if cleaning:
            _passthrough(doc, cleaning, "PER-RUN OUTLIER BREAKDOWN (MOVING data, all enabled stages combined)",
                         f"Čistenie dát podľa jazdy ({label})", CLEANING_COLUMNS,
                         name=f"calib_{key.lower()}_cleaning")
        if key == "RADAR_SPEED":
            summary.append(["RMS radaru pred → po kalibrácii", _rms(results)])
        if key == "WIG_SPEED":
            summary.append(["RMS otáčkomera pred → po kalibrácii", _rms(results)])
    doc.comment("zhodnotenie kalibrácie a stability modelov medzi jazdami")


def _safe_speed(doc, inp, summary) -> None:
    doc.heading("Bezpečná rýchlosť")
    batch = inp.combined("SAFE_SPEED", "batch_summary_*.json")
    compliance = inp.combined("SAFE_SPEED", "campaign_compliance_*.json")
    rows = []
    if batch:
        rows += [["Spracované jazdy", loc(batch.value("Overview", "Successful processing"))],
                 ["Jazdy s GNSS referenciou", loc(batch.value("Overview", "GNSS data available"))],
                 ["Jazdy vyhovujúce SIL4", loc(batch.value("SIL4 compliance", "SIL4 compliant runs"))]]
        summary.append(["Jazdy vyhovujúce SIL4", loc(batch.value("SIL4 compliance", "SIL4 compliant runs"))])
    if compliance:
        c = "Speed-dependent compliance"
        w = "Interval width statistics"
        rows += [["Zhoda s limitmi závislými od rýchlosti", loc(compliance.value(c, "Compliance with speed-dependent limits"))],
                 ["Cieľ 95 % / 98 % / 99 %", " / ".join(TARGET.get(compliance.value(c, f"Target {t}% compliance"), "-")
                                                        for t in (95, 98, 99))],
                 ["Šírka intervalu: priemer", loc(compliance.value(w, "Mean width"))],
                 ["Šírka intervalu: medián", loc(compliance.value(w, "Median width"))],
                 ["Šírka intervalu: 95. percentil", loc(compliance.value(w, "95th percentile"))],
                 ["Šírka intervalu: 99. percentil", loc(compliance.value(w, "99th percentile"))]]
        summary.append(["Zhoda s limitmi závislými od rýchlosti",
                        loc(compliance.value(c, "Compliance with speed-dependent limits"))])
        summary.append(["Stredná šírka intervalu spoľahlivosti", loc(compliance.value(w, "Mean width"))])
    if rows:
        doc.key_value("Bezpečná rýchlosť – súhrn kampane", rows, name="safe_speed_summary")
    _sil4_per_run(doc, inp)
    doc.comment("zhodnotenie zhody so SIL4 a šírky intervalov")


def _sil4_per_run(doc, inp) -> None:
    """Per-run GNSS validation. The module still writes it as plain text
    (gnss_validation.txt, no JSON sidecar), so it is read as 'key: value' lines."""
    rows, runs, violations = [], [], []
    times = []
    for run in inp.runs("SAFE_SPEED"):
        path = inp.txt / "SAFE_SPEED" / run / "gnss_validation.txt"
        if not path.exists():
            continue
        v = load_plain_kv(path)
        times.append(datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"))
        points, bad = _n(v.get("Validation Points")), _n(v.get("Violation Points"))
        verdict = v.get("SIL4 ASSESSMENT", "-")
        rows.append([run, loc(v.get("Validation Points")), loc(v.get("Violation Points")),
                     loc(v.get("Compliance Rate")), verdict, loc(v.get("Mean width")),
                     loc(v.get("95th percentile width")), loc(v.get("Max violation magnitude", "-"))])
        runs.append(run)
        violations.append(100.0 * bad / points if points else 0.0)
        if verdict == "FAIL":
            inp.warnings.append(f"Jazda {run} nevyhovuje SIL4 (zhoda {loc(v.get('Compliance Rate'))}).")
    if not rows:
        inp.warnings.append("Chýba SAFE_SPEED/<jazda>/gnss_validation.txt – tabuľka SIL4 podľa jazdy je vynechaná.")
        return
    inp.sources.append(Source(Path("SAFE_SPEED/<jazda>/gnss_validation.txt"),
                              times[0] if len(set(times)) == 1 else f"{min(times)} – {max(times)}",
                              f"počet jázd: {len(rows)}, čas podľa súboru, textový formát"))
    doc.table("Validácia intervalov spoľahlivosti voči GNSS podľa jazdy",
              ["Jazda", "Body", "Porušenia", "Zhoda", "SIL4", "Šírka priemer", "Šírka 95. perc.",
               "Max. porušenie"], rows, align="lrrrlrrr", name="sil4_runs")
    if len(runs) > 1:
        png = charts.hbar(runs, violations, doc.fig_path("sil4_violations"), "podiel porušení intervalu [%]",
                          ref=(SIL4_LIMIT_PCT, f"limit SIL4 {num(SIL4_LIMIT_PCT, 1)} %"), decimals=3)
        doc.figure("Podiel bodov, v ktorých GNSS rýchlosť leží mimo intervalu spoľahlivosti", png)


def _errors(doc, inp, summary) -> None:
    doc.heading("Chyby bezpečnej rýchlosti voči GNSS")
    stats = inp.combined("ERRORS", "error_statistics.json")
    campaign = inp.combined("ERRORS", "campaign_summary.json")
    sigma = inp.combined("ERRORS", "quantile_sigma_analysis.json")
    cause = inp.combined("ERRORS", "correlation_cause_analysis.json")
    if stats:
        b, m = "Basic Statistics", "Error Metrics"
        doc.key_value("Chyba (GNSS − bezpečná rýchlosť) za celú kampaň", [
            ["Počet bodov", loc(stats.value(b, "Count"))],
            ["Bias", loc(stats.value(m, "Bias"))], ["RMSE", loc(stats.value(m, "RMSE"))],
            ["MAE", loc(stats.value(m, "MAE"))], ["MAD", loc(stats.value(m, "MAD"))],
            ["Smerodajná odchýlka", loc(stats.value(b, "Std"))],
            ["Min / Max", loc(stats.value(b, "Min / Max"))],
            ["Šikmosť / špicatosť", f"{loc(stats.value(b, 'Skewness'))} / {loc(stats.value(b, 'Kurtosis'))}"],
            ["Normalita rozdelenia", {"normal": "áno", "not normal": "nie"}.get(
                stats.value("Normality Tests", "Overall assessment") or "", "-")],
        ], name="error_summary")
        summary.append(["RMSE bezpečnej rýchlosti voči GNSS", loc(stats.value(m, "RMSE"))])
        summary.append(["Bias bezpečnej rýchlosti voči GNSS", loc(stats.value(m, "Bias"))])
    if campaign:
        _passthrough(doc, campaign, "Error Metrics Per Run", "Chyby podľa jazdy, hodnoty v km/h",
                     {"RUN_ID": "Jazda", "RADAR_BIAS": "Bias radar", "WIG_BIAS": "Bias otáč.",
                      "CORR": "Korelácia", "SYST_CORR": "Syst. korelácia"}, name="error_runs")
        table = campaign.tables.get("ERROR METRICS PER RUN")
        if table:
            col = table["columns"]
            png = charts.hbar([r[0] for r in table["rows"]], [_n(r[col.index("RMSE")]) for r in table["rows"]],
                              doc.fig_path("error_rmse_runs"), "RMSE voči GNSS [km/h]", decimals=3)
            doc.figure("RMSE bezpečnej rýchlosti voči GNSS podľa jazdy", png)
        _passthrough(doc, campaign, "Standstill Bias Per Run", "Bias pri státí podľa jazdy, hodnoty v km/h",
                     {"RUN_ID": "Jazda", "N_STANDSTILL": "Body státia", "SS_RADAR_BIAS": "Radar",
                      "SS_WIG_BIAS": "Otáčkomer", "SS_WIG2_BIAS": "Otáčkomer 2 (sim.)",
                      "SS_FUSED_BIAS": "Fúzia", "WIG_CONS_FLAGGED": "Nesúlad otáčkomerov"},
                     name="error_standstill")
    if sigma:
        _passthrough(doc, sigma, "Quantile-Based Sigma Estimates", "Robustné odhady σ chyby",
                     {"Method": "Metóda", "Outlier Resistance": "Odolnosť voči odľahlým"})
    if cause:
        _passthrough(doc, cause, "Speed Dependency Analysis", "Korelácia chýb radaru a otáčkomera podľa rýchlosti",
                     {"Speed Range [km/h]": "Rýchlosť [km/h]", "Correlation": "Korelácia"})
    doc.comment("zhodnotenie presnosti a zvyškových systematických chýb")


def _check_mixed_runs(inp) -> None:
    stamps = []
    for s in inp.sources:
        try:
            stamps.append((datetime.strptime(s.generated[:19], "%Y-%m-%d %H:%M:%S"), s))
        except ValueError:
            continue
    if len(stamps) < 2:
        return
    stamps.sort(key=lambda x: x[0])
    hours = (stamps[-1][0] - stamps[0][0]).total_seconds() / 3600.0
    if hours > MIXED_RUNS_HOURS:
        inp.warnings.append(
            f"Zdroje pochádzajú z rôznych behov pipeline: najstarší {stamps[0][1].path.name} "
            f"({stamps[0][1].generated[:19]}), najnovší {stamps[-1][1].path.name} "
            f"({stamps[-1][1].generated[:19]}), rozdiel {num(hours, 1)} h.")


def _summary_chapter(doc, inp, summary, marker: int) -> None:
    """Write the opening chapter last (it needs all warnings) and move it to the front."""
    body = doc.doc.element.body
    before = len(list(body)) - 1
    doc.heading("Zhrnutie", numbered=False)
    if summary:
        doc.key_value("Kľúčové výsledky kampane", summary, name="summary")
    doc.heading("Upozornenia k dátam", 2, numbered=False)
    if inp.warnings:
        for w in inp.warnings:
            doc.doc.add_paragraph(w, style="List Paragraph" if _has_style(doc, "List Paragraph") else None)
    else:
        doc.para("Bez upozornení.")
    doc.comment("celkové zhodnotenie kampane")
    doc.page_break()
    children = list(body)
    new = [el for el in children[before:] if not el.tag.endswith("sectPr")]
    anchor = children[marker]
    for el in new:
        anchor.addprevious(el)
    # Keep the contents list in reading order: the summary entries were recorded last.
    n = sum(1 for e in doc._toc if e[1] in ("Zhrnutie", "Upozornenia k dátam"))
    doc._toc[:] = doc._toc[-n:] + doc._toc[:-n]


def _has_style(doc, name: str) -> bool:
    try:
        doc.doc.styles[name]
        return True
    except KeyError:
        return False
