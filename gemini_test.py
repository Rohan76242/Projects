from google import genai

client = genai.Client()

response = client.models.generate_content(
    model="gemini-robotics-er-2-streaming-preview",
    contents="You are Sohan, my personal AI assistant. Say hello to me in one short sentence."
)

print(response.text)
