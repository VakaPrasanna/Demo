import re
import yaml
from github_actions_manager import GithubActionsManager
import shared_library_handler



#Sushobhan's code------------------------------------------------------------------------------------------------------

def clean_invisible_chars(text):
    # Replace non-breaking spaces and other invisible characters with normal spaces
    return text.replace('\u200b', '').replace('\xa0', ' ').replace('\u200a', ' ').replace('\u2009', ' ').replace('\u202f', ' ')

def extract_block(text, word):
    text = clean_invisible_chars(text)
    start_match = re.search(r'script\s*\{', text)
    if word=='steps':
        start_match = re.search(r'steps\s*\{', text)
    if not start_match:
        return None

    start_index = start_match.end() 
    brace_count = 1
    current_index = start_index
    extracted_content = []
    text_length = len(text)

    while current_index < text_length and brace_count > 0:
        char = text[current_index]
        
        if char == '{':
            brace_count += 1
        elif char == '}':
            brace_count -= 1

        if brace_count > 0:
            extracted_content.append(char)
        
        current_index += 1

    return ''.join(extracted_content).strip('\n')

def convert_script_to_shell_lines(jenkins_script):
    """
    Converts Jenkins scripted pipeline content (Groovy script block)
    into equivalent shell commands for GitHub Actions.
    """
    shell_lines = ["#!/bin/bash"]
    indent_stack = []
    
    lines = jenkins_script.strip().split('\n')

    for raw_line in lines:
        line = raw_line.strip()

        if not line:
            shell_lines.append('')
            continue

        if line.startswith("echo "):
            message = line[5:].strip()
            shell_lines.append(f"echo {message}")
        
        # Handle Groovy variable assignment (def var = 'value')
        elif re.match(r"def\s+\w+\s*=\s*'.*'", line):
            match = re.match(r"def\s+(\w+)\s*=\s*'(.*)'", line)
            if match:
                var_name, var_value = match.groups()
                shell_lines.append(f"{var_name}=\"{var_value}\"")
        
        # Handle Groovy variable assignment (def var = value without quotes)
        elif re.match(r"def\s+\w+\s*=\s*.*", line):
            match = re.match(r"def\s+(\w+)\s*=\s*(.*)", line)
            if match:
                var_name, var_value = match.groups()
                shell_lines.append(f"{var_name}={var_value}")

        # Handle shell script (sh 'command')
        elif re.match(r"sh\s+['\"](.*)['\"]", line):
            match = re.match(r"sh\s+['\"](.*)['\"]", line)
            if match:
                command = match.group(1)
                shell_lines.append(command)

        # Handle if condition (simple boolean)
        elif re.match(r"if\s*\(.*\)\s*\{?", line):
            condition = re.findall(r"if\s*\((.*)\)", line)
            if condition:
                shell_lines.append(f"if {condition[0]}; then")
                indent_stack.append('if')

        # Handle else
        elif re.match(r"else\s*\{?", line):
            shell_lines.append("else")

        # Handle for loop (Groovy: for (item in items))
        elif re.match(r"for\s*\(.* in .*\)\s*\{?", line):
            loop_match = re.findall(r"for\s*\(\s*(\w+)\s+in\s+(.*)\)", line)
            if loop_match:
                var_name, collection = loop_match[0]
                shell_lines.append(f"for {var_name} in {collection}; do")
                indent_stack.append('for')

        # Handle closing braces
        elif line == "}":
            if indent_stack:
                last_control = indent_stack.pop()
                if last_control == 'if':
                    shell_lines.append("fi")
                elif last_control == 'for':
                    shell_lines.append("done")

        # Default: treat as shell command (best effort)
        #else:
        #    shell_lines.append(line)
    return "; ".join(shell_lines)


#------------------------------------------------------------------------------------------------------


def handle_git_stage(stage, parameters):
    print("Handling Git stage:")
    splitted = stage["content"].lstrip().split(" ")
    main_content = [
        i for i in splitted if i not in ["steps", "{\n", "}\n", ""]
    ]
    dic = {}
    # print(main_content)
    for i in main_content:
        if i in ['git']:
            dic['name'] = "git"
        elif i == 'branch:':
            
            if "${" in main_content[main_content.index(i)+1]:
                branch = re.search(r"\$\{params\.branch\}", main_content[main_content.index(i)+1]).group(0)
                dic['branch'] = branch
            else:
                dic['branch'] = main_content[main_content.index(i)+1]
        elif i == 'url:' :
            if "${" in main_content[main_content.index(i)+1]:
                url = re.search(r"\$\{params\.sourceCode_url\}", main_content[main_content.index(i)+1]).group(0)
                dic['url'] = url
            else:
                dic['url'] = main_content[main_content.index(i)+1]
            
        elif i == 'credentialsId:' :
            if "${" in main_content[main_content.index(i)+1]:
                token = re.search(r"\$\{params\.credentialsId\}", main_content[main_content.index(i)+1]).group(0)
                dic['token'] = token
            else:
                dic['token'] = main_content[main_content.index(i)+1]

    for key, value in dic.items():
        if 'params.' in str(value):  # Check if the value references a param
            param_name = value.split('params.')[1].strip('${}').strip()  # Extract param name
            # Find the corresponding parameter in 'parameters'
            matching_param = next((param for param in parameters if param['name'] == param_name), None)
            if matching_param and 'defaultValue' in matching_param:  # Check if defaultValue exists
                dic[key] = matching_param['defaultValue']  # Replace value in dic
   
    print(dic)
    url1 = dic['url']
    match = re.search(r"github\.com/(.*?)(\.git)?$", url1)
    if 'token' not in dic.keys():
        dic['token'] = None
    #import pdb; pdb.set_trace()
    if match:
        extracted_part = match.group(1)
        dic['url'] = extracted_part

    return {
        "name": "Checkout code",
        "uses": "actions/checkout@v2",
        "with": {
            "repository": "DaggupatiPavan/java-web-app-docker",
            #"token": f"${{ secrets.{dic['token']} }}",
            #"ref": dic["branch"],
        },
    }

from yaml.representer import Representer

# Define a custom representer for multiline strings
def literal_representer(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')

def handle_build_stage(stage):
    print("Handling Build stage:") 
    stage_name = stage.get('stage_name', 'Unnamed Stage')
    content = stage.get('content', '')
    print(stage["content"])
    commands = ["#!/bin/bash"]
    maven_content = None
    for line in content.split('\n'):
        line = line.strip()
        match = re.match(r"sh '(.*)'", line) or re.match(r'sh "(.*)"', line)
        if line.startswith("withMaven("):
            maven_content = {"name": "setup JDK for Maven","uses": "actions/setup-java@v3","with":{"java-version": 11, "distribution": "adopt"}}
        if match:
            commands.append(match.group(1))

    
    #yaml.add_representer(str, literal_representer)
    yaml_content = {
    "name": "Build and Deploy",
    "run":  "; ".join(commands) 
    }
    print(yaml_content)

    yaml_str = yaml.dump([yaml_content], default_flow_style=False, sort_keys=False)

    # Print the generated YAML for validation
    print(yaml_str)
    #yaml.representer.SafeRepresenter.add_representer(str, yaml.representer.SafeRepresenter.represent_str)

    #import pdb;pdb.set_trace()
    maven_cmd_content = {
        'name': stage["stage_name"],
        'run':  "; ".join(commands)
    }

    if type(maven_content)==dict and type(maven_cmd_content)==dict:
        return maven_content,maven_cmd_content
    else:
        return maven_cmd_content


def handle_sonarqube_stage(stage):
    #import pdb;pdb.set_trace()
    print("Handling SonarQube stage:")  
    print(stage["content"])

    content = stage.get('content', '')

    commands = ["#!/bin/bash"]
    for line in content.split('\n'):
        line = line.strip()
        match = re.match(r"sh '(.*)'", line) or re.match(r'sh "(.*)"', line)
        if line.startswith("withSonar"):
            sonar_content = {"name": "Set up SonarQube environment", "uses": "sonarsource/sonarqube-scan-action@v1.0","with": {"sonarQubeEnv": {"credentialsId": "sonarQube","installationName": "QualityChecks"}}}

        if match:
            commands.append(match.group(1))

    sonar_cmd_content =  {
            'name': stage["stage_name"],
            'run': "; ".join(commands)
            }
    if sonar_content and sonar_cmd_content:
        return sonar_content,sonar_cmd_content



def handle_docker_stage(stage):
    print("Handling Docker stage:")
    print(stage["content"]) 
    
    content = stage.get('content', '')
    commands = ["#!/bin/bash"]
    #import pdb;pdb.set_trace()

    for line in content.split('\n'):
        line = line.strip()
        match = re.match(r"sh '(.*)'", line) or re.match(r'sh "(.*)"', line)
        if match:
            commands.append(match.group(1))
    

    return {
            'name': stage["stage_name"],
            'run': "; ".join(commands)
            }

    
def handle_kubernetes_stage(stage):

    def handle_kubernetes_plugin(content):
        #import pdb;pdb.set_trace()
        for line in content.split('\n'):
            line = line.strip()
            configs = re.match(r"configs: '(.*)'", line)
            if configs:
                config = configs.group(1)

        kubernetes_content = {"name": "Deploy To Kubernetes","uses": "azure/k8s-deploy@v4","with": {"namespace": "default","manifests": config},"env": {"KUBECONFIG": "${{ secrets.KUBECONFIG}}"}}

        return kubernetes_content

    print("Handling Kubernetes stage : ")
    print(stage["content"])

    content = stage.get('content', '')

    # Extract the command from the content, handling 'script' blocks as well
    commands = ["#!/bin/bash"]

    for line in content.split('\n'):
        line = line.strip()
        match = re.match(r"sh '(.*)'", line) or re.match(r'sh "(.*)"', line)
        if match:
            commands.append(match.group(1))
        elif "kubernetesDeploy(" in line:
            k8s_content = handle_kubernetes_plugin(content)
            
            return k8s_content
    

    return {
            'name': stage["stage_name"],
            'run': "; ".join(commands)
            }

# srinija's cod
allBranches = ["main"]
def  handle_when_stages(stage):
    print("Handling when stage:")
    print("In when handler....",stage["content"]) 
    
    content = stage.get('content', '')
    if "sh " in content:
        commands = ["#!/bin/bash"]
    else:
        commands = []
    branch_match=""
    branch_cond=""
    val=""
    for line in content.split('\n'):
        line = line.strip()
        branch_match=re.findall(r"branch\s*'([^']+)'",line)
        if branch_match:
            val=branch_match[0]
            # print("searched branch value...",branch_match[0])
        match = re.match(r"sh '(.*)'", line) or re.match(r'sh "(.*)"', line)
        match_echo=re.match(r'echo "(.*)"', line)
        if match_echo:
            commands.append(f'echo "{match_echo.group(1)}"')
        if match:
            commands.append(match.group(1))

    if "not {" in content and val:
        branch_cond=f"github.ref != 'refs/heads/{val}'"
        allBranches.append("!"+val)

    elif val:
        branch_cond=f"github.ref == 'refs/heads/{val}'"
        allBranches.append(val)

    else:
        branch_cond=""
    print("val value branch- ", val)
    print(allBranches)
    return {
            'if': branch_cond,
            'name': stage["stage_name"],
            'run': "; ".join(commands)
            }

#New Function
def implement_triggers(file_path):
    # triggers=[]
    cron=""
    with open(file_path, "r") as file:
        inside_triggers = False
        for line in file:
            if "triggers {" in line:
                inside_triggers=True
            elif inside_triggers and "}" in line:
                inside_triggers=False
            elif inside_triggers:
                trigger_line=line.strip()
                # print("Trigger Line",trigger_line)
                if trigger_line.startswith("cron("):
                    cron=trigger_line.split("cron('")[1].split("'")[0]
                    # cron.replace('H','*')
                # triggers.append(cron)
    return cron.strip() 
    # return ("".join(triggers))


def handle_sh_stages(stage):
    print("Handling sh stage")
    print(stage["content"])

    content = stage.get('content', '')
    commands = ["#!/bin/bash"]

    # Extract multi-line and single-line sh commands
    sh_matches = re.findall(r"sh\s+['\"]{3}([\s\S]*?)['\"]{3}|sh\s+['\"](.*?)['\"]", content)

    for match in sh_matches:
        multi_line, single_line = match
        command = multi_line if multi_line else single_line
        if command:
            commands.append(command.strip())

    return {
        'name': stage["stage_name"],
        'run': "; ".join(commands)
    }

def handle_artifacts(stage):
    print("Handling artifacts")
    content = stage.get('content','')
    print(type(content))
    match = re.findall(r"archiveArtifacts\s+artifacts:\s*'.*'",content.replace('"',"'"))[0]
    fileName = re.findall("'.*'",match)[0][1:-1]
    return {
        'name': 'Upload artifact',
        'uses': 'actions/upload-artifact@v4',
        'with':{
            'name': 'my_artifact',
            'path': fileName
        }
    }


def extract_parameters(file_path):
    parameters = []
    with open(file_path, "r") as file:
        inside_parameters_block = False
        for line in file:
            if "parameters {" in line:
                inside_parameters_block = True
            elif inside_parameters_block and "}" in line:
                inside_parameters_block = False
            elif inside_parameters_block:
                param_line = line.strip().replace('"',"'")
                param_dict = {}
                if param_line.startswith("string("):
                    param_dict["type"] = "string"
                elif param_line.startswith("choice("):
                    param_dict["type"] = "choice"
                elif param_line.startswith("text("):
                    param_dict["type"] = "text"
                elif param_line.startswith("boolean"):
                    param_dict["type"] = "boolean"
                elif param_line.startswith("password"):
                    param_dict["type"] = "password"
                name = re.findall(r"name:\s*'([^']+)',\s",param_line)
                if name:
                    param_dict["name"] = name[0]
            
                description = re.findall(r"description:\s*'([^']+)'\s*",param_line)
                if description:
                    param_dict["description"] = description[0]
                if "defaultValue" in param_line:
                    defaultValue = re.findall(r"defaultValue:\s*(?:'([^']*)'|(\btrue\b|\bfalse\b))?\s*",param_line)
                    dVal = list(defaultValue[0])
                    if len(dVal[0]) or len(dVal[1]) > 2:        
                        if dVal[0]:
                            param_dict["defaultValue"] = dVal[0]
                        else:
                            if dVal[1] == 'true':
                                param_dict["defaultValue"] = True
                            else:
                                param_dict["defaultValue"] = False                   
                        # param_dict["defaultValue"] = dVal[0] if dVal[0] else dVal[1]
                if param_dict.get("type") == "choice":
                    choices = re.findall(r"choices:\s*\[(.*?)\]\s*",param_line)
                    if choices:
                        choices_ste = choices[0]
                        choices = [choice.strip().strip("'\"") for choice in choices_ste.split(',')]
                        param_dict["choices"] = choices

                if param_dict:
                    parameters.append(param_dict)
    print(parameters)
    return parameters if len(parameters)<10 else parameters[:10]


def implementing_shared_libraries(shared_library_directory):
    print("The pipeline has shared libraries")
    slf = shared_library_handler.library_handler(shared_library_directory)
    return slf

def handle_parameters(parameters):
    res = {"inputs":{}}
    for para in parameters:
        current = {
            "description":para.get("description"),
            
            # "default": para.get("defaultValue") if para["defaultValue"] else "",
            # "choices":para["choices"] if para["choices"] else ""
        }
        print(para["name"])
        if para.get("type") != "string":
            current["type"] = para.get("type")
        if para.get("defaultValue"):
            current["default"] = para.get("defaultValue")
        if para.get("choices"):
            current["options"]= para.get("choices")
        res["inputs"][para["name"]] = current
    print(res)
    return res

"""
if __name__ == "__main__":
"""

def parse_jenkinsfile(file,shared_library_directory):
    #with open("./Jenkinsfile_complex.groovy", "r") as file:
    file_name = file
    
    with open(file,"r") as file:
        stage_list = []
        current_stage = {}
        current_content = []
        in_stage = False
        shared_library_files = []

        for line in file:
            stripped_line = line.lstrip()

            if stripped_line.startswith("@Library"):
                slr = implementing_shared_libraries(shared_library_directory)
                shared_library_files.append(slr)

            if stripped_line.lower().startswith("stage("):
                if in_stage:
                    steps_block = []
                    inside_steps = False
                    inside_when1 = False

                    for content_line in current_content:
                        content_stripped = content_line.lstrip()
                        if content_stripped.startswith("when {"):
                            inside_when1 = True
                        if inside_when1:
                            steps_block.append(content_line)
                        if inside_when1 and content_stripped.startswith("}"):
                            inside_when1 = False

                        if content_stripped.startswith("steps {"):
                            inside_steps = True
                        if inside_steps:
                            steps_block.append(content_line)
                        if inside_steps and content_stripped.startswith("}"):
                            inside_steps = False

                    current_stage["content"] = "".join(steps_block)
                    stage_list.append(current_stage)
                    current_content = []

                stage_name = stripped_line.split("(")[1].split(")")[0].strip("'\"")
                current_stage = {"stage_name": stage_name}
                in_stage = True

            if in_stage:
                current_content.append(line)

        if in_stage and current_stage:
            steps_block = []
            inside_steps = False
            inside_when=False

            for content_line in current_content:
                content_stripped = content_line.lstrip()
                if content_stripped.startswith("when {"):
                    inside_when = True
                if inside_when:
                    steps_block.append(content_line)
                if inside_when and content_stripped.startswith("}"):
                    inside_when = False

                if content_stripped.startswith("steps {"):
                    inside_steps = True
                if inside_steps:
                    steps_block.append(content_line)
                if inside_steps and content_stripped.startswith("}"):
                    inside_steps = False

            current_stage["content"] = "".join(steps_block)
            stage_list.append(current_stage)

    parameters = extract_parameters(file_name)
    parametersL =""
    if parameters:
        parametersL = handle_parameters(parameters)
    triggers = implement_triggers(file_name)

    manager = GithubActionsManager(allBranches,parametersL,triggers,file_name)
    # print(stage_list)
    for stage in stage_list:
        print(stage_list)
        stage_name = stage["stage_name"].lower()
        if any(item in stage['content'] for item in shared_library_files):
            content = stage['content'].strip()
            match = re.search(r'script\s*\{(.*?)\}', content, re.DOTALL)
            if match:
                script_content = match.group(1).strip()
                print("Script content:", script_content)
            else:
                print("No script block found")
            #import pdb;pdb.set_trace()
            library_name = script_content.split('.')[0]
            function_name = script_content.split('.')[-1]
            shared_library_content = shared_library_handler.library_snippet_generator(library_name,function_name)
            manager.append_to_file(shared_library_content)
            


        elif "mvn" in stage["content"]:
            if "mvn" in stage["content"] and "withSonarQubeEnv" in stage["content"]:
                all_sonar_contents = []
                sonar_content, sonar_cmd_content = handle_sonarqube_stage(stage)
                all_sonar_contents.append(sonar_content)
                all_sonar_contents.append(sonar_cmd_content)
                for content in all_sonar_contents:
                    manager.append_to_file(content)
            else:
                #import pdb;pdb.set_trace()
                all_maven_contents = []
                maven = handle_build_stage(stage)
                if type(maven)==tuple:
                    for content in  maven:
                        all_maven_contents.append(content)
                elif type(maven)==dict:
                    all_maven_contents.append(maven)
                for content in all_maven_contents:                   
                    manager.append_to_file(content)      

        elif "docker build " in stage["content"] or ">> Dockerfile" in stage["content"] :
            docker_step = handle_docker_stage(stage)
            manager.append_to_file(docker_step)
        
        elif "docker push " in stage["content"] :
            docker_step = handle_docker_stage(stage)
            docker_login_content = {
            "name": "Log in to Docker Hub",
            "uses": "docker/login-action@v2",
            "with": {
            "username": "${{ secrets.DOCKER_USERNAME }}",
            "password": "${{ secrets.DOCKER_PASSWORD }}"
            }
            }
            manager.append_to_file(docker_login_content)
            manager.append_to_file(docker_step)

        elif ('Approval' or 'approval') in stage["stage_name"]:
            dict_content = {
                'runs-on': 'ubuntu-latest',
                'needs': 'build',
                'environment': 'production',  # This forces the job to wait for approval
                'steps': [
                    {
                        'name': 'Await Manual Approval',
                        'run': 'echo "Approval required. Approve this job to continue."'
                    }
                ]
            }
            manager.append_to_job('approval', dict_content)

        elif 'Deploy with Approval' == stage["stage_name"]:
            dict_content = {
                    'runs-on': 'ubuntu-latest',
                    'needs': 'approval',
                    #'if': '${{ github.event.inputs.APPROVAL_CHOICE == "yes" }}',
                    'steps': [
                        {
                            'name': 'Checkout Repository',
                            'uses': 'actions/checkout@v4'
                        }
                    ]
            }
            step_content = extract_block( stage["content"], "steps")
            script = convert_script_to_shell_lines(step_content)
            new_dict = {
                    'name': stage["stage_name"],
                    'run': script
                }
            dict_content["steps"].append(new_dict)
            manager.append_to_job('deploy', dict_content)
        
        elif "sshagent" in stage["content"]:
            dict_content = {
                    'name': "Set up SSH",
                    'uses': "webfactory/ssh-agent@v0.5.3",
                    'with': {
                        'ssh-private-key': '${{ secrets.SSH_PRIVATE_KEY }}'
                    }
                }
            manager.append_to_file(dict_content)
            if re.search(r'script\s*\{', stage["content"]):
                script_content = extract_block( stage["content"], "script")
                script = convert_script_to_shell_lines(script_content)
                dict_content = {
                    'name': stage["stage_name"],
                    'run': script
                }
                manager.append_to_file(dict_content)
        
        elif "when " in stage["content"]:
            when_step = handle_when_stages(stage)
            # print("when_step....",when_step)
            when_step["branchesAll"] = allBranches
            manager.append_to_file(when_step)  
        
        elif  "kubernetesDeploy(" in stage["content"]:
            kube_step = handle_kubernetes_stage(stage)
            manager.append_to_file(kube_step)
        elif "archiveArtifacts" in stage['content']:
            print("got it artifact")          
            artifact = handle_artifacts(stage)
            manager.append_to_file(artifact)
        elif " sh " in stage["content"]:
            #import pdb;pdb.set_trace()
            shell = handle_sh_stages(stage)
            manager.append_to_file(shell)
        elif "git" in stage["content"]:
            
            git_step = handle_git_stage(stage, parameters)
            manager.append_to_file(git_step)
        else:
            print(f"No specific handler for stage: {stage['stage_name']}\n")



    
