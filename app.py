import streamlit as st
import sqlite3
import pandas as pd

# --- CONFIG & SETUP ---
st.set_page_config(page_title="World Cup Draft", layout="wide")
st.title("🏆 World Cup Team Draft & Tracker")

# Initialize database (Local SQLite)
# Note: On Streamlit Cloud, SQLite resets if the app sleeps. 
# For long-term production, swap this with Supabase, Firebase, or Google Sheets.
conn = sqlite3.connect('worldcup_draft.db', check_same_thread=False)
c = conn.cursor()

def init_db():
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT UNIQUE)')
    c.execute('''CREATE TABLE IF NOT EXISTS teams 
                 (name TEXT PRIMARY KEY, owner TEXT, is_drafted BOOLEAN)''')
    c.execute('''CREATE TABLE IF NOT EXISTS matches 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, team TEXT, result TEXT, stage TEXT, points INTEGER)''')
    conn.commit()

    # Populate 32 World Cup Teams if empty
    c.execute('SELECT count(*) FROM teams')
    if c.fetchone()[0] == 0:
        wc_teams = [
            "Argentina", "Australia", "Belgium", "Brazil", "Cameroon", "Canada", "Costa Rica", "Croatia",
            "Denmark", "Ecuador", "England", "France", "Germany", "Ghana", "Iran", "Japan",
            "Mexico", "Morocco", "Netherlands", "Poland", "Portugal", "Qatar", "Saudi Arabia", "Senegal",
            "Serbia", "South Korea", "Spain", "Switzerland", "Tunisia", "United States", "Uruguay", "Wales"
        ]
        for team in wc_teams:
            c.execute('INSERT INTO teams (name, owner, is_drafted) VALUES (?, ?, ?)', (team, None, False))
        conn.commit()

init_db()

# --- HELPER FUNCTIONS ---
def get_users():
    return [row[0] for row in c.execute('SELECT name FROM users').fetchall()]

def get_available_teams():
    return [row[0] for row in c.execute('SELECT name FROM teams WHERE is_drafted = False').fetchall()]

# --- UI TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["👥 Registration", "📋 The Draft", "⚽ Log Matches", "🏆 Leaderboard"])

# 1. REGISTRATION TAB
with tab1:
    st.header("Register for the League")
    st.write("Maximum of 6 players allowed.")
    
    users = get_users()
    st.write(f"**Current Players ({len(users)}/6):** {', '.join(users) if users else 'None'}")
    
    if len(users) < 6:
        new_user = st.text_input("Enter your name:")
        if st.button("Register"):
            if new_user and new_user not in users:
                c.execute('INSERT INTO users (name) VALUES (?)', (new_user,))
                conn.commit()
                st.success(f"{new_user} registered successfully!")
                st.rerun()
            elif new_user in users:
                st.error("Name already exists.")
    else:
        st.warning("The league is full! (6 players max)")

# 2. DRAFT TAB
with tab2:
    st.header("Draft Your Teams")
    users = get_users()
    
    if not users:
        st.info("Waiting for players to register...")
    else:
        # Determine whose turn it is based on number of drafted teams
        c.execute('SELECT count(*) FROM teams WHERE is_drafted = True')
        drafted_count = c.fetchone()[0]
        
        if drafted_count >= 32:
            st.success("The draft is complete!")
        else:
            current_turn = users[drafted_count % len(users)]
            st.write(f"### It is currently **{current_turn}**'s turn to pick!")
            
            available_teams = get_available_teams()
            selected_team = st.selectbox("Select a team to draft:", available_teams)
            
            if st.button(f"Draft {selected_team} for {current_turn}"):
                c.execute('UPDATE teams SET owner = ?, is_drafted = True WHERE name = ?', (current_turn, selected_team))
                conn.commit()
                st.success(f"{selected_team} drafted by {current_turn}!")
                st.rerun()

        st.subheader("Current Rosters")
        rosters = pd.read_sql_query('SELECT owner as Player, name as Team FROM teams WHERE is_drafted = True', conn)
        if not rosters.empty:
            st.dataframe(rosters.sort_values(by="Player"), use_container_width=True)

# 3. MATCH LOGGING TAB
with tab3:
    st.header("Log Match Results")
    st.write("Add points to your teams based on their real-world performance.")
    
    c.execute('SELECT name FROM teams WHERE is_drafted = True')
    drafted_teams = [row[0] for row in c.fetchall()]
    
    if drafted_teams:
        col1, col2, col3 = st.columns(3)
        with col1:
            team_played = st.selectbox("Select Team:", drafted_teams)
        with col2:
            match_result = st.selectbox("Result:", ["Win", "Draw", "Loss"])
        with col3:
            stage = st.selectbox("Tournament Stage:", ["Group Stage", "Finals/Knockout"])
        
        if st.button("Log Result"):
            # Calculate Points
            points = 0
            if match_result == "Win":
                points = 3
            elif match_result == "Draw":
                points = 1
                
            # Double points for finals
            if stage == "Finals/Knockout":
                points *= 2
                
            c.execute('INSERT INTO matches (team, result, stage, points) VALUES (?, ?, ?, ?)', 
                      (team_played, match_result, stage, points))
            conn.commit()
            st.success(f"Logged {match_result} for {team_played} ({points} points awarded).")
    else:
        st.info("Draft some teams first before logging matches!")

# 4. LEADERBOARD TAB
with tab4:
    st.header("Live Leaderboard")
    if st.button("Refresh Standings"):
        st.rerun()
        
    query = '''
        SELECT t.owner as Player, SUM(m.points) as Total_Points
        FROM teams t
        LEFT JOIN matches m ON t.name = m.team
        WHERE t.owner IS NOT NULL
        GROUP BY t.owner
        ORDER BY Total_Points DESC
    '''
    leaderboard = pd.read_sql_query(query, conn)
    
    # Fill NaN with 0 for users who haven't scored yet
    leaderboard['Total_Points'] = leaderboard['Total_Points'].fillna(0).astype(int)
    
    if not leaderboard.empty:
        st.dataframe(leaderboard, use_container_width=True)
    else:
        st.write("No points scored yet.")
