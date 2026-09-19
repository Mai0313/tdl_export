# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A small Python wrapper around the [`tdl`](https://github.com/iyear/tdl) CLI that keeps a local mirror
of the media in one or more Telegram chats. Everything that talks to Telegram is tdl; what lives here
is the bookkeeping tdl does not do — which messages have already arrived, and whether what is on disk
is actually the file it claims to be.

**The download ledger is the filesystem.** tdl puts the chat id and the message id at the front of
every filename it writes, so a listing of `data/downloads/<chat_id>/` already answers "what do I
have". `data/chats/<chat_id>.json` is an archive of the chat's messages, not a ledger: deleting the
whole of `data/chats/` costs one export and never a re-download. That split replaced a `downloaded`
boolean persisted in the JSON, which was recomputed from disk on every run anyway — a cache that read
as authoritative.

**A file's existence is not proof that it arrived**, which is why the archive also records the byte
size Telegram reports for each message and every run measures the local file against it. PR #30 has
the evidence that made this necessary.

**The `tdl` skill under `.agents/skills/` owns tdl's behaviour** — what its flags really do, what it
fails to report, what an export costs, and the source citations behind all of it. Read it before
changing anything in the download path. This file says why the code here is shaped the way it is; the
skill says how to judge tdl. A claim written in both places drifts, so anything about tdl itself lives
there and is only referred to from here.

## Development flow

Read `gh-dev-flow` before starting; it owns the path from a task landing to the change being merged.

**CI cannot currently fail on a test.** `test.yml` runs pytest only when a `tests/` directory exists,
and that step is `uv run pytest -vv | tee .coverage.txt` with no `shell:` key anywhere in the file, so
it runs under Actions' default `bash -e` — which does not set `pipefail` — and the pipeline reports
`tee`'s status. A failing suite, a collection error and a missed coverage gate would all read as a
pass. There are no tests today so nothing is being hidden yet, but adding the first one means fixing
that step in the same change, or CI will report green on a red suite. `test.yml` comes from the repo
template, so the fix belongs upstream as well as here.

## Commands

```bash
uv sync --all-groups                  # ruff, pytest and the docs tooling live in non-default groups
uv run tdl_export <chat_id> ...       # mirror those chats; no arguments falls back to the list in cli.py
uv run tdl_export <chat_id> --verify  # full re-export: refresh every recorded size, re-check every file
make fmt                              # pre-commit: ruff, mdformat, codespell, ty, gitleaks, uv-lock
make gen-docs                         # rebuild docs/ from the READMEs, src/ and scripts/
```

`tdl` has to be on PATH and logged in, and on a fresh machine its peer cache has to be warmed before a
numeric chat id will resolve at all. The `tdl` skill's diagnostic section covers that along with the
rest of the "the run did nothing and said nothing" cases.

## Architecture

`src/tdl_export/cli.py` is the whole package today. `fire` exposes `run()`, which loops over chat ids
and calls `download_media` once per chat. That function is one ordered pass, and the order is the
design rather than an implementation detail:

1. **Load the archive and decide the export scope.** An archive where no message carries a `size`
    predates them, so a full export is forced; otherwise the export is incremental from `max(id) + 1`.
    This is what lets an archive written by an older version repair itself without anyone knowing to
    pass `--verify`.
2. **Export, merge, save.** `--raw` is there only to reach the media's byte size, which the plain
    export does not carry; the blob is dropped as soon as the size is read. `--all` keeps the messages
    with no downloadable media and `--with-content` fills in their dates and text; together they are
    why the archive is a chat history rather than a download list, and neither costs extra API calls.
    Merging is keyed on message id, newest wins.
3. **Reconcile with the disk.** Sweep `*.tmp`, lower-case file extensions, then read the directory
    back into `{message_id: path}` off the filename prefix.
4. **Work out what is pending.** A message with a `file` that is missing from disk, or present at the
    wrong size. A wrong-size file is deleted *before* the download rather than overwritten, so a retry
    cannot leave two files for one message under different extension casings.
5. **Download, then check again.** tdl's exit code says nothing about whether the files arrived, so
    re-scanning and reporting what is still missing or still the wrong size is the only honest result
    a run can give.

The archive is written through a staging file and `Path.replace`, because it holds the only copy of
the recorded sizes and rebuilding it costs a full rate-limited export.

## Project rules

- **Structured values are Pydantic models.** `Message` and `ChatData` carry everything that travels
    between functions, and `ChatData` does double duty as both the on-disk archive and the request
    handed to `tdl dl`. The one exception is `get_media_size`, which reads tdl's raw MTProto blob as a
    `dict[str, Any]`: modelling a structure tdl owns, and that is discarded the moment the size comes
    out of it, buys nothing. Do not add a `dataclass` or a `TypedDict`.
- **`ChatData` declares `id` before `messages` on purpose.** tdl's `-f` parser materialises every
    top-level value until it reaches `id`, so putting `messages` first decodes the whole array for
    nothing. Correctness is a separate matter and comes from `id` being typed `int`: tdl's assertion on
    that value is unchecked, and a string there panics rather than erroring.
- **`--template` is pinned in the code even though it matches tdl's default**, because the rendered
    filename is what the ledger is read back out of, and an environment variable can move that default
    under you.
- **Read the `<chat_id>_<message_id>_` prefix and nothing else.** tdl rewrites and truncates the rest
    of the name; the skill has the specifics and the version they were measured against.
- **A change that outdates the `tdl` skill updates that skill in the same PR.** It is read into every
    session that touches this code and nothing re-checks it when tdl moves, so a line that has stopped
    being true keeps costing on every one of them.
- **`AGENTS.md` is a symlink to this file, and `.claude/skills` to `.agents/skills`.** Both are
    committed as mode 120000 so a fresh clone picks them up. Do not replace either with a real file: a
    hand-maintained second copy drifts, and the copy nobody is reading is the one that goes stale.
- **`data/` and `docs/` are gitignored.** `docs/` is generated by `make gen-docs` — edit the READMEs
    and the docstrings, never the output. `data/` holds both the archives and the media, which is the
    point of the layout: one directory holds everything worth backing up.
- **English for anything that reaches GitHub**: commit messages, PR titles and bodies, issues,
    comments, and the code itself.
