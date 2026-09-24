import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

RUNTIME_PATHS = (
    "agent.py",
    "models.py",
    "subagents.py",
    "instructions.md",
    "pyproject.toml",
    "uv.lock",
    "README.md",
    "refinery_data",
    "tools",
    "middleware",
    "skills",
    "sandbox",
)


def main() -> None:
    required = ("LANGSMITH_API_KEY", "LANGSMITH_GATEWAY_API_KEY", "LANGSMITH_WORKSPACE_ID")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"Missing deployment configuration: {', '.join(missing)}")
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="refinery-deploy-") as temporary:
        staged = Path(temporary)
        for name in RUNTIME_PATHS:
            source = root / name
            if source.is_dir():
                shutil.copytree(
                    source, staged / name, ignore=shutil.ignore_patterns("__pycache__", "*.db")
                )
            else:
                shutil.copy2(source, staged / name)
        env_path = staged / ".env"
        values = {
            "LANGSMITH_GATEWAY_API_KEY": os.environ["LANGSMITH_GATEWAY_API_KEY"],
            "AGENT_MODEL": os.environ.get("AGENT_MODEL", "langsmith:openai/gpt-6-sol"),
        }
        env_path.touch(mode=0o600)
        env_path.write_text(
            "".join(f"{name}={json.dumps(value)}\n" for name, value in values.items())
        )
        subprocess.run(
            [
                "mda",
                "deploy",
                str(staged),
                "--name",
                os.environ.get("MDA_DEPLOYMENT_NAME", "refinery-reliability-agent"),
                "--deployment-type",
                os.environ.get("MDA_DEPLOYMENT_TYPE", "dev"),
                "--workspace-id",
                os.environ["LANGSMITH_WORKSPACE_ID"],
                "--context-strategy",
                "overwrite",
            ],
            check=True,
        )


if __name__ == "__main__":
    main()
