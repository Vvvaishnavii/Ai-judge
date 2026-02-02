"""
AI Judge for Rock-Paper-Scissors Plus - FINAL WORKING VERSION
==============================================================
Tries all possible Gemini API endpoints.
"""

import requests
import json
import random
from dataclasses import dataclass

# ============================================================================
# CONFIGURATION
# ============================================================================

API_KEY = "AIzaSyDfufiqEMzkiLOTlF_HV4JXBeg07DDGqHI"


# ============================================================================
# UNIFIED PROMPT
# ============================================================================

UNIFIED_JUDGE_PROMPT = """You are an AI Judge for a Rock-Paper-Scissors Plus game.

GAME RULES:
1. Valid moves: rock, paper, scissors, bomb
2. Standard rules: rock > scissors, scissors > paper, paper > rock
3. Bomb beats everything (rock, paper, scissors)
4. Bomb vs bomb = draw
5. Bomb can only be used ONCE per player per game
6. Invalid/unclear moves waste the turn (opponent wins by default)

GAME STATE:
- Round: {round_number}
- User bomb used: {user_bomb_used}
- Bot bomb used: {bot_bomb_used}

USER INPUT: "{user_input}"
BOT MOVE: {bot_move}

YOUR TASK:
1. Understand user's intent (handle typos like "rok"→rock, "papper"→paper, "bom"→bomb)
2. Check if move is VALID, INVALID, or UNCLEAR
3. Determine round winner
4. Generate helpful response

TYPO TOLERANCE:
- "rok", "rocc", "r" → rock
- "papper", "papre", "p" → paper
- "scissor", "scizzors", "s" → scissors
- "bom", "bombb", "b" → bomb

AMBIGUOUS (mark as UNCLEAR):
- "maybe rock", "rock or paper?", "idk", "hmm"

INVALID:
- Not game moves: "gun", "water", etc.
- Bomb when already used

Respond with ONLY a JSON object:
{{
  "move_status": "VALID|INVALID|UNCLEAR",
  "user_move": "rock|paper|scissors|bomb|unknown",
  "reason": "why this status was assigned",
  "round_winner": "USER|BOT|DRAW",
  "explanation": "what happened and why",
  "feedback": "optional tip if move was unclear/invalid"
}}"""


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class GameState:
    """Minimal state tracking"""
    round_number: int = 0
    user_score: int = 0
    bot_score: int = 0
    user_bomb_used: bool = False
    bot_bomb_used: bool = False


# ============================================================================
# AI JUDGE
# ============================================================================

class AIJudge:
    """AI Judge using Gemini API"""
    
    def __init__(self):
        self.state = GameState()
        self.api_url = None
        self._find_working_model()
        
    def _find_working_model(self):
        """Find an available Gemini model"""
        
        # Priority: Use the endpoint that's working for you!
        priority_endpoints = [
            "https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent",
            "https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent",
            "https://generativelanguage.googleapis.com/v1/models/gemini-1.5-pro:generateContent",
            "https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent",
        ]
        
        print("🔍 Finding working Gemini model...")
        
        test_payload = {
            "contents": [{
                "parts": [{"text": "test"}]
            }]
        }
        
        # Try priority endpoints first
        for endpoint in priority_endpoints:
            url = f"{endpoint}?key={API_KEY}"
            
            try:
                response = requests.post(url, json=test_payload, timeout=5)
                
                if response.status_code == 200:
                    self.api_url = url
                    model_name = endpoint.split('/')[-1].split(':')[0]
                    print(f"✅ Using: {model_name}\n")
                    return
            except:
                continue
        
        raise Exception("❌ No working model found! Check API key.")
        
    def call_llm(self, prompt: str) -> str:
        """Call Gemini API with retry logic"""
        headers = {'Content-Type': 'application/json'}
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }
        
        max_retries = 5
        for attempt in range(max_retries):
            try:
                response = requests.post(self.api_url, headers=headers, json=payload, timeout=30)
                response.raise_for_status()
                result = response.json()
                return result['candidates'][0]['content']['parts'][0]['text']
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:  # Rate limit
                    if attempt < max_retries - 1:
                        import time
                        wait_time = min(60, (2 ** attempt) * 5)
                        print(f"⏳ Rate limited. Waiting {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                raise
            except Exception as e:
                if attempt < max_retries - 1:
                    import time
                    time.sleep(2)
                    continue
                raise
        
        raise Exception("API request failed after retries")
    
    def get_bot_move(self) -> str:
        """Simple bot strategy"""
        if not self.state.bot_bomb_used and random.random() < 0.12:
            self.state.bot_bomb_used = True
            return "bomb"
        return random.choice(["rock", "paper", "scissors"])
    
    def parse_json_response(self, response: str) -> dict:
        """Extract and parse JSON from LLM response"""
        try:
            response = response.strip()
            
            # Remove markdown code blocks
            if '```' in response:
                parts = response.split('```')
                for part in parts:
                    part = part.strip()
                    if part.startswith('json'):
                        part = part[4:].strip()
                    if part.startswith('{') and part.endswith('}'):
                        response = part
                        break
            
            # Find JSON object
            start_idx = response.find('{')
            end_idx = response.rfind('}')
            
            if start_idx != -1 and end_idx != -1:
                response = response[start_idx:end_idx + 1]
            
            return json.loads(response)
        except Exception as e:
            print(f"⚠️  Parse error: {str(e)[:80]}")
            return {
                "move_status": "UNCLEAR",
                "user_move": "unknown",
                "reason": "System error",
                "round_winner": "BOT",
                "explanation": "Technical issue - bot wins by default",
                "feedback": ""
            }
    
    def judge_move(self, user_input: str) -> str:
        """Main judging - single API call"""
        self.state.round_number += 1
        bot_move = self.get_bot_move()
        
        # Single unified prompt
        prompt = UNIFIED_JUDGE_PROMPT.format(
            round_number=self.state.round_number,
            user_bomb_used=self.state.user_bomb_used,
            bot_bomb_used=self.state.bot_bomb_used,
            user_input=user_input,
            bot_move=bot_move
        )
        
        # Get judgment
        try:
            response = self.call_llm(prompt)
            result = self.parse_json_response(response)
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            result = {
                "move_status": "UNCLEAR",
                "user_move": "unknown",
                "reason": "API error",
                "round_winner": "BOT",
                "explanation": f"Error: {str(e)[:100]}",
                "feedback": ""
            }
        
        # Update state
        if (result.get('user_move') == 'bomb' and 
            result.get('move_status') == 'VALID'):
            self.state.user_bomb_used = True
        
        winner = result.get('round_winner', 'BOT')
        if winner == 'USER':
            self.state.user_score += 1
        elif winner == 'BOT':
            self.state.bot_score += 1
        
        # Format response
        feedback_line = f"\nFEEDBACK: {result.get('feedback')}" if result.get('feedback') else ""
        
        return f"""---
MOVE_STATUS: {result.get('move_status', 'UNCLEAR')}
USER_MOVE: {result.get('user_move', 'unknown')}
REASON: {result.get('reason', 'Unknown')}
BOT_MOVE: {bot_move}
ROUND_WINNER: {winner}
EXPLANATION: {result.get('explanation', 'No explanation')}{feedback_line}
---"""
    
    def get_summary(self) -> str:
        """Generate game summary"""
        if self.state.user_score > self.state.bot_score:
            result = "🎉 USER WINS THE GAME!"
        elif self.state.bot_score > self.state.user_score:
            result = "🤖 BOT WINS THE GAME!"
        else:
            result = "🤝 GAME IS A DRAW!"
        
        return f"""
{'='*60}
GAME SUMMARY
{'='*60}
Total Rounds: {self.state.round_number}
User Score: {self.state.user_score}
Bot Score: {self.state.bot_score}

{result}

Stats:
- User bomb used: {'Yes' if self.state.user_bomb_used else 'No'}
- Bot bomb used: {'Yes' if self.state.bot_bomb_used else 'No'}
- Win rate: {(self.state.user_score / max(self.state.round_number, 1) * 100):.1f}%
{'='*60}
"""


# ============================================================================
# MAIN GAME LOOP
# ============================================================================

def main():
    print("="*60)
    print("🎮 ROCK-PAPER-SCISSORS PLUS - AI Judge")
    print("="*60)
    print("\nRules:")
    print("  • Valid moves: rock, paper, scissors, bomb")
    print("  • Bomb beats everything (use wisely - only once!)")
    print("  • Unclear/invalid moves waste your turn")
    print("\nCommands:")
    print("  • Type your move (typos are OK!)")
    print("  • 'quit' to end game")
    print("  • 'stats' for current score")
    print("="*60)
    print()
    
    try:
        judge = AIJudge()
    except Exception as e:
        print(str(e))
        return
    
    while True:
        user_input = input(f"\n[Round {judge.state.round_number + 1}] Your move: ").strip()
        
        if user_input.lower() in ['quit', 'exit', 'q']:
            print("\n👋 Thanks for playing!")
            break
        
        if user_input.lower() == 'stats':
            print(f"\n📊 Score: {judge.state.user_score} - {judge.state.bot_score}")
            print(f"   Bomb: {'Used ✓' if judge.state.user_bomb_used else 'Available ○'}")
            continue
        
        if not user_input:
            print("⚠️  Please enter a move!")
            continue
        
        # Judge the move
        print("\n" + "="*60)
        judgment = judge.judge_move(user_input)
        print(judgment)
        print("="*60)
        print(f"\n📊 Score: User {judge.state.user_score} - {judge.state.bot_score} Bot")
    
    print(judge.get_summary())


if __name__ == "__main__":
    main()
