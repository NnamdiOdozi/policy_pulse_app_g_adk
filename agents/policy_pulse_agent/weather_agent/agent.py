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

import random
from google.adk.agents import Agent

# Note: get_current_time function has been moved to time_agent/agent.py

# Base temperatures C = city -> time_of_day -> base_temp_celsius
BASE_TEMPERATURES = {
    "newyork": {"morning": 18, "noon": 26, "evening": 20, "night": 15},
    "london": {"morning": 10, "noon": 16, "evening": 12, "night": 8},
    "tokyo": {"morning": 15, "noon": 20, "evening": 17, "night": 14},
    "paris": {"morning": 12, "noon": 21, "evening": 18, "night": 10},
    "berlin": {"morning": 10, "noon": 18, "evening": 14, "night": 7},
    "sydney": {"morning": 19, "noon": 24, "evening": 20, "night": 16},
    "delhi": {"morning": 28, "noon": 35, "evening": 30, "night": 25},
    "bengaluru": {"morning": 22, "noon": 28, "evening": 24, "night": 20},
}

PLEASANT_CONDITIONS = [
    {"condition": "clear and sunny", "temp_adjust": (0, 1)},
    {"condition": "partly cloudy with a gentle breeze", "temp_adjust": (0, 0)},
    {"condition": "mild and pleasantly overcast", "temp_adjust": (-1, 0)},
    {"condition": "crisp and clear", "temp_adjust": (0, 0)},
    {"condition": "a beautiful day, perfect for a stroll", "temp_adjust": (0, 1)},
    {"condition": "calm and comfortable", "temp_adjust": (0,0)},
]

INCONVENIENT_CONDITIONS = [
    {"condition": "light rain showers, you might want an umbrella", "temp_adjust": (-2, -1)},
    {"condition": "drizzling and a bit cool", "temp_adjust": (-2, -1)},
    {"condition": "quite windy, hold onto your hat!", "temp_adjust": (-1, 0)},
    {"condition": "hazy and humid", "temp_adjust": (0, 1)},
    {"condition": "a bit chilly, layer up if walking", "temp_adjust": (-2, -1)},
    {"condition": "grey and overcast, chance of light drizzle", "temp_adjust": (-1, -1)},
]

SEVERE_CONDITIONS = [
    {"condition": "heavy rain, definitely cab weather!", "temp_adjust": (-3, -2)},
    {"condition": "snowfall, roads might be tricky", "temp_adjust": (-5, -3)}, # More likely in colder cities
    {"condition": "dusty winds, visibility could be low", "temp_adjust": (0, 1)}, # More likely in specific regions
    {"condition": "thunderstorms likely, best to stay indoors or take a cab", "temp_adjust": (-2, 0)},
    {"condition": "very windy and cold, not pleasant for walking", "temp_adjust": (-4, -2)},
    {"condition": "unexpected heatwave, very hot!", "temp_adjust": (3, 5)}, # For normally cooler places
]


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

    if city_normalized not in BASE_TEMPERATURES or time_of_day not in BASE_TEMPERATURES[city_normalized]:
        return {"status": "error", "error_message": f"Sorry, I don't have base weather data for '{city}' at {time_of_day} ({time_str})."}

    base_temp = BASE_TEMPERATURES[city_normalized][time_of_day]
    
    # Determine weather category based on probability
    # 70% pleasant, 20% inconvenient, 10% severe
    rand_val = random.random()
    selected_condition_data = None
    
    if rand_val < 0.70:
        selected_condition_data = random.choice(PLEASANT_CONDITIONS)
    elif rand_val < 0.90: # 0.70 to 0.89
        selected_condition_data = random.choice(INCONVENIENT_CONDITIONS)
    else: # 0.90 to 0.99
        # City-specific severe conditions
        if city_normalized in ["newyork", "london", "paris", "berlin", "tokyo"] and base_temp < 5: # Higher chance of snow in colder temps
            if random.random() < 0.3: # 30% chance of snow if conditions are right
                 selected_condition_data = next((c for c in SEVERE_CONDITIONS if "snow" in c["condition"].lower()), None)
        elif city_normalized == "delhi" and time_of_day in ["morning", "noon"]:
             if random.random() < 0.2: # 20% chance of dust
                 selected_condition_data = next((c for c in SEVERE_CONDITIONS if "dust" in c["condition"].lower()), None)
        
        if not selected_condition_data: # Default severe condition if specific one not picked
            selected_condition_data = random.choice(SEVERE_CONDITIONS)
            # Avoid snow/dust if not appropriate for city/temp by re-picking if necessary
            while (( "snow" in selected_condition_data["condition"].lower() and (city_normalized not in ["newyork", "london", "paris", "berlin", "tokyo"] or base_temp >= 5) ) or
                   ( "dust" in selected_condition_data["condition"].lower() and city_normalized != "delhi")):
                selected_condition_data = random.choice(SEVERE_CONDITIONS)


    final_temp = base_temp + random.randint(selected_condition_data["temp_adjust"][0], selected_condition_data["temp_adjust"][1])

    return {
        "status": "success",
        "report": {
            "condition": selected_condition_data["condition"],
            "temperature_celsius": final_temp,
            "time_of_day_approximated": time_of_day,
        },
    }


INSTRUCTION = (
        "You are a weather information agent."
        "You will help provide the user with weather forecast information for a specified city and time."
        "The following tool will help you with answering the requests:"
        " - get_weather_forecast(): use this to find the weather in any city at a specified time of day."
        ""
        "If the user's request is incomplete, ask for the city and time."
        "In case the city or time is unsupported by the forecast data, give a regret response."
    )

weather_agent = Agent(
    name="weather_agent",
    model="gemini-2.5-flash-preview-05-20",
    description=(
        "Agent which provides weather forecast information for a given city and time."
    ),
    instruction=INSTRUCTION,
    tools=[get_weather_forecast]
)
