---
description: Look up exact Godot 4.7 API signatures locally, or verify GDScript against the engine analyser
argument-hint: <Class | Class.member | keyword | path/to/file.gd>
allowed-tools: Read, Bash, Glob, Grep
---

# /gd:api — the local Godot 4.7 reference

@gsd-gd/references/gdscript-4x.md

Query: **$ARGUMENTS**

## Decide what was asked, then answer it

| the argument looks like | run |
|---|---|
| `CharacterBody3D` (a class) | `python gsd-gd/bin/gddoc.py class CharacterBody3D` |
| `Input.action_press` (has a dot) | `python gsd-gd/bin/gddoc.py member Input.action_press` |
| `something.gd` (a file) | `python gsd-gd/bin/gd.py check something.gd` |
| anything else (a keyword) | `python gsd-gd/bin/gddoc.py search <query>` |
| empty | `python gsd-gd/bin/gddoc.py stats`, then explain what is available |

Add `--full` to `class` when the user wants behaviour, not just signatures.

## Answer with the real signature, not a paraphrase

Quote the signature verbatim from the tool output. The whole point of this
command is that the answer is the engine's, not a recollection — so do not
restate it in your own words and do not "simplify" a default value.

If the lookup misses, use the `did_you_mean` list. If the class does not exist
in this build, say so plainly and give the 4.7 replacement.

## If the question is really "how do I do X"

Search first, then read the class, then show a small typed example — and say
which lookups you did. An example written without a lookup is exactly the
failure mode this command exists to prevent.

```bash
python gsd-gd/bin/gddoc.py search <keyword>     # find the surface
python gsd-gd/bin/gddoc.py class <Class> --full # read what it actually does
```

For behaviour the XML does not explain, read the engine source at
the engine source tree, **if this machine has one** — it is the same tree the
binary was built from. `gd config` prints `toolchain.godot.source_root`; a blank
value means there is no checkout here and the class reference is the whole
answer:

```bash
grep -rn "<symbol>" "$SOURCE_ROOT/scene/" "$SOURCE_ROOT/core/"
```

## Maintenance

```bash
python gsd-gd/bin/gddoc.py index --force   # after rebuilding or upgrading the engine
```

The index is `gsd-gd/cache/godot-api-index.json`, built from
`<source_root>/doc/classes/` and each module's `doc_classes/` — or, with no
source tree, from `godot --doctool`, which makes the binary dump the same XML it
was compiled with. It is
version-locked to the binary because it comes from the binary's own source tree
— if the engine is rebuilt from a newer checkout, re-index or the reference and
the runtime will disagree.
