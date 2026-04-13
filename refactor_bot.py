import re

with open('app/core/bot.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = False
for line in lines:
    # Match block removals (methods or properties)
    if re.match(r'^\s*def _update_market_analysis', line):
        skip = True
    elif re.match(r'^\s*def _fetch_mtf_sentiment', line):
        skip = True
    elif re.match(r'^\s*def _record_signal_analysis', line):
        skip = True
    elif re.match(r'^\s*@property\s*$', line) and (
        "_update_market_analysis" in line or 
        "copilot_sentiment" in line
        # we check the next line for copilot_sentiment below, so handled better via state machine
    ):
        pass # Handle @property copilot_sentiment

    if skip:
        # If we hit an unexpectedly un-indented def/class, stop skipping
        if re.match(r'^\s*(def |class )', line) and not 'def _update_market_analysis' in line and not 'def _fetch_mtf_sentiment' in line and not 'def _record_signal_analysis' in line:
            skip = False
            
    # Additional line-by-line removals
    if 'from app.core.asset_gamification import' in line: continue
    if 'from app.services.analyst_service import' in line: continue
    if 'self.gamification' in line: continue
    if 'self.trade_recorder' in line: continue # Removing trade_recorder instances inside bot.py to simplify
    if 'from app.core.trade_recorder import' in line: continue

    if not skip:
        new_lines.append(line)

with open('app/core/bot_clean.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
