import os
import argparse

from converter import parse_jenkinsfile
from github_actions_manager import create_github_workflow, create_composite_action


def process_jenkinsfile(jenkinsfile_path):
    print(f"📄 Processing Jenkinsfile: {jenkinsfile_path}")
    parsed_data = parse_jenkinsfile(jenkinsfile_path)
    if not parsed_data:
        print("❌ Failed to parse Jenkinsfile.")
        return

    parameters = parsed_data.get("parameters", [])
    triggers = parsed_data.get("triggers", [])
    stages = parsed_data.get("stages", [])

    cron = None
    if triggers:
        for trigger in triggers:
            if "cron" in trigger:
                cron = trigger.split("cron('")[-1].rstrip("')")

    # Create composite actions for each stage
    for stage in stages:
        stage_name = stage["name"]
        commands = stage.get("steps", [])
        create_composite_action(stage_name, commands)

    # Create main GitHub Actions workflow
    create_github_workflow(
        stages=stages,
        workflow_name="converted_workflow",
        schedule=cron,
        parameters=parameters
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert Jenkinsfile to GitHub Actions")
    parser.add_argument("--dir", required=True, help="Directory containing Jenkinsfile")
    args = parser.parse_args()

    jenkinsfile_path = os.path.join(args.dir, "Jenkinsfile")
    if not os.path.exists(jenkinsfile_path):
        print(f"❌ Jenkinsfile not found at: {jenkinsfile_path}")
    else:
        process_jenkinsfile(jenkinsfile_path)
