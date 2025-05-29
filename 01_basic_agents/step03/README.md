# Step 03: Data flow between tools

In this step, we've enhanced our weather tool. It now takes both a city and a time as input and provides mocked-up weather conditions for different times of the day.

Previously, only one of the two tools (`get_time` or `get_weather`) was selected based on the user's input. Now, you'll observe that if you ask for the weather for a specific time or in general, since the weather is dependent on the time, the `get_time` tool is called first. The obtained time is then passed to the `get_weather` tool.

You can even ask for weather in the future (e.g., "weather later in the day"). In this case, the current time is fetched, a few hours are added to it, and then the `get_weather` tool is called with the updated time. This demonstrates how data flows across multiple tools within the agent.

As in previous steps, you can start the agent from within this folder by running:

```bash
adk web
```

Interact with the agent in your web browser and observe how the tools are chained together to answer your queries about the weather.
