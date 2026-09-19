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

🚀 **tdl_export** 是一個基於 [tdl](https://github.com/iyear/tdl) 命令行工具建構的自動化、支援斷點續傳的 Telegram 媒體下載器與聊天紀錄匯出工具。

其他語言: [English](README.md) | [繁體中文](README.zh-TW.md) | [简体中文](README.zh-CN.md)

## ✨ 重點特色

- **增量匯出聊天紀錄**：使用 `tdl chat export`，只抓取比已封存訊息更新的部分。
- **以檔案系統為準**：下載狀態是從 `./data/downloads/<chat_id>/` 的檔名讀回來的，就算刪掉 `./data/chats/` 也不會重新下載。
- **尺寸驗證**：每個本地檔案都會跟 Telegram 回報的位元組數比對。`tdl` 可能把下載失敗的半截檔改名成正式檔名，這類檔案會被刪除並重新抓取。
- **批次媒體下載**：自動呼叫 `tdl dl` 高併發下載所有新增的媒體檔案。

## 🚀 快速開始

### 前置要求

1. 已安裝 **Python 3.11+**。
2. 已安裝 **uv** 套件管理器。
3. 已安裝 **tdl CLI** 並且已登入您的 Telegram 帳號。

### 安裝步驟

1. 複製倉庫：
    ```bash
    git clone https://github.com/Mai0313/tdl_export.git
    cd tdl_export
    ```
2. 安裝依賴：
    ```bash
    uv sync
    ```

### 使用方法

指定您要同步的聊天室：

```bash
uv run tdl_export 5727382280 8801654201
```

不帶參數時，會沿用 `src/tdl_export/cli.py` 裡的清單。

加上 `--verify` 會改成全量重新匯出，刷新記錄的檔案尺寸並重新檢查磁碟上的每個檔案。它慢得多（`tdl chat export` 被限速在每秒 2 個請求），適合偶爾跑而不是每次都跑：

```bash
uv run tdl_export 5727382280 --verify
```

舊版本留下的封存檔沒有尺寸資訊，所以第一次執行會自動做這件事。

## 📁 目錄結構

- `data/chats/<chat_id>.json`: 單一聊天室的訊息紀錄，包含每個媒體檔案的位元組大小。
- `data/downloads/<chat_id>/`: 媒體檔案，由 `tdl` 命名為 `<chat_id>_<message_id>_<檔名>`。這個前綴就是本工具判斷「已經下載過」的依據。

## 📄 授權

MIT — 詳見 `LICENSE`。
