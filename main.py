import os
from converter import convert_jenkinsfile_to_github_actions

def find_jenkinsfiles(root_dir="."):
    jenkinsfiles = []
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file == "Jenkinsfile":
                jenkinsfiles.append(os.path.join(root, file))
    return jenkinsfiles

if __name__ == "__main__":
    jenkinsfiles = find_jenkinsfiles()
    if not jenkinsfiles:
        print("[INFO] No Jenkinsfiles found.")
    for jenkinsfile_path in jenkinsfiles:
        print(f"\n[INFO] Converting {jenkinsfile_path}...")
        convert_jenkinsfile_to_github_actions(jenkinsfile_path)
