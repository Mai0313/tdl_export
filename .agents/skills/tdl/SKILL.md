---
name: tdl
description: >-
  How the `tdl` Telegram CLI (github.com/iyear/tdl) really behaves when you drive it from a script,
  and how this repo's `tdl_export` builds on it. Read this before touching anything that shells out to
  `tdl chat export` or `tdl dl`, before deciding whether a media file was already downloaded, and
  before believing a tdl run that exited 0. Use it whenever a download "succeeded" but the file is
  empty or truncated, a run downloads nothing and reports nothing, a re-run fetches files that are
  already on disk, a `.tmp` file turns up, an export seems to walk the whole chat every time, or a
  subprocess call to tdl appears to hang. Also use it when someone asks how `tdl_export` knows what it
  already has, or proposes tracking download state in a JSON flag, a database, or a filename.
---

# Driving tdl from a script

Everything here was verified against **tdl v0.20.4** (commit `9d7d49e`) by reading the Go source at
that tag and by running it against real chats. `references/tdl-internals.md` carries the source
citations and the per-flag detail; this file is what you need to make decisions.

## The thing that breaks every naive design

**tdl reports success it did not have.** `core/downloader/downloader.go` logs a failed transfer and
returns `nil` for every error except a user cancel, so the progress callback takes its success path:
the partial `.tmp` is renamed to the **final** filename, the mtime is set, and the process exits **0**.

Three consequences you have to design around:

- **A file's existence proves nothing.** Only its byte size does, compared against the size Telegram
    reports for that message.
- **The exit code is not a result.** Reconcile what you asked for against what is on disk afterwards.
    A run can also legitimately download nothing and say nothing — if every entry in a `-f` file gets
    filtered out, tdl prints one line and exits 0.
- **A `.tmp` is dead weight, not progress.** tdl opens it with `O_TRUNC`, so the next attempt starts
    from byte zero regardless. A clean Ctrl+C deletes it; a hard kill leaves it. Sweeping stale `.tmp`
    files loses nothing.

This repo found 15 files in a real tree that the old filename-only design had written off as
complete: 7 at zero bytes, 5 abandoned `.tmp` (largest 1.7 GB), and 3 truncated multi-gigabyte videos.

## Reading download state off the disk

The default download template is `{{ .DialogID }}_{{ .MessageID }}_{{ filenamify .FileName }}`, where
`.DialogID` is the **raw positive** chat id — the same number `tdl chat export` writes as its
top-level `id`, and the same one you pass to `--chat`. So a per-chat directory plus that prefix is a
complete record of which messages arrived.

Parse `^<chat_id>_(\d+)_` and **stop there**. Do not try to reconstruct the original filename from the
tail: `filenamify` truncates at 100 runes *including* the extension, so a long name can lose it
entirely, and it maps `<>:"/\|?*` and control characters to `!`. Skip `*.tmp` while scanning.

Pin `--template` explicitly even when you want the default. A `TDL_TEMPLATE` environment variable
silently replaces it when the flag is absent (viper reads `TDL_`-prefixed variables automatically),
and the naming contract is the thing you are reading state back out of.

## Flags that decide whether a script works

| Flag                           | Why it matters                                                                                                                                                                                                                    |
| ------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--continue` or `--restart`    | **Pass one.** With neither, leftover resume state makes tdl block on an interactive confirm prompt — a hang in a subprocess with no TTY. Resume is per-file-in-the-list, never byte-level, so the two differ less than they look. |
| `--template`                   | Pin it, per above.                                                                                                                                                                                                                |
| `--skip-same`                  | `os.Stat` on the exact rendered path plus an exact size match. Useful, but it runs **after** the per-message API call, so it saves bandwidth and no API budget. It is also defeated by any renaming of the file on disk.          |
| `--rewrite-ext`                | Renames the finished file to a MIME-sniffed extension, which the next run's `--skip-same` then fails to find. The two together re-download forever. Pick one.                                                                     |
| `--group`                      | Acknowledged-broken upstream, and an export already lists every album member. Leave it off.                                                                                                                                       |
| `-i/--include`, `-e/--exclude` | Matched against the extension of the **original Telegram filename**, case-sensitively, and mutually exclusive. `-i mp4` does not match `.MP4`. Filter in your own code instead.                                                   |

## What an export gives you, and what it costs

`tdl chat export` is hard rate-limited to **2 requests per second at 100 messages each**, and no flag
lifts it. Walking a 13k-message chat takes a couple of minutes. That is the budget to design against.

- **Incremental**: `-T id -i <N>` with a *single* integer expands to `[N, MaxInt]`, both bounds
    inclusive. Keep your own high-water mark and pass `max_seen + 1`.
- **`--all`** adds the messages with no downloadable media. It costs no extra API calls — the same
    pages are walked either way — so the only question is whether you want the text history archived.
- **`--raw`** attaches the full MTProto message, which is the only way to learn a file's **size**:
    `Media.Document.Size`, or for a photo `Media.Photo.Sizes[-1]` (its `.Sizes[-1]` when progressive,
    else `.Size`). Verified exact against 15,891 real messages.
- **`--with-content`** is what adds `date` and `text`. Without it there is no date field at all.

Downloading has a different cost shape: `tdl dl -f` spends **one serial `messages.getHistory` per
message id** in the file, with no batching. Handing it 11,000 already-downloaded ids is 11,000 round
trips before `--skip-same` gets a chance to skip anything. Prune the list yourself — that is the only
thing that saves flood-wait budget.

The `-f` JSON itself is read very narrowly: the top-level `id` (a **bare number**, and the **first**
key, or you pay for materialising the whole array), and per message `id` plus `type == "message"` plus
a non-empty `file` or `photo` as a has-media gate. Everything else is ignored, so extra fields are
safe.

## An empty `file` is usually not a bug

A message that used to carry media and now exports with `file: ""` normally means the media was
removed from the message, not that tdl lost it. In this repo's targets that is routine: several of
them are file-manager bots that delete their own attachments after a while, and a group whose history
has been wiped exports zero messages while still appearing in `tdl chat ls`.

Treat it as "this is no longer fetchable" rather than something to retry. `tdl chat ls` distinguishes
the cases: a chat you left is gone from the list entirely, while a bot that cleaned up its files is
still there.

## How `tdl_export` puts this together

`src/tdl_export/cli.py` is one ordered pass per chat, and every step in it exists because of something
above. **`CLAUDE.md`'s Architecture section is the description of that pass** — read it there rather
than here, so the two cannot drift apart when the code moves.

What is worth knowing before you open either: the pass never asks tdl what has been downloaded, it
reads that off the directory; `--verify` is what forces the full export when the archive itself is
what needs rebuilding; and the run's result comes from re-scanning the disk afterwards, not from tdl.

## When a run does nothing

Work down this ladder rather than guessing:

1. **Did the `-f` file survive parsing?** Entries need `type: "message"`, a non-negative `id` and a
    non-empty `file`. Anything else is dropped in silence.
2. **Is the chat reachable?** `tdl chat ls` shows whether you are still in it. A numeric chat id also
    needs a warm peer cache in `~/.tdl/data` — on a fresh machine run `tdl chat ls` once first.
3. **Do the messages still carry media?** Export the specific ids with `-T id -i <n>,<n> --all --raw`
    and look for a `Media` key.
4. **Is it silent rather than stuck?** A tdl process producing no output for a long time is usually
    absorbing a FLOOD_WAIT, which it does indefinitely and without saying so. Killing and retrying
    compounds it.
