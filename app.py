import os
import requests
from flask import Flask, request, redirect, render_template
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
db = SQLAlchemy(app)

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
BOT_TOKEN = os.getenv("BOT_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")
REDIRECT_URI = os.getenv("REDIRECT_URI")
LOG_CHANNEL = os.getenv("LOG_CHANNEL")

ROLE_ADD = os.getenv("ROLE_ADD")
ROLE_REMOVE = os.getenv("ROLE_REMOVE")

class Verified(db.Model):
    id = db.Column(db.String(50), primary_key=True)
    username = db.Column(db.String(100))
    verified_at = db.Column(db.DateTime, default=datetime.utcnow)

@app.route("/")
def home():
    count = Verified.query.count()
    return render_template("index.html", count=count)

@app.route("/login")
def login():
    return redirect(
        f"https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=identify%20guilds.join"
    )

@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return "Fehler: Kein Code erhalten.", 400

    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }

    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    r = requests.post("https://discord.com/api/oauth2/token", data=data, headers=headers)
    token_json = r.json()
    access_token = token_json.get("access_token")
    if not access_token:
        return "Fehler beim Abrufen des Tokens.", 400

    user = requests.get(
        "https://discord.com/api/users/@me",
        headers={"Authorization": f"Bearer {access_token}"}
    ).json()

    user_id = user["id"]
    username = f'{user["username"]}#{user["discriminator"]}'

    # User zum Server hinzufügen
    requests.put(
        f"https://discord.com/api/guilds/{GUILD_ID}/members/{user_id}",
        headers={"Authorization": f"Bot {BOT_TOKEN}"},
        json={"access_token": access_token},
    )

    # Rolle hinzufügen
    requests.put(
        f"https://discord.com/api/guilds/{GUILD_ID}/members/{user_id}/roles/{ROLE_ADD}",
        headers={"Authorization": f"Bot {BOT_TOKEN}"}
    )

    # Alte Rolle entfernen
    requests.delete(
        f"https://discord.com/api/guilds/{GUILD_ID}/members/{user_id}/roles/{ROLE_REMOVE}",
        headers={"Authorization": f"Bot {BOT_TOKEN}"}
    )

    # In Datenbank speichern
    if not Verified.query.get(user_id):
        new_user = Verified(id=user_id, username=username)
        db.session.add(new_user)
        db.session.commit()

    # Logging
    if LOG_CHANNEL:
        requests.post(
            f"https://discord.com/api/channels/{LOG_CHANNEL}/messages",
            headers={"Authorization": f"Bot {BOT_TOKEN}"},
            json={"content": f"✅ {username} wurde verifiziert."}
        )

    return render_template("success.html")

@app.route("/admin")
def admin():
    users = Verified.query.all()
    return render_template("admin.html", users=users)

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
