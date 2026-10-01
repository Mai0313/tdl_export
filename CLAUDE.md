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

**The pytest step in `test.yml` keeps its explicit `shell: bash`.** That step pipes pytest into
`tee`, and only an explicit shell runs with `pipefail`; under Actions' default `bash -e` a failing
suite, a collection error and a missed coverage gate all read as a pass. The file comes from
`Mai0313/repo_template`, so a template sync must keep that key.

**Tests never touch `data/` or `~/.tdl`, and never run the real tdl.** `tests/conftest.py` points
every data path at a temp dir and replaces `subprocess.run`, so a test that forgets its fake fails
instead of reaching Telegram.

## Commands

```bash
uv sync --all-groups                  # ruff, pytest and the docs tooling live in non-default groups
uv run tdl_export <chat_id> ...       # mirror those chats; no arguments falls back to the list in cli.py
uv run tdl_export <chat_id> --verify  # full re-export: refresh every recorded size, re-check every file
uv run tdl_export --limit 8           # more files at once than the measured default
make test                             # pytest, with the coverage gate from pyproject.toml
make fmt                              # every pre-commit hook, the same set CI runs
make gen-docs                         # rebuild docs/ from the READMEs, src/ and scripts/
```

`tdl` has to be on PATH and logged in, and on a fresh machine its peer cache has to be warmed before a
numeric chat id will resolve at all. The `tdl` skill's diagnostic section covers that along with the
rest of the "the run did nothing and said nothing" cases.

## Architecture

One module per concept under `src/tdl_export/`: `archive.py` is the chat archive and its models,
`tdl.py` is everything that encodes tdl's command line and output formats, `ledger.py` is the
download folder read as the record of what arrived, and `cli.py` runs the pass. `fire` exposes
`run()`. A run is one ordered pass over every chat, and the order is the design rather than an
implementation detail:

1. **Per chat, bring the archive up to date.** An archive where no message carries a `size` predates
    them, so a full export is forced; otherwise the export is incremental from `max(id) + 1`. This is
    what lets an archive written by an older version repair itself without anyone knowing to pass
    `--verify`. `--all` and `--with-content` make the archive a chat history rather than a download
    list, and `--raw` is there only for the byte size. Merging is keyed on message id, newest wins. A
    chat whose export fails is skipped, and the run's exit code says so at the end.
2. **Per chat, reconcile with the disk.** Sweep `*.tmp`, lower-case file extensions, read the folder
    back into `{message_id: path}` off the filename prefix, and list what is pending: a message with a
    `file` that is missing, or present at the wrong size. A wrong-size file is deleted *before* the
    download rather than overwritten, so a retry cannot leave two files for one message under
    different extension casings.
3. **One `tdl dl` per chat with something pending, in turn.** One process for every chat would share
    its download slots, but one message tdl cannot resolve then stops every chat after it, on every
    run; the skill's "One tdl process at a time" has the mechanics. The speed comes from `--limit`
    inside each process.
4. **Measure again.** tdl's exit code says nothing about whether the files arrived, so the per-chat
    table of what is still missing or the wrong size is the only honest result a run can give. The
    run exits 1 only when a tdl process failed; a file still missing is reported, not failed, since
    some never come back (media its sender deleted).

**Stopping halfway and starting again is the normal case, not a recovery path.** Every run rebuilds
its pending list from the folders, so a run stopped at any point, or picked up days later, fetches
exactly the files that are not there in full. The archive is saved before anything downloads, a
leftover `.tmp` is swept, and tdl's own resume state is never read. A single file cannot be resumed:
tdl restarts an interrupted transfer from byte zero.

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
- **`--template`, `--limit` and `--threads` are always passed explicitly.** tdl reads a
    `TDL_<FLAG>` environment variable for each of them when it is left out, and the rendered filename
    is what the ledger is read back out of, even where it matches tdl's default.
- **The concurrency defaults come from a measurement, not from the machine.** tdl's throughput is
    bound by the network and by Telegram, never by CPU count; the skill has the numbers. Change
    `LIMIT` or `THREADS` only with a new measurement.
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
