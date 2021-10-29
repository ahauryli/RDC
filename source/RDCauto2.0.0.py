#Importing standard libraries
import os
import datetime
import string
import sys
import time
import copy
import multiprocessing
import pdb
from multiprocessing import Pool,cpu_count

#Importing custom libraries
from fileObj import *
from confReader import config
from rawFileReader import read
from errTrackers import *
from genericHelpers import *

NAME="RAMP Data Cleaner"

#________Define folder and file names________#
#Subfolders
SETTINGS="Settings"
TEMPLATES="templates"
CONSTANTS="Constants"
PERFORMANCE="Performance"
OUTPUT="Output"

#File names
VERSION="version.ini"
TEMPLATE="template.ini"
DEPENDENCIES="dependencies.ini"
RUNFILE="test2021-10-28.ini"
CRITERIA="bounds.ini"
CONST="const.ini"
ECHEM="SensorMix.csv"
PERF="Performance.csv"

#____Construct Paths for external files____#
if getattr(sys,'frozen',False):
    SCRIPTPATH=sys.executable
    SCRIPTDIR=os.path.dirname(SCRIPTPATH)
    WORKDIR=SCRIPTDIR
else:
    SCRIPTPATH=os.path.abspath(__file__)
    SCRIPTDIR=os.path.dirname(SCRIPTPATH)
    WORKDIR=os.path.dirname(SCRIPTDIR)
if WORKDIR.endswith('MacOS'):
    WORKDIR=os.path.dirname(os.path.dirname(os.path.dirname(WORKDIR)))
VERSPATH=os.path.join(WORKDIR,VERSION)
TEMPLPATH=os.path.join(WORKDIR,SETTINGS,TEMPLATES,TEMPLATE)
DEPENDPATH=os.path.join(WORKDIR,SETTINGS,TEMPLATES,DEPENDENCIES)
RUNPATH=os.path.join(WORKDIR,SETTINGS,RUNFILE)
CRITPATH=os.path.join(WORKDIR,CONSTANTS,CRITERIA)
CONSTPATH=os.path.join(WORKDIR,CONSTANTS,CONST)
ECHEMPATH=os.path.join(WORKDIR,CONSTANTS,ECHEM)
PERFPATH=os.path.join(WORKDIR,PERFORMANCE,PERF)

#________________CLASS DECLARATIONS______________________________#

#Script Parameters:
class runParams(object):
#Contains user inputs that determine how the program will run
    def __init__(self):
        print("Importing Template")
        self.param=config.importDict(TEMPLPATH)
        (self.runPath,self.echemPath)=self.setDefPaths() #Path to Defaults.csv,if it exists
        self.yesterday=datetime.date.today()-datetime.timedelta(days=1)
        self.rampDict=dict() #Maps RAMP number to RAMP object
        self.rParamDict=dict() #e.g. Raw Directory:Paths, Auto Checks:Toggles
        self.rOutputDict=dict()  #e.g. {PTR: [PM010, PM025, PM100]} --> {PM010:PTR, PM025:PTR, PM100:PTR} (from template)
        self.echemDict=dict()
        print("Writing Reverse Dictionary")
        self.writeReverseDict() #auto-Populates self.rParamDict
        self.writeCatNameDict() #auto-Populates self.rOutputDict

    def __repr__(self):
        #Uniquely represents a runParams object as a string containing
        #All of its parameters and mapped values
        sOut="" #Stores the output string
        for key in self.param:
            sOut+="\n" #Separate categories by blank lines
            for subkey in self.param[key]:
                sOut+=subkey+' : ' #Adds parameter name to output string
                member=self.param[key][subkey] #i.e. value of parameter
                if (type(member)==list or type(member)==set):
                    if key!='Output': member=sorted(member) #Sorts things like dates,ramp nums, etc.
                    strList=stringify(member) #Converts lists/sets/etc. into a string
                    sOut+=runParams.cleanLine(str(strList))+"\n" #Cleans up line before adding it
                else: sOut+=str(self.param[key][subkey])+'\n'
        return sOut

    def get(self,param):
        #Fetches a given parameter from the self.param dictionary using the reverse dictionary
        #Raises a KeyError if the entry is not there
        if param not in self.rParamDict: raise KeyError("No parameter '%s' found" %param)
        else:
            category=self.rParamDict[param]
            return self.param[category][param]

    def setDefPaths(self):
        #Imports from global variables the path to echem and runInfo files
        #Catches if these files do not exist and crash the program
        runPath=RUNPATH
        echemPath=ECHEMPATH
        if os.path.exists(runPath):
            if os.path.exists(echemPath): return (runPath,echemPath)
            else: 
                raise FileNotFoundError('Sensor Mix file was not found. Check Path:\n%s' %echemPath)
        else: raise FileNotFoundError('run info file was not found. Check Path:\n%s' %runPath)

    def writeReverseDict(self):
        for key in self.param:
            for subkey in self.param[key]: 
                self.rParamDict[subkey]=key

    def writeCatNameDict(self):
        #Creates a Dictionary mapping parameter name to category
        #e.g. {PTR: [PM010, PM025, PM100]} --> {PM010:PTR, PM025:PTR, PM100:PTR}
        outputDict=self.param['Output']
        excludeSet={'Order','Output File Name'} #Headers w/o parsed param names
        for key in outputDict:
            if key not in excludeSet:
                entry=outputDict[key]
                if type(entry)==list: #Iterate thru param lists if needed to get ea. elem
                    for value in outputDict[key]:
                        self.rOutputDict[value]=key
                else:
                    self.rOutputDict[entry]=key #Otherwise just add to reversedict

    def loadParams(self):
        print("\nLoading Parameters")
        self.loadEchem()
        #Separate loader that takes care of importing parameters and verifying them:
        loader=config(self.param,WORKDIR)
        dependencies=config.importDict(DEPENDPATH)
        self.param=loader.load(self.runPath,check=True,dependencies=dependencies)
        if loader.noErrors(): 
            print("Parameters Loaded:")
            print(self)
            self.consolidateRampInfo()
            print("Parameters reorganized")
        else:
            raise RuntimeError("Error(s) in loading parameters:\n%s" 
                                %(config.write.dict2str(loader.errors)))

    def loadEchem(self):
        #Loads in a dictionary mapping ramp number to echem sensor mix
            echem=open(self.echemPath,'r')
            line=echem.readline()
            while line!="":
                line=removeChars(line,{"\n"})
                line=line.split(",")
                rampNum=int(line[0])
                #Save in format ramp -> [S1,S2,S3,S4] e.g. 154->["CO","SO2","NO2","O3"]
                self.echemDict[rampNum]=line[1:]
                line=echem.readline()

    def consolidateRampInfo(self):
        #Consolidates path,echem, and output dictionaries into a dict or RAMP objects
        #self.rampDict will store the dict in format rampNo.->RAMP obj
        pathDict=config.pull.ramps.all(self.get("Raw Directory"),returnPathDict=True)
        echemDict=self.echemDict
        outDict=self.getOutDict() #Get a dictionary mapping RAMP->output
        for rampNum in self.get("Ramp Nums"):
            if rampNum in echemDict: 
                echemLine=echemDict[rampNum] #Load the sensor mix if available
                ramp=RAMP(rampNum,echemLine) #Create the RAMP object w/echem line
            else:
                error="\nECHEM info was not found for RAMP #%d" %rampNum
                solution="Update the SensorMix file and run again"
                raise KeyError("%s\n%s"%(error,solution))
            if rampNum in outDict: ramp.output=outDict[rampNum] #Add output string if available
            pathList=pathDict[rampNum] #Load the list of directories found for the RAMP
            ramp.addDirs(pathList) #Add them in
            self.rampDict[rampNum]=ramp

    def getOutDict(self):
        #Returns a dictionary mapping:
        #rampNo.->"order"->order line of output
        #and rampNo->"params"->dictionary of headers mapped to list of parameters
        if self.get("Output Format File"):
            #Load a format file if given
            return runParams.loadFormatFile(self.get("Output File Name"),self.get("Ramp Nums"))
        else:
            #Otherwise, assign the same output to every RAMP
            outDict=dict()
            output=self.param["Output"]
            runParams.writeOutput2Ramps(output,self.get("Ramp Nums"),outDict)
            return outDict

    @staticmethod
    def loadFormatFile(fileName,rampNums=None): 
        #Loads an output dictionary from a file
        restKwrd="rest" #String that specifies ramps not enumerated in the output file
        outDict=dict()
        path2File=os.path.join(WORKDIR,OUTPUT,fileName) #Construct path to the output file
        loadedDict=config.importDict(path2File) #dumbLoaded dictionary
        if type(rampNums)==set:
            #Create a set of ramps that did not have an output mapped:
            notDoneSet=copy.copy(rampNums)
            #First load in the enumerated entries:
            for rNumStr in loadedDict:
                rampSet=config.pull.ramps.nums(rNumStr)
                #Skip iteration of the loop in case ramp Set could not be loaded
                if type(rampSet)==str and rampSet.startswith("Error Parsing"): continue
                else:rampSet=rampSet&notDoneSet #Look at intersection of parsed set and selection
                if rampSet!=set():
                    #If there are ramps in format file that are also part of the selection
                    output=loadedDict[rNumStr] 
                    if output!=set() and output!=dict() and output!=None: #Ensure that a dud was not passed. 
                        #If a dud was, passed, lump the ramps with "rest"
                        #write output map to outDict
                        runParams.writeOutput2Ramps(output,rampSet,outDict) 
                        notDoneSet-=rampSet #update notDoneSet
            #Write output map to ramps that were not enumerated in the file:
            if restKwrd in loadedDict:
                output=loadedDict[restKwrd]
                runParams.writeOutput2Ramps(output,notDoneSet,outDict)
            #If no 'rest' keyword present and there are ramps that do not have an output dict:
            elif notDoneSet!=set(): 
                raise KeyError("The following RAMPs do not have an output specified:",
                                "\n%s" %str(notDoneSet))
        #If function was not given a set of ramps to look for, dumb-load as much as possible
        else:
            for rNumStr in loadedDict:
                rampSet=config.pull.ramps.nums(rNumStr)
                if type(rampSet)==str and rampSet.startswith("Error Parsing"): continue
                output=loadedDict[rNumStr]
                runParams.writeOutput2Ramps(output,rampSet,outDict)
        return outDict

    @staticmethod
    def writeOutput2Ramps(output,rampSet,outDict):
        #Populates the outDict with each ramp in the rampSet mapped as:
        #ramp->"order"-> order string of output
        #As well as ramp->"params"->dictionary of headers mapped to list of parameters
        #Doesn't return, uses aliasing on the outDict
        for ramp in rampSet:
            outDict[ramp]=  { #keeps track of order and header dictionaries as separate entries
                            "order" : None,
                            "params": dict()
                            }
            outDict[ramp]["order"]=output["Order"]
            skipHeaders={"Order","Output File Name"} #Entries which don't contain header information
            for header in output:
                if header not in skipHeaders:
                    if type(output[header])==str:
                        outDict[ramp]["params"][header]=[output[header]]
                    else:
                        outDict[ramp]["params"][header]=output[header]

    @staticmethod
    def cleanLine(s):
        toRemove={'"',"'","","\t","\n"}
        return removeChars(s,toRemove)

#RAMP properties
class RAMP(object):
    #Handles properties of each RAMP
    def __init__(self,num,echemLine=["S1","S2","S3","S4"]):
        self.num=num #Number (as integer)
        self.dirs=  { #Directories where data for the RAMP is found
                    "Server": set(),
                    "SD": set()
                    }
        self.echem=echemLine
        self.output=None

    def __eq__(self,other):
        return self.num==other.num

    def __repr__(self):
        return "RAMP "+str(self.num)

    def __str__(self):
        return str(self.num)

    def __hash__(self):
        return hash(repr(self))

    def addDir(self,path):
        if path in self.dirs: return
        else: self.dirs.add(path)

    def addDirs(self,paths):
        #Check paths for server and SD, allocate appropriately to self.dirs dict
        for path in paths:
            if path.endswith("s%d"%(self.num)): self.dirs["Server"].add(path)
            else: self.dirs["SD"].add(path)

    @staticmethod
    def nums(rampSet):
        rSet=set()
        for ramp in rampSet:
            rSet.add(ramp.num)
        return rSet

#Parameters for file and RAMP workers
class workParams(object):
    def __init__(self,runInfo,raw,cal,chk=None,crit=None):
            #Takes parameters necessary for worker operation and type of worker
            #Returns an object with the given parameters
            self.runInfo=runInfo
            self.crit=crit
            self.chkFile=chk
            self.raw=raw
            self.cal=cal

    def extractAll(self):
        #Returns values for all parameters in a standard order
        return (self.runInfo,self.raw,self.cal,self.chkFile,self.crit)

#Dummy object to hold various data
class Struct(object): pass
#_____________________SCRIPT MAIN AND MAIN HELPERS________________#

def init():
    (version,revision,status)=getVersion()
    print("\n%s %s %s (%s) now running...."%(NAME,("v."+version),status,revision))
    runInfo=runParams()
    runInfo.loadParams()
    files=Struct()
    sTime=time.time()
    listFiles(runInfo,files)
    eTime=time.time()
    print('File Search and Concatenation took:  %d seconds' %(eTime-sTime))
    process(runInfo,files)

def getVersion():
    #Imports version information from version.txt file
    versionFileDict=config.importDict(VERSPATH)
    version=versionFileDict['Version']['RDCversion']
    revision=versionFileDict['Version']['RDCrevision']
    status=versionFileDict['Status']['RDCstatus']
    return (version,revision,status)

##________________Searching for files__________________________##
def listFiles(runInfo,files):
    sTime=time.time()
    getFilesTime=0
    files.raw=dict()
    files.cal=dict()
    if runInfo.get("Auto Checks"): files.err=dict()
    concatFilesDir=runInfo.get("Concatenated Files Directory")
    #Creates error file list, if the option is enabled
    print("Locating files...")
    for rampNum in runInfo.rampDict: #Go ramp by ramp through the ramp selection
        ramp=runInfo.rampDict[rampNum]
        concatDir=os.path.join(concatFilesDir,"s%s" %str(rampNum))
        #Precompile dicts of dates mapped to sets of paths for which these dates are present
        serverDict=precompilePathSet(ramp.dirs["Server"])
        sdDict=precompilePathSet(ramp.dirs["SD"])
        nFiles=0
        for date in runInfo.get("Date Range"): #Go date by date
            (sdFiles,serverFiles)=(set(),set())
            if date in sdDict: #Get SD files corresponding to the date
                paths=sdDict[date]
                sdFiles=getDateFiles(ramp,date,paths,SD=True) 
            if date in serverDict: #Get server files corresponding to the date
                paths=serverDict[date]
                serverFiles=getDateFiles(ramp,date,paths,SD=False)
            rawFileSD=rawFile.get.bestFile(sdFiles,concatDir) 
            rawFileServ=rawFile.get.bestFile(serverFiles,concatDir)
            readFile=rawFile.get.bestFile({rawFileServ,rawFileSD},concatDir) #THERE CAN BE ONLY ONE
            if readFile!=None: 
                addFile(files,readFile,runInfo)
                nFiles+=1
        if nFiles==0 and runInfo.get("Print Output"):
            print("RAMP %d: No useable files found" %rampNum)

def precompilePathSet(dirList):
    #outputs a set of all date files in a directory and returns it
    dateDict=dict()
    for folder in dirList:
        fDateDict=config.pull.dates.fromDir(folder,pathDict=True)
        config.mergeDicts(dateDict,fDateDict)
    return dateDict

def getDateFiles(ramp,date,pathList,SD=False):
    #Converts a set of paths for a given ramp, date and SD status into a rawFile object
    dateFiles=set()
    for path in pathList:
        file=rawFile(ramp,date,path=path,SD=SD)
        dateFiles.add(file)
    return dateFiles

def addFile(files,readFile,runInfo):
    ramp=readFile.ramp
    date=readFile.date
    writeFile=calFile.create(readFile,runInfo)
    if runInfo.get("Auto Checks"): chkFile=errorFile.create(readFile,runInfo)
    if ramp in files.raw:
        files.raw[ramp].append(readFile)
        files.cal[ramp].append(writeFile)
        if runInfo.get("Auto Checks"): files.err[ramp].append(chkFile)
    else: #In case the lists of files have not been created yet
        files.raw[ramp]=[readFile]
        files.cal[ramp]=[writeFile]
        if runInfo.get("Auto Checks"): files.err[ramp]=[chkFile]
    if runInfo.get("Print Output"): print(readFile) #Print the file if requested

##______________Processing____________________________##

def process(runInfo,files):
    #Wrapper for initializing processing routines
    (lenFiles,sFiles)=getRawLen(files.raw) #Get the number and total size of query

    if lenFiles==0:
        print("No useable RAMP files found. Please check that:\
        \n1. The raw directory address is correct\
        \n2. The raw directory is populated\
        \n3. RAMP files in the raw directory are not corrupted\
        \n4. RAMP files have useable timestamps (e.g. not 21/75/128 00:153:27)")
        return

    sFiles=sFiles/(1024**2) #Change size from bytes to Mb
    rTime=getEstRunTime(lenFiles,runInfo)/60.0 #Compute a runtime estimate

    print("%d files found (%d MB)" %(lenFiles,sFiles))
    print("Estimated Time to Completion: %.2f minute(s)" %rTime)
    print("\nBeginning Processing:\n")
    
    start=time.time() #Start a runtime timer

    if runInfo.get("Multiprocess"): parallelProcess(runInfo,files)
    else: serialProcess(runInfo,files)
    print("\nProcessing Complete")
    
    end=time.time() #End runtime timer

    print("%d files (%d MB) cleaned in %.1f seconds" %(lenFiles,sFiles,end-start))
    
    if runInfo.get("Log Performance"):
        logPerformance(runInfo,lenFiles,sFiles,end-start)

def getEstRunTime(nFiles,runInfo):
    clockSpeed=4e9 #Assumed clock speed in Hz
    parallel=runInfo.get("Multiprocess")
    cCount=runInfo.get("Num. Process")
    czechs=runInfo.get("Auto Checks")
    if parallel:
        if czechs: fCycles=3.4e10
        else: fCycles=1.1e10
        estTime=fCycles*nFiles/(cCount*clockSpeed)
    else:
        if czechs: fCycles=6.3e9
        else: fCycles=1.96e9
        estTime=fCycles*nFiles/clockSpeed
    return estTime

def serialProcess(runInfo,files):
    #Calls a helper to organize params,
    #Then calls a woker on each set of params
    workerParamSeq=organizeByFile(runInfo,files)

    for workerInput in workerParamSeq:
        fileWorker(workerInput)

def parallelProcess(runInfo,files):
    workerInput=organizeByFile(runInfo,files)
    worker=fileWorker

    numProc=runInfo.get("Num. Process")
    if not numProc: numProc=2

    print("Allocating %d processes to the parralel pool" %numProc)
    print("Please wait, this may take some time...")
    with Pool(numProc) as p:
        p.map(worker,workerInput)

def organizeByFile(runInfo,files):
    #Pulls and compacts all necessary parameters from runInfo and files
    #into structs to be passed to fileWorker
    err=runInfo.get("Auto Checks")
    rm=runInfo.get("Auto Remove")
    (raw,cal)=(files.raw,files.cal)
    
    if err: chk=files.err
    else: chk=None

    if err or rm: crit=critLoader(CRITPATH,CONSTPATH)
    else: crit=None

    out=[]
    for ramp in raw:
#        pdb.set_trace()
        for i in range(len(raw[ramp])):
            if err:
                ap=workParams(runInfo,raw[ramp][i],cal[ramp][i],chk[ramp][i],crit)
            else:
                ap=workParams(runInfo,raw[ramp][i],cal[ramp][i])
            out.append(ap) 
    return tuple(out)

def fileWorker(workInput):
    #I know opening and closing inside a worker seems stupid, but I
    #think the multiprocessing library has a built-in mutex lock
    (runInfo,raw,cal,chk,crit)=(workInput.extractAll())
    printOut=runInfo.get("Print Output")
    openIO(raw,cal,printOut,chk)
    writeStartLines(raw,cal,chk)
    readWrite(runInfo,raw,cal,crit,chk)
    closeIO(raw,cal,chk)

def openIO(raw,cal,printOut,chk=None): 
    raw.open()
    if chk:
        if not os.path.isdir(chk.dir): 
            os.makedirs(chk.dir)
            if printOut:print("\nCreated Directory %s" %chk.dir)
        chk.open('w')
    if not os.path.isdir(cal.dir):
        os.makedirs(cal.dir)
        if printOut:print("\nCreated Directory %s" %cal.dir)
    cal.open('w')

def closeIO(raw,cal,chk=None):
    raw.close()
    cal.close()
    if chk: chk.close()

def writeStartLines(raw,cal,chk=None):
    cal.writeStartLine()
    if chk: chk.writeStartLine(raw)

def readWrite(runInfo,raw,cal,crit,chk=None):
    printOut=runInfo.get("Print Output")
    if printOut: print("Processing file:\n%s" %str(raw)) #Print to terminal if option is enabled

    #Initialize error tracker if needed:
    if chk: tracker=errorTracker(runInfo,cal,raw.getSize(),crit,errorFile=chk) 
    elif runInfo.get("Auto Remove"): tracker=errorTracker(runInfo,cal,raw.getSize(),crit)
    else: tracker=None

    line=raw.readline() #Get first line of raw file

    #Check if line has v9.xx firmware. If so, don't bother checking subsequently
    #Otherwise, check every line
    isV9=parse.v9.check(line)

    while line!="":
        #Performs firmware checks only until v.9.xx firmware is detected
        if isV9: parse.v9.chunk(line,cal,tracker) #Parses raw string, does write and tracker push operations
        else: isV9=parse.blind(line,cal,tracker) 
        line=raw.readline() #Continue reading lines
    if printOut: print("Processed and published to:\n%s" %str(cal)) 
    #Lets the user know that a file has been processed successfully if option is enabled
    if chk: #If auto checks are on
        tracker.publishReport()
        if printOut: print("Error report published to:\n%s" %str(chk))
        #let user know that error reports were written successfully (if enabled)
    if printOut: print('\n') #Blank line between reports of processing completion

class parse(object): #Collection of methods used to parse a line of data
    @staticmethod
    def blind(line,cal,tracker=None): 
        """Checks if a line is likely from v8.xx firmware or v9.xx firmware
        if either, calls the appropriate parsing function and returns if the firmware is v9.xx
        if neither, returns an empty dictionary
        Short circuited to prioritize V9 line detection
        """
        if parse.v9.check(line):
            parse.v9.chunk(line,cal,tracker)
            return True
        elif parse.v8.check(line):
            parse.v8.chunk(line,cal,tracker)
            return False
        else: return False

    class v8(object):
        def __init__(self): pass

        @staticmethod
        def check(line): #Check if line is consistent with v.8.13 - 8.44 RAMP firmware
            #Determine whether the line is at least a 5-element "X"-delimited list
            minLength=5
            lineList=line.split("X")
            if len(lineList)<minLength: return False
            #Determine whether "DATE" and "ECHEM" fields are present, minimum requirements for a useful line
            keyTerms={'DATE','ECHEM'}
            for key in keyTerms:
                if line.find(key)==-1: return False
            #If the line passes these checks, it is likely a v8.xx line
            return True

        @staticmethod
        def chunk(line,cal,tracker=None): #Wrapper for parse.v8.line(), additionally handles reading/writing
            pDict=parse.v8.line(line,cal,tracker)
            wLine=parse.config4Writing(pDict,cal) #Rewrites dictionary as an output string
            if wLine!=None: cal.write(wLine)  #If valid string, write to processed file

        @staticmethod
        def line(line,cal,tracker=None): #Processes the data for older firmware (v.8.13 - 8.44)
            parsedDict=dict()
            dtStr='DATE'
            line=line.split("X")
            for i in range(len(line)):
                elem=line[i]
                if elem.startswith(dtStr):
                    dateReader=read.v8.options()[dtStr] #Pull the datetime reader function
                    dateTime=dateReader(elem,cal.date)
                    if tracker!=None: dateTime=tracker.push(dtStr,dateTime)
                    if dateTime!=None: 
                        parsedDict[dtStr]=dateTime
                        line.pop(i) #Remove the datettime element from list so as not to double-read
                        break #Stop the loop once a valid datetime has been found
                    #If a valid datetime has not been found, check the rest of the line
            try: #If date could not be established, do not read or track line
                if dateTime==None: return None
            except: return None
            for elem in line:
                (eType,eParsed)=parse.v8.element(elem,tracker)
                if eParsed: parsedDict[eType]=eParsed
            return parsedDict

        @staticmethod
        def element(elem,tracker): #Determines which parsing function to use and applies it
            #Pushes the read values to a tracker and returns them if valid
            pDict=read.v8.options() #Map of parameter name to read method
            for key in pDict.keys(): #Check which element the parser is dealing with         
                if elem.startswith(key):
                    readings=pDict[key](elem) #Applies the appropriate reading function
                    if tracker: readings=tracker.push(key,readings) #Passes the values to a tracker
                    if readings: return (key,readings) #Returns readings if valid
                    else: return (None,None) #Otherwise returns nothing
                elif tracker!=None and elem.startswith("CON"): #Checks for XCONNECT flags
                    tracker.push("STAT","XCON")
                    return(None,None)
            return (None,None)

    class v9(object):
        def __init__(self): pass

        @staticmethod
        def check(line):  #Check if line is consistent with v.9.13+ RAMP firmware
            #Look for keywords
            keyTerms={'DATE','RAW','T','RH','CHRG','RUN'}
            for key in keyTerms:
                if line.find(key)==-1: return False
            #Look for anti-keywords
            antiKey={'ECHEM'}
            for key in antiKey:
                if line.find(key)!=-1: return False
            #If all the keywords are present, attempt to process
            return True 

        @staticmethod
        def chunk(text,cal,tracker=None): #Wrapper, handles line splitting
            dataHeader="DATE"
            isolatedLines=text.split(dataHeader) #Try to break up multiple data points between line breaks
            if len(isolatedLines)>1: #Only try to parse if a "DATE" header was found
                for singleLine in isolatedLines[1:]:
                #Go thru points one-by-one (fist element definitely not a data pt, no "DATE" header)
                    pDict=parse.v9.line(singleLine,cal,tracker)
                    wLine=parse.config4Writing(pDict,cal) #Rewrites dictionary as an output string
                    if wLine!=None: cal.write(wLine)

        @staticmethod
        def line(line,cal,tracker=None): #Processes data for new firmware (v.9.13 and up)
            #Takes a 'decapitated' line, i.e. ",mm/dd/yy,..." to parse
            #parsedDict=copy.deepcopy(cal.parsedBlankDict) #Map to store parsed values
            parsedDict=dict()

            lineList=line.split(",") #Values are comma-delimite
            #The date header should now be the first element in the list, and the date the second:

            if len(lineList)>2: #i.e. if there is more than just a time stamp in the line
                #pass2Parser=','.join(['DATE',lineList[1]]) #Second element assumed to be the date
                dateTime=read.timeStamp(lineList[1],cal.date)
                if tracker:  dateTime=tracker.push('DATE',dateTime)
                if dateTime!=None: 
                    parsedDict['DATE']=dateTime #Add to output if time stamp is valid
            readingsID=2 #Third list element onward assumed to be the start of readings (after time stamp)
            return parse.v9.substrings(parsedDict,lineList[readingsID:],cal.catNameDict,tracker) #Get value map

        @staticmethod
        def substrings(parsedDict,line,rParamDict,tracker=None):
            #Parse the data string after the time stamp
            tempDict=dict()
            pDict=read.v9.options() #Get map of readable headers
            eLenDict=read.v9.expectedLengths() #Get map of readable headers:expected number of outputs
            readableSet=pDict.keys()
            i=0 #Start immediately after the time stamp
            #Run thru line and attempt to parse out elements
            while i<(len(line)-1):
                elem=line[i]
                if elem in readableSet: #if header is known by the reader, attempt to parse
                    #If header is in the map of expected lengths, reterieve that value:
                    if elem in eLenDict: expLen=eLenDict[elem]
                    else: #Otherwise, assume there is only one
                        expLen=1

                    expDatLst=line[i:i+expLen+1] #Isolate data thought to be pertinent to the header
                    multiHeader=len(readableSet & set(expDatLst))>1 
                    if multiHeader:#i.e. if more than one header in isolated list
                        i+=1
                        continue
                    else:#Otherwise, try to parse
                        #pass2Parser=','.join(expDatLst) #prepare string to be parsed
                        readings=pDict[elem](expDatLst) #Get output
                        if readings==None:
                            #Continue to next parameter if could not be parsed
                            i+=1
                            continue
                        #Use a random header for current element as determinant for category
                        #(all headers in 'readings' should be in the same category)
                        randHeader=next(iter(readings.keys())) #Random header from output
                        catName=rParamDict[randHeader]
                        if catName in tempDict:
                            tempDict[catName].update(readings)
                        else:
                            tempDict[catName]=readings
                        i+=expLen+1
                else: i+=1
            #Run all parsed readings through the tracker (so that all readings are there)
            if tracker:
                for cat in tempDict:
                    try:
                        parsedDict[cat]=tracker.push(cat,tempDict[cat])
                    except: 
                        raise RuntimeError(cat,tempDict[cat])
                return parsedDict
            else:
                tempDict.update(parsedDict)
                return tempDict

    @staticmethod
    def config4Writing(pDict,cal):
        if pDict==None: return None #If whole line couldn't be read (e.g. bad date stamp)
        outList=cal.pDict2valLine(pDict)
        nLine=stringify(outList)
        dlm=","
        nLine=dlm.join(nLine)+"\n"
        return nLine

def logPerformance(runInfo,lFiles,sFiles,runTime):
    #Records completion speed and other statistics
    speed=4e9 #Processor clock speed
    perfPath=PERFPATH #Full path to performance file
    performance=open(perfPath,'a+')
    #Format: nFiles,Size,Checks,R/F,Print,nProc,Time,FPS,FPS/core,pCycles,Throughput,pCycles/file
    if runInfo.get("Auto Checks") or runInfo.get("Auto Remove"): checks="Y"
    else: checks="N" #Shows that checks are enabled when Auto Checks or Auto Remove are on
    if runInfo.get("Print Output"): printOut="Y"
    else: printOut="N"
    if runInfo.get("Multiprocess")==False: nProc=1
    else: nProc=runInfo.get("Num. Process")
    fps=runTime/lFiles #Files per second
    fpsC=fps/nProc #Files per second per core
    pCycles=speed*runTime*nProc #pseudoCycles to complete program
    thruPut=sFiles/runTime #Amount of data processed per second
    pCyclesF=pCycles/lFiles #pseudoCycles per file
    pCyclesS=pCycles/sFiles #pseduoCycles per MB
    out=[lFiles,sFiles,checks,printOut,nProc,runTime,fps,fpsC,pCycles,thruPut,pCyclesF,pCyclesS]
    out=stringify(out)
    nLine="\n"+",".join(out)
    performance.write(nLine)
    performance.close()
    print("\nPerformance recorded in: %s" %perfPath)

#________________OTHER HELPER FUNCTIONS____________________________#

def dateRangeFormatChecker(s):
#Format:yyyy-mm-dd/yyyy-mm-dd
    try:
        s0=s.split("/")
        str2Date(s0[0])
        str2Date(s0[1])
        return True
    except: return False

def range2Dates(L): #transforms a date range into a list of dates
    dateList=[]
    rng=L.split("/")
    try:
        sDate=str2Date(rng[0])
        eDate=str2Date(rng[1])
        if sDate>eDate: (sDate,eDate)=(eDate,sDate) #In case the range is backwards
    except ValueError:
        print("\nERROR\nInvalid Date Range\n\
            Please make sure it is entered in the format: yyyy-mm-dd/yyyy-mm-dd")
        return []
    cDate=sDate
    day=datetime.timedelta(days=1)
    while cDate<=eDate:
        dateList+=[cDate] #Appends a date
        cDate+=day
    return(dateList)

def str2Date(s):
#Input format: y-m-d-> datetime object
    (y,m,d)=s.split("-")
    (y,m,d)=(int(y),int(m),int(d))
    return datetime.date(y,m,d)

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

def stringify(L):
#Turns lists/sets of integers,floats, etc. into list of strings
    newL=[]
    for item in L:
        if item==None: newL.append("")
        else: newL.append(str(item))
    return newL

def flatten(L):
#Collapses a list of lists into a single list of base elements
    if L==[]: return L #Base case that Catches empty lists
    elif type(L)!=list: return L #base case that catches nonlist elements
    elif type(L[0])==list: #recursively flattens a sublist
        flatList=flatten(L[0]) 
        return flatList+flatten(L[1:])
    else: return [L[0]]+flatten(L[1:]) 

def getListVals(L,Ind):
#returns the values of a list at corresponding indexes
    Ind=sorted(list(Ind))
    rL=[None]*len(Ind)
    for i in range(len(Ind)):
        rL[i]=L[Ind[i]]
    return Ind

def FtoC(F):
    if type(F)!=float: #In case the input is non-numeric
        try: F=float(F)
        except: return None
    return round((F-32)*5/9,1)

def concatenatePath(L):
#Takes a path as a list or tuple, concatenates it into a single string
    cPath=L[0]
    L=L[1:]
    for elem in L:
        cPath=os.path.join(cPath,elem)
    return cPath

def getRawLen(D):
    counter=0 #Keeps track of total file length
    sCounter=0 #Keeps track of total file size
    for ramp in D:
        counter+=len(D[ramp])
        for file in D[ramp]:
            sCounter+=file.size
    return (counter,sCounter)

def transferDictVals(pDict,tgtDict,app=None):
    #Takes two dictionaries with shared keys, 
    #transfers information over from pDict to tgtDict for shared keys
    #Optionally appends the keys in pDict
    #function takes advantage of aliasing and does not return
    for key in pDict:
        if (type(key)==type(app)) : keyTgt=key+app
        else: keyTgt=key
        if keyTgt in tgtDict: tgtDict[keyTgt]=pDict[key]

def blankIterable(I):
    return len(I)==0

def closestDateRange(ranges,date=None):
    #Given a list of date range strings chooses:
    # one with the latest expiration date if no date is given
    # one closest to date if it is given
    latestDate=None
    for dateStr in ranges:
        dates=dateStr.split("/")
        d1=str2Date(dates[0])
        d2=str2Date(dates[1])
        if d2<d1: (d1,d2)=(d2,d1) #Swaps in case the order is backwards
        if latestDate==None:
            latestDate=(dateStr,d1,d2)
        elif date and closerDate((d1,d2),latestDate,date): 
            latestDate=(dateStr,d1,d2)
        elif not(date) and laterDate((d1,d2),latestDate): 
            latestDate=(dateStr,d1,d2)
    return latestDate[0]

def laterDate(dates,lastDate):
    #Returns true if either the start of the range is later
    #or the end is later if the start dates are equal
    d1=dates[0]
    d2=dates[1]

    ld1=lastDate[1]
    ld2=lastDate[2]

    if d1>ld1: return True #i.e. if newer
    elif ld1==d1 and d2>ld2: return True 
    #If start at same time, one that expires later
    else: return False

def closerDate(dates,lastDate,tgt):
    #Returns true if the start date of the range is closer to the target date
    zdt=datetime.timedelta(0)

    d1=dates[0]
    d2=dates[1]

    diffD1=tgt-d1
    diffD2=tgt-d2

    ld1=lastDate[1]
    ld2=lastDate[2]

    diffLd1=tgt-ld1
    diffLd2=tgt-ld2

    #i.e. if start date is closer and either:
    #start date is before target date
    #both dates are after the target date
    if abs(diffD1)<=abs(diffLd1) and (diffD1>=zdt or diffD2<zdt): return True

if __name__ == '__main__':
    multiprocessing.freeze_support() #Enables conversion to executable
    init()