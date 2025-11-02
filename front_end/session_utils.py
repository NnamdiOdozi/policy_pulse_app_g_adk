# =============================================================================
# SESSION MANAGEMENT & CONVERSATION UTILITIES
# =============================================================================
# PURPOSE: Bridge between Streamlit UI and Google ADK session system
# CRITICAL CONCEPT: TWO parallel session systems working together:
#   1. ADK sessions (Google's agent framework) - actual conversation content
#   2. chat_sessions table (our custom metadata) - UI display information

import os
import sys
import asyncio
import secrets
import uuid
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

from Utils.client_factory import get_db_connection

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def create_new_session(user_id):
    """
    Create a new ADK session for starting a conversation
    
    ASYNC/SYNC BOUNDARY ISSUE:
    - ADK's create_session() is async (uses await)
    - Streamlit is synchronous (no async/await support)
    - SOLUTION: Wrap async call with asyncio.run()
    
    HOW IT WORKS:
    1. Generate unique session_id: "session_{8_hex_chars}"
    2. Import ADK session_service from agent.py
    3. Create async wrapper function
    4. Use asyncio.run() to execute async function in sync context
    5. Return session_id for use in Streamlit session_state
    
    SESSION_ID FORMAT:
    - Prefix "session_" for readability in logs
    - 8 hex chars = 4 billion possible IDs (collision unlikely)
    - Shorter than full UUID for cleaner URLs/logs
    
    WHY THIS PATTERN?:
    - Can't make Streamlit app async (framework limitation)
    - Can't call async ADK directly from sync Streamlit
    - asyncio.run() creates new event loop for single async operation
    
    GOTCHA: asyncio.run() should only be called from sync code
    - Don't use inside existing async functions
    - Creates new event loop each time (overhead)
    - Fine for occasional operations like session creation
    """

    session_id = f"session_{uuid.uuid4().hex[:8]}"
    
    # Import the session service from your agent
    from agents.policy_pulse_agent.agent import session_service
    
    # Actually create the session in ADK (this is the key part)
    async def _create():
        await session_service.create_session(
            app_name="policy_pulse_app",
            user_id=user_id,
            session_id=session_id
        )
    
    asyncio.run(_create())
    return session_id

def save_conversation(user_id, session_id, title):
    """
    Save conversation metadata to chat_sessions table
    
    WHEN CALLED: After first user message (creates conversation entry)
    
    DESIGN PATTERN: Check-then-insert to avoid duplicates
    1. Query if session_id already exists for this user
    2. If not found, insert new row
    3. If found, do nothing (idempotent)
    
    WHY NOT UPSERT?: 
    - We never update title after creation
    - First message title is permanent
    - Simpler logic than ON CONFLICT DO NOTHING
    
    TITLE GENERATION:
    - Usually first 100 chars of user's first message
    - Truncated in pulse_streamlit_app.py before passing here
    - Provides meaningful conversation list in UI
    
    RELATIONSHIP TO ADK:
    - This ONLY updates chat_sessions (UI metadata)
    - ADK sessions table already has the session (created by create_new_session)
    - Both tables share session_id as linking key
    
    ERROR HANDLING:
    - Silent failure (prints to console only)
    - Won't crash app if database write fails
    - Conversation still works, just won't appear in sidebar list
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Check if conversation already exists
                cur.execute("""
                    SELECT session_id FROM chat_sessions 
                    WHERE session_id = %s AND user_id = %s
                """, (session_id, user_id))
                
                if not cur.fetchone():
                    # Insert new conversation metadata
                    cur.execute("""
                        INSERT INTO chat_sessions (session_id, user_id, title)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (session_id) DO NOTHING
                    """, (session_id, user_id, title))
                    conn.commit()
                    
    except Exception as e:
        print(f"Error saving conversation: {e}")

def get_user_conversations(user_id):
    """
    Retrieve all conversations for a user (for sidebar display)
    
    QUERY STRATEGY:
    - Join chat_sessions with ADK events table
    - Count messages per conversation
    - Order by most recent first (latest activity on top)
    
    MESSAGE COUNT CALCULATION:
    - Counts rows in events table for this session
    - Includes both user messages and agent responses
    - Zero messages possible if ADK data inconsistent
    
    RETURN FORMAT:
    List of dicts, each containing:
    - session_id: For loading conversation
    - title: For display in sidebar
    - created_at: Timestamp for sorting/display
    - message_count: Shows conversation length
    
    UI INTEGRATION:
    - Streamlit sidebar iterates over this list
    - Each conversation becomes clickable button
    - Message count shown as badge
    
    WHY JOIN WITH EVENTS?:
    - Need message count for UI display
    - Single query more efficient than N queries
    - PostgreSQL COUNT() is fast with proper indexes
    
    PERFORMANCE NOTE:
    - Uses LEFT JOIN (returns conversations even if zero messages)
    - GROUP BY needed because of COUNT aggregate
    - Indexed on user_id and session_id for fast queries
    """

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Get conversations from our metadata table
                cur.execute("""
                    SELECT cs.session_id, cs.title, cs.created_at,
                           COUNT(s.id) as message_count
                    FROM chat_sessions cs
                    LEFT JOIN sessions s ON cs.session_id = s.id 
                        AND s.user_id = %s
                        AND s.app_name = 'policy_pulse_app'
                    WHERE cs.user_id = %s
                    GROUP BY cs.session_id, cs.title, cs.created_at
                    ORDER BY cs.created_at DESC
                    LIMIT 20
                """, (user_id, user_id))
                
                conversations = cur.fetchall()
                
                return [
                    {
                        'session_id': conv['session_id'],
                        'title': conv['title'],
                        'created_at': conv['created_at'],
                        'message_count': conv['message_count'] or 0
                    }
                    for conv in conversations
                ]
                
    except Exception as e:
        print(f"Error getting conversations: {e}")
        return []

def get_conversation_messages(user_id, session_id):
    """
    Load full conversation history from ADK events table
    
    CRITICAL: This reads DIRECTLY from ADK's internal tables
    - ADK stores all conversation events in 'events' table
    - We query this to reconstruct conversation for display
    
    QUERY EXPLANATION:
    - Join events with sessions table
    - Filter by session_id AND user_id (security!)
    - Filter by app_name (multi-tenancy within same DB)
    - Order by timestamp (chronological conversation flow)
    
    CONTENT EXTRACTION COMPLEXITY:
    ADK stores content as nested JSON structure:
    {
      "parts": [
        {"text": "actual message text"},
        {"text": "more text if multi-part"}
      ]
    }
    
    EXTRACTION LOGIC:
    1. Check if content is dict with 'parts' key
    2. Iterate through parts array
    3. Extract 'text' field from each part
    4. Join multiple parts with newlines
    5. Fallback to str(content) if structure unexpected
    
    ROLE DETERMINATION:
    - author = 'user' → role = 'user'
    - author = anything else → role = 'assistant'
    - Covers root_agent, FAQ_agent, ReportWriting_agent
    
    WHY SKIP EMPTY MESSAGES?:
    - Tool calls generate events with no text content
    - Internal ADK events we don't want to display
    - Keeps UI clean and focused on conversation
    
    RETURN VALUE:
    List of dicts for easy Streamlit display:
    - role: 'user' or 'assistant'
    - content: Plain text string
    - timestamp: For optional display/debugging
    
    SECURITY NOTE:
    - Always filters by BOTH session_id AND user_id
    - Prevents users from accessing others' conversations
    - Defense in depth (RLS provides second layer)
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Get events from ADK events table
                cur.execute("""
                    SELECT e.content, e.author, e.timestamp
                    FROM events e
                    JOIN sessions s ON e.session_id = s.id
                    WHERE s.id = %s 
                        AND s.user_id = %s 
                        AND s.app_name = 'policy_pulse_app'
                    ORDER BY e.timestamp ASC
                """, (session_id, user_id))
                
                events = cur.fetchall()
                
                messages = []
                for event in events:
                    content = event['content']
                    
                    # Extract text from parts structure
                    text_content = ""
                    if isinstance(content, dict) and 'parts' in content:
                        text_parts = []
                        for part in content['parts']:
                            if isinstance(part, dict) and 'text' in part:
                                text_parts.append(part['text'])
                        text_content = '\n'.join(text_parts)
                    else:
                        text_content = str(content) if content else ""
                    
                    # Skip events with no text content (like tool calls)
                    if not text_content.strip():
                        continue
                    
                    # Determine role based on author
                    if event['author'] == 'user':
                        role = 'user'
                    else:  # root_agent or any other agent
                        role = 'assistant'
                    
                    messages.append({
                        'role': role,
                        'content': text_content,
                        'timestamp': event['timestamp']
                    })
                
                return messages
                
    except Exception as e:
        print(f"Error getting conversation messages: {e}")
        return []

def delete_conversation(user_id, session_id):
    """
    Delete conversation from UI (soft delete approach)
    
    WHAT GETS DELETED:
    - Row from chat_sessions table only
    - UI no longer shows this conversation
    
    WHAT STAYS:
    - ADK sessions table row (preserved)
    - ADK events table rows (preserved)
    - Full audit trail maintained
    
    WHY SOFT DELETE?:
    - Compliance requirements (data retention)
    - Debugging (can recover "deleted" conversations)
    - Audit trail (see what user discussed)
    - Undo functionality possible
    
    ALTERNATIVE APPROACH:
    Could add deleted_at timestamp to chat_sessions instead
    - Allows "undelete" functionality
    - Shows deletion time in admin panel
    - Keeps row for referential integrity
    
    USER EXPERIENCE:
    - Conversation disappears from sidebar immediately
    - User can't reload it through UI
    - Data still exists in database for admins
    
    SECURITY:
    - Filters by BOTH session_id AND user_id
    - Users can only delete their own conversations
    - Prevents unauthorized deletion
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Delete from chat_sessions (ADK sessions will remain for audit)
                cur.execute("""
                    DELETE FROM chat_sessions 
                    WHERE session_id = %s AND user_id = %s
                """, (session_id, user_id))
                conn.commit()
                return True
                
    except Exception as e:
        print(f"Error deleting conversation: {e}")
        return False