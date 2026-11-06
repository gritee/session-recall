---
name: session-recall
description: Turn the current working session into a reinforcement-learning export — a short recap of what was discussed (including tangents), a 3-option multiple-choice quiz grounded in the session, and verified reference links — saved as a versioned JSON file (plus an Obsidian-friendly Markdown note) in a remembered folder, with a single-page HTML quiz runner. Use when the user runs /session-recall, asks to "recap/quiz me on this session", or wants to capture learnings at the end of a jam session. `/session-recall quiz` opens the runner over all saved sessions.
argument-hint: "[quiz [all|latest|<id>]] | [dir <path>] | [focus notes...]"
---

# Session Recall

Capture what was *learned* in this session — main thread and tangents — as a
recap, a quiz and references, so the user can reinforce it later. Output is a
portable, versioned JSON file (canonical) plus a derived Markdown note, written
to a flat folder the user picks once.

Helper script: `scripts/recall.py` in this skill's base directory (shown when
the skill loads). Below, `RECALL` means `python3 "<skill-dir>/scripts/recall.py"`.
Format spec: `references/format.md`. Question rules: `references/question-guidelines.md`
— **read it before writing any question.**

## Modes (from `$ARGUMENTS`)

| Arguments | Action |
|---|---|
| *(empty)* or free text | **Generate** an export for this session. Free text is a focus hint ("focus on the IAM tangent"), never a reason to invent content. |
| `quiz` / `quiz all` | Rebuild the runner and open it with all sessions. |
| `quiz latest` / `quiz <id>` | Open the runner preselecting that session. |
| `dir <path>` | Change the remembered output folder, then stop. |

## Step 1 — Resolve the output folder

Run `RECALL config get`.

- If it prints a folder: use it. In the final message, say it was used and how
  to change it (`/session-recall dir <path>`).
- If it reports no config (first run): ask the user (AskUserQuestion if available)
  where exports should live. Suggest an Obsidian vault subfolder such as
  `<vault>/Learning/session-recall`, or `./learning/session-recall` inside the
  current repo if they want it committed alongside the code. Then run
  `RECALL config set --dir "<path>"` and tell the user it will be reused on
  every future run.

For `dir <path>` mode: run `config set`, confirm, stop.
For `quiz` modes: run `RECALL build "<dir>"` then `RECALL open "<dir>" [--session <id>|--latest]`, report the path, stop.

## Step 2 — Read the session, user first

The only source material is **this session**. Do not pull in other sessions,
memory files, or general knowledge as *topics*. General knowledge is used only
to *verify* answers.

Get the material:
1. Use the conversation in your context.
2. If the context was compacted or summarized, or the session was long, also
   extract the full transcript:
   `RECALL transcript --cwd "$PWD" > <scratch-file>` (newest transcript for this
   project; `--file <path.jsonl>` to pick one). Read it. If it can't be found,
   continue with context only and record `source.coverage = "partial"`.
3. If the user supplied a transcript or notes file, use that instead and record it.

Then analyze it in two passes. **The order matters.**

**Pass 1: the user's messages (primary).** What the user writes is the best
approximation of what they are learning. Read every user message in order,
ignoring the assistant for now, and note these signals:

| Signal (`signals` value) | What it looks like | Why it matters |
|---|---|---|
| `direct-question` | "what is…", "why does…", "how is X different from Y" | the user didn't know this |
| `confirmation` | restating in their own words: "so basically…", "is it right that…", "ok so that means…" | the user was consolidating; check whether the restatement was **correct** |
| `repeated-followup` | asking again, rephrasing, drilling into the same thing over several turns | it didn't land the first time; strongest signal |
| `tangent` | steering away from the session goal, then coming back | curiosity; note what it connected back to |
| `problem` | an error, surprise or confusion the user hit and asked about | understanding the cause is the lesson |
| `goal` | what the user said they set out to do | defines the main line; a topic of its own only if it was explained along the way |

Rough weight: `repeated-followup` and `confirmation` > `direct-question` and
`problem` > `tangent` > a passing mention. A confirmation that was wrong or
half-right is a prime question.

**Pass 2: the assistant's side (secondary).** Now read the assistant's
messages and tool output. Use them to find what was concluded for each user
signal, which facts sit behind the user's questions, and misconceptions on
either side. Something only the assistant brought up, which the user never
asked about, acted on or engaged with, does **not** become a topic. At most it
feeds the recap (`signals: ["agent-introduced"]`).

Write an inventory before anything else. For each topic, list its user signals,
a paraphrase of what the user asked or restated, `origin` (`main` or
`tangent`), `depth` (judged by the **user's** engagement: `mentioned` /
`explored` / `deep`) and what was concluded. Leave out tooling chatter
(permission prompts, retries, typos) and private details (secrets, tokens,
emails, internal hostnames). Never copy them into the export.

## Step 3 — Write recap, questions, references

Follow `references/question-guidelines.md` exactly. Work in this order:

0. **Check web access first.** You need a way to fetch pages: WebFetch,
   WebSearch, or a web-fetch subagent. Every question must be verified against
   a page fetched in this run, so without web access you **write no questions**.
   Tell the user, save a recap-only export (`questions: []`), and suggest running
   again once web tools are available.
1. **Draft candidates** from the Pass 1 signals, more than you expect to keep.
2. **Run the confidence gate** (guidelines section 3) on every candidate,
   including **actively verifying each one against external web sources**:
   fetch the page, find the statement, and record a verbatim quote as evidence. Only
   compose questions whose answer you are *very* confident about, meaning it
   passes every test there, not that it feels right. When in doubt, drop it.
   This is the step everything else depends on: a confidently wrong answer
   teaches the user something false.
3. **Blind-check** the survivors (guidelines section 3), using a fresh subagent
   if one is available.
4. **Write** the recap, the kept questions and the references. If nothing
   survives, save a recap-only export. That's a valid result.

Summary of the rules that matter most:

- **Truth comes from sources, not from the session.** A question's answer is
  what authoritative documentation says, not what the user or the assistant said.
  If the session got something wrong, quiz the correct fact and say in
  `correction` that the session claimed otherwise.
- Every question needs an answer that is true **independently of this
  conversation**. Project decisions and preferences ("we picked Postgres") go in
  the recap, not the quiz.
- Exactly 3 options, exactly one defensible answer, plausible distractors
  (prefer real misconceptions from the session). Never put the answer in the
  same slot every time. The runner shuffles anyway.
- Questions come from the Pass 1 signals. Each question should trace
  back to something the user asked, restated, repeated or struggled with, and
  `session_anchor` paraphrases **that user moment**, not the assistant's reply.
- Quantity follows substance: roughly 1–2 questions per explored topic and
  more for deep ones. Usually 4–12 questions.
  A thin session gets a short quiz. Don't pad.
- No flattery anywhere. The recap describes what was discussed, not how well the
  user did.

**References and verification (mandatory for every question):** each
question cites at least one reference fetched in this run (`verified: true`,
`accessed` date, the final URL after redirects). Its `verification.evidence`
holds a verbatim quote from that page stating the answer. The validator rejects
any question without this. There is no "unverified" question: if it can't be
verified, drop it and list it in the report. Fetching several pages in
parallel (or with one web-fetch subagent per batch of claims) keeps this quick.

## Step 4 — Save, validate, build

1. Choose the id: `YYYY-MM-DD-<short-kebab-slug>` (e.g. `2026-11-05-cloud-webapp-iac`).
   If `<dir>/<id>.json` exists and is a different session, append `-2`, `-3`...
2. Write the JSON to a scratch file, then run
   `RECALL save <scratch.json> --dir "<dir>"`. The command validates, writes
   `<id>.json`, renders `<id>.md` and rebuilds the runner bundle. On validation
   errors, fix the JSON and run it again. Never skip validation.
3. Optional: `RECALL open "<dir>" --session <id>` if the user wants to take the quiz now.

## Step 5 — Report (keep it short)

- File paths written (json, md) and the runner path (`<dir>/session-recall.html`).
- Counts: topics, questions, references (verified/unverified).
- How many questions were verified, and against how many fetched pages.
- Candidates dropped at the confidence gate or blind check: one line each,
  topic and reason (e.g. "S3 consistency: couldn't find it stated in current
  docs"). Don't reveal the kept questions' answers.
- Coverage (`full` or `partial`, and why).
- That the folder is remembered, and the commands `/session-recall quiz` and `/session-recall dir <path>`.
Don't repeat the quiz in chat. Answers in chat spoil the exercise.
