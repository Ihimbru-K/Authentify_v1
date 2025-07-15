from app.security import get_password_hash

#from app.security import get_password_hash

password = "mine"  
new_hash = get_password_hash(password)
print(new_hash)





####### for testing any random scripts such as tokens