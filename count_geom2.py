siteMap = [59,57,55,52,54,48,64,62,49,61,63,53,51,56,58,60,33,35,37,39,41,43,45,47,50,46,44,42,40,38,36,34,31,29,27,25,23,21,19,17,16,20,22,24,26,28,30,32,5,7,9,14,12,18,2,4,15,3,1,11,13,10,8,6]

print(f"Total elements: {len(siteMap)}")
print(f"Unique elements: {len(set(siteMap))}")
missing = set(range(1, 65)) - set(siteMap)
print(f"Missing elements: {missing}")
