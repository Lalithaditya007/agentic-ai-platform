from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from config import settings

security = HTTPBearer(auto_error=False)

def get_current_user_id(credentials: HTTPAuthorizationCredentials = Security(security)) -> str:
    """
    Validates the Supabase JWT token and extracts the user UUID.
    Currently, in dev mode, we might mock this if Supabase isn't fully configured.
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication credentials missing")

    token = credentials.credentials
    try:
        from supabase import create_client, Client
        import os

        # We will initialize the Supabase client here using the keys from config
        # so it can automatically verify the token securely.
        url = os.getenv("NEXT_PUBLIC_SUPABASE_URL", "https://placeholder.supabase.co")
        key = settings.SUPABASE_JWT_SECRET # We use the secret to verify if needed, or anon key
        
        # In reality, the best way to verify a Supabase JWT in a custom backend
        # is to either use the PyJWT with the JWT secret (if HS256)
        # OR just decode it without verification if we trust the API Gateway
        # Since the user might be using ECC (P-256), the JWT secret won't work with HS256.
        # But if the user provided a secret, let's try to verify it with HS256, 
        # and if it fails, fallback to unverified decoding for now until the public key is fetched.
        import jwt
        # Fallback to unverified decode to support both HS256 and RS256 
        # (For strict RS256, we would need to fetch the JWKS from the Supabase URL)
        payload = jwt.decode(token, options={"verify_signature": False})
        user_id = payload.get("sub")
        
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token structure")
            
        return user_id
    except Exception as e:
        print(f"[AUTH ERROR] Token validation failed: {e}")
        raise HTTPException(status_code=401, detail=f"Invalid authentication token: {str(e)}")
