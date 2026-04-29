import re
p1 = re.compile(r"^\s*:(50F|50K|59F|59):", re.IGNORECASE)
p2 = re.compile(r"^\s*:?(50F|50K|59F|59):", re.IGNORECASE)

s1 = ":50K:/729615-941"
s2 = "50K:/729615-941"

print(p1.match(s1))
print(p1.match(s2))
print(p2.match(s1))
print(p2.match(s2))
