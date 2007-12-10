import wx, osaf, application
def run():
    """
        Choose menu 'Collection > New' (0)
        Type u'testTriageButton' (3)
        Left Mouse Down in ApplicationBar (57)
        Left Mouse Down in ApplicationBar (59)
        Choose toolbar button 'New' (61)
        Left Mouse Down in HeadlineBlockAEEditControl (63)
        Left Mouse Down in HeadlineBlockAEEditControl (65)
        Type u'Test Triage Button' (69)
        Left Mouse Down in NotesBlock (127)
        Left Mouse Down in DashboardSummaryViewGridWindow (130)
        Left Mouse Down in TriageStamp (132)
        Left Mouse Down in DashboardSummaryViewGridWindow (135)
        Left Mouse Down in TriageStamp (137)
        Left Mouse Down in DashboardSummaryViewGridWindow (140)
        Left Mouse Down in TriageStamp (142)
    """

    wx.GetApp().RunRecordedScript ([
        (0, wx.CommandEvent, {'associatedBlock':'NewCollectionItem', 'eventType':wx.EVT_MENU, 'sentTo':u'MainViewRoot'}, {}),
        (1, wx.FocusEvent, {'eventType':wx.EVT_SET_FOCUS, 'sentTo':u'SidebarAttributeEditor'}, {}),
        (2, wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':u'SidebarAttributeEditor', 'lastWidgetValue':u'Untitled'}, {'m_rawCode':84, 'm_keyCode':84, 'm_x':166, 'm_y':36, 'UnicodeKey':84}),
        (3, wx.KeyEvent, {'eventType':wx.EVT_CHAR, 'sentTo':u'SidebarAttributeEditor', 'lastWidgetValue':u'Untitled'}, {'m_rawCode':116, 'm_keyCode':116, 'm_x':166, 'm_y':36, 'UnicodeKey':116}),
        (4, wx.KeyEvent, {'eventType':wx.EVT_KEY_UP, 'sentTo':u'SidebarAttributeEditor'}, {'m_rawCode':84, 'm_keyCode':84, 'm_x':166, 'm_y':36, 'UnicodeKey':84}),
        (5, wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':u'SidebarAttributeEditor', 'lastWidgetValue':u't'}, {'m_rawCode':69, 'm_keyCode':69, 'm_x':166, 'm_y':36, 'UnicodeKey':69}),
        (6, wx.KeyEvent, {'eventType':wx.EVT_CHAR, 'sentTo':u'SidebarAttributeEditor', 'lastWidgetValue':u't'}, {'m_rawCode':101, 'm_keyCode':101, 'm_x':166, 'm_y':36, 'UnicodeKey':101}),
        (7, wx.KeyEvent, {'eventType':wx.EVT_KEY_UP, 'sentTo':u'SidebarAttributeEditor'}, {'m_rawCode':69, 'm_keyCode':69, 'm_x':166, 'm_y':36, 'UnicodeKey':69}),
        (8, wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':u'SidebarAttributeEditor', 'lastWidgetValue':u'te'}, {'m_rawCode':83, 'm_keyCode':83, 'm_x':166, 'm_y':36, 'UnicodeKey':83}),
        (9, wx.KeyEvent, {'eventType':wx.EVT_CHAR, 'sentTo':u'SidebarAttributeEditor', 'lastWidgetValue':u'te'}, {'m_rawCode':115, 'm_keyCode':115, 'm_x':166, 'm_y':36, 'UnicodeKey':115}),
        (10, wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':u'SidebarAttributeEditor', 'lastWidgetValue':u'tes'}, {'m_rawCode':84, 'm_keyCode':84, 'm_x':166, 'm_y':36, 'UnicodeKey':84}),
        (11, wx.KeyEvent, {'eventType':wx.EVT_CHAR, 'sentTo':u'SidebarAttributeEditor', 'lastWidgetValue':u'tes'}, {'m_rawCode':116, 'm_keyCode':116, 'm_x':166, 'm_y':36, 'UnicodeKey':116}),
        (12, wx.KeyEvent, {'eventType':wx.EVT_KEY_UP, 'sentTo':u'SidebarAttributeEditor'}, {'m_rawCode':83, 'm_keyCode':83, 'm_x':166, 'm_y':36, 'UnicodeKey':83}),
        (13, wx.KeyEvent, {'eventType':wx.EVT_KEY_UP, 'sentTo':u'SidebarAttributeEditor'}, {'m_rawCode':84, 'm_keyCode':84, 'm_x':166, 'm_y':36, 'UnicodeKey':84}),
        (14, wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':u'SidebarAttributeEditor', 'lastWidgetValue':u'test'}, {'m_rawCode':16, 'm_keyCode':306, 'm_shiftDown':True, 'm_x':166, 'm_y':36, 'UnicodeKey':16}),
        (15, wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':u'SidebarAttributeEditor', 'lastWidgetValue':u'test'}, {'m_rawCode':84, 'm_keyCode':84, 'm_shiftDown':True, 'm_x':166, 'm_y':36, 'UnicodeKey':84}),
        (16, wx.KeyEvent, {'eventType':wx.EVT_CHAR, 'sentTo':u'SidebarAttributeEditor', 'lastWidgetValue':u'test'}, {'m_rawCode':84, 'm_keyCode':84, 'm_shiftDown':True, 'm_x':166, 'm_y':36, 'UnicodeKey':84}),
        (17, wx.KeyEvent, {'eventType':wx.EVT_KEY_UP, 'sentTo':u'SidebarAttributeEditor'}, {'m_rawCode':16, 'm_keyCode':306, 'm_x':166, 'm_y':36, 'UnicodeKey':16}),
        (18, wx.KeyEvent, {'eventType':wx.EVT_KEY_UP, 'sentTo':u'SidebarAttributeEditor'}, {'m_rawCode':84, 'm_keyCode':84, 'm_x':166, 'm_y':36, 'UnicodeKey':84}),
        (19, wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':u'SidebarAttributeEditor', 'lastWidgetValue':u'testT'}, {'m_rawCode':82, 'm_keyCode':82, 'm_x':166, 'm_y':36, 'UnicodeKey':82}),
        (20, wx.KeyEvent, {'eventType':wx.EVT_CHAR, 'sentTo':u'SidebarAttributeEditor', 'lastWidgetValue':u'testT'}, {'m_rawCode':114, 'm_keyCode':114, 'm_x':166, 'm_y':36, 'UnicodeKey':114}),
        (21, wx.KeyEvent, {'eventType':wx.EVT_KEY_UP, 'sentTo':u'SidebarAttributeEditor'}, {'m_rawCode':82, 'm_keyCode':82, 'm_x':166, 'm_y':36, 'UnicodeKey':82}),
        (22, wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':u'SidebarAttributeEditor', 'lastWidgetValue':u'testTr'}, {'m_rawCode':73, 'm_keyCode':73, 'm_x':166, 'm_y':36, 'UnicodeKey':73}),
        (23, wx.KeyEvent, {'eventType':wx.EVT_CHAR, 'sentTo':u'SidebarAttributeEditor', 'lastWidgetValue':u'testTr'}, {'m_rawCode':105, 'm_keyCode':105, 'm_x':166, 'm_y':36, 'UnicodeKey':105}),
        (24, wx.KeyEvent, {'eventType':wx.EVT_KEY_UP, 'sentTo':u'SidebarAttributeEditor'}, {'m_rawCode':73, 'm_keyCode':73, 'm_x':166, 'm_y':36, 'UnicodeKey':73}),
        (25, wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':u'SidebarAttributeEditor', 'lastWidgetValue':u'testTri'}, {'m_rawCode':65, 'm_keyCode':65, 'm_x':166, 'm_y':36, 'UnicodeKey':65}),
        (26, wx.KeyEvent, {'eventType':wx.EVT_CHAR, 'sentTo':u'SidebarAttributeEditor', 'lastWidgetValue':u'testTri'}, {'m_rawCode':97, 'm_keyCode':97, 'm_x':166, 'm_y':36, 'UnicodeKey':97}),
        (27, wx.KeyEvent, {'eventType':wx.EVT_KEY_UP, 'sentTo':u'SidebarAttributeEditor'}, {'m_rawCode':65, 'm_keyCode':65, 'm_x':166, 'm_y':36, 'UnicodeKey':65}),
        (28, wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':u'SidebarAttributeEditor', 'lastWidgetValue':u'testTria'}, {'m_rawCode':71, 'm_keyCode':71, 'm_x':166, 'm_y':36, 'UnicodeKey':71}),
        (29, wx.KeyEvent, {'eventType':wx.EVT_CHAR, 'sentTo':u'SidebarAttributeEditor', 'lastWidgetValue':u'testTria'}, {'m_rawCode':103, 'm_keyCode':103, 'm_x':166, 'm_y':36, 'UnicodeKey':103}),
        (30, wx.KeyEvent, {'eventType':wx.EVT_KEY_UP, 'sentTo':u'SidebarAttributeEditor'}, {'m_rawCode':71, 'm_keyCode':71, 'm_x':166, 'm_y':36, 'UnicodeKey':71}),
        (31, wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':u'SidebarAttributeEditor', 'lastWidgetValue':u'testTriag'}, {'m_rawCode':69, 'm_keyCode':69, 'm_x':166, 'm_y':36, 'UnicodeKey':69}),
        (32, wx.KeyEvent, {'eventType':wx.EVT_CHAR, 'sentTo':u'SidebarAttributeEditor', 'lastWidgetValue':u'testTriag'}, {'m_rawCode':101, 'm_keyCode':101, 'm_x':166, 'm_y':36, 'UnicodeKey':101}),
        (33, wx.KeyEvent, {'eventType':wx.EVT_KEY_UP, 'sentTo':u'SidebarAttributeEditor'}, {'m_rawCode':69, 'm_keyCode':69, 'm_x':166, 'm_y':36, 'UnicodeKey':69}),
        (34, wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':u'SidebarAttributeEditor', 'lastWidgetValue':u'testTriage'}, {'m_rawCode':16, 'm_keyCode':306, 'm_shiftDown':True, 'm_x':166, 'm_y':36, 'UnicodeKey':16}),
        (35, wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':u'SidebarAttributeEditor', 'lastWidgetValue':u'testTriage'}, {'m_rawCode':66, 'm_keyCode':66, 'm_shiftDown':True, 'm_x':166, 'm_y':36, 'UnicodeKey':66}),
        (36, wx.KeyEvent, {'eventType':wx.EVT_CHAR, 'sentTo':u'SidebarAttributeEditor', 'lastWidgetValue':u'testTriage'}, {'m_rawCode':66, 'm_keyCode':66, 'm_shiftDown':True, 'm_x':166, 'm_y':36, 'UnicodeKey':66}),
        (37, wx.KeyEvent, {'eventType':wx.EVT_KEY_UP, 'sentTo':u'SidebarAttributeEditor'}, {'m_rawCode':16, 'm_keyCode':306, 'm_x':166, 'm_y':36, 'UnicodeKey':16}),
        (38, wx.KeyEvent, {'eventType':wx.EVT_KEY_UP, 'sentTo':u'SidebarAttributeEditor'}, {'m_rawCode':66, 'm_keyCode':66, 'm_x':166, 'm_y':36, 'UnicodeKey':66}),
        (39, wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':u'SidebarAttributeEditor', 'lastWidgetValue':u'testTriageB'}, {'m_rawCode':85, 'm_keyCode':85, 'm_x':166, 'm_y':36, 'UnicodeKey':85}),
        (40, wx.KeyEvent, {'eventType':wx.EVT_CHAR, 'sentTo':u'SidebarAttributeEditor', 'lastWidgetValue':u'testTriageB'}, {'m_rawCode':117, 'm_keyCode':117, 'm_x':166, 'm_y':36, 'UnicodeKey':117}),
        (41, wx.KeyEvent, {'eventType':wx.EVT_KEY_UP, 'sentTo':u'SidebarAttributeEditor'}, {'m_rawCode':85, 'm_keyCode':85, 'm_x':166, 'm_y':36, 'UnicodeKey':85}),
        (42, wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':u'SidebarAttributeEditor', 'lastWidgetValue':u'testTriageBu'}, {'m_rawCode':84, 'm_keyCode':84, 'm_x':166, 'm_y':36, 'UnicodeKey':84}),
        (43, wx.KeyEvent, {'eventType':wx.EVT_CHAR, 'sentTo':u'SidebarAttributeEditor', 'lastWidgetValue':u'testTriageBu'}, {'m_rawCode':116, 'm_keyCode':116, 'm_x':166, 'm_y':36, 'UnicodeKey':116}),
        (44, wx.KeyEvent, {'eventType':wx.EVT_KEY_UP, 'sentTo':u'SidebarAttributeEditor'}, {'m_rawCode':84, 'm_keyCode':84, 'm_x':166, 'm_y':36, 'UnicodeKey':84}),
        (45, wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':u'SidebarAttributeEditor', 'lastWidgetValue':u'testTriageBut'}, {'m_rawCode':84, 'm_keyCode':84, 'm_x':166, 'm_y':36, 'UnicodeKey':84}),
        (46, wx.KeyEvent, {'eventType':wx.EVT_CHAR, 'sentTo':u'SidebarAttributeEditor', 'lastWidgetValue':u'testTriageBut'}, {'m_rawCode':116, 'm_keyCode':116, 'm_x':166, 'm_y':36, 'UnicodeKey':116}),
        (47, wx.KeyEvent, {'eventType':wx.EVT_KEY_UP, 'sentTo':u'SidebarAttributeEditor'}, {'m_rawCode':84, 'm_keyCode':84, 'm_x':166, 'm_y':36, 'UnicodeKey':84}),
        (48, wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':u'SidebarAttributeEditor', 'lastWidgetValue':u'testTriageButt'}, {'m_rawCode':79, 'm_keyCode':79, 'm_x':166, 'm_y':36, 'UnicodeKey':79}),
        (49, wx.KeyEvent, {'eventType':wx.EVT_CHAR, 'sentTo':u'SidebarAttributeEditor', 'lastWidgetValue':u'testTriageButt'}, {'m_rawCode':111, 'm_keyCode':111, 'm_x':166, 'm_y':36, 'UnicodeKey':111}),
        (50, wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':u'SidebarAttributeEditor', 'lastWidgetValue':u'testTriageButto'}, {'m_rawCode':78, 'm_keyCode':78, 'm_x':166, 'm_y':36, 'UnicodeKey':78}),
        (51, wx.KeyEvent, {'eventType':wx.EVT_CHAR, 'sentTo':u'SidebarAttributeEditor', 'lastWidgetValue':u'testTriageButto'}, {'m_rawCode':110, 'm_keyCode':110, 'm_x':166, 'm_y':36, 'UnicodeKey':110}),
        (52, wx.KeyEvent, {'eventType':wx.EVT_KEY_UP, 'sentTo':u'SidebarAttributeEditor'}, {'m_rawCode':79, 'm_keyCode':79, 'm_x':166, 'm_y':36, 'UnicodeKey':79}),
        (53, wx.KeyEvent, {'eventType':wx.EVT_KEY_UP, 'sentTo':u'SidebarAttributeEditor'}, {'m_rawCode':78, 'm_keyCode':78, 'm_x':166, 'm_y':36, 'UnicodeKey':78}),
        (54, wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':u'SidebarAttributeEditor', 'lastWidgetValue':u'testTriageButton'}, {'m_rawCode':13, 'm_keyCode':13, 'm_x':166, 'm_y':36, 'UnicodeKey':13}),
        (55, wx.FocusEvent, {'eventType':wx.EVT_SET_FOCUS, 'sentTo':u'SidebarGridWindow'}, {}),
        (56, wx.KeyEvent, {'eventType':wx.EVT_KEY_UP, 'sentTo':u'SidebarGridWindow'}, {'m_rawCode':13, 'm_keyCode':13, 'm_x':188, 'm_y':168, 'UnicodeKey':13}),
        (57, wx.MouseEvent, {'associatedBlock':'ApplicationBar', 'eventType':wx.EVT_LEFT_DOWN, 'sentTo':u'ApplicationBar', 'recordedFocusWindow':u'SidebarGridWindow', 'recordedFocusWindowClass':wx.Window}, {'m_leftDown':True, 'm_x':33, 'm_y':25}),
        (58, wx.MouseEvent, {'associatedBlock':'ApplicationBar', 'eventType':wx.EVT_LEFT_UP, 'sentTo':u'ApplicationBar'}, {'m_x':33, 'm_y':25}),
        (59, wx.MouseEvent, {'associatedBlock':'ApplicationBar', 'eventType':wx.EVT_LEFT_DOWN, 'sentTo':u'ApplicationBar'}, {'m_leftDown':True, 'm_x':287, 'm_y':25}),
        (60, wx.MouseEvent, {'associatedBlock':'ApplicationBar', 'eventType':wx.EVT_LEFT_UP, 'sentTo':u'ApplicationBar'}, {'m_x':287, 'm_y':25}),
        (61, wx.CommandEvent, {'associatedBlock':'ApplicationBarNewButton', 'eventType':wx.EVT_MENU, 'sentTo':u'ApplicationBar'}, {}),
        (62, wx.FocusEvent, {'eventType':wx.EVT_SET_FOCUS, 'sentTo':u'HeadlineBlockAEEditControl'}, {}),
        (63, wx.MouseEvent, {'eventType':wx.EVT_LEFT_DOWN, 'sentTo':u'HeadlineBlockAEEditControl', 'recordedFocusWindow':u'HeadlineBlockAEEditControl', 'recordedFocusWindowClass':osaf.framework.attributeEditors.DragAndDropTextCtrl.DragAndDropTextCtrl, 'lastWidgetValue':u'Untitled'}, {'m_leftDown':True, 'm_x':85, 'm_y':7}),
        (64, wx.MouseEvent, {'eventType':wx.EVT_LEFT_UP, 'sentTo':u'HeadlineBlockAEEditControl', 'selectionRange': (8,8)}, {'m_x':85, 'm_y':7}),
        (65, wx.MouseEvent, {'eventType':wx.EVT_LEFT_DOWN, 'sentTo':u'HeadlineBlockAEEditControl', 'lastWidgetValue':u'Untitled'}, {'m_leftDown':True, 'm_x':85, 'm_y':8}),
        (66, wx.MouseEvent, {'eventType':wx.EVT_LEFT_UP, 'sentTo':u'HeadlineBlockAEEditControl', 'selectionRange': (0,8)}, {'m_x':-13, 'm_y':15}),
        (67, wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':u'HeadlineBlockAEEditControl', 'lastWidgetValue':u'Untitled'}, {'m_rawCode':16, 'm_keyCode':306, 'm_shiftDown':True, 'm_x':-11, 'm_y':17, 'UnicodeKey':16}),
        (68, wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':u'HeadlineBlockAEEditControl', 'lastWidgetValue':u'Untitled'}, {'m_rawCode':84, 'm_keyCode':84, 'm_shiftDown':True, 'm_x':-11, 'm_y':17, 'UnicodeKey':84}),
        (69, wx.KeyEvent, {'eventType':wx.EVT_CHAR, 'sentTo':u'HeadlineBlockAEEditControl', 'lastWidgetValue':u'Untitled'}, {'m_rawCode':84, 'm_keyCode':84, 'm_shiftDown':True, 'm_x':-11, 'm_y':17, 'UnicodeKey':84}),
        (70, wx.KeyEvent, {'eventType':wx.EVT_KEY_UP, 'sentTo':u'HeadlineBlockAEEditControl'}, {'m_rawCode':16, 'm_keyCode':306, 'm_x':-11, 'm_y':17, 'UnicodeKey':16}),
        (71, wx.KeyEvent, {'eventType':wx.EVT_KEY_UP, 'sentTo':u'HeadlineBlockAEEditControl'}, {'m_rawCode':84, 'm_keyCode':84, 'm_x':-11, 'm_y':17, 'UnicodeKey':84}),
        (72, wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':u'HeadlineBlockAEEditControl', 'lastWidgetValue':u'T'}, {'m_rawCode':69, 'm_keyCode':69, 'm_x':-11, 'm_y':17, 'UnicodeKey':69}),
        (73, wx.KeyEvent, {'eventType':wx.EVT_CHAR, 'sentTo':u'HeadlineBlockAEEditControl', 'lastWidgetValue':u'T'}, {'m_rawCode':101, 'm_keyCode':101, 'm_x':-11, 'm_y':17, 'UnicodeKey':101}),
        (74, wx.KeyEvent, {'eventType':wx.EVT_KEY_UP, 'sentTo':u'HeadlineBlockAEEditControl'}, {'m_rawCode':69, 'm_keyCode':69, 'm_x':-11, 'm_y':17, 'UnicodeKey':69}),
        (75, wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':u'HeadlineBlockAEEditControl', 'lastWidgetValue':u'Te'}, {'m_rawCode':83, 'm_keyCode':83, 'm_x':-11, 'm_y':17, 'UnicodeKey':83}),
        (76, wx.KeyEvent, {'eventType':wx.EVT_CHAR, 'sentTo':u'HeadlineBlockAEEditControl', 'lastWidgetValue':u'Te'}, {'m_rawCode':115, 'm_keyCode':115, 'm_x':-11, 'm_y':17, 'UnicodeKey':115}),
        (77, wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':u'HeadlineBlockAEEditControl', 'lastWidgetValue':u'Tes'}, {'m_rawCode':84, 'm_keyCode':84, 'm_x':-11, 'm_y':17, 'UnicodeKey':84}),
        (78, wx.KeyEvent, {'eventType':wx.EVT_CHAR, 'sentTo':u'HeadlineBlockAEEditControl', 'lastWidgetValue':u'Tes'}, {'m_rawCode':116, 'm_keyCode':116, 'm_x':-11, 'm_y':17, 'UnicodeKey':116}),
        (79, wx.KeyEvent, {'eventType':wx.EVT_KEY_UP, 'sentTo':u'HeadlineBlockAEEditControl'}, {'m_rawCode':83, 'm_keyCode':83, 'm_x':-11, 'm_y':17, 'UnicodeKey':83}),
        (80, wx.KeyEvent, {'eventType':wx.EVT_KEY_UP, 'sentTo':u'HeadlineBlockAEEditControl'}, {'m_rawCode':84, 'm_keyCode':84, 'm_x':-11, 'm_y':17, 'UnicodeKey':84}),
        (81, wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':u'HeadlineBlockAEEditControl', 'lastWidgetValue':u'Test'}, {'m_rawCode':32, 'm_keyCode':32, 'm_x':-11, 'm_y':17, 'UnicodeKey':32}),
        (82, wx.KeyEvent, {'eventType':wx.EVT_CHAR, 'sentTo':u'HeadlineBlockAEEditControl', 'lastWidgetValue':u'Test'}, {'m_rawCode':32, 'm_keyCode':32, 'm_x':-11, 'm_y':17, 'UnicodeKey':32}),
        (83, wx.KeyEvent, {'eventType':wx.EVT_KEY_UP, 'sentTo':u'HeadlineBlockAEEditControl'}, {'m_rawCode':32, 'm_keyCode':32, 'm_x':-11, 'm_y':17, 'UnicodeKey':32}),
        (84, wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':u'HeadlineBlockAEEditControl', 'lastWidgetValue':u'Test '}, {'m_rawCode':16, 'm_keyCode':306, 'm_shiftDown':True, 'm_x':-11, 'm_y':17, 'UnicodeKey':16}),
        (85, wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':u'HeadlineBlockAEEditControl', 'lastWidgetValue':u'Test '}, {'m_rawCode':84, 'm_keyCode':84, 'm_shiftDown':True, 'm_x':-11, 'm_y':17, 'UnicodeKey':84}),
        (86, wx.KeyEvent, {'eventType':wx.EVT_CHAR, 'sentTo':u'HeadlineBlockAEEditControl', 'lastWidgetValue':u'Test '}, {'m_rawCode':84, 'm_keyCode':84, 'm_shiftDown':True, 'm_x':-11, 'm_y':17, 'UnicodeKey':84}),
        (87, wx.KeyEvent, {'eventType':wx.EVT_KEY_UP, 'sentTo':u'HeadlineBlockAEEditControl'}, {'m_rawCode':84, 'm_keyCode':84, 'm_shiftDown':True, 'm_x':-11, 'm_y':17, 'UnicodeKey':84}),
        (88, wx.KeyEvent, {'eventType':wx.EVT_KEY_UP, 'sentTo':u'HeadlineBlockAEEditControl'}, {'m_rawCode':16, 'm_keyCode':306, 'm_x':-11, 'm_y':17, 'UnicodeKey':16}),
        (89, wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':u'HeadlineBlockAEEditControl', 'lastWidgetValue':u'Test T'}, {'m_rawCode':82, 'm_keyCode':82, 'm_x':-11, 'm_y':17, 'UnicodeKey':82}),
        (90, wx.KeyEvent, {'eventType':wx.EVT_CHAR, 'sentTo':u'HeadlineBlockAEEditControl', 'lastWidgetValue':u'Test T'}, {'m_rawCode':114, 'm_keyCode':114, 'm_x':-11, 'm_y':17, 'UnicodeKey':114}),
        (91, wx.KeyEvent, {'eventType':wx.EVT_KEY_UP, 'sentTo':u'HeadlineBlockAEEditControl'}, {'m_rawCode':82, 'm_keyCode':82, 'm_x':-11, 'm_y':17, 'UnicodeKey':82}),
        (92, wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':u'HeadlineBlockAEEditControl', 'lastWidgetValue':u'Test Tr'}, {'m_rawCode':73, 'm_keyCode':73, 'm_x':-11, 'm_y':17, 'UnicodeKey':73}),
        (93, wx.KeyEvent, {'eventType':wx.EVT_CHAR, 'sentTo':u'HeadlineBlockAEEditControl', 'lastWidgetValue':u'Test Tr'}, {'m_rawCode':105, 'm_keyCode':105, 'm_x':-11, 'm_y':17, 'UnicodeKey':105}),
        (94, wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':u'HeadlineBlockAEEditControl', 'lastWidgetValue':u'Test Tri'}, {'m_rawCode':65, 'm_keyCode':65, 'm_x':-11, 'm_y':17, 'UnicodeKey':65}),
        (95, wx.KeyEvent, {'eventType':wx.EVT_CHAR, 'sentTo':u'HeadlineBlockAEEditControl', 'lastWidgetValue':u'Test Tri'}, {'m_rawCode':97, 'm_keyCode':97, 'm_x':-11, 'm_y':17, 'UnicodeKey':97}),
        (96, wx.KeyEvent, {'eventType':wx.EVT_KEY_UP, 'sentTo':u'HeadlineBlockAEEditControl'}, {'m_rawCode':73, 'm_keyCode':73, 'm_x':-11, 'm_y':17, 'UnicodeKey':73}),
        (97, wx.KeyEvent, {'eventType':wx.EVT_KEY_UP, 'sentTo':u'HeadlineBlockAEEditControl'}, {'m_rawCode':65, 'm_keyCode':65, 'm_x':-11, 'm_y':17, 'UnicodeKey':65}),
        (98, wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':u'HeadlineBlockAEEditControl', 'lastWidgetValue':u'Test Tria'}, {'m_rawCode':71, 'm_keyCode':71, 'm_x':-11, 'm_y':17, 'UnicodeKey':71}),
        (99, wx.KeyEvent, {'eventType':wx.EVT_CHAR, 'sentTo':u'HeadlineBlockAEEditControl', 'lastWidgetValue':u'Test Tria'}, {'m_rawCode':103, 'm_keyCode':103, 'm_x':-11, 'm_y':17, 'UnicodeKey':103}),
        (100, wx.KeyEvent, {'eventType':wx.EVT_KEY_UP, 'sentTo':u'HeadlineBlockAEEditControl'}, {'m_rawCode':71, 'm_keyCode':71, 'm_x':-11, 'm_y':17, 'UnicodeKey':71}),
        (101, wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':u'HeadlineBlockAEEditControl', 'lastWidgetValue':u'Test Triag'}, {'m_rawCode':69, 'm_keyCode':69, 'm_x':-11, 'm_y':17, 'UnicodeKey':69}),
        (102, wx.KeyEvent, {'eventType':wx.EVT_CHAR, 'sentTo':u'HeadlineBlockAEEditControl', 'lastWidgetValue':u'Test Triag'}, {'m_rawCode':101, 'm_keyCode':101, 'm_x':-11, 'm_y':17, 'UnicodeKey':101}),
        (103, wx.KeyEvent, {'eventType':wx.EVT_KEY_UP, 'sentTo':u'HeadlineBlockAEEditControl'}, {'m_rawCode':69, 'm_keyCode':69, 'm_x':-11, 'm_y':17, 'UnicodeKey':69}),
        (104, wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':u'HeadlineBlockAEEditControl', 'lastWidgetValue':u'Test Triage'}, {'m_rawCode':32, 'm_keyCode':32, 'm_x':-11, 'm_y':17, 'UnicodeKey':32}),
        (105, wx.KeyEvent, {'eventType':wx.EVT_CHAR, 'sentTo':u'HeadlineBlockAEEditControl', 'lastWidgetValue':u'Test Triage'}, {'m_rawCode':32, 'm_keyCode':32, 'm_x':-11, 'm_y':17, 'UnicodeKey':32}),
        (106, wx.KeyEvent, {'eventType':wx.EVT_KEY_UP, 'sentTo':u'HeadlineBlockAEEditControl'}, {'m_rawCode':32, 'm_keyCode':32, 'm_x':-11, 'm_y':17, 'UnicodeKey':32}),
        (107, wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':u'HeadlineBlockAEEditControl', 'lastWidgetValue':u'Test Triage '}, {'m_rawCode':16, 'm_keyCode':306, 'm_shiftDown':True, 'm_x':-11, 'm_y':17, 'UnicodeKey':16}),
        (108, wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':u'HeadlineBlockAEEditControl', 'lastWidgetValue':u'Test Triage '}, {'m_rawCode':66, 'm_keyCode':66, 'm_shiftDown':True, 'm_x':-11, 'm_y':17, 'UnicodeKey':66}),
        (109, wx.KeyEvent, {'eventType':wx.EVT_CHAR, 'sentTo':u'HeadlineBlockAEEditControl', 'lastWidgetValue':u'Test Triage '}, {'m_rawCode':66, 'm_keyCode':66, 'm_shiftDown':True, 'm_x':-11, 'm_y':17, 'UnicodeKey':66}),
        (110, wx.KeyEvent, {'eventType':wx.EVT_KEY_UP, 'sentTo':u'HeadlineBlockAEEditControl'}, {'m_rawCode':16, 'm_keyCode':306, 'm_x':-11, 'm_y':17, 'UnicodeKey':16}),
        (111, wx.KeyEvent, {'eventType':wx.EVT_KEY_UP, 'sentTo':u'HeadlineBlockAEEditControl'}, {'m_rawCode':66, 'm_keyCode':66, 'm_x':-11, 'm_y':17, 'UnicodeKey':66}),
        (112, wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':u'HeadlineBlockAEEditControl', 'lastWidgetValue':u'Test Triage B'}, {'m_rawCode':85, 'm_keyCode':85, 'm_x':-11, 'm_y':17, 'UnicodeKey':85}),
        (113, wx.KeyEvent, {'eventType':wx.EVT_CHAR, 'sentTo':u'HeadlineBlockAEEditControl', 'lastWidgetValue':u'Test Triage B'}, {'m_rawCode':117, 'm_keyCode':117, 'm_x':-11, 'm_y':17, 'UnicodeKey':117}),
        (114, wx.KeyEvent, {'eventType':wx.EVT_KEY_UP, 'sentTo':u'HeadlineBlockAEEditControl'}, {'m_rawCode':85, 'm_keyCode':85, 'm_x':-11, 'm_y':17, 'UnicodeKey':85}),
        (115, wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':u'HeadlineBlockAEEditControl', 'lastWidgetValue':u'Test Triage Bu'}, {'m_rawCode':84, 'm_keyCode':84, 'm_x':-11, 'm_y':17, 'UnicodeKey':84}),
        (116, wx.KeyEvent, {'eventType':wx.EVT_CHAR, 'sentTo':u'HeadlineBlockAEEditControl', 'lastWidgetValue':u'Test Triage Bu'}, {'m_rawCode':116, 'm_keyCode':116, 'm_x':-11, 'm_y':17, 'UnicodeKey':116}),
        (117, wx.KeyEvent, {'eventType':wx.EVT_KEY_UP, 'sentTo':u'HeadlineBlockAEEditControl'}, {'m_rawCode':84, 'm_keyCode':84, 'm_x':-11, 'm_y':17, 'UnicodeKey':84}),
        (118, wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':u'HeadlineBlockAEEditControl', 'lastWidgetValue':u'Test Triage But'}, {'m_rawCode':84, 'm_keyCode':84, 'm_x':-11, 'm_y':17, 'UnicodeKey':84}),
        (119, wx.KeyEvent, {'eventType':wx.EVT_CHAR, 'sentTo':u'HeadlineBlockAEEditControl', 'lastWidgetValue':u'Test Triage But'}, {'m_rawCode':116, 'm_keyCode':116, 'm_x':-11, 'm_y':17, 'UnicodeKey':116}),
        (120, wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':u'HeadlineBlockAEEditControl', 'lastWidgetValue':u'Test Triage Butt'}, {'m_rawCode':79, 'm_keyCode':79, 'm_x':-11, 'm_y':17, 'UnicodeKey':79}),
        (121, wx.KeyEvent, {'eventType':wx.EVT_CHAR, 'sentTo':u'HeadlineBlockAEEditControl', 'lastWidgetValue':u'Test Triage Butt'}, {'m_rawCode':111, 'm_keyCode':111, 'm_x':-11, 'm_y':17, 'UnicodeKey':111}),
        (122, wx.KeyEvent, {'eventType':wx.EVT_KEY_UP, 'sentTo':u'HeadlineBlockAEEditControl'}, {'m_rawCode':84, 'm_keyCode':84, 'm_x':-11, 'm_y':17, 'UnicodeKey':84}),
        (123, wx.KeyEvent, {'eventType':wx.EVT_KEY_DOWN, 'sentTo':u'HeadlineBlockAEEditControl', 'lastWidgetValue':u'Test Triage Butto'}, {'m_rawCode':78, 'm_keyCode':78, 'm_x':-11, 'm_y':17, 'UnicodeKey':78}),
        (124, wx.KeyEvent, {'eventType':wx.EVT_CHAR, 'sentTo':u'HeadlineBlockAEEditControl', 'lastWidgetValue':u'Test Triage Butto'}, {'m_rawCode':110, 'm_keyCode':110, 'm_x':-11, 'm_y':17, 'UnicodeKey':110}),
        (125, wx.KeyEvent, {'eventType':wx.EVT_KEY_UP, 'sentTo':u'HeadlineBlockAEEditControl'}, {'m_rawCode':79, 'm_keyCode':79, 'm_x':-11, 'm_y':17, 'UnicodeKey':79}),
        (126, wx.KeyEvent, {'eventType':wx.EVT_KEY_UP, 'sentTo':u'HeadlineBlockAEEditControl'}, {'m_rawCode':78, 'm_keyCode':78, 'm_x':-11, 'm_y':17, 'UnicodeKey':78}),
        (127, wx.MouseEvent, {'associatedBlock':'NotesBlock', 'eventType':wx.EVT_LEFT_DOWN, 'sentTo':u'NotesBlock', 'lastWidgetValue':u'Test Triage Button'}, {'m_leftDown':True, 'm_x':107, 'm_y':166}),
        (128, wx.FocusEvent, {'associatedBlock':'NotesBlock', 'eventType':wx.EVT_SET_FOCUS, 'sentTo':u'NotesBlock'}, {}),
        (129, wx.MouseEvent, {'associatedBlock':'NotesBlock', 'eventType':wx.EVT_LEFT_UP, 'sentTo':u'NotesBlock', 'selectionRange': (0,0)}, {'m_x':107, 'm_y':172}),
        (130, wx.MouseEvent, {'eventType':wx.EVT_LEFT_DOWN, 'sentTo':u'DashboardSummaryViewGridWindow', 'recordedFocusWindow':u'NotesBlock', 'recordedFocusWindowClass':osaf.framework.attributeEditors.AETypeOverTextCtrl.AENonTypeOverTextCtrl, 'lastWidgetValue':u''}, {'m_leftDown':True, 'm_x':505, 'm_y':30}),
        (131, wx.MouseEvent, {'eventType':wx.EVT_LEFT_UP, 'sentTo':u'DashboardSummaryViewGridWindow'}, {'m_x':505, 'm_y':30}),
        (132, wx.MouseEvent, {'associatedBlock':'TriageStamp', 'eventType':wx.EVT_LEFT_DOWN, 'sentTo':u'TriageStamp'}, {'m_leftDown':True, 'm_x':13, 'm_y':16}),
        (133, wx.MouseEvent, {'associatedBlock':'TriageStamp', 'eventType':wx.EVT_LEFT_UP, 'sentTo':u'TriageStamp'}, {'m_x':13, 'm_y':16}),
        (134, wx.PyCommandEvent, {'associatedBlock':'TriageStamp', 'eventType':wx.EVT_BUTTON, 'sentTo':u'TriageStamp'}, {}),
        (135, wx.MouseEvent, {'eventType':wx.EVT_LEFT_DOWN, 'sentTo':u'DashboardSummaryViewGridWindow'}, {'m_leftDown':True, 'm_x':502, 'm_y':25}),
        (136, wx.MouseEvent, {'eventType':wx.EVT_LEFT_UP, 'sentTo':u'DashboardSummaryViewGridWindow'}, {'m_x':502, 'm_y':25}),
        (137, wx.MouseEvent, {'associatedBlock':'TriageStamp', 'eventType':wx.EVT_LEFT_DOWN, 'sentTo':u'TriageStamp'}, {'m_leftDown':True, 'm_x':31, 'm_y':11}),
        (138, wx.MouseEvent, {'associatedBlock':'TriageStamp', 'eventType':wx.EVT_LEFT_UP, 'sentTo':u'TriageStamp'}, {'m_x':31, 'm_y':11}),
        (139, wx.PyCommandEvent, {'associatedBlock':'TriageStamp', 'eventType':wx.EVT_BUTTON, 'sentTo':u'TriageStamp'}, {}),
        (140, wx.MouseEvent, {'eventType':wx.EVT_LEFT_DOWN, 'sentTo':u'DashboardSummaryViewGridWindow'}, {'m_leftDown':True, 'm_x':504, 'm_y':27}),
        (141, wx.MouseEvent, {'eventType':wx.EVT_LEFT_UP, 'sentTo':u'DashboardSummaryViewGridWindow'}, {'m_x':504, 'm_y':27}),
        (142, wx.MouseEvent, {'associatedBlock':'TriageStamp', 'eventType':wx.EVT_LEFT_DOWN, 'sentTo':u'TriageStamp'}, {'m_leftDown':True, 'm_x':21, 'm_y':19}),
        (143, wx.MouseEvent, {'associatedBlock':'TriageStamp', 'eventType':wx.EVT_LEFT_UP, 'sentTo':u'TriageStamp'}, {'m_x':21, 'm_y':19}),
        (144, wx.PyCommandEvent, {'associatedBlock':'TriageStamp', 'eventType':wx.EVT_BUTTON, 'sentTo':u'TriageStamp'}, {}),
    ])
