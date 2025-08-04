import yaml

class NoQuoteDumper(yaml.Dumper):
    def increase_indent(self, flow=False, indentless=False):
        return super(NoQuoteDumper, self).increase_indent(flow, indentless)

class GithubActionsManager:
    def __init__(self, result_dict,parameters,triggers,file):
        """
        Initialize the github_actions.yml file with the given base structure.
        """
        #self.file_path = ".github/workflows/github_actions.yml"
        self.file_path = str(file)+'.yaml'
        print(file)
        triggers=triggers+' '
        print(type(triggers))
        # print(len(triggers))
        triggers=f"'{triggers}'"
        print("Cron value",triggers)
        triggers=triggers[1:-1]


        self.base_structure = {
            "name": "CI/CD Pipeline",
            "on": {
                # "push": {
                #     "branches": [result_dict["branch"]]
                # }
            },
            "jobs": {}
        }
        if parameters:
            self.base_structure["on"]["workflow_dispatch"] = parameters

        else:
            print("from githubactionmanger ",result_dict)
            self.base_structure["on"]["push"] = {"branches":"main"}
        if len(triggers)>2:
            self.base_structure["on"]["schedule"] = [{"cron": triggers}]
        # Write the base structure to the file
        self._write_to_file(self.base_structure)


    def _write_to_file(self, content):
        """
        Write the YAML content to the github_actions.yml file.
        """
        with open(self.file_path, "w") as file:
            yaml.safe_dump(content, file, default_style=None, sort_keys=False, default_flow_style=False)

    def _read_from_file(self):
        """
        Read the current YAML content from the file.
        """
        with open(self.file_path, "r") as file:
            return yaml.safe_load(file)

    def append_to_file(self, step_content):
        """
        Append a new step to the build job in the github_actions.yml file.
        """
        #import pdb;pdb.set_trace()
        current_content = self._read_from_file()
        camel_case = lambda s: ''.join(word.capitalize() if i else word.lower() for i,word in enumerate(s.split()))
        name = camel_case(step_content["name"])
           
   
        if step_content.get('if'):
                    arllist= step_content.get("branchesAll")[1:]
                    arllist.append("main")
                    current_content["on"]["push"] = "hellp"
                    current_content["on"]["push"] = {"branches":arllist} 
                    val_if = step_content['if']
                    step_content.pop('if')
                    step_content.pop('branchesAll')
                    current_content["jobs"][step_content["name"]]={'if':val_if,"runs-on": "ubuntu-latest","steps":[step_content]}
        else:
            current_content["jobs"][name] = {'runs-on': 'ubntu-latest',
            "steps":[
                step_content,
                ]}
        self._write_to_file(current_content)

    def append_to_job(self, key, content):
        """
        Append a new job to the github_actions.yml file.
        """
        current_content = self._read_from_file()
        current_content["jobs"][key] = content
        self._write_to_file(current_content)
