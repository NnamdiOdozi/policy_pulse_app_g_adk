from pinecone import Pinecone
import requests
import os
import datetime

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Import session manager
from .session_manager import SessionManager

# Get API keys from environment variables
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY")
SONAR_API_KEY = os.environ.get("SONAR_API_KEY")

def get_system_prompt(retrieved_chunks):
    system_prompt = (
        "You are an expert compliance assistant specializing in workplace reproductive and fertility health policies.\n\n"
        "CRITICAL INSTRUCTIONS:\n"
         "You MUST use the citation format [DOC X] where X is the document number.This is critical!\n\n"
        "INCORRECT: 'Companies should provide fertility benefits [1].'\n"
        "CORRECT: 'Companies should provide fertility benefits [DOC 1].'\n\n"
        "INCORRECT: 'Reproductive health policies should be inclusive [DOCUMENT 2].'\n"
        "CORRECT: 'Reproductive health policies should be inclusive [DOC 2].'\n\n"
        #"- ONLY use information contained in the provided documents to answer questions\n"
        #"- If the documents don't contain the answer, state clearly that you don't have that information\n"
        "- NEVER make up or hallucinate information not present in the documents\n"
        #"- NEVER reference companies, monetary values, or details not explicitly mentioned in the documents\n"
        "- Provide specific citations linking each piece of information to its source document\n"
        "- When uncertain about any detail, express uncertainty rather than guessing\n\n"
        "Your role is to:\n"
        #"- Provide accurate information based SOLELY on the provided context documents\n"
        "- Generate well-structured responses that clearly separate facts from the documents\n"
        "- Always cite your sources with clear document numbers\n"
        "- Refuse to speculate beyond what is explicitly stated in the documents\n"
        "- Prioritize searching official government sources, serious think tanks, research institutes and serious newspapers and magazines\n"
        "- Clearly list the primary sources used for the summary. You must include details like authors, publication year and direct URL if available\n"
    )
    # Add retrieved context to the system prompt
    if retrieved_chunks:
        system_prompt += "\n\n===== REFERENCE DOCUMENTS =====\n\n"
        for i, chunk in enumerate(retrieved_chunks):
            # Extract a short identifier from the ID for clearer reference
            doc_id = chunk['id']
            system_prompt += f"DOC {i+1}: [ID: {'doc_id'}]\n{chunk['text']}\n\n"
    else:
        system_prompt += "\n\nNO REFERENCE DOCUMENTS AVAILABLE. If you cannot answer the query based on your general knowledge, please state that you do not have sufficient information to provide an accurate answer."
    
    return system_prompt

def retrieve_relevant_chunks(text, index_name, api_key, top_k=5):
    """
    Retrieve relevant text chunks from Pinecone based on a query
    
    Parameters:
    text (str): The user's query text
    index_name (str): Name of Pinecone index
    api_key (str): Pinecone API key
    top_k (int): Number of relevant chunks to retrieve
    
    Returns:
    list: List of relevant document chunks
    """
    from pinecone import Pinecone
    
    # Initialize Pinecone
    pc = Pinecone(api_key=api_key)
    
    # Get the index
    index = pc.Index(index_name)
 
    # Use the search method with proper format
    response = index.search(
        namespace="",
        query={
            "inputs": {"text": text},
            "top_k": top_k
        },
        fields=["ID", "text", "metadata"],  # Specify the fields you want to retrieve
    )
        
    print(f"Search response received")
    
    # Extract and return the retrieved chunks
    retrieved_chunks = []

    # Force it into a dict if needed
    if not isinstance(response, dict) and hasattr(response, "to_dict"):
        response = response.to_dict()

    hits = response.get("result", {}).get("hits", [])
    print(f"Found {len(hits)} hits")

    retrieved_chunks = []
    for hit in hits:
        retrieved_chunks.append({
            "id":       hit.get("_id", "unknown"),
            "score":    hit.get("_score", 0),
            "text":     hit.get("fields", {}).get("text", ""),
            "metadata": hit.get("metadata", {})  # if you stored metadata
        })
    return retrieved_chunks
    
def query_sonar(system_prompt, user_query):
    """
    Query the SONAR API with system prompt and user query
    
    Parameters:
    system_prompt (str): System prompt including retrieved context
    user_query (str): User's question
    
    Returns:
    str: Response from SONAR
    """
    
    # SONAR API endpoint and key
    SONAR_API_URL = "https://api.perplexity.ai/chat/completions"
    SONAR_API_KEY = os.environ.get("SONAR_API_KEY")
    
    # Prepare the request
    headers = {
        "Authorization": f"Bearer {SONAR_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "sonar",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query}
        ],
        "temperature": 0.0,
        "web_search_options": {
            "search_context_size": "medium"
        },
        "search_domain_filter": [
            "peppy.health",
            "getjuniper.co.uk",
            "fertifa.com"
            "fertilitynetworkuk.org"
            "hertilityhealth.com"
            "https://resolve.org/learn/financial-resources-for-family-building/insurance-coverage/getting-insurance-coverage-at-work/"
            "fertilitymattersatwork.com"
            "bournhall.co.uk"
            "unfpa.org"
            "gaiafamily.com/en-gb/gaia-plan/how-it-works"

    ]
    }
    # Make the API call
    response = requests.post(SONAR_API_URL, headers=headers, json=payload)
    
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        return f"Error calling SONAR API: {response.status_code} - {response.text}"

def query_sonar_with_history(messages):
    """
    Query the SONAR API with full message history
    
    Parameters:
    messages (list): List of message objects with role and content
    
    Returns:
    str: Response from SONAR
    """
    # SONAR API endpoint and key
    SONAR_API_URL = "https://api.perplexity.ai/chat/completions"
    SONAR_API_KEY = os.environ.get("SONAR_API_KEY")
    
    # Prepare the request
    headers = {
        "Authorization": f"Bearer {SONAR_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "sonar",
        "messages": messages,
        "temperature": 0.0,
        "web_search_options": {
            "search_context_size": "low"
        }
    }
    
    # Make the API call
    response = requests.post(SONAR_API_URL, headers=headers, json=payload)
    
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        return f"Error calling SONAR API: {response.status_code} - {response.text}"

def answer_question(user_query, index_name, api_key=PINECONE_API_KEY, top_k=5, conversation_history=None):
    """
    Main function to answer a user question using RAG approach with conversation history
    
    Parameters:
    user_query (str): User's question
    index_name (str): Name of Pinecone index
    api_key (str): Pinecone API key
    top_k (int): Number of relevant chunks to retrieve
    conversation_history (list): List of previous exchanges in the conversation
    
    Returns:
    str: Response from SONAR
    """
    # Retrieve relevant chunks
    print(f"Retrieving relevant chunks for query: {user_query}")
    retrieved_chunks = retrieve_relevant_chunks(user_query, index_name, api_key, top_k)
    print(f"Retrieved {len(retrieved_chunks)} relevant chunks")
    
    # Generate system prompt with retrieved chunks
    system_prompt = get_system_prompt(retrieved_chunks)
    
    # Prepare messages including conversation history
    messages = [
        {"role": "system", "content": system_prompt}
    ]
    
    # Add conversation history to messages if available
    if conversation_history and len(conversation_history) > 0:
        # Add a note about conversation history to the system prompt
        history_note = "\n\n===== CONVERSATION HISTORY =====\n\n"
        history_note += "The following is the conversation history. Use this context to understand the current query.\n\n"
        
        # Append the note to the system prompt
        messages[0]["content"] += history_note
        
        # Add previous exchanges (up to a reasonable limit, e.g., last 5)
        for exchange in conversation_history[-5:]:
            messages.append({"role": "user", "content": exchange["user"]})
            if "assistant" in exchange:
                messages.append({"role": "assistant", "content": exchange["assistant"]})
    
    # Add current query
    messages.append({"role": "user", "content": user_query})
    
    # Query SONAR API with the full message history
    print("Querying SONAR API...")
    response = query_sonar_with_history(messages)
    
    return response

def process_command(command, args, session_manager, index_name, api_key):
    """
    Process a command from the user
    
    Parameters:
    command (str): Command to process
    args (str): Arguments for the command
    session_manager (SessionManager): Session manager instance
    index_name (str): Name of the Pinecone index
    api_key (str): Pinecone API key
    
    Returns:
    str: Response message
    """
    if command == "new":
        session_id = session_manager.new_session()
        return f"Started new conversation. Session ID: {session_id}"
    
    elif command == "save":
        session_name = args.strip() if args else None
        session_id = session_manager.save_session(session_name)
        name_display = f" as '{session_name}'" if session_name else ""
        return f"Conversation saved{name_display}. Session ID: {session_id}"
    
    elif command == "load":
        session_id = args.strip()
        if not session_id:
            return "Error: Please specify a session ID or name to load."
        
        success = session_manager.load_session(session_id)
        if success:
            return f"Loaded conversation: {session_manager.get_session_name()}"
        else:
            return f"Error: Could not load session '{session_id}'."
    
    elif command == "list":
        sessions = session_manager.list_sessions()
        if not sessions:
            return "No saved conversations found."
        
        response = "Available conversations:\n"
        for i, session in enumerate(sessions):
            name = session["name"] or session["id"]
            created = session["created_at"].split("T")[0]  # Just the date part
            response += f"{i+1}. {name} ({session['message_count']} messages, created {created})\n"
        
        return response
    
    elif command == "help":
        return (
            "Available commands:\n"
            "/new - Start a new conversation\n"
            "/save [name] - Save current conversation with optional name\n"
            "/load [id|name] - Load a specific conversation\n"
            "/list - Show available saved conversations\n"
            "/exit - Exit the program\n"
            "/help - Show this help message"
        )
    
    else:
        return f"Unknown command: {command}. Type /help for available commands."

def interactive_qa(index_name="policypulse", api_key=PINECONE_API_KEY):
    """
    Interactive Q&A loop with session management
    """
    print("Welcome to Policy Pulse, the Reproductive and Fertility Health Compliance Agent!")
    print("Type /help for available commands or /exit to quit.")
    
    # Initialize session manager
    session_manager = SessionManager()
    current_session_id = session_manager.get_current_session_id()
    
    # Track when we last auto-saved
    last_autosave = datetime.datetime.now()
    autosave_interval = datetime.timedelta(minutes=1)  # Save every 1 minute

    while True:
        # Auto-save check
        now = datetime.datetime.now()
        if now - last_autosave > autosave_interval and session_manager.get_conversation_history():
            print("\n[Auto-saving session...]")
            session_manager.save_session()
            last_autosave = now
            print(f"[Session auto-saved as {session_manager.get_current_session_id()}]")

        # Display prompt with current session
        user_input = input(f"\n[Session: {session_manager.get_session_name()}] Your question: ")
        
        # Check for commands
        if user_input.startswith("/"):
            parts = user_input[1:].split(maxsplit=1)
            command = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""
            
            if command == "exit":
                print("Thank you for using Policy Pulse. Goodbye!")
                break
            
            response = process_command(command, args, session_manager, index_name, api_key)
            print(response)
            continue
        
        # Process regular questions
        response = answer_question(
            user_input, 
            index_name, 
            api_key, 
            conversation_history=session_manager.get_conversation_history()
        )
        
        # Display the response
        print("\nCompliance Bot Response:")
        print(response)
        
        # Add this exchange to the session
        session_manager.add_message(user_input, response)

if __name__ == "__main__":      
    # Start the interactive Q&A session
    interactive_qa()