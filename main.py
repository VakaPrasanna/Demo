import os
from converter import convert_jenkinsfile_to_github_actions

if __name__ == "__main__":
    input_dir = "end-to-end-testing"

    # Loop through all Jenkinsfiles in the directory
    for filename in os.listdir(input_dir):
        if filename.startswith("Jenkinsfile"):
            jenkinsfile_path = os.path.join(input_dir, filename)
            convert_jenkinsfile_to_github_actions(jenkinsfile_path)
