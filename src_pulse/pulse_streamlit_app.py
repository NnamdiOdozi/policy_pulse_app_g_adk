import streamlit as st
import os
import datetime
import json
from pathlib import Path
import uuid
import pandas as pd
import time

# Import your RAG functionality
import sys
sys.path.append(".")  # Ensure local imports work
from .ai_agent import answer_question, retrieve_relevant_chunks, get_system_prompt
from .session_manager import SessionManager

# Set page configuration
st.set_page_config(
    page_title="Policy Pulse - Reproductive Health Compliance Assistant",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Authentication token - in production you would use an environment variable
# In a more secure setup, store this in an environment variable:
# ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN", "default_token_for_development")
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN") # Change this to your desired token

# Initialize ALL session state variables - make this comprehensive
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_manager" not in st.session_state:
    st.session_state.session_manager = SessionManager()
if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = st.session_state.session_manager.get_current_session_id()
if "retrieved_chunks" not in st.session_state:
    st.session_state.retrieved_chunks = []
if "current_query" not in st.session_state:
    st.session_state.current_query = ""
if "needs_processing" not in st.session_state:
    st.session_state.needs_processing = False
if "user_input" not in st.session_state:
    st.session_state.user_input = ""

# Pinecone configuration (in production, use environment variables)
index_name = "policypulse"  # Your Pinecone index name
api_key = os.environ.get("PINECONE_API_KEY")  # Your Pinecone API key

# Authentication page
def show_auth_page():
    st.title("🌱 Policy Pulse")
    st.subheader("Reproductive Health Compliance Assistant")
    
    # Use a unique, static key for the text input
    token = st.text_input("Enter access token:", type="password", key="auth_token_input")
    
    # Use a button outside the form (simpler approach)
    if st.button("Login", key="auth_submit_button"):
        if token == ACCESS_TOKEN:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Invalid token. Please try again.")

# Function to save messages to the session manager
def save_messages():
    # Only save if we have messages
    if not st.session_state.messages:
        return
        
    # Create conversation pairs for the session manager
    for i in range(0, len(st.session_state.messages), 2):
        if i+1 < len(st.session_state.messages):
            user_msg = st.session_state.messages[i]["content"]
            assistant_msg = st.session_state.messages[i+1]["content"]
            
            # Check if this exchange is already in the session manager
            existing_messages = st.session_state.session_manager.get_conversation_history()
            if len(existing_messages) <= i // 2:  # This is a new exchange
                st.session_state.session_manager.add_message(user_msg, assistant_msg)
    
    # Save the session
    st.session_state.session_manager.save_session()

# Function to handle chat input
# Define callback for when input changes
def on_input_change():
    """Callback that runs when chat input value changes"""
    if "user_input" in st.session_state and st.session_state.user_input.strip():
        # Store the value in a different session state variable
        st.session_state.current_query = st.session_state.user_input.strip()
        # Set a flag instead of directly processing input
        st.session_state.needs_processing = True
        # DON'T call process_input here

# Function to process user input
def process_input(user_input):
    """Process user input - commands or questions"""
    # Handle commands
    if user_input.startswith("/"):
        parts = user_input[1:].split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        # Process commands
        if command == "new":
            st.session_state.session_manager.new_session()
            st.session_state.current_session_id = st.session_state.session_manager.get_current_session_id()
            st.session_state.messages = []
            st.session_state.retrieved_chunks = []
            st.info(f"Started new conversation. Session ID: {st.session_state.current_session_id}")
            st.rerun()
        
        elif command == "save":
            session_name = args.strip() if args else None
            session_id = st.session_state.session_manager.save_session(session_name)
            name_display = f" as '{session_name}'" if session_name else ""
            st.info(f"Conversation saved{name_display}. Session ID: {session_id}")
        
        elif command == "load":
            session_id = args.strip()
            if not session_id:
                st.error("Please specify a session ID or name to load.")
                return
            
            success = st.session_state.session_manager.load_session(session_id)
            if success:
                st.session_state.current_session_id = st.session_state.session_manager.get_current_session_id()
                history = st.session_state.session_manager.get_conversation_history()
                
                # Convert history to messages
                st.session_state.messages = []
                for exchange in history:
                    st.session_state.messages.append({"role": "user", "content": exchange["user"]})
                    st.session_state.messages.append({"role": "assistant", "content": exchange["assistant"]})
                
                st.info(f"Loaded conversation: {st.session_state.session_manager.get_session_name()}")
                st.rerun()
            else:
                st.error(f"Could not load session '{session_id}'.")
        
        elif command == "help":
            help_text = (
                "Available commands:\n"
                "/new - Start a new conversation\n"
                "/save [name] - Save current conversation with optional name\n"
                "/load [id|name] - Load a specific conversation\n"
                "/list - Show available saved conversations\n"
                "/help - Show this help message"
            )
            st.info(help_text)
        
        elif command == "list":
            sessions = st.session_state.session_manager.list_sessions()
            if not sessions:
                st.info("No saved conversations found.")
            else:
                sessions_df = pd.DataFrame([
                    {
                        "ID/Name": s["name"] or s["id"],
                        "Messages": s["message_count"],
                        "Created": s["created_at"].split("T")[0],
                        "Last Updated": s["last_updated"].split("T")[0]
                    } for s in sessions
                ])
                st.table(sessions_df)
        
        else:
            st.error(f"Unknown command: {command}. Type /help for available commands.")
    
    else:
        # Regular question - add user message
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        # Create a placeholder for the assistant's response
        with st.chat_message("assistant"):
            thinking_placeholder = st.empty()
            thinking_placeholder.text("Thinking...")
            
            # Process the question
            # 1. Retrieve chunks
            try:
                with st.spinner("Searching for relevant information..."):
                    retrieved_chunks = retrieve_relevant_chunks(user_input, index_name, api_key, top_k=5)
                    st.session_state.retrieved_chunks = retrieved_chunks
                
                # 2. Generate answer
                with st.spinner("Generating response..."):
                    conversation_history = st.session_state.session_manager.get_conversation_history()
                    response = answer_question(
                        user_input, 
                        index_name, 
                        api_key, 
                        conversation_history=conversation_history
                    )
                
                # Add assistant message
                thinking_placeholder.empty()
                st.session_state.messages.append({"role": "assistant", "content": response})
                thinking_placeholder.markdown(response)  # Use markdown instead of write for better formatting
                
                # Save the conversation
                st.session_state.session_manager.add_message(user_input, response)
                
            except Exception as e:
                thinking_placeholder.error(f"Error processing your question: {str(e)}")
                # You may want to log the full error details somewhere
                import traceback
                print(f"Error in process_input: {traceback.format_exc()}")
    
    # Force a rerun to update the UI
    #st.rerun()

# Main chat interface
def show_chat_interface():
    # Sidebar for session management and settings
    with st.sidebar:
        st.title("🌱 Policy Pulse")
        st.caption("Reproductive Health Compliance Assistant")
        
        # Show current session info
        st.subheader("Current Session")
        st.text(f"ID: {st.session_state.current_session_id}")
        
        # Session management options
        if st.button("New Conversation"):
            st.session_state.session_manager.new_session()
            st.session_state.current_session_id = st.session_state.session_manager.get_current_session_id()
            st.session_state.messages = []
            st.session_state.retrieved_chunks = []
            st.rerun()
        
        # Name and save session
        with st.expander("Save Conversation"):
            session_name = st.text_input("Session Name (optional):")
            if st.button("Save"):
                session_id = st.session_state.session_manager.save_session(session_name)
                st.success(f"Saved as: {session_id}")
        
        # Load session
        with st.expander("Load Conversation"):
            sessions = st.session_state.session_manager.list_sessions()
            if sessions:
                session_options = {s["name"] or s["id"]: s["id"] for s in sessions}
                selected_session = st.selectbox("Select a conversation:", list(session_options.keys()))
                
                if st.button("Load"):
                    success = st.session_state.session_manager.load_session(session_options[selected_session])
                    if success:
                        st.session_state.current_session_id = st.session_state.session_manager.get_current_session_id()
                        history = st.session_state.session_manager.get_conversation_history()
                        
                        # Convert history to messages
                        st.session_state.messages = []
                        for exchange in history:
                            st.session_state.messages.append({"role": "user", "content": exchange["user"]})
                            st.session_state.messages.append({"role": "assistant", "content": exchange["assistant"]})
                        
                        st.rerun()
                    else:
                        st.error("Failed to load session.")
            else:
                st.info("No saved conversations found.")
        
        # Help section
        with st.expander("Help"):
            st.markdown("""
            **Available Commands:**
            - `/new` - Start a new conversation
            - `/save [name]` - Save current conversation
            - `/load [id|name]` - Load a specific conversation
            - `/list` - Show available saved conversations
            - `/help` - Show help message
            """)
        
        # Logout option
        if st.button("Logout"):
            st.session_state.authenticated = False
            st.rerun()
    
    # Main chat area - Create a 2-column layout
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Chat header
        st.header("Reproductive & Fertility Health Compliance Assistant")
        st.caption("Ask questions about workplace reproductive health policies and compliance")
        
        # Display chat messages
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.write(message["content"])
        
        # Chat input
        st.chat_input(
            "Ask a question about reproductive health policies...", 
            key="user_input", 
            on_submit=on_input_change
        )
    
    with col2:
        # Evidence panel
        st.subheader("Supporting Evidence")
        
        if st.session_state.retrieved_chunks:
            for i, chunk in enumerate(st.session_state.retrieved_chunks):
                with st.expander(f"Document {i+1}: {chunk['id'][:30]}..."):
                    st.markdown(f"**Score:** {chunk['score']:.4f}")
                    st.markdown(f"**Content:**\n{chunk['text']}")
        else:
            st.info("Ask a question to see supporting evidence from our knowledge base.")

# Main app logic
def main():
    if not st.session_state.authenticated:
        show_auth_page()
    else:
        show_chat_interface()

    # Process any pending input from the callback
    if st.session_state.get("needs_processing", False):
        process_input(st.session_state.current_query)
        st.session_state.needs_processing = False
        st.rerun()    

if __name__ == "__main__":
    main()