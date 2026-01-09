"""
Script to restructure all strategy check_conditions methods
Simplifies check_conditions to return only names/status
Adds get_threshold_comparisons for detailed comparisons
"""

import re
import os

STRATEGIES_DIR = r"c:\Users\User\Desktop\novabot\strategies"

# List of strategy files to process (excluding elastic_reversion which is already done)
STRATEGY_FILES = [
    "smart_mean_reversion.py",
    "bollinger_bounce_v2.py",
    "smart_trend.py",
    "scalp_ema_rsi.py",
    "institutional_scalp.py",
    "rsi_ping_pong.py",
    "bollinger_bounce.py",
    "bull_flag.py",
    "double_bottom.py",
    "double_top.py",
    "fibo_pullback.py",
    "head_shoulders.py"
]

def process_strategy_file(filepath):
    """Process a single strategy file"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find check_conditions method
    pattern = r'(    def check_conditions\(self, df, extra_data=None\):.*?)(    def \w+|^class |\Z)'
    match = re.search(pattern, content, re.DOTALL | re.MULTILINE)
    
    if not match:
        print(f"❌ Could not find check_conditions in {os.path.basename(filepath)}")
        return False
    
    method_content = match.group(1)
    
    # Extract all conditions with their values
    value_pattern = r'"value":\s*f?"([^"]+)"'
    values = re.findall(value_pattern, method_content)
    
    # Replace all value fields with empty strings
    new_method = re.sub(r'"value":\s*f?"[^"]+"', '"value": ""', method_content)
    new_method = re.sub(r'"value":\s*"[^"]*"\s*if.*?else\s*"[^"]*"', '"value": ""', new_method)
    
    # Create get_threshold_comparisons method
    threshold_method = f'''
    
    def get_threshold_comparisons(self, df, extra_data=None):
        """Get detailed threshold comparisons for Parameters section"""
        if df is None or df.empty:
            return {{}}
        
        try:
            # TODO: Extract actual threshold comparisons from check_conditions logic
            return {{}}
        except Exception as e:
            return {{"Error": str(e)}}
'''
    
    # Replace in content
    new_content = content.replace(method_content, new_method + threshold_method)
    
    # Write back
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"✅ Processed {os.path.basename(filepath)}")
    return True

# Process all files
for filename in STRATEGY_FILES:
    filepath = os.path.join(STRATEGIES_DIR, filename)
    if os.path.exists(filepath):
        process_strategy_file(filepath)
    else:
        print(f"⚠️ File not found: {filename}")

print("\n✅ All strategies processed!")
