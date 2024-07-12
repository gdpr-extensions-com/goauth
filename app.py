import identity.web
import requests
from flask import Flask, redirect, render_template, request, session, url_for
from flask_session import Session
from werkzeug.middleware.proxy_fix import ProxyFix
from cryptography.fernet import Fernet
import app_config

__version__ = "0.8.0"  # The version of this sample, for troubleshooting purposes

app = Flask(__name__)
app.config.from_object(app_config)
assert app.config["REDIRECT_PATH"] != "/", "REDIRECT_PATH must not be /"
Session(app)

app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

app.jinja_env.globals.update(Auth=identity.web.Auth)  # Useful in template for B2C
auth = identity.web.Auth(
    session=session,
    authority=app.config["AUTHORITY"],
    client_id=app.config["CLIENT_ID"],
    client_credential=app.config["CLIENT_SECRET"],
)

# Ensure you store this key securely
encryption_key = '6jnxS0LbauUL0vJLaD7-kjx0zVHPmvU6DmQo0NKVKLc='
cipher_suite = Fernet(encryption_key)

def get_user_group_ids(access_token):
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get("https://graph.microsoft.com/v1.0/me/memberOf", headers=headers)
    response.raise_for_status()  # Raise an HTTPError for bad responses
    groups_info = response.json()
    group_ids = [group['id'] for group in groups_info.get('value', [])]
    return group_ids

def encrypt_group_ids(group_ids_str):
    try:
        encrypted_group_ids = cipher_suite.encrypt(group_ids_str.encode()).decode()
        return encrypted_group_ids
    except Exception as e:
        print(f"Encryption error: {e}")
        return None

@app.route("/login")
def login():
    return render_template("login.html", version=__version__, **auth.log_in(
        scopes=app_config.SCOPE,  # Have user consent to scopes during log-in
        redirect_uri=url_for("auth_response", _external=True),  # Optional. If present, this absolute URL must match your app's redirect_uri registered in Azure Portal
        prompt="select_account",  # Optional. More values defined in https://openid.net/specs/openid-connect-core-1_0.html#AuthRequest
    ))

@app.route(app_config.REDIRECT_PATH)
def auth_response():
    result = auth.complete_log_in(request.args)
    if "error" in result:
        return render_template("auth_error.html", result=result)
    return redirect(url_for("index"))

@app.route("/")
def index():
    if not (app.config["CLIENT_ID"] and app.config["CLIENT_SECRET"]):
        return render_template('config_error.html')
    if not auth.get_user():
        return redirect(url_for("login"))

    try:
        token = auth.get_token_for_user(app_config.SCOPE)
        user = get_user_details(token['access_token'])
        group_ids = get_user_group_ids(token['access_token'])
        group_ids_str = ','.join(group_ids)

        encrypted_group_ids = encrypt_group_ids(group_ids_str)

        if encrypted_group_ids is None:
            raise Exception("Failed to encrypt group IDs")

        return redirect(f'http://localhost:3000/?gid={encrypted_group_ids}')

    except Exception as e:
        print(f"Error in index route: {e}")
        return render_template('error.html', error_message=str(e)), 500

@app.route("/logout")
def logout():
    return redirect(auth.log_out(url_for("index", _external=True)))

@app.route("/call_downstream_api")
def call_downstream_api():
    token = auth.get_token_for_user(app_config.SCOPE)
    if "error" in token:
        return redirect(url_for("login"))
    api_result = requests.get(
        app_config.ENDPOINT,
        headers={'Authorization': 'Bearer ' + token['access_token']},
        timeout=30,
    ).json()
    return render_template('display.html', result=api_result)

def get_user_details(access_token):
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get(app.config['ENDPOINT'], headers=headers)
    response.raise_for_status()
    user_info = response.json()
    return user_info

if __name__ == "__main__":
    app.run(debug=True)
