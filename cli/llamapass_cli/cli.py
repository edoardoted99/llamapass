import os
import shutil
import subprocess
import sys

from llamapass_cli import __version__
from llamapass_cli.config import load, set_value
from llamapass_cli.proxy import start_proxy


def cmd_config(args):
    action = args[0] if args else "show"

    if action == "show":
        cfg = load()
        print(f"  url:     {cfg['url']}")
        print(f"  api_key: {cfg['api_key'][:10]}..." if cfg["api_key"] else "  api_key: (not set)")

    elif action == "set-url":
        if len(args) < 2:
            print("Usage: llamapass config set-url <url>")
            sys.exit(1)
        set_value("url", args[1])
        print(f"URL set to: {args[1]}")

    elif action == "set-key":
        if len(args) < 2:
            print("Usage: llamapass config set-key <key>")
            sys.exit(1)
        set_value("api_key", args[1])
        print("API key saved.")

    else:
        print(f"Unknown action: {action}")
        print("Available: show, set-url, set-key")
        sys.exit(1)


def main():
    args = sys.argv[1:]

    # Handle --version / -v
    if not args or args[0] in ("-h", "--help"):
        print(f"llamapass {__version__} — CLI client for LlamaPass")
        print()
        print("Usage: llamapass <ollama-command> [args...]")
        print()
        print("All Ollama commands are supported (run, list, show, pull, ps, ...)")
        print("Requests are proxied through your LlamaPass server with authentication.")
        print()
        print("LlamaPass commands:")
        print("  config show          Show current configuration")
        print("  config set-url <url> Set LlamaPass server URL")
        print("  config set-key <key> Set API key")
        print()
        print("Examples:")
        print("  llamapass run gemma3")
        print("  llamapass list")
        print("  llamapass pull llama3")
        print("  llamapass launch claude")
        sys.exit(0)

    if args[0] in ("-v", "--version"):
        print(f"llamapass {__version__}")
        sys.exit(0)

    # Handle config subcommand (llamapass-only)
    if args[0] == "config":
        cmd_config(args[1:])
        return

    # Everything else: proxy to ollama
    if not shutil.which("ollama"):
        print("Error: ollama is not installed. Install it from https://ollama.com")
        sys.exit(1)

    cfg = load()
    if not cfg.get("api_key"):
        print("Error: no API key configured. Run: llamapass config set-key <key>")
        sys.exit(1)

    server, port = start_proxy()
    if server is None:
        print("Error: failed to start local proxy.")
        sys.exit(1)

    env = os.environ.copy()
    env["OLLAMA_HOST"] = f"http://127.0.0.1:{port}"

    try:
        result = subprocess.run(["ollama"] + args, env=env)
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
