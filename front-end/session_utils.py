import os
import asyncio
import secrets
import uuid
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

def get_db_connection():
    """Get database connection"""
    db_url = os.environ.get("DATABASE_URL")
    return psycopg2.connect(db_url, cursor_factory=RealDictCursor)

def create_new_session(user_id):
    """Create a new ADK session for the user"""
    import uuid
    import asyncio
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
    """Save conversation metadata"""
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
    """Get all conversations for a user"""
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
    """Get messages from a specific conversation"""
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
    """Delete a conversation"""
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