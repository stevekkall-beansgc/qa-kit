#!/usr/bin/env python3
"""health.py — ONE pane for BeanLabs fleet health.

Aggregates: service probes (hub, runner, Qdrant, LM Studio, harness
console), per-repo latest GitHub Actions conclusion, last qa-kit baseline
verdict, monitor/drift state. Emits public/index.html (served by the hub
at /qa) + public/health.json for machines.

Exit 0 always (reporting tool, not a gate); failures render AS red.
Stdlib only. Scheduled hourly alongside ci_monitor via bean-sched.
"""
import json
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import shutil
GH_BIN = shutil.which("gh") or "/opt/homebrew/bin/gh"  # launchd PATH lacks homebrew

HERE = Path(__file__).resolve().parent.parent
MANIFEST = HERE / "manifest.json"
PUBLIC = HERE / "public"
OWNER = "stevekkall-beansgc"


def expand(p):
    return Path(p).expanduser()


def probe_url(url, timeout=3):
    """Liveness: ANY http response (<500) proves something is serving."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status < 500, ""
    except Exception as e:
        return False, str(e)[:120]


def gh(args):
    try:
        p = subprocess.run([GH_BIN, *args], capture_output=True, text=True, timeout=30)
        return json.loads(p.stdout) if p.returncode == 0 else None
    except Exception:
        return None


def services():
    out = []
    ok, _ = probe_url("http://127.0.0.1:8800/api/health")
    out.append(("Hub API", ":8800", ok))
    runner = None
    try:
        with urllib.request.urlopen("http://127.0.0.1:8800/api/runner/status", timeout=3) as r:
            d = json.loads(r.read())
        age = d.get("heartbeat_age_seconds", 9999)
        out.append(("Runner heartbeat", f"{age}s old", age < 120))
    except Exception as e:
        out.append(("Runner heartbeat", str(e)[:60], False))
    ok, _ = probe_url("http://127.0.0.1:6333/readyz")
    out.append(("Qdrant", ":6333", ok))
    models = "-"
    try:
        with urllib.request.urlopen("http://127.0.0.1:1234/v1/models", timeout=3) as r:
            models = f"{len(json.loads(r.read()).get('data', []))} loaded"
    except Exception:
        pass
    ok, _ = probe_url("http://127.0.0.1:1234/v1/models")
    out.append(("LM Studio", f":1234 · {models}", ok))
    ok, _ = probe_url("http://127.0.0.1:8766/api/status")
    out.append(("Harness console", ":8766 · benchmark lane", ok))

    tick, tick_ok = "never", False
    try:
        state_dir = Path.home() / "Desktop/bean-sched/state"
        candidates = [state_dir / "state.json", state_dir / "history.json"]
        mtimes = [f.stat().st_mtime for f in candidates if f.exists()]
        if mtimes:
            age = max(0, int((datetime.now(timezone.utc).timestamp() - max(mtimes)) // 60))
            tick = "just now" if age < 2 else f"{age}m ago"
            tick_ok = age <= 10  # tick cadence is ~5 min
    except Exception:
        pass
    out.append(("bean-sched tick", f"5-min cadence · last write {tick}", tick_ok))
    return out


def ci_rows():
    man = json.loads(MANIFEST.read_text())
    rows = []
    for repo in man["repos"]:
        if repo.get("status") == "planned":
            rows.append((repo["name"], "planned", "", False))
            continue
        name = repo["name"]
        gh_name = repo.get("github", name)
        if not ((expand(repo["path"]) / ".git").exists() and
                "origin" in (expand(repo["path"]) / ".git" / "config").read_text(errors="ignore")):
            rows.append((name, "local-only", "", True))  # ok=True: known state
            continue
        runs = gh(["run", "list", "--repo", f"{OWNER}/{gh_name}",
                   "--branch", "main", "--limit", "1",
                   "--json", "conclusion,url,displayTitle"])
        if not runs:
            rows.append((name, "no runs", "", True))
            continue
        r = runs[0]
        conclusion = r.get("conclusion") or ""
        if conclusion in ("running", "queued"):
            ok = True  # in-flight is not failing; render neutral
        else:
            ok = conclusion == "success"
        rows.append((name, conclusion or r.get("displayTitle", "")[:40],
                     r.get("url", ""), ok))
    return rows


def qa_baseline():
    logs = sorted(HERE.glob("logs/run-*.json"))
    if not logs:
        return {"verdict": "never-run", "when": ""}
    d = json.loads(logs[-1].read_text())
    res = d.get("results", [])
    failed = [r for r in res if not r["ok"]]
    return {"when": d.get("when", ""), "total": len(res),
            "failed": len(failed),
            "verdict": "PASS" if res and not failed else "FAIL"}


def monitors():
    st = {}
    p = HERE / "logs" / "ci-state.json"
    if p.exists():
        try:
            st = json.loads(p.read_text())
        except ValueError:
            pass
    return {"checked": st.get("checked", "never"),
            "repos_watched": len(st.get("repos", {}))}


def html(data):
    def dot(ok, neutral=False):
        cls = "y" if neutral else ("g" if ok else "r")
        return f'<span class="d {cls}"></span>'
    svc = "".join(f"<tr><td>{dot(ok)}</td><td>{n}</td><td class=m>{detail}</td></tr>"
                  for n, detail, ok in data["services"])
    repos = "".join(
        f'<tr><td>{dot(ok, neutral=state in ("running", "queued"))}</td>'
        f'<td><a href="{url}" target="_blank">{n}</a></td>'
        f"<td>{state}</td></tr>" if url else
        f'<tr><td>{dot(ok, neutral=state in ("running", "queued"))}</td>'
        f'<td>{n}</td><td>{state}</td></tr>'
        for n, state, url, ok in data["repos"])
    q = data["qa"]
    mon = data["monitors"]
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>BeanLabs fleet health</title><meta http-equiv="refresh" content="300">
<style>body{{font-family:-apple-system,sans-serif;background:#0f1216;color:#e6e8eb;
margin:0;padding:24px}}h1{{font-size:1.3rem}} h2{{font-size:1rem;margin:22px 0 8px;
color:#9aa4af;text-transform:uppercase;letter-spacing:.08em;font-size:.75rem}}
table{{border-collapse:collapse;width:100%;max-width:720px}} td{{padding:6px 10px;
border-bottom:1px solid #232a33}} .m{{color:#667085}} .d{{display:inline-block;
width:10px;height:10px;border-radius:50%}} .g{{background:#34d399}} .r{{background:#f87171}} .y{{background:#fbbf24}}
a{{color:#7dd3fc;text-decoration:none}} .sub{{color:#667085;font-size:.85rem}}</style></head><body>
<h1>BeanLabs fleet health</h1>
<p class="sub"><a href="https://github.com/stevekkall-beansgc/qa-kit/blob/main/STANDARDS.md">Standards & maintenance loops</a> · this pane regenerates every 15 min</p>
<p class="sub">generated {data['generated']} · refreshes every 5 min</p>
<h2>services</h2><table>{svc}</table>
<h2>repositories · latest main-branch run</h2><table>{repos}</table>
<h2>qa baseline</h2><table>
<tr><td>{dot(q['verdict'] == 'PASS')}</td><td>last run_all</td><td class=m>
{q['verdict']} · {q['total']} checks · {q['when']}</td></tr>
<tr><td>{dot(mon['checked'] != 'never')}</td><td>ci monitor</td><td class=m>
watching {mon['repos_watched']} repos · swept {mon['checked']}</td></tr>
</table></body></html>"""


def main():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    data = {
        "generated": now,
        "services": services(),
        "repos": [(n, s, u, ok) for n, s, u, ok in ci_rows()],
        "qa": qa_baseline(),
        "monitors": monitors(),
    }
    PUBLIC.mkdir(exist_ok=True)
    (PUBLIC / "index.html").write_text(html(data))
    (PUBLIC / "health.json").write_text(json.dumps(data, indent=2))
    print(f"health dashboard -> {PUBLIC}/index.html "
          f"({sum(1 for *_ , ok in data['repos'] if ok)}/{len(data['repos'])} repos ok, "
          f"{sum(1 for *_ , ok in data['services'] if ok)}/{len(data['services'])} services up)")


if __name__ == "__main__":
    main()
