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

🚀 **tdl_export** 是一个基于 [tdl](https://github.com/iyear/tdl) 命令行工具构建的自动化、支持断点续传的 Telegram 媒体下载器和聊天记录导出工具。

其他语言: [English](README.md) | [繁體中文](README.zh-TW.md) | [简体中文](README.zh-CN.md)

## ✨ 重点特色

- **自动导出聊天记录**：使用 `tdl chat export` 获取指定 Telegram 群组或频道的历史消息和元数据。
- **支持断点续传**：将聊天数据和下载状态记录在本地 JSON 文件中（如 `./data/<group_id>.json`）。
- **避免重复下载**：自动扫描本地 `./downloads/<group_id>` 目录，跳过已下载的媒体文件。
- **批量媒体下载**：自动调用 `tdl dl` 并发下载所有新增的媒体文件。

## 🚀 快速开始

### 前置要求

1.  已安装 **Python 3.11+**。
2.  已安装 **uv** 包管理器。
3.  已安装 **tdl CLI** 并已登录您的 Telegram 账号。

### 安装步骤

1.  克隆仓库：
    ```bash
    git clone https://github.com/Mai0313/tdl_export.git
    cd tdl_export
    ```
2.  安装依赖：
    ```bash
    uv sync
    ```

### 使用方法

您可以使用 `uv` 运行脚本：

```bash
uv run tdl_export
```

*（注：目标 Telegram 群组 ID 目前在脚本的 `main()` 函数中配置。运行前请修改 `src/tdl_export/cli.py` 以更改 `group_id`。）*

## 📁 目录结构

- `data/`: 包含记录每个群组聊天历史和下载状态的 JSON 文件。
- `downloads/`: 保存所有下载的媒体文件的目标文件夹，按群组 ID 分类。

## 📄 授权

MIT — 详见 `LICENSE`。