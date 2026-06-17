#!/usr/bin/env bash
#
# premarket_gappers.sh — Premarket gappers scanner
# -------------------------------------------------
# Pulls the day's top gainers, applies gap/price/volume filters, keeps the
# top 10 by gap %, then attaches a news catalyst for each from Benzinga.
#
# HOW IT FETCHES
#   "WebFetch <url> with <prompt>" is a fetch + LLM-extraction operation, so
#   this script shells out to the authenticated `claude -p` CLI, which performs
#   the WebFetch internally. No ANTHROPIC_API_KEY is required (the CLI uses its
#   own session auth), but the host running this must have network egress to
#   finance.yahoo.com and www.benzinga.com. See "EGRESS" below.
#
# EGRESS (Claude Code on the web)
#   The remote environment uses a network egress allowlist. For a live run you
#   must allow:  finance.yahoo.com  and  www.benzinga.com
#   (Configure this on the environment that runs the session — see
#    https://code.claude.com/docs/en/claude-code-on-the-web )
#
# REQUIREMENTS:  bash, claude (CLI), jq, python3
#
# OUTPUT:  ./premarket_gappers_YYYY-MM-DD.json   (see schema in the README/PR)
#
# OFFLINE TEST HOOKS (optional, for validating logic without network):
#   GAINERS_MOCK_FILE=path     use this file's text instead of fetching Yahoo
#   CATALYST_MOCK_DIR=path     read $DIR/<SYMBOL>.txt instead of fetching Benzinga
#
set -uo pipefail

# ----- config ---------------------------------------------------------------
GAINERS_URL="https://finance.yahoo.com/markets/stocks/gainers/"
BENZINGA_URL_TMPL="https://www.benzinga.com/quote/%s"
FETCH_TIMEOUT="${FETCH_TIMEOUT:-90}"      # seconds per claude -p call
MAX_PARALLEL="${MAX_PARALLEL:-5}"         # concurrent Benzinga lookups
TOP_N=10

DATE="$(date +%F)"                        # YYYY-MM-DD (local)
SCANNED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
OUT="./premarket_gappers_${DATE}.json"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
CATDIR="$TMP/catalysts"; mkdir -p "$CATDIR"

log() { printf '[scanner] %s\n' "$*" >&2; }

# ----- preflight ------------------------------------------------------------
for bin in jq python3; do
  command -v "$bin" >/dev/null 2>&1 || { log "FATAL: '$bin' not found on PATH"; exit 1; }
done
if [ -z "${GAINERS_MOCK_FILE:-}" ] || [ -z "${CATALYST_MOCK_DIR:-}" ]; then
  command -v claude >/dev/null 2>&1 || { log "FATAL: 'claude' CLI not found on PATH"; exit 1; }
fi

# ----- helpers --------------------------------------------------------------

# run_claude <prompt> : print the model's text answer (uses WebFetch internally)
run_claude() {
  timeout "$FETCH_TIMEOUT" claude -p "$1" \
    --allowedTools WebFetch \
    --output-format text 2>/dev/null
}

# JSON extractor program (written to a file so piped stdin is NOT shadowed by
# the heredoc — `python3 - <<EOF` would consume stdin for the program itself).
cat > "$TMP/extract.py" <<'PY'
import sys, json
s = sys.stdin.read().strip()
# strip a leading ```lang fence and trailing ``` fence if present
if s.startswith("```"):
    s = s.split("\n", 1)[1] if "\n" in s else ""
    if s.rstrip().endswith("```"):
        s = s.rstrip()[:-3]
s = s.strip()

def emit(x):
    sys.stdout.write(json.dumps(x)); sys.exit(0)

# 1) whole string is JSON?
try:
    emit(json.loads(s))
except Exception:
    pass

# 2) bracket-match from the EARLIEST opening bracket ('{' or '['), string-aware,
#    so a prose-wrapped object whose values contain arrays is carved whole.
opens = [i for i in (s.find("{"), s.find("[")) if i != -1]
if opens:
    start = min(opens)
    open_ch = s[start]
    close_ch = "}" if open_ch == "{" else "]"
    depth = in_str = esc = 0
    for k in range(start, len(s)):
        c = s[k]
        if in_str:
            if esc:            esc = 0
            elif c == "\\":    esc = 1
            elif c == '"':     in_str = 0
            continue
        if c == '"':           in_str = 1
        elif c == open_ch:     depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                try:
                    emit(json.loads(s[start:k+1]))
                except Exception:
                    break

# 3) last-ditch greedy span
for op, cl in (("{", "}"), ("[", "]")):
    i, j = s.find(op), s.rfind(cl)
    if i != -1 and j > i:
        try:
            emit(json.loads(s[i:j+1]))
        except Exception:
            continue
sys.exit(1)
PY

# extract_json : read possibly-noisy text on stdin, print one valid compact
#                JSON value (object or array), or exit 1 if none found.
extract_json() { python3 "$TMP/extract.py"; }

# fetch_gainers : print raw model text containing the gainers JSON array
fetch_gainers() {
  if [ -n "${GAINERS_MOCK_FILE:-}" ]; then
    cat "$GAINERS_MOCK_FILE"; return 0
  fi
  local prompt
  prompt="Use the WebFetch tool to fetch ${GAINERS_URL} . Parse the stocks gainers table. \
Return ONLY a JSON array (no markdown, no prose). One object per row with keys: \
\"symbol\" (ticker as a string), \"price\" (last price as a number), \
\"gap_pct\" (the percent change as a number), \
\"premarket_volume\" (the row's volume as an integer; expand abbreviations, e.g. 1.2M=1200000, 3.4B=3400000000). \
Include every row you can read from the table."
  run_claude "$prompt"
}

# fetch_catalyst <symbol> : print raw model text containing {catalyst,headlines}
fetch_catalyst() {
  local sym="$1"
  if [ -n "${CATALYST_MOCK_DIR:-}" ]; then
    cat "$CATALYST_MOCK_DIR/$sym.txt" 2>/dev/null
    return 0
  fi
  local url exact prompt
  printf -v url "$BENZINGA_URL_TMPL" "$sym"
  # The user's exact Benzinga prompt, passed through to WebFetch verbatim:
  exact="What recent news or catalyst is driving ${sym} stock today? Return a one-sentence summary, then up to 2 recent headlines verbatim. Just the data — no commentary."
  prompt="Use the WebFetch tool to fetch ${url} with this exact prompt: \"${exact}\" \
Then output ONLY a JSON object (no markdown, no extra text) shaped exactly like: \
{\"catalyst\": \"<the one-sentence summary as a string, or null if no news found>\", \"headlines\": [\"<up to 2 verbatim headlines>\"]}."
  run_claude "$prompt"
}

# ----- 1) gainers -----------------------------------------------------------
log "Fetching gainers from Yahoo Finance ..."
ALL_RAW="$(fetch_gainers)"
if ! printf '%s' "$ALL_RAW" | extract_json > "$TMP/all.json"; then
  log "WARN: could not parse any gainers rows (empty/blocked response)."
  printf '[]' > "$TMP/all.json"
fi
TOTAL="$(jq 'length' "$TMP/all.json" 2>/dev/null || echo 0)"
log "Parsed ${TOTAL} rows. Applying filters (gap>5%, price>\$3, vol>50k) ..."

# ----- 2) filter + rank -----------------------------------------------------
jq -c --argjson n "$TOP_N" '
  [ .[]
    | { symbol: (.symbol // empty | tostring),
        price: (.price // 0),
        gap_pct: (.gap_pct // 0),
        premarket_volume: (.premarket_volume // 0) }
    | select(.gap_pct > 5 and .price > 3 and .premarket_volume > 50000)
  ]
  | sort_by(.gap_pct) | reverse | .[0:$n]
' "$TMP/all.json" > "$TMP/top.json" 2>/dev/null || printf '[]' > "$TMP/top.json"

KEPT="$(jq 'length' "$TMP/top.json")"
log "Kept ${KEPT} gappers after filtering."

# ----- 3) catalysts (parallel) ----------------------------------------------
if [ "$KEPT" -gt 0 ]; then
  log "Fetching catalysts from Benzinga (up to ${MAX_PARALLEL} in parallel) ..."
  while IFS= read -r sym; do
    [ -n "$sym" ] || continue
    {
      raw="$(fetch_catalyst "$sym")"
      if js="$(printf '%s' "$raw" | extract_json)" \
         && printf '%s' "$js" | jq -e 'type=="object" and has("catalyst")' >/dev/null 2>&1; then
        # normalise: ensure headlines is an array of <=2 strings
        printf '%s' "$js" | jq -c '{
          catalyst: (.catalyst // null),
          headlines: ((.headlines // []) | map(tostring) | .[0:2])
        }' > "$CATDIR/$sym.json"
        log "  $sym: catalyst ok"
      else
        printf '{"catalyst":null,"headlines":[]}' > "$CATDIR/$sym.json"
        log "  $sym: catalyst lookup failed -> null"
      fi
    } &
    # throttle concurrency
    while [ "$(jobs -rp | wc -l)" -ge "$MAX_PARALLEL" ]; do
      wait -n 2>/dev/null || sleep 0.3
    done
  done < <(jq -r '.[].symbol' "$TMP/top.json")
  wait
fi

# ----- 4) assemble output ----------------------------------------------------
python3 - "$OUT" "$SCANNED_AT" "$TMP/top.json" "$CATDIR" <<'PY'
import sys, json, os
out, scanned_at, top_path, catdir = sys.argv[1:5]
top = json.load(open(top_path))
gappers = []
for rank, row in enumerate(top, start=1):
    sym = row["symbol"]
    catalyst, headlines = None, []
    p = os.path.join(catdir, f"{sym}.json")
    if os.path.exists(p):
        try:
            c = json.load(open(p))
            catalyst = c.get("catalyst")
            headlines = [str(h) for h in (c.get("headlines") or [])][:2]
        except Exception:
            pass
    gappers.append({
        "rank": rank,
        "symbol": sym,
        "price": row.get("price"),
        "gap_pct": row.get("gap_pct"),
        "premarket_volume": row.get("premarket_volume"),
        "catalyst": catalyst,
        "headlines": headlines,
    })
json.dump({"scanned_at": scanned_at, "gappers": gappers},
          open(out, "w"), indent=2)
print(out, file=sys.stderr)
PY

log "Wrote $OUT"

# ----- 5) one-line summary ---------------------------------------------------
python3 - "$OUT" <<'PY'
import sys, json
d = json.load(open(sys.argv[1]))
g = d["gappers"]
def fmt(x):
    cat = x["catalyst"] if x["catalyst"] else "no catalyst found"
    return f'{x["symbol"]} ({x["gap_pct"]}%) — {cat}'
top3 = ", ".join(fmt(x) for x in g[:3])
print(f'Premarket Gappers: {len(g)} names.' + (f' Top: {top3}' if top3 else ''))
PY
