#!/usr/bin/env python3
"""
convert_asset.py — clone a Softpaws aggr.trade workspace to another asset.

    python3 tools/convert_asset.py workspaces/softpaws-avax-flow.json \
        --asset ETH --threshold-scale 10 --beta 1.2 --ratio-mult 1000 \
        --add-market DERIBIT:ETH-PERPETUAL \
        -o workspaces/softpaws-eth-flow.json

What it does, in order:
  1. New id / name / timestamps so the source workspace is never overwritten on import.
  2. Rewrites every market symbol in every pane (and hiddenMarkets) by swapping the
     asset token, case-preserved, so each exchange's naming convention survives
     (BINANCE_FUTURES:avaxusd_perp -> ethusd_perp, KRAKEN:PF_AVAXUSD -> PF_ETHUSD ...).
  3. Rewrites bare market references inside indicator scripts the same way, then
     REGENERATES the venue-z _vbuy/_vsell sums from the pane's actual market list
     (per venue) instead of trusting the string swap.
  4. Renames the <asset>-btc-ratio indicator (id, name, scale index, title, x-multiplier).
  5. Sets the beta-residual manual fallback beta (used only when toggleRolling is off) and adapts the rolling-beta comment.
  6. Scales every USD `amount` in trades-pane thresholds and liquidations, rounding to
     two significant figures. Adaptive indicators (size buckets, absorption, cascade,
     z-scores) are scale-free and are not touched.
  7. Clears indicatorsErrors and asserts the source asset string is gone everywhere.

Run scripts/validate_workspace.py (aggr-workspace skill) on the output afterwards.
"""
import argparse
import json
import math
import re
import time
from pathlib import Path

DEFAULT_BETA = {"ETH": 1.2, "SOL": 1.5, "AVAX": 1.4}
DEFAULT_RATIO_MULT = {"ETH": 1_000, "SOL": 100_000, "AVAX": 1_000_000}
IMPULSE_HINT = {
    "ETH": "Drifting toward 2 = impulse regime.",
    "SOL": "Drifting toward 2-3 = impulse regime.",
}


def round2sig(x: float) -> float:
    if x == 0:
        return 0
    mag = 10 ** (math.floor(math.log10(abs(x))) - 1)
    return round(x / mag) * mag


def swap_token(s: str, src: str, dst: str) -> str:
    """Replace src asset token with dst, preserving upper / lower case."""
    s = s.replace(src.upper(), dst.upper())
    s = s.replace(src.lower(), dst.lower())
    # Title-case (e.g. 'Avax') is not used anywhere in these templates; guard anyway.
    s = s.replace(src.capitalize(), dst.capitalize())
    return s


def mult_label(m: int) -> str:
    return f"x1e{int(round(math.log10(m)))}"


def regenerate_venue_sums(script: str, exchange: str, pane_markets: list[str]) -> str:
    """Rebuild the _vbuy / _vsell lines of a venue-z script from the pane market list."""
    mk = [m for m in pane_markets if m.split(":", 1)[0] == exchange]
    if not mk:
        raise SystemExit(f"venue-z-{exchange}: pane has no {exchange} markets to sum")
    vb = "_vbuy=(" + "+".join(f"{m}.vbuy" for m in mk) + ")"
    vs = "_vsell=(" + "+".join(f"{m}.vsell" for m in mk) + ")"
    out, seen = [], {"vb": False, "vs": False}
    for ln in script.split("\n"):
        if ln.startswith("_vbuy=("):
            out.append(vb); seen["vb"] = True
        elif ln.startswith("_vsell=("):
            out.append(vs); seen["vs"] = True
        else:
            out.append(ln)
    if not all(seen.values()):
        raise SystemExit(f"venue-z-{exchange}: could not find _vbuy/_vsell lines to regenerate")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", type=Path)
    ap.add_argument("--asset", required=True, help="target asset ticker, e.g. ETH")
    ap.add_argument("--source-asset", default=None, help="asset token in the source file (auto-detect from id/name)")
    ap.add_argument("--threshold-scale", type=float, required=True,
                    help="multiply every trades-pane USD threshold by this (ETH from AVAX ~10, SOL ~4)")
    ap.add_argument("--beta", type=float, default=None, help="default options.beta for the residual (else per-asset table)")
    ap.add_argument("--ratio-mult", type=int, default=None, help="x-multiplier for the <asset>/BTC ratio line")
    ap.add_argument("--add-market", action="append", default=[],
                    help="extra EXCHANGE:pair to append to every perp-side pane (repeatable)")
    ap.add_argument("--id", default=None)
    ap.add_argument("--name", default=None)
    ap.add_argument("-o", "--out", type=Path, required=True)
    a = ap.parse_args()

    dst = a.asset.upper()
    d = json.loads(a.src.read_text())
    st = d["states"]

    # --- 0. detect source asset -------------------------------------------------------
    src = a.source_asset
    if not src:
        m = re.search(r"softpaws[-_ ]([a-z]+)", d["id"], re.I) or re.search(r"Softpaws (\w+)", d["name"])
        if not m:
            raise SystemExit("could not detect source asset; pass --source-asset")
        src = m.group(1).upper()
    if src == dst:
        raise SystemExit("source and target asset are the same")
    print(f"converting {src} -> {dst}")

    beta = a.beta if a.beta is not None else DEFAULT_BETA.get(dst, 1.4)
    ratio_mult = a.ratio_mult or DEFAULT_RATIO_MULT.get(dst, 1_000_000)

    # --- 1. identity ----------------------------------------------------------------------
    now = int(time.time() * 1000)
    d["id"] = a.id or f"softpaws-{dst.lower()}-flow"
    d["name"] = a.name or f"Softpaws {dst} — Flow"
    d["createdAt"] = now
    d["updatedAt"] = now

    # --- 2. markets -----------------------------------------------------------------------
    panes = st["panes"]["panes"]
    perp_side_panes = set()
    for pid, p in panes.items():
        new = [swap_token(m, src, dst) for m in p["markets"]]
        if any(m.startswith(("BINANCE_FUTURES:", "HYPERLIQUID:")) for m in new):
            perp_side_panes.add(pid)
        p["markets"] = new
    for pid in perp_side_panes:
        for extra in a.add_market:
            if extra not in panes[pid]["markets"]:
                panes[pid]["markets"].append(extra)
    for pid, p in panes.items():
        if p["type"] == "chart" and pid in st:
            hm = st[pid].get("hiddenMarkets") or {}
            st[pid]["hiddenMarkets"] = {swap_token(k, src, dst): v for k, v in hm.items()}

    # --- 3. scripts -----------------------------------------------------------------------
    old_ratio_id = f"{src.lower()}-btc-ratio"
    new_ratio_id = f"{dst.lower()}-btc-ratio"
    old_ratio_name = f"{src}/BTC ratio"
    new_ratio_name = f"{dst}/BTC ratio"

    for pid, p in panes.items():
        if p["type"] != "chart":
            continue
        cs = st[pid]
        inds = cs["indicators"]
        for iid, ind in list(inds.items()):
            sc = swap_token(ind["script"], src, dst)

            if iid.startswith("venue-z-") and iid != "venue-z-bands":
                sc = regenerate_venue_sums(sc, iid[len("venue-z-"):], p["markets"])

            if iid == old_ratio_id:
                sc = re.sub(r"\* *1000000", f"* {ratio_mult}", sc)
                sc = sc.replace("x1e6", mult_label(ratio_mult))

            if iid == "rolling-beta" and dst in IMPULSE_HINT:
                sc = re.sub(r"Drifting toward [\d\-]+ = impulse regime\.", IMPULSE_HINT[dst], sc)

            ind["script"] = sc
            for k in ("name", "displayName"):
                if k in ind:
                    ind[k] = swap_token(ind[k], src, dst)

            if iid == "beta-residual":
                ind["options"]["beta"] = beta

        # --- 4. rename ratio indicator id -------------------------------------------------
        if old_ratio_id in inds:
            ind = inds.pop(old_ratio_id)
            ind["id"] = new_ratio_id
            ind["libraryId"] = new_ratio_id
            ind["series"] = [new_ratio_id if s == old_ratio_id else s for s in ind.get("series", [])]
            inds[new_ratio_id] = ind
            cs["indicatorOrder"] = [new_ratio_id if x == old_ratio_id else x for x in cs["indicatorOrder"]]
            for sid, sc_ in cs["priceScales"].items():
                sc_["indicators"] = [new_ratio_name if n == old_ratio_name else n for n in sc_["indicators"]]

        cs["indicatorsErrors"] = {}

    # --- 6. thresholds ----------------------------------------------------------------------
    for pid, p in panes.items():
        if p["type"] != "trades":
            continue
        ts = st[pid]
        for key in ("thresholds", "liquidations"):
            for t in ts.get(key, []):
                t["amount"] = round2sig(t["amount"] * a.threshold_scale)
        print(f"  {pid:8s} thresholds -> {[t['amount'] for t in ts['thresholds']]}"
              f"  liqs -> {[t['amount'] for t in ts['liquidations']]}")

    # --- 7. assert clean --------------------------------------------------------------------
    blob = json.dumps(d)
    leftovers = sorted(set(re.findall(r"[^\"\\ ]*" + re.escape(src) + r"[^\"\\ ]*", blob, re.I)))
    if leftovers:
        raise SystemExit(f"source asset still present: {leftovers[:10]}")

    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(d, ensure_ascii=False, indent=None))
    print(f"wrote {a.out}  id={d['id']}  beta={beta}  ratio x{ratio_mult}")


if __name__ == "__main__":
    main()
