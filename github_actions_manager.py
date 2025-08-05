import os
import yaml

def create_github_workflow(stages, workflow_name="converted_workflow", schedule=None, parameters=None, shared_libraries=None):
    workflow = {
        "name": workflow_name,
        "on": {},
        "jobs": {
            "run-pipeline": {
                "runs-on": "ubuntu-latest",
                "steps": []
            }
        }
    }

    if schedule:
        workflow["on"]["schedule"] = [{"cron": schedule}]
    else:
        workflow["on"]["workflow_dispatch"] = {}

    if parameters:
        workflow["on"]["workflow_dispatch"] = {
            "inputs": {
                param["name"]: {
                    "description": param["description"],
                    "required": True,
                    "default": param["default"]
                }
                for param in parameters
            }
        }

    if shared_libraries:
        for lib in shared_libraries:
            workflow["jobs"]["run-pipeline"]["steps"].append({
                "name": f"Checkout shared library {lib}",
                "uses": "actions/checkout@v4",
                "with": {
                    "repository": lib,
                    "path": f"shared-libs/{lib.split('/')[-1]}"
                }
            })

    for stage in stages:
        action_name = stage["name"].replace(" ", "_").lower()
        action_path = f"./actions/{action_name}"
        workflow["jobs"]["run-pipeline"]["steps"].append({
            "name": f"Run {stage['name']}",
            "uses": f"{action_path}",
            "with": {
                "env": "${{ github.event.inputs.DEPLOY_ENV || 'dev' }}" if parameters else ""
            }
        })

    os.makedirs(".github/workflows", exist_ok=True)
    with open(f".github/workflows/{workflow_name}.yml", "w") as f:
        yaml.dump(workflow, f, default_flow_style=False)

    print(f"Workflow created at .github/workflows/{workflow_name}.yml")


def create_composite_action(stage_name, commands):
    action_dir = f"actions/{stage_name.replace(' ', '_').lower()}"
    os.makedirs(action_dir, exist_ok=True)

    action_yml = {
        "name": stage_name,
        "description": f"Composite action for stage {stage_name}",
        "inputs": {
            "env": {
                "description": "Deployment environment",
                "required": False,
                "default": "dev"
            }
        },
        "runs": {
            "using": "composite",
            "steps": []
        }
    }

    for command in commands:
        action_yml["runs"]["steps"].append({
            "name": f"Run command",
            "shell": "bash",
            "run": command
        })

    with open(os.path.join(action_dir, "action.yml"), "w") as f:
        yaml.dump(action_yml, f, default_flow_style=False)

    print(f"Composite action created at {action_dir}/action.yml")
