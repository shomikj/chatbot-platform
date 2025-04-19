from fastapi import FastAPI, Depends, Request
import gradio as gr
import uvicorn
from starlette.middleware.sessions import SessionMiddleware
from starlette.config import Config
from authlib.integrations.starlette_client import OAuth, OAuthError
import os
from starlette.responses import RedirectResponse
from huggingface_hub import InferenceClient

app = FastAPI()

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
app.add_middleware(SessionMiddleware, secret_key="my_secret")

def get_user(request: Request):
    user = request.session.get('user')
    if user:
        return user['email']
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
    #redirect_uri = urlunparse(urlparse(str(redirect_uri))._replace(scheme='https'))
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
    return []

# Make the chatbot and msg visible only after data loaded
def load_app():
    return gr.update(visible=True), gr.update(visible=True)

# Add user's message to chatbot and clear input box
def save_msg(user_message, history: list):
    return "", history + [{"role": "user", "content": user_message}]

# Generate bot's response and save in local file
def generate_response(request: gr.Request | None, history: list):
    client = InferenceClient("HuggingFaceH4/zephyr-7b-beta", token=os.getenv("HF_TOKEN"))

    bot_message = client.chat.completions.create(
        messages=history,
        temperature=0.7,
        max_tokens=256,
    ).choices[0].message.content
    history.append({"role": "assistant", "content": bot_message})

    return history

# Record redaction feedback and save in local file
def redact_msg(message: gr.LikeData, request: gr.Request | None, history: list):
    del history[message.index] # Delete the chatbot message
    del history[message.index-1] # Delete the user message
    return history    

# Fix the bug that causes the redact button to be highlighted

fix_redact_ui_bug = """
function updateFeedbackDiv() {
  // Select the feedback button using a stable attribute
  const feedbackButton = document.querySelector('button[title="Feedback"]');
  if (!feedbackButton) return;

  // Update style
  feedbackButton.style.color = 'var(--block-label-text-color)';

  // Replace the icon SVG path
  const svgIcon = feedbackButton.querySelector('svg#icon path');
  if (svgIcon) {
    svgIcon.setAttribute('d', 'M6,30H4V2H28l-5.8,9L28,20H6ZM6,18H24.33L19.8,11l4.53-7H6Z');
  }

  // Select the "Redact From Study" button
  const redactButton = Array.from(document.querySelectorAll('button'))
    .find(btn => btn.textContent.trim() === 'Redact From Study');

  if (redactButton) {
    redactButton.style.fontWeight = 'normal';
  }
}
"""

with gr.Blocks(css=".icon-button-wrapper.top-panel { display: none !important; }") as main_demo:
    chatbot = gr.Chatbot(type="messages", show_share_button=False, show_copy_button=True, visible=False, feedback_options=["Redact From Study"])
    msg = gr.Textbox(show_label=False, submit_btn=True, placeholder="Ask anything", visible=True)
    logout_button = gr.Button("Logout", link="/logout")
    main_demo.load(load_data, inputs=None, outputs=[chatbot]).then(load_app, inputs=None, outputs=[chatbot, msg])
    msg.submit(save_msg, inputs=[msg, chatbot], outputs=[msg, chatbot], queue=False).then(generate_response, inputs=[chatbot], outputs=[chatbot])
    chatbot.like(redact_msg, inputs=[chatbot], outputs=[chatbot]).then(fn=None, inputs=[], outputs=[], js=fix_redact_ui_bug)

app = gr.mount_gradio_app(app, main_demo, path="/chat", auth_dependency=get_user)

if __name__ == '__main__':
    uvicorn.run(app)