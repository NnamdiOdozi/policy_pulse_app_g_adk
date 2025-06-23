import os
import json
import datetime
import uuid
from pathlib import Path

class SessionManager:
    """
    Manages chat sessions, including saving, loading, and creating new conversations
    """
    
    def __init__(self, sessions_dir="conversations"):
        """
        Initialize the session manager
        
        Parameters:
        sessions_dir (str): Directory to store session files
        """
        # Create sessions directory if it doesn't exist
        self.sessions_dir = Path(sessions_dir)
        self.sessions_dir.mkdir(exist_ok=True)
        
        # Initialize current session
        self.current_session = {
            "id": f"session_{uuid.uuid4().hex[:8]}",
            "name": None,
            "created_at": datetime.datetime.now().isoformat(),
            "last_updated": datetime.datetime.now().isoformat(),
            "messages": []
        }
    
    def save_session(self, session_name=None):
        """
        Save the current session to a file
        
        Parameters:
        session_name (str): Optional name for the session
        
        Returns:
        str: ID of the saved session
        """
        # Update session metadata
        if session_name:
            # Sanitize the session name to be safe for filenames
            safe_name = "".join([c for c in session_name if c.isalnum() or c in "_-"]).rstrip()
            if not safe_name:
                safe_name = f"session_{uuid.uuid4().hex[:8]}"
            self.current_session["name"] = session_name  # Original name for display
            self.current_session["id"] = safe_name  # Sanitized name for file
        else:
            # Keep existing ID if no name provided
            if "id" not in self.current_session:
                self.current_session["id"] = f"session_{uuid.uuid4().hex[:8]}"
                
        self.current_session["last_updated"] = datetime.datetime.now().isoformat()
        
        # Save to file
        session_id = self.current_session["id"]
        file_path = self.sessions_dir / f"{session_id}.json"
        
        # Ensure parent directory exists
        self.sessions_dir.mkdir(exist_ok=True, parents=True)
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.current_session, f, ensure_ascii=False, indent=2)
            print(f"Session saved successfully to {file_path}")
        except Exception as e:
            print(f"Error saving session: {e}")
            
        return session_id
    
    def load_session(self, session_id):
        """
        Load a session from a file
        
        Parameters:
        session_id (str): ID of the session to load
        
        Returns:
        bool: True if successful, False otherwise
        """
        file_path = self.sessions_dir / f"{session_id}.json"
        
        if not file_path.exists():
            return False
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.current_session = json.load(f)
            return True
        except Exception as e:
            print(f"Error loading session: {e}")
            return False
    
    def new_session(self):
        """
        Create a new empty session
        
        Returns:
        str: ID of the new session
        """
        self.current_session = {
            "id": f"session_{uuid.uuid4().hex[:8]}",
            "name": None,
            "created_at": datetime.datetime.now().isoformat(),
            "last_updated": datetime.datetime.now().isoformat(),
            "messages": []
        }
        return self.current_session["id"]
    
    def add_message(self, user_message, assistant_message):
        """
        Add a message exchange to the current session
        
        Parameters:
        user_message (str): Message from the user
        assistant_message (str): Response from the assistant
        """
        message_pair = {
            "timestamp": datetime.datetime.now().isoformat(),
            "user": user_message,
            "assistant": assistant_message
        }
        self.current_session["messages"].append(message_pair)
        self.current_session["last_updated"] = datetime.datetime.now().isoformat()
    
    def get_conversation_history(self):
        """
        Get the conversation history from the current session
        
        Returns:
        list: List of message exchanges
        """
        return self.current_session["messages"]
    
    def list_sessions(self):
        """
        List all available sessions
        
        Returns:
        list: List of session metadata
        """
        sessions = []
        for file_path in self.sessions_dir.glob("*.json"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    session = json.load(f)
                    # Create a summary with key information
                    summary = {
                        "id": session["id"],
                        "name": session["name"],
                        "created_at": session["created_at"],
                        "last_updated": session["last_updated"],
                        "message_count": len(session["messages"])
                    }
                    sessions.append(summary)
            except Exception as e:
                print(f"Error reading session {file_path}: {e}")
        
        # Sort by last updated timestamp (most recent first)
        sessions.sort(key=lambda x: x["last_updated"], reverse=True)
        return sessions
    
    def get_current_session_id(self):
        """
        Get the ID of the current session
        
        Returns:
        str: Current session ID
        """
        return self.current_session["id"]
    
    def get_session_name(self):
        """
        Get the name of the current session
        
        Returns:
        str: Current session name or ID if no name
        """
        return self.current_session.get("name") or self.current_session["id"]