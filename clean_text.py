
discordFormatChars = [
    "`",
    "*",
    "_",
    "|"
]

# escape formatting chars
def discordStringEscape(str):
    reslist = list(str)
    i = 0
    while i < len(reslist):
        if reslist[i] in discordFormatChars:
            if i == 0 or reslist[i-1] != '\\':
                reslist.insert(i, "\\")
                i += 1
        
        i += 1
    return "".join(reslist)

# deescape formatting chars
def discordStringDeescape(str): # THIS FUNCTION IS NOT FINISHED YET
    reslist = list(str)
    i = 0
    while i < len(reslist):
        if reslist[i] in discordFormatChars:
            if i == 0 or reslist[i-1] != '\\':
                reslist.insert(i, "\\")
                i += 1
        
        i += 1
    return "".join(reslist)

# remove formatting chars, that are unescaped
def discordRemoveUnescapedFormatting(str):
    reslist = list(str)
    i = 0
    while i < len(reslist):
        if reslist[i] in discordFormatChars:
            if i == 0 or reslist[i-1] != '\\':
                del reslist[i]
                i -= 1
        
        i += 1
    return "".join(reslist)


# Exit formatting in user string, so that it cant spill into subsequent text.
# example string: '||test' becomes '||test||'
def discordCleanFormatting(str): # THIS FUNCTION IS NOT FINISHED YET
    return str