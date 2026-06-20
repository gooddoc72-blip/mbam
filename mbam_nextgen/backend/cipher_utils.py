import os
from cryptography.fernet import Fernet
from dotenv import load_dotenv

def get_cipher():
    # Load the base encryption key from environment
    # If not present, warn or fallback to a dummy key for dev
    key = os.environ.get("ENV_CIPHER_KEY")
    if not key:
        # Default dev key (do not use in prod)
        key = Fernet.generate_key().decode()
        os.environ["ENV_CIPHER_KEY"] = key
    return Fernet(key.encode())

def encrypt_val(val: str) -> str:
    if not val:
        return ""
    cipher = get_cipher()
    return cipher.encrypt(val.encode()).decode()

def decrypt_val(encrypted_val: str) -> str:
    if not encrypted_val:
        return ""
    try:
        cipher = get_cipher()
        return cipher.decrypt(encrypted_val.encode()).decode()
    except Exception:
        # If decryption fails, return original assuming it's not encrypted yet
        return encrypted_val

def get_decrypted_env(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        return ""
    
    # Check if the value is explicitly marked as encrypted, or try decrypting
    if val.startswith("ENC_"):
        return decrypt_val(val[4:])
    
    # If not prefixed with ENC_, assume it's raw
    return val
