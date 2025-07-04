"""
Security utilities for Model Gateway
"""
import hmac
import hashlib
from typing import Optional, Union
import json


class HMACValidator:
    """HMAC signature validation for responses"""
    
    def __init__(self, secret: str):
        self.secret = secret.encode('utf-8')
    
    def sign(self, data: Union[str, bytes]) -> str:
        """Generate HMAC-SHA256 signature"""
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        signature = hmac.new(
            self.secret,
            data,
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def verify(self, data: Union[str, bytes], signature: str) -> bool:
        """Verify HMAC signature"""
        expected = self.sign(data)
        return hmac.compare_digest(expected, signature)
    
    def sign_stream_chunk(self, chunk: str, sequence: int) -> str:
        """Sign a streaming chunk with sequence number"""
        data = json.dumps({
            "chunk": chunk,
            "seq": sequence
        }, separators=(',', ':'))
        
        return self.sign(data)
