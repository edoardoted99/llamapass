# LlamaPass CLI

CLI client for [LlamaPass](https://llamapass.org) - an Ollama gateway with authentication.

## Install

```bash
pip install llamapass
```

## Setup

```bash
llamapass config set-url https://llamapass.org
llamapass config set-key oah_your_api_key
```

## Usage

```bash
llamapass run gemma3       # interactive chat
llamapass list             # list available models
llamapass config show      # show current config
```
