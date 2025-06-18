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

# Mock database of restaurants
RESTAURANTS_DB = {
    "newyork": {
        "local": {"name": "NYC Diner (American)", "opens": "07:00", "closes": "22:00"}, # Breakfast/Lunch/Dinner
        "italian": {"name": "Joe's Pizza", "opens": "11:00", "closes": "23:00"},
        "chinese": {"name": "Golden Dragon", "opens": "12:00", "closes": "22:00"},
    },
    "paris": {
        "local": {"name": "Le Petit Bistro (French)", "opens": "12:00", "closes": "22:00"},
        "italian": {"name": "Mamma Mia Trattoria", "opens": "18:00", "closes": "23:00"},
        "chinese": {"name": "Délices de Chine", "opens": "11:30", "closes": "15:00"}, # Lunch only
    },
    "london": {
        "local": {"name": "The Royal Oak (British Pub)", "opens": "12:00", "closes": "23:00"},
        "indian": {"name": "Taste of India", "opens": "17:00", "closes": "23:30"},
        "italian": {"name": "La Dolce Vita", "opens": "12:00", "closes": "22:30"}, # Lunch/Dinner
    },
    "delhi": {
        "indian": {"name": "Dilli Darbar (North Indian)", "opens": "12:00", "closes": "23:00"},
        "chinese": {"name": "Wok In The Clouds", "opens": "12:30", "closes": "23:00"},
        "italian": {"name": "Roma Ristorante", "opens": "13:00", "closes": "22:00"},
    },
    "bengaluru": {
        "indian": {"name": "Vidyarthi Bhavan (South Indian)", "opens": "07:00", "closes": "20:00"}, # All day
        "chinese": {"name": "Beijing Bites", "opens": "12:00", "closes": "23:00"},
        "italian": {"name": "Little Italy", "opens": "12:30", "closes": "16:00"}, # Lunch only
    },
    "tokyo": {
        "local": {"name": "Ichiraku Ramen (Japanese)", "opens": "11:00", "closes": "02:00"}, # Lunch/Late Night
        "italian": {"name": "Saizeriya Tokyo", "opens": "11:00", "closes": "23:00"},
        "chinese": {"name": "Tokyo Gyoza Lou", "opens": "11:30", "closes": "21:30"},
    },
}
def find_restaurant(city: str, cuisine: str, time: str) -> dict:
    """
    Finds a restaurant in a given city for a specific cuisine and time.

    Args:
        city (str): The city where the user wants to find a restaurant.
        cuisine (str): The type of cuisine the user is interested in.
                       Can be "local" to indicate the city's native cuisine.
        time (str): The desired time for the meal, in HH:MM format (e.g., "19:00").

    Returns:
        dict: A dictionary containing the status of the search and either a success report or an error message.
    """
    print(f"--- Tool: find_restaurant called for {city}, {cuisine} at {time} ---")
    city_normalized = city.lower().replace(" ", "")

    if city_normalized in RESTAURANTS_DB and cuisine.lower() in RESTAURANTS_DB[city_normalized]:
        restaurant_info = RESTAURANTS_DB[city_normalized][cuisine.lower()]
        # Check if the restaurant is open at the requested time
        # This is a simple example. A real implementation would be more robust.
        if restaurant_info["opens"] <= time <= restaurant_info["closes"]:
            return {"status": "success", "report": f"I found a {cuisine} restaurant called '{restaurant_info['name']}'."}
        else:
            return {"status": "error", "error_message": f"Sorry, I couldn't find any {cuisine} restaurants open at {time}."}
    else:
        return {"status": "error", "error_message": f"Sorry, I couldn't find any {cuisine} restaurants in {city}."}

def get_available_cuisines(city: str) -> dict:
    """
    Gets a list of available cuisines in a given city.

    Args:
        city (str): The city to check for available cuisines.

    Returns:
        dict: A dictionary containing the status and a list of cuisines or an error message.
    """
    print(f"--- Tool: get_available_cuisines called for {city} ---")
    city_normalized = city.lower().replace(" ", "")
    if city_normalized in RESTAURANTS_DB:
        cuisines = list(RESTAURANTS_DB[city_normalized].keys())
        return {"status": "success", "cuisines": cuisines}
    else:
        return {"status": "error", "error_message": f"Sorry, I don't have information for the city: {city}."}

def list_available_cities() -> dict:
    """
    Lists all available cities in the restaurant database.

    Returns:
        dict: A dictionary containing the status and a list of cities.
    """
    print("--- Tool: list_available_cities called ---")
    cities = list(RESTAURANTS_DB.keys())
    return {"status": "success", "cities": [city.title() for city in cities]}
