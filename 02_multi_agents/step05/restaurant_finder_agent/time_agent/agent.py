# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
from zoneinfo import ZoneInfo
from google.adk.agents import Agent

def get_current_time(city: str) -> dict:
    """Returns the current time in a specified city.

    Args:
        city (str): The name of the city for which to retrieve the current time.

    Returns:
        dict: status and result or error msg.
    """
    print(f"--- Tool: get_current_time called for city: {city} ---") # Log tool execution
    city_normalized = city.lower().replace(" ", "")

    # Mapping of cities to their IANA timezone identifiers
    city_timezones = {
        "newyork": "America/New_York",
        "london": "Europe/London",
        "tokyo": "Asia/Tokyo",
        "paris": "Europe/Paris",
        "berlin": "Europe/Berlin",
        "sydney": "Australia/Sydney",
        "delhi": "Asia/Kolkata",
        "bengaluru": "Asia/Kolkata",
    }

    if city_normalized not in city_timezones:
        return {
            "status": "error",
            "error_message": f"Sorry, I don't have timezone information for '{city}'.",
        }

    tz_identifier = city_timezones[city_normalized]
    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    report = (
        f'The current time in {city} is {now.strftime("%Y-%m-%d %H:%M:%S %Z%z")}'
    )
    return {"status": "success", "report": report}

INSTRUCTION = (
        "You are a time information agent."
        "You will help provide the user with the current local time in a specified city."
        "The following tool will help you with answering the requests:"
        " - get_current_time(): use this to get the current local time for any city."
        ""
        "If the user's request is incomplete, ask for the city."
        "In case the city is unsupported, give a regret response."
    )

time_agent = Agent(
    name="time_agent",
    model="gemini-2.5-flash-preview-05-20",
    description=(
        "Agent which helps find the current time in a given city."
    ),
    instruction=INSTRUCTION,
    tools=[get_current_time]
)