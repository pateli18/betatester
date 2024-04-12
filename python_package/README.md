# BetaTester

BetaTester is a simple tool to help you automatically test the UI / UX of your web application on different browsers and devices without having to right brittle front-end tests. It uses LLMs to plan and select actions and [Playwright](https://playwright.dev/) to execute those actions.

As you develop and change your web application, you can specify BetaTester to continuously test high level flows like "Sign up", "Login", "Add to cart", etc. Failures can indicate either a bug in the UI or potentially non-intuitive UX, which you can investigate further using the [application](#application) or the [Playwright trace](https://playwright.dev/python/docs/trace-viewer-intro) it automatically generates.

If you don't want to keep using LLMs for every test, BetaTester [generates a scrape spec](#usage) from an LLM run that can be run deterministically.

## Contents

- [Python Package](#python-package)
- [CLI](#cli)
- [Application](#application)
- [Extensions](#extensions)

## Python Package

### Installation

1. Install the package

```bash
pip install betatester
```

2. If you have not run Playwright before, you will need to [install the browser dependencies](https://playwright.dev/python/docs/installation#installation). This only needs to be done once per system

```bash
playwright install --with-deps chromium`
```

3. Make sure to retrieve an [your OpenAI API key](https://platform.openai.com/docs/quickstart/account-setup) if you have not already done so.

### Usage

Run the test using LLMs. See the docstring [here](./src/betatester/execution.py#L559) for more information on the avaiable parameters.

```python
from betatester import ScrapeAiExecutor
from betatester.file.local import LocalFileClient

file_client = LocalFileClient("./app-data/")

scrape_executor = ScrapeAiExecutor(
    url="https://google.com",
    high_level_goal="Find images of cats",
    openai_api_key="...",
    file_client=file_client,
)
await scrape_executor.run()
```

Run the test using a scrape spec (with no LLM calls) generated from a previous LLM run. See the docstring [here](./src/betatester/execution.py#L758) for more information on the avaiable parameters.

```python
from betatester import ScrapeSpecExecutor
from betatester.file.local import LocalFileClient

file_client = LocalFileClient("./app-data/")
scrape_spec = await file_client.load_scrape_spec("/path/to/scrape_spec.json")

scrape_spec_executor = ScrapeSpecExecutor(
    scrape_spec=scrape_spec,
)
await scrape_spec_executor.run()
```

## CLI

### Installation

1. Install the package

```bash
pip install betatester[cli]
```

2. If you have not run Playwright before, you will need to [install the browser dependencies](https://playwright.dev/python/docs/installation#installation). This only needs to be done once per system

```bash
playwright install --with-deps chromium`
```

3. Make sure to retrieve an [your OpenAI API key](https://platform.openai.com/docs/quickstart/account-setup) if you have not already done so and set it as an environment variable `OPENAI_API_KEY`.

### Usage

Run the test using LLMs. Use `betatester start_ai --help` for more information on the avaiable parameters.

```bash
FILE_CLIENT_CONFIG='{"save_path": "./app-data/"}' betatester start_ai --url "https://google.com" --high-level-goal "Find images of cats" --file-client-type "local"
```

Run the test using a scrape spec (with no LLM calls) generated from a previous LLM run. Use `betatester start_spec --help` for more information on the avaiable parameters.

```bash
FILE_CLIENT_CONFIG='{"save_path": "./app-data/"}' betatester start_spec --scrape-spec-path "/path/to/scrape_spec.json" --file-client-type "local"
```

## Extensions

### File

AutoTransform provides a file extension that allows you to store your files in the storage provider of your choice. To use the file extension, you will need to provide the following environment variables:

- **FILE_CLIENT_TYPE**: The file client you are using, currently only `local` is supported
- **FILE_CLIENT_CONFIG**: A string that contains the configuration for your file client. The format of this object is specific to the provider you are using.
  - For `local` the format is a json obejct with the following keys:
    - **save_path**: The path to the directory where you want to store your files

You can add other file proviers by:

1. Adding a new class that inherits from [FileClient](./src/betatester/betatester_types.py#L252). See [local.py](./src/betatester/file/local.py) for an example.
2. Updating [\_\_init\_\_.py](../backend/betatester/file/__init__.py) to return your new class when the `FILE_CLIENT_TYPE` environment variable is set to the name of your new class.
3. Updating the [FileCLientType](./src/betatester/betatester_types.py#L252) enum to include your new client type
