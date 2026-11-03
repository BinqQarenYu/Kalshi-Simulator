with open("src/kalshi_sim/order_client.py", "r", encoding="utf-8") as f:
    text = f.read()

target = 'amount_units = int(amount_dollars * Decimal("10000"))'
assert target in text, "target not found"

replacement = '''if not isinstance(amount_dollars, Decimal):
            amount_dollars = Decimal(str(amount_dollars))
        amount_units = int(amount_dollars * Decimal("10000"))'''

text = text.replace(target, replacement, 1)

with open("src/kalshi_sim/order_client.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Successfully patched order_client.py")
