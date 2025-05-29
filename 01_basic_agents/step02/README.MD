# Step 2: Agents with Tools

In this step, we enhance our basic agent by providing it access to external tools. This allows the agent to perform actions or retrieve information that is outside of its inherent knowledge.

## Agent Capabilities

The system instructions for the agent remain the same as in Step 1. The agent is still instructed to respond concisely and avoid unnecessary pleasantries.

The key change is the addition of two tools:

1. **Weather Tool**: This tool can provide a mocked-up weather report for a predefined set of supported cities.
2. **Time Tool**: This tool can provide the current local time for the same set of supported cities.

## Running the Agent

To run this enhanced agent, use the following command:

```bash
adk web
```

This will start the ADK web interface, allowing you to interact with the agent.

## Observing Agent Behavior

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
