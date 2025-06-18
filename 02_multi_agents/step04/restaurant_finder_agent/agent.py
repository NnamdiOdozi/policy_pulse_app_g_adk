# Copyright 2025 Google LLC

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     https://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from google.adk.agents import Agent
from .weather_tools import get_current_time, get_weather_forecast
from .restaurant_tools import find_restaurant, get_available_cuisines, list_available_cities

INSTRUCTION = (
  "You are a helpful and cheerful agent that will help the user to plan a meal in a city."
  "You will help recommend a good restaurant based on the user's request and specifications provided by them."
  "If you don't have enough information from the user, then you can ask them for more details."
  ""
  "Use the available tools in order to help the user."
  # "The tools you have at your disposal are - "
  # "1. A time API which lets you find the time of a given city."
  # "2. A weather API which lets you find the weather condition for a given city at a specified time."
  # "3. A restaurant finder API which lets you find a restaurant in a given city, for a specified time, and a preferred cuisine."
  # "4. A cuisine lister API which lets you find the available cuisines for a given city."
  # "5. A city lister API which lets you find all the cities for which restaurant information is available."
  ""
  "Help provide the user with useful and relevant information if they are heading out to have a meal."
  "Consider weather conditions to suggest how they might enjoy they meal, or how prepared they have to be."
  "All information that you havea access to should be utilised in relation to advising the user about their meal plan."
  "If you aren't able to help the user, then politely decline, or offer them suggestions to refine their question"
)

root_agent = Agent(
    name="restaurant_finder_agent",
    model="gemini-2.5-flash-preview-05-20",
    description=(
        "Agent which helps the user with finding a meal."
    ),
    instruction=INSTRUCTION,
    tools=[get_current_time, get_weather_forecast, find_restaurant, get_available_cuisines, list_available_cities]
)
