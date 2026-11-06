# session-recall export format — v1

One session → one JSON file, `<id>.json`, in a flat folder. The JSON is the
canonical, shareable artifact. `<id>.md` (Obsidian note) and
`session-recall.data.js` (runner bundle) are **derived** and can be rebuilt
at any time with `recall.py build <dir>`.

Machine-readable schema: `../schema/session-recall.v1.schema.json`.
`recall.py validate` enforces the schema plus cross-field rules (unique ids,
answer ∈ options, refs resolve, ...).

## Folder layout

```
<dir>/
  2026-11-05-cloud-webapp-iac.json   ← canonical (commit/share these)
  2026-11-05-cloud-webapp-iac.md     ← derived note (Obsidian)
  2026-11-09-dns-deep-dive.json
  2026-11-09-dns-deep-dive.md
  session-recall.html                ← quiz runner (copied from the skill)
  session-recall.data.js             ← derived bundle of all *.json
```

Files whose names start with `session-recall.` are tooling. Any other `*.json`
with `"format": "session-recall"` is a session export.

## Top level

| Field | Type | Notes |
|---|---|---|
| `format` | `"session-recall"` | constant, identifies the file |
| `schema_version` | integer | `1`. Major version: breaking changes bump it. Readers ignore unknown fields. |
| `id` | string | `YYYY-MM-DD-slug`, equals the filename stem |
| `title` | string | human title of the session |
| `created` | string | ISO-8601 timestamp of the export |
| `author` | string? | optional display name/handle |
| `project` | object? | `{ name, repo?, path? }`: what the session was working on |
| `source` | object | `{ basis, coverage, notes? }` (see below) |
| `generator` | object | `{ skill, skill_version, model? }` |
| `summary` | string | recap paragraph(s), Markdown allowed |
| `tags` | string[] | lower-kebab tags; become Obsidian tags |
| `topics` | Topic[] | ≥ 1 |
| `questions` | Question[] | may be empty for very thin sessions |
| `references` | Reference[] | |
| `open_questions` | string[]? | raised and unresolved |
| `next_steps` | string[]? | learning follow-ups |

`source.basis`: `"context"` (live conversation only), `"transcript"` (Claude
Code session JSONL), or `"provided"` (user-supplied file).
`source.coverage`: `"full"` or `"partial"` (e.g. compacted context without transcript).

## Topic

```json
{ "id": "tf-state", "name": "Terraform remote state",
  "origin": "main | tangent", "depth": "mentioned | explored | deep",
  "tags": ["iac", "terraform"], "summary": "1–3 sentence takeaway",
  "signals": ["direct-question", "repeated-followup"],
  "related": ["iam-roles"] }
```

`signals` (optional) records *why* this is a topic, judged from the user's
messages: `goal`, `direct-question`, `confirmation`, `repeated-followup`,
`tangent`, `problem`, or `agent-introduced` (the assistant raised it and the
user didn't engage). Across sessions, these show which topics the user keeps
returning to.

Topic `id`s are slugs, and **should be reused across sessions** for the same
concept (`dns-ttl`, `oauth-pkce`, ...). Tags and topic ids link sessions to
each other: in Obsidian, and for later cross-session analysis.

## Question

```json
{ "id": "q1", "topic": "tf-state",
  "difficulty": 1, "context": "optional scene-setting from the session",
  "prompt": "...?",
  "options": [ {"id": "a", "text": "..."}, {"id": "b", "text": "..."}, {"id": "c", "text": "..."} ],
  "answer": "b",
  "explanation": "why b; why not a/c",
  "correction": "optional: what the session got wrong",
  "session_anchor": "paraphrase of the triggering moment",
  "verification": {
    "status": "verified",
    "refs": ["r1"],
    "evidence": [ { "ref": "r1", "quote": "verbatim sentence from the fetched page" } ] } }
```

Exactly 3 options with ids `a`,`b`,`c`. **Every question is web-verified**:
`status` is always `"verified"`, `refs` lists at least one reference with
`verified: true`, and `evidence` holds at least one verbatim quote (under 400
characters) from one of those refs that states the answer. A question that
can't meet this is dropped, never saved as unverified.

## Reference

```json
{ "id": "r1", "title": "...", "url": "https://...",
  "kind": "docs | spec | tutorial | explainer | video | community | other",
  "topics": ["tf-state"], "verified": true, "accessed": "2026-11-05",
  "note": "optional: what it's good for" }
```

`verified: true` means the page was fetched in this run and checked;
`accessed` (required when verified) is the fetch date. Unverified references
may appear only as recap reading and are never cited by a question.

## Compatibility

- Additive changes (new optional fields) keep `schema_version: 1`.
- Renames/removals/semantic changes → `schema_version: 2`, plus a migration note here.
- The runner reads any version it knows and shows a warning for newer versions.
