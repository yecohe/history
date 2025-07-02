import streamlit as st
import uuid
import random
from PIL import Image
from io import BytesIO
import os
import tempfile
import sqlite3
import datetime

# SQLite setup
conn = sqlite3.connect("game_data.db")
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS games (
    game_id TEXT PRIMARY KEY,
    created_at TEXT,
    status TEXT
)''')
c.execute('''CREATE TABLE IF NOT EXISTS players (
    game_id TEXT,
    name TEXT,
    photo BLOB,
    PRIMARY KEY (game_id, name)
)''')
c.execute('''CREATE TABLE IF NOT EXISTS guesses (
    game_id TEXT,
    guesser TEXT,
    photo_index INTEGER,
    guessed TEXT
)''')
conn.commit()

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
            created_at = datetime.datetime.now().isoformat()
            c.execute("INSERT INTO games (game_id, created_at, status) VALUES (?, ?, ?)", (game_id, created_at, "waiting"))
            conn.commit()
            st.session_state.game_id = game_id
    with col2:
        existing_id = st.text_input("Enter Game ID")
        if st.button("Join Game") and existing_id:
            c.execute("SELECT * FROM games WHERE game_id = ?", (existing_id.upper(),))
            if c.fetchone():
                st.session_state.game_id = existing_id.upper()
            else:
                st.error("Game ID not found")
    st.stop()

st.sidebar.header("Game Code")
st.sidebar.code(st.session_state.game_id)

st.subheader("1. Enter Your Name and Upload a Photo")
name = st.text_input("Your name")
photo = st.file_uploader("Upload a photo of someone you hooked up with", type=["jpg", "jpeg", "png"])

if st.button("Submit Photo"):
    if name and photo:
        st.session_state.name = name
        c.execute("SELECT * FROM players WHERE game_id = ? AND name = ?", (st.session_state.game_id, name))
        if not c.fetchone():
            photo_data = photo.read()
            c.execute("INSERT INTO players (game_id, name, photo) VALUES (?, ?, ?)", (st.session_state.game_id, name, photo_data))
            conn.commit()
            st.success("Photo uploaded and saved!")
        else:
            st.warning("You have already submitted a photo.")
    else:
        st.error("Please provide both your name and a photo.")

st.markdown("---")
st.subheader("2. Start the Game")

if st.button("Start Game"):
    c.execute("SELECT COUNT(*) FROM players WHERE game_id = ?", (st.session_state.game_id,))
    if c.fetchone()[0] >= 2:
        c.execute("UPDATE games SET status = 'started' WHERE game_id = ?", (st.session_state.game_id,))
        conn.commit()
    else:
        st.error("At least two players need to submit photos to start the game.")

# Load game status
c.execute("SELECT status FROM games WHERE game_id = ?", (st.session_state.game_id,))
game_status = c.fetchone()[0]

if game_status in ["started", "reveal"]:
    st.markdown("### 3. Match Photos to Players")
    c.execute("SELECT name, photo FROM players WHERE game_id = ?", (st.session_state.game_id,))
    photo_entries = c.fetchall()
    players = [entry[0] for entry in photo_entries]
    random.seed(st.session_state.game_id)
    shuffled = list(enumerate(photo_entries))
    random.shuffle(shuffled)

    current_player = st.session_state.name or st.selectbox("Who are you?", players)

    if current_player and st.button("I'm Ready to Guess"):
        st.session_state.name = current_player

    if st.session_state.name:
        for idx, (original_index, (pname, img_data)) in enumerate(shuffled):
            st.image(Image.open(BytesIO(img_data)), width=150)
            guess = st.selectbox(
                f"Who uploaded this photo? (Photo {idx+1})",
                options=["--"] + players,
                key=f"guess_{idx}"
            )
            if guess != "--":
                c.execute("REPLACE INTO guesses (game_id, guesser, photo_index, guessed) VALUES (?, ?, ?, ?)",
                          (st.session_state.game_id, current_player, idx, guess))
                conn.commit()

    if st.button("Reveal Answers"):
        c.execute("UPDATE games SET status = 'reveal' WHERE game_id = ?", (st.session_state.game_id,))
        conn.commit()

if game_status == "reveal":
    st.markdown("## 🔍 Reveal Phase")
    for idx, (original_index, (pname, img_data)) in enumerate(shuffled):
        st.image(Image.open(BytesIO(img_data)), width=250)
        st.markdown(f"**Actual player:** {pname}")
        st.markdown("**Guesses:**")
        c.execute("SELECT guesser, guessed FROM guesses WHERE game_id = ? AND photo_index = ?", (st.session_state.game_id, idx))
        for guesser, guessed in c.fetchall():
            st.write(f"- {guesser} guessed: {guessed}")
        st.markdown("---")

    st.markdown("## 🏆 Final Scores")
    c.execute("SELECT DISTINCT guesser FROM guesses WHERE game_id = ?", (st.session_state.game_id,))
    guessers = [row[0] for row in c.fetchall()]
    scores = {}
    for guesser in guessers:
        score = 0
        for idx, (original_index, (real_name, _)) in enumerate(shuffled):
            c.execute("SELECT guessed FROM guesses WHERE game_id = ? AND guesser = ? AND photo_index = ?",
                      (st.session_state.game_id, guesser, idx))
            row = c.fetchone()
            if row and row[0] == real_name and guesser != real_name:
                score += 1
        scores[guesser] = score
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    for player, score in sorted_scores:
        st.write(f"{player}: {score} correct matches")

    if st.button("Finish Game and Delete Data"):
        c.execute("DELETE FROM games WHERE game_id = ?", (st.session_state.game_id,))
        c.execute("DELETE FROM players WHERE game_id = ?", (st.session_state.game_id,))
        c.execute("DELETE FROM guesses WHERE game_id = ?", (st.session_state.game_id,))
        conn.commit()
        st.success("Game finished and all data deleted from database.")
