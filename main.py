import os
from fastapi import FastAPI, Depends, Request
from starlette.config import Config
from starlette.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
import uvicorn
import gradio as gr
from huggingface_hub import InferenceClient, CommitScheduler, snapshot_download
from pathlib import Path
from datetime import datetime
import json

app = FastAPI()

#GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
#GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

#config_data = {'GOOGLE_CLIENT_ID': GOOGLE_CLIENT_ID, 'GOOGLE_CLIENT_SECRET': GOOGLE_CLIENT_SECRET}
#starlette_config = Config(environ=config_data)
#oauth = OAuth(starlette_config)
#oauth.register(
#    name='google',
#    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
#    client_kwargs={'scope': 'openid email profile'},
#)
#app.add_middleware(SessionMiddleware, secret_key="my_secret")


def get_user(request: Request):
    user = request.session.get('user')
    if user:
        return user['email']
    return None

@app.get('/')
def public(user: dict = Depends(get_user)):
    if user:
        return RedirectResponse(url='/login-page')
    else:
        return RedirectResponse(url='/login-page')

'''
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
'''

with gr.Blocks() as login_demo:
    gr.Button("Login")#, link="/login")

app = gr.mount_gradio_app(app, login_demo, path="/login-page")

'''
def greet(request: gr.Request):
    return f"Welcome to Gradio, {request.username}"

with gr.Blocks(css=".icon-button-wrapper.top-panel { display: none !important; }") as main_demo:
    msg = gr.Textbox(show_label=False, submit_btn=True, placeholder="Ask anything", visible=True)
    main_demo.load(greet, inputs=None, outputs=[msg])

app = gr.mount_gradio_app(app, main_demo, path="/chat", auth_dependency=get_user)
'''
