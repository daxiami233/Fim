from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from pydantic import SecretStr
import os

load_dotenv()

# llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", max_retries=3, temperature=1.0) 
llm_flash = ChatOpenAI(
    model=os.getenv("GOOGLE_MODEL"),
    base_url=os.getenv("GOOGLE_BASE_URL"),
    api_key=SecretStr(os.getenv("GOOGLE_API_KEY")),
    temperature=0,
    max_retries=3
)     
llm_pro = ChatOpenAI(
    model="gemini-2.5-flash-thinking",
    base_url=os.getenv("GOOGLE_BASE_URL"),
    api_key=SecretStr(os.getenv("GOOGLE_API_KEY")),
    temperature=1.0,
    max_retries=3
) 
uitars = ChatOpenAI(
    model=os.getenv("SPECIALIZED_MODEL"),
    base_url=os.getenv("SPECIALIZED_BASE_URL"),
    api_key=SecretStr(os.getenv("SPECIALIZED_API_KEY")),
    temperature=0.0,
    max_completion_tokens= 400,
    max_retries=3,
)     




