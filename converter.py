import os
import re
from github_actions_manager import create_composite_action, create_workflow_yaml
from shared_library_handler import extract_shared_libraries

# Util to extract stages and their shell commands from a Jenkinsfile
def parse_jenkinsfile(jenkinsfile_path):
    with open(jenkinsfile_path, 'r') as file:
        content = file.read()
        
    shared_libraries = extract_shared_libraries(content)
    if shared_libraries:
        print(f"Detected Shared Libraries: {shared_libraries}")

    stages = re.findall(r'stage\(["\'](.*?)["\']\)\s*\{(.*?)\}', content, re.DOTALL)
    steps_dict = {}
    for stage_name, stage_block in stages:
        steps = re.findall(r'sh\s+["\']{3}(.*?)["\']{3}|sh\s+["\'](.*?)["\']', stage_block, re.DOTALL)
        commands = []
        for triple_cmd, single_cmd in steps:
            cmd = triple_cmd or single_cmd
            if cmd:
                commands.extend([line.strip() for line in cmd.strip().split('\n') if line.strip()])
        steps_dict[stage_name.strip()] = commands
    return steps_dict

# Extract cron triggers from Jenkinsfile
def extract_cron_trigger(jenkinsfile_path):
    with open(jenkinsfile_path, 'r') as file:
        content = file.read()
    match = re.search(r'cron\(["\'](.*?)["\']\)', content)
    return match.group(1) if match else None

# Extract parameter inputs
def extract_parameters(jenkinsfile_path):
    with open(jenkinsfile_path, 'r') as file:
        content = file.read()
    parameters = []
    choice_matches = re.findall(r'choice\(.*?name:\s*["\'](.*?)["\'].*?choices:\s*\[(.*?)\]', content, re.DOTALL)
    for name, choices_str in choice_matches:
        choices = [c.strip(" '") for c in choices_str.strip().split(',') if c.strip()]
        parameters.append({"name": name, "choices": choices})
    return parameters

def convert_jenkinsfile_to_github_actions(jenkinsfile_path):
    print(f"Converting {jenkinsfile_path}...")
    
    stages = parse_jenkinsfile(jenkinsfile_path)
    cron_schedule = extract_cron_trigger(jenkinsfile_path)
    parameters = extract_parameters(jenkinsfile_path)

    workflow_name = os.path.basename(os.path.dirname(jenkinsfile_path)) or "jenkins"
    job_id = workflow_name.replace('-', '_')

    composite_action_paths = {}
    for stage, commands in stages.items():
        action_dir = f".github/actions/{stage.lower().replace(' ', '-')}/"
        os.makedirs(action_dir, exist_ok=True)
        create_composite_action(stage, commands, action_dir)
        composite_action_paths[stage] = action_dir

    create_workflow_yaml(workflow_name, composite_action_paths, cron_schedule, parameters)
    print(f"✅ Successfully converted {jenkinsfile_path} to GitHub Actions.")
