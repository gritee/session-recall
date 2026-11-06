# Question & recap guidelines

The goal is **reinforcement of things that are actually true**, anchored in what
the user explored. These rules exist mainly to stop the export from becoming
an echo of the conversation, flattering to the user or the assistant, instead of an honest learning aid.

## 1. Where truth comes from

Two things are kept separate:

| | Comes from | Used for |
|---|---|---|
| **Relevance** (what to ask about) | the session, **the user's messages first** (see SKILL.md Step 2) | choosing topics, wording context, distractors |
| **Correctness** (what the answer is) | authoritative external sources | the answer, the explanation, references |

- An answer is correct because primary docs, specs, or well-established
  references say so, **not** because it was said, agreed on, or worked once in
  the session.
- Sessions contain mistakes from both sides. If something said in the session
  conflicts with the docs, the question tests the **docs' version** and the
  `correction` field names the in-session claim neutrally ("The session assumed X;
  per the docs, Y."). These are often the most valuable questions. Include them.
- Every question must pass the confidence gate in section 3. Being "fairly
  sure" isn't enough.

## 2. What may become a question

Ask: *"Would a domain expert, given the docs, give the same answer regardless of
who is asking or what this project needed?"* If not, it isn't a quiz question.

Good candidates, strongest first:
- Something the user kept coming back to (`repeated-followup`). Ask about the
  part that took several tries.
- Something the user restated to check their understanding (`confirmation`).
  If the restatement was off, build the question around the difference, and use
  the user's own wrong version as a distractor.
- Something the user asked directly, or the cause of a problem they hit.
- What a user-driven tangent taught, and how it connected back to the main goal.
- Commands/configs, **only** when the user engaged with them and the fact is
  stable and worth remembering, not trivia.

Not a question: anything only the assistant brought up that the user didn't
engage with. It can appear in the recap.

Not questions (put them in the recap if anywhere):
- Project-specific decisions, preferences, naming, taste ("which DB did we pick").
- Opinions or contested best practices, unless the question is phrased as
  attribution ("According to the AWS Well-Architected guidance, ...").
- Things only the transcript can confirm ("what did the assistant suggest first").
- Trivia with no learning value (exact version numbers, error-code digits).
- Every passing mention. A tangent that only got a sentence usually gets no question.

## 3. Confidence gate (the most important section)

The whole skill depends on this. A quiz that confidently teaches a wrong answer
is worse than no quiz: it reinforces a falsehood with the user's own effort.
So the bar is **very high confidence**, and the default for any doubt is to
**drop the question**. Dropping is cheap. A few solid questions beat many
shaky ones, and **zero questions is a valid result** (save a recap-only export).

Don't rely on a feeling of confidence. Language models feel sure about things
that are wrong, especially fluent, plausible details. Confidence here means
**passing every test below**. Run them on each candidate, after drafting it and
before keeping it:

1. **One sentence, one source.** Write the answer as a single plain
   declarative sentence and name the page you expect to state it (which doc,
   spec or section).
2. **Fetch it and find it, every time. No exceptions.** Actively verify
   **every** question against external web resources fetched in this run, even
   facts you consider basic. Open the page and find the statement itself, not
   something you infer or extrapolate from it. Copy a short **verbatim** quote
   that states the answer into `verification.evidence`.
   - Prefer primary sources: official docs, specs, RFCs. Use an explainer or
     tutorial only when no primary source states it, and never a forum answer alone.
   - Read what the source says; don't search for a source that agrees with
     your draft. If the source says something different, the source wins:
     rewrite the question to match it or drop it.
   - If you can't find it stated, drop the question. Memory doesn't count, and
     neither does "it's well known".
   - The quote must be text from the page. If your fetch tool returns a
     model-written summary instead of the page text, a quote from that summary
     doesn't count. Fetch again, or try another page, until you have the
     page's own words, or drop the question.
   - Check that the quoted page covers the version or product the question is
     about, and pin the version in the prompt when it matters.
3. **The question and the evidence say the same thing.** Re-read the prompt
   and the correct option next to the quote. If the option claims more than the
   quote supports (broader scope, extra detail, a different version), narrow
   the option to what the quote says.
4. **Every distractor is definitely wrong.** Wrong under any reasonable
   reading, configuration, version or platform, not just "usually wrong". If a
   distractor is right in some common setup, pin the setup in the prompt or drop
   the question.
5. **Argue against yourself.** Make the strongest case you can that a
   distractor is correct, or that the answer is wrong or incomplete. If that case
   has any real substance, narrow the question until it doesn't, or drop it.
6. **The session is not evidence.** A conclusion reached in the session, a
   command that worked, or agreement between the user and the assistant proves
   nothing about the general fact. Something that worked may have worked for a
   different reason than the one stated.
7. **No hedging needed.** If the explanation needs "usually", "generally",
   "in most cases" or "it depends", the question isn't crisp. Narrow it or drop it.

**Blind check.** After drafting all questions, check each kept question
without its answer, so the check isn't anchored on your draft:
- If a subagent tool is available, give a fresh subagent only the `prompt`,
  `context` and the 3 options, with no answer and no session. Ask it to pick an
  answer, say how sure it is, and flag any ambiguity, a second defensible
  option, or a fact that may be outdated. If its pick differs from yours or it
  raises a substantive flag, fix the question and check once more. If it still
  doesn't agree cleanly, drop it.
- Otherwise do the same yourself: re-read each question cold, as a skeptical
  domain expert who hasn't seen the session.

Keep a short list of dropped candidates (topic and reason) for the final report,
so the user can see what was left out and why.

## 4. Shape of a question

- `prompt`: self-contained and answerable without the session. Use
  `context` to set the scene from the session when that helps recall
  ("While wiring the CDN in front of the bucket you hit ..."). Context may make
  the answer easier. Use that on purpose and set `difficulty` to match:
  1 = recognition (context strongly cues it), 2 = understanding, 3 = application/edge case.
- Exactly **3 options**, exactly **one** defensible answer.
  - Distractors must be plausible: real misconceptions (ideally ones that
    came up in the session), near-miss mechanisms, or adjacent tools. No joke
    options, no "all/none of the above", and no options that differ only in wording.
  - Keep options similar in length and specificity. The longest, most careful
    option shouldn't always be the right one.
  - Spread the correct answer across a/b/c.
- `explanation`: why the answer is right **and** why each distractor is wrong
  or when it would be right. 2–5 sentences, neutral tone.
- `session_anchor`: one short paraphrase of the **user's** message or moment
  that produced this question ("Asked twice why the CDN still served the old
  file"). Paraphrase only; never quote secrets or private data.

## 5. Anti-sycophancy checklist (run before saving)

For every question and the recap:
- [ ] The question passed every test in the confidence gate (section 3) and the blind check.
- [ ] Each question traces back to a user signal (question,
      restatement, repeat, problem, tangent), not just to something the assistant said.
- [ ] The answer would be unchanged if the user had held the opposite opinion.
- [ ] No answer is "correct" because the user or the assistant preferred it.
- [ ] In-session errors are corrected, not reinforced.
- [ ] No praise, grading, or judgement of the user ("great question", "you mastered ...").
- [ ] The recap doesn't overstate depth: a topic that was only mentioned is labelled `mentioned`.
- [ ] Explanations don't hedge a wrong answer into being "also kind of right".
- [ ] Every question cites a reference fetched in this run, with a verbatim quote that states the answer.
- [ ] Removing this question would lose something the user would want to remember.
      If not, remove it.

## 6. Recap

- `summary`: 3–8 sentences. What the session set out to do, what it did, the
  main tangents, and open questions. Factual and past tense.
- `topics[].summary`: 1–3 sentences on the takeaway, including any correction.
- `open_questions`: things raised and left unresolved. Useful later for
  spotting gaps across sessions.
- `next_steps`: optional. Learning follow-ups the session implies, not project TODOs.

## 7. References

- Prefer primary sources: official docs, specs/RFCs, vendor guides, then
  well-known explainers and tutorials, then community threads (label `kind: community`).
- Every reference should back at least one topic or question.
- `verified: true` (with `accessed` set to today's date) only if the URL was
  fetched in this run and checked. Record the URL you actually ended up on,
  after redirects.
- A reference cited by a question must be verified. Unverified references may
  only appear as recap reading, and should be stable landing pages, not
  guessed deep links.
