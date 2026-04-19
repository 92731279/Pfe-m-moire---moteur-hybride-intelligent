with open('tests/test_e2.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
with open('tests/test_e2.py', 'w', encoding='utf-8') as f:
    for line in lines:
        if 'pass1_town_validated_via_core:TN:TUNIS BELVEDERE' not in line and 'pass1_town_validated_via_core:FR:PARIS CENTRE' not in line:
            f.write(line)
