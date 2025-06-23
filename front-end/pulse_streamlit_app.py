import streamlit as st
import asyncio
import sys
import os
from datetime import datetime

from dotenv import load_dotenv
load_dotenv(override=True)  # This must happen FIRST

st.set_page_config(
    page_title="Policy Pulse Agent",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'About': "Policy Pulse Agent v1.0"
    }
)

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from auth import authenticate_user, create_user, hash_password
from session_utils import get_user_conversations, save_conversation, create_new_session, get_conversation_messages, delete_conversation
from agents.policy_pulse_agent.agent import root_agent, runner, session_service
from google.genai import types

def init_session_state():
    """Initialize Streamlit session state"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None
    if 'username' not in st.session_state:
        st.session_state.username = None
    if 'current_session_id' not in st.session_state:
        st.session_state.current_session_id = None
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'conversations' not in st.session_state:
        st.session_state.conversations = []

def login_page():
    """Display login/signup page"""
    st.title("🏥 Policy Pulse Agent")
    st.subheader("AI Assistant for Workplace Reproductive & Fertility Health Policies")
    
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    
    with tab1:
        st.subheader("Login")
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            login_submit = st.form_submit_button("Login")
            
            if login_submit:
                user = authenticate_user(email, password)
                if user:
                    st.session_state.authenticated = True
                    st.session_state.user_id = user['user_id']
                    st.session_state.username = user['username']
                    st.success(f"Welcome back, {user['username']}!")
                    st.rerun()
                else:
                    st.error("Invalid email or password")
    
    with tab2:
        st.subheader("Sign Up")
        with st.form("signup_form"):
            username = st.text_input("Username")
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            confirm_password = st.text_input("Confirm Password", type="password")
            signup_submit = st.form_submit_button("Sign Up")
            
            if signup_submit:
                if password != confirm_password:
                    st.error("Passwords don't match")
                elif len(password) < 6:
                    st.error("Password must be at least 6 characters")
                elif create_user(username, email, password):
                    st.success("Account created successfully! Please login.")
                else:
                    st.error("Failed to create account. Email might already exist.")

def load_conversations():
    """Load user's conversations"""
    conversations = get_user_conversations(st.session_state.user_id)
    st.session_state.conversations = conversations

def start_new_conversation():
    """Start a new conversation"""
    session_id = create_new_session(st.session_state.user_id)
    st.session_state.current_session_id = session_id
    st.session_state.messages = []
    st.rerun()

def load_conversation(session_id: str):
    """Load a conversation by session ID."""
    st.session_state.current_session_id = session_id
    
    # Get messages for this session
    messages = get_conversation_messages(st.session_state.user_id, session_id)
    
    # Clear and repopulate the messages
    st.session_state.messages = []
    
    for msg in messages:
        # Handle assistant messages that have parts structure
        if msg["role"] == "assistant" and isinstance(msg["content"], dict) and "parts" in msg["content"]:
            # Extract text from parts
            text_parts = []
            for part in msg["content"]["parts"]:
                if "text" in part:
                    text_parts.append(part["text"])
            content = "\n".join(text_parts)
        else:
            content = msg["content"]
        
        st.session_state.messages.append({
            "role": msg["role"],
            "content": content
        })
    
    st.rerun()

async def get_agent_response(user_message):
    """Get response from the agent"""
    try:
        message_content = types.Content(
            role='user',
            parts=[types.Part(text=user_message)]
        )
        
        response_text = ""
        async for event in runner.run_async(
            user_id=st.session_state.user_id,
            session_id=st.session_state.current_session_id,
            new_message=message_content
        ):
            if hasattr(event, 'content') and hasattr(event.content, 'parts'):
                for part in event.content.parts:
                    if hasattr(part, 'text') and part.text is not None:
                        response_text += part.text
        
        # Return only the text content, not a structured object
        return response_text if response_text else "I'm sorry, I couldn't generate a response."
    except Exception as e:
        return f"Error: {str(e)}"

def chat_interface():
    """Main chat interface"""
    st.title("🏥 Policy Pulse Agent")
    
    # Sidebar for conversations
    with st.sidebar:
        st.subheader(f"Welcome, {st.session_state.username}!")
        
        if st.button("🆕 New Conversation", use_container_width=True):
            start_new_conversation()
        
        if st.button("🔄 Refresh Conversations", use_container_width=True):
            load_conversations()
        
        if st.button("🚪 Logout", use_container_width=True):
            for key in st.session_state.keys():
                del st.session_state[key]
            st.rerun()
        
        st.divider()
        st.subheader("Previous Conversations")
        
        if st.session_state.conversations:
            for conv in st.session_state.conversations:
                # Use first 50 chars as title
                title = conv['title'][:50] + "..." if len(conv['title']) > 50 else conv['title']
                
                # Create columns for button and delete icon
                col1, col2 = st.columns([5, 1])
                
                with col1:
                    if st.button(
                        f"💬 {title}",
                        key=f"conv_{conv['session_id']}",
                        use_container_width=True
                    ):
                        load_conversation(conv['session_id'])
                
                with col2:
                    if st.button(
                        "🗑️",
                        key=f"del_{conv['session_id']}",
                        help="Delete this conversation",
                        use_container_width=True
                    ):
                        if delete_conversation(st.session_state.user_id, conv['session_id']):
                            st.success("Conversation deleted")
                            load_conversations()
                            st.rerun()
                        else:
                            st.error("Failed to delete conversation")
        else:
            st.write("No previous conversations")
    
    # Main chat area
    if not st.session_state.current_session_id:
        st.info("👈 Start a new conversation to begin chatting!")
        return
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            content = message["content"]
            
            # Handle content that might still be in parts format
            if isinstance(content, dict) and "parts" in content:
                # Extract text from parts
                text_parts = []
                for part in content["parts"]:
                    if "text" in part:
                        text_parts.append(part["text"])
                content = "\n".join(text_parts)
            
            st.markdown(content)
    
    # Chat input
    if prompt := st.chat_input("Ask about reproductive & fertility health policies..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Get agent response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = asyncio.run(get_agent_response(prompt))
                st.markdown(response)
                
        # Add assistant message
        st.session_state.messages.append({"role": "assistant", "content": response})
        
        # Auto-save conversation
        if len(st.session_state.messages) == 2:  # First exchange
            # Create title from first user message
            title = prompt[:100]
            save_conversation(
                st.session_state.user_id,
                st.session_state.current_session_id,
                title
            )
        
        # Refresh conversations list
        load_conversations()

def main():
    init_session_state()
    
    if not st.session_state.authenticated:
        login_page()
    else:
        if not st.session_state.conversations:
            load_conversations()
        chat_interface()

if __name__ == "__main__":
    main()