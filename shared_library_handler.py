def extract_shared_libraries(jenkinsfile_path):
    shared_libs = []
    with open(jenkinsfile_path, "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("@Library"):
                lib_name = line.split("@Library('")[1].split("')")[0]
                shared_libs.append(lib_name)
    if shared_libs:
        print(f"[INFO] Found shared libraries: {shared_libs}")
    return shared_libs
