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
from weather_tools import get_current_time, get_weather

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
    tools=[get_current_time, get_weather]
)
