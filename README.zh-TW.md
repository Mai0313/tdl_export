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

🚀 **tdl_export** 是一個基於 [tdl](https://github.com/iyear/tdl) 命令行工具建構的自動化、支援斷點續傳的 Telegram 媒體下載器與聊天紀錄匯出工具。

其他語言: [English](README.md) | [繁體中文](README.zh-TW.md) | [简体中文](README.zh-CN.md)

## ✨ 重點特色

- **自動匯出聊天紀錄**：使用 `tdl chat export` 獲取指定 Telegram 群組或頻道的歷史訊息與元數據。
- **支援斷點續傳**：將聊天數據與下載狀態記錄在本地 JSON 檔案中（例如 `./data/<group_id>.json`）。
- **避免重複下載**：自動掃描本地 `./downloads/<group_id>` 目錄，略過已下載的媒體檔案。
- **批次媒體下載**：自動呼叫 `tdl dl` 高併發下載所有新增的媒體檔案。

## 🚀 快速開始

### 前置要求

1.  已安裝 **Python 3.11+**。
2.  已安裝 **uv** 套件管理器。
3.  已安裝 **tdl CLI** 並且已登入您的 Telegram 帳號。

### 安裝步驟

1.  複製倉庫：
    ```bash
    git clone https://github.com/Mai0313/tdl_export.git
    cd tdl_export
    ```
2.  安裝依賴：
    ```bash
    uv sync
    ```

### 使用方法

您可以使用 `uv` 執行腳本：

```bash
uv run tdl_export
```

*（註：目標 Telegram 群組 ID 目前在腳本的 `main()` 函式中設定。執行前請修改 `src/tdl_export/cli.py` 以更改 `group_id`。）*

## 📁 目錄結構

- `data/`: 包含記錄每個群組聊天歷史和下載狀態的 JSON 檔案。
- `downloads/`: 儲存所有下載媒體檔案的目標資料夾，依照群組 ID 分類。

## 📄 授權

MIT — 詳見 `LICENSE`。