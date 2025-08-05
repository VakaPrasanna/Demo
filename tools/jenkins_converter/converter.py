import yaml
from pathlib import Path
import sys

def update_build_action(deploy_env_default):
    path = Path(".github/actions/build/action.yml")
    data = yaml.safe_load(path.read_text())
    data.setdefault("inputs", {})["DEPLOY_ENV"] = {
        "description": "Environment to deploy",
        "default": deploy_env_default
    }
    path.write_text(yaml.safe_dump(data, sort_keys=False))

def main():
    # Example: parse Jenkinsfile to get default for DEPLOY_ENV
    # Fallback to 'dev'
    deploy_env = "dev"
    jenkinsfile = Path("Jenkinsfile").read_text()
    m = re.search(r"choice\(name:\s*'DEPLOY_ENV'.*choices:\s*\[([^\]]+)\]", jenkinsfile, re.DOTALL)
    if m:
        choices = [c.strip().strip("'\"") for c in m.group(1).split(",")]
        if choices:
            deploy_env = choices[0]

    update_build_action(deploy_env)
    print(f"Updated build composite action with default DEPLOY_ENV={deploy_env}")

if __name__ == "__main__":
    main()

