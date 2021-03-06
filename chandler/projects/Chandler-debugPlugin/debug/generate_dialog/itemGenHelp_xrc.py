# This file was automatically generated by pywxrc, do not edit by hand.
# -*- coding: UTF-8 -*-

import wx
import wx.xrc as xrc
import pkg_resources
import application.Globals as Globals

__res = None

def get_resources():
    """ This function provides access to the XML resources in this module."""
    global __res
    if __res == None:
        __init_resources()
    return __res


class xrcHelpWin(wx.Dialog):
    def PreCreate(self, pre):
        """ This function is called during the class's initialization.
        
        Override it for custom setup before the window is created usually to
        set additional window styles using SetWindowStyle() and SetExtraStyle()."""
        pass

    def __init__(self, parent):
        # Two stage creation (see http://wiki.wxpython.org/index.cgi/TwoStageCreation)
        pre = wx.PreDialog()
        self.PreCreate(pre)
        get_resources().LoadOnDialog(pre, parent, "DIALOG1")
        self.PostCreate(pre)

        # create attributes for the named items in this container



# ------------------------ Resource data ----------------------

def __init_resources():
    global __res
    xml = pkg_resources.resource_string(__name__, 'itemGenHelp.xrc')
    __res = xrc.EmptyXmlResource()
    __res.LoadFromString(xml)
    
def showStandAlone():
    app = wx.PySimpleApp()
    dialog = xrcHelpWin(None)
    result = dialog.Show()

if __name__ == '__main__':
    showStandAlone()
