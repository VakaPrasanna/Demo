import os
import re
import yaml
from shared_library_handler import extract_shared_libraries
from github_actions_manager import create_workflow_yaml


def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def parse_jenkinsfile(jenkinsfile_path):
    """Parse Jenkinsfile and extract parameters, stages, cron triggers."""
    parameters = []
    stages = []
    cron_schedule = None

    with open(jenkinsfile_path, "r") as f:
        lines = f.readlines()

    inside_parameters = False
    inside_stages = False
    current_stage = None
    inside_sh_block = False
    sh_buffer = []

    for raw_line in lines:
        line = raw_line.strip()

        # ---- Parameters ----
        if line.startswith("parameters {"):
            inside_parameters = True
            continue
        elif inside_parameters and line == "}":
            inside_parameters = False
            continue
        elif inside_parameters:
            if line.startswith(("string", "boolean", "choice")):
                try:
                    parts = line.split("(", 1)[1].rsplit(")", 1)[0]
                    param_dict = {}
                    for kv in parts.split(","):
                        if "=" in kv:
                            k, v = kv.split("=", 1)
                            param_dict[k.strip()] = v.strip().strip('"').strip("'")
                    if "name" in param_dict:
                        parameters.append(param_dict)
                    else:
                        print(f"[WARNING] Skipping Parameter missing 'name': {param_dict}")
                except Exception as e:
                    print(f"[WARNING] Failed to parse parameter line: {line}. Error: {e}")

        # ---- Cron triggers ----
        elif "triggers" in line and "cron" in line:
            if "'" in line:
                cron_schedule = line.split("cron('")[1].split("')")[0]
            elif '"' in line:
                cron_schedule = line.split('cron("')[1].split('")')[0]

        # ---- Stages ----
        elif line.startswith("stages {"):
            inside_stages = True
            continue
        elif inside_stages:
            # New stage
            stage_match = re.match(r"stage\s*\(['\"](.+?)['\"]\)", line)
            if stage_match:
                current_stage = {"name": stage_match.group(1), "steps": []}
                continue

            # Inside steps
            if "steps {" in line and current_stage:
                current_stage["inside_steps"] = True
                continue
            elif "}" in line and current_stage and current_stage.get("inside_steps"):
                current_stage["inside_steps"] = False
                stages.append(current_stage)
                current_stage = None
                continue

            # Multiline sh start
            if line.startswith(("sh '''", 'sh """')):
                inside_sh_block = True
                sh_buffer = []
                continue

            # Multiline sh end
            if inside_sh_block and (line.endswith("'''") or line.endswith('"""')):
                inside_sh_block = False
                if current_stage:
                    script = "\n".join(sh_buffer).strip()
                    if script and not script.startswith(("//", "/*", "*/", "*")):
                        current_stage["steps"].append({"run": script})
                sh_buffer = []
                continue

            # Collect multiline sh content
            if inside_sh_block:
                sh_buffer.append(line)
                continue

            # Single line sh
            if current_stage and current_stage.get("inside_steps"):
                single_sh = re.match(r"sh\s+['\"](.+?)['\"]", line)
                cmd = None
                if single_sh:
                    cmd = single_sh.group(1).strip()
                else:
                    cmd = line.strip()

                # ---- FILTER COMMENTS ----
                if cmd and not cmd.startswith(("//", "/*", "*/", "*")):
                    current_stage["steps"].append({"run": cmd})

    return parameters, stages, cron_schedule


def create_composite_action(stage_name, steps, output_dir):
    """Generate composite action for a stage."""
    action_dict = {
        "name": stage_name,
        "description": f"Composite action for {stage_name}",
        "runs": {
            "using": "composite",
            "steps": steps
        }
    }

    stage_dir = os.path.join(output_dir, stage_name.replace(" ", "_").lower())
    os.makedirs(stage_dir, exist_ok=True)
    action_path = os.path.join(stage_dir, "action.yml")

    with open(action_path, "w") as f:
        yaml.dump(action_dict, f, sort_keys=False)


def convert_jenkins_to_github_actions(jenkinsfile_path, output_dir):
    """Main converter function."""
    parameters, stages, cron_schedule = parse_jenkinsfile(jenkinsfile_path)

    composite_action_paths = []
    for stage in stages:
        action_name = stage["name"].replace(" ", "_").lower()
        create_composite_action(stage["name"], stage["steps"], output_dir)
        composite_action_paths.append(f".github/actions/{action_name}")

    workflow_name = os.path.basename(os.path.dirname(jenkinsfile_path)) or "main"

    create_workflow_yaml(
        workflow_name=workflow_name,
        composite_actions=composite_action_paths,
        cron_schedule=cron_schedule,
        parameters=parameters
    )


if __name__ == "__main__":
    jenkinsfile_path = "Jenkinsfile"
    output_dir = ".github/actions"
    convert_jenkins_to_github_actions(jenkinsfile_path, output_dir)
    print(f"[INFO] Conversion complete! Actions written to {output_dir}")





"""
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
        elif inside_parameters:
            if line.startswith("string") or line.startswith("boolean") or line.startswith("choice"):
                try:
                    parts = line.split("(",1)[1].rsplit(")",1)[0]
                    param_dict = {}
                    for kv in parts.split(","):
                        if "=" in kv:
                            k, v = kv.split("=", 1)
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
                if line.startswith("sh "):
                    cmd=line.split("sh", 1)[1].strip(" '\"")
                    current_stage["steps"].append({"run": cmd})
                else:
                    current_stage["steps"].append({"run": line})

    return parameters, stages, cron_schedule

def convert_jenkinsfile_to_github_actions(jenkinsfile_path):
    parameters, stages, cron_schedule = parse_jenkinsfile(jenkinsfile_path)
    shared_libraries = extract_shared_libraries(jenkinsfile_path)

    workflow_name = os.path.basename(os.path.dirname(jenkinsfile_path)) or os.path.splitext(os.path.basename(jenkinsfile_path))[0]
    composite_action_paths = []

    for stage in stages:
        action_name = stage["name"].replace(" ", "_").lower()
        create_composite_action(action_name, stage["steps"])
        composite_action_paths.append(f".github/actions/{action_name}")

    create_workflow_yaml(
        workflow_name=workflow_name,
        composite_actions=composite_action_paths,
        cron_schedule=cron_schedule,
        parameters=parameters
    )
"""
