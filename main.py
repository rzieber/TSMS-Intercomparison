"""
TSMS Intercomparison: command center. Run every step of the pipeline from here (from the repo root, venv active).

    python main.py status                     what exists, and when each output was last written
    python main.py reformat                   1.  build data/reformatted from the SD-card and CHORDS sources
    python main.py splice                     1b. fix the mislabeled CHORDS columns (SF-10) in data/reformatted
    python main.py clean --label <CHANGE>     2.  back up data/cleaned to data/archive, then run the QC framework
    python main.py analyze [--timescale h D]  3.  error analysis + WMO classification (backs up outputs first)
    python main.py compare                    4.  side-by-side with the TSMS report (backs up outputs first)
    python main.py plots [names ...]          5.  plots from plot-gen-final.py (--list shows the names)
    python main.py failures [SF-xx ...]       6.  sensor-failure diagnostic figures (plots/diagnostics/)
    python main.py all --label <CHANGE>       clean → analyze → compare → plots → failures

Workflow notes
    1.  reformat runs final_paws_reformatter.py and final_tsms_reformatter.py. Their source folders are absolute paths
        outside the repo (see scripts/reformatting/README.txt for where the source data lives).
    1b. splice runs scripts/reformatting/splice_chords_dec2024.py. It replaces Dec 2024 → Nov 2025 with the correctly
        labeled CHORDS batch (data/raw/3D-PAWS/Dec-2024_Nov-2025), re-maps the CHORDS rows before 2024-03-11 00:00 UTC
        at TSMS02, 03, 04, 05, 08, and excludes TSMS04's temperatures for that window (docs/methods.md, SF-10). It
        always starts from the untouched originals in data/archive/reformatted_backup_pre-chords-splice/.
    2.  clean runs scripts/outliers/outlier-removal.py (QC Steps 0–8, docs/qc-framework.md). data/cleaned is not in
        git and can't be recovered once overwritten, so the current files are first copied to
        data/archive/cleaned-backup-<MMDDYYYY>_[BEFORE-<LABEL>]/ and verified byte for byte.
        Documented events (maintenance logs, confirmed failures) are rows in docs/station-events.csv.
    3.  analyze runs scripts/error/error-analysis.py once per timescale (hourly and daily by default); the WMO
        classification is written on every run (it uses its own averaging times).
    4.  compare runs scripts/comparison/compare_with_report.py → data/report-comparison/.
    5.  plots runs scripts/plotter/plot-gen-final.py; arguments after `plots` are passed through
        (e.g. `python main.py plots windrose --stations TSMS00`).
    6.  failures runs scripts/plotter/plot-sensor-failures.py (arguments passed through).
"""
import argparse
import filecmp
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ARCHIVE = ROOT / "data" / "archive"

SCRIPTS = {
    "reformat_paws": ROOT / "scripts/reformatting/final_paws_reformatter.py",
    "reformat_tsms": ROOT / "scripts/reformatting/final_tsms_reformatter.py",
    "splice":        ROOT / "scripts/reformatting/splice_chords_dec2024.py",
    "clean":         ROOT / "scripts/outliers/outlier-removal.py",
    "analyze":       ROOT / "scripts/error/error-analysis.py",
    "compare":       ROOT / "scripts/comparison/compare_with_report.py",
    "plots":         ROOT / "scripts/plotter/plot-gen-final.py",
    "failures":      ROOT / "scripts/plotter/plot-sensor-failures.py",
}
OUTPUTS = {  # what each step writes, for `status` and backups
    "reformatted":       ROOT / "data/reformatted",
    "cleaned":           ROOT / "data/cleaned",
    "error-analysis":    ROOT / "data/error-analysis",
    "report-comparison": ROOT / "data/report-comparison",
    "wind-roses":        ROOT / "plots/wind-roses",
    "diagnostics":       ROOT / "plots/diagnostics",
}


# ----------------------------------------------------------------------------------------------------------- helpers
def run(script: Path, *args: str):
    """Run one pipeline script from the repo root with this interpreter; stop the pipeline if it fails."""
    cmd = [sys.executable, "-u", str(script), *args]
    print(f"\n=== {script.relative_to(ROOT)} {' '.join(args)}".rstrip(), flush=True)
    started = datetime.now()
    result = subprocess.run(cmd, cwd=ROOT)
    took = datetime.now() - started
    if result.returncode != 0:
        sys.exit(f"\n{script.name} failed (exit {result.returncode}) after {took}. Stopping.")
    print(f"=== done in {str(took).split('.')[0]}", flush=True)


def backup(src: Path, name: str, pattern: str = "*"):
    """Copy the top-level files of src matching pattern into data/archive/<name>/ and verify them byte for byte."""
    files = sorted(p for p in src.glob(pattern) if p.is_file() and p.name != ".DS_Store")
    if not files:
        print(f"Nothing to back up in {src.relative_to(ROOT)}.")
        return None
    dest = ARCHIVE / name
    if dest.exists():
        sys.exit(f"{dest.relative_to(ROOT)} already exists; pick another --label so nothing is overwritten.")
    dest.mkdir(parents=True)
    for f in files:
        shutil.copy2(f, dest / f.name)
    bad = [f.name for f in files if not filecmp.cmp(f, dest / f.name, shallow=False)]
    if bad:
        sys.exit(f"Backup verification failed for {bad}; nothing was run.")
    print(f"Backed up {len(files)} files from {src.relative_to(ROOT)} to {dest.relative_to(ROOT)} (verified).")
    return dest


def stamp():
    return datetime.now().strftime("%m%d%Y")


def confirm(question: str, assume_yes: bool):
    if assume_yes:
        return
    if input(f"{question} [y/N] ").strip().lower() not in ("y", "yes"):
        sys.exit("Stopped; nothing was changed.")


# ----------------------------------------------------------------------------------------------------------- steps
def step_status(_):
    print("Output                 Files  Last written")
    for label, path in OUTPUTS.items():
        files = [p for p in path.rglob("*") if p.is_file() and p.name != ".DS_Store"] if path.exists() else []
        newest = max((p.stat().st_mtime for p in files), default=None)
        when = datetime.fromtimestamp(newest).strftime("%Y-%m-%d %H:%M") if newest else "—"
        print(f"{label:<22} {len(files):>5}  {when}")
    backups = sorted(p.name for p in ARCHIVE.iterdir() if p.is_dir()) if ARCHIVE.exists() else []
    print(f"\ndata/archive: {len(backups)} backup folder(s)" + ("".join(f"\n  {b}" for b in backups)))


def step_reformat(args):
    confirm("Rebuild data/reformatted from the source folders (absolute paths in the reformatter scripts)? "
            "Re-run `splice` afterwards.", args.yes)
    run(SCRIPTS["reformat_paws"])
    run(SCRIPTS["reformat_tsms"])


def step_splice(args):
    confirm("Re-apply the CHORDS column fixes to data/reformatted (starts from the originals in data/archive)?", args.yes)
    run(SCRIPTS["splice"])


def step_clean(args):
    label = args.label.upper().replace(" ", "-")
    confirm(f"Regenerate data/cleaned? The current files are first backed up to "
            f"data/archive/cleaned-backup-{stamp()}_[BEFORE-{label}]/.", args.yes)
    backup(OUTPUTS["cleaned"], f"cleaned-backup-{stamp()}_[BEFORE-{label}]", "*.csv")
    run(SCRIPTS["clean"])


def step_analyze(args):
    label = (args.label or datetime.now().strftime("RUN-%H%M")).upper().replace(" ", "-")
    backup(OUTPUTS["error-analysis"], f"error-analysis-backup-{stamp()}_[BEFORE-{label}]")
    for ts in args.timescale:
        run(SCRIPTS["analyze"], "--timescale", ts)


def step_compare(args):
    label = (args.label or datetime.now().strftime("RUN-%H%M")).upper().replace(" ", "-")
    backup(OUTPUTS["report-comparison"], f"report-comparison-backup-{stamp()}_[BEFORE-{label}]")
    run(SCRIPTS["compare"])


def step_plots(args):
    run(SCRIPTS["plots"], *args.rest)


def step_failures(args):
    run(SCRIPTS["failures"], *args.rest)


def step_all(args):
    step_clean(args)
    args.timescale = args.timescale or ["h", "D"]
    step_analyze(args)
    step_compare(args)
    args.rest = []
    step_plots(args)
    step_failures(args)


# ----------------------------------------------------------------------------------------------------------- CLI
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="step", required=True, metavar="step")

    def add(name, fn, help_):
        p = sub.add_parser(name, help=help_, description=help_)
        p.set_defaults(fn=fn)
        return p

    add("status", step_status, "show each output folder's file count and last-written time, and the archive")
    for name, fn, help_ in [("reformat", step_reformat, "1. build data/reformatted from the source data"),
                            ("splice", step_splice, "1b. fix the mislabeled CHORDS columns (SF-10)")]:
        add(name, fn, help_).add_argument("--yes", action="store_true", help="don't ask for confirmation")

    p = add("clean", step_clean, "2. back up data/cleaned to data/archive, then run the QC framework")
    p.add_argument("--label", required=True, help="what changed, used in the backup name, e.g. STATION-EVENTS")
    p.add_argument("--yes", action="store_true", help="don't ask for confirmation")

    p = add("analyze", step_analyze, "3. error analysis and WMO classification")
    p.add_argument("--timescale", nargs="+", choices=["h", "D", "none"], default=["h", "D"])
    p.add_argument("--label", help="used in the backup name (default RUN-<time>)")

    p = add("compare", step_compare, "4. side-by-side with the TSMS report")
    p.add_argument("--label", help="used in the backup name (default RUN-<time>)")

    for name, fn, help_ in [("plots", step_plots, "5. plot-gen-final.py (arguments passed through; --list for names)"),
                            ("failures", step_failures, "6. sensor-failure figures (arguments passed through)")]:
        add(name, fn, help_).add_argument("rest", nargs=argparse.REMAINDER, help="passed to the script")

    p = add("all", step_all, "clean → analyze → compare → plots → failures")
    p.add_argument("--label", required=True, help="what changed, used in the backup names")
    p.add_argument("--timescale", nargs="+", choices=["h", "D", "none"])
    p.add_argument("--yes", action="store_true", help="don't ask for confirmation before cleaning")

    args, extra = ap.parse_known_args()
    if extra:   # options meant for a passed-through script (e.g. `plots --list`, `plots windrose --stations TSMS00`)
        if args.step not in ("plots", "failures"):
            ap.error(f"unrecognized arguments: {' '.join(extra)}")
        args.rest = list(args.rest) + extra
    args.fn(args)


if __name__ == "__main__":
    main()
