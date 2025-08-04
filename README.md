# Jenkins to GitHub Actions Converter

This Python framework facilitates the conversion of **Declarative Jenkins Pipelines** into **GitHub Actions workflow files**. It automates the translation of pipeline syntax, reducing manual effort and streamlining CI/CD migration.

## Features

1. **Batch Conversion**
   - The tool processes all Jenkins pipeline files within a specified directory.
   - Usage: `python3 main.py --dir <directory_name>`

2. **Shared Libraries Conversion**
   - `.groovy` files should be placed inside the `vars/` directory.
   - The framework first parses `.groovy` files and converts them to YAML.
   - When encountering shared library calls in the pipeline, it references the pre-converted YAML content.

3. **Supported Plugins**
   - The framework currently supports the following plugins:
     - **Git**
     - **Maven**
     - **Shell**
     - **Docker**
     - **Kubernetes**

4. **Extensibility**
   - To support additional plugins, logic must be added to `converter.py` to handle new Jenkins constructs.

## Future Enhancements

- **Environment Variables and Parameters** (`env` and `params`) are not yet supported but can be added with additional logic.
- Further comparisons with the **GitHub Actions Importer Plugin** will be included in this document later.

## Observations

- The framework significantly reduces manual intervention when migrating Jenkins pipelines to GitHub Actions.
- Future updates will refine the conversion accuracy and expand plugin support.

## How to Use

```bash
python main.py --dir <directory_name>
```

```
example: python3 main.py  --dir Jenkins_files/
```
Ensure that your Jenkins pipelines and shared libraries are structured correctly for optimal results.

---

For contributions or enhancements, feel free to open an issue or submit a pull request!

