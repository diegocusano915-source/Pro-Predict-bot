"""
ProPredict Auto-Posting Bot
Posts sports predictions 3x per week: Mon (recap), Wed (midweek), Fri (weekend preview)
"""

import requests
import schedule
import time
import json
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

load_dotenv()

# ============ CONFIG ============
SITE_URL = os.getenv("PROPREDICT_URL", "https://propredict-app.onrender.com")
EMAIL = os.getenv("PROPREDICT_EMAIL", "propredict.support@gmail.com")
PASSWORD = os.getenv("PROPREDICT_PASSWORD")
AI_KEY = os.getenv("GEMINI_API_KEY")
SPORTSDB_KEY = os.getenv("THESPORTSDB_API_KEY", "123")

# ============ AUTH ============
def login():
    """Login to ProPredict and get JWT token"""
    try:
        resp = requests.post(f"{SITE_URL}/api/auth/login", json={
            "email": EMAIL,
            "password": PASSWORD
        }, timeout=15)
        data = resp.json()
        if "token" in data:
            print("✅ Logged in successfully")
            return data["token"]
        else:
            print(f"❌ Login failed: {data}")
            return None
    except Exception as e:
        print(f"❌ Login error: {e}")
        return None


# ============ AI CONTENT GENERATION (via OpenRouter) ============
def generate_text(prompt):
    """Generate text using OpenRouter (free tier)"""
    try:
        headers = {
            "Authorization": f"Bearer {AI_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "google/gemini-2.0-flash-001",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 800
        }
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        data = resp.json()
        if "choices" in data:
            return data["choices"][0]["message"]["content"]
        else:
            print(f"❌ AI error: {data}")
            return None
    except Exception as e:
        print(f"❌ AI generation error: {e}")
        return None


# ============ SPORTS DATA ============
def get_upcoming_events(days_ahead=5):
    """Fetch upcoming events from TheSportsDB"""
    all_events = []
    
    # Leagues to check (TheSportsDB league IDs)
    leagues = [
        ("English Premier League", "4328"),
        ("Spanish La Liga", "4335"),
        ("Italian Serie A", "4332"),
        ("German Bundesliga", "4331"),
        ("French Ligue 1", "4334"),
        ("UEFA Champions League", "4480"),
    ]
    
    for league_name, league_id in leagues:
        try:
            # Get next 5 events per league
            url = f"https://www.thesportsdb.com/api/v1/json/{SPORTSDB_KEY}/eventsnextleague.php?id={league_id}"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("events"):
                    for event in data["events"][:4]:
                        event["strLeague"] = league_name
                        all_events.append(event)
        except Exception as e:
            print(f"⚠️ Failed to fetch {league_name}: {e}")
    
    return all_events


def get_recent_results(days_back=3):
    """Fetch recent match results from TheSportsDB"""
    results = []
    leagues = [
        ("English Premier League", "4328"),
        ("Spanish La Liga", "4335"),
        ("Italian Serie A", "4332"),
        ("German Bundesliga", "4331"),
    ]
    
    for league_name, league_id in leagues:
        try:
            url = f"https://www.thesportsdb.com/api/v1/json/{SPORTSDB_KEY}/eventspastleague.php?id={league_id}"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("events"):
                    for event in data["events"][:3]:
                        event["strLeague"] = league_name
                        results.append(event)
        except Exception as e:
            print(f"⚠️ Failed to fetch results for {league_name}: {e}")
    
    return results


# ============ POST TO SITE ============
def post_prediction(token, match_name, prediction_text, sport, league, confidence, odds, match_date):
    """Post a prediction to the ProPredict site"""
    try:
        payload = {
            "sport": sport,
            "league": league,
            "match_name": match_name,
            "prediction": prediction_text,
            "odds": odds,
            "confidence": confidence,
            "match_date": match_date
        }
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        resp = requests.post(
            f"{SITE_URL}/api/admin/predictions",
            headers=headers,
            json=payload,
            timeout=15
        )
        if resp.status_code == 200:
            print(f"  ✅ Posted: {match_name}")
            return True
        else:
            print(f"  ❌ Failed to post {match_name}: {resp.text}")
            return False
    except Exception as e:
        print(f"  ❌ Error posting {match_name}: {e}")
        return False


# ============ MAIN TASKS ============
def monday_weekend_recap():
    """Monday: Recap weekend results"""
    print("\n📅 MONDAY - Weekend Recap")
    print("=" * 50)
    
    token = login()
    if not token:
        print("❌ Skipping - login failed")
        return
    
    results = get_recent_results()
    if len(results) < 2:
        print("⚠️ Not enough results found, skipping")
        return
    
    # Pick 3-4 interesting results
    selected = random.sample(results, min(4, len(results)))
    
    for event in selected:
        home = event.get("strHomeTeam", "Unknown")
        away = event.get("strAwayTeam", "Unknown")
        home_score = event.get("intHomeScore", "?")
        away_score = event.get("intAwayScore", "?")
        league = event.get("strLeague", "League")
        date = event.get("dateEvent", "Unknown")
        
        prompt = f"""Write a short, punchy football recap (2-3 sentences) about this real match result:

MATCH: {home} {home_score} - {away_score} {away}
LEAGUE: {league}
DATE: {date}

Tone: Sports analyst, human-sounding, no AI fluff. Be direct like a real football pundit.
Mention the score and one key moment or implication. Use plain English, no markdown."""

        recap = generate_text(prompt)
        if not recap:
            recap = f"{home} defeated {away} {home_score}-{away_score} in an entertaining {league} clash. The result keeps {home} on track while {away} will need to regroup quickly."
        
        match_name = f"Recap: {home} vs {away}"
        post_prediction(
            token=token,
            match_name=match_name,
            prediction_text=recap,
            sport="Football",
            league=league,
            confidence=3,
            odds="N/A",
            match_date=date
        )
        time.sleep(2)  # Rate limit safety
    
    print("✅ Monday recap complete")


def wednesday_midweek_preview():
    """Wednesday: Preview upcoming midweek matches"""
    print("\n📅 WEDNESDAY - Midweek Preview")
    print("=" * 50)
    
    token = login()
    if not token:
        print("❌ Skipping - login failed")
        return
    
    events = get_upcoming_events(days_ahead=3)
    if len(events) < 2:
        print("⚠️ Not enough events found, skipping")
        return
    
    selected = random.sample(events, min(3, len(events)))
    
    for event in selected:
        home = event.get("strHomeTeam", "Unknown")
        away = event.get("strAwayTeam", "Unknown")
        league = event.get("strLeague", "League")
        date = event.get("dateEvent", "Unknown")
        time_str = event.get("strTime", "TBD")
        
        prompt = f"""Write a short match preview (3-4 sentences) for this real upcoming fixture:

MATCH: {home} vs {away}
LEAGUE: {league}
DATE: {date} at {time_str}

Tone: Confident betting analyst. Include a brief prediction (who wins or if it's a draw) and one reason why.
Sound human. No "AI" language. No markdown. Be like a tipster at a pub."""

        preview = generate_text(prompt)
        if not preview:
            preview = f"{home} host {away} in what promises to be a competitive {league} encounter. Based on recent form, {home} enter as slight favorites but {away} have the quality to cause problems. A tight match expected."
        
        # Extract a prediction from the preview
        prediction_label = "Home Win"
        if "draw" in preview.lower() or "stalemate" in preview.lower() or "split points" in preview.lower():
            prediction_label = "Draw"
        elif away.lower() in preview.lower().split("win")[0] if "win" in preview.lower() else False:
            prediction_label = "Away Win"
        
        match_name = f"{home} vs {away}"
        post_prediction(
            token=token,
            match_name=match_name,
            prediction_text=f"{preview}\n\nPrediction: {prediction_label}",
            sport="Football",
            league=league,
            confidence=random.randint(3, 5),
            odds=f"{random.uniform(1.5, 3.0):.2f}",
            match_date=date
        )
        time.sleep(2)
    
    print("✅ Wednesday preview complete")


def friday_weekend_big_preview():
    """Friday: Big weekend match analysis"""
    print("\n📅 FRIDAY - Weekend Big Preview")
    print("=" * 50)
    
    token = login()
    if not token:
        print("❌ Skipping - login failed")
        return
    
    events = get_upcoming_events(days_ahead=4)
    if len(events) < 2:
        print("⚠️ Not enough events found, skipping")
        return
    
    selected = random.sample(events, min(5, len(events)))
    
    for event in selected:
        home = event.get("strHomeTeam", "Unknown")
        away = event.get("strAwayTeam", "Unknown")
        league = event.get("strLeague", "League")
        date = event.get("dateEvent", "Unknown")
        time_str = event.get("strTime", "TBD")
        
        prompt = f"""Write a detailed betting-focused match preview (4-5 sentences) for this real fixture:

MATCH: {home} vs {away}
LEAGUE: {league}
DATE: {date} at {time_str}

Include:
- Team form hint
- A specific betting tip (e.g., "Home win looks value", "Both teams to score is the play")
- A predicted scoreline

Tone: Expert tipster. Confident but realistic. Human, conversational. No markdown, no hashtags, no "AI" speak."""

        preview = generate_text(prompt)
        if not preview:
            preview = f"All eyes on this {league} clash as {home} welcome {away}. Recent form suggests goals could be on the cards here. The value bet looks to be Both Teams to Score given both sides' attacking quality. We're leaning {home} to edge it by the odd goal. Score prediction: 2-1."
        
        match_name = f"{home} vs {away}"
        post_prediction(
            token=token,
            match_name=match_name,
            prediction_text=preview,
            sport="Football",
            league=league,
            confidence=random.randint(3, 5),
            odds=f"{random.uniform(1.6, 2.8):.2f}",
            match_date=date
        )
        time.sleep(2)
    
    print("✅ Friday weekend preview complete")


# ============ SCHEDULE ============
def run_scheduled_task():
    """Determine which task to run based on today's day"""
    today = datetime.now().strftime("%A")
    print(f"\n🕐 Bot woke up - Today is {today}")
    print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if today == "Monday":
        monday_weekend_recap()
    elif today == "Wednesday":
        wednesday_midweek_preview()
    elif today == "Friday":
        friday_weekend_big_preview()
    else:
        print(f"📴 Not a scheduled day. Bot runs Mon/Wed/Fri only.")


# ============ START ============
if __name__ == "__main__":
    print("=" * 50)
    print("🤖 ProPredict Auto-Post Bot Starting")
    print("=" * 50)
    print(f"📅 Schedule: Monday, Wednesday, Friday")
    print(f"🌐 Target: {SITE_URL}")
    print("=" * 50)
    
    # Schedule: run at 8 AM on Mon, Wed, Fri
    schedule.every().monday.at("08:00").do(monday_weekend_recap)
    schedule.every().wednesday.at("08:00").do(wednesday_midweek_preview)
    schedule.every().friday.at("08:00").do(friday_weekend_big_preview)
    
    # Also run immediately on startup to test
    print("\n🚀 Running first post now to test...")
    run_scheduled_task()
    
    print("\n⏳ Bot is now waiting for next scheduled run...")
    print("   (Keeps checking every 60 seconds)\n")
    
    # Keep alive loop
    while True:
        schedule.run_pending()
        time.sleep(60)
