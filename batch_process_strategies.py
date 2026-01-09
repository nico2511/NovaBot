"""
Quick batch processor for remaining strategies
Simplifies check_conditions value fields and adds get_threshold_comparisons stub
"""
import re
import os

STRATEGIES_DIR = r"c:\Users\User\Desktop\novabot\strategies"
FILES = [
    "rsi_ping_pong.py",
    "bollinger_bounce.py", 
    "bull_flag.py",
    "double_bottom.py",
    "double_top.py",
    "head_shoulders.py"
]

THRESHOLD_TEMPLATE = '''
    
    def get_threshold_comparisons(self, df, extra_data=None):
        """Get detailed threshold comparisons for Parameters section"""
        if df is None or df.empty:
            return {}
        
        try:
            # TODO: Implement threshold comparisons based on check_conditions logic
            return {}
        except Exception as e:
            return {"Error": str(e)}
'''

for filename in FILES:
    filepath = os.path.join(STRATEGIES_DIR, filename)
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Step 1: Replace all "value": "..." with "value": ""
    content = re.sub(r'"value":\s*f?"[^"]*"', '"value": ""', content)
    content = re.sub(r'"value":\s*"[^"]*"\s*if.*?else\s*"[^"]*"', '"value": ""', content)
    
    # Step 2: Add get_threshold_comparisons if not exists
    if 'def get_threshold_comparisons' not in content:
        # Find the end of check_conditions method
        # Insert before the last line (usually just a newline)
        content = content.rstrip() + THRESHOLD_TEMPLATE + '\n'
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ {filename}")

print("\n✅ All 6 files processed!")
