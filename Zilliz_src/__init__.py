from . import doc_processor, indexer, search, client_factory

import sys
import os

# Add project root to Python path
current_dir = os.path.dirname(__file__)
project_root = os.path.join(current_dir, '..')
sys.path.insert(0, os.path.abspath(project_root))

__all__ = ['indexer', 'doc_processor', 'search', 'client_factory']