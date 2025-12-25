#!/usr/bin/env python3
"""
Simple verification script to check strategy implementations
"""
import inspect

print("=" * 80)
print("🔍 VÉRIFICATION DES IMPLÉMENTATIONS DE STRATÉGIES")
print("=" * 80)
print()

# Read the definitions file
with open('strategies/definitions.py', 'r') as f:
    content = f.read()

# Check each strategy
strategies = [
    'ScalpEmaRsi',
    'InstitutionalScalp',
    'SwingTrendPullback',
    'DayTradingORB',
    'MeanReversion',
    'SMCFVG'
]

print("📊 Analyse du fichier strategies/definitions.py:\n")

results = {}

for strategy in strategies:
    # Find the class definition
    class_start = content.find(f'class {strategy}(BaseStrategy):')
    
    if class_start == -1:
        results[strategy] = "❌ Classe non trouvée"
        continue
    
    # Find the generate_signal method
    method_start = content.find('def generate_signal(self, df):', class_start)
    
    if method_start == -1:
        results[strategy] = "❌ Méthode generate_signal non trouvée"
        continue
    
    # Find the next line after the method definition
    next_line_start = content.find('\n', method_start) + 1
    next_line_end = content.find('\n', next_line_start)
    next_line = content[next_line_start:next_line_end].strip()
    
    # Check if it's just "return None"
    if next_line == 'return None':
        results[strategy] = "⚠️  Non implémentée (return None)"
    elif '"""' in next_line or "'''" in next_line:
        # Has a docstring, likely implemented
        results[strategy] = "✅ Implémentée (avec docstring)"
    elif 'if' in next_line or 'params' in next_line:
        # Has logic
        results[strategy] = "✅ Implémentée (avec logique)"
    else:
        results[strategy] = "⚪ État inconnu"

# Display results
for strategy, status in results.items():
    print(f"   {strategy:25} {status}")

# Count
implemented = sum(1 for s in results.values() if "✅" in s)
not_implemented = sum(1 for s in results.values() if "⚠️" in s)
total = len(results)

print()
print("=" * 80)
print(f"📈 RÉSUMÉ: {implemented}/{total} stratégies implémentées")
print("=" * 80)

if implemented == total:
    print("\n✅ EXCELLENT! Toutes les stratégies sont implémentées!")
elif implemented > not_implemented:
    print(f"\n⚪ {implemented} stratégies implémentées, {not_implemented} à faire")
else:
    print(f"\n⚠️  Seulement {implemented} stratégies implémentées sur {total}")

print()

# Show line counts for each strategy
print("📏 Taille des implémentations (lignes de code):\n")

for strategy in strategies:
    class_start = content.find(f'class {strategy}(BaseStrategy):')
    if class_start == -1:
        continue
    
    # Find next class or end of file
    next_class = content.find('\nclass ', class_start + 1)
    if next_class == -1:
        next_class = len(content)
    
    strategy_code = content[class_start:next_class]
    lines = len(strategy_code.split('\n'))
    
    status = "📝" if lines > 10 else "📄"
    print(f"   {status} {strategy:25} {lines:3} lignes")

print()
print("=" * 80)
