---
description: Dashboard — where the project is, what is green, what is blocked
allowed-tools: Read, Bash, Glob, Grep
---

# /gd:status

Gather, then summarise. Do not editorialise; report what the tools say.

```bash
python gsd-gd/bin/gd.py doctor
python gsd-gd/bin/gd.py state
python gsd-gd/bin/gd.py phase list
python gsd-gd/bin/gd.py check
git -C . log --oneline -10
git -C . status --short
```

Then the gate status, from the last verdicts on disk (do not re-run them here -
`/gd:playtest` does that):

```bash
ls game/*/lab/*.json
for v in game/*/.gd_out/*/verdict.json; do echo "== $v"; python -c "import json,sys;d=json.load(open(sys.argv[1]));print(' ', d.get('name'), 'PASS' if d.get('ok') else 'FAIL', d.get('perf',{}))" "$v"; done
```

## Report

A short table, in this order:

| | |
|---|---|
| beat | from STATE.md |
| phase | current phase, jobs done / total |
| loop locked / palette locked / greybox passed | yes-no, from STATE.md |
| gates | n passing, m failing, which |
| GDScript check | clean, or the failing files |
| perf | last measured fps_avg / fps_1pct_low / draw calls vs budget |
| licences | rows in CREDITS.md vs external assets on disk |
| blockers | from STATE.md, plus anything the tools just surfaced |

Finish with **one** recommended next command and why. Not a menu - the single
next action.
