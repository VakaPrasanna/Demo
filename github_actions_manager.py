import os
import yaml

def create_composite_action(action_name, steps, output_dir=".github/actions"):
    action_dir = os.path.join(output_dir, action_name)
    os.makedirs(action_dir, exist_ok=True)

    action_content = {
        "name": action_name,
        "description": f"Composite action for {action_name}",
        "runs": {
            "using": "composite",
            "steps": steps
        }
    }

    action_path = os.path.join(action_dir, "action.yml")
    with open(action_path, "w") as f:
        yaml.dump(action_content, f, default_flow_style=False)

    print(f"[INFO] Created composite action: {action_path}")

def create_workflow_yaml(workflow_name, composite_actions, cron_schedule=None, parameters=None, output_dir=".github/workflows"):
    os.makedirs(output_dir, exist_ok=True)

    on_event = {"push": {"branches": ["main"]}}
    if cron_schedule:
        on_event["schedule"] = [{"cron": cron_schedule}]

    jobs = {
        "build": {
            "runs-on": "ubuntu-latest",
            "steps": []
        }
    }

    for action in composite_actions:
        jobs["build"]["steps"].append({
            "uses": f"./.github/actions/{action}"
        })

    if parameters:
        jobs["build"]["steps"].insert(0, {
            "name": "Set Parameters",
            "run": "\n".join([f"echo {param.get('name', 'UNKNOWN')}=${{{{ github.event.inputs.{param.get('name', 'UNKNOWN')} }}}}" for param in parameters if 'name' in param])
        })

    workflow_content = {
        "name": workflow_name,
        "on": on_event,
        "jobs": jobs
    }

    workflow_path = os.path.join(output_dir, f"{workflow_name}.yml")
    with open(workflow_path, "w") as f:
        yaml.dump(workflow_content, f, sort_keys=False)

    print(f"[INFO] Created workflow file: {workflow_path}")
