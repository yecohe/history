import streamlit as st
import uuid
import random
from PIL import Image
from io import BytesIO
import sqlite3
import datetime

# SQLite setup
conn = sqlite3.connect("game_data.db")
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS games (
    game_id TEXT PRIMARY KEY,
    created_at TEXT,
    status TEXT,
    host TEXT
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

# Session state
for key in ["game_id", "name", "screen", "is_host"]:
    if key not in st.session_state:
        st.session_state[key] = None if key != "screen" else "lobby"

# --- Lobby Screen ---
if st.session_state.screen == "lobby":
    st.subheader("🎮 Lobby")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("New Game"):
            game_id = str(uuid.uuid4())[:6].upper()
            created_at = datetime.datetime.now().isoformat()
            st.session_state.is_host = True
            st.session_state.screen = "upload"
            st.session_state.game_id = game_id
            st.session_state.name = st.text_input("Your name", key="host_name")
            if st.session_state.name:
                c.execute("INSERT INTO games (game_id, created_at, status, host) VALUES (?, ?, ?, ?)",
                          (game_id, created_at, "waiting", st.session_state.name))
                conn.commit()
    with col2:
        name = st.text_input("Your name", key="join_name")
        game_id = st.text_input("Enter Game ID")
        if st.button("Join Game") and name and game_id:
            c.execute("SELECT * FROM games WHERE game_id = ?", (game_id.upper(),))
            if c.fetchone():
                st.session_state.game_id = game_id.upper()
                st.session_state.name = name
                st.session_state.is_host = False
                st.session_state.screen = "upload"
            else:
                st.error("Game ID not found")

# --- Upload Screen ---
elif st.session_state.screen == "upload":
    st.sidebar.header("Game Code")
    st.sidebar.code(st.session_state.game_id)
    st.header(f"👤 Welcome, {st.session_state.name}")
    photo = st.file_uploader("Upload a photo of someone you hooked up with", type=["jpg", "jpeg", "png"])
    if st.button("Submit Photo") and photo:
        c.execute("SELECT * FROM players WHERE game_id = ? AND name = ?",
                  (st.session_state.game_id, st.session_state.name))
        if not c.fetchone():
            c.execute("INSERT INTO players (game_id, name, photo) VALUES (?, ?, ?)",
                      (st.session_state.game_id, st.session_state.name, photo.read()))
            conn.commit()
            st.success("Photo submitted!")
        else:
            st.warning("You already submitted a photo.")

    if st.session_state.is_host and st.button("Start Game"):
        c.execute("SELECT COUNT(*) FROM players WHERE game_id = ?", (st.session_state.game_id,))
        if c.fetchone()[0] >= 2:
            c.execute("UPDATE games SET status = 'started' WHERE game_id = ?", (st.session_state.game_id,))
            conn.commit()
            st.session_state.screen = "game"
        else:
            st.error("Need at least 2 players.")

# --- Game Screen ---
elif st.session_state.screen == "game":
    st.sidebar.header("Game Code")
    st.sidebar.code(st.session_state.game_id)
    st.header("🖼️ Match Photos to Players")
    c.execute("SELECT name, photo FROM players WHERE game_id = ?", (st.session_state.game_id,))
    photo_entries = c.fetchall()
    players = [entry[0] for entry in photo_entries]
    shuffled = list(enumerate(photo_entries))
    random.seed(st.session_state.game_id)
    random.shuffle(shuffled)

    for idx, (i, (pname, img_data)) in enumerate(shuffled):
        st.image(Image.open(BytesIO(img_data)), width=150)
        guess = st.selectbox(
            f"Who uploaded this photo? (Photo {idx+1})",
            options=["--"] + players,
            key=f"guess_{idx}"
        )
        if guess != "--":
            c.execute("REPLACE INTO guesses (game_id, guesser, photo_index, guessed) VALUES (?, ?, ?, ?)",
                      (st.session_state.game_id, st.session_state.name, idx, guess))
            conn.commit()

    if st.session_state.is_host and st.button("Reveal Answers"):
        c.execute("UPDATE games SET status = 'reveal' WHERE game_id = ?", (st.session_state.game_id,))
        conn.commit()
        st.session_state.screen = "reveal"

# --- Reveal Screen ---
elif st.session_state.screen == "reveal":
    st.sidebar.header("Game Code")
    st.sidebar.code(st.session_state.game_id)
    st.header("🔍 Reveal Phase")
    c.execute("SELECT name, photo FROM players WHERE game_id = ?", (st.session_state.game_id,))
    photo_entries = c.fetchall()
    shuffled = list(enumerate(photo_entries))
    random.seed(st.session_state.game_id)
    random.shuffle(shuffled)

    for idx, (i, (real_name, img_data)) in enumerate(shuffled):
        st.image(Image.open(BytesIO(img_data)), width=250)
        st.markdown(f"**Actual player:** {real_name}")
        c.execute("SELECT guesser, guessed FROM guesses WHERE game_id = ? AND photo_index = ?",
                  (st.session_state.game_id, idx))
        for guesser, guessed in c.fetchall():
            st.write(f"- {guesser} guessed: {guessed}")
        st.markdown("---")

    st.subheader("🏆 Final Scores")
    c.execute("SELECT DISTINCT guesser FROM guesses WHERE game_id = ?", (st.session_state.game_id,))
    guessers = [row[0] for row in c.fetchall()]
    scores = {}
    for guesser in guessers:
        score = 0
        for idx, (i, (real_name, _)) in enumerate(shuffled):
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
        c.execute("DELETE FROM guesses WHERE game_id = ?", (st.session_state.game_id,))
        c.execute("UPDATE players SET photo = NULL WHERE game_id = ?", (st.session_state.game_id,))
        c.execute("DELETE FROM players WHERE game_id = ?", (st.session_state.game_id,))
        conn.commit()
        st.success("Game finished and all data deleted.")
