# Step 1: Happy Weather Agent - Evolving through Tool Usage

This folder contains a simple ADK agent that is very happy about the current weather in any city. This agent will evolve through the steps to incorporate tool usage.

## Running the Agent

1. Make sure you have the ADK installed and configured.
2. Navigate to the specific step directory in your terminal.
3. Run the agent using the ADK command:

    ```bash
    adk web
    ```

4. A web interface will start where you can interact with the agent and trace the agent flow and look at debug information.

## Agent Functionality (Step 01)

This agent is designed to be very simple. It does not use any tools. Its behavior is entirely guided by its system instructions.

When you ask this agent about the weather in a specific city, it will respond in an approximate but mostly positive way. It doesn't have real-time weather data, so the response will be based on its training and the system instructions.

To run this agent, navigate to this directory in your terminal and execute the following command:

```bash
adk web
```

This will start a web server and provide you with a URL to interact with the agent through a web interface.

## Evolving the Agent: From Step 01 to Step 02

In step 01, the agent doesn't use any tools. It just responds based on its system instructions.

**Exercise:**

1. Add `get_weather` and `get_current_time` as tools to the agent.
2. Import the functions from the `tools` module.

    ```python
    from tools import get_current_time, get_weather
    ```

3. Update the `tools` list in the agent's configuration to include the new tools:

    ```python
    tools=[get_current_time, get_weather]
    ```

**Explanation:**

By adding tools, the agent can now access external information. The `get_weather` tool can provide a mocked-up weather report for a predefined set of supported cities, and the `get_current_time` tool can provide the current local time for the same set of supported cities.

**What you can learn:**

* How to add tools to an ADK agent.
* How the agent decides whether a tool is needed based on your prompt.
* How the agent handles ambiguity and seeks necessary information.

## Agent Functionality (Step 02)

In this step, we enhance our basic agent by providing it access to external tools. This allows the agent to perform actions or retrieve information that is outside of its inherent knowledge.

The system instructions for the agent remain the same as in Step 1. The agent is still instructed to respond concisely and avoid unnecessary pleasantries.

The key change is the addition of two tools:

1. **Weather Tool**: This tool can provide a mocked-up weather report for a predefined set of supported cities.
2. **Time Tool**: This tool can provide the current local time for the same set of supported cities.

To run this enhanced agent, use the following command:

```bash
adk web
```

This will start the ADK web interface, allowing you to interact with the agent.

When you interact with the agent, pay close attention to its behavior:

* **Tool Usage**: Observe how the agent decides whether a tool is needed based on your prompt. If your prompt relates to weather or time for a supported city, the agent will likely utilize the relevant tool.
* **Follow-up Questions**: Notice that if you ask for information that requires a city name (e.g., "What is the weather like?"), but don't specify one, the agent will ask for clarification. This demonstrates its ability to handle ambiguity and seek necessary information, even though this specific behavior isn't explicitly included in the system instructions.

Experiment with different prompts to see how the agent leverages the tools and handles various scenarios. For example, try asking for:

* The weather in a supported city.
* The time in a supported city.
* The weather in an unsupported city.
* Both the weather and time in a supported city in a single prompt.
* Information that does not require a tool.

This will help you understand how the agent integrates tools into its decision-making process.

## Evolving the Agent: From Step 02 to Step 03

In step 02, the agent uses two separate tools to get the weather and the time.

**Exercise:**

1. Change the `get_weather` tool to `get_weather_forecast`.
2. Modify the `get_weather_forecast` tool to take both a city and a time as input.

**Explanation:**

In step 03, the weather tool now takes both a city and a time as input and provides mocked-up weather conditions for different times of the day.

Previously, only one of the two tools (`get_time` or `get_weather`) was selected based on the user's input. Now, you'll observe that if you ask for the weather for a specific time or in general, since the weather is dependent on the time, the `get_time` tool is called first. The obtained time is then passed to the `get_weather` tool.

You can even ask for weather in the future (e.g., "weather later in the day"). In this case, the current time is fetched, a few hours are added to it, and then the `get_weather` tool is called with the updated time. This demonstrates how data flows across multiple tools within the agent.

**What you can learn:**

* How to modify existing tools.
* How to make tools dependent on each other.
* How data flows across multiple tools within the agent.

## Agent Functionality (Step 03)

In this step, we've enhanced our weather tool. It now takes both a city and a time as input and provides mocked-up weather conditions for different times of the day.

Previously, only one of the two tools (`get_time` or `get_weather`) was selected based on the user's input. Now, you'll observe that if you ask for the weather for a specific time or in general, since the weather is dependent on the time, the `get_time` tool is called first. The obtained time is then passed to the `get_weather` tool.

You can even ask for weather in the future (e.g., "weather later in the day"). In this case, the current time is fetched, a few hours are added to it, and then the `get_weather` tool is called with the updated time. This demonstrates how data flows across multiple tools within the agent.

As in previous steps, you can start the agent from within this folder by running:

```bash
adk web
```

Interact with the agent in your web browser and observe how the tools are chained together to answer your queries about the weather.
