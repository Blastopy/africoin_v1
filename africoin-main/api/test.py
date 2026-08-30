from cryptography.fernet import Fernet
import secrets

key = Fernet.generate_key()
f = Fernet(key)              # <-- this creates the instance

text = secrets.token_hex(32)
print(f"Original: {text}")
token = f.encrypt(text.encode())
print(f"Token: {token}")
decoded = f.decrypt(token).decode()
print(f"Decoded: {decoded}")