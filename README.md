# Step-by-Step ADK

This repository contains sample code that will allow you to learn the features of [Google ADK](https://google.github.io/adk-docs/) and how to use it.

You will learn the following through the course of the steps in this repo

1. How to create a basic app using ADK
2. How is ADK different from GenAI SDK
3. How to do define and call tools using ADK
4. How to use the advanced features of ADK such as session, state, memory
5. How to deploy an ADK app to a cloud runtime
6. Agent workflows
7. Multi-agent interactions

## Getting started

To get started with this repository:

1. Clone the repository in your IDE.
2. Set up a Python environment (if you don't have uv installed, install it using `pip install uv`):

    ```shell
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3. Install dependencies using uv:

    ```shell
    uv pip install -r requirements.txt
    ```

4. Go to the step you'd like to execute

    ```shell
    cd step1
    ```

5. Run the ADK server

    ```shell
    adk web
    ```

## Creating your own agent

Any ADK agent needs to be create using the specified folder structure below.

```
parent_folder/
    multi_tool_agent/
        __init__.py
        agent.py
        .env
```

The the below command within a folder where you would like to create the agent to automatically bootstrap the required files.

``` bash
mkdir my_agent && cd my_agent && touch __init__.py agent.py && echo "from . import agent" >> __init__.py && touch .env && echo "GOOGLE_GENAI_USE_VERTEXAI=FALSE" >> .env && echo "GOOGLE_API_KEY=<paste your key here>" >> .env
```
