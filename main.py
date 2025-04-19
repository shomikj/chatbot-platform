from fastapi import FastAPI
import gradio as gr
import uvicorn

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello World"}

def alternatingly_agree(message, history):
    if len([h for h in history if h['role'] == "assistant"]) % 2 == 0:
        return f"Yes, I do think that: {message}"
    else:
        return "I don't think so"

demo = gr.ChatInterface(
    fn=alternatingly_agree, 
    title="Alternating ChatBot",
    description="This chatbot alternates between agreeing and disagreeing with you.",
    type="messages"
)

app = gr.mount_gradio_app(app, demo, path="/chat")

if __name__ == '__main__':
    uvicorn.run(app)