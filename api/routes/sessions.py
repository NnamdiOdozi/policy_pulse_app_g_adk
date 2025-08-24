# backend/api/routes/sessions.py
from fastapi import APIRouter, HTTPException
from agents.policy_pulse_agent.agent import session_service

router = APIRouter()

@router.get("/sessions")
async def list_sessions_endpoint(user_id: str):
    """List all available sessions for a user"""
    try:
        # Get all sessions for the user
        sessions = session_service.list_sessions(user_id)
        return {
            "sessions": sessions,
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Session retrieval error: {str(e)}")

@router.post("/sessions/new")
async def new_session_endpoint(user_id: str, session_name: str = None):
    """Create a new session"""
    try:
        # Create a new session
        session_id = session_service.new_session(user_id, session_name)
        return {
            "session_id": session_id,
            "status": "created"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Session creation error: {str(e)}")

@router.get("/sessions/{session_id}")
async def get_session_endpoint(session_id: str):
    """Get details for a specific session"""
    try:
        # Get session details
        session = session_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
            
        return {
            "session": session,
            "status": "success"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Session retrieval error: {str(e)}")

@router.put("/sessions/{session_id}")
async def update_session_endpoint(session_id: str, session_name: str = None):
    """Update session details"""
    try:
        # Update session
        updated = session_service.update_session(session_id, session_name)
        if not updated:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
            
        return {
            "session_id": session_id,
            "status": "updated"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Session update error: {str(e)}")

@router.delete("/sessions/{session_id}")
async def delete_session_endpoint(session_id: str):
    """Delete a session"""
    try:
        # Delete session
        deleted = session_service.delete_session(session_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
            
        return {
            "session_id": session_id,
            "status": "deleted"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Session deletion error: {str(e)}")