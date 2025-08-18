import os
import argparse
import sys
from converter import convert_jenkins_to_github_actions

def find_jenkinsfiles(root_dir="."):
    jenkinsfiles = []
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file == "Jenkinsfile":
                jenkinsfiles.append(os.path.join(root, file))
    return jenkinsfiles

if __name__ == "__main__":
    parser=argparse.ArgumentParser(description="Convert Jenkinsfiles to Github Actions workflows")
    parser.add_argument("--dir",type=str,required=True,help="Root Direcctory to search for Jenkinsfiles ")
    args=parser.parse_args()


    root_dir = args.dir
    jenkinsfiles = find_jenkinsfiles(root_dir)

    if not jenkinsfiles:
        print("[INFO] No Jenkinsfiles found.")
    else:
        for jenkinsfile_path in jenkinsfiles:
            print(f"\n[INFO] Converting {jenkinsfile_path}...")
            convert_jenkins_to_github_actions(
                jenkinsfile_path, os.path.join(root_dir, ".github", "workflows")
            )
