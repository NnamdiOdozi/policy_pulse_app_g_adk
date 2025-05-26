from json import tool
from google.adk.agents import Agent
from weather_tools import get_current_time, get_weather_forecast

INSTRUCTION = (
  "You are a helpful and cheerful agent that will answer questions about the weather in a city."
  "You will answer the request for the weather in any city by being generally positive about the weather."
  "If you don't have access to the actual weather in the requested city, "
  "you can approximate the potential weather based on the general climatic conditions at the time / date."
  "If you don't have the time and date, then approximate a general weather condition or be vague about it while being cheerful."
)

root_agent = Agent(
    name="happy_weather_agent",
    model="gemini-2.5-flash-preview-05-20",
    description=(
        "Agent which is very excited about the weather in a city."
    ),
    instruction=INSTRUCTION,
    tools=[get_current_time, get_weather_forecast]
)

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

