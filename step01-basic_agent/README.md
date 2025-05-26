# Step 1: Happy Weather Agent

This folder contains a simple ADK agent that is very happy about the current weather in any city.

## Running the Agent

1. Make sure you have the ADK installed and configured.
2. Navigate to this directory in your terminal.
3. Run the agent using the ADK command:

   ```bash
   adk run
   ```

4. The agent will start and listen for requests.

## Agent Functionality

The agent exposes a single endpoint that takes a city name as input and returns a message expressing happiness about the weather in that city.

Example request:

```
GET /weather?city=London
```

Example response:

```
The weather in London is great! I'm so happy!
