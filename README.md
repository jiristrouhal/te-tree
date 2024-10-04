# Te-Tree
A base for simple applications for organizing, analysing and storing data in tree structure.

## Usage

### Before use

Make sure you have Python 3.11 or higher installed.

Install dependencies:
- create virtual environment: `python -m venv .venv`
- [activate](https://docs.python.org/3/library/venv.html#how-venvs-work),
- install dependencies: `pip install -r requirements.txt`.

### Example of app definition

For example of the app usage, see examples in individual subfolders of the `example` in the root directory. To use the examples, in the virtual environment install the te_tree package by running:
```bash
pip install .
```

### Testing

To run unit tests, make sure you have completed instruction in the [before use](#before-use) section.

Run tests:
```bash
python3 -m tests [-h] [PATH1] [PATH2] ...
```

Each PATH is specified relative to the tests folder. If no PATH is specified, all the tests will run. Otherwise

when PATH is a directory, the script will run all tests in this directory (and subdirectories),
when PATH is a Python file, the script will run all tests in the file.
The -h flag makes the script display tests' coverage in an HTML format, for example in your web browser.

## Other notes

Other content will be filled up soon, everything explained in detail.


For any questions, use contact on my [profile](https://github.com/jiristrouhal). Thank you!
