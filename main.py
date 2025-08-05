import os
from converter import convert_jenkinsfile_to_stages
from shared_library_handler import extract_shared_libraries
from github_actions_manager import create_github_workflow, create_composite_action


def process_jenkinsfile(jenkinsfile_path):
    with open(jenkinsfile_path, "r") as f:
        jenkinsfile_text = f.read()

    print(f"🔎 Processing {jenkinsfile_path}...")

    # Convert Jenkinsfile text into pipeline metadata
    result = convert_jenkinsfile_to_stages(jenkinsfile_text)

    # Extract shared libraries (even if empty)
    shared_libs = extract_shared_libraries(jenkinsfile_text)
    result['shared_libraries'] = shared_libs
    if shared_libs:
        print(f"📦 Found shared libraries: {shared_libs}")

    stages = result["stages"]
    parameters = result.get("parameters", [])
    schedule = result.get("schedule", None)

    # Generate composite actions for each stage
    for stage in stages:
        create_composite_action(stage["name"], stage["commands"])

    # Create the main GitHub Actions workflow
    workflow_name = os.path.splitext(os.path.basename(jenkinsfile_path))[0]
    create_github_workflow(stages, workflow_name, schedule, parameters)

    print(f"✅ Conversion complete for {jenkinsfile_path}\n")


if __name__ == "__main__":
    # Path to directory containing Jenkinsfiles
    input_dir = "end-to-end-testing"

    # Loop through all Jenkinsfiles in the directory
    for filename in os.listdir(input_dir):
        if filename.startswith("Jenkinsfile"):
            jenkinsfile_path = os.path.join(input_dir, filename)
            process_jenkinsfile(jenkinsfile_path)
