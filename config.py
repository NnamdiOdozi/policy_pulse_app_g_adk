import os

class Config:
    # Search provider selection
    SEARCH_PROVIDER = os.getenv("SEARCH_PROVIDER", "tavily")
    
    # Tool configuration
    class Search:
        DEFAULT_RESULTS = 5
        TIMEOUT_SECONDS = 10
        ENABLE_CACHING = True