##___CHANGELOG___##
    #2018-10-23:
        #Created (pulled out of RDCauto0.1.2 WIP)
        #Fixed compatibility issue with new echem reader
    #2019-01-09
        #Fixed bug where deleted files were being called during best raw file search
    #2019-01-10
        #Fixed bug where valid Concatenated files were removed, but not replaced

#Contains objects responsible for handling file properties and methods
#as well as parent classes of file objects and helpers

import os
import datetime
import string
import sys
import copy
import shutil
import pdb
from genericHelpers import *
from rawFileReader import read

class rampFile(object):
    def __init__(self,ramp,path):
        self.ramp=ramp
        self.path=path
        self.dir=os.path.dirname(path)
        self.name=os.path.split(path)[-1]
        if os.path.exists(path): self.size=self.getSize()
        else: self.size=0
        self.io=None

    def __repr__(self):
        return self.path

    def open(self, mode='r'):
        if not mode.startswith('r'):
            #Create directory if one does not exist and file is in writing mode
            if not os.path.exists(self.dir): os.makedirs(self.dir)
        self.io=open(self.path,mode)

    def close(self):
        try: 
            self.io.close()
            self.io=None #Cleans up to make object serializable
        except: pass

    def updatePath(self,newPath,overwrite=True):
        #Enables relocation of the file
        if self.path==newPath: return self
        elif os.path.exists(newPath):
            if overwrite==True:
                os.remove(newPath)
            else:
                raise OSError('File at %s already exists\n',
                    'Enable overwrite or remove it')
        shutil.copy(self.path,newPath)

        #Change the path and directory of current object to match the copied object:
        if os.path.isdir(newPath): 
            newDir=newPath
            self.dir=newDir
            self.path=os.path.join(newDir,self.name) #Create full path from dir and name
        else: 
            newDir=os.path.dirname(newPath)
            self.path=newPath
            self.dir=newDir
        return self

    def seek(self,param):
        self.io.seek(param)

    def read(self):
        return self.io.read()

    def tell(self):
        return self.io.tell()

    def getSize(self):
        return os.path.getsize(self.path)

    def readline(self):
        return self.io.readline()

    def exists(self):
        return os.path.exists(self.path)

    def write(self,s):
        self.io.write(s)

class dataFile(rampFile):
    def __init__(self,ramp,date,path):
        self.date=date
        if path!=None:
            self.path=path
            self.dir=os.path.dirname(self.path)
        elif "dir" in kwargs:
            self.dir=kwargs["dir"]
            self.path=os.path.join()
        else:
            raise KeyError("A path or a dir must be specified for a data file")
        super().__init__(ramp,self.path)

class rawFile(dataFile):
    def __init__(self,ramp,date,path,SD=False,concat=False):
        super().__init__(ramp,date,path)
        self.SD=SD
        self.concat=concat
        self.dateStr=rawFile.get.dateFormatCorrection(date,SD)
        self.fName=self.dateStr+rawFile.ext(SD=SD)
        (self.start,self.end)=(None,None)

    def __repr__(self):
        if self.SD: typeStr="SD"
        else:       typeStr="Server"
        if self.concat: cStr="Concatenated "
        else:           cStr=""
        return "%s%s file at %s" %(cStr,typeStr,self.path)

    def open(self,mode='r',updateEndPoints=False,forceUpdate=False):
        if updateEndPoints==True:
            if forceUpdate==True: self.updateEndPoints()
            elif (self.start==None or self.end==None): self.updateEndPoints()
        if mode=='r':
            self.io=open(self.path,encoding='ascii',errors='surrogateescape')
        else: super().open(mode)

    def open4Writing(self):
        #Create directory if one does not exist:
        if not os.path.exists(self.path): os.makedirs(self.dir)
        self.io=open(self.path,'w')

    def close(self,updateEndPoints=False,forceUpdate=False):
        #Closes the io stream
        #Optionally updates the start and end stamps of the file
        if updateEndPoints==True:
            if forceUpdate==True: self.updateEndPoints()
            elif (self.start==None or self.end==None): self.updateEndPoints()
        super().close()

    def updateEndPoints(self):
        self.size=self.getSize() #Updates size every time a file is closed
        try: (self.start,self.end)=rawFile.get.startEndStamps(self,openFile=True)
        except: pass

    @staticmethod
    def ext(SD=False):
        #Returns the appropriat file extension
        if SD: return ".TXT"
        else: return "-raw.txt"

    class get(object):
        @staticmethod
        def fNameFromDate(date,SD=False):
            dateStr=dateFormatCorrection(date,SD)
            return "%s%s" %(dateStr,ext(SD))

        @staticmethod
        def serverFile(ramp,date,folder):
            #Checks if the server file is in the given directory
            #Returns a rawFile object if so, None otherwise
            dateStr=rawFile.get.dateFormatCorrection(date,SD=False)
            path=os.path.join(folder,dateStr+rawFile.ext(SD=False))
            if os.path.exists(path): return rawFile(ramp,date,path=path)
            else: return None

        @staticmethod
        def sdFile(ramp,date,folder):
            #Checks if a file with that date is in a given SD directory
            #Returns a rawFile object if so, None otherwise
            file=None
            dateStr=rawFile.get.dateFormatCorrection(date,SD=True)
            path1=os.path.join(folder,'DATA',dateStr+rawFile.ext(SD=True)) #In case of .../ramp no./DATA/file
            path2=os.path.join(folder,'USB',dateStr+rawFile.ext(SD=True)) #In case of .../ramp no./USB/file
            path3=os.path.join(folder,dateStr+rawFile.ext(SD=True)) #In case of .../ramp no./file
            possiblePaths={path1,path2,path3}
            validPaths=rawFile.get.validPathSet(possiblePaths)
            if len(validPaths)==0: return None
            elif len(validPaths)==1:
                (validPath,)=validPaths #Unpack valid path into a tuple
                return rawFile(ramp,date,path=validPath,SD=True)
            else: #Concatenate into outer SD folder if needed
                return rawFile.get.bestFile(validPaths,folder)

        @staticmethod
        def validPathSet(pathList):
            #takes a list of paths, return a set of valid ones
            validSet=set()
            for path in pathList:
                if os.path.exists(path):
                    validSet.add(path)
            return validSet

        @staticmethod
        def dateFormatCorrection(date,SD=False):
            date=str(date)
            if SD:
                dtLen=6
                date=date.split('-')
                date[0]=date[0][2:] #removes the first two digits in the year
                date=''.join(date)
                date=date[:dtLen] #truncates in case datetime is given
            else:
                date=date.split('-')
                date[-1]=str(int(date[-1])) #Removes the zero in front of day (server format)
                date='-'.join(date)
            return date 

        @staticmethod
        def concatenatedPartialFiles(f1,f2,svPath,forceRelocate=False):
            #Concatenates f1 and f2 into a file on save path (svPath) based on timestamps
            fOut=None #Variable that stores the final concatenated file
            f3SD=f1.SD and f2.SD #Format as SD file only if both f1 and f2 are SD files
            f3=rawFile(f1.ramp,f1.date,svPath,SD=f3SD,concat=True) #The concatenated file
            f1.open(updateEndPoints=True,forceUpdate=False) #Open files in case concatenation is required
            f2.open(updateEndPoints=True,forceUpdate=False)
            if f1.start and f1.end and f2.start and f2.end: #If all start and end stamps are defined
                if f1.start>=f2.end: #i.e. file 1 starts after filed 2 ends
                    f3.open('w')
                    #Default .open method for raw files is read-only 
                    rawFile.write2f3(f2,f1,f3) #Write f2, then f1 to f3
                    fOut=f3 #Set concatenated file as output
                elif f2.start>=f1.end: #i.e. file 1 ends before file 2 starts
                    f3.open('w')
                    rawFile.write2f3(f1,f2,f3) #Write f1, then f2 to f3
                    fOut=f3
                elif f2.start<=f1.start and f2.end>=f1.end: fOut=f2
                #i.e. if f2 starts earlier and ends later than f1, just use f2
                elif f2.start>=f1.start and f2.end<f1.end: fOut=f1 
                #same, but for f1

                #Check file sizes, go for the larger one
                elif f1.size>=f2.size: fOut=f1
                elif f2.size>=f1.size: fOut=f2
                elif f1.SD==True: fOut=f1
                else: fOut=f2
            elif f2.start and f2.end: fOut=f2 #IF start and end stamps are defined only for f2, use f2
            elif f1.start and f1.end: fOut=f1   
            else: 
                f1.close()#Close all files that may have been open
                f2.close()
                return None #If no valid date stamps found, skip rest

            f1.close()#Close all files that may have been open
            f2.close()
            if fOut==f3:
                f3.close(updateEndPoints=True,forceUpdate=False)
                fOut.close(updateEndPoints=True,forceUpdate=False)
            else: fOut.close()

            #Relocate output file if necessary:
            if forceRelocate:fOut.updatePath(svPath)
            return fOut

        @staticmethod
        def startEndStamps(f,openFile=False):
            #Gets the first and last time stamps of a raw file. optionally uses io.
            (startStamp,endStamp)=(None,None)
            if openFile: f.open() #If told, open the file
            line=f.readline()
            while line!="": #Go through the file line by line
                dt=rawFile.get.lineDateTime(line,f.date) #Parse out date stamp from the line
                if dt:
                    if startStamp==None: startStamp=dt
                    endStamp=dt
                line=f.readline()
            f.seek(0) #Returns file parser to beginning in case file is open after return
            if openFile: f.close() #If told to open the file, close it
            return (startStamp,endStamp)

        @staticmethod
        def lineDateTime(line,date=None):
            line=line.split("X")
            for elem in line:
                if elem.startswith("DATE"):
                    tStampDict=read.timeStamp(elem,date)
                    if tStampDict!=None:
                        return tStampDict["DATETIME"]
                    else: return None
            return None

        @staticmethod
        def bestFile(fSet,concatDir):
            bestFile=None
            if None in fSet: fSet.remove(None)
            if len(fSet)==0: return None
            elif len(fSet)==1: 
                (bestFile,)=fSet #unpacks the only element in the set
                return bestFile
            else:
                if len(fSet)==2: #Base case of two files being written to a third
                    (f1,f2)=fSet
                    svPath=rawFile.get.concatFilePath(f1,f2,concatDir)
                    bestFile=rawFile.get.concatenatedPartialFiles(f1,f2,svPath)
                else:
                    tempDir="temp" #Directory that temporaily stores concatenated files
                    tempDir=os.path.join(concatDir,tempDir)
                    tempDirPresent= os.path.exists(tempDir) #Figure out if tempDir was there before
                    if not tempDirPresent: os.makedirs(tempDir) #creates tempDir if wasn't there before
                    bestFile=rawFile.get.bestFileRecursively(fSet,concatDir,tempDir)
                    if not tempDirPresent: 
                        shutil.rmtree(tempDir) #removes tempDir if wasn't there before
            return bestFile

        @staticmethod
        def bestFileRecursively(fSet,concatDir,tempDir,depth=0):
            if len(fSet)==0: return None
            if len(fSet)==1: #Base case for one file given
                (bestFile,)=fSet #unpacks the only element in the set
                if depth==0 and bestFile.dir==tempDir: #Move top-level candidates out of temp dir
                    bestFile.updatePath(concatDir)
                return bestFile
            else:              
                if depth==0: #Ensure that top-level merges get placed in the Concatenation dir
                    svDir=concatDir
                    forceRelocate=True
                else: #Place all other merges in the 'temp' directory
                    svDir=tempDir
                    forceRelocate=False
                if len(fSet)==2: #Base case of two files being written to a third
                    (f1,f2)=fSet
                    #Decides what file format to use when saving concatenated file:
                    svPath=rawFile.get.concatFilePath(f1,f2,svDir)
                else:
                    fList=list(fSet) #Creates a list that can be split and fed back in recursively
                    listMidPt=len(fList)//2
                    #Split the list into two parts:
                    (subList1,subList2)=(fList[:listMidPt],fList[listMidPt:])
                    #Recursive calls on subLists:
                    f1=rawFile.get.bestFileRecursively(subList1,concatDir,tempDir,depth+1)
                    f2=rawFile.get.bestFileRecursively(subList2,concatDir,tempDir,depth+1)
                    svPath=rawFile.get.concatFilePath(f1,f2,svDir)
                return rawFile.get.concatenatedPartialFiles(f1,f2,svPath,forceRelocate)

        @staticmethod
        def concatFilePath(f1,f2,svDir):
            #Determines full path to a hypothetical concatenated file
            #Using parameters of f1, f2, and a save directory
            if f1!=None and f2!=None:
                if not f1.SD: dateStr=f1.dateStr
                else: dateStr=f2.dateStr
                f3SD=f1.SD and f2.SD #Only format bestFile as SD if both f1 and f2 are SD files
            elif f1!=None:
                f3SD=f1.SD
                dateStr=f1.dateStr
            elif f2!=None:
                f3SD=f2.SD
                dateStr=f2.dateStr
            f3Name=dateStr+rawFile.ext(SD=f3SD)
            svPath=os.path.join(svDir,f3Name)
            return svPath

    @staticmethod
    def write2f3(f1,f2,f3):
        #Writes the contents of two files into 1
        #Write the contents of f1, followed by contents of f2 to f3
        line=f1.readline()
        while line!="":
            if checkASCII(line): f3.write(line)
            line=f1.readline()
        line=f2.readline()
        while line!="":
            if checkASCII(line): f3.write(line)
            line=f2.readline()
        #Set endpoints to the same value as for f1 and f2:
        f3.start=f1.start
        f3.end=f2.end

class calFile(dataFile):
    def __init__(self,ramp,date,path,runInfo):
        super().__init__(ramp,date,path)
        self.echemOrdDict=calFile.convertEchem2OrdDict(ramp.echem)
        self.echem=self.getEchemDecode()
        self.output=ramp.output

        self.blankLine=None         #Defined in self.writeStartLine method
        self.paramOrder=None        #Defined in self.writeStartLine method
        self.catNameDict=runInfo.rOutputDict
        self.parsedBlankDict=dict() #Populated in self.compileParsedRefDicts
        self.compileParsedRefDicts()


    def compileParsedRefDicts(self):
        #Creates a Dictionary mapping parameter name to category
        #e.g. {PTR: [PM010, PM025, PM100]} --> {PM010:PTR, PM025:PTR, PM100:PTR}
        #and a blank dictionary to be used by config4writing function:
        #e.g {PTR: [PM010, PM025, PM100]} --> {PTR: {PM010: None, PM025: None, PM100: None}}

        outputDict=self.output['params'] #Get source dictionary

        for key in outputDict:
            entry=outputDict[key]
            if entry==None:
                continue
            else:
                self.parsedBlankDict[key]=dict()

            for value in outputDict[key]:
                self.parsedBlankDict[key][value]=None

    def writeStartLine(self):
        #Format: 
        #([Column Name 1,..., Column Name n], Delimiter in raw file)#
        (params,order)=(copy.copy(self.output['params']),copy.copy(self.output['order']))
        params["ECHEM"]=self.orderECHEM(params["ECHEM"])
        (params,order)=calFile.orderParams(params,order)

        self.blankLine=calFile.genBlankLine(params)
        self.order=order
        self.paramOrder=flatten(params)

        vals=flatten(params) #Flatten list to 1d
        apStr=('_%s') %str(self.ramp) # Add _RAMP No. to every header
        for i in range(len(vals)):
            vals[i]+=apStr
        outStr=','.join(vals) #Separate headers with commas
        outStr+='\n'
        self.write(outStr)

    def pDict2valLine(self,pDict):
        if pDict==None: return None #If whole line couldn't be read (e.g. bad date stamp)
        #pdb.set_trace()
        nLine=copy.copy(self.blankLine) #Create a new list of values to output
        for key in self.order: #Go thru categories in output order
            if (key in pDict) & (key in self.output['params']): #If the category is in the parsed dict & output  dict
                iCat=self.order[key] #Index in nLine
                oCat=self.output['params'][key] #Order of parameters in category
                subLine=copy.copy(oCat)
                for i in range(len(subLine)): #Go parameter by parameter
                    param=subLine[i]    #Parameter name
                    if param in pDict[key]: #If parameter in parsed Dict
                        item=pDict[key][param] #Pull the reading in question
                        if checkASCII(str(item)):subLine[i]=item #Add to subline
                    else: subLine[i]=None #Otherwise, replace param name w. None
                nLine[iCat]=copy.copy(subLine) #Copy parameter order into correct slot in nLine
        return flatten(nLine)


    def orderECHEM(self,order):
        newOrder=copy.copy(order)
        for i in range(len(order)):
            param=order[i] #parameter (e.g. S1AUX, S1ACT, etc)
            gasDecode=self.echem[param]
            newOrder[i]=gasDecode
        return newOrder

    def getEchemDecode(self):
        #Converts an order dictionary e.g.{CO:1, SO2:2} into a decode dictionary:
        #e.g. {S1AUX:COAUX, S2NET:SO2NET}, pulling parameters from a read method
        #and the order from a list processed by calFile.convertEchem2OrdDict
        dlm='' #What goes between the gas name and the reading type. e.g. if dlm=='.': CO.AUX
        endStrLen=3 #Length of the string at the end describing reading type (e.g AUX, NET, ACT)
        decodeDict=dict()
        allEchem=self.ramp.output['params']['ECHEM']
        for param in allEchem:
            sensor=param[0:-endStrLen] #Get sensor name (e.g. S1, S2, S3, S4)
            suffix=param[-endStrLen:] #Get the reading suffix ('NET','ACT','AUX')
            sPlace=int(sensor[1:]) #Get the sensor order by chopping off the "S"
            gasType=self.echemOrdDict[sPlace] #Query the gas type of the sensor
            outStr=gasType+dlm+suffix #Reconstruct str (e.g. COAUX)
            decodeDict[param]=outStr #Store in dictionary: S1AUX:COAUX
        return decodeDict

    @staticmethod
    def convertEchem2OrdDict(echemLine):
        #Given a list e.g. ["CO","SO2","NO2","O3"] converts to an order dictionary
        #e.g. {1:CO,2:SO2,3:NO2,4:O3}
        echemDict=dict()
        for i in range(len(echemLine)):
            echemDict[i+1]=echemLine[i]
        return echemDict

    @staticmethod
    def ext(): #file extension (after the date)
        return "-cal.txt"

    @staticmethod
    def genBlankLine(order):
        lFormat=[]
        for element in order:
            lFormat.append(','*(len(element)-1))
        return lFormat

    @staticmethod
    def orderParams(params,order=None):
        #Converts a parameter dictionary into a list sorted by the order list
        #Converts order list to a dictionary
        ordDict=dict()
        ordParams=[]
        if order==[]: return(ordParams,ordDict)
        elif order==None:
            i=0
            for elem in params.keys():
                ordParams+=[params[elem]]
                ordDict[elem]=i
                i+=1
        else:
            i=0
            for elem in order:
                ordParams+=[params[elem]]
                ordDict[elem]=i
                i+=1
        return (ordParams,ordDict)

    @staticmethod
    def create(rawFile,runInfo):
    #Creates a calFile object with the appropriate ramp, date, and path
        ramp=rawFile.ramp
        calDir=runInfo.get("Output Directory")
        rampStr="s"+str(ramp) #All processed subdirectories start with "s"
        dirStr=os.path.join(calDir,rampStr)
        date=rawFile.date
        path=os.path.join(dirStr,str(date)+calFile.ext())
        out=calFile(ramp,date,path,runInfo)
        return out

class errorFile(dataFile):
    def __init__(self,ramp,date,path,SD):
        self.SD=SD
        super().__init__(ramp,date,path)

    def writeStartLine(self,raw):
        dateStr=str(raw.date)
        if raw.SD: dateStr+=" (SD)"
        dateStr=dateStr+':\n'
        self.write(dateStr)

    @staticmethod
    def create(rawFile,runInfo):
        #Outputs an errorFile with the same ramp and date as rawFile
        #Stores in a directory specified in runInfo
        storDir=runInfo.get("Error Reports Directory")
        ramp=rawFile.ramp
        rampStr="s"+str(ramp) #Store in folders with "s" appended to the front

        date=rawFile.date
        dateStr=str(date)+errorFile.ext()

        SD=rawFile.SD

        fullPath=os.path.join(storDir,rampStr,dateStr)
        return errorFile(ramp,date,fullPath,SD)

    @staticmethod
    def ext(): return "_checks.txt"