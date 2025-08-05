import yaml
import os

def library_handler(shared_library_directory):
    directory = shared_library_directory
    file_name = "echoMessage.groovy"
    extracted_file_name = file_name.split('.')[0]
    file_path = directory + '/' + file_name

    with open(file_path, 'r') as file:
        lines = file.readlines()

    commands_by_function = {} 
    current_function = None
    function_started = False

    for line in lines:
        line = line.strip()

        if line.startswith('def '):  
            current_function = line.split()[1].split("(")[0]  
            function_started = True
            commands_by_function[current_function] = [] 
            continue  

        if line == "}":  
            function_started = False
            current_function = None
            continue  

        if function_started and current_function:
            if line.startswith("echo"):
                commands_by_function[current_function].append(line)

    yaml_data = []
    for function, commands in commands_by_function.items():
        yaml_data.append({
            "name": function,
            "run": "\n".join(commands)
        })

    yaml_output = yaml.dump(yaml_data, default_flow_style=False)
    print(yaml_output)

    output_file_name = directory + '/' + extracted_file_name + '.yaml'
    with open(output_file_name, "w") as yaml_file:
        yaml.dump(yaml_data, yaml_file, default_flow_style=False)


    
    return file_name.split('.')[0]

def library_snippet_generator(library_name, function_name):
   
    filename = library_name + ".yaml"
    directory = "Jenkins_files/vars"
    file_path = os.path.join(directory, filename)
    function_name = function_name.split('(')[0]
    # Check if the file exists.
    if not os.path.exists(file_path):
        print(f"File {file_path} not found.")
        return None

    # Load the YAML content from the file.
    with open(file_path, "r") as file:
        try:
            data = yaml.safe_load(file)
        except yaml.YAMLError as e:
            print(f"Error reading YAML file: {e}")
            return None

    # Ensure data is a list of blocks.
    if not isinstance(data, list):
        print("Unexpected YAML format: expected a list of blocks.")
        return None

    # Retrieve the block where the 'name' key matches the function_name.
    snippet = next((block for block in data if block.get("name") == function_name), None)
    
    if snippet is None:
        print(f"Function '{function_name}' not found in {file_path}")
        return None

    return snippet

def extract_shared_libraries(jenkinsfile_text):
    shared_libs=[]
    if "@Library" in jenkinsfile_text:
        shared_libs.append("example-shared-library")
    return shared_libs
