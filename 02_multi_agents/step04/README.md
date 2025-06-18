# Step 04: Enhanced Agent with Restaurant Finder Workflow

In this step, we significantly enhance our agent by equipping it with a suite of tools to help users find information about restaurants. This demonstrates a more complex workflow where the agent might need to use multiple tools or process information to answer user queries effectively.

## New Agent Capabilities

We've enhanced the agent's code with new methods (tools) to handle restaurant-related inquiries. These tools would allow the agent to:
*   Find restaurants based on criteria like city, cuisine, and mealtime.
*   Retrieve the menu for a specific restaurant.
*   Get the operating hours of a restaurant.

## Exercise: Implement the Tools

To make the agent fully functional for this step, you'll need to implement the following tool functions. We encourage you to use Gemini Code Assist to help you write the implementation for these!

Here are the suggested method signatures:

```python
# In your tools.py or a similar module

def find_restaurants(city: str, cuisine: str = "any", meal: str = "any") -> list:
    """
    Finds restaurants in a given city, optionally filtering by cuisine and mealtime.
    Returns a list of restaurant names or a list of dictionaries with restaurant details.
    (Example: [{'name': 'Restaurant A', 'cuisine': 'Italian'}, {'name': 'Restaurant B', 'cuisine': 'Mexican'}])
    """
    # TODO: Implement this function.
    # You can use a mock dataset or call a real API.
    # Remember to handle cases where no restaurants are found.
    pass

def get_restaurant_menu(restaurant_name: str, city: str) -> dict:
    """
    Retrieves the menu for a specific restaurant in a given city.
    Returns a dictionary representing the menu.
    (Example: {'appetizers': ['Salad', 'Soup'], 'main_courses': ['Pasta', 'Steak']})
    """
    # TODO: Implement this function.
    # You can use a mock dataset or call a real API.
    pass

def get_restaurant_hours(restaurant_name: str, city: str) -> str:
    """
    Gets the operating hours for a specific restaurant in a given city.
    Returns a string describing the hours (e.g., "Mon-Fri: 9 AM - 10 PM, Sat-Sun: 10 AM - 11 PM").
    """
    # TODO: Implement this function.
    # You can use a mock dataset or call a real API.
    pass
```

Don't forget to import these functions and add them to the `tools` list in your agent's configuration.

## Interacting with the Agent

Once you've implemented and integrated these tools, you can start the agent by navigating to this directory in your terminal and running:

```bash
adk web
```

This will start the ADK web interface. Given the new tools, you can now ask the agent questions like: 
+ "Find Italian restaurants in San Francisco for dinner." 
+ "What's on the menu at 'The Cozy Corner Cafe' in London?" 
+ "Is 'Burger Central' in New York open now?" 
+ "Can you suggest some places to eat Mexican food right now in Delhi?" 
+ "Tell me about restaurants in Paris." 

Observe how the agent uses the tools you've implemented to respond to your queries. Experiment with different prompts to see how it handles various scenarios!

