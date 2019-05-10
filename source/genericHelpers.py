import datetime
import sys

def reverseDict(D):
    #Flips mapping in a dictionary: value->key
    if type(D)!=dict: raise TypeError('Input is not a dictionary')
    else:
        nD=dict()
        for key in D:
            val=D[key]
            nD[val]=key
    return nD

def str2TimeDelta(s):
    #Takes a string in the format h:m:s or m:s and converts to time delta
    if type(s)!=str: raise TypeError("Input needs to be a string")
    try: 
        s=s.split(":")
        if len(s)==3: #i.e. if h:m:s
            (hr,mn,sc)=(int(s[0]),int(s[1]),int(s[2]))
            return datetime.timedelta(hours=hr,minutes=mn,seconds=sc)
        elif len(s)==2: #i.e. if m:s
            (mn,sc)=(int(s[0]),int(s[1]))
            return datetime.timedelta(minutes=mn,seconds=sc)
    except: raise ValueError("Could not parse the string: %s" %s)

def flatten(L):
#Collapses a list of lists into a single list of base elements
    if L==[]: return L #Base case that Catches empty lists
    elif type(L)!=list: return L #base case that catches nonlist elements
    elif type(L[0])==list: #recursively flattens a sublist
        flatList=flatten(L[0]) 
        return flatList+flatten(L[1:])
    else: return [L[0]]+flatten(L[1:]) 

def checkASCII(s):
#Returns true only if all characters are ASCII
    try: return len(s.encode())==len(s)
    except: return False

def noneDict(D):
    #Checks that all of the non-key entries in a dictionary are not None
    #Recursively checks subdicts
    if type(D)!=dict: raise TypeError('Input is not a dictionary') #Check for non-dict entries
    for elem in D:
        entry=D[elem]
        if type(entry)==dict and noneDict(entry)==False: return False #Check subdicts 
        elif entry!=None: return False #Check actual entries
    return True        

def mean(L):
    if len(L)==0: raise IndexError('List has zero length')
    try:
        try: lSum=genSum(L)
        except: raise TypeError('Could not sum the list') 
        return lSum/len(L)
    except: raise TypeError('Cannot divide sum of list (%s) by integer' %type(lSum).__name__)

def median(LIn):
    L=sorted(LIn)
    length=len(L)
    if length==0: raise IndexError('List has zero length')
    if length%2==0:
        try:
            (mid0,mid1)=(float(L[length//2-1]),float(L[length//2]))
            return (mid0+mid1)/2
        except: raise TypeError('Could not convert entries to floats')
    else:
        try: return float(L[length//2])
        except: raise TypeError('Could not convert entry to float')

def genSum(L):
    #Infers data type of list from first element and sums accordingly
    if len(L)==0: raise IndexError('Cannot sum over an empty list')
    elif len(L)==1: return L[0]
    total=L[0]
    for elem in L[1:]:
        try: total+=elem
        except: raise TypeError('Cannot add %s and %s' %(type(total).__name__,type(elem).__name__))
    return total

def removeChars(s,toRemove):
#Given a string and a set of characters/substrings,
#Removes the characters/substrings from the input string and returns
    s_modified=""
    for i in range(len(s)):
        if (s[i] in toRemove)==True:
            i+=1 #skips over undesired character
        else:
            s_modified+=s[i]
    return s_modified