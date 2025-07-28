from fastapi import FastAPI, Depends, Request
import gradio as gr
import uvicorn
from starlette.middleware.sessions import SessionMiddleware
from starlette.config import Config
from authlib.integrations.starlette_client import OAuth, OAuthError
import os
from starlette.responses import RedirectResponse
import json
from datetime import datetime
from pathlib import Path
import openai
import hashlib

app = FastAPI()

openai.api_key = os.getenv("OPENAI_API_KEY")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

config_data = {'GOOGLE_CLIENT_ID': GOOGLE_CLIENT_ID, 'GOOGLE_CLIENT_SECRET': GOOGLE_CLIENT_SECRET}
starlette_config = Config(environ=config_data)
oauth = OAuth(starlette_config)
oauth.register(
    name='google',
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'},
)
app.add_middleware(SessionMiddleware, secret_key="my_secret2")

data_folder = Path("/mnt/user_data/")

error_message = "Sorry, an error occured when generating your response. Please try again later."

def get_user(request: Request):
    user = request.session.get('user')
    if user:
        hash_obj = hashlib.sha256(user['email'].encode('utf-8'))
        return hash_obj.hexdigest()[:10]
    return None

@app.get('/')
def public(user: dict = Depends(get_user)):
    if user:
        return RedirectResponse(url='/chat')
    else:
        return RedirectResponse(url='/login-page')

@app.route('/logout')
async def logout(request: Request):
    request.session.pop('user', None)
    return RedirectResponse(url='/')

@app.route('/login')
async def login(request: Request):
    redirect_uri = request.url_for('auth')
    return await oauth.google.authorize_redirect(request, redirect_uri)

@app.route('/auth')
async def auth(request: Request):
    try:
        access_token = await oauth.google.authorize_access_token(request)
    except OAuthError:
        return RedirectResponse(url='/')
    request.session['user'] = dict(access_token)["userinfo"]
    return RedirectResponse(url='/')

with gr.Blocks() as login_demo:
    gr.Button("Login", link="/login")

app = gr.mount_gradio_app(app, login_demo, path="/login-page")


# Populate the chatbot with the user's previous interactions
def load_data(request: gr.Request):
    user_interactions_file = data_folder / f"interactions_{request.username}.json"
    user_redactions_file = data_folder / f"redactions_{request.username}.json"

    history = []
    if os.path.exists(user_interactions_file):
        with user_interactions_file.open("r") as f:
            for line in f:
                turn = json.loads(line)
                if turn["output"]==error_message:
                    continue
                history.append({"role": "user", "content": turn["input"]})
                history.append({"role": "assistant", "content": turn["output"], "tokens": turn["tokens"]})
    
    redactions = []
    if os.path.exists(user_redactions_file):
        with user_redactions_file.open("r") as f:
            for line in f:
                feedback = json.loads(line)
                redactions.append(feedback["message_idx"])

    # Remove redacted messages from history
    for r in redactions:
        del history[r]
        del history[r-1]

    return history

# Make the chatbot and msg visible only after data loaded
def load_app():
    return gr.update(visible=True), gr.update(visible=True)

# Add user's message to chatbot and clear input box
def save_msg(user_message, history: list):
    return "", history + [{"role": "user", "content": user_message}]

# Generate bot's response and save in local file
def generate_response(request: gr.Request | None, history: list):
    client = openai.OpenAI()
    
    formatted_history = []
    tokens = 0
    for h in reversed(history):
        if "tokens" in h:
            tokens += h["tokens"]
        if tokens > 500000:
            break
        formatted_history.append({"role": h["role"], "content": h["content"]})
    formatted_history.reverse()

    responses = client.responses.create(
        model="gpt-4.1-mini-2025-04-14",
        input=formatted_history,
        temperature=1,
        max_output_tokens=1000,
        stream=True,
    )

    response = ""
    completed = False
    history.append({"role": "assistant", "content": "", "tokens": 0})
    for chunk in responses:
        if chunk.type == "response.output_text.delta":
            response += chunk.delta
            history[-1]["content"] = response
            yield history
        elif chunk.type == "response.completed":
            completed = True
            history[-1]["tokens"] = chunk.response.usage.total_tokens
            yield history
        elif chunk.type == "response.error":
            history[-1]["content"] = error_message
            history[-1]["tokens"] = 0
            yield history

    if not completed:
        history[-1]["content"] = error_message
        history[-1]["tokens"] = 0

    if request is not None:
        user_interactions_file = data_folder / f"interactions_{request.username}.json"
        with user_interactions_file.open("a") as f:
            f.write(json.dumps({"timestamp": datetime.now().isoformat(), "input": history[-2]["content"], "output": history[-1]["content"], "tokens": history[-1]["tokens"]}))
            f.write("\n")

    yield history

# Record redaction feedback and save in local file
def redact_msg(message: gr.LikeData, request: gr.Request | None, history: list):
    if request is not None and message.liked == "Redact From Study":
        user_redactions_file = data_folder / f"redactions_{request.username}.json"
        with user_redactions_file.open("a") as f:
            f.write(json.dumps({"timestamp": datetime.now().isoformat(), "message_idx": message.index}))
            f.write("\n")

    del history[message.index] # Delete the chatbot message
    del history[message.index-1] # Delete the user message
    return history    


def _noop():
    # this exists only so Gradio always has a Python function to call
    return


fix_redact_ui_bug = """
function updateFeedbackDiv() {
  const feedbackButtons = document.querySelectorAll('button[title="Feedback"]');
  if (!feedbackButtons.length) return;

  feedbackButtons.forEach(button => {
    // Update style
    button.style.color = 'var(--block-label-text-color)';

    // Update SVG path
    const svgIcon = button.querySelector('svg#icon path');
    if (svgIcon) {
      svgIcon.setAttribute('d', 'M6,30H4V2H28l-5.8,9L28,20H6ZM6,18H24.33L19.8,11l4.53-7H6Z');
    }

    // Add blur on click to remove focus highlight
    button.addEventListener('click', () => {
      // Delay blur slightly to allow click handlers to work
      setTimeout(() => {
        if (document.activeElement === button) {
          button.blur();
        }
      }, 0);
    });
  });
}
"""

scroll_to_bottom_js = """
function scrollChatToBottom() {
    const chatbot = document.querySelector('.bubble-wrap.svelte-gjtrl6');
    
    if (chatbot) {
        chatbot.scrollTop = chatbot.scrollHeight;
        console.log('Scrolled chatbot to bottom');
    }
}
"""




with gr.Blocks(css=".icon-button-wrapper.top-panel { display: none !important; }") as main_demo:
    chatbot = gr.Chatbot(type="messages", show_share_button=False, show_copy_button=True, visible=False, feedback_options=["Redact From Study"], height="75vh")
    msg = gr.Textbox(show_label=False, submit_btn=True, placeholder="Ask anything", visible=False)
    logout_button = gr.Button("Logout", link="/logout")

    main_demo.load(load_data, inputs=None, outputs=[chatbot]).then(
        load_app, inputs=None, outputs=[chatbot, msg]
    ).then(
        fn=_noop, inputs=[], outputs=[], js=scroll_to_bottom_js
    )

    msg.submit(save_msg, inputs=[msg, chatbot], outputs=[msg, chatbot]).then(generate_response, inputs=[chatbot], outputs=[chatbot]).then(
        fn=_noop, inputs=[], outputs=[], js=scroll_to_bottom_js
    )
    chatbot.like(redact_msg, inputs=[chatbot], outputs=[chatbot]).then(fn=_noop, inputs=[], outputs=[], js=fix_redact_ui_bug)

app = gr.mount_gradio_app(app, main_demo, path="/chat", auth_dependency=get_user)

if __name__ == '__main__':
    uvicorn.run(app)
