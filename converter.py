import os
import yaml
from shared_library_handler import extract_shared_libraries
from github_actions_manager import create_composite_action, create_workflow_yaml

def parse_jenkinsfile(jenkinsfile_path):
    with open(jenkinsfile_path, "r") as f:
        content = f.read()
    parameters = []
    stages = []
    cron_schedule = None

    lines = content.splitlines()
    inside_parameters = False
    inside_stages = False
    current_stage = None

    for line in lines:
        line = line.strip()
        if line.startswith("parameters {"):
            inside_parameters = True
            continue
        elif inside_parameters and line == "}":
            inside_parameters = False
            continue
        elif inside_parameters and line.startswith("string"):
            try:
                parts = line.split("(",1)[1].rsplit(")",1)[0]
                param_dict = {}
                for kv in parts.split(","):
                    if ":" in kv:
                        k, v = kv.split(":", 1)
                        param_dict[k.strip()] = v.strip().strip('"').strip("'")
                if "name" in param_dict:
                    parameters.append(param_dict)
                else:
                    print(f"[WARNING] Skipping Parameter missing 'name': {param_dict}")
            except Exception as e:
                print(f"[WARNING] Failed to parse parameter line: {line}.Error: {e}")
        elif "triggers" in line and "cron" in line:
            if "'" in line:
                cron_schedule = line.split("cron('")[1].split("')")[0]
            elif '"' in line:
                cron_schedule = line.split('cron("')[1].split('")')[0]
        elif line.startswith("stages {"):
            inside_stages = True
            continue
        elif inside_stages:
            if line.startswith("stage("):
                current_stage = {
                    "name": line.split("stage(")[1].split(")")[0].strip("'\""),
                    "steps": []
                }
            elif "steps {" in line and current_stage:
                current_stage["inside_steps"] = True
            elif "}" in line and current_stage and current_stage.get("inside_steps"):
                current_stage["inside_steps"] = False
                stages.append(current_stage)
                current_stage = None
            elif current_stage and current_stage.get("inside_steps"):
                step = normalize_step(line)
                if step:
                    current_stage["steps"].append(step)

    return parameters, stages, cron_schedule


def normalize_step(line: str):
    line = line.strip().strip("'").strip('"')

    if line.startswith("script") or line.startswith("{") or line == "}":
        return None

    if line.startswith("sh "):
        cmd = line.replace("sh ", "").strip("'").strip('"')
        return {"run": cmd}

    if line.startswith("echo "):
        return {"run": line}

    if line.startswith("junit "):
        path = line.split("junit ")[1].strip("'").strip('"')
        return {
            "uses": "actions/upload-artifact@v3",
            "with": {"name": "junit-results", "path": path}
        }

    if line.startswith("archiveArtifacts"):
        return {
            "uses": "actions/upload-artifact@v3",
            "with": {
                "name": "app-artifact",
                "path": "build/libs/app-artifact.jar"
            }
        }

    if "aws s3 cp" in line:
        return {"run": line}

    if line.startswith("ssh "):
        return {"run": line}

    return {"run": line}


def convert_jenkinsfile_to_github_actions(jenkinsfile_path):
    parameters, stages, cron_schedule = parse_jenkinsfile(jenkinsfile_path)
    shared_libraries = extract_shared_libraries(jenkinsfile_path)

    workflow_name = os.path.basename(os.path.dirname(jenkinsfile_path)) or "main"
    composite_action_paths = []

    for stage in stages:
        action_name = stage["name"].replace(" ", "_").lower()
        create_composite_action(action_name, stage["steps"])
        composite_action_paths.append(action_name)

    create_workflow_yaml(
        workflow_name=workflow_name,
        composite_actions=composite_action_paths,
        cron_schedule=cron_schedule,
        parameters=parameters
    )
