## FunctionalList1.py
## Author : Olivier Giroussens
## Description: This test suite runs the 4 basic testcases of generating event, mail, task and note items in chandler
 
import tools.QAUITestAppLib as QAUITestAppLib
import os, sys

functional_dir = os.path.join(os.getenv('CHANDLERHOME'),"tools/QATestScripts/Functional")

#initialization
fileName = "FunctionalTestSuite.log"
logger = QAUITestAppLib.QALogger(fileName,"FunctionalTestSuite")

def run_tests(tests):
    for filename in tests:
        execfile(os.path.join(functional_dir, filename))
        
allTests = ["TestBlocks.py",
            "TestCreateAccounts.py",
            "TestAllDayEvent.py", 
            "TestNewCollection.py",
            "TestDates.py", 
            "TestNewEvent.py",
            "TestNewMail.py",
            "TestNewTask.py",
            "TestNewNote.py",
            "TestStamping.py", 
            "TestMoveToTrash.py", 
            "TestDeleteCollection.py",
            "TestNewCollNoteStampMulti.py", 
            "TestCalView.py",
            "TestRecurrenceImporting.py", 
            "TestRecurringEvent.py",  
            "TestSwitchingViews.py",
            "TestExporting.py",
            "TestFlickr.py",
            "TestImporting.py",
            "TestImportOverwrite.py",
            "TestSharing.py",
            ]

if sys.platform == 'win32': 
    platform = 'windows'
elif sys.platform == 'darwin': 
    platform = 'mac'
else:
    platform = 'other'
    
exclusions = {
    'other':(
        "TestCalView.py", #bug 5109 emulate typing starting with unhighlighted text appends rather than overwrites                                     
    ),
    
    'mac':( 
    ),
    
    'windows':(
    ),
    
    'all':(        
        "TestAllDayEvent.py", #test not functioning bug#5110
        "TestDates.py", #Chandler not handling daylightsavings bug#5038
        "TestRecurrenceImporting.py", #Chandler bug #5116
        "TestNewEvent.py", # bug 5086
        "TestNewCollNoteStampMulti.py", # bug 5233
    )
}

tests_to_run = filter(lambda test : test not in exclusions['all'] and test not in exclusions[platform], allTests)

try:
    run_tests(tests_to_run)
finally:    
    #cleaning
    logger.Close()
