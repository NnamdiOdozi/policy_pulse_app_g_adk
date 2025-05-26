import datetime
from zoneinfo import ZoneInfo

def get_weather(city: str) -> dict:
    """Retrieves the current weather report for a specified city.

    Args:
        city (str): The name of the city (e.g., "New York", "London", "Tokyo").

    Returns:
        dict: A dictionary containing the weather information.
              Includes a 'status' key ('success' or 'error').
              If 'success', includes a 'report' key with weather details.
              If 'error', includes an 'error_message' key.
    """
    print(f"--- Tool: get_weather called for city: {city} ---") # Log tool execution
    city_normalized = city.lower().replace(" ", "") # Basic normalization

    # Mock weather data
    mock_weather_db = {
        "newyork": {
            "status": "success",
            "report": {"condition": "sunny", "temperature_celsius": 25},
        },
        "london": {
            "status": "success",
            "report": {"condition": "cloudy", "temperature_celsius": 15},
        },
        "tokyo": {
            "status": "success",
            "report": {
                "condition": "light rain",
                "temperature_celsius": 18,
            },
        },
        "paris": {
            "status": "success",
            "report": {"condition": "partly cloudy", "temperature_celsius": 20},
        },
        "berlin": {
            "status": "success",
            "report": {"condition": "windy", "temperature_celsius": 17},
        },
        "sydney": {
            "status": "success",
            "report": {
                "condition": "sunny",
                "temperature_celsius": 22,
            }, # Sydney is in the Southern Hemisphere, so it might be warmer if it's winter in the Northern Hemisphere.
        },
    }

    if city_normalized in mock_weather_db:
        return mock_weather_db[city_normalized]
    else:
        return {"status": "error", "error_message": f"Sorry, I don't have weather information for '{city}'."}


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
