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



# Todo(s):
# Step 1 - add the get_weather and get_current_time as tools to the agent
#             tools=[get_current_time, get_weather]
#         don't forget to import the functions. :-)
#             from tools import get_current_time, get_weather
# Try Out: Now ask questions about the weather in various cities as well as the times
#           Observe the tool calls in the trace
# Step 2 - change the get_weather tool to get_weather_forecast
#             tools=[get_current_time, get_weather_forecast]
# Try Out: Ask questions that include a city and the time
#           Observe the tools call in the trace now
# Try Out:  Ask questions that have already been answered, or ask questions
#           related to what you have already asked.

