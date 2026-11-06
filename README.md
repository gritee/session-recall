# session-recall
A Claude Code plugin (one skill) that turns a working ("jam") session into a reinforcement
kit: a recap of what was discussed (including the tangents), a 3-option quiz
grounded in the session, and references. Each session
becomes one versioned JSON file in a flat folder you pick once (an Obsidian
vault folder works well). A single-file HTML runner quizzes you on one session
or many.

```
/plugin marketplace add https://github.com/Gritee/claude-plugins.git
/plugin install session-recall@gritee
```

```
/session-recall:session-recall                  # export this session (asks for a folder on first run)
/session-recall:session-recall focus on the DNS tangent
/session-recall:session-recall quiz             # open the runner with all saved sessions
/session-recall:session-recall quiz latest      # ...preselecting the newest
/session-recall:session-recall dir ~/Vault/Learning/session-recall   # change the folder
```

Type `/session-recall` and pick it from autocomplete, or just ask "recap and
quiz me on this session". With a [manual install](#manual-install) the command
is plain `/session-recall`.

## From Me:
Agent readme below if you want to skip my Chain-of-Thought, : D

One of the joys of agent assistance is to learn what you want, how you want. I often enguage in side quests tangent to the session's initial/main goal. The learnings from the side quests are inevitably squeezed out of the project, and gone, not captured.

This skill retains session learnings to "feed an Obsidian brain" (folder) which eventually can be mined for project ideas, next steps, analyzing gaps, etc.

The user explicitly invokes the skill to create artifacts for agent session learned concepts, for capture and/or to reinforce via the cheeky html quiz runner.

It's a bit of an art deciding when to invoke the skill and for which session, and be aware of agent sycophantism, etc. but it's a tool, helpful or dangerous. I'm still playing around with it

(embarrassing) My initial note/kernel idea during another project:
```
I was jamming with an agent coding agent for a refresher on implementing a live
cloud hosted web application from scratch (latest-tools/tooling, IaC, code,
deployment, etc..). While in the first session, I as always, similar to my
browser tab habits, engage in multiple tangents of various bredth and depth.
This is joy's of agents: bespoke learning strategy. It ocurred to me, that my
tangent inqueries, and the conversion it self could support both a power summary
and "check-your-knowlage" quiz. In these agent "jamming" sessions, there is many
topics discussed and learned about which fall out of mind as the project makes
further and further progress. I want to capture and take advantage of these
learnings/tangents at whatever depth they occur, even if the learnings are not
distilled in the final project. This idea is prime candidate for an agent skill,
to be invoked at the end of a jam session. It might even be worth standardizing,
serializing, and committing to the code repository, so it's sharable with
other's, similar to how a wiki is related to the code but doesn't affect
production, or tests, etc.. The tree of learnings and quiz would be specific to
the author producing it, but can still be valuable to others for learning or
demonstrating where the author's head was at. At a minimum the skill itself is
valuable, as it would support accelerated re-inforced learning tailored to
individuals, and is opt-in. And skill is session agnostic, covers any topics
discussed. I suppose enough of related skill exports could be used to resolve
larger curriculums based off real expierence, or perhaps, maintain a centralized
ongoing stream of skill exports to maintain running average topical curriculums
(guess this is separate project blocked by the standard and mechanisms). it's
almost like democratizing what cloud ai providers get for free. cool.
```


## From Agent:

### Install

Requires `python3` (stdlib only).

#### As a plugin (recommended)

```
/plugin marketplace add https://github.com/Gritee/claude-plugins.git
/plugin install session-recall@gritee
```

`gritee` is the marketplace catalog ([Gritee/claude-plugins](https://github.com/Gritee/claude-plugins));
it points at this repo. Get new versions with `/plugin marketplace update gritee`.
Invoke as `/session-recall:session-recall` (plugin skills are namespaced).

#### Manual install

Personal (all projects). Clone, then symlink so `git pull` updates the skill:

```sh
git clone https://github.com/Gritee/session-recall.git ~/src/session-recall
mkdir -p ~/.claude/skills
ln -s ~/src/session-recall/skills/session-recall ~/.claude/skills/session-recall
```

Per project: copy the skill folder into the project (commit it to share with
the team):

```sh
mkdir -p .claude/skills
cp -R ~/src/session-recall/skills/session-recall .claude/skills/
```

Restart Claude Code, then run `/session-recall`.

### What gets written

```
<your folder>/
  2026-11-05-cloud-webapp-iac.json   canonical export: share/commit these
  2026-11-05-cloud-webapp-iac.md     Obsidian note (tags, foldable answers, "My notes" kept on re-render)
  session-recall.html                quiz runner (open in a browser)
  session-recall.data.js             derived bundle of all *.json (rebuild: recall.py build)
```

The folder is stored in `~/.claude/session-recall.json`
(override with `SESSION_RECALL_CONFIG`).

### Design principles

- **Session-only source.** Topics come only from the session (live context, or
  the Claude Code transcript when context was compacted).
- **Truth from sources, not the conversation.** Answers must hold independently
  of what the user or assistant said. In-session mistakes become corrected
  questions. References are marked `verified` only if actually fetched. See
  [question-guidelines.md](skills/session-recall/references/question-guidelines.md).
- **Standard first.** The JSON format ([format.md](skills/session-recall/references/format.md),
  [schema](skills/session-recall/schema/session-recall.v1.schema.json)) is the
  contract. Markdown notes and the runner are derived from it. Stable topic ids
  and tags let separate sessions link to each other.

### Layout

```
.claude-plugin/plugin.json         plugin manifest (name, version)
skills/session-recall/
  SKILL.md                         skill instructions
  references/question-guidelines.md
  references/format.md             export format v1
  schema/session-recall.v1.schema.json
  scripts/recall.py                config | validate | save | build | open | transcript
  viewer/session-recall.html       runner (copied into the output folder)
examples/                          sample export
CHANGELOG.md
```

Try the runner on the example without installing (from the repo root):

```sh
python3 skills/session-recall/scripts/recall.py build examples && open examples/session-recall.html
```

### Releasing

1. Bump `version` in [.claude-plugin/plugin.json](.claude-plugin/plugin.json)
   and add an entry to [CHANGELOG.md](CHANGELOG.md).
2. Commit, tag (`git tag v1.0.1`), push with tags.
3. Plugin users pick it up with `/plugin marketplace update gritee`.

### License

[MIT](LICENSE)
