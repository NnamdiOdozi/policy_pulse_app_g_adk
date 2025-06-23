from . import agent

import sys
import os

# Add project root to Python path
current_dir = os.path.dirname(__file__)
project_root = os.path.join(current_dir, '..' , '..')
sys.path.insert(0, os.path.abspath(project_root))

# Now absolute imports will work
from src_pulse.ai_agent import retrieve_relevant_chunks
from .agent import root_agent, runner