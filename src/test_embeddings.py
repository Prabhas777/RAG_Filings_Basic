import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI()

response = client.embeddings.create(
    model="text-embedding-3-small",
    input="NVIDIA reports record Data Center revenue in its 10-K filing."
)

vector = response.data[0].embedding
print(f"Embedding successful! Vector length: {len(vector)}")
print(f"First 5 numbers: {vector[:5]}")
