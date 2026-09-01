import hashlib, uuid

#-------------Hashing----------------------------#
#for encrypting the password in the database
def hash_password(password):
    salt = uuid.uuid4().hex
    return hashlib.sha256(salt.encode() + password.encode()).hexdigest() + ':' + salt

#for decrypting the password in the database - returns True if correct
def check_password(hashed_password, user_password):
    if not hashed_password:
        return False

    if ':' not in hashed_password:
        return hashed_password == user_password

    password, salt = hashed_password.split(':', 1)
    return password == hashlib.sha256(salt.encode() + user_password.encode()).hexdigest()