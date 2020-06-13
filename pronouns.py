
# i and me is a bit more complex, since they both are "you" in reverse direction
# If  you reverse "you", it is dependend wether "you" is used as subject or object
# Not sure how to handle that

directionalPronouns = [
	("me", "you"),
	("my", "your"),
	("mine", "yours"),
	("i", "yourself"),
	("our", "your"), #important: this tuple cant be above ("my", "your"), unless the you represent a group (ie. snake is a group)
	("us", "you") # Same here with ("me", "you")
]

# transfers casing from ow to nw, such that:
# (ow, nw) -> res
# (Hello, hi) -> Hi
# (HeLlO, somewhat) -> SoMeWhAt
# The casing of the 1st letter in ow determines the casing of the 1st letter in res
# All following cases are determined by using the casing pattern of ow after the 1st letter
def transferCasing(ow, nw):
	oletters = list(ow)
	nletters = list(nw)
	if oletters[0].isupper():
		nletters[0] = nletters[0].upper()
	else:
		nletters[0] = nletters[0].lower()
	
	oletters.pop(0)
	if len(oletters) == 0:
		return "".join(nletters)
	
	for i, l in enumerate(nletters):
		if i == 0: # skip 1st letter
			continue
		oi = (i-1) % len(oletters)
		if oletters[oi].isupper():
			nletters[i] = nletters[i].upper()
		else:
			nletters[i] = nletters[i].lower()
	
	return "".join(nletters)

# Reverses the direction of pronouns such as "me" to "you"
# "yourself" to "myself"
# It does not work for plurals or normal sentences.
# Either it is a single pronoun, such as "you"
# Or it is a possessive pronoun, such as "my", "your"
def reversePronouns(text):
	words = text.split(" ")
	for k, w in enumerate(words):
		lowerW = w.lower()
		newW = None
		for i, p in enumerate(directionalPronouns):
			if not lowerW in p: continue
			newW = p[(p.index(lowerW)+1)%2]
			break
		
		if newW is None:
			continue
		# Transfer case-pattern (only)
		words[k] = transferCasing(w, newW)

	return " ".join(words)

# Returns the correct form of "is" for the given noun
# Note this does not include special cases yet
def nounIs(n):
	if n.lower() == "i": # "i" special case
		return "am"
	if n.lower() == "you": # "you" special case
		return "are"
	words = n.split(" ")
	if words[len(words)-1].endswith("s"):
		return "are"
	return "is"

def asSubject(n):
	if n.lower() == "i":
		return "myself"
	return n
