<div align="center" markdown="1">

# tdl_export

[![PyPI version](https://img.shields.io/pypi/v/swebenchv2.svg)](https://pypi.org/project/swebenchv2/)
[![python](https://img.shields.io/badge/-Python_%7C_3.12%7C_3.13%7C_3.14-blue?logo=python&logoColor=white)](https://www.python.org/downloads/source/)
[![uv](https://img.shields.io/badge/-uv_dependency_management-2C5F2D?logo=python&logoColor=white)](https://docs.astral.sh/uv/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![ty](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ty/main/assets/badge/v0.json)](https://github.com/astral-sh/ty)
[![Pydantic v2](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/pydantic/pydantic/main/docs/badge/v2.json)](https://docs.pydantic.dev/latest/contributing/#badges)
[![tests](https://github.com/Mai0313/tdl_export/actions/workflows/test.yml/badge.svg)](https://github.com/Mai0313/tdl_export/actions/workflows/test.yml)
[![code-quality](https://github.com/Mai0313/tdl_export/actions/workflows/code-quality-check.yml/badge.svg)](https://github.com/Mai0313/tdl_export/actions/workflows/code-quality-check.yml)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/Mai0313/tdl_export)
[![license](https://img.shields.io/badge/License-MIT-green.svg?labelColor=gray)](https://github.com/Mai0313/tdl_export/tree/main?tab=License-1-ov-file)
[![PRs](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/Mai0313/tdl_export/pulls)
[![contributors](https://img.shields.io/github/contributors/Mai0313/tdl_export.svg)](https://github.com/Mai0313/tdl_export/graphs/contributors)

</div>

🚀 **tdl_export** is an automated, resumable Telegram media downloader and chat exporter built on top of the [tdl](https://github.com/iyear/tdl) CLI tool.

Other Languages: [English](README.md) | [繁體中文](README.zh-TW.md) | [简体中文](README.zh-CN.md)

## ✨ Highlights

- **Incremental Chat Export**: Uses `tdl chat export` to fetch only the messages newer than the ones already archived.
- **Filesystem as the Ledger**: Download state is read back from the file names under `./data/downloads/<chat_id>/`, so deleting `./data/chats/` never costs you a re-download.
- **Size Verification**: Every local file is measured against the byte size Telegram reports. Truncated files — which `tdl` can leave behind under their final name — are removed and fetched again.
- **Concurrent Downloads**: Every chat is exported first, then each chat's missing files are fetched several at a time, in a `tdl dl` of its own so one chat's trouble never holds up the others.
- **Stop and Restart Anytime**: Each run works out what is missing from the folders, so a run stopped halfway, or picked up days later, fetches only what is not there in full. A file that was mid-transfer starts over from its first byte.

## 🚀 Quick Start

### Prerequisites

1. **Python 3.12+** installed.
2. **uv** package manager installed.
3. **tdl CLI** installed and logged into your Telegram account.

### Setup

1. Clone the repository:
    ```bash
    git clone https://github.com/Mai0313/tdl_export.git
    cd tdl_export
    ```
2. Install dependencies:
    ```bash
    uv sync
    ```

### Usage

Name the chats you want mirrored:

```bash
uv run tdl_export 5727382280 8801654201
```

With no arguments it falls back to the list in `src/tdl_export/cli.py`.

Add `--verify` to re-export the whole chat instead of only what is new, which refreshes the recorded sizes and re-checks every file on disk. It is much slower — `tdl chat export` is rate limited to 2 requests per second — so it is worth running occasionally rather than every time:

```bash
uv run tdl_export 5727382280 --verify
```

The first run on a chat archived by an older version does this automatically, because those archives carry no sizes yet.

`--limit` sets how many files download at once (default 4) and `--threads` how many parts of one large file (default 4). The defaults were measured: higher values ran no faster, because Telegram capped the measured account at about 12 MB/s on a line that does three times that, and photos and other small files stay near one per second whatever the setting:

```bash
uv run tdl_export --limit 8
```

Press Ctrl+C to stop. Finished files stay, and the next run continues from there.

## 📁 Directory Structure

- `data/chats/<chat_id>.json`: The exported message history for one chat, including the byte size of each media file.
- `data/downloads/<chat_id>/`: The media, named `<chat_id>_<message_id>_<filename>` by `tdl`. That prefix is what the tool reads back to know what it already has.

## 📄 License

MIT — see `LICENSE`.
