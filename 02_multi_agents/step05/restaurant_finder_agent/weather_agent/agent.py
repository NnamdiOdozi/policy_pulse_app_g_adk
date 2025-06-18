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


def get_weather_forecast(city: str, time_str: str) -> dict:
    """
    Retrieves a weather forecast for a specified city and time.

    Args:
        city (str): The name of the city.
        time_str (str): The time for the forecast (e.g., "08:00", "14:30", "21:00").

    Returns:
        dict: A dictionary containing the forecast information.
              Includes a 'status' key ('success' or 'error').
              If 'success', includes a 'report' key with 'condition' and 'temperature_celsius'.
              If 'error', includes an 'error_message' key.
    """
    print(f"--- Tool: get_weather_forecast called for city: {city} at time: {time_str} ---")
    city_normalized = city.lower().replace(" ", "")

    try:
        hour = int(time_str.split(":")[0])
    except (ValueError, IndexError):
        return {"status": "error", "error_message": "Invalid time format. Please use HH:MM (e.g., '08:00')."}

    time_of_day = ""
    if 6 <= hour < 12:
        time_of_day = "morning"
    elif 12 <= hour < 17:
        time_of_day = "noon" # Covers afternoon as well
    elif 17 <= hour < 21:
        time_of_day = "evening"
    else: # 21:00 to 05:59
        time_of_day = "night"

    # Mock forecast data: city -> time_of_day -> {condition, temperature}
    mock_forecast_db = {
        "newyork": {
            "morning": {"condition": "cool and sunny", "temperature_celsius": 18},
            "noon": {"condition": "warm and sunny", "temperature_celsius": 26},
            "evening": {"condition": "mild and clear", "temperature_celsius": 20},
            "night": {"condition": "cool and clear", "temperature_celsius": 15},
        },
        "london": {
            "morning": {"condition": "chilly and cloudy", "temperature_celsius": 10},
            "noon": {"condition": "mild and partly cloudy", "temperature_celsius": 16},
            "evening": {"condition": "cool and overcast", "temperature_celsius": 12},
            "night": {"condition": "cold and drizzly", "temperature_celsius": 8},
        },
        "tokyo": {
            "morning": {"condition": "mild with morning mist", "temperature_celsius": 15},
            "noon": {"condition": "warm with scattered showers", "temperature_celsius": 20},
            "evening": {"condition": "pleasant with a chance of rain", "temperature_celsius": 17},
            "night": {"condition": "cool and humid", "temperature_celsius": 14},
        },
        "paris": {
            "morning": {"condition": "crisp and clear", "temperature_celsius": 12},
            "noon": {"condition": "pleasant and partly sunny", "temperature_celsius": 21},
            "evening": {"condition": "mild with a gentle breeze", "temperature_celsius": 18},
            "night": {"condition": "cool and starlit", "temperature_celsius": 10},
        },
        "berlin": {
            "morning": {"condition": "brisk and sunny", "temperature_celsius": 10},
            "noon": {"condition": "moderate and windy", "temperature_celsius": 18},
            "evening": {"condition": "cool and breezy", "temperature_celsius": 14},
            "night": {"condition": "chilly and clear", "temperature_celsius": 7},
        },
        "sydney": { # Southern Hemisphere, opposite seasons in mind for general feel
            "morning": {"condition": "mild and sunny", "temperature_celsius": 19}, # Assuming it's a pleasant time of year
            "noon": {"condition": "warm and bright", "temperature_celsius": 24},
            "evening": {"condition": "balmy evening", "temperature_celsius": 20},
            "night": {"condition": "clear and cool", "temperature_celsius": 16},
        },
        "delhi": {
            "morning": {"condition": "hazy sun", "temperature_celsius": 28},
            "noon": {"condition": "hot and sunny", "temperature_celsius": 35},
            "evening": {"condition": "warm and clear", "temperature_celsius": 30},
            "night": {"condition": "pleasant", "temperature_celsius": 25},
        },
        "bengaluru": {
            "morning": {"condition": "pleasant with a light breeze", "temperature_celsius": 22},
            "noon": {"condition": "warm and partly cloudy", "temperature_celsius": 28},
            "evening": {"condition": "mild with a chance of showers", "temperature_celsius": 24},
            "night": {"condition": "cool and clear", "temperature_celsius": 20},
        },
    }

    if city_normalized in mock_forecast_db:
        if time_of_day in mock_forecast_db[city_normalized]:
            forecast_report = mock_forecast_db[city_normalized][time_of_day]
            return {
                "status": "success",
                "report": {
                    "condition": forecast_report["condition"],
                    "temperature_celsius": forecast_report["temperature_celsius"],
                    "time_of_day_approximated": time_of_day
                }
            }
    return {"status": "error", "error_message": f"Sorry, I don't have a forecast for '{city}' at {time_of_day} ({time_str})."}


INSTRUCTION = (
        "You are a location information agent."
        "You will help provide the user with information related to the time and weather in a city."
        "The following tools will help you with answering the requests"
        " - get_current_time(): use this to get the current local time for any city"
        " - get_weather_forecast(): use this to find the weather in any city at a specified time of day"
        ""
        "In case the APIs are unable to fetch the data for a given city or the city is unsupported,"
        "Give a regret response expressing you are unable to help with that city."
    )

weather_agent = Agent(
    name="weather_agent",
    model="gemini-2.5-flash-preview-05-20",
    description=(
        "Agent which helps find the weather for a given time in a given city."
    ),
    instruction=INSTRUCTION,
    tools=[get_current_time, get_weather_forecast]
)
