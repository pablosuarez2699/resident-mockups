#!/usr/bin/env python3
"""Run the Purolator pipeline end to end: prospecting agent → outreach agent.

The prospecting agent discovers + qualifies leads and writes an Excel report;
this wrapper then feeds that report straight into the outreach agent, which
composes the emails. Each agent still reads its own .env (API keys, rep identity).

Examples:
    python run_pipeline.py
    python run_pipeline.py --sectors industrial,retail --leads 25 --mode follow-up
    python run_pipeline.py --mode no-answer --compose template   # free, no Claude
"""
import argparse
import glob
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PROSPECT_DIR = os.path.join(ROOT, "prospecting_agent")
OUTREACH_DIR = os.path.join(ROOT, "outreach_agent")


def _run(cmd, cwd, step):
    print(f"\n{'=' * 70}\n{step}\n  $ {' '.join(cmd)}  (in {os.path.relpath(cwd, ROOT)}/)\n{'=' * 70}")
    result = subprocess.run([sys.executable, *cmd], cwd=cwd)
    if result.returncode != 0:
        sys.exit(f"\n✗ {step} failed (exit {result.returncode}). Stopping.")


def _newest_report():
    reports = glob.glob(os.path.join(PROSPECT_DIR, "reports", "*.xlsx"))
    if not reports:
        sys.exit("✗ The prospecting agent produced no report — nothing to hand off.")
    return max(reports, key=os.path.getmtime)


def main():
    p = argparse.ArgumentParser(
        description="Run prospecting then outreach, back to back.")
    p.add_argument("--sectors", default="industrial",
                   help='Sectors for prospecting (e.g. "all" or "industrial,retail").')
    p.add_argument("--leads", default=25, type=int, help="Target number of leads.")
    p.add_argument("--mode", default="no-answer",
                   help="Outreach mode trigger: no-answer | follow-up (aliases allowed).")
    p.add_argument("--compose", default=None, choices=["llm", "template"],
                   help="Override outreach COMPOSE_MODE (default: agent's .env, usually llm).")
    p.add_argument("--randomize", action="store_true",
                   help="Shuffle prospecting leads within score bands.")
    args = p.parse_args()

    # 1) Prospecting → Excel report
    prospect_cmd = ["main.py", "--sectors", args.sectors, "--leads", str(args.leads)]
    if args.randomize:
        prospect_cmd.append("--randomize")
    _run(prospect_cmd, PROSPECT_DIR, "STEP 1/2 · Prospecting (discover + qualify leads)")

    # 2) Handoff
    report = _newest_report()
    print(f"\n→ Handoff report: {report}")

    # 3) Outreach → email drafts
    outreach_cmd = ["main.py", "--mode", args.mode, "--input", report, "--source", "excel"]
    if args.compose:
        outreach_cmd += ["--compose", args.compose]
    _run(outreach_cmd, OUTREACH_DIR, "STEP 2/2 · Outreach (compose personalized emails)")

    print(f"\n✅ Pipeline complete. Drafts are in {os.path.relpath(OUTREACH_DIR, ROOT)}/drafts/")


if __name__ == "__main__":
    main()
