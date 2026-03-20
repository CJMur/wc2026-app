import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# --- CONFIG & SETUP ---
st.set_page_config(page_title="World Cup Draft", layout="wide")
st.title("🏆 World Cup Team Draft & Tracker")

# Connect to Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# Fetch fresh data from sheets (ttl=0 ensures no caching)
users_df = conn.read(worksheet="Users", ttl=0).dropna(how="all")
teams_df = conn.read(worksheet="Teams", ttl=0).dropna(how="all")
matches_df = conn.read(worksheet="Matches", ttl=0).dropna(how="all")

# Populate 32 World Cup Teams if the sheet is empty
if teams_df.empty or len(teams_df) < 32:
    wc_teams = [
        "Argentina", "Australia", "Belgium", "Brazil", "Cameroon", "Canada", "Costa Rica", "Croatia",
        "Denmark", "Ecuador", "England", "France", "Germany", "Ghana", "Iran", "Japan",
        "Mexico", "Morocco", "Netherlands", "Poland", "Portugal", "Qatar", "Saudi Arabia", "Senegal",
        "Serbia", "South Korea", "Spain", "Switzerland", "Tunisia", "United States", "Uruguay", "Wales"
    ]
    teams_df = pd.DataFrame({
        "Team": wc_teams,
        "Owner": [None] * 32,
        "Is_Drafted": [False] * 32
    })
    conn.update(worksheet="Teams", data=teams_df)
    st.rerun()

# --- UI TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["👥 Registration", "📋 The Draft", "⚽ Log Matches", "🏆 Leaderboard"])

# 1. REGISTRATION TAB
with tab1:
    st.header("Register for the League")
    st.write("Maximum of 6 players allowed.")
    
    current_users = users_df["Name"].tolist() if not users_df.empty else []
    st.write(f"**Current Players ({len(current_users)}/6):** {', '.join(current_users) if current_users else 'None'}")
    
    if len(current_users) < 6:
        new_user = st.text_input("Enter your name:")
        if st.button("Register"):
            if new_user and new_user not in current_users:
                # Add new user and update sheet
                new_row = pd.DataFrame([{"Name": new_user}])
                updated_users = pd.concat([users_df, new_row], ignore_index=True)
                conn.update(worksheet="Users", data=updated_users)
                st.success(f"{new_user} registered successfully!")
                st.rerun()
            elif new_user in current_users:
                st.error("Name already exists.")
    else:
        st.warning("The league is full! (6 players max)")

# 2. DRAFT TAB
with tab2:
    st.header("Draft Your Teams")
    current_users = users_df["Name"].tolist() if not users_df.empty else []
    
    if not current_users:
        st.info("Waiting for players to register...")
    else:
        drafted_count = len(teams_df[teams_df["Is_Drafted"] == True])
        
        if drafted_count >= 32:
            st.success("The draft is complete!")
        else:
            current_turn = current_users[drafted_count % len(current_users)]
            st.write(f"### It is currently **{current_turn}**'s turn to pick!")
            
            available_teams = teams_df[teams_df["Is_Drafted"] == False]["Team"].tolist()
            selected_team = st.selectbox("Select a team to draft:", available_teams)
            
            if st.button(f"Draft {selected_team} for {current_turn}"):
                # Update the specific team's owner and drafted status
                teams_df.loc[teams_df["Team"] == selected_team, ["Owner", "Is_Drafted"]] = [current_turn, True]
                conn.update(worksheet="Teams", data=teams_df)
                st.success(f"{selected_team} drafted by {current_turn}!")
                st.rerun()

        st.subheader("Current Rosters")
        drafted_teams = teams_df[teams_df["Is_Drafted"] == True][["Owner", "Team"]]
        if not drafted_teams.empty:
            st.dataframe(drafted_teams.sort_values(by="Owner").reset_index(drop=True), use_container_width=True)

# 3. MATCH LOGGING TAB
with tab3:
    st.header("Log Match Results")
    
    drafted_teams_list = teams_df[teams_df["Is_Drafted"] == True]["Team"].tolist()
    
    if drafted_teams_list:
        col1, col2, col3 = st.columns(3)
        with col1:
            team_played = st.selectbox("Select Team:", drafted_teams_list)
        with col2:
            match_result = st.selectbox("Result:", ["Win", "Draw", "Loss"])
        with col3:
            stage = st.selectbox("Tournament Stage:", ["Group Stage", "Finals/Knockout"])
        
        if st.button("Log Result"):
            points = 3 if match_result == "Win" else 1 if match_result == "Draw" else 0
            if stage == "Finals/Knockout":
                points *= 2
                
            new_match = pd.DataFrame([{
                "Team": team_played, 
                "Result": match_result, 
                "Stage": stage, 
                "Points": points
            }])
            updated_matches = pd.concat([matches_df, new_match], ignore_index=True)
            conn.update(worksheet="Matches", data=updated_matches)
            
            st.success(f"Logged {match_result} for {team_played} ({points} points awarded).")
            st.rerun()
    else:
        st.info("Draft some teams first before logging matches!")

# 4. LEADERBOARD TAB
with tab4:
    st.header("Live Leaderboard")
    if st.button("Refresh Standings"):
        st.rerun()
        
    if not teams_df.empty and not matches_df.empty:
        # Merge teams and matches to calculate points per owner
        merged_df = pd.merge(teams_df, matches_df, on="Team", how="left")
        
        # Calculate scores
        leaderboard = merged_df.groupby("Owner")["Points"].sum().reset_index()
        leaderboard = leaderboard.sort_values(by="Points", ascending=False).reset_index(drop=True)
        leaderboard["Points"] = leaderboard["Points"].fillna(0).astype(int)
        
        st.dataframe(leaderboard, use_container_width=True)
    elif not teams_df[teams_df["Is_Drafted"] == True].empty:
        # Show drafted players with 0 points if no matches logged yet
        owners = teams_df[teams_df["Is_Drafted"] == True]["Owner"].unique()
        empty_leaderboard = pd.DataFrame({"Owner": owners, "Points": [0] * len(owners)})
        st.dataframe(empty_leaderboard, use_container_width=True)
    else:
        st.write("No points scored yet.")
