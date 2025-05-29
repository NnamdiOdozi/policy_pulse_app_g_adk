# Step-by-Step ADK

This repository contains sample code that will allow you to learn the features of [Google ADK](https://google.github.io/adk-docs/) and how to use it.

## Learning Objectives

Through the course of the steps in this repository, you will learn:

1. **01_basic_agents**: How to create a basic agent using ADK.
2. How ADK is different from the GenAI SDK (Upcoming)
3. How to define and call tools using ADK (Covered progressively, starting with exercises in 01_basic_agents)
4. How to use advanced ADK features such as session, state, and memory (Upcoming)
5. How to deploy an ADK app to a cloud runtime (Upcoming)
6. Agent workflows (Upcoming)
7. Multi-agent interactions (Upcoming)

## Getting started

This repository is structured into sequential steps, each in its own directory (e.g., `01_basic_agents`, `02_another_step`, etc.).

To get started with this repository:

1. Clone the repository in your IDE.
2. Set up a Python environment (_Note: if you don't have `uv` installed, install it using `pip install uv` - I highly recommend this tool_):

    ```shell
    uv venv
    ```

    or

    ```shell
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3. Install dependencies using uv:

    ```shell
    uv sync
    ```

     or

     ```shell
     pip install -r requirements.txt
    ```

4. Go to the step you'd like to execute

    ```shell
    cd 01_basic_agents
    ```

    Each step directory contains its own `README.md` with specific instructions and explanations for that agent.

5. Run the ADK server

    ```shell
    adk web
    ```

    This will start a local server (usually at `http://localhost:8000`). Open this URL in your web browser to interact with the agent for that step.

## Repository Structure

* **/01_basic_agents**: Learn the fundamentals of creating and running a simple ADK agent. The `README.md` in this directory includes exercises for adding tools.
* **(More steps will be added here as they are developed)**

Follow the `README.md` file within each step's directory for detailed guidance.

## Creating your own agent

Any ADK agent needs to be create using the specified folder structure below.

```shell
parent_folder/
    multi_tool_agent/
        __init__.py
        agent.py
        .env
```

Then run the below command within a folder where you would like to create the agent to automatically bootstrap the required files.

``` bash
mkdir my_agent && cd my_agent && touch __init__.py agent.py && echo "from . import agent" >> __init__.py && touch .env && echo "GOOGLE_GENAI_USE_VERTEXAI=FALSE" >> .env && echo "GOOGLE_API_KEY=<paste your key here>" >> .env
```

The API Key for Gemini can be obtained from [Google AI Studio](https://aistudio.google.com/app/apikey)

_I recommend that you export the API key to the environment. Either use the below command or include it in your **bash** or **zsh** env files._

```bash
  export GOOGLE_API_KEY=<paste your key here>
```

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues.

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE file](LICENSE) for details.
