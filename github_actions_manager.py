import os
import yaml

def create_composite_action(action_name, steps, output_dir=".github/actions"):
    """
    Creates a composite GitHub Action with the given steps.
    Saves it under .github/actions/{action_name}/action.yml.
    """
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

def create_workflow_yaml(workflow_name, on_event, jobs, output_dir=".github/workflows"):
    """
    Creates a workflow YAML file that uses the generated composite actions.
    Saves it under .github/workflows/{workflow_name}.yml.
    """
    os.makedirs(output_dir, exist_ok=True)

    workflow_content = {
        "name": workflow_name,
        "on": on_event,
        "jobs": jobs
    }

    workflow_path = os.path.join(output_dir, f"{workflow_name}.yml")
    with open(workflow_path, "w") as f:
        yaml.dump(workflow_content, f, default_flow_style=False)
    print(f"[INFO] Created workflow file: {workflow_path}")
