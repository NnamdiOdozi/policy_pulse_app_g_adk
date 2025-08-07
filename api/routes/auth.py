# backend/api/routes/auth.py
from fastapi import APIRouter, HTTPException
from front_end.auth import authenticate_user, create_user

router = APIRouter()

@router.post("/auth/login")
async def login_endpoint(email: str, password: str):
    """Login using YOUR existing authentication function"""
    try:
        # Use YOUR existing function from auth.py
        user = authenticate_user(email, password)
        
        if user:
            return {
                "user": user,
                "status": "authenticated"
            }
        else:
            raise HTTPException(status_code=401, detail="Invalid credentials")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Authentication error: {str(e)}")

@router.post("/auth/signup")
async def signup_endpoint(username: str, email: str, password: str):
    """Create user using YOUR existing function"""
    try:
        # Use YOUR existing function from auth.py
        success = create_user(username, email, password)
        
        if success:
            return {
                "username": username,
                "email": email,
                "status": "created"
            }
        else:
            raise HTTPException(status_code=400, detail="User creation failed - email might already exist")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Signup error: {str(e)}")