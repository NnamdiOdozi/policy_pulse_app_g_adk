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
import datetime
from google.adk.agents import Agent

def get_cab_availability(time_str: str, city: str) -> dict:
    """
    Gets the availability of a cab for a given city along with fare details.

    Args:
        time_str: The time for which to check cab availability (e.g., "10:00 AM").
        city: The city where the cab is needed.

    Returns:
        A dictionary containing:
            - "available": Boolean indicating if a cab is available.
            - "fare_estimate": A string representing the estimated fare (e.g., "$15 - $25").
            - "time_to_destination": A string representing the estimated time to destination (e.g., "10-15 minutes").
    """
    # Simulate higher availability during off-peak hours and lower during peak hours
    # For simplicity, let's consider peak hours to be 8-10 AM and 5-7 PM
    try:
        # Attempt to parse time like "10:00 AM" or "14:30"
        time_obj = datetime.datetime.strptime(time_str.split()[0], "%H:%M")
        hour = time_obj.hour
    except ValueError:
        # Fallback for other formats or if AM/PM is missing and it's just HH:MM
        try:
            time_obj = datetime.datetime.strptime(time_str, "%I:%M %p") # e.g. 2:30 PM
            hour = time_obj.hour
        except ValueError:
             # Default to a neutral probability if time format is unexpected
            hour = 12  # Noon

    # Supported cities (from RESTAURANTS_DB in restaurant_agent.py)
    # Normalized to lowercase and no spaces for comparison
    supported_cities = ["newyork", "paris", "london", "delhi", "bengaluru", "tokyo"]
    major_supported_cities = ["newyork", "paris", "london", "tokyo"]
    city_normalized = city.lower().replace(" ", "")

    # Base availability probability
    availability_probability = 0.7  # 70% base chance

    if 8 <= hour < 10 or 17 <= hour < 19:  # Peak hours (8-9:59 AM, 5-6:59 PM)
        availability_probability = 0.4  # 40% chance during peak
    elif 0 <= hour < 6 or 22 <= hour < 24:  # Late night / early morning (midnight-5:59 AM, 10 PM - 11:59 PM)
        availability_probability = 0.5 # 50% chance

    # City-based adjustment
    if city_normalized in supported_cities:
        if city_normalized in major_supported_cities:
            availability_probability += 0.15 # Higher boost for major supported cities
        else: # Other supported cities like delhi, bengaluru
            availability_probability += 0.05 # Smaller boost
    else:
        # For unsupported cities, significantly reduce availability
        availability_probability = 0.1 # Low chance for unsupported cities
    
    # Ensure probability is within [0, 1]
    availability_probability = max(0, min(1, availability_probability))

    is_available = random.random() < availability_probability

    if not is_available:
        return {
            "available": False,
            "fare_estimate": None,
            "time_to_destination": None,
        }

    # Mock dynamic fare based on time and a base rate
    base_fare = random.uniform(10, 30)  # Base fare between $10 and $30
    fare_multiplier = 1.0
    if 8 <= hour < 10 or 17 <= hour < 19: # Peak hour surcharge
        fare_multiplier = 1.5
    elif 0 <= hour < 6 or 22 <= hour < 24: # Late night surcharge
        fare_multiplier = 1.3
    
    final_fare_lower = base_fare * fare_multiplier
    final_fare_upper = final_fare_lower * random.uniform(1.15, 1.30) # Add a 15-30% range

    # Mock dynamic time estimate
    base_time_to_dest = random.randint(5, 25) # Base time 5 to 25 mins
    time_multiplier = 1.0
    if 8 <= hour < 10 or 17 <= hour < 19: # Peak hour traffic
        time_multiplier = 1.8
    # Adjust for high-traffic supported cities
    elif city_normalized in ["newyork", "paris", "london", "delhi", "bengaluru", "tokyo"]:
        time_multiplier = 1.5 # Consistent high traffic multiplier for supported cities
        
    final_time_lower = int(base_time_to_dest * time_multiplier)
    # Ensure upper time is at least a few minutes more than lower, and adds some variability
    final_time_upper = final_time_lower + random.randint(3, 10)


    return {
        "available": True,
        "fare_estimate": f"${final_fare_lower:.2f} - ${final_fare_upper:.2f}",
        "time_to_destination": f"{final_time_lower}-{final_time_upper} minutes",
    }


INSTRUCTION = (
        "You are an agent that can help with transportation in a city."
        "You will help provide the user with information that will help them find a restaurant."
        "The following tools will help you with answering the requests"
        " - get_cab_availability(): use this to find whether transportation is available for a given city at a given time"
        "If a cab is available, then it will also return an ETA and an estimated fare"
        "If the user's request is incomplete, ask specific and pointed questions to grth."
        ""
        "In case the APIs are unable to fetch the data for a given city or the city is unsupported,"
        "Give a regret response expressing you are unable to help with that city."
        ""
    )

transport_agent = Agent(
    name="transport_agent",
    model="gemini-2.5-flash-preview-05-20",
    description=(
        "Agent which helps find a transport to a restaurant in a city at a give time."
    ),
    instruction=INSTRUCTION,
    tools=[get_cab_availability]
)
