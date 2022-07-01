# Contributing

This is a Python [CDK][getting-started] project.

## Environment Set-up

To start developing you can use our [Taskfile](../docs/TASKFILE.md) to run `run install` or `run env`

Or you can do this step by step:

### Create a virtualenv:

```shell script
python3 -m venv venv
```

### Activate virtualenv

Use the following to activate the newly created virtualenv:

```shell script
source venv/bin/activate
```

If you are using Windows platform, you would activate the virtualenv like this:

```shell script
venv\Scripts\activate.bat
```

### Install dependencies

Once the virtualenv is activated, you can install the required dependencies:

```shell script
pip install pip-tools
pip-sync
```

### Synthetize template

At this point you can now synthesize the CloudFormation template for this project:

```shell script
cdk synth
```

## Code formatting

This project is using [black][black] to handle formatting.

Install `black`:

```shell script
brew install black
```

Format all files:

```shell script
black .
```

There are also [editor integrations][black-editor] available. The file watcher for
PyCharm/Intellij works well for auto-formatting on file save.

## Pre-commit integration

If you are a frequent contributor, you should setup the [pre-commit][pre-commit]
integration. From within this project's directory, run:

```shell script
brew install pre-commit
pre-commit install
```

Now various checks, import sorting and formatting will be done on git commit. To run
manually on all files, use this:

```shell script
pre-commit run --all-files
```

If you want to know where `pre-commit` installs the tools it uses, see [this
section][pre-commit-cache] on how `pre-commit` handles caching.

## Dependency management

This project uses [pip-tools][pip-tools] to manage dependencies. The following commands
require the virtualenv to be active:

```shell script
source venv/bin/activate
```

There are two primary workflows, **update** and **sync**.

### Update

To update dependencies, modify `requirements.in` file. Generally requirements get pinned
in this file for simplicity. After that, run:

```shell script
pip-compile --upgrade --no-emit-index-url
```

This will update `requirements.txt`.

### Sync

The sync command will sync `requirements.txt` with the virtualenv:

```shell script
pip-sync
```

## Useful CDK commands

- `cdk ls` list all stacks in the app
- `cdk synth` emits the synthesized CloudFormation template
- `cdk deploy` deploy this stack to your default AWS account/region
- `cdk diff` compare deployed stack with current state
- `cdk docs` open CDK documentation

[getting-started]: https://docs.aws.amazon.com/cdk/latest/guide/getting_started.html
[black]: https://github.com/psf/black
[black-editor]: https://black.readthedocs.io/en/stable/editor_integration.html
[pre-commit]: https://pre-commit.com
[pre-commit-cache]: https://pre-commit.com/#managing-ci-caches
[pip-tools]: https://github.com/jazzband/pip-tools
