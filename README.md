<div align="center" markdown="1">

# tdl_export

[![python](https://img.shields.io/badge/-Python_%7C_3.11%7C_3.12%7C_3.13%7C_3.14-blue?logo=python&logoColor=white)](https://www.python.org/downloads/source/)
[![uv](https://img.shields.io/badge/-uv_dependency_management-2C5F2D?logo=python&logoColor=white)](https://docs.astral.sh/uv/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
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

- **Automated Chat Export**: Uses `tdl chat export` to fetch messages and metadata from a specific Telegram group/channel.
- **Resumable Downloads**: Tracks downloaded files and chat state locally in JSON format (e.g., `./data/<group_id>.json`).
- **Duplicate Prevention**: Scans the local `./downloads/<group_id>` directory to skip already downloaded media files.
- **Batch Media Download**: Automatically downloads all new media files using `tdl dl` with high concurrency.

## 🚀 Quick Start

### Prerequisites

1. **Python 3.11+** installed.
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

You can run the script using `uv`:

```bash
uv run tdl_export
```

*(Note: The target Telegram group ID is currently set within the script's `main()` function. Modify `src/tdl_export/cli.py` to change the `group_id` before running.)*

## 📁 Directory Structure

- `data/`: Contains JSON files that track the exported chat history and download status for each group.
- `downloads/`: The destination folder where all media files are saved, organized by group ID.

## 📄 License

MIT — see `LICENSE`.
