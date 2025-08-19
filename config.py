import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

def check_env_file():
    """Check if .env file exists, create example file and prompt user to configure if not"""
    env_path = Path('.env')
    if not env_path.exists():
        logger.error("No .env configuration file found!")
        # Create example .env file
        with open('.env.example', 'w') as f:
            f.write('BASE_URL="https://api.openai.com/v1"\n')
            f.write('MODEL="gpt-4-turbo"\n')
            f.write('API_KEY="YOUR_API_KEY"\n')
        
        logger.error("Please configure your .env file before running the program!")
        logger.info("An .env.example file has been created. Copy it to .env and configure it.")
        logger.info("Configuration command: cp .env.example .env")
        sys.exit(1)
    
    # Load .env file
    load_dotenv()

    
def init_config():
    """Initialize configuration"""
    check_env_file()  
    config = {
        "base_url": os.getenv("BASE_URL"),
        "model": os.getenv("MODEL"),
        "api_key": os.getenv("API_KEY")
    }
    return config
