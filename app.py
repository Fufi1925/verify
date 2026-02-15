import os
import requests
from flask import Flask, redirect, render_template
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# === ENV VARS ===
CLIENT_ID = os.getenv("CLIENT_ID")       # Discord App Client ID
CLIENT_SECRET = os.getenv("CLIENT_SECRET") # Discord App Secret
BOT_TOKEN = os.getenv("BOT_TOKEN")       # Bot Token
GUILD_ID = os.getenv("GUILD_ID")         # Dein Server
REDIRECT_URI = os.getenv("REDIRECT_URI") # z.B. https://deine-seite.onrender.com/callback
LOG_CHANNEL = os.getenv("LOG_CHANNEL")   # Channel für Embed posten
ROLE_ADD = os.getenv("ROLE_ADD")         # Rolle die man bekommt
ROLE_REMOVE = os.getenv("ROLE_REMOVE")   # Rolle die entfernt wird

# === FLASK INIT ===
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# === DATABASE ===
class Verified(db.Model):
    id = db.Column(db.String(50), primary_key=True)
    username = db.Column(db.String(100))
    verified_at = db.Column(db.DateTime, default=datetime.utcnow)

# === AUTOMATISCHES EMBED POSTEN ===
def post_verification_embed():
    if not LOG_CHANNEL:
        return
    url = f"https://discord.com/api/channels/{LOG_CHANNEL}/messages"
    headers = {"Authorization": f"Bot {BOT_TOKEN}"}
    json = {
        "username": "Botium",
        "embeds": [
            {
                "title": "Verifizierung",
                "description": "Klicke auf den Button unten, um dich zu verifizieren!",
                "color": 5763719,
                "footer": {"text": "Created by L"}
            }
        ],
        "components": [
            {
                "type": 1,
                "components": [
                    {
                        "type": 2,
                        "label": "Verifizieren",
                        "style": 5,  # Link-Button
                        "url": f"https://discord.com/oauth2/authorize?client_id={CLIENT_ID}&permissions=268435584&scope=identify%20guilds.join&redirect_uri={REDIRECT_URI}&response_type=code"
                        # permissions=268435584 → Banner + Server-Mitglied hinzufügen
                    }
                ]
            }
        ]
    }
    requests.post(url, headers=headers, json=json)

# === ROUTES ===
@app.route("/")
def home():
    count = Verified.query.count()
    return f"Verifizierte Nutzer: {count}"

@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return "Fehler: Kein Code erhalten", 400

    # Token holen
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    token_res = requests.post("https://discord.com/api/oauth2/token", data=data, headers=headers)
    token_json = token_res.json()
    access_token = token_json.get("access_token")
    if not access_token:
        return "Fehler beim Token", 400

    # User Info
    user = requests.get(
        "https://discord.com/api/users/@me",
        headers={"Authorization": f"Bearer {access_token}"}
    ).json()
    user_id = user["id"]
    username = f'{user["username"]}#{user["discriminator"]}'

    # Server join
    requests.put(
        f"https://discord.com/api/guilds/{GUILD_ID}/members/{user_id}",
        headers={"Authorization": f"Bot {BOT_TOKEN}"},
        json={"access_token": access_token}
    )

    # Rollen setzen/entfernen
    requests.put(f"https://discord.com/api/guilds/{GUILD_ID}/members/{user_id}/roles/{ROLE_ADD}",
                 headers={"Authorization": f"Bot {BOT_TOKEN}"})
    requests.delete(f"https://discord.com/api/guilds/{GUILD_ID}/members/{user_id}/roles/{ROLE_REMOVE}",
                    headers={"Authorization": f"Bot {BOT_TOKEN}"})

    # DB speichern
    if not Verified.query.get(user_id):
        new_user = Verified(id=user_id, username=username)
        db.session.add(new_user)
        db.session.commit()

    # Weiterleitung nach erfolgreicher Verifizierung
    return redirect("https://rover.link/login")

# === MAIN ===
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        post_verification_embed()  # Embed automatisch posten
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
