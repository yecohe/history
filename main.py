import streamlit as st
import uuid
import random
from PIL import Image
from io import BytesIO

st.set_page_config(page_title="Show Your History", layout="wide")

st.title("📸 Show Your History")

# Game session state
if "game_id" not in st.session_state:
    st.session_state.game_id = None
if "players" not in st.session_state:
    st.session_state.players = {}
if "photos" not in st.session_state:
    st.session_state.photos = {}
if "guesses" not in st.session_state:
    st.session_state.guesses = {}
if "reveal" not in st.session_state:
    st.session_state.reveal = False
if "current_photo" not in st.session_state:
    st.session_state.current_photo = 0

# Initial screen: New Game or Existing Game
if st.session_state.game_id is None:
    st.subheader("Start or Join a Game")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("New Game"):
            st.session_state.game_id = str(uuid.uuid4())[:6].upper()
    with col2:
        existing_id = st.text_input("Enter Game ID")
        if st.button("Join Game") and existing_id:
            st.session_state.game_id = existing_id.upper()
    st.stop()

st.sidebar.header("Game Code")
st.sidebar.code(st.session_state.game_id)

st.subheader("1. Enter Your Name and Upload a Photo")
name = st.text_input("Your name")
photo = st.file_uploader("Upload a photo of someone you hooked up with", type=["jpg", "jpeg", "png"])

if st.button("Submit Photo"):
    if name and photo:
        st.session_state.players[name] = True
        st.session_state.photos[name] = photo.read()
        st.success("Photo submitted!")
    else:
        st.error("Please provide both your name and a photo.")

st.markdown("---")
st.subheader("2. Start the Game")

if st.button("Start Game"):
    if len(st.session_state.photos) >= 2:
        st.session_state.shuffled_photos = list(st.session_state.photos.items())
        random.shuffle(st.session_state.shuffled_photos)
    else:
        st.error("At least two players need to submit photos to start the game.")

if "shuffled_photos" in st.session_state:
    st.markdown("### 3. Match Photos to Players")
    current_player = st.selectbox("Who are you?", list(st.session_state.players.keys()))

    if current_player not in st.session_state.guesses:
        st.session_state.guesses[current_player] = {}

    for i, (real_name, img_data) in enumerate(st.session_state.shuffled_photos):
        col1, col2 = st.columns([1, 2])
        with col1:
            st.image(Image.open(BytesIO(img_data)), width=150)
        with col2:
            guess = st.selectbox(
                f"Who uploaded this photo? (Photo {i+1})",
                options=["--"] + list(st.session_state.players.keys()),
                key=f"guess_{current_player}_{i}"
            )
            if guess != "--":
                st.session_state.guesses[current_player][i] = guess

    if st.button("Submit Guesses"):
        st.success("Guesses saved!")

    st.markdown("---")
    if st.button("Reveal Answers"):
        st.session_state.reveal = True

if st.session_state.reveal:
    st.markdown("## 🔍 Reveal Phase")
    for i, (real_name, img_data) in enumerate(st.session_state.shuffled_photos):
        st.image(Image.open(BytesIO(img_data)), width=250)
        st.markdown(f"**Actual player:** {real_name}")
        st.markdown("**Guesses:**")
        for player, guesses in st.session_state.guesses.items():
            guess = guesses.get(i, "No guess")
            st.write(f"- {player} guessed: {guess}")
        st.markdown("---")

    st.markdown("## 🏆 Final Scores")
    scores = {}
    for player, guesses in st.session_state.guesses.items():
        score = sum(
            1 for i, (real_name, _) in enumerate(st.session_state.shuffled_photos)
            if guesses.get(i) == real_name
        )
        scores[player] = score
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    for player, score in sorted_scores:
        st.write(f"{player}: {score} correct matches")
