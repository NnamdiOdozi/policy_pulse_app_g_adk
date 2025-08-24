import streamlit as st
import asyncio
import sys
import os
import json
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

# NEW IMPORTS - Add these for the enhanced functionality
from document_processor import extract_text_from_upload, summarize_document_if_needed
from template_manager import PolicyTemplateManager
from dynamic_sections import generate_dynamic_template
from word_generator import generate_policy_word_doc
import re

def show_landing_page():
    """Display the landing page"""
    import streamlit.components.v1 as components
    
    # Read the HTML file
    html_path = os.path.join(os.path.dirname(__file__), "static", "Landing_page.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    # Modify the CTA button to redirect to login
    html_content = html_content.replace(
        'href="mailto:nnamdi.odozi@we-are-eden.com?subject=LMF%20Awards%20Follow-Up:%20PolicyPulse%20Demo%20Request"',
        'href="#" onclick="document.getElementById(\'get-started-btn\').click(); return false;"'
    )
    html_content = html_content.replace(
        'Request a 15-Min PolicyPulse™ Demo',
        'Get Started with PolicyPulse™'
    )
    
    # Display the HTML
    components.html(html_content, height=2000, scrolling=True)
    
    # Add a hidden button that Streamlit can detect
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("Get Started with PolicyPulse™", key="get-started-btn", type="primary", use_container_width=True):
            st.session_state.show_login = True
            st.rerun()


def init_session_state():
    """Initialize Streamlit session state"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'show_login' not in st.session_state:
        st.session_state.show_login = False    
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
    
    # NEW SESSION STATE VARIABLES - Add these for enhanced functionality
    if 'template_manager' not in st.session_state:
        st.session_state.template_manager = PolicyTemplateManager()
    if 'in_questionnaire' not in st.session_state:
        st.session_state.in_questionnaire = False
    if 'questionnaire_data' not in st.session_state:
        st.session_state.questionnaire_data = {}
    if 'uploaded_docs' not in st.session_state:
        st.session_state.uploaded_docs = []
    if 'questionnaire_step' not in st.session_state:
        st.session_state.questionnaire_step = 0
    if 'questionnaire_complete' not in st.session_state:
        st.session_state.questionnaire_complete = False

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
    # Reset questionnaire state
    st.session_state.in_questionnaire = False
    st.session_state.questionnaire_data = {}
    st.session_state.uploaded_docs = []
    st.session_state.questionnaire_step = 0
    st.session_state.questionnaire_complete = False
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
    
    # Reset questionnaire state when loading conversation
    st.session_state.in_questionnaire = False
    st.session_state.questionnaire_data = {}
    st.session_state.uploaded_docs = []
    st.session_state.questionnaire_step = 0
    st.session_state.questionnaire_complete = False
    
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

# NEW FUNCTIONS - Add these for enhanced functionality
def show_document_uploader():
    """Show document uploader in sidebar during questionnaire"""
    if st.session_state.in_questionnaire:
        st.sidebar.markdown("### Document Upload")
        st.sidebar.markdown("Upload existing policies for reference or refinement:")
        
        uploaded_files = st.sidebar.file_uploader(
            "Choose files",
            type=['docx', 'pdf', 'txt'],
            accept_multiple_files=True,
            key="policy_uploader"
        )
        
        if uploaded_files:
            st.session_state.uploaded_docs = []
            for file in uploaded_files:
                try:
                    text = extract_text_from_upload(file)
                    text, was_summarized = summarize_document_if_needed(text)
                    st.session_state.uploaded_docs.append({
                        'filename': file.name,
                        'content': text,
                        'was_summarized': was_summarized
                    })
                    st.sidebar.success(f"✅ {file.name} processed")
                    if was_summarized:
                        st.sidebar.warning("⚠️ Document was summarized due to length")
                except Exception as e:
                    st.sidebar.error(f"❌ Error processing {file.name}: {str(e)}")

def detect_complete_policy_document(response):
    """FIXED: Only detect actual complete policy documents, not meta-commentary"""
    
    # Must have substantial content (not just meta-commentary)
    if len(response) < 1500:
        return False
    
    # Must NOT contain meta-commentary phrases
    meta_phrases = [
        "Here is the draft",
        "Key points for your review:",
        "[Policy text as drafted above]",
        "Please review and let me know",
        "Any revisions or specific formatting preferences?",
        "To ensure I tailor the document precisely",
        "What type of document do you need:",
        "What's the main focus:",
        "Which specific areas should be covered?"
    ]
    
    for phrase in meta_phrases:
        if phrase in response:
            return False
    
    # Must contain multiple numbered sections with actual content
    numbered_sections = len(re.findall(r'^\d+\.', response, re.MULTILINE))
    if numbered_sections < 3:
        return False
    
    # Must contain policy-like structure
    policy_indicators = [
        'POLICY' in response.upper(),
        'Purpose' in response or 'Scope' in response,
        'Version' in response or 'v1.0' in response.lower()
    ]
    
    return sum(policy_indicators) >= 2

def check_policy_request(user_input):
    """Check if user is requesting a policy document"""
    policy_keywords = ['policy', 'guide', 'guidelines', 'procedure']
    action_keywords = ['draft', 'create', 'write', 'generate', 'develop', 'build']
    
    has_policy_keyword = any(keyword in user_input.lower() for keyword in policy_keywords)
    has_action_keyword = any(keyword in user_input.lower() for keyword in action_keywords)
    
    return has_policy_keyword and has_action_keyword

def should_generate_policy(response):
    """Check if the questionnaire is complete and should trigger policy generation"""
    
    # Must be in questionnaire mode
    if not st.session_state.in_questionnaire:
        return False
    
    # Ensure response is a string
    if not isinstance(response, str):
        return False
    
    # Check if questionnaire appears complete based on response content
    completion_indicators = [
        "no i don't have any existing policies",
        "do you have any existing policies", 
        "upload for reference or refinement",
        "existing policies or documents to upload"
    ]
    
    # Convert response to lowercase once
    response_lower = response.lower()
    
    # If response indicates final question was asked/answered
    if any(indicator in response_lower for indicator in completion_indicators):
        st.session_state.questionnaire_complete = True
        return True
    
    return False

async def generate_and_send_template():
    """Generate dynamic template and send to agent"""
    
    try:
        # Add current date to responses
        st.session_state.questionnaire_data['created_date'] = datetime.now().strftime('%B %d, %Y')
        
        # Generate dynamic template
        dynamic_template = generate_dynamic_template(st.session_state.questionnaire_data)
        
        # Create template message for the agent
        template_message = f"""DYNAMIC_TEMPLATE:
{json.dumps(dynamic_template, indent=2)}

User Requirements Summary:
- Document Type: {st.session_state.questionnaire_data.get('document_type', 'policy')}
- Policy Focus: {st.session_state.questionnaire_data.get('policy_focus', 'comprehensive')}
- Coverage Areas: {st.session_state.questionnaire_data.get('coverage_areas', [])}
- Detail Level: {st.session_state.questionnaire_data.get('detail_level', 'standard')}

Uploaded Documents Context:
{chr(10).join([f"- {doc['filename']}: {doc['content'][:500]}..." for doc in st.session_state.uploaded_docs]) if st.session_state.uploaded_docs else "No documents uploaded"}

Please generate the complete policy document following the template structure above."""
        
        # Send to agent
        response = await get_agent_response(template_message)
        
        # Save template
        try:
            template_name = st.session_state.template_manager.generate_template_name(
                st.session_state.questionnaire_data
            )
            st.session_state.template_manager.save_template(
                template_name,
                st.session_state.questionnaire_data,
                dynamic_template
            )
            st.success(f"✅ Template saved as: {template_name}")
        except Exception as e:
            st.warning(f"Could not save template: {str(e)}")
        
        return response
        
    except Exception as e:
        return f"Error generating policy: {str(e)}"

def show_questionnaire_progress():
    """Show questionnaire progress in sidebar"""
    if st.session_state.in_questionnaire:
        st.sidebar.markdown("### Policy Generation Progress")
        
        steps = [
            "Document Type",
            "Policy Focus", 
            "Coverage Areas",
            "Detail Level",
            "Additional Context"
        ]
        
        current_step = st.session_state.questionnaire_step
        
        for i, step in enumerate(steps):
            if i < current_step:
                st.sidebar.markdown(f"✅ {step}")
            elif i == current_step:
                st.sidebar.markdown(f"🔄 {step} (current)")
            else:
                st.sidebar.markdown(f"⏳ {step}")
        
        # Show collected data
        if st.session_state.questionnaire_data:
            st.sidebar.markdown("### Responses So Far")
            for key, value in st.session_state.questionnaire_data.items():
                st.sidebar.markdown(f"**{key.replace('_', ' ').title()}:** {value}")

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
        
        # Show document uploader if in questionnaire
        show_document_uploader()
        
        # Show questionnaire progress
        show_questionnaire_progress()
        
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
        # Check if this is a policy request and we're not already in questionnaire
        if check_policy_request(prompt) and not st.session_state.in_questionnaire:
            st.session_state.in_questionnaire = True
            st.session_state.questionnaire_step = 0
            st.session_state.questionnaire_data = {}
            st.session_state.questionnaire_complete = False
        
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Get agent response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                # Check if questionnaire is complete and should generate policy
                if st.session_state.in_questionnaire:
                    response = asyncio.run(get_agent_response(prompt))
                    
                    # Check if questionnaire is now complete
                    if should_generate_policy(response):
                        st.markdown(response)  # Show final questionnaire response
                        
                        # Add to messages
                        st.session_state.messages.append({"role": "assistant", "content": response})
                        
                        # Generate policy using dynamic template
                        with st.spinner("Generating your policy document..."):
                            policy_response = asyncio.run(generate_and_send_template())
                        
                        # Display policy and download button
                        st.markdown("---")
                        st.markdown(policy_response)
                        
                        # Check if it's a complete policy
                        if detect_complete_policy_document(policy_response):
                            st.markdown("---")
                            try:
                                word_buffer = generate_policy_word_doc(policy_response)
                                
                                col1, col2, col3 = st.columns([1, 2, 1])
                                with col2:
                                    st.download_button(
                                        label="📄 Download Policy as Word Document",
                                        data=word_buffer.getvalue(),
                                        file_name=f"policy_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx",
                                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                        use_container_width=True
                                    )
                            except Exception as e:
                                st.error(f"Error generating Word document: {str(e)}")
                        
                        # Add policy to messages
                        st.session_state.messages.append({"role": "assistant", "content": policy_response})
                        
                        # Reset questionnaire state
                        st.session_state.in_questionnaire = False
                        st.session_state.questionnaire_data = {}
                        st.session_state.uploaded_docs = []
                        st.session_state.questionnaire_step = 0
                        st.session_state.questionnaire_complete = False
                    else:
                        # Regular questionnaire response
                        st.markdown(response)
                        st.session_state.messages.append({"role": "assistant", "content": response})
                else:
                    # Not in questionnaire - regular response
                    response = asyncio.run(get_agent_response(prompt))
                    
                    # Check if this is a complete policy (from non-questionnaire generation)
                    is_complete_policy = detect_complete_policy_document(response)
                    
                    if is_complete_policy:
                        st.markdown(response)
                        # Add download button for non-questionnaire policies
                        st.markdown("---")
                        try:
                            word_buffer = generate_policy_word_doc(response)
                            col1, col2, col3 = st.columns([1, 2, 1])
                            with col2:
                                st.download_button(
                                    label="📄 Download Policy as Word Document",
                                    data=word_buffer.getvalue(),
                                    file_name=f"policy_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx",
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    use_container_width=True
                                )
                        except Exception as e:
                            st.error(f"Error generating Word document: {str(e)}")
                    else:
                        st.markdown(response)
                    
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
        if not st.session_state.show_login:
            show_landing_page()
        else:
            login_page()
    else:
        if not st.session_state.conversations:
            load_conversations()
        chat_interface()

if __name__ == "__main__":
    main()