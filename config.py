# This file is yet to be tested or used and is haphazard at the moment. Do not make any reliances or assumptions about it!!! For example there are some endpoints that are only listed in the base config and not in other configs. The idea is a central config file that we can use to set config parameters for different parts of the systme and different stages of the 
# project eg development, testing and production. The paramaters set here are yet to be imported into the different project .

import os
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Load environment variables based on environment
def load_environment():
    """Load appropriate .env file based on ENVIRONMENT setting"""
    env = os.getenv("ENVIRONMENT", "development")
    
    # Load base .env first
    load_dotenv(override=False)
    
    # Load environment-specific .env file if it exists
    env_files = {
        "development": ".env.dev",
        "test": ".env.test", 
        "production": ".env.prod"
    }
    
    if env in env_files:
        env_file = env_files[env]
        if os.path.exists(env_file):
            load_dotenv(env_file, override=True)
            print(f"Loaded environment config: {env_file}")
        else:
            print(f"Environment file {env_file} not found, using base .env")
    
    return env

# Load environment on import
CURRENT_ENVIRONMENT = load_environment()

class BaseConfig:
    """Base configuration class with all environment variables"""
    
    # Environment
    ENVIRONMENT = CURRENT_ENVIRONMENT
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    
    # API Keys - All centralized here
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    PINECONE_API_KEY = os.getenv("PINECONE_API_KEY") 
    SONAR_API_KEY = os.getenv("SONAR_API_KEY")
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
    EXA_API_KEY = os.getenv("EXA_API_KEY")
    SERPAPI_KEY = os.getenv("SERPAPI_KEY")
    AGENTOPS_API_KEY = os.getenv("AGENTOPS_API_KEY")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL")
    DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
    DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    DB_POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "240"))
    
    # Vector Database (Pinecone)
    PINECONE_ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT", "us-east-1-aws")
    PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "policy-pulse-index")
    
    # Search Configuration
    SEARCH_PROVIDER = os.getenv("SEARCH_PROVIDER", "tavily")
    
    # Application Settings
    APP_NAME = "policy_pulse_app"
    DEFAULT_USER_ID = "default_user"
    
    # Security
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    SESSION_TIMEOUT = int(os.getenv("SESSION_TIMEOUT", "3600"))  # 1 hour
    
    # Google Services
    GOOGLE_GENAI_USE_VERTEXAI = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "FALSE")

    # Embedding and Vector DB Indexing
    ZILLIZ_CLOUD_URI="https://in03-768dd5416cd6745.serverless.aws-eu-central-1.cloud.zilliz.com"
    ZILLIZ_COLLECTION_NAME = "docs_voyage_3_large"

    # Validation
    @classmethod
    def validate_required_keys(cls) -> list:
        """Validate that required environment variables are set"""
        required_keys = [
            "GOOGLE_API_KEY",
            "DATABASE_URL", 
            "PINECONE_API_KEY",
            "TAVILY_API_KEY"
        ]
        
        missing_keys = []
        for key in required_keys:
            if not getattr(cls, key):
                missing_keys.append(key)
        
        return missing_keys

class DevelopmentConfig(BaseConfig):
    """Development environment configuration"""
    DEBUG = True
    
    # Tool configuration for development
    class Search:
        DEFAULT_RESULTS = 3  # Fewer results for faster dev testing
        TIMEOUT_SECONDS = 10
        ENABLE_CACHING = False  # Disable caching for fresh results during dev
        
        # Tavily settings for development
        TAVILY_FAQ_CHAR_LIMIT = 300  # Shorter for dev testing
        TAVILY_REPORT_CHAR_LIMIT = 2000
        TAVILY_DEFAULT_DEPTH = "basic"
        
        # Exa settings for development  
        EXA_MAX_CHARACTERS = 500
        EXA_CONTENT_LIMIT = 300
        
    # Database settings for development
    DB_POOL_SIZE = 3
    DB_MAX_OVERFLOW = 5
    LOG_SQL_QUERIES = True
    
    # AI/Agent settings for development
    MODEL_TEMPERATURE = 0.1
    MAX_TOKENS = 1000
    ENABLE_AGENT_LOGGING = True

class TestConfig(BaseConfig):
    """Test environment configuration"""
    DEBUG = True
    TESTING = True
    
    # Tool configuration for testing
    class Search:
        DEFAULT_RESULTS = 2  # Minimal results for fast tests
        TIMEOUT_SECONDS = 5
        ENABLE_CACHING = False
        
        # Tavily settings for testing
        TAVILY_FAQ_CHAR_LIMIT = 200  # Very short for test speed
        TAVILY_REPORT_CHAR_LIMIT = 1000
        TAVILY_DEFAULT_DEPTH = "basic"
        
        # Exa settings for testing
        EXA_MAX_CHARACTERS = 300
        EXA_CONTENT_LIMIT = 200
        
    # Database settings for testing
    DB_POOL_SIZE = 2
    DB_MAX_OVERFLOW = 2
    LOG_SQL_QUERIES = True
    
    # AI/Agent settings for testing
    MODEL_TEMPERATURE = 0.0  # Deterministic for testing
    MAX_TOKENS = 500
    ENABLE_AGENT_LOGGING = True
    
    # Override with test database if available
    DATABASE_URL = os.getenv("TEST_DATABASE_URL", BaseConfig.DATABASE_URL)

class ProductionConfig(BaseConfig):
    """Production environment configuration"""
    DEBUG = False
    
    # Tool configuration for production
    class Search:
        DEFAULT_RESULTS = 5  # Standard results for production
        TIMEOUT_SECONDS = 15  # Longer timeout for reliability
        ENABLE_CACHING = True
        
        # Tavily settings for production
        TAVILY_FAQ_CHAR_LIMIT = 500  # Standard limits
        TAVILY_REPORT_CHAR_LIMIT = 5000
        TAVILY_DEFAULT_DEPTH = "basic"
        
        # Exa settings for production
        EXA_MAX_CHARACTERS = 1000
        EXA_CONTENT_LIMIT = 500
        
    # Database settings for production
    DB_POOL_SIZE = 10  # Higher for production load
    DB_MAX_OVERFLOW = 20
    LOG_SQL_QUERIES = False  # Disable for performance
    
    # AI/Agent settings for production
    MODEL_TEMPERATURE = 0.3
    MAX_TOKENS = 2000
    ENABLE_AGENT_LOGGING = False  # Disable verbose logging
    
    # Security settings for production
    REQUIRE_HTTPS = True
    SESSION_TIMEOUT = 1800  # 30 minutes

# Configuration factory
def get_config() -> BaseConfig:
    """Get configuration class based on environment"""
    env = CURRENT_ENVIRONMENT.lower()
    
    config_map = {
        "development": DevelopmentConfig,
        "test": TestConfig,
        "production": ProductionConfig
    }
    
    config_class = config_map.get(env, DevelopmentConfig)
    return config_class()

# Global configuration instance
config = get_config()

# Validate configuration on import
missing_keys = config.validate_required_keys()
if missing_keys:
    print(f"WARNING: Missing required environment variables: {missing_keys}")
    if CURRENT_ENVIRONMENT == "production":
        raise RuntimeError(f"Missing required environment variables in production: {missing_keys}")

# Export commonly used values for backward compatibility
SEARCH_PROVIDER = config.SEARCH_PROVIDER
DEFAULT_RESULTS = config.Search.DEFAULT_RESULTS
TIMEOUT_SECONDS = config.Search.TIMEOUT_SECONDS
ENABLE_CACHING = config.Search.ENABLE_CACHING