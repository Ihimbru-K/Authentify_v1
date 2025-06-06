from dotenv import load_dotenv #imports function to load .env files
import os  #access environment variables

load_dotenv()  #fetch variables from a .env file into the environment

DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"  #common algo for jwt encoding 