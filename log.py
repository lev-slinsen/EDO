
from time import time
from json import dumps

log_output_path = "" #If set to nothing it will be the current directory.

directPath = None #will be determined by initLog

async def initLog() :
    curTime = int(time())
    currentLogName = "Log" + str(curTime) + ".log" #everytime startup new log file.
    global directPath #so it can be modified outside of it's scope.
    if (log_output_path == "" or log_output_path==None) :
        directPath = currentLogName #if u open a file (or read a file) with a path it will assume it is in the current directy
    else :
        directPath = log_output_path + currentLogName

    openFile = open(directPath,"w+") #create the file
    openFile.write(str(dumps({'time':curTime, 'event':'starting_log', 'details':'' })) + "\n") #write initial message
    openFile.close() #save it
    
async def logEvent(eventType, details) : #be careful with this and strange characters, if you ever wanna read this log with code strange characters r gonna mess everything up. underscores r ok
    if(directPath==None) : #if the log hasn't been initialized
        initLog() #initalize it
    
    openFile = open(directPath, 'a') #open it with append mode
    openFile.write(str(dumps({'time':int(time()), 'event':str(eventType), 'details':str(details)})) + "\n")
    openFile.close() #save it
