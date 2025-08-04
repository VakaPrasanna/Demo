import argparse
from pathlib import Path
import converter


def find_jenkinsfiles(directory):
    """Recursively search for Jenkinsfile in the given directory"""
    jenkinsfiles = list(Path(directory).rglob("Jenkinsfile*"))  # Finds all Jenkinsfile variants
    return jenkinsfiles

if __name__ == "__main__":
    # Setup argument parser
    parser = argparse.ArgumentParser(description="Search for Jenkinsfiles in a directory.")
    parser.add_argument("--dir", required=True, help="Directory to search for Jenkinsfiles")
    
    args = parser.parse_args()
    search_directory = args.dir
    shared_library_directory = args.dir+'/vars'

    # Find Jenkinsfiles
    jenkinsfiles = find_jenkinsfiles(search_directory)

    if jenkinsfiles:
        for jenkinsfile in jenkinsfiles:
            print(f"Found: {jenkinsfile}")
            filename = str(jenkinsfile)
            converter.parse_jenkinsfile(filename,shared_library_directory)
    else:
        print("No Jenkinsfile found.")
