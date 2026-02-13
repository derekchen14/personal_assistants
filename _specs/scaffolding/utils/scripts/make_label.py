
lines = []
# open the data.txt file and print each line
with open('display.txt') as file:
  for line in file:
    lines.append(line.strip())

# sort the list in place
uniques = len(set(lines))
total = len(lines)

print("Total lines: ", total)
print("Unique lines: ", uniques)