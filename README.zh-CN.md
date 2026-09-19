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

🚀 **tdl_export** 是一个基于 [tdl](https://github.com/iyear/tdl) 命令行工具构建的自动化、支持断点续传的 Telegram 媒体下载器和聊天记录导出工具。

其他语言: [English](README.md) | [繁體中文](README.zh-TW.md) | [简体中文](README.zh-CN.md)

## ✨ 重点特色

- **增量导出聊天记录**：使用 `tdl chat export`，只抓取比已归档消息更新的部分。
- **以文件系统为准**：下载状态从 `./data/downloads/<chat_id>/` 的文件名读回，即使删掉 `./data/chats/` 也不会重新下载。
- **尺寸校验**：每个本地文件都会与 Telegram 报告的字节数比对。`tdl` 可能把下载失败的半截文件改名成正式文件名，这类文件会被删除并重新抓取。
- **批量媒体下载**：自动调用 `tdl dl` 并发下载所有新增的媒体文件。

## 🚀 快速开始

### 前置要求

1. 已安装 **Python 3.11+**。
2. 已安装 **uv** 包管理器。
3. 已安装 **tdl CLI** 并已登录您的 Telegram 账号。

### 安装步骤

1. 克隆仓库：
    ```bash
    git clone https://github.com/Mai0313/tdl_export.git
    cd tdl_export
    ```
2. 安装依赖：
    ```bash
    uv sync
    ```

### 使用方法

指定您要同步的聊天室：

```bash
uv run tdl_export 5727382280 8801654201
```

不带参数时，会沿用 `src/tdl_export/cli.py` 里的列表。

加上 `--verify` 会改成全量重新导出，刷新记录的文件尺寸并重新检查磁盘上的每个文件。它慢得多（`tdl chat export` 被限速在每秒 2 个请求），适合偶尔运行而不是每次都跑：

```bash
uv run tdl_export 5727382280 --verify
```

旧版本留下的归档文件没有尺寸信息，所以第一次运行会自动做这件事。

## 📁 目录结构

- `data/chats/<chat_id>.json`: 单个聊天室的消息记录，包含每个媒体文件的字节大小。
- `data/downloads/<chat_id>/`: 媒体文件，由 `tdl` 命名为 `<chat_id>_<message_id>_<文件名>`。这个前缀就是本工具判断「已经下载过」的依据。

## 📄 授权

MIT — 详见 `LICENSE`。
