#   Copyright (c) 2003-2008 Open Source Applications Foundation
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import tools.cats.framework.ChandlerTestLib as QAUITestAppLib
from tools.cats.framework.ChandlerTestCase import ChandlerTestCase

class TestSwitchingViews(ChandlerTestCase):

    def startTest(self):
    
        # make user collection, since only user
        # collections can be displayed as a calendar
        col = QAUITestAppLib.UITestItem("Collection", self.logger)
        QAUITestAppLib.UITestView(self.logger).SwitchToCalView()

        # creation
        testView = QAUITestAppLib.UITestView(self.logger)
        
        # action
        # switch to all view
        testView.SwitchToAllView()
        # switch to tasks view
        testView.SwitchToTaskView()
        # switch to calendar view
        testView.SwitchToCalView()

