# Step 05: Transitioning to a Multi-Agent System with Dynamic Logic

In this step, we evolve our restaurant finder application by refactoring its core functionalities into a system of specialized, autonomous sub-agents. This approach enhances modularity, allows for more complex agent interactions (hand-offs), and enables each agent to possess more sophisticated and dynamic internal logic.

## Key Architectural Changes from Step 04

The primary shift from Step 04 is the move from a single agent with multiple tools to a **root agent orchestrating several specialized sub-agents**.

*   **Increased Autonomy:** Each sub-agent now encapsulates a specific domain of expertise (e.g., weather, transport), making the system more organized and scalable.
*   **Dynamic Responses:** The internal logic of these agents has been enhanced to provide more dynamic and realistic mock responses, rather than static data or simple tool outputs. For example, the `weather_agent` now simulates varied conditions, and the `transport_agent` considers factors like peak hours.

## Meet the Sub-Agents

Our `restaurant_finder_agent` (the root agent) now coordinates the following specialized sub-agents:

1.  **`restaurant_agent`**:
    *   **Purpose**: Manages information about restaurants, including their availability, cuisines, and operating hours.
    *   **Key Functionality**:
        *   `list_available_cities()`: Lists cities for which restaurant data is available.
        *   `get_available_cuisines(city: str)`: Lists cuisines available in a specific city.
        *   `find_restaurant(city: str, cuisine: str, time: str)`: Finds a restaurant based on city, cuisine, and desired time, checking against mock opening hours.
    *   **Location**: [`02_multi_agents/step05/restaurant_finder_agent/restaurant_agent/agent.py`](02_multi_agents/step05/restaurant_finder_agent/restaurant_agent/agent.py)

2.  **`transport_agent`**:
    *   **Purpose**: Simulates cab availability and provides estimated fare and travel time.
    *   **Key Functionality**:
        *   `get_cab_availability(time_str: str, city: str)`: Mocks cab availability using random probability, influenced by time (peak/off-peak) and city. Returns fare and travel time estimates if a cab is "available."
    *   **Location**: [`02_multi_agents/step05/restaurant_finder_agent/transport_agent/agent.py`](02_multi_agents/step05/restaurant_finder_agent/transport_agent/agent.py)

3.  **`time_agent`**:
    *   **Purpose**: Provides the current local time for a given city.
    *   **Key Functionality**:
        *   `get_current_time(city: str)`: Returns the current time in a specified city using its IANA timezone.
    *   **Location**: [`02_multi_agents/step05/restaurant_finder_agent/time_agent/agent.py`](02_multi_agents/step05/restaurant_finder_agent/time_agent/agent.py)

4.  **`weather_agent`**:
    *   **Purpose**: Delivers dynamic mock weather forecasts.
    *   **Key Functionality**:
        *   `get_weather_forecast(city: str, time_str: str)`: Provides a weather forecast (condition and temperature) based on the city and time of day (morning, noon, evening, night). It dynamically selects conditions (pleasant, inconvenient, severe) with varying probabilities and adjusts a base temperature.
    *   **Location**: [`02_multi_agents/step05/restaurant_finder_agent/weather_agent/agent.py`](02_multi_agents/step05/restaurant_finder_agent/weather_agent/agent.py)

## Exercise: Implement the Multi-Agent System

We encourage you to build this multi-agent system yourself! This involves creating the directory structure for each agent (`restaurant_agent`, `transport_agent`, `time_agent`, `weather_agent`), defining their respective `agent.py` and `__init__.py` files, and implementing the logic described above.

**Delta from Step 04:**
In Step 04, you were asked to implement tools like `find_restaurants`, `get_restaurant_menu`, etc., within a single agent. In Step 05, these responsibilities are distributed across dedicated agents. The core logic for these functions is now more fleshed out with mock data and dynamic behaviors.

**Using Gemini Code Assist for Implementation:**

Here are some example prompts and method signatures you can use with Gemini Code Assist to help generate the Python code for each agent's core tool:

*   **For `restaurant_agent`'s tools:**
    *   **Prompt:** "Create Python functions for a restaurant information system.
        1.  `list_available_cities()`: Returns a list of supported cities (e.g., New York, Paris, London, Delhi, Bengaluru, Tokyo).
        2.  `get_available_cuisines(city: str)`: Takes a city and returns a list of mock cuisines available there.
        3.  `find_restaurant(city: str, cuisine: str, time: str)`: Takes city, cuisine, and time (HH:MM). Check against a mock database of restaurants (with names, cuisines, opening/closing hours for each city) and return the restaurant name if open, otherwise an appropriate message."
    *   **Signatures (as implemented):**
        ```python
        RESTAURANTS_DB = { ... } # Define your mock DB
        def list_available_cities() -> dict: ...
        def get_available_cuisines(city: str) -> dict: ...
        def find_restaurant(city: str, cuisine: str, time: str) -> dict: ...
        ```

*   **For `transport_agent`'s tool:**
    *   **Prompt:** "Write a Python function `get_cab_availability(time_str: str, city: str)` to mock cab availability. It should use random probability, with lower chances during peak hours (e.g., 8-10 AM, 5-7 PM). If a cab is 'available', return a mock fare (e.g., '$15 - $25') and estimated travel time (e.g., '10-15 minutes'). Adjust fare and travel time based on peak hours and city characteristics (e.g., higher traffic in New York vs. a smaller town)."
    *   **Signature (as implemented):**
        ```python
        def get_cab_availability(time_str: str, city: str) -> dict: ...
        ```

*   **For `time_agent`'s tool:**
    *   **Prompt:** "Create a Python function `get_current_time(city: str)` that returns the current formatted time string for a given city. Use the `zoneinfo` module for IANA timezones. Support cities like New York (America/New_York), London (Europe/London), Tokyo (Asia/Tokyo), Paris (Europe/Paris), Delhi (Asia/Kolkata)."
    *   **Signature (as implemented):**
        ```python
        def get_current_time(city: str) -> dict: ...
        ```

*   **For `weather_agent`'s tool:**
    *   **Prompt:** "Develop a Python function `get_weather_forecast(city: str, time_str: str)` for dynamic mock weather.
        1.  Determine time of day (morning, noon, evening, night) from `time_str`.
        2.  Use a base temperature for each city and time of day.
        3.  Randomly select a weather category: 'pleasant' (70% chance), 'inconvenient' (e.g., light rain, windy, 20% chance), or 'severe' (e.g., heavy rain, snow, 10% chance).
        4.  Pick a specific condition string from the chosen category.
        5.  Adjust the base temperature slightly based on the condition.
        6.  Return the condition string and final temperature."
    *   **Signature (as implemented):**
        ```python
        def get_weather_forecast(city: str, time_str: str) -> dict: ...
        ```

Remember to also create the `Agent` instances for each sub-agent and for the main `root_agent`, configuring their `name`, `model`, `description`, `instruction`, and `tools` (for sub-agents) or `sub_agents` (for the root_agent) attributes. The `root_agent`'s instructions should guide it on how to coordinate these sub-agents.

## Interacting with the Multi-Agent System

Once you've set up the directory structure and implemented the agents:

1.  Navigate to the `02_multi_agents/step05/` directory in your terminal.
2.  Run the ADK web interface:
    ```bash
    adk web
    ```
3.  Interact with the `restaurant_finder_agent` (which is the `root_agent`):

    *   "I want to find an Italian restaurant in Paris for tonight around 8 PM. What's the weather like there now, and how easy is it to get a cab?"
    *   "Suggest a place for dinner in Tokyo. What's the local time?"
    *   "I'm looking for Indian food in London. Is it raining? How much would a cab cost?"
    *   "Find a local restaurant in Bengaluru open for lunch. Also, tell me the current time and weather."

Observe how the root agent now delegates tasks to the appropriate sub-agents and synthesizes their responses to provide comprehensive answers. This step showcases a more sophisticated and realistic agent architecture.
