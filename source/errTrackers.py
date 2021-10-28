#__CHANGELOG__#
    #2018-11-14
        #Switched Error Tracker to get criteria et
    #2018-11-13
        #Fixed bug where subTrackers kept receiving a delta-T of zero
    #2018-11-1
        #Routines for loading bounds.ini and const.ini moved to separate obj
            #-Will later be called outside errorTracker to give errorTracker its parameters
        #Overhauled bounds.ini and how the ini files are parsed
    #2018-10-30
        #Work Started on converting all trackers to use integer POSIXTIME
    #2018-10-24
        #Created (pulled out of RDC 0.1.2 WIP)
    #2018-12-04
        #Updated algorithm for calculations of averages in ddtTracker: improved performance

import datetime as dt
import copy
from confReader import config
from genericHelpers import *

class critLoader(object):
    #This object will parse bounds.ini and const.ini, pulling values from them and
    #storing them in corresponding dictionaries
    def __init__(self,critPath,constPath):
        (self.pSet,
        self.bpDict,
        self.collectionDict)=critLoader.loadCriteria(critPath)   #Parse bounds.ini
        self.cpDict=critLoader.loadConst(constPath)          #Parse const.ini
        (self.bDict,self.cDict)=critLoader.collectCriteria(self.collectionDict,
                                                    self.bpDict,self.cpDict)

    @staticmethod
    def loadCriteria(critPath):
        #Parses the CRITERIA file in the program's directory to determine
        #criteria for throwing error flags
        contents=config.importDict(critPath,delimit=True,dlm=",")
        (pSet,collDict)=critLoader.getParams(contents["ASSIGNMENT"])
        bDict=critLoader.getBounds(contents,pSet)
        return (pSet,bDict,collDict)

    @staticmethod
    def getParams(assignDict):
        #Given a dictionary mapping tracker->list of parameters
        #Returns the set of values in the lists as well as original dictionary
        #but with lists of parameters replaced by sets
        pSet=set() #parameter Set: will hold set of all parameter names in bounds.ini
        collDict=dict() #Will map tracker name to which parameters it needs from bounds.ini
        for tracker in assignDict:
        #Go thru dict mapping tracker name -> list of parameters it needs
        #e.g. 'CO2'->['CO2','T','RH']
            params=assignDict[tracker]
            if params==None: collDict[tracker]=set()
            elif type(params)==list: #If more than one param per key
                #Convert params to set with leading/trailing whitespaces removed:
                pSubSet={elem.strip() for elem in params}
                pSet=pSet.union(pSubSet) #Update the set of all parameters
                collDict[tracker]=pSubSet #Update collection dictionary
            elif type(params)==str: #If only one param assigned to key
                pSet.add(params) #Add single param to set
                collDict[tracker]={params} #update collection dict
        return (pSet,collDict)

    @staticmethod
    def getBounds(contents,pSet):
        #Calls a helper to get a decode dictionary of columns
        #e.g {'lower':1, 'upper':2, etc.}
        decode=critLoader.getBoundsDecode(contents["DECODE"])
        rDecode=reverseDict(decode) #Flip mapping: index->value
        bData=contents["BOUNDS"]
        bDict=dict() #Initialize output dictionary
        for key in bData: #Go thru keys in the bounds table
            if key in pSet: 
            #Try to decode only if specified in 'ASSIGNMENT' section of bounds.ini

                #Initialize subdict for the parameter as a noneDict:
                bDict[key]=dict() 
                for dc in decode: bDict[key][dc]=None

                #Attempt to parse in:
                val=bData[key]
                if type(val)==list: #Only try to iterate if a list of values is given
                    for i in range(len(val)): #Iterate through values
                        if i in rDecode: #If corresponding value is present in list
                            valType=rDecode[i] #Get the value type (e.g. lower, upper, etc.)
                            bDict[key][valType]=critLoader.parseVal(val[i]) #Attemtp to convert
                elif type(val)==str: #i.e. if only one element after "=" sign
                    if 1 in rDecode:
                        valType=rDecode[1]
                        bDict[key][valType]=critLoader.parseVal(val[i])
        return bDict

    @staticmethod
    def getBoundsDecode(decode):
        #Converts string 
        newDecode=dict() #Blank dictionary to be populated and returned
        for key in decode:
            val=decode[key]
            try: newDecode[key]=int(val)
            except: newDecode[key]=None
        return newDecode

    @staticmethod
    def parseVal(val):
        #Attempt to convert a string value to a correct data type
        dtStr=':' #Values with this character will be read as timedelta in h:m:s
        floatStr1='.' #If this char in val, convert to float
        floatStr2='e' #if this char in val, convert to float
        val=val.strip() #Remove leading/trailing whitespace
        valCharSet=set(val) #Set of all characters in the string
        if dtStr in valCharSet:
            #Try to convert to time delta and then to seconds (to use w/POSIXTIME)
            try: return round(str2TimeDelta(val).total_seconds())
            except: return None
        elif ((floatStr1 in valCharSet) or (floatStr2 in valCharSet)):
            #try to convert to float if specific characters present
            try: return(float(val))
            except: return None
        else: #If not a special case, try to convert to integer. 
            try: return (int(val))
            except: return None

    @staticmethod
    def loadConst(constPath):
        #Loads constants from a file to be later used in individual trackers
        contents=config.importDict(constPath,delimit=False)
        for tracker in contents:
            for param in contents[tracker]:
                contents[tracker][param]=critLoader.parseVal(contents[tracker][param])
        return contents

    @staticmethod
    def loadConst_OldButQuick(constPath):
        #Loads constants from a file to be later used in individual trackers
        constDict=dict()   #Stores in format: {trackerName:{parameter:value}}
        constFile=constPath
        try: constFile=open(constFile,'r')
        except: raise FileNotFoundError("No file in the following path: %s" %const)
        line=constFile.readline()
        category=None
        while line!="": #Loop that reads the file text line by line
            entry=None
            while line.startswith("#"): 
                line=constFile.readline() #Skip over comments
            if line.startswith("[") and line.endswith("]\n"): #Indicators of category name
                category=line[1:-2] #Saves the category, chops off brackets and \n
                if category=="": category==None
                elif category not in constDict: constDict[category]=dict() #Adds category to dict
            elif category!=None and len(line)>1: 
                if line.endswith("\n"): line=line[:-1]  #Removes the \n at the end of every line
                try:
                    line=line.split("=") #parameter=value
                    parameter=line[0]
                    value=line[1]
                    if ":" in value: 
                        entry=str2TimeDelta(value) #Try to read a time in h:m:s format
                        entry=entry.total_seconds() #Convert entry to No. of seconds
                    else: #Must be either a float or an integer
                        try: 
                            if "." in value or "e" in value:
                                entry=float(value) #Implies a floating-point value
                            else: entry=int(value) #Integer by default
                        except: pass
                    if entry!=None:
                        constDict[category][parameter]=entry
                except: pass #Do not bother with lines that cannot be read
            line=constFile.readline()
        constFile.close()
        return constDict

    @staticmethod
    def collectCriteria(collectionDict,bDict,cDict):
    #Collects loaded data on bounds,spike, and flatline criteria into
    #tags seen in the raw file
        boundsDict=dict()
        constDict=dict()
        for key in collectionDict:
            boundsDict[key]=dict()
            constDict[key]=dict() 
            for param in cDict["General"]: #Transfer general values to eaach tracker
                constDict[key][param]=cDict["General"][param]
            if key in cDict:
                #Copy tracker specific constants and
                #override general values with ones specific for the tracker
                for param in cDict[key]:
                    constDict[key][param]=cDict[key][param]
            for subkey in collectionDict[key]:
                boundsDict[key][subkey]=bDict[subkey]
        #   A   A   A   A
        #   |   |   |   |
        #Reorganizes criteria in the following format: 
        #Category:{parameter1:crtieria, paramter2:criteria, etc.}
        #e.g. CO2:{T:{lower:-20C,upper:50C,spike:1ug*m^-3*min^-1,flatT: 5h,0m,0s ,flatS:0.1C/hr}}
        return (boundsDict,constDict)

class errorTracker(object):
    #Responsible for initializing parameter-specific trackers
    def __init__(self,runInfo,cal,rawSize,crit,errorFile=None):
        ramp=cal.ramp
        self.fSize=rawSize
        self.file=errorFile
        self.critLoader=crit
        #self.critLoader=critLoader(crit[0],crit[1])
        self.remove=runInfo.get("Auto Remove")
        self.autoChk=runInfo.get("Auto Checks")
        self.dispEphErr=runInfo.get("Show Instantaneous Errors")
        self.echem=cal.echem
        self.params=set(cal.order.keys())
        self.setErrorTracking(runInfo)

    def setErrorTracking(self,runInfo):
        #Initializes helper tracker objects that'll handle their own categories 
        if self.autoChk or self.remove: #Initialize if Auto Checks or Auto Remove are enabled
            (bDict,cDict)=(self.critLoader.bDict,self.critLoader.cDict)
            self.subTrackers=\
                { #Creates tracker helpers and passes them the required parameters
                "DATE":     tGapTracker(runInfo.get("Time Gap"),self.fSize,cDict["DATE"])
                ,"METEO":   valTracker(runInfo,"METEO",bDict["METEO"],cDict["METEO"])
                ,"ECHEM":   eChemTracker(runInfo,"ECHEM",bDict["ECHEM"],cDict["ECHEM"],self.echem)
                ,"MET":     metTracker(runInfo,"MET",bDict["MET"],cDict["MET"])
                ,"TSI":     tsiTracker(runInfo,"TSI",bDict["TSI"],cDict["TSI"])
                ,"ADI":     adiTracker(runInfo,"ADI",bDict["ADI"],cDict["ADI"])
                ,"PPA":     ptrTracker(runInfo,"PPA",bDict["PPA"],cDict["PPA"])
                ,"PTR":     ptrTracker(runInfo,"PTR",bDict["PTR"],cDict["PTR"])
                ,"PWR":     battTracker(runInfo,"PWR",bDict["PWR"],cDict["PWR"])
                ,"WIND":    valTracker(runInfo,"WIND",bDict["WIND"],cDict["WIND"])
                ,"GPS":     gpsTracker(runInfo,"GPS",bDict["GPS"],cDict["GPS"])
                ,"STAT":    statTracker(runInfo,"STAT",bDict["STAT"],cDict["STAT"])
                }

    def push(self,param,L=None):
        #Directs date from a category to the appropriate tracker
        if param in self.subTrackers: #Could potentially improve runtime by selecting option at initialization
            dateTrackNm="DATE"
            time=self.subTrackers[dateTrackNm].stamp["current"]
            dt=self.subTrackers[dateTrackNm].stamp["change"] #Calls last change in datetime from tGapTracker

            #Do not engage trackers and do not publish data in line if the timestamp could not be
            if time==None and param!=dateTrackNm: return None 

            if self.remove:  return self.subTrackers[param].push(L,time,dt)
            else: 
                self.subTrackers[param].push(L,time,dt)
                return L
        else: return L

    def publishReport(self):
        #Handles writing to the error checks file
        if self.file:
            dateTracker=self.subTrackers["DATE"]
            self.file.write("\t<_Begin Report_>\n")
            for key in self.subTrackers:
                self.subTrackers[key].publish(self.file,self.dispEphErr,dateTracker)
            self.file.write("\n\t<_End Report_>\n\n")

class valTracker(object):
    #Parent to other tracker objects (except time gap tracker)
    def __init__(self,runInfo,name,crit,const):
        self.autoChecks=runInfo.get("Auto Checks")
        #Convert time gap criterion into number of seconds (used w/POSIXTIME)
        self.connCrit=round(runInfo.get("Time Gap").total_seconds()) 
        self.name=name
        #self.decode=valTracker.getDecode(name)
        self.vals={"last": dict(), "current": dict(), "change": dict(), "output": dict()}
        self.crit=crit      #Criteria for bounds, spikes, flatlines, etc.
        self.const=const    #Constants such as disagreement criteria, time between posts, etc.
        self.flagNames=set()
        self.doNotAutoRemove=set()
        self.flat=dict()    #Stores current flatline
        self.flatDict=dict()#Stores flatline objects in a map: timeStamp -> flatLine obj
        self.eFlags=dict()  #Stores error flags as timeStamp -> error Flag
        self.ddt=dict()     #Stores a few downsampled points in memory to track noise and spikes
        self.ndFlag=dict()  #Stores the information needed for NO DATA flag
        self.ddtOn=False    #ddtTracker off by default
        self.setRoutines()  #

    def setRoutines(self):
        pass

    def setupddt(self):
        self.ddtOn=True
        for param in self.crit: #Set up ddtTracker for each parameter listed in the bounds file
            self.ddt[param]=ddtTracker(critT=self.crit[param]["spikeT"],
                                        critLen=self.const["ddtNumPts"])

    def push(self,val,time,dt):
        #Gives the tracker a new set of values to analyze
        if val!=None:
            self.vals["last"]=self.vals["current"] #Updates self.vals
            self.vals["current"]=val #Sets the current readings to what was pushed to the object
            self.vals["output"]=copy.deepcopy(self.vals["current"]) #Output line will be cleaned by checkAgainstCriteria()
            if self.autoChecks: self.checkConn(time,dt)
            if self.autoChecks: self.checkParsed(time,dt)
            self.timeDerivative(time,dt)
            self.checkAgainstCriteria(time,dt)
            return self.vals["output"]
        return None

    def checkConn(self,time,dt):
        #Keeps track of when the sensor has been connected and for how long, going from how
        #frequently the tracker receives pushes
        if time!=None:
            if "CONN" not in self.eFlags: 
                self.eFlags["CONN"]=[{  "start" : time,
                                        "end"   : time,
                                        "dur"   : 0,
                                        "lines" : 1
                                    }]
            elif dt!=None:
                lastConn=self.eFlags["CONN"][-1] #Reads the last element of the connection list
                if time-lastConn["end"]>self.connCrit: 
                    #Start a new conn entry if D/C time is longer than a single time gap 
                    self.eFlags["CONN"].append({
                                                "start" : time,
                                                "end"   : time,
                                                "dur"   : dt,
                                                "lines" : 1
                                                }) 
                #If a sensor has been disconnected for more than one post length, create a new connection entry
                else:
                    #Otherwise, update current connection entry
                    lastConn["end"]=time
                    lastConn["dur"]+=dt
                    lastConn["lines"]+=1

    def checkParsed(self,time,dt):
        #Adds flags based on how much data is being parsed in
        if dt!=0:
            curVals=self.vals["current"]
            #Initialize dataYield tracker if not already:
            if "General" not in self.ndFlag: self.ndFlag["General"]=dataYield(time,self.const)
            else: #Update the tracker if initialized:
                dataIn=not (curVals==None or (type(curVals)==dict and noneDict(curVals)))
                flagOut=self.ndFlag["General"].update(dt,time,data=dataIn)
                if flagOut!=None:
                    (flagName,time)=flagOut
                    self.addFlagEntry(None,flagName,time,rm=False) #Add a flag if the tracker says so
                if dataIn: #If there is data parsed in, check subcategories
                    for key in curVals:
                        #Initialized trackers for subcategories:
                        if key not in self.ndFlag: self.ndFlag[key]=dataYield(time,self.const)
                        entry=curVals[key]
                        #Determine whether there is data in the entry:
                        entryIn=not (entry==None or (type(entry)==dict and noneDict(entry)))
                        keyFlagOut=self.ndFlag[key].update(dt,time,data=entryIn)
                        if keyFlagOut!=None:
                            (flagName,time)=keyFlagOut
                            #Add a flag if the tracker say s so:
                            self.addFlagEntry(key,flagName,time,rm=False) 

    def timeDerivative(self,time,dt): 
        #Gets time derivative from last and current stamps
        last=self.vals["last"]
        current=self.vals["current"]
        if last!=None:
            for key in last:
                if (key.endswith("FLAG") or key in self.flagNames): return #Filters out error flags
                elif key not in self.ddt and self.ddtOn: self.ddt[key]=ddtTracker()
                if last[key]!=None and current[key]!=None and dt!=None:
                    change=last[key]-current[key]
                    if self.ddtOn: self.ddt[key].push(time,current[key],change,dt)
                    if dt>0: 
                        minuteChange=change*60.0/dt #Rate of change per minute
                        self.vals["change"][key]=(minuteChange,change)
                    else:
                        self.vals["change"][key]=None #In case of duplicate time stamps
                else: self.vals["change"][key]=None

    def checkAgainstCriteria(self,time,dt):
        #Decided whether values are out of bounds, spikes, error flags, or flatlines
        current=self.vals["current"] #Just to do less typing
        change=self.vals["change"]
        crit=self.crit
        for key in current:
            if key in crit:
                if key not in self.eFlags: self.eFlags[key]=dict()
                if current[key]==None: return #Skip iteration if value couldn't be read
                if ((crit[key]["lower"] and current[key]<crit[key]["lower"])
                    or (crit[key]["upper"] and current[key]>crit[key]["upper"])):
                    #If either out of bound criterion exists and is met
                    flag="OOB"
                    if key in self.doNotAutoRemove: remove=False
                    else: remove=True
                    self.addFlagEntry(key,flag,time,rm=remove)
                elif change!=dict(): #No spikes are reported during the OOB flag
                    cChange=change[key]
                    if cChange!=None: #Checks that change between two lines has been established
                        if self.ddtOn: self.trackNoiseAndSpike(key)
                        postChange=abs(change[key][1])  #change in value between two posts
                        self.trackFlatLine(key,current[key],postChange,crit[key],time,dt) 

    def trackNoiseAndSpike(self,key):
        minuteChange=self.vals["change"][key][0] #assigning variables to save on typing
        crit=self.crit[key]["spike"]
        critT=self.crit[key]["spikeT"]
        ddt=self.ddt[key]
        if crit==None: return #Skips if no spike criterion
        if not ddt.enoughData(): return #Skips noise/spike detection if insufficient data
        elif abs(minuteChange)>crit:
            if (abs(ddt.dVal*60)>crit):
            #If average derivative exceeds spike criterion and spike time criterion is met:
            #Avg. deriv. multiplied by 60 as it is output in units/s, not units/min
                flag="SPIKE"
                self.addFlagEntry(key,flag,ddt.tList,False)
            elif abs(ddt.avg_adVdt*60)>crit:
                #If the average of the abs(derivatives) is high
                flag="NOISE"
                self.addFlagEntry(key,flag,ddt.tList,False)

    def trackFlatLine(self,key,current,change,crit,time,dt):
        #Determines whether rate of change and its duration meet the criteria for a flatline
        if change==None: return #catches the case where out of bound values are removed
        if key not in self.flat: self.flat[key]=None
        if self.flat[key]==None and crit['flatS'] and crit['flatT'] and change<crit['flatS']:
            #Starts tracking the flatline if the criteria are given
            #And change between posts is less than some pre-defined value
            if key not in self.flatDict: self.flatDict[key]=set()
            #Adds parameter to flatline dictionary if not already there
            self.flat[key]=flat(current,time,time,dt,crit['flatT'],crit['flatS']) #initializes flatline as an object
        elif self.flat[key]: #Only works triggered if flatline criteria exist
            if self.flat[key].continues(current,dt):
            #if critical derivative is not exceeded, add time to flatline
                if self.flat[key].largeEnough():
                    #If flatline large enough, try to overwrite it in dictionary 
                    self.flatDict[key].discard(self.flat[key]) #Removes flatline object from set if present
                    self.flat[key].update(time,dt)
                    self.flatDict[key].add(self.flat[key])
                else: self.flat[key].update(time,dt)
            else: #Ends the flatline if critical derivative is exceeded
                self.flat[key]=None

    def checkFlag(self,time,flagName,normFlag,fDict=None):
        #Compares the error flags to a normal flag. Adds to the error dict if flag is abnormal
        #Optionally takes a dictionary of expected error flags and what they mean
        flag=self.vals["current"][flagName]
        if not(checkASCII(str(flag))) or flag==None: 
            self.vals["output"][flagName]=None #Removes non-ascii and NoneType flags
            return #Ensures that invalid flags are not compared or written
        if flag!=normFlag:
            if flagName not in self.eFlags: self.eFlags[flagName]=dict() 
            #adds the flag to the error dictionary if not already present
            if fDict!=None: #if passed a set of valid flags
                if flag in fDict: #if a flag is a valid error flag
                    fInterp=fDict[flag] #Flag interpretation from the dictionary
                    if fInterp!=None: #If a known error flag is detected, add the occurence time to a list
                        self.addFlagEntry(flagName,fInterp,time,False)
                else: self.vals["output"][flagName]=None #Removes the flag from the output, if unknown
            else:
                #creates a list of occurences of the flag if not list of valid ones is given
                self.addFlagEntry(flagName,flag,time)

    def addFlagEntry(self,key,flag,time,rm=False):
        #Adds the given flag for a given parameter to a list
        #Optionally removes the entry from the output list
        nonExcFlag={"SPIKE","NOISE"}
        #Add key and flag to error dict if not already present:
        #If key is not specified, just adds the error flag
        if key==None:
            if flag not in self.eFlags: self.eFlags[flag]=list()
            #Add stamp or stamps depending on whether a single or a list of time stamps was given
            if type(time)==list: self.eFlags[flag]+=time
            else: self.eFlags[flag].append(time)
            #Auto remove the flagged entries if they aren't spikes or noise
            if rm and (flag not in nonExcFlag): self.vals["output"]=None
        else:
            if key not in self.eFlags: self.eFlags[key]={flag:list()}
            elif flag not in self.eFlags[key]: self.eFlags[key][flag]=list()
            #Add stamp or stamps depending on whether a single or a list of time stamps was given
            if type(time)==list: self.eFlags[key][flag]+=time
            else: self.eFlags[key][flag].append(time)
            #Auto remove the flagged entries if they aren't spikes or noise
            if rm and (flag not in nonExcFlag): self.vals["output"][key]=None

    def publish(self,file,DER,dateTracker):
        #DER (boolean) Display Ephemeral Errors
        if file:
            report=self.compileReport(DER,dateTracker)
            file.write("\n\t"+self.name+':')
            file.write(report)

    def compileReport(self,DER,dateTracker):
        #DER: display ephemeral errors
        report=""
        catIndent=2 #Num(tabs) to category (e.g. CO2, T, RH, etc.)
        lineIndent=3 #Num(tabs to actual error stamp)
        self.mergeErrors()
        cStatus=valTracker.report.conn.status(dateTracker,self.eFlags,self.const,DER)
        report+=cStatus
        if self.eFlags==dict() or self.noErrors(): #Skips if no error flags found for category
            if cStatus=="\tConnected": return (report+"\tOK") 
            else: return report
        for param in self.eFlags:
            if param=="CONN": continue
            elif valTracker.noErrSubcat(self.eFlags[param]): continue 
            #Skips parameter if no error flags found for subcategory
            else:
                if type(self.eFlags[param])==dict: #For maps parameter->error->time series
                    subReport=""
                    intervals=list()
                    for error in self.eFlags[param]:
                        if error=="FLAT":
                            #Flatlines have a different format, and thus need a different parser
                            intervals+=valTracker.flatList2Intervals\
                                        (error,self.eFlags[param][error])
                        else:
                            intervals+=valTracker.dtList2Intervals\
                                                    (error,self.eFlags[param][error],DER,self.const)
                    subReport=valTracker.printIntervals(intervals,lineIndent,DER)
                    if subReport=="": continue #If nothing found after ephemeral errors are removed, skip category
                    else: report+='\n'+catIndent*"\t"+param+":"+subReport
                else: #Otherwise error is specified without parameter (for category in general)
                    intervals=valTracker.dtList2Intervals(param,self.eFlags[param],DER,self.const)
                    subReport=valTracker.printIntervals(intervals,lineIndent,DER)
                    if subReport=="": continue #If nothing found after ephemeral errors are removed, skip category
                    else: report+=catIndent*"\t"+subReport
        return report

    def mergeErrors(self):
        #merges error flags dictionary with flatline dictionary
        efSet=set(self.eFlags.keys())
        flSet=set(self.flatDict.keys())
        allParams=efSet.union(flSet) #Combined set of keys from both dictionaries
        for param in allParams:
            if param not in self.eFlags: self.eFlags[param]=dict()
            if param in self.flatDict: self.eFlags[param]["FLAT"]=self.flatDict[param]
        self.flatDict=None #clears flatDict to not take up RAM

    def noErrors(self):
        #Checks that error subdictionaries are empty
        for param in self.eFlags:
            if param=="CONN": continue #Skips the continuity parameter (not needed)
            subCat=self.eFlags[param]
            if type(subCat)==dict:
                for err in subCat:
                    if len(subCat[err])!=0: return False
            elif subCat==None: continue #Skip error entries with no time stamps in them
            elif len(subCat)!=0: return False
        return True

    class report(object):
        
        class conn(object):
            @staticmethod
            def status(dateTracker,eFlags,const,DER):
                #Determines whether sensors were connected or not. Adds nots to the report and returns it
                outReport=""
                (fStart,fEnd,gSet)=(dateTracker.stamp["start"],dateTracker.stamp["end"],
                                                                    dateTracker.gapSet)
                if "CONN" not in eFlags: outReport="\tDisconnected" #Means tracker never received a push
                else:
                    #Margin of error when comparing to end of day (defined in constants file)
                    eodMargin=const["eodMargin"] 
                    conn=eFlags["CONN"]
                    if len(conn)==1:
                        conn=conn[0]
                        (cStart,cEnd)=(conn["start"],conn["end"]) #Connection start and end times
                        if abs(fStart-cStart)<=eodMargin and abs(fEnd-cEnd)<=eodMargin:
                            outReport="\tConnected"
                        else:
                            #Prints CON and D/C messages if not near the end of day for the ramp
                            if abs(fStart-cStart)>eodMargin: 
                                cStartStr=str(dt.datetime.fromtimestamp(cStart))
                                outReport+="\tConnected at %s" %str(cStartStr)
                            if abs(fEnd-cEnd)>eodMargin: 
                                cEndStr=str(dt.datetime.fromtimestamp(cEnd))
                                outReport+="\tDisconnected at %s" %str(cEndStr)
                    elif len(conn)==0: outReport="\tDisconnected"
                    else:
                        outReport+=valTracker.report.conn.parseList(conn,const,dateTracker,DER)
                        if outReport=="":
                            #i.e. if all C and D/C stamps fall either on end of day or time gaps
                            return "\tConnected"
                return outReport

            @staticmethod
            def parseList(conn,const,dateTracker,DER):
                outReport=""
                #re-import file start and end times, as well as the set of time gaps
                (fStart,fEnd,gSet)=\
                            (dateTracker.stamp["start"],dateTracker.stamp["end"],dateTracker.gapSet)
                #how long the sensor needs to operate to be considered connected (def in const file)
                eodMargin=const["eodMargin"]
                critDCtime=const["critDCtime"]
                for i in range(len(conn)):
                    entry=conn[i]
                    #Connection start,end, duration, and number of lines:
                    (cStart,cEnd,cDur,cLines)=\
                                    (entry["start"],entry["end"],entry["dur"],entry["lines"])
                    #Check that the device has been posting for a significant amount of time: 
                    (connect,stamp)=valTracker.report.conn.connect(conn,i,fStart,fEnd,
                                                                        gSet,const,DER)
                    if connect:
                        if i==0: outReport+="\t" #First 'Connected' tabbed over once
                        else: outReport+="\t\t" #Subsequent are tabbed over twice
                        if stamp: 
                            cStartStr=str(dt.datetime.fromtimestamp(cStart))
                            outReport+="Connected at %s" %str(cStartStr)
                        else: outReport+="Connected" 
                    if valTracker.report.conn.disconnect(conn,i,fEnd,gSet,const,DER):
                            cEndStr=str(dt.datetime.fromtimestamp(cEnd))
                            outReport+="\tDisconnected at %s" %str(cEndStr)
                            #Add a new line, unless looking at final stamp:
                            if i!=len(conn)-1: outReport+="\n"
                if outReport=="": outReport+="\tIntermittent Connection"
                return outReport

            @staticmethod
            def entry(entry,const,DER):
                #Determines whether the entry is to be displayed or ignored
                return ((entry["dur"]>const["critOpTime"] and 
                        entry["lines"]>const["critOpLines"]) or DER)

            @staticmethod
            def connect(conn,i,fStart,fEnd,gSet,const,DER):
                #Check if it is appropriate to put a "Connect" flag and whether to 
                #report a time stamp with it
                (dispFlag,dispStamp)=(None,None)
                eodMargin=const["eodMargin"]
                cStart=conn[i]["start"]
                if valTracker.report.conn.entry(conn[i],const,DER):
                    #If it is the first post of the device:
                    if i==0 and abs(fStart-cStart)<eodMargin: return (True,False)
                    #If the device was connected not when a time gap ended:
                    elif cStart not in gSet: return (True,True)
                    #Display if a device was D/C before a time gap started, but reconnected
                    #When a time gap ended:
                    elif (i!=0 and 
                        valTracker.report.conn.disconnect(conn,i-1,fEnd,gSet,const,DER)):
                        return (True,True)
                return (False,False)


            @staticmethod
            def disconnect(conn,i,fEnd,gSet,const,DER):
                #Check if it is appropriate to put a "Disconnect" flag 
                eodMargin=const["eodMargin"]
                cEnd=conn[i]["end"]
                if abs(fEnd-cEnd)<eodMargin: return False #Don't display D/C at the end of day (eod)
                #Otherwise, do not display D/C for short entries unless DER is on:
                elif not valTracker.report.conn.entry(conn[i],const,DER): return False
                #Otherwise don't display if occurs at time gap, but not if it is a final entry
                elif cEnd in gSet and i!=len(conn)-1: return False  
                else: return True

    @staticmethod
    def dtList2Intervals(error,dtList,DER,const):
        if len(dtList)==0: return list()
        #Converts a list of time stamps into a list of intervals (start,end)
        tCrit=const["postLen"] #Length of one post @ 15s/line ratio=30
        tIso=const["tIso"] #Instantaneous errors this far apart from the next one get thrown out (if DER is)
        minLen=const["minErrLen"] #Throw away instances that do not recur within this interval
        #tCrit corresponds to minimum amount of error-free operation required to end an error flag
        intervals=list() #Stores time stamps as 
        start=dtList[0]
        end=dtList[0]
        if len(dtList)==1:
            if DER: return [(start,end,end-start,error)] #Display singular error if DER is on
            else:   return list()
        elif len(dtList)==2:
            dt=dtList[1]-dtList[0]
            if not DER:
                if dt>minLen and dt<tCrit: return [(start,dtList[1],dt,error)]
                else: return list()
            elif dt>=tCrit: 
                return [(start,end,end-start,error),(dtList[1],dtList[1],0,error)]
            else: return [(start,dtList[1],dt,error)]
        for i in range(1,len(dtList)-1):
            (stampL,stampM,stampH)=(dtList[i-1],dtList[i],dtList[i+1]) #Three adjacent time stamps
            (dt1,dt2)=(stampM-stampL,stampH-stampM) #delta-t between adj time stamps
            sdError=(type(error)==str and (error.startswith("SD") or error=="NO SD")) #Check of whether error is sd-related
            if (not DER) and (not sdError) and dt1>tIso and dt2>tIso: 
                (start,end)=(stampH,stampH)
                continue #Skip time stamp if isolated and not SD-related (those tend to cause skipping)
            if dt1<tCrit:
                end=stampM #extends end time if tCrit has not yet passed 
            else: #if tCrit has passed since last documented error, start new error stamp
                dur=end-start
                if DER or ((not DER) and (dur>minLen)):
                    intervals.append((start,end,dur,error))
                (start,end)=(stampM,stampM)
        dur=end-start
        if DER or ((not DER) and (dur>minLen)):
            intervals.append((start,end,dur,error)) #Loop always misses last interval
        return intervals

    @staticmethod
    def flatList2Intervals(error,flatList): 
        #Parses the list of flatlines and converts to format [(start1,end1),(start2,end2),etc.]
        intervals=list()
        for entry in flatList:
            intervals.append((entry.start,entry.end,entry.duration,error))
        return intervals

    @staticmethod
    def printIntervals(ivals,indent,DER):
        #Converts list of intervals into a report string
        #Format: start Time to end Time : error Code
        outStr=""
        indent="\n"+indent*'\t'
        ivals=sorted(ivals)
        for entry in ivals:
            (start,end,dur,errID)=(entry[0],entry[1],entry[2],entry[3])
            if dur>0: #Only records if errors have a finite duration
                start=str(dt.datetime.fromtimestamp(start).time())
                end=str(dt.datetime.fromtimestamp(end).time())
                dur=str(dt.timedelta(seconds=dur))
                outStr+="%s%s to %s (%s) : %s" %(indent,start,end,dur,errID)
            #Converts start and end datetimes to times for easier reading
        return outStr

    @staticmethod
    def getDecode(name):
        #Gets output format of the sensor(s) in the cal file
        #which is the same as the list format of the input to the push() method
        (params,order)=calFile.options()
        return params[name]

    @staticmethod
    def noErrSubcat(subcat):
        #Takes a subcategory and inspects it for presense of errors
        #e.g. checks if there are flatlines, spikes, etc. in RH sensor of CO2
        if type(subcat)==dict:
            for err in subcat:
                if len(subcat[err])!=0: return False
        else:
            if len(subcat)!=0: return False
        return True

class tGapTracker(object):
    #Looks for time gaps
    def __init__(self,tGapDur,fSize,const):
        #Convert duration into seconds to work w/posixtime
        #Convert duration from timedelta to seconds:
        self.minGapDur=round(tGapDur.total_seconds()) 
        self.fSize=fSize
        self.totalGapDur=0 #total duration of time gaps in seconds
        self.stamp={"last": None, "current": None,"change": None,
                    "start" : None,"end" : None}
        self.gapList=[]
        self.gapSet=set()
        self.flags=[]
        self.badStamps=0
        self.const=const

    def asessGap(self):
        #Decided whether adjacent time stamps are further apart than the time gap criterion
        #Assign last and current time to local variables (to save on typing):
        lastStamp=self.stamp["last"] 
        curStamp=self.stamp["current"]
        if self.minGapDur!=None and lastStamp!=None and curStamp!=None:
            #i.e. if time gap criterion, current and last stamp are defined
            dt=curStamp-lastStamp #difference between last and current time stamp
            if (dt>=self.minGapDur):
                #i.e. if more time has passed betweeh current and last stamp
                # than the time gap criterion
                gap=dict()  #Initialize the time gap as a dictionary
                #store the time gap in the form: 
                #{start:stamp1, end:stamp2, duration: stamp3}
                #Populate the dictionary:
                gap["start"]=lastStamp
                gap["end"]=curStamp
                gap["duration"]=dt
                self.gapList.append(gap) #Add gap to the list:
                #Add endpoints to a set used to cross-check against other errors:
                self.gapSet.add(lastStamp) 
                self.gapSet.add(curStamp)
                self.totalGapDur+=dt #keep track of total gap length
            self.stamp["change"]=dt #Update deltaT between two time stamps

    def push(self,dtIn=None,*args):
        #Updates object based on last time stamp fed to it
        key='POSIXTIME' #Key to access POSIX time in output dictionary
        if type(dtIn)!=dict:
            raise TypeError('Tracker requires a dictionary')
        elif key not in dtIn:
            raise KeyError('Datetime output does not contain POSIXTIME:\n%s' %str(dtIn))
        dt=dtIn[key]
        if dt==None:
            #If time stamp could not be parsed or converted to POSIX,
            #increment the badStamps counter 
            self.badStamps+=1
            return None
        #Set start stamp if one not set:
        elif self.stamp["start"]==None: self.stamp["start"]=dt 
        #Update the last time stamp:
        self.stamp["last"]=self.stamp["current"]
        # Update the current time stamp and end time for the file:
        self.stamp["current"]=dt
        self.stamp["end"]=dt
        self.asessGap()
        #As no conversion takes place, return the original output dict if OK:
        return dtIn 

    def publish(self,file,*args):
        #Writes the time gap report to a file given in __init()__
        if file:
            file.write("\tTime Gaps:")
            file.write(self.publishFlags())

            try:
                file.write("\n\t\tFile Start:\t%s" 
                                            %str(dt.datetime.fromtimestamp(self.stamp["start"])))
            except: file.write("\n\t\tFile Start:\tUndefined")

            try:
                file.write("\n\t\tFile End:\t%s" %str(dt.datetime.fromtimestamp(self.stamp["end"])))
            except: file.write("\n\t\tFile End:\tUndefined")

            try:
                file.write("\n\t\tGap Length:\t%s" %str(dt.timedelta(seconds=self.totalGapDur)))
            except: file.write("\n\t\tGap Length:\tNone")

            file.write("\n\t\tGaps:")
            #If list is empty, write "None" instead of gap report:
            if self.gapList==list(): file.write("\t\tNone")
            else:
                for gap in self.gapList: #Otherwise publish gaps one by one
                    file.write(tGapTracker.publishGap(gap))

    def publishFlags(self):
        self.checkFlags()
        outStr="\n\t\tFlags:\t\t"
        if len(self.flags)==0: outStr+="None"
        else: outStr+=", ".join(self.flags)
        return outStr

    def checkFlags(self):
        bStampCrit=self.const["badStamps"] #Number of bad date stamps at which BADSTAMPS flag is thrown
        gaps1crit=3600 #1 hour in seconds
        gaps6crit=3600*6 #6 hours in seconds
        if self.stamp["start"]==None or self.stamp["end"]==None:
            self.flags.append("BADSTAMPS")
        else:
            if self.stamp["end"]-self.stamp["start"]<self.const["eodCrit"]: 
                self.flags.append("EOD")
            if self.smallFileSize():
                self.flags.append("FSIZE")
        if self.badStamps>=bStampCrit: #If large number of date stamps
            self.flags.append("BADSTAMPS")
        if self.totalGapDur>=gaps6crit:
            self.flags.append("GAPS6")
        elif self.totalGapDur>=gaps1crit:
            self.flags.append("GAPS1")

    def smallFileSize(self):
        typicalSize=self.const["typicalSize"] #Expected size of full day in bytes
        typicalDur=self.const["typicalDur"] #Typical duration of a day
        fileDur=(self.stamp["end"]-self.stamp["start"])-self.totalGapDur #Duration of file
        durFrac=fileDur/typicalDur #Fraction of day that the RAMP was reporting
        modSize=typicalSize*durFrac  #Expected file size factoring in the duration and time gaps
        errMargin=modSize*self.const["errMargin"]
        return self.fSize<(typicalSize-errMargin) #If file is smaller than expected within a margin

    @staticmethod
    def publishGap(gap):
        start=dt.datetime.fromtimestamp(gap["start"])
        end=dt.datetime.fromtimestamp(gap["end"])
        dur=dt.timedelta(seconds=gap["duration"])
        gapLine='\n\t\t'+str(start)+' to '+str(end)
        gapLine+='  -->  '+str(dur)
        return gapLine

class eChemTracker(valTracker):
    def __init__(self,runInfo,name,crit,const,echem):
        super().__init__(runInfo,name,crit,const)
        self.encodeDict=reverseDict(echem)
        self.decodeDict=echem
        self.echem=self.encodeDict.keys()
        self.setupddt()

    def push(self,val,time,dt):
        corrVal=self.decode(val)
        pushReturn=super().push(corrVal,time,dt)
        if type(pushReturn)==dict: return eChemTracker.encode(pushReturn,self.encodeDict)
        else: return pushReturn


    def decode(self,val):
        #Converst S1NET:60, S2NET: 30, etc. to e.g. CONET:60, SO2NET: 30, etc.
        newDict=dict()
        for key in val:
            corrKey=self.decodeDict[key] #Reads map of e.g. S1NET:CONET, S2AUX:SO2AUX,etc.
            newDict[corrKey]=val[key] #Applies the map
        return newDict

    @staticmethod
    def encode(D,enc):
        nD=dict()
        for key in enc:
            nD[enc[key]]=D[key]
        return nD

    def setupddt(self):
        self.ddtOn=True
        for gas in self.echem:
            if gas in self.crit:
                self.ddt[gas]=ddtTracker(critT=self.crit[gas]["spikeT"])

class co2Tracker(valTracker):
    def __init__(self,runInfo,name,crit,const):
        super().__init__(runInfo,name,crit,const)
        super().setupddt()

class metTracker(valTracker):
    def __init__(self,runInfo,name,crit,const):
        super().__init__(runInfo,name,crit,const)
        self.setupddt()
        self.flagName="METFLAG"
        self.normFlag=0

    def setupddt(self):
        self.ddtOn=True
        self.ddt["MET"]=ddtTracker(critT=self.crit["MET"]["spikeT"])

    def push(self,val,time,dt):
        if val:
            super().push(val,time,dt)
            super().checkFlag(time,self.flagName,self.normFlag)
            return self.vals["output"]
        return None

class tsiTracker(valTracker):
    def __init__(self,runInfo,name,crit,const):
        super().__init__(runInfo,name,crit,const)
        self.setupddt()
        self.flagName="CPCFLAG"
        self.normFlag="C08"
        self.doNotAutoRemove={
                            "CPC",
                            "CPCFLOW",
                            "CPC_T",
                            "CPCPULSE"
                            }

    def setupddt(self):
        self.ddtOn=True
        self.ddt["CPC"]=ddtTracker(critT=self.crit["CPC"]["spikeT"])

    def push(self,val,time,dt):
        if val:
            super().push(val,time,dt)
            super().checkFlag(time,self.flagName,self.normFlag)
            return self.vals["output"]
        return None

class adiTracker(valTracker):
    def __init__(self,runInfo,name,crit,const):
        super().__init__(runInfo,name,crit,const)

class ppaTracker(valTracker):
    def __init__(self,runInfo,name,crit,const):
        super().__init__(runInfo,name,crit,const)
        self.setupDisagErr()
        self.setupddt()
        self.badLines=0
        self.bLCrit=const["badLineCrit"]

    def setupDisagErr(self):
        self.disagCounter=dict() #Keeps track of multiple consecutive disagreements
        self.noDisagCounter=dict() #keeps track of multiple consecutive agreements
        self.disagStamps=dict()
        self.lines2pushDisag=self.const["lines2pushDisag"]
        self.lines2stopDisag=self.const["lines2stopDisag"]
        self.PMtags={"PM010","PM025","PM100"}
        for tag in self.PMtags:
            self.eFlags[tag]={"DISAG" : list()} #Set up error flag dictionary
            self.disagCounter[tag]=0 #Start the disagreement counter for each PM reading
            self.noDisagCounter[tag]=0 #Start the end disagreement counter for each PM reading
            self.disagStamps[tag]=list() #Time stamps of disagreement errors

    def setupddt(self):
        self.ddtOn=True
        self.ddt=dict()
        for tag in self.PMtags: #ddt trackers for PM010A, PM010B, etc.
            for channel in ["A","B"]:
                param=tag+channel
                self.ddt[param]=ddtTracker(critT=self.const["ddtTrackLen"],
                                            critLen=self.const["ddtNumPts"])
        for param in self.crit: #T, RH, etc.
            if param not in (self.PMtags):
                self.ddt[param]=ddtTracker(critT=self.crit[param]["spikeT"],
                                        critLen=self.const["ddtNumPts"])

    def push(self,val,time,dt):
        pushOut=super().push(val,time,dt)
        return self.checkDisag(pushOut,time)

    def checkDisag(self,out,time):
        disagCrit=self.const["disagCrit"] #Agreement criterion between sensors
        minDisag=self.const["minDisag"] #Cutoff for disagreement
        for tag in self.PMtags:
            (Atag,Btag)=(tag+"A",tag+"B")
            (A,B)=(out[Atag],out[Btag]) #Channel readings
            #(medA,medB)=(self.ddt[Atag].mVal,self.ddt[Btag].mVal) #Running medians for channels
            if (A!=None and B!=None): #If readings are defined
                err=max((disagCrit*max(A,B)),minDisag) 
                #Choose rither % criterion if readings are large, or absolute if readings are small
                if abs(A-B)>err: #If difference between channels exceeds error criterion
                    self.noDisagCounter[tag]=0 
                    self.disagCounter[tag]+=1
                    if self.disagCounter[tag]>self.lines2pushDisag: 
                        self.eFlags[tag]["DISAG"].append(time)
                    else: self.disagStamps[tag].append(time)
                    (out[Atag],out[Btag])=(None,None)
                else: self.noDisagCounter[tag]+=1
                self.assessDisag(tag)
        return out

    def assessDisag(self,tag):
        if self.disagCounter[tag]>=self.lines2pushDisag and self.disagStamps[tag]!=list(): 
            #If enough disagreements detected and the stamp list is not empty
            self.eFlags[tag]["DISAG"]+=self.disagStamps[tag]
            self.disagStamps[tag]=list() #clear to free up RAM
        elif self.noDisagCounter[tag]>=self.lines2stopDisag:
            #If operating error-free for sufficient amount of time
            self.disagCounter[tag]=0
            self.disagStamps[tag]=list()

class battTracker(valTracker):
    def __init__(self,runInfo,name,crit,const):
        super().__init__(runInfo,name,crit,const)
        self.flagNames={"STAT"}
        self.setupddt()
        #(avg. derivative criterion for DRAIN FLAG, min. volt. crit. for DRAIN FLAG, 
        # min. volt for LOW FLAG)
        self.drainFlag="DRAIN"

    def push(self,val,time,dt):
        if val:
            super().push(val,time,dt)
            self.checkFlag(time)
            self.checkPowerLoss(time)
            return self.vals["output"]
        return None

    def checkFlag(self,time):
        #Special function to verify battery error flags 
        okFlags={"A/C","OK","BATTPWR"} #Flags which do not require an error to be dispayed
        if "STAT" not in self.eFlags: self.eFlags["STAT"]=dict() #Declare stat error dict if absent
        flag=self.vals["current"]["STAT"]
        if flag!=None and flag not in okFlags:
            if flag in self.eFlags["STAT"]: self.eFlags["STAT"][flag].append(time)
            else: self.eFlags["STAT"][flag]=[time]

    def checkPowerLoss(self,time):
        #Checks for power loss by monitoring battery voltage and its average change
        #To avoid missing power losses after long charge cycles, average change resets every so often
        if "BATT" in self.ddt:
            battDdt=self.ddt["BATT"] #Object that tracks the mean value and derivative
            if not battDdt.enoughData(): return #Skips the check if there is not enough data

            (mVolt,mdVdt)=(battDdt.aVal,battDdt.dVal) #Avg voltage and change in voltage over 20 lines
            (dvdtDrain,vDrain)=(self.const["draindVdt"],self.const["drainMinV"])
            #renames variables for less typing

            if mVolt<=self.const["lowCrit"]: #If battery is low
                if "LOW" not in self.eFlags["STAT"]: self.eFlags["STAT"]["LOW"]=list()
                self.eFlags["STAT"]["LOW"].append(time)
            elif mVolt<=vDrain and mdVdt<=dvdtDrain: #If battery is draining
                if self.drainFlag not in self.eFlags["STAT"]: 
                    self.eFlags["STAT"][self.drainFlag]=list()
                self.eFlags["STAT"][self.drainFlag].append(time)         

    def setupddt(self):
        self.ddtOn=True
        self.ddt={"BATT":ddtTracker(critT=self.const["ddtTrackLen"],
                                    critLen=self.const["ddtNumPts"])}

    @staticmethod
    def makeBattSubDict():
        #Constructs the battery error dictionary based on the facts that:
        #reading is in the form XYZ where
        #X: Temp Status – 0 if temp below -20°C, which disables charging
        #Y: Charge Status – 1 when battery voltage below 3.6V
        #Z: Fault Status – 1 when battery good; 0 if battery disconnected or fault
        outDict=dict()
        numVals=2
        for ones in range(numVals):
            for tens in range(numVals):
                for hundreds in range(numVals):
                    code=100*hundreds+10*tens+ones
                    if ones==0: outDict[code]="FAULT"
                    elif hundreds==0: outDict[code]="COLD"
                    elif tens==1: outDict[code]=None   
        return outDict

class statTracker(valTracker):
    def __init__(self,runInfo,name,crit,const):
        super().__init__(runInfo,name,crit,const)
        self.initializeFlags()

    def push(self,val,time,dt):
        if val!=None:
            if val=="XCON": 
                self.addFlagEntry("AUXstat","XCON",time)
                return None
            self.vals["current"]=val
            self.checkConn(time,dt)
            self.checkFlag(time,"recharge",0,{1 : "SIM DEPLETED"})
            self.checkSD(time)
            self.checkSignal(time)
        return None

    def checkSD(self,time):
        sdFlag=self.vals["current"]["SDstat"]
        if sdFlag==None: return
        elif len(sdFlag)==2: #i.e. flag is from old firmware
            if sdFlag[0]=="1": self.eFlags["SDstat"]["NO SD"].append(time)
            elif sdFlag[1]=="1": self.eFlags["SDstat"]["SD ERROR"].append(time)
        elif len(sdFlag)==3: #i.e. if new firmware
            if sdFlag[0]=="0":  self.eFlags["SDstat"]["NO SD"].append(time)
            elif sdFlag[1]=="0":self.eFlags["SDstat"]["SD INIT ERROR"].append(time)
            elif sdFlag[2]=="1":self.eFlags["SDstat"]["SD ERROR"].append(time)

    def checkSignal(self,time):
        if type(self.vals["current"]["signal"])==int and  self.vals["current"]["signal"]<10: 
                self.eFlags["signal"]["LOW"].append(time) 

    def initializeFlags(self):
        self.eFlags["SDstat"]={"NO SD": list(), "SD ERROR": list(), "SD INIT ERROR": list()}
        self.eFlags["signal"]={"LOW": list()}

class ddtTracker(object):
    #Keeps a small list of values, derivatives, and times on hand for average derivatives,
    #noise detection,etc.
    def __init__(self,sInterval=None,critLen=None,critT=None):
        self.val=list()
        self.advdt=list() #stores the absolute value of the derivative
        self.dt=list()
        self.tList=list() #Stores the time stamps considered
        self.sumVal=0       #Sum of all values held by tracker
        self.sortVals=list()#Stores a sorted list of represented values (for calculating median)
        self.aVal=None      #Average of values
        #self.mVal=None      #Median of values
        self.mdVdt=None     #Mean of derivatives
        self.sum_adVdt=0     #Sum of abs(derivatives)
        self.totalTime=0 #Total time in the subset
        self.sInterval=sInterval #Sampling interval (if modified)
        self.lastSample=None
        self.cLen=0
        self.critLen=critLen     #Number of data points held in RAM
        if critLen==None: 
            self.optCritLen=5
            self.critLen=self.optCritLen
        else: self.optCritLen=critLen      #Desired number of points (tradeoff between sample size and performance)
        if critT!=None: self.getSival(critT)

    def getSival(self,critT):
        #Determines whether downsampling is necessary given a desired critical time
        #And the desired maximum size of the sample
        postLen=15 #Time between two lines is assumed to be 15 seconds long on average
        if critT<=(postLen*self.optCritLen):
            self.sInterval=None
            self.critLen=round(critT/postLen)
        else:
            seconds=critT/self.optCritLen
            self.sInterval=seconds

    def push(self,time,val,dvdt,dt):
        if val!=None and dvdt!=None and dt!=None and dt>0:
            dt=self.sampleTime(dt)
            if dt==None: return #i.e. if tracker needs to wait before sampling again
            else: self.cLen+=1 #Increment counter of points
            
            #If the number of points represented increases past some limit, start removing points
            if self.cLen>self.critLen: self.removePoints(dt)
            
            self.val.append(val)
            self.sumVal+=val #Update the running sum
            self.aVal=self.sumVal/self.cLen #Calculate mean val from sum of vals and current length

            self.advdt.append(abs(dvdt))
            self.sum_adVdt+=abs(dvdt) #Update the running sum of abs. derivatives
            self.avg_adVdt=self.sum_adVdt/self.cLen #

            self.dt.append(dt)
            self.totalTime+=dt

            self.tList.append(time)

            self.dVal=(self.val[-1]-self.val[0])/self.totalTime #Average derivative

    def removePoints(self,dt):
        #Removes old entries before updating the list
        tSum=0
        while (tSum<dt and self.cLen>0):
            #remove the first element of the list until either the list ends or the sum or
            #an equivalent amount of time is removed from the ddt tracker

            self.totalTime-=self.dt[0] #Update totalTime before removing point
            self.dt.pop(0)
            
            #Do the same thing for other parameters:
            self.sumVal-=self.val[0]
            self.val.pop(0)

            self.sum_adVdt-=self.advdt[0]
            self.advdt.pop(0)
            
            self.tList.pop(0)

            self.cLen-=1 #Decrement counter of current tracker length
            tSum+=dt

    def sampleTime(self,dt):
        #Determines if downsampling is enabled,
        #Returns None if it isn't sampling time
        #Otherwise returns the time since the last sample
        if self.sInterval==None: return dt
        elif self.lastSample==None: 
            self.lastSample=dt
            return None

        self.lastSample+=dt
        if self.lastSample>=self.sInterval: 
            lastSample=self.lastSample
            self.lastSample=0
            return lastSample
        else: return None

    def enoughData(self): 
        return (self.cLen>=self.critLen)

class flat(object):
    #keeps track of a flatline 
    def __init__(self,medianValue,start,end,duration,critT,critS):
        postLen=dt.timedelta(minutes=7.5)
        postLen=postLen.total_seconds()
        self.medianValue=medianValue
        self.start=start
        self.end=end
        self.duration=duration
        self.maxOffDur=duration/4 #Amount of time the sensor is off before a new flatline is started
        self.stamps=0 #Number of time stamps in flatline
        self.sNumCrit=round(duration/postLen) #Number of time stamps necessary to declare a flatline
        self.critT=critT
        self.critS=critS
        self.minVal=medianValue-critS
        self.maxVal=medianValue+critS

    def __str__(self):
        startStr=str(dt.datetime.fromtimestamp(self.start)),
        endStr=str(dt.datetime.fromtimestamp(seconds=self.end))
        durStr=str(dt.timedelta(seconds=self.duration))
        critStr=str(dt.timedelta(seconds=self.critT))
        outStr=""
        outStr+="Median: %s, Magnitude: %s" %(self.medianValue, self.critS) 
        outStr+="\nStart: %s, End: %s, Duration: %s, Min.Dur.: %s" %(startStr,endStr,
                                                                    durStr,critStr)
        return outStr

    def update(self,stamp,dt):
        self.end=stamp
        self.duration+=dt
        self.stamps+=1

    def largeEnough(self):
        return (self.duration>self.critT and self.stamps>self.sNumCrit)

    def continues(self,value,dt):
        return (value>=self.minVal and value<=self.maxVal and dt>=self.maxOffDur)

class dataYield(object):
    #Object that keeps track of how many points were pushed during a given period of time
    #Returns None when updating unless a NO DATA flag needs to be thrown
    def __init__(self,startTime,const):
        self.start=startTime
        fracIso=0.25 #fraction of isolation time has to be <0.5 to not be caught in tIso filter
        self.sampleTime=fracIso*const["tIso"] #Ensure that the flag is not isolated when report is compled
        self.resetTime=const["minErrLen"] #If more time than this has elapsed, just reset
        self.timeLeft=self.sampleTime #Countown to deciding whether to push a flag
        #How many missed lines to throw a no data flag:
        self.expNumLines=self.sampleTime/const["logLen"]
        self.ndCrit=self.expNumLines*const["NDcrit"] 
        #How many missed lines to throw an intermittent data flag:
        self.idCrit=self.expNumLines*const["IDcrit"]
        self.dataPoints=0
        self.totalPoints=0

    def __str__(self):
        sOut=("Start:\t%s\n"
            "Points: \t%s\n"
            "tLeft: \t%s\n"     %(dt.datetime.fromtimestamp(self.start),
                                  self.dataPoints,
                                  dt.duration(seconds=self.timeLeft)))
        return sOut

    def update(self,dt,time,data=True):
        #Updates the timer, and counters of valid data points and calls to the tracker
        #Returns None until flag criteria are met
        if dt==None: return None #Skip if dt not yet defined
        if dt>self.resetTime: #If last stamp seen was a while ago, start anew
            self.reset(time)
            return None
        if data==True: #Increase counters, decrease timer
            self.dataPoints+=1
        self.totalPoints+=1
        self.timeLeft-=dt
        if self.timeLeft<=0: 
            #When sample time elapses, check if a flag needs to be returned
            return self.returnFlag(time)
        else: return None

    def returnFlag(self,time):
        #Check if there is cause for concern:
        flag=None
        if self.totalPoints<self.idCrit: flag="LOW LOG FREQ" #Fewer than expected calls
        elif self.dataPoints<self.ndCrit: flag="NO DATA" #Little data pushed
        elif self.dataPoints<self.idCrit: flag="INTERMITTENT DATA" #Data pushed only occasionally
        start=self.start
        self.reset(time)
        if flag!=None: return(flag,start)
        else: return None

    def reset(self,time):
        #Annulates counters and timer
        self.start=time
        self.timeLeft=self.sampleTime
        self.dataPoints=0
        self.totalPoints=0
