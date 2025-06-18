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
from .weather_agent import weather_agent
from .restaurant_agent import restaurant_agent
from .transport_agent import transport_agent
from .time_agent import time_agent

INSTRUCTION = (
  "You are a helpful and cheerful agent that will help the user to plan a meal in a city."
  "You will help recommend a good restaurant based on the user's request and specifications provided by them."
  "If you don't have enough information from the user, then you can ask them for more details."
  "Try to minimise back and forth with the user and where possible provide options or suggestions to help the user"
  "Do not ask for information that you cannot help with or don't have knowledge about"
  ""
  "Use the available sub agents in order to help the user."
  "As the primary user facing agent, you should coordinate among the sub-agents to meet the user's objectives"
  ""
  "The time agent will help find the current time in the city."
  "The weather agent will help find the weather conditions for a given city."
  "The restaurant agent will help find the restaurants, the cuisine served, and the open times"
  "The transportation agent will help find availability of cabs"
  ""
  "Help provide the user with useful and relevant information if they are heading out to have a meal."
  "Consider weather conditions to suggest how they might enjoy they meal, or how prepared they have to be, or should they look for transport."
  "All information that you havea access to should be utilised in relation to advising the user about their meal plan."
  "If you aren't able to help the user, then politely decline, or offer them suggestions to refine their question"
)

root_agent = Agent(
    name="restaurant_finder_agent",
    model="gemini-2.5-flash-preview-05-20",
    description=(
        "Agent which helps the user have a good meal experience."
    ),
    instruction=INSTRUCTION,
    sub_agents=[time_agent, weather_agent, restaurant_agent, transport_agent]
)
