from dotenv import load_dotenv
from openai import OpenAI

# Load the API key from .env
load_dotenv()

# Create the API client
client = OpenAI()

# Send a small test request
response = client.responses.create(
    model="gpt-4.1-mini",
    input="Reply with exactly: Hello from my RAG project!"
)

print(response.output_text)
