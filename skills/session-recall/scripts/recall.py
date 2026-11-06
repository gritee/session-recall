#!/usr/bin/env python3
"""session-recall helper: config, validation, saving, Markdown rendering,
runner bundle, and Claude Code transcript extraction. Stdlib only.

Usage:
  recall.py config get
  recall.py config set --dir PATH [--author NAME]
  recall.py validate FILE...
  recall.py save FILE [--dir DIR] [--overwrite]
  recall.py build [DIR] [--render-all]
  recall.py open [DIR] [--session ID | --latest]
  recall.py transcript [--cwd PATH | --file PATH.jsonl] [--max-chars N]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import sys
import webbrowser
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
VIEWER_SRC = SKILL_DIR / "viewer" / "session-recall.html"
SKILL_VERSION = "1.0.0"
SCHEMA_VERSION = 1

VIEWER_NAME = "session-recall.html"
BUNDLE_NAME = "session-recall.data.js"
FOCUS_NAME = "session-recall.focus.js"
NOTES_MARKER = "<!-- session-recall:notes (everything below this line is preserved on re-render) -->"

SIGNALS = {"goal", "direct-question", "confirmation", "repeated-followup", "tangent", "problem", "agent-introduced"}
SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-[a-z0-9]+(-[a-z0-9]+)*$")


def die(msg: str, code: int = 1):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


# ---------------------------------------------------------------- config
def config_path() -> Path:
    env = os.environ.get("SESSION_RECALL_CONFIG")
    if env:
        return Path(env).expanduser()
    # Lives with Claude Code's own files (honours CLAUDE_CONFIG_DIR like Claude Code does).
    base = os.environ.get("CLAUDE_CONFIG_DIR") or str(Path.home() / ".claude")
    return Path(base) / "session-recall.json"


def load_config() -> dict:
    p = config_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError as e:
        die(f"config {p} is not valid JSON: {e}")


def resolve_dir(arg: str | None) -> Path:
    if arg:
        return Path(arg).expanduser().resolve()
    d = load_config().get("dir")
    if not d:
        die("no output folder configured; run: recall.py config set --dir PATH", 2)
    return Path(d)


def cmd_config(a):
    if a.action == "get":
        cfg = load_config()
        if not cfg.get("dir"):
            print(f"NOT CONFIGURED (config file: {config_path()})")
            sys.exit(3)
        print(cfg["dir"])
        if cfg.get("author"):
            print(f"author: {cfg['author']}")
        print(f"(config file: {config_path()})")
        return
    if not a.dir:
        die("config set requires --dir")
    d = Path(a.dir).expanduser().resolve()
    d.mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    cfg["dir"] = str(d)
    if a.author is not None:
        cfg["author"] = a.author
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg, indent=2) + "\n")
    print(f"saved: exports will go to {d}\n(config file: {p})")


# ---------------------------------------------------------------- validation
def validate(doc) -> list[str]:
    errs: list[str] = []

    def req(obj, key, where, typ=None):
        if not isinstance(obj, dict) or key not in obj:
            errs.append(f"{where}: missing '{key}'")
            return None
        v = obj[key]
        if typ and not isinstance(v, typ):
            errs.append(f"{where}.{key}: expected {typ.__name__ if isinstance(typ, type) else typ}")
            return None
        return v

    def enum(v, allowed, where):
        if v is not None and v not in allowed:
            errs.append(f"{where}: {v!r} not in {sorted(allowed, key=str)}")

    def slugs(lst, where):
        if lst is None:
            return
        if not isinstance(lst, list):
            errs.append(f"{where}: expected list")
            return
        for i, s in enumerate(lst):
            if not isinstance(s, str) or not SLUG.match(s):
                errs.append(f"{where}[{i}]: {s!r} is not a lower-kebab slug")

    if not isinstance(doc, dict):
        return ["root: expected object"]
    if doc.get("format") != "session-recall":
        errs.append("format: must be 'session-recall'")
    sv = doc.get("schema_version")
    if sv != SCHEMA_VERSION:
        errs.append(f"schema_version: expected {SCHEMA_VERSION}, got {sv!r}")
    i = req(doc, "id", "root", str)
    if i is not None and not ID_RE.match(i):
        errs.append(f"id: {i!r} must look like YYYY-MM-DD-slug")
    t = req(doc, "title", "root", str)
    if t is not None and not t.strip():
        errs.append("title: empty")
    c = req(doc, "created", "root", str)
    if c is not None:
        try:
            dt.datetime.fromisoformat(c.replace("Z", "+00:00"))
        except ValueError:
            errs.append(f"created: {c!r} is not ISO-8601")
    if "author" in doc and not isinstance(doc["author"], str):
        errs.append("author: expected string")
    if "project" in doc:
        req(doc["project"], "name", "project", str)
    src = req(doc, "source", "root", dict)
    if src is not None:
        enum(req(src, "basis", "source", str), {"context", "transcript", "provided"}, "source.basis")
        enum(req(src, "coverage", "source", str), {"full", "partial"}, "source.coverage")
    gen = req(doc, "generator", "root", dict)
    if gen is not None:
        if gen.get("skill") != "session-recall":
            errs.append("generator.skill: must be 'session-recall'")
        req(gen, "skill_version", "generator", str)
    s = req(doc, "summary", "root", str)
    if s is not None and not s.strip():
        errs.append("summary: empty")
    slugs(req(doc, "tags", "root", list), "tags")
    for k in ("open_questions", "next_steps"):
        if k in doc and not (isinstance(doc[k], list) and all(isinstance(x, str) for x in doc[k])):
            errs.append(f"{k}: expected list of strings")

    # topics
    topic_ids: set[str] = set()
    topics = req(doc, "topics", "root", list) or []
    if not topics:
        errs.append("topics: need at least one topic")
    for n, tp in enumerate(topics):
        w = f"topics[{n}]"
        if not isinstance(tp, dict):
            errs.append(f"{w}: expected object")
            continue
        tid = req(tp, "id", w, str)
        if tid is not None:
            if not SLUG.match(tid):
                errs.append(f"{w}.id: {tid!r} is not a lower-kebab slug")
            if tid in topic_ids:
                errs.append(f"{w}.id: duplicate {tid!r}")
            topic_ids.add(tid)
        req(tp, "name", w, str)
        req(tp, "summary", w, str)
        enum(req(tp, "origin", w, str), {"main", "tangent"}, f"{w}.origin")
        enum(req(tp, "depth", w, str), {"mentioned", "explored", "deep"}, f"{w}.depth")
        slugs(tp.get("tags"), f"{w}.tags")
        slugs(tp.get("related"), f"{w}.related")
        sig = tp.get("signals")
        if sig is not None:
            if not isinstance(sig, list):
                errs.append(f"{w}.signals: expected list")
            else:
                for x in sig:
                    enum(x, SIGNALS, f"{w}.signals")

    # references
    refs: dict[str, dict] = {}
    for n, r in enumerate(req(doc, "references", "root", list) or []):
        w = f"references[{n}]"
        if not isinstance(r, dict):
            errs.append(f"{w}: expected object")
            continue
        rid = req(r, "id", w, str)
        if rid is not None:
            if not re.match(r"^r[0-9]+$", rid):
                errs.append(f"{w}.id: {rid!r} must look like r1, r2, ...")
            if rid in refs:
                errs.append(f"{w}.id: duplicate {rid!r}")
            refs[rid] = r
        req(r, "title", w, str)
        u = req(r, "url", w, str)
        if u is not None and not re.match(r"^https?://\S+$", u):
            errs.append(f"{w}.url: {u!r} is not an http(s) URL")
        enum(req(r, "kind", w, str), {"docs", "spec", "tutorial", "explainer", "video", "community", "other"}, f"{w}.kind")
        if req(r, "verified", w, bool) is True:
            acc = r.get("accessed")
            if not (isinstance(acc, str) and re.match(r"^\d{4}-\d{2}-\d{2}$", acc)):
                errs.append(f"{w}.accessed: verified references need the fetch date (YYYY-MM-DD)")
        for tid in r.get("topics", []) or []:
            if tid not in topic_ids:
                errs.append(f"{w}.topics: unknown topic {tid!r}")

    # questions
    qids: set[str] = set()
    answer_slots: list[str] = []
    for n, q in enumerate(req(doc, "questions", "root", list) or []):
        w = f"questions[{n}]"
        if not isinstance(q, dict):
            errs.append(f"{w}: expected object")
            continue
        qid = req(q, "id", w, str)
        if qid is not None:
            if not re.match(r"^q[0-9]+$", qid):
                errs.append(f"{w}.id: {qid!r} must look like q1, q2, ...")
            if qid in qids:
                errs.append(f"{w}.id: duplicate {qid!r}")
            qids.add(qid)
        tp = req(q, "topic", w, str)
        if tp is not None and tp not in topic_ids:
            errs.append(f"{w}.topic: unknown topic {tp!r}")
        enum(req(q, "difficulty", w), {1, 2, 3}, f"{w}.difficulty")
        for k in ("prompt", "explanation"):
            v = req(q, k, w, str)
            if v is not None and not v.strip():
                errs.append(f"{w}.{k}: empty")
        opts = req(q, "options", w, list)
        if opts is not None:
            ids = [o.get("id") if isinstance(o, dict) else None for o in opts]
            if sorted(x for x in ids if x) != ["a", "b", "c"] or len(opts) != 3:
                errs.append(f"{w}.options: need exactly 3 options with ids a, b, c")
            texts = [(o.get("text") or "").strip().lower() for o in opts if isinstance(o, dict)]
            if any(not t for t in texts):
                errs.append(f"{w}.options: empty option text")
            if len(set(texts)) != len(texts):
                errs.append(f"{w}.options: duplicate option text")
        ans = req(q, "answer", w, str)
        enum(ans, {"a", "b", "c"}, f"{w}.answer")
        if ans:
            answer_slots.append(ans)
        # Every question must be web-verified: verified refs + verbatim evidence quotes.
        ver = req(q, "verification", w, dict)
        if ver is not None:
            vw = f"{w}.verification"
            if ver.get("status") != "verified":
                errs.append(f"{vw}.status: must be 'verified'; drop questions you could not verify against a fetched source")
            rl = req(ver, "refs", vw, list) or []
            if not rl:
                errs.append(f"{vw}.refs: at least one fetched reference is required")
            for rid in rl:
                if rid not in refs:
                    errs.append(f"{vw}.refs: unknown reference {rid!r}")
                elif refs[rid].get("verified") is not True:
                    errs.append(f"{vw}.refs: {rid!r} is not a verified (fetched) reference")
            ev = req(ver, "evidence", vw, list) or []
            if not ev:
                errs.append(f"{vw}.evidence: at least one verbatim quote from a fetched source is required")
            for k, e in enumerate(ev):
                ew = f"{vw}.evidence[{k}]"
                if not isinstance(e, dict):
                    errs.append(f"{ew}: expected object")
                    continue
                if e.get("ref") not in rl:
                    errs.append(f"{ew}.ref: {e.get('ref')!r} must be one of this question's refs")
                qt = e.get("quote")
                if not isinstance(qt, str) or not qt.strip():
                    errs.append(f"{ew}.quote: empty")
                elif len(qt) > 400:
                    errs.append(f"{ew}.quote: keep quotes under 400 characters")

    if len(answer_slots) >= 4 and len(set(answer_slots)) == 1:
        errs.append(f"questions: every answer is {answer_slots[0]!r}; spread correct answers across a/b/c")
    return errs


def load_json(p: Path):
    try:
        return json.loads(Path(p).read_text())
    except json.JSONDecodeError as e:
        die(f"{p}: invalid JSON: {e}")
    except FileNotFoundError:
        die(f"{p}: not found")


def cmd_validate(a):
    bad = 0
    for f in a.files:
        errs = validate(load_json(Path(f)))
        if errs:
            bad += 1
            print(f"✗ {f}")
            for e in errs:
                print(f"   - {e}")
        else:
            print(f"✓ {f}")
    sys.exit(1 if bad else 0)


# ---------------------------------------------------------------- markdown
def _oneline(s: str) -> str:
    # Collapse whitespace and neutralise raw HTML so Obsidian shows "<script>" as text.
    return " ".join((s or "").split()).replace("<", "&lt;")


def _yaml_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def render_md(doc: dict) -> str:
    refs = {r["id"]: r for r in doc.get("references", [])}
    topics = {t["id"]: t for t in doc.get("topics", [])}
    tags = ["session-recall"] + list(doc.get("tags", [])) + [f"topic/{t}" for t in topics]
    seen, tags_u = set(), []
    for t in tags:
        if t not in seen:
            seen.add(t)
            tags_u.append(t)

    L: list[str] = ["---"]
    L.append(f"id: {doc['id']}")
    L.append(f"title: {_yaml_str(doc['title'])}")
    L.append(f"created: {doc['created']}")
    if doc.get("author"):
        L.append(f"author: {_yaml_str(doc['author'])}")
    if doc.get("project", {}).get("name"):
        L.append(f"project: {_yaml_str(doc['project']['name'])}")
    L.append(f"coverage: {doc['source']['coverage']}")
    L.append("tags:")
    L += [f"  - {t}" for t in tags_u]
    L.append("---")
    L.append("")
    L.append(f"# {doc['title']}")
    L.append("")
    L.append(f"> Generated by session-recall from `{doc['id']}.json`. Open `{VIEWER_NAME}` in this folder to take the quiz.")
    L.append("")
    L.append("## Recap")
    L.append("")
    L.append(doc["summary"].strip().replace("<", "&lt;"))
    L.append("")
    L.append("## Topics")
    L.append("")
    for t in doc["topics"]:
        extra = f" · related: {', '.join('#topic/' + r for r in t.get('related', []))}" if t.get("related") else ""
        L.append(f"- **{_oneline(t['name'])}** #topic/{t['id']} — _{t['origin']}, {t['depth']}{'; ' + ', '.join(t['signals']) if t.get('signals') else ''}_{extra}  ")
        L.append(f"  {_oneline(t['summary'])}")
    L.append("")
    for key, head in (("open_questions", "Open questions"), ("next_steps", "Next steps")):
        if doc.get(key):
            L.append(f"## {head}")
            L.append("")
            L += [f"- {_oneline(x)}" for x in doc[key]]
            L.append("")

    if doc.get("questions"):
        L.append("## Quiz")
        L.append("")
        for q in doc["questions"]:
            tname = topics.get(q["topic"], {}).get("name", q["topic"])
            L.append(f"> [!question] {q['id'].upper()} · {tname} · difficulty {q['difficulty']}")
            if q.get("context"):
                L.append(f"> _{_oneline(q['context'])}_")
                L.append(">")
            L.append(f"> {_oneline(q['prompt'])}")
            L.append(">")
            for o in q["options"]:
                L.append(f"> - **{o['id']})** {_oneline(o['text'])}")
            L.append(">")
            L.append("> > [!success]- Answer")
            ans = next((o for o in q["options"] if o["id"] == q["answer"]), None)
            L.append(f"> > **{q['answer']})** {_oneline(ans['text']) if ans else ''}")
            L.append("> >")
            L.append(f"> > {_oneline(q['explanation'])}")
            if q.get("correction"):
                L.append("> >")
                L.append(f"> > **Correction:** {_oneline(q['correction'])}")
            for e in q.get("verification", {}).get("evidence", []):
                r = refs.get(e.get("ref"))
                if r:
                    L.append("> >")
                    L.append(f"> > [{r['title']}]({r['url']}): “{_oneline(e['quote'])}”")
            L.append("")

    if doc.get("references"):
        L.append("## References")
        L.append("")
        for r in doc["references"]:
            mark = "" if r.get("verified") else " _(unverified)_"
            note = f" — {_oneline(r['note'])}" if r.get("note") else ""
            L.append(f"- [{r['title']}]({r['url']}) · {r['kind']}{mark}{note}")
        L.append("")

    src = doc["source"]
    L.append("---")
    L.append(
        f"_Source: {src['basis']} ({src['coverage']} coverage){' — ' + _oneline(src['notes']) if src.get('notes') else ''}. "
        f"Generator: {doc['generator']['skill']} {doc['generator']['skill_version']}"
        f"{' / ' + doc['generator']['model'] if doc['generator'].get('model') else ''}._"
    )
    L.append("")
    L.append(NOTES_MARKER)
    L.append("")
    L.append("## My notes")
    L.append("")
    return "\n".join(L)


def write_md(doc: dict, d: Path):
    p = d / f"{doc['id']}.md"
    body = render_md(doc)
    if p.exists():
        old = p.read_text()
        if NOTES_MARKER in old:
            body = body.split(NOTES_MARKER)[0] + NOTES_MARKER + old.split(NOTES_MARKER, 1)[1]
    p.write_text(body)
    return p


# ---------------------------------------------------------------- build / save / open
def session_files(d: Path) -> list[tuple[Path, dict]]:
    out = []
    for p in sorted(d.glob("*.json")):
        if p.name.startswith("session-recall."):
            continue
        try:
            doc = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            print(f"warning: skipping unreadable {p.name}", file=sys.stderr)
            continue
        if isinstance(doc, dict) and doc.get("format") == "session-recall":
            out.append((p, doc))
    return out


def build(d: Path, render_all: bool = False) -> int:
    d.mkdir(parents=True, exist_ok=True)
    sessions = []
    for p, doc in session_files(d):
        errs = validate(doc)
        if errs:
            print(f"warning: {p.name} has {len(errs)} validation issue(s); included anyway", file=sys.stderr)
        sessions.append(doc)
        if render_all or not (d / f"{doc['id']}.md").exists():
            if not errs:
                write_md(doc, d)
    sessions.sort(key=lambda s: (s.get("created", ""), s.get("id", "")))
    bundle = {
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "sessions": sessions,
    }
    (d / BUNDLE_NAME).write_text(
        "// Generated by session-recall (recall.py build). Do not edit; rebuild instead.\n"
        "window.SESSION_RECALL_BUNDLE = " + json.dumps(bundle, ensure_ascii=False) + ";\n"
    )
    if not VIEWER_SRC.exists():
        die(f"viewer not found at {VIEWER_SRC}")
    shutil.copyfile(VIEWER_SRC, d / VIEWER_NAME)
    return len(sessions)


def cmd_build(a):
    d = resolve_dir(a.dir)
    n = build(d, a.render_all)
    print(f"built runner for {n} session(s): {d / VIEWER_NAME}")


def cmd_save(a):
    doc = load_json(Path(a.file))
    if isinstance(doc, dict):
        doc.setdefault("generator", {"skill": "session-recall", "skill_version": SKILL_VERSION})
        if not doc.get("author") and load_config().get("author"):
            doc["author"] = load_config()["author"]
    errs = validate(doc)
    if errs:
        print("validation failed:", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)
    d = resolve_dir(a.dir)
    d.mkdir(parents=True, exist_ok=True)
    target = d / f"{doc['id']}.json"
    if target.exists() and not a.overwrite:
        die(f"{target} already exists; choose a new id (e.g. {doc['id']}-2) or pass --overwrite")
    target.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    md = write_md(doc, d)
    n = build(d)
    qs = doc["questions"]
    refs = doc["references"]
    print(f"saved   {target}")
    print(f"note    {md}")
    print(f"runner  {d / VIEWER_NAME}  ({n} session(s) in bundle)")
    print(
        f"counts  topics={len(doc['topics'])} questions={len(qs)} refs={len(refs)} "
        f"(verified={sum(bool(r['verified']) for r in refs)})"
    )


def cmd_open(a):
    d = resolve_dir(a.dir)
    if not (d / VIEWER_NAME).exists() or not (d / BUNDLE_NAME).exists():
        build(d)
    focus = None
    if a.session:
        focus = a.session
    elif a.latest:
        ss = sorted((doc for _, doc in session_files(d)), key=lambda s: (s.get("created", ""), s.get("id", "")))
        focus = ss[-1]["id"] if ss else None
    # A focus file instead of a URL #fragment: macOS `open` drops fragments on file:// URLs.
    (d / FOCUS_NAME).write_text(f"window.SESSION_RECALL_FOCUS = {json.dumps(focus)};\n")
    url = (d / VIEWER_NAME).as_uri()
    print(f"opening {url}" + (f" (session {focus})" if focus else " (all sessions)"))
    if not a.no_browser:
        webbrowser.open(url)


# ---------------------------------------------------------------- transcript
REMINDER = re.compile(r"<system-reminder>.*?</system-reminder>", re.S)


def project_transcript_dir(cwd: str) -> Path:
    base = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    return base / "projects" / re.sub(r"[^A-Za-z0-9]", "-", cwd)


def _clip(s: str, n: int) -> str:
    s = s.strip()
    return s if len(s) <= n else s[:n] + f" …[+{len(s) - n} chars]"


def cmd_transcript(a):
    if a.file:
        f = Path(a.file).expanduser()
    else:
        pdir = project_transcript_dir(str(Path(a.cwd or os.getcwd()).resolve()))
        cands = sorted(pdir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime) if pdir.exists() else []
        if not cands:
            die(f"no transcripts found in {pdir}", 4)
        f = cands[-1]
    print(f"# transcript: {f}\n")
    n = 0
    with open(f, encoding="utf-8") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("type") not in ("user", "assistant") or rec.get("isSidechain") or rec.get("isMeta"):
                continue
            msg = rec.get("message") or {}
            content = msg.get("content")
            blocks = [{"type": "text", "text": content}] if isinstance(content, str) else (content or [])
            parts = []
            for b in blocks:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text":
                    t = REMINDER.sub("", b.get("text", "")).strip()
                    if t:
                        parts.append(_clip(t, a.max_chars))
                elif b.get("type") == "tool_use":
                    inp = b.get("input") or {}
                    desc = inp.get("description") or inp.get("file_path") or inp.get("query") or inp.get("url") or ""
                    parts.append(f"[tool: {b.get('name')}{' — ' + _clip(str(desc), 160) if desc else ''}]")
            if not parts:
                continue
            role = "SUMMARY" if rec.get("isCompactSummary") else rec["type"].upper()
            ts = (rec.get("timestamp") or "")[:19]
            print(f"### {role} {ts}\n" + "\n".join(parts) + "\n")
            n += 1
    print(f"# {n} messages")


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(prog="recall.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)

    c = sp.add_parser("config")
    c.add_argument("action", choices=["get", "set"])
    c.add_argument("--dir")
    c.add_argument("--author")
    c.set_defaults(fn=cmd_config)

    v = sp.add_parser("validate")
    v.add_argument("files", nargs="+")
    v.set_defaults(fn=cmd_validate)

    s = sp.add_parser("save")
    s.add_argument("file")
    s.add_argument("--dir")
    s.add_argument("--overwrite", action="store_true")
    s.set_defaults(fn=cmd_save)

    b = sp.add_parser("build")
    b.add_argument("dir", nargs="?")
    b.add_argument("--render-all", action="store_true", help="re-render every .md (notes below the marker are kept)")
    b.set_defaults(fn=cmd_build)

    o = sp.add_parser("open")
    o.add_argument("dir", nargs="?")
    g = o.add_mutually_exclusive_group()
    g.add_argument("--session")
    g.add_argument("--latest", action="store_true")
    o.add_argument("--no-browser", action="store_true")
    o.set_defaults(fn=cmd_open)

    t = sp.add_parser("transcript")
    t.add_argument("--cwd")
    t.add_argument("--file")
    t.add_argument("--max-chars", type=int, default=4000)
    t.set_defaults(fn=cmd_transcript)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
