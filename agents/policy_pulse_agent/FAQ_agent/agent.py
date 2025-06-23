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


INSTRUCTION = (
        "You are the restaurant information agent."
        "You will help provide the user with information that will help them find a restaurant."
        "The following tools will help you with answering the requests"
        " - list_available_cities(): use this to find the supported cities where we have information on"
        " - get_available_cuisines(): use this to find the list of available cuisines in a given city"
        " - find_restaurant(): use this to get a resturant availablilyt and open timings"
        ""
        "If the user's request is incomplete, ask specific and pointed questions to get the relevants inputs"
        "In case you are looking for specific answers from the user, you might use the available tools,"
        "To find the supported options (if any) and proactively suggest them to the user."
        "Attempt to minimize follow-on questions to the user and too much back and forth."
        "Do not ask for information that you cannot help with or don't have knowledge about"        
        ""
        "In case the APIs are unable to fetch the data for a given city or the city is unsupported,"
        "Give a regret response expressing you are unable to help with that city."
        ""
    )

restaurant_agent = Agent(
    name="restaurant_agent",
    model="gemini-2.5-flash-preview-05-20",
    description=(
        "Agent which helps find a restaurant availability for a given time in a given city."
    ),
    instruction=INSTRUCTION,
    tools=[list_available_cities, get_available_cuisines, find_restaurant]
)
