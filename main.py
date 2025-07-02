import streamlit as st
import uuid
import random
from PIL import Image
from io import BytesIO
import firebase_admin
from firebase_admin import credentials, firestore, storage
import tempfile
import os

# Initialize Firebase
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase_credentials.json")  # Make sure this file is in your directory
    firebase_admin.initialize_app(cred, {
        'storageBucket': '<your-firebase-storage-bucket>.appspot.com'
    })
    db = firestore.client()
    bucket = storage.bucket()

st.set_page_config(page_title="Show Your History", layout="wide")

st.title("📸 Show Your History")

# Game session state
if "game_id" not in st.session_state:
    st.session_state.game_id = None
if "name" not in st.session_state:
    st.session_state.name = None

# Initial screen: New Game or Existing Game
if st.session_state.game_id is None:
    st.subheader("Start or Join a Game")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("New Game"):
            game_id = str(uuid.uuid4())[:6].upper()
            db.collection("games").document(game_id).set({
                "created_at": firestore.SERVER_TIMESTAMP,
                "status": "waiting",
                "players": {}
            })
            st.session_state.game_id = game_id
    with col2:
        existing_id = st.text_input("Enter Game ID")
        if st.button("Join Game") and existing_id:
            st.session_state.game_id = existing_id.upper()
    st.stop()

st.sidebar.header("Game Code")
st.sidebar.code(st.session_state.game_id)

game_ref = db.collection("games").document(st.session_state.game_id)
st.subheader("1. Enter Your Name and Upload a Photo")
name = st.text_input("Your name")
photo = st.file_uploader("Upload a photo of someone you hooked up with", type=["jpg", "jpeg", "png"])

if st.button("Submit Photo"):
    if name and photo:
        st.session_state.name = name
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_file.write(photo.read())
        temp_file.close()

        blob = bucket.blob(f"games/{st.session_state.game_id}/photos/{name}.jpg")
        blob.upload_from_filename(temp_file.name)
        blob.make_public()
        os.remove(temp_file.name)

        game_ref.update({f"players.{name}": {"photo_url": blob.public_url, "guesses": {}}})
        st.success("Photo uploaded and saved!")
    else:
        st.error("Please provide both your name and a photo.")

st.markdown("---")
st.subheader("2. Start the Game")

if st.button("Start Game"):
    game_doc = game_ref.get()
    if game_doc.exists:
        players = game_doc.to_dict().get("players", {})
        if len(players) >= 2:
            game_ref.update({"status": "started"})
        else:
            st.error("At least two players need to submit photos to start the game.")

# Load game data
game_doc = game_ref.get().to_dict()
if game_doc.get("status") in ["started", "guessing", "reveal"]:
    st.markdown("### 3. Match Photos to Players")
    players = list(game_doc["players"].keys())
    current_player = st.session_state.name or st.selectbox("Who are you?", players)

    if current_player and st.button("I'm Ready to Guess"):
        st.session_state.name = current_player

    if st.session_state.name:
        for idx, (pname, pdata) in enumerate(game_doc["players"].items()):
            st.image(pdata["photo_url"], width=150)
            guess = st.selectbox(
                f"Who uploaded this photo? (Photo {idx+1})",
                options=["--"] + players,
                key=f"guess_{idx}"
            )
            if guess != "--":
                game_ref.update({f"players.{current_player}.guesses.{idx}": guess})

    if st.button("Reveal Answers"):
        game_ref.update({"status": "reveal"})

if game_doc.get("status") == "reveal":
    st.markdown("## 🔍 Reveal Phase")
    for idx, (pname, pdata) in enumerate(game_doc["players"].items()):
        st.image(pdata["photo_url"], width=250)
        st.markdown(f"**Actual player:** {pname}")
        st.markdown("**Guesses:**")
        for guesser, gdata in game_doc["players"].items():
            guess = gdata.get("guesses", {}).get(str(idx), "No guess")
            st.write(f"- {guesser} guessed: {guess}")
        st.markdown("---")

    st.markdown("## 🏆 Final Scores")
    scores = {}
    for guesser, gdata in game_doc["players"].items():
        score = 0
        for idx, (real_name, _) in enumerate(game_doc["players"].items()):
            correct = guesser != real_name and gdata.get("guesses", {}).get(str(idx)) == real_name
            if correct:
                score += 1
        scores[guesser] = score
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    for player, score in sorted_scores:
        st.write(f"{player}: {score} correct matches")
