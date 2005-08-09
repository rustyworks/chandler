import wx
import osaf.framework.scripting.QATestAppLib as QATestAppLib

logger = QATestAppLib.Logger()

logger.Start("Creating Calendar View Event")
createdCollection = NewItemCollection()[0]
logger.Stop()
createdCollection.displayName = 'Test Collection'
testCollection = FindByName(pim.ItemCollection, "Test Collection")

logger.SetChecked(True)
if testCollection.displayName == 'Test Collection':
 logger.ReportPass("Checking Item Collection creation")
else:
 logger.ReportFailure("Checking Item Collection creation: Item Collection not created")
logger.Report()
logger.Close()
