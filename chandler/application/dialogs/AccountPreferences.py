#: Copyright (c) 2003-2008 Open Source Applications Foundation
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


# Account Preferences Dialog
# Invoke this using the ShowAccountPreferencesDialog() method

import os, sys
import wx
import wx.xrc

import application.schema as schema
from   application import Globals
import osaf.pim.mail as Mail
from osaf.mail import constants
from osaf import sharing
from osaf.framework.twisted import waitForDeferred
from i18n import ChandlerMessageFactory as _
from AccountPreferencesDialogs import MailTestDialog, \
                                      AutoDiscoveryDialog, \
                                      ChandlerIMAPFoldersDialog, \
                                      RemoveChandlerIMAPFoldersDialog, \
                                      SharingTestDialog, \
                                      showYesNoDialog, \
                                      showOKDialog, \
                                      showConfigureDialog
from osaf.framework import password
from pkg_resources import iter_entry_points
import logging
logger = logging.getLogger(__name__)


class AccountPanel(schema.Item):
    accountClass = schema.One(schema.Class)
    key = schema.One(schema.Text)
    info = schema.One(schema.Dictionary)
    xrc = schema.One(schema.Text)


# Localized messages displayed in dialogs

CREATE_TEXT = _(u"Configure")
REMOVE_TEXT = _(u"Remove")

# --- Error Messages ----- #
FIELDS_REQUIRED = _(u"The following fields are required:\n\n\tServer\n\tUser name\n\tPassword\n\tPort\n\n\nPlease correct the error and try again.")
FIELDS_REQUIRED_ONE = _(u"The following fields are required:\n\n\tServer\n\tPort\n\n\nPlease correct the error and try again.")
FIELDS_REQUIRED_TWO = _(u"The following fields are required:\n\n\tServer\n\tPath\n\tUser name\n\tPassword\n\tPort\n\n\nPlease correct the error and try again.")
FIELDS_REQUIRED_THREE = _(u"The following fields are required:\n\n\tUser name\n\tPassword\n\n\nPlease correct the error and try again.")

HOST_REQUIRED  = _(u"Auto-configure requires a server name.")




# --- Yes No Dialog Messages ----- #
CREATE_FOLDERS_TITLE = _(u"Configure Chandler Folders")

CREATE_FOLDERS = _(u"""Chandler will attempt to create the following IMAP folders in your account on '%(host)s':

    %(ChandlerMailFolder)s
    %(ChandlerStarredFolder)s
    %(ChandlerEventsFolder)s

If you have already set up Chandler folders in your account, no new folders will be created. If you have an existing folder named %(ChandlerTasksFolder)s, it will be renamed to %(ChandlerStarredFolder)s.

Folders may take a while to show up in your email application.""")


REMOVE_FOLDERS_TITLE = _(u"Remove Chandler Folders")
REMOVE_FOLDERS = _(u"""Chandler will now attempt to remove the following IMAP folders on '%(host)s':

    %(ChandlerMailFolder)s
    %(ChandlerStarredFolder)s
    %(ChandlerEventsFolder)s

Would you like to proceed?""")


# Will print out saved account changes
# before exiting the dialog when set to True
DEBUG = False
FOLDERS_URL = "http://chandlerproject.org/chandlerfolders"
SHARING_URL = "http://hub.chandlerproject.org/signup"

# Special handlers referenced in the panelsInfo dictionary below:

def IncomingValidationHandler(item, fields, values):
    newAddressString = values['INCOMING_EMAIL_ADDRESS']
    # Blank address string?  Don't bother the user now, they will get
    # reminded when they actually try to fetch mail.  Bogus address?
    # They better fix it before leaving the dialog box.
    if not newAddressString or \
        Mail.EmailAddress.isValidEmailAddress(newAddressString):
        return None
    else:
        return _(u"'%(emailAddress)s' is not a valid email address") % \
                {'emailAddress': newAddressString}

def IncomingSaveHandler(item, fields, values):
    newAddressString = values['INCOMING_EMAIL_ADDRESS']
    newFullName = values['INCOMING_FULL_NAME']
    newUsername = values['INCOMING_USERNAME']
    newServer = values['INCOMING_SERVER']
    newAccountProtocol = values['INCOMING_PROTOCOL']

    # If either the host, username, or protocol changes
    # we need to set this account item to inactive and
    # create a new one.
    if (item.host and item.host != newServer) or \
       (item.username and item.username != newUsername) or \
       (item.accountProtocol != newAccountProtocol):
        item.isActive = False

        ns_pim = schema.ns('osaf.pim', item.itsView)

        isCurrent = item == getattr(ns_pim.currentIncomingAccount, \
                                    "item", None)

        if newAccountProtocol == "IMAP":
            item = Mail.IMAPAccount(itsView=item.itsView)

        elif newAccountProtocol == "POP":
            item = Mail.POPAccount(itsView=item.itsView)
        else:
            # If this code is reached then there is a
            # bug which needs to be fixed.
            raise Exception("Internal Exception")

        if not hasattr(item, 'password'):
            item.password = password.Password(itsView=item.itsView,
                                              itsParent=item)

        if isCurrent:
            ns_pim.currentIncomingAccount.item = item


    item.replyToAddress = Mail.EmailAddress.getEmailAddress(item.itsView,
                                                            newAddressString,
                                                            newFullName)


    return item # Returning a non-None item tells the caller to continue
                # processing this item.
                # Returning None would tell the caller that processing this
                # item is complete.


def IncomingDeleteHandler(item, values, data):
    return True

def OutgoingSaveHandler(item, fields, values):
    newAddressString = values['OUTGOING_EMAIL_ADDRESS']
    newFullName =  values['OUTGOING_FULL_NAME']


    item.fromAddress = Mail.EmailAddress.getEmailAddress(item.itsView,
                                                         newAddressString,
                                                         newFullName)

    return item # Returning a non-None item tells the caller to continue
                # processing this item.
                # Returning None would tell the caller that processing this
                # item is complete.

def OutgoingDeleteHandler(item, values, data):
    return True

def SharingDeleteHandler(item, values, data):
    return not len(getattr(item, 'conduits', []))



# Generic defaults based on the attr type.  Use "default" on attr for
# specific defaults.
DEFAULTS = {'string': '', 'password': '', 'integer': 0, 'boolean': False}

# If incoming email addresses domain matches, we will automatically fill
# in what we can.
PREFILLED_INCOMING_EMAIL = {
#        'example.com': {
#            'server'   : 'mail.example.com',
#            'port'     : <int>,
#            'useSSL'   : 'NONE' | 'SSL' | 'TLS',
#            'protocol' : 'POP' | 'IMAP',
#            'user'     : True for username, False for username@domain.com
#        },
        'comcast.net': { # auto-configure times out with these settings, but these are correct
            'server'   : 'mail.comcast.net',
            'port'     : 995,
            'useSSL'   : 'SSL',
            'protocol' : 'POP',
            'user'     : True
        },
        'osafoundation.org': {
            'server'   : 'imap.osafoundation.org',
            'port'     : 993,
            'useSSL'   : 'SSL',
            'protocol' : 'IMAP',
            'user'     : True
        },
        'gmail.com': {
            'server'   : 'pop.gmail.com',
            'port'     : 995,
            'useSSL'   : 'SSL',
            'protocol' : 'POP',
            'user'     : True
        },
        'mac.com': {
            'server'   : 'mail.mac.com',
            'port'     : 993,
            'useSSL'   : 'SSL',
            'protocol' : 'IMAP',
            'user'     : True
        },
        'yahoo.com': { # http://help.yahoo.com/l/us/yahoo/mail/original/mailplus/pop/pop-06.html
            'server'   : 'pop.mail.yahoo.com',
            'port'     : 995,
            'useSSL'   : 'SSL',
            'protocol' : 'POP',
            'user'     : True
        },
}

# If outgoing email addresses domain matches, we will automatically fill
# in what we can.
PREFILLED_OUTGOING_EMAIL = {
#        'example.com': {
#            'server'   : 'mail.example.com',
#            'port'     : <int>,
#            'useSSL'   : 'NONE' | 'SSL' | 'TLS',
#            'auth'     : True | False,
#            'user'     : True for username, False for username@domain.com
#        },
        'comcast.net': {
            'server' : 'smtp.comcast.net',
            'port'   : 465,
            'useSSL' : 'SSL',
            'auth'   : True,
            'user'   : True
        },
        'osafoundation.org': {
            'server' : 'smtp.osafoundation.org',
            'port'   : 587,
            'useSSL' : 'TLS',
            'auth'   : True,
            'user'   : True
        },
        'gmail.com': {
            'server' : 'smtp.gmail.com',
            'port'   : 465,
            'useSSL' : 'SSL',
            'auth'   : True,
            'user'   : False
        },
        'mac.com': {
            'server'   : 'smtp.mac.com',
            'port'     : 587,
            'useSSL'   : 'TLS',
            'auth'     : True,
            'user'     : True
        },
        'yahoo.com': { # http://help.yahoo.com/l/us/yahoo/mail/original/mailplus/pop/pop-06.html
            'server'   : 'smtp.mail.yahoo.com',
            'port'     : 465,
            'useSSL'   : 'SSL',
            'auth'     : True,
            'user'     : True
        },
}

class AccountPreferencesDialog(wx.Dialog):

    def __init__(self, title, size=wx.DefaultSize,
         pos=wx.DefaultPosition, style=wx.DEFAULT_DIALOG_STYLE, resources=None,
         account=None, rv=None, modal=True, create=None):

        wx.Dialog.__init__(self, wx.GetApp().mainFrame, -1, title, pos, size,
                           style)

        # Used to map form fields to item attributes:
        self.panelsInfo = {
            "INCOMING" : {
                "fields" : {
                    "INCOMING_DESCRIPTION" : {
                        "attr" : "displayName",
                        "type" : "string",
                        "required" : True,
                        "default": _(u"New Incoming Mail Account"),
                    },
                    "INCOMING_EMAIL_ADDRESS" : {
                        "attr" : "emailAddress",
                        "type" : "string",
                        "killFocusCallback": self.OnFocusLostIncomingEmail,
                    },
                    "INCOMING_FULL_NAME" : {
                        "attr" : "fullName",
                        "type" : "string",
                    },
                    "INCOMING_SERVER" : {
                        "attr" : "host",
                        "type" : "string",
                    },
                    "INCOMING_USERNAME" : {
                        "attr" : "username",
                        "type" : "string",
                    },
                    "INCOMING_PASSWORD" : {
                        "attr" : "password",
                        "type" : "password",
                    },

                    "INCOMING_PORT" : {
                        "attr" : "port",
                        "type" : "integer",
                        "default": 143,
                        "required" : True,
                    },

                    "INCOMING_PROTOCOL" : {
                        "attr" : "accountProtocol",
                        "type" : "protocolChoice",
                        "default": "IMAP",
                    },

                    "INCOMING_SECURE" : {
                        "attr" : "connectionSecurity",
                        "type" : "radioEnumeration",
                        "buttons" : {
                            "INCOMING_SECURE_NO" : "NONE",
                            "INCOMING_TLS" : "TLS",
                            "INCOMING_SSL" : "SSL",
                            },
                        "default" : "NONE",
                        "linkedTo" :
                         {
                           "callback": "getIncomingProtocol",
                           "protocols": {
                              "IMAP": ("INCOMING_PORT",
                                { "NONE":"143", "TLS":"143", "SSL":"993" } ),
                              "POP":  ("INCOMING_PORT",
                                { "NONE":"110", "TLS":"110", "SSL":"995" } ),
                            },
                         }
                    },

                    "INCOMING_FOLDERS" : {
                        "attr" : "folders",
                        "type" : "chandlerFolders",
                    },
                },
                "id" : "INCOMINGPanel",
                "order": 0,
                "saveHandler" : IncomingSaveHandler,
                "validationHandler" : IncomingValidationHandler,
                "deleteHandler" : IncomingDeleteHandler,
                "displayName" : u"INCOMING_DESCRIPTION",
                "protocol" : "IMAP",
                "class" : Mail.IMAPAccount,
                "description" : _(u"Incoming Mail"),
                "callbacks" : (
                                ("INCOMING_DISCOVERY", "OnIncomingDiscovery"),
                              ),
                "messages" : ("INCOMING_MESSAGE",),
                "init" : "initIncomingPanel",
            },
            "OUTGOING" : {
                "fields" : {
                    "OUTGOING_DESCRIPTION" : {
                        "attr" : "displayName",
                        "type" : "string",
                        "required" : True,
                        "default": _(u"New Outgoing Mail Account"),
                    },
                    "OUTGOING_EMAIL_ADDRESS" : {
                        "attr" : "emailAddress",
                        "type" : "string",
                        "killFocusCallback": self.OnFocusLostOutgoingEmail,
                    },
                    "OUTGOING_FULL_NAME" : {
                        "attr" : "fullName",
                        "type" : "string",
                    },
                    "OUTGOING_SERVER" : {
                        "attr" : "host",
                        "type" : "string",
                    },
                    "OUTGOING_PORT" : {
                        "attr" : "port",
                        "type" : "integer",
                        "default": 25,
                        "required" : True,
                    },
                    "OUTGOING_SECURE" : {
                        "attr" : "connectionSecurity",
                        "type" : "radioEnumeration",
                        "buttons" : {
                            "OUTGOING_SECURE_NO" : "NONE",
                            "OUTGOING_SECURE_TLS" : "TLS",
                            "OUTGOING_SECURE_SSL" : "SSL",
                            },
                        "default" : "NONE",
                        "linkedTo" :
                                ("OUTGOING_PORT", 
                                    { "NONE":"25", "TLS":"25", "SSL":"465" }),
                    },
                    "OUTGOING_USE_AUTH" : {
                        "attr" : "useAuth",
                        "type" : "boolean",
                    },
                    "OUTGOING_USERNAME" : {
                        "attr" : "username",
                        "type" : "string",
                    },
                    "OUTGOING_PASSWORD" : {
                        "attr" : "password",
                        "type" : "password",
                    },
                },
                "id" : "OUTGOINGPanel",
                "order": 1,
                "saveHandler" : OutgoingSaveHandler,
                "deleteHandler" : OutgoingDeleteHandler,
                "displayName" : u"OUTGOING_DESCRIPTION",
                "description" : _(u"Outgoing Mail"),
                "protocol" : "SMTP",
                "class" : Mail.SMTPAccount,
                "callbacks" : (("OUTGOING_DISCOVERY", "OnOutgoingDiscovery"),),
                "messages" : ("OUTGOING_MESSAGE",),
            },

            "SHARING_HUB" : {
                "fields" : {
                    "HUBSHARING_DESCRIPTION" : {
                        "attr" : "displayName",
                        "type" : "string",
                        "required" : True,
                        "default": _(u"New Chandler Hub Sharing Account"),
                    },
                    "HUBSHARING_USERNAME" : {
                        "attr" : "username",
                        "type" : "string",
                    },
                    "HUBSHARING_PASSWORD" : {
                        "attr" : "password",
                        "type" : "password",
                    },
                },
                "id" : "HUBSHARINGPanel",
                "order": 2,
                "deleteHandler" : SharingDeleteHandler,
                "displayName" : "HUBSHARING_DESCRIPTION",
                "protocol" : "Morsecode",
                "class" : sharing.HubAccount,
                "description" : _(u"Chandler Hub Sharing"),
                "messages" : ("SHARING_MESSAGE", "SHARING_MESSAGE2"),
            },

            "SHARING_MORSECODE" : {
                "fields" : {
                    "MORSECODE_DESCRIPTION" : {
                        "attr" : "displayName",
                        "type" : "string",
                        "required" : True,
                        "default": _(u"New Chandler Server Sharing Account"),
                    },
                    "MORSECODE_SERVER" : {
                        "attr" : "host",
                        "type" : "string",
                    },
                    "MORSECODE_PATH" : {
                        "attr" : "path",
                        "type" : "string",
                        "default": "/chandler",
                    },
                    "MORSECODE_USERNAME" : {
                        "attr" : "username",
                        "type" : "string",
                    },
                    "MORSECODE_PASSWORD" : {
                        "attr" : "password",
                        "type" : "password",
                    },
                    "MORSECODE_PORT" : {
                        "attr" : "port",
                        "type" : "integer",
                        "default": 80,
                        "required" : True,
                    },
                    "MORSECODE_USE_SSL" : {
                        "attr" : "useSSL",
                        "type" : "boolean",
                        "linkedTo" :
                                ("MORSECODE_PORT", { True:"443", False:"80" }),
                    },
                },
                "id" : "MORSECODEPanel",
                "order": 3,
                "deleteHandler" : SharingDeleteHandler,
                "displayName" : "MORSECODE_DESCRIPTION",
                "description" : _(u"Chandler Server Sharing"),
                "protocol" : "Morsecode",
                "class" : sharing.CosmoAccount,
            },

            "SHARING_DAV" : {
                "fields" : {
                    "DAV_DESCRIPTION" : {
                        "attr" : "displayName",
                        "type" : "string",
                        "required" : True,
                        "default": _(u"New WebDAV Sharing Account"),
                    },
                    "DAV_SERVER" : {
                        "attr" : "host",
                        "type" : "string",
                    },
                    "DAV_PATH" : {
                        "attr" : "path",
                        "type" : "string",
                    },
                    "DAV_USERNAME" : {
                        "attr" : "username",
                        "type" : "string",
                    },
                    "DAV_PASSWORD" : {
                        "attr" : "password",
                        "type" : "password",
                    },
                    "DAV_PORT" : {
                        "attr" : "port",
                        "type" : "integer",
                        "default": 80,
                        "required" : True,
                    },
                    "DAV_USE_SSL" : {
                        "attr" : "useSSL",
                        "type" : "boolean",
                        "linkedTo" :
                                ("DAV_PORT", { True:"443", False:"80" }),
                    },
                },
                "id" : "DAVPanel",
                "order": 4,
                "deleteHandler" : SharingDeleteHandler,
                "displayName" : "DAV_DESCRIPTION",
                "description" : _(u"WebDAV Sharing"),
                "protocol" : "WebDAV",
                "class" : sharing.WebDAVAccount,
            },
        }
        self.resources = resources
        self.rv = rv

        # outerSizer will have two children to manage: on top is innerSizer,
        # and below that is the okCancelSizer
        self.outerSizer = wx.BoxSizer(wx.VERTICAL)

        self.innerSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.accountsPanel = self.resources.LoadPanel(self, "AccountsPanel")
        self.innerSizer.Add(self.accountsPanel, 0, wx.ALIGN_TOP|wx.ALL,
                            self.getPlatformBorderSize())

        self.outerSizer.Add(self.innerSizer, 0, wx.ALIGN_CENTER|wx.ALL, 5)
        self.bottomSizer = wx.BoxSizer(wx.HORIZONTAL)

        self.messagesPanel = self.resources.LoadPanel(self, "MessagesPanel")
        self.okCancelPanel = self.resources.LoadPanel(self, "OkCancelPanel")

        # The tmp panel and tmp sizer are used to force the messagePanel to
        # maintain a specific size regardless of what text is showing.
        # There is a bug in the HyperLinkCtrl related to layout that
        # was preventing using Sizer objects in the messagesPanel.
        self.tmpSizer = wx.BoxSizer(wx.VERTICAL)
        self.tmpPanel = self.resources.LoadPanel(self, "TmpPanel")
        self.tmpSizer.Add(self.messagesPanel, 0, wx.ALIGN_TOP|wx.ALL, 0)
        self.tmpSizer.Add(self.tmpPanel, 0, wx.ALIGN_TOP|wx.ALL, 0)
        self.bottomSizer.Add(self.tmpSizer, 0, wx.ALIGN_TOP|wx.ALL, 5)

        self.bottomSizer.Add(self.okCancelPanel, 0, wx.ALIGN_TOP|wx.ALL, 5)
        self.outerSizer.Add(self.bottomSizer, 0, wx.ALIGN_TOP|wx.ALIGN_LEFT|wx.ALL, 0)

        # Load the various account form panels:
        self.panels = {}
        #isMac = Utility.getPlatformName().startswith("Mac")

        for (key, value) in self.panelsInfo.iteritems():
            self.panels[key] = self.resources.LoadPanel(self, value['id'])

            #if isMac:
            #    self.panels[key].SetWindowVariant(wx.WINDOW_VARIANT_LARGE)


            self.panels[key].Hide()

        for accountPanel in AccountPanel.iterItems(self.rv):
            info = dict(accountPanel.info)
            self.panelsInfo[accountPanel.key] = info
            self.panelsInfo[accountPanel.key]['class'] = \
                accountPanel.accountClass
            resources = wx.xrc.EmptyXmlResource()
            resources.LoadFromString(accountPanel.xrc)
            self.panels[accountPanel.key] = resources.LoadPanel(self,
                info['id'])
            self.panels[accountPanel.key].Hide()

        self.defaultPanel = self.resources.LoadPanel(self, "DEFAULTPanel")

        # These are wxHyperlinkCtrl widgets
        self.folderLink = wx.xrc.XRCCTRL(self, "INCOMING_FOLDERS_VERBAGE2")
        self.sharingLink = wx.xrc.XRCCTRL(self.messagesPanel,
            "SHARING_MESSAGE2")

        # Theses values are not localizing if set in xrc.
        # The xrc support for the wxHyperlinkCtrl needs improvement.
        self.sharingLink.SetLabel(_(u"Sign up here."))
        self.folderLink.SetLabel(_(u"Learn more."))

        # On Linux the wx layer raises an assert when
        # hiding the wxHyperlinkCtrl via xrc. So
        # instead hide the control in code.
        self.sharingLink.Hide()

        for hyperCtrl in (self.folderLink, self.sharingLink):
            hyperCtrl.SetNormalColour("#0080ff")
            hyperCtrl.SetVisitedColour("#0080ff")
            hyperCtrl.SetHoverColour("#9999cc")

        self.folderLink.SetURL(FOLDERS_URL)
        self.sharingLink.SetURL(SHARING_URL)

        self.SetSizer(self.outerSizer)
        self.outerSizer.SetSizeHints(self)
        self.outerSizer.Fit(self)

        self.accountsList = wx.xrc.XRCCTRL(self, "ACCOUNTS_LIST")
        self.choiceNewType = wx.xrc.XRCCTRL(self, "CHOICE_NEW_ACCOUNT")

        # Populate the "new account" listbox:
        typeNames = []

        for (key, value) in self.panelsInfo.iteritems():
            # store a tuple with account type description, and name
            typeNames.append( (value['order'], value['description'], key) )

        def compare(x, y):
            if x[0] == y[0]:
                return 0

            if x[0] > y[0]:
                return 1

            return -1

        typeNames.sort(cmp=compare)

        for (order, description, name) in typeNames:
            newIndex = self.choiceNewType.Append(description)
            self.choiceNewType.SetClientData(newIndex, name)

        self.choiceNewType.SetSelection(0)

        self.currentIndex = None # the list index of account in detail panel
        self.currentPanelType = None
        self.currentPanel = None # whatever detail panel we swap in

        #XXX There is a bug in the wx code that prevents
        #    a wx.HyperlinkCtrl from being hidden via
        #    xrc so the Hide() method is called by
        #    putting the sharingLink widget in
        #    the currentMessages list
        self.currentMessages = (self.sharingLink,)

        # data is a list of dictionaries of the form:
        # 'item' => item.itsUUID
        # 'values' => a dict mapping field names to attribute values
        # 'type' => accountType
        # The order of the data list needs to be the same order as what's in
        # the accounts list widget.
        self.data = [ ]

        # If the user deletes an account, its data will be moved here:
        self.deletions = [ ]

        # Keep track of accounts created during this session so "Cancel"
        # can delete them
        self.creations = set()

        if not self.__PopulateAccountsList(account):
            wx.CallAfter(self.OnCancel, None)

        self.Bind(wx.EVT_CHOICE, self.OnToggleIncomingProtocol,
                  id=wx.xrc.XRCID("INCOMING_PROTOCOL"))

        self.Bind(wx.EVT_BUTTON, self.OnIncomingFolders,
                  id=wx.xrc.XRCID("INCOMING_FOLDERS"))

        self.Bind(wx.EVT_BUTTON, self.OnOk, id=wx.ID_OK)
        self.Bind(wx.EVT_BUTTON, self.OnCancel, id=wx.ID_CANCEL)

        self.Bind(wx.EVT_BUTTON, self.OnTestAccount,
                      id=wx.xrc.XRCID("ACCOUNT_TEST"))

        self.Bind(wx.EVT_CHOICE, self.OnNewAccount,
                  id=wx.xrc.XRCID("CHOICE_NEW_ACCOUNT"))

        self.Bind(wx.EVT_BUTTON, self.OnDeleteAccount,
                  id=wx.xrc.XRCID("BUTTON_DELETE"))

        self.Bind(wx.EVT_LISTBOX, self.OnAccountSel,
         id=wx.xrc.XRCID("ACCOUNTS_LIST"))

        self.SetDefaultItem(wx.xrc.XRCCTRL(self, "wxID_OK"))

        # Setting focus to the accounts list let's us "tab" to the first
        # text field (without this, on the mac, tabbing doesn't work)
        self.accountsList.SetFocus()

        if create:
            self.CreateNewAccount(create)

    def getPlatformBorderSize(self):
        if wx.Platform == "__WXMAC__":
            return 5
        elif wx.Platform == "__WXMSW__":
            return 10

        # Linux
        return 22

    def isDefaultAccount(self, item):
        isDefault = False

        if item.accountType == "INCOMING":
            default = getattr(schema.ns('osaf.pim',
                item.itsView).currentIncomingAccount, "item", None)
            isDefault = default and item is default

        elif item.accountType == "OUTGOING":
            default = getattr(schema.ns('osaf.pim',
                item.itsView).currentOutgoingAccount, "item", None)
            isDefault = default and item is default

        return isDefault

    def getDefaultAccounts(self):
        ns_pim = schema.ns('osaf.pim', self.rv)

        incoming  = getattr(ns_pim.currentIncomingAccount, "item", None)
        outgoing  = getattr(ns_pim.currentOutgoingAccount, "item", None)
        return (incoming, outgoing)


    def selectAccount(self, accountIndex):

        delButton = wx.xrc.XRCCTRL(self, "BUTTON_DELETE")
        testButton = wx.xrc.XRCCTRL(self, "ACCOUNT_TEST")

        if accountIndex != -1:

            self.accountsList.SetSelection(accountIndex)
            self.__SwapDetailPanel(accountIndex)

            item = self.rv.findUUID(self.data[accountIndex]['item'])

            # Disable the delete button if the delete handler says to

            deleteHandler = self.panelsInfo[item.accountType].get(
                'deleteHandler', None)
            if deleteHandler is None:
                canDelete = True
            else:
                canDelete = deleteHandler(item,
                    self.data[accountIndex]['values'], self.data)
            delButton.Enable(canDelete)
            testButton.Enable(True)

        else: # no account

            delButton.Enable(False)
            testButton.Enable(False)
            self.__SwapDetailPanel(-1)


    def __PopulateAccountsList(self, account):
        """ Find all account items and put them in the list; also build
            up a data structure with the applicable attribute values we'll
            be editing. If account is passed in, show its details. """

        # Make sure we're sync'ed with any changes other threads have made
        self.rv.refresh()
        accountIndex = 0 # which account to select first
        accounts = []

        if False:
            #add the default accounts first
            for item in self.getDefaultAccounts():
                accounts.append(item)

        for cls in (Mail.IMAPAccount, Mail.POPAccount, Mail.SMTPAccount):
            for item in cls.iterItems(self.rv):
                if item.isActive and hasattr(item, 'displayName'):
                    accounts.append(item)

        for item in sharing.SharingAccount.iterItems(self.rv):
            if hasattr(item, 'displayName'):
                accounts.append(item)

        i = 0

        accounts = sorted(accounts, key = lambda x: x.displayName.lower())
        for item in accounts:
            # If an account was passed in, remember its index so we can
            # select it
            if account == item:
                accountIndex = i

            # 'values' is a dict whose keys are the field names defined in
            # the panelsInfo data structure above
            values = { }

            for (field, desc) in \
             self.panelsInfo[item.accountType]['fields'].iteritems():
                if desc['type'] == 'currentPointer':
                    # See if this item is the current item for the given
                    # pointer name, storing a boolean.
                    ns = schema.ns(desc['ns'], self.rv)
                    ref = getattr(ns, desc['pointer'])
                    setting = (ref.item == item)

                elif desc['type'] == 'itemRef':
                    # Store an itemRef as a UUID
                    try:
                        setting = getattr(item, desc['attr']).itsUUID
                    except AttributeError:
                        setting = None

                elif desc['type'] == 'chandlerFolders':
                    if item.accountProtocol == "IMAP":
                        setting = {"hasFolders": self.hasChandlerFolders(item)}
                    else:
                        setting = {}

                elif desc['type'] == 'password':
                    try:
                        pw = item.password
                    except AttributeError:
                        setting = u''
                    else:
                        try:
                            setting = waitForDeferred(pw.decryptPassword(window=self))
                        except password.NoMasterPassword:
                            return False
                else:
                    # Otherwise store a literal
                    try:
                        setting = getattr(item, desc['attr'])
                    except AttributeError:
                        try:
                            setting = desc['default']
                        except KeyError:
                            setting = DEFAULTS[desc['type']]

                values[field] = setting

            # Store a dictionary for this account, including the following:
            self.data.append( { "item"   : item.itsUUID,
                                "values" : values,
                                "type"   : item.accountType,
                                "protocol": item.accountProtocol } )


            self.accountsList.Append(item.displayName)

            i += 1
            # End of account loop

        if i > 0:
            self.selectAccount(accountIndex)
        else:
            self.selectAccount(-1)

        return True

    def __ApplyChanges(self):
        """ Take the data from the list and apply the values to the items. """

        # First store the current form values to the data structure
        if self.currentIndex is not None:
            self.__StoreFormData(self.currentPanelType,
                                 self.currentPanel,
                                 self.data[self.currentIndex]['values'])

        if DEBUG:
            counter = 0

        for account in self.data:
            uuid = account['item']

            if uuid:
                # We already have an account item created
                item = self.rv.findUUID(account['item'])

            else:
                # We need to create an account item

                if account['protocol'] == "IMAP":
                    item = Mail.IMAPAccount(itsView=self.rv)

                elif account['protocol'] == "POP":
                    item = Mail.POPAccount(itsView=self.rv)

                elif account['protocol'] == "SMTP":
                    item = Mail.SMTPAccount(itsView=self.rv)

                elif account['protocol'] == "WebDAV":
                    item = sharing.WebDAVAccount(itsView=self.rv)

                elif account['protocol'] == "Morsecode":
                    item = sharing.CosmoAccount(itsView=self.rv)

            if not hasattr(item, 'password'):
                item.password = password.Password(itsView=self.rv,
                                                  itsParent=item)

            values = account['values']
            panel = self.panelsInfo[account['type']]

            if panel.has_key("saveHandler"):
                # Call custom save handler; if None returned, we don't do
                # any more processing of that account within this loop
                item = panel["saveHandler"](item, panel['fields'], values)

            if item is not None:
                if DEBUG:
                    # This stores the account which could have
                    # changed based on the results of the
                    # saveHandler to the data list.
                    # This info is only needed for
                    # debugging account saving.
                    self.data[counter]['item'] = item.itsUUID
                    counter += 1

                # Process each field defined in the PANEL data structure;
                # applying the values to the appropriate attributes:

                for (field, desc) in panel['fields'].iteritems():

                    if desc['type'] == 'currentPointer':
                        # If this value is True, make this item current:
                        if values[field]:
                            ns = schema.ns(desc['ns'], self.rv)
                            ref = getattr(ns, desc['pointer'])
                            ref.item = item

                    elif desc['type'] == 'itemRef':
                        # Find the item for this UUID and assign the itemref:
                        if values[field]:
                            setattr(item, desc['attr'],
                                    self.rv.findUUID(values[field]))

                    elif desc['type'] == 'chandlerFolders':
                        if values['INCOMING_PROTOCOL'] != "IMAP":
                            continue

                        action = values[field].get("action", None)

                        if action == "ADD" and not \
                           self.hasChandlerFolders(item):
                            folderChanges = values[field]["folderChanges"]
                            self.updateChandlerFolders(item, *folderChanges)

                        elif action == "REMOVE" and \
                            self.hasChandlerFolders(item):
                            folderChanges = values[field]["folderChanges"]
                            self.updateChandlerFolders(item, *folderChanges)

                    elif desc['type'] == 'password':
                        try:
                            waitForDeferred(item.password.encryptPassword(values[field], window=self))
                        except password.NoMasterPassword:
                            pass # XXX Passwords will not be updated unless master password is provided, should we tell the user/ask again?
                                
                    else:
                        # Otherwise, make the literal assignment:
                        try:
                            val = values[field]

                            if val is None:
                                # wx controls require unicode
                                # or str values and will raise an
                                # error if passed None
                                val = u""

                            setattr(item, desc['attr'], val)
                        except AttributeError:
                            pass

    def __ApplyDeletions(self):
        # Since we don't delete items right away, we need to do it here:

        for data in self.deletions:
            uuid = data['item']

            if uuid:
                item = self.rv.findUUID(uuid)

                # Remove any folders in the IMAPAccount
                folders = getattr(item, "folders", None)

                if folders:
                    for folder in folders:
                        folders.remove(folder)
                        folder.delete()

                if hasattr(item, 'password'):
                    item.password.delete()
                item.delete(recursive=True)

    def __ApplyCancellations(self):
        if self.currentIndex is not None:
            self.__StoreFormData(self.currentPanelType,
                                 self.currentPanel,
                                 self.data[self.currentIndex]['values'])

        # The only thing we need to do on Cancel is to remove any account items
        # we created this session:

        for account in self.data:
            if account['type'] == "INCOMING":
                #If there are pending changes on Chandler IMAP Folders
                # that have already been carried out on the server then
                # we need to store those changed values even on a cancel
                # since the operation was already performed.

                values = account['values']

                if values['INCOMING_PROTOCOL'] != "IMAP":
                    continue

                item = self.rv.findUUID(account['item'])

                action = values['INCOMING_FOLDERS'].get("action", None)

                if action == "ADD" and not self.hasChandlerFolders(item):
                    folderChanges = values['INCOMING_FOLDERS']["folderChanges"]
                    self.updateChandlerFolders(item, *folderChanges)

                elif action == "REMOVE" and self.hasChandlerFolders(item):
                    folderChanges = values['INCOMING_FOLDERS']["folderChanges"]
                    self.updateChandlerFolders(item, *folderChanges)

        for item in list(self.creations):
            if hasattr(item, 'password'):
                item.password.delete()
            item.delete(recursive=True)


    def __Validate(self):
        # Call any custom validation handlers that might be defined

        # First store the current form values to the data structure
        if self.currentIndex is not None:
            self.__StoreFormData(self.currentPanelType, self.currentPanel,
                self.data[self.currentIndex]['values'])

        i = 0

        for account in self.data:

            uuid = account['item']

            if uuid:
                item = self.rv.findUUID(uuid)

            else:
                item = None

            values = account['values']
            panel = self.panelsInfo[account['type']]

            if panel.has_key("validationHandler"):

                invalidMessage = panel["validationHandler"](item,
                    panel['fields'], values)

                if invalidMessage:
                    # Show the invalid panel
                    self.selectAccount(i)
                    alertError(invalidMessage, self)
                    return False

            i += 1

        return True


    def __GetIndexDisplayName(self, index):
        # Each panel type has a field that is designated the displayName; this
        # method determines which field is the displayName, then gets the value

        data = self.data[self.currentIndex]
        accountType = data['type']
        panel = self.panelsInfo[accountType]
        values = data['values']
        item = self.rv.findUUID(data['item'])
        return values[panel["displayName"]]


    def __SwapDetailPanel(self, index):
        """ Given an index into the account list, store the current panel's
            (if any) contents to the data list, destroy current panel, determine
            type of panel to pull in, load it, populate it. """

        if index == self.currentIndex: return

        if self.currentIndex != None:
            # Get current form data and tuck it away
            self.__StoreFormData(self.currentPanelType, self.currentPanel,
             self.data[self.currentIndex]['values'])

            self.accountsList.SetString(self.currentIndex,
                self.__GetIndexDisplayName(self.currentIndex))

        if self.currentPanel:
            self.innerSizer.Detach(self.currentPanel)
            self.currentPanel.Hide()

        if index == -1:
            # show the default panel
            self.innerSizer.Add(self.defaultPanel, 0, wx.ALIGN_TOP|wx.ALL,
                                self.getPlatformBorderSize())
            self.defaultPanel.Show()
            self.currentPanel = self.defaultPanel
            self.resizeLayout()
            return

        self.currentIndex = index
        self.currentPanelType = self.data[index]['type']
        self.currentPanel = self.panels[self.currentPanelType]


        init = self.panelsInfo[self.currentPanelType].get("init", None)

        self.__FetchFormData(self.currentPanelType, self.currentPanel,
                             self.data[index]['values'])

        if init:
            cb = getattr(self, init, None)
            cb and cb()

        self.innerSizer.Add(self.currentPanel, 0, wx.ALIGN_TOP|wx.ALL,
                            self.getPlatformBorderSize())

        self.currentPanel.Show()

        # When a text field receives focus, call the handler.
        # When an exclusive radio button is clicked, call another handler.

        for field in self.panelsInfo[self.currentPanelType]['fields'].keys():

            fieldInfo = self.panelsInfo[self.currentPanelType]['fields'][field]

            # This enables the clicking of a radio button to affect the value
            # of another field.  In this case, the OnLinkedControl( ) method
            # will get called.
            if fieldInfo['type'] == "radioEnumeration":
                linkedTo = fieldInfo.get('linkedTo', None)
                if linkedTo is not None:
                    for (button, value) in fieldInfo['buttons'].iteritems():
                        control = wx.xrc.XRCCTRL(self.currentPanel, button)
                        wx.EVT_RADIOBUTTON(control, control.GetId(),
                                           self.OnLinkedControl)
                continue

            control = wx.xrc.XRCCTRL(self.currentPanel, field)

            if isinstance(control, wx.TextCtrl):
                wx.EVT_SET_FOCUS(control, self.OnFocusGained)
                
                killFocusCallback = fieldInfo.get('killFocusCallback', None)
                if killFocusCallback is not None:
                    wx.EVT_KILL_FOCUS(control, killFocusCallback)

            elif isinstance(control, wx.RadioButton):
                # Set up the callback for an "exclusive" radio button, i.e.,
                # one who when checked within one account will get unchecked
                # in all other accounts
                if fieldInfo.get('exclusive', False):
                    try:
                        # On GTK if you want to have a radio button which can
                        # be set to False, you really need to create a second
                        # radio button and set that guy's value to True, thus
                        # setting the visible button to False:
                        hidden = wx.xrc.XRCCTRL(self.currentPanel,
                                                "%s_HIDDEN" % field)
                        hidden.Hide()
                    except:
                        pass
                    wx.EVT_RADIOBUTTON(control,
                                       control.GetId(),
                                       self.OnExclusiveRadioButton)

            elif isinstance(control, wx.CheckBox):
                # This allows a checkbox to affect the value of another field
                linkedTo = fieldInfo.get('linkedTo', None)
                if linkedTo is not None:
                    wx.EVT_CHECKBOX(control,
                                    control.GetId(),
                                    self.OnLinkedControl)

        # Hook up any other callbacks not tied to any fields, such as the
        # account testing buttons:
        for callbackReg in self.panelsInfo[self.currentPanelType].get(
            'callbacks', ()):
            self.Bind(wx.EVT_BUTTON,
                      getattr(self, callbackReg[1]),
                      id=wx.xrc.XRCID(callbackReg[0]))

        for messageWidget in self.currentMessages:
            messageWidget.Hide()

        self.currentMessages = []

        for message in self.panelsInfo[self.currentPanelType].get('messages',
            ()):
            messageWidget = wx.xrc.XRCCTRL(self.messagesPanel, message)
            messageWidget.Show()

            self.currentMessages.append(messageWidget)

        self.resizeLayout()


    def __StoreFormData(self, panelType, panel, data):
        # Store data from the wx widgets into the "data" dictionary

        for field in self.panelsInfo[panelType]['fields'].keys():

            fieldInfo = self.panelsInfo[panelType]['fields'][field]
            valueType = fieldInfo['type']
            valueRequired = fieldInfo.get('required', False)

            if fieldInfo['type'] == 'radioEnumeration':
                # A radio button group is handled differently, since there
                # are multiple wx controls controlling a single attribute.
                for (button, value) in fieldInfo['buttons'].iteritems():
                    control = wx.xrc.XRCCTRL(panel, button)
                    if control.GetValue() == True:
                        data[field] = value
                        break
                continue

            control = wx.xrc.XRCCTRL(panel, field)

            # Handle password
            if valueType == "password":
                val = control.GetValue().strip()
                if valueRequired and not val:
                    continue

            # Handle strings:
            if valueType == "string":
                val = control.GetValue().strip()
                if valueRequired and not val:
                    continue

            # Handle booleans:
            elif valueType == "boolean":
                val = (control.GetValue() == True)

            # Handle current pointers, which are stored as booleans:
            elif valueType == "currentPointer":
                val = (control.GetValue() == True)

            # Handle itemrefs, which are stored as UUIDs:
            elif valueType == "itemRef":
                index = control.GetSelection()
                if index == -1:
                    val = None
                else:
                    val = control.GetClientData(index)

            elif valueType == "chandlerFolders":
                # The action and folderChanges have
                # already been stored via callbacks
                # so do not do anything here
                continue

            elif valueType == "choice" or \
                 valueType == "protocolChoice":
                index = control.GetSelection()

                if index == -1:
                    val = None
                elif valueType == "protocolChoice":
                    val = index and "POP" or "IMAP"
                else:
                    val = control.GetString(index)

            # Handle integers:
            elif valueType == "integer":
                try:
                    val = int(control.GetValue().strip())
                except:
                    # Skip if not valid
                    continue

            data[field] = val


    def __FetchFormData(self, panelType, panel, data):
        # Pull data out of the "data" dictionary and stick it into the widgets:

        for field in self.panelsInfo[panelType]['fields'].keys():

            fieldInfo = self.panelsInfo[panelType]['fields'][field]

            if fieldInfo['type'] == 'radioEnumeration':
                # a radio button group is handled differently, since there
                # are multiple wx controls controlling a single attribute.
                for (button, value) in fieldInfo['buttons'].iteritems():
                    if value == data[field]:
                        control = wx.xrc.XRCCTRL(panel, button)
                        control.SetValue(True)
                        break
                continue

            control = wx.xrc.XRCCTRL(panel, field)

            valueType = self.panelsInfo[panelType]['fields'][field]['type']

            # Handle strings:
            if valueType in ("string", "password"):
                # The control can not accept a None value
                val = data[field] and data[field] or u""

                control.SetValue(val)

            # Handle booleans:
            elif valueType == "boolean":
                control.SetValue(data[field])

            # Handle current pointers, which are stored as booleans:
            elif valueType == "currentPointer":
                try:
                    # On GTK if you want to have a radio button which can
                    # be set to False, you really need to create a second
                    # radio button and set that guy's value to True, thus
                    # setting the visible button to False:
                    if data[field]:
                        control.SetValue(True)
                    else:
                        hidden = wx.xrc.XRCCTRL(panel, "%s_HIDDEN" % field)
                        hidden.SetValue(True)
                except:
                    pass

            elif valueType == "choice":
                pos = control.FindString(data[field])

                if pos != wx.NOT_FOUND:
                    control.SetSelection(pos)

            elif valueType == "protocolChoice":
                if data[field] == "IMAP":
                    pos = 0
                else:
                    pos = 1

                control.SetSelection(pos)


            elif valueType == "chandlerFolders":
                if data["INCOMING_PROTOCOL"] == "IMAP":
                    hasFolders = data[field].get("hasFolders", False)
                    data['INCOMING_FOLDERS']['create'] = not hasFolders
                    control.SetLabel(self.getButtonVerbage(hasFolders))
                    control.GetContainingSizer().Layout()
                else:
                    control.SetLabel(CREATE_TEXT)
                    control.GetContainingSizer().Layout()


            # Handle itemrefs, which are stored as UUIDs.  We need to find
            # all items of the kind specified in the PANEL, filtering out those
            # which have been marked for deletion, or are inactive.
            elif valueType == "itemRef":
                items = []
                count = 0
                index = -1
                uuid = data[field]
                kindClass = self.panelsInfo[panelType]['fields'][field]['kind']
                for item in kindClass.iterItems(self.rv):
                    deleted = False
                    for accountData in self.deletions:
                        if accountData['item'] == item.itsUUID:
                            deleted = True
                            break

                    if item.isActive and not deleted:
                        items.append(item)
                        if item.itsUUID == uuid:
                            index = count
                        count += 1

                control.Clear()

                for item in items:
                    # Add items to the dropdown list...

                    # ...however we need to grab displayName from the form
                    # data rather than from the item (as long as it's an item
                    # that's being edited in the dialog).  If the item doesn't
                    # appear in self.data, then it's an item that isn't being
                    # edited by the dialog and therefore we can ask it directly
                    # for its displayName:

                    displayName = item.displayName
                    for accountData in self.data:
                        if item.itsUUID == accountData['item']:
                            displayNameField = \
                                self.panelsInfo[item.accountType]['displayName']
                            displayName = \
                                accountData['values'][displayNameField]
                            break

                    newIndex = control.Append(displayName)
                    control.SetClientData(newIndex, item.itsUUID)

                if index != -1:
                    control.SetSelection(index)

            # Handle integers:
            elif valueType == "integer":
                control.SetValue(str(data[field]))



    def OnOk(self, evt):
        if self.__Validate():
            self.__ApplyChanges()
            self.__ApplyDeletions()

            if self.IsModal():
                self.EndModal(True)

            self.rv.commit()

            if DEBUG:
                self.debugAccountSaving()

            #Adding a recalulation here fixes a bug
            # where the recal method was getting called
            # for new mail accounts before the values
            # in the PANEL had been assigned to the
            # account item.
            #
            # This was resulting in account.isSetUp()
            # returning False.
            Mail._recalculateMeEmailAddresses(self.rv)

            Globals.mailService.refreshMailServiceCache()


            # Look for handler classes registered for the account dialog
            handlers = [ep.load() for ep in
                iter_entry_points('chandler.account_dialog_handlers')]
            for handler in handlers:
                try:
                    handler().onOk(self.rv)
                except:
                    logger.exception("Error calling account dialog handler")


            # TODO: change the following code to use the above endpoint:

            # Initiate a sharing sync to pick up previously published
            # collections
            if (Globals.options.catch != 'tests' and
                sharing.getAutoSyncInterval(self.rv) is not None):
                sharing.scheduleNow(self.rv)

            self.Destroy()

    def debugAccountSaving(self):
        buf = ["\n"]
        ns_pim = schema.ns('osaf.pim', self.rv)
        sharing_ns = schema.ns('osaf.sharing', self.rv)

        currentOutgoing = getattr(ns_pim.currentOutgoingAccount, "item", None)
        currentIncoming = getattr(ns_pim.currentIncomingAccount, "item", None)

        for account in self.data:
            item = self.rv.findUUID(account['item'])

            buf.append(item.displayName)
            buf.append("=" * 35)
            buf.append("host: %s" % item.host)
            buf.append("port: %s" % item.port)
            buf.append("username: %s" % item.username)
            buf.append("password: %s" % waitForDeferred(
                item.password.decryptPassword(window=self)))

            if item.accountType in ("SHARING_DAV", "SHARING_MORSECODE",
                "SHARING_HUB"):
                buf.append("useSSL: %s" % item.useSSL)
                buf.append("path: %s" % item.path)


            elif item.accountType == "INCOMING":
                buf.append("protocol %s" % item.accountProtocol)
                buf.append("security: %s" % item.connectionSecurity)
                buf.append("name: %s" % getattr(item, "fullName", ""))
                buf.append("email: %s" % getattr(item, "emailAddress", ""))

                folders = getattr(item, "folders", None)

                if folders:
                    buf.append("\nFOLDERS:")

                    for folder in folders:
                        buf.append("\tname: %s" % folder.displayName)
                        buf.append("\tIMAP name: %s" % folder.folderName)
                        buf.append("\ttype: %s" % folder.folderType)

                if item == currentIncoming:
                    buf.append("CURRENT: True")

            elif item.accountType == "OUTGOING":
                buf.append("security: %s" % item.connectionSecurity)
                buf.append("useAuth: %s" % item.useAuth)
                buf.append("name: %s" % getattr(item, "fullName", ""))
                buf.append("email: %s" % getattr(item, "emailAddress", ""))

                if item == currentOutgoing:
                    buf.append("CURRENT: True")

            buf.append("\n")

        print (u"\n".join(buf)).encode("utf-8")

    def OnCancel(self, evt):
        self.__ApplyCancellations()
        self.rv.commit()
        if self.IsModal():
            self.EndModal(False)
        self.Destroy()

    def OnIncomingFolders(self, evt):
        if not Globals.mailService.isOnline():
            return alertOffline(self)

        if not self.incomingAccountValid():
            return

        data = self.data[self.currentIndex]['values']

        create  = data['INCOMING_FOLDERS']['create']
        account = self.getIncomingAccount()
        if account is None:
            return

        if create:
            config = showConfigureDialog(CREATE_FOLDERS_TITLE,
                                  CREATE_FOLDERS % {
                                    "host": account.host,
                                    "ChandlerMailFolder": constants.CHANDLER_MAIL_FOLDER,
                                    "ChandlerTasksFolder": constants.CHANDLER_TASKS_FOLDER,
                                    "ChandlerStarredFolder": constants.CHANDLER_STARRED_FOLDER,
                                    "ChandlerEventsFolder": constants.CHANDLER_EVENTS_FOLDER,
                                   },
                                  self)

            if config:
                ChandlerIMAPFoldersDialog(self, account, self.OnFolderCreation)
        else:
            yes = showYesNoDialog(REMOVE_FOLDERS_TITLE,
                                  REMOVE_FOLDERS % {
                                    "host": account.host,
                                    "ChandlerMailFolder": constants.CHANDLER_MAIL_FOLDER,
                                    "ChandlerStarredFolder": constants.CHANDLER_STARRED_FOLDER,
                                    "ChandlerEventsFolder": constants.CHANDLER_EVENTS_FOLDER,
                                   },
                                  self)

            if yes:
                RemoveChandlerIMAPFoldersDialog(self, account,
                    self.OnFolderRemoval)

    def OnFolderCreation(self, result):
        statusCode, value = result

        # Failure
        if statusCode == 0:
            # Since no folders created just return
            return

        button = wx.xrc.XRCCTRL(self.currentPanel, "INCOMING_FOLDERS")

        # It worked so set the text to remove folders
        button.SetLabel(REMOVE_TEXT)
        button.GetContainingSizer().Layout()

        data = self.data[self.currentIndex]['values']

        data['INCOMING_FOLDERS']['create'] = False
        data['INCOMING_FOLDERS']['action'] = "ADD"
        data['INCOMING_FOLDERS']['folderChanges'] = value
        data['INCOMING_FOLDERS']['hasFolders'] = True


    def OnFolderRemoval(self, result):
        statusCode, value = result
        button = wx.xrc.XRCCTRL(self.currentPanel, "INCOMING_FOLDERS")

        # Failure
        if statusCode == 0:
            # Since folders still exist just return
            return

        # It worked so set the checkbox to false
        button.SetLabel(CREATE_TEXT)
        button.GetContainingSizer().Layout()

        data = self.data[self.currentIndex]['values']

        data['INCOMING_FOLDERS']['create'] = True
        data['INCOMING_FOLDERS']['action'] = "REMOVE"
        data['INCOMING_FOLDERS']['folderChanges'] = value
        data['INCOMING_FOLDERS']['hasFolders'] = False

    def OnAutoDiscovery(self, account):
        if account.accountType == "INCOMING":
            proto = wx.xrc.XRCCTRL(self.currentPanel, "INCOMING_PROTOCOL")
            if account.accountProtocol == "IMAP":
                proto.SetSelection(0)
            else:
                proto.SetSelection(1)

            port = wx.xrc.XRCCTRL(self.currentPanel, "INCOMING_PORT")
            port.SetValue(str(account.port))

            fields = self.panelsInfo[self.currentPanelType]['fields']
            fieldInfo = fields['INCOMING_SECURE']

            for (button, value) in fieldInfo['buttons'].iteritems():
                if account.connectionSecurity == value:
                    control = wx.xrc.XRCCTRL(self.currentPanel, button)
                    control.SetValue(True)
                    break

            self.toggleIncomingFolders(account.accountProtocol=="IMAP")

        elif account.accountType == "OUTGOING":
            port = wx.xrc.XRCCTRL(self.currentPanel, "OUTGOING_PORT")
            port.SetValue(str(account.port))

            fields = self.panelsInfo[self.currentPanelType]['fields']
            fieldInfo = fields['OUTGOING_SECURE']

            for (button, value) in fieldInfo['buttons'].iteritems():
                if account.connectionSecurity == value:
                    control = wx.xrc.XRCCTRL(self.currentPanel, button)
                    control.SetValue(True)
                    break
        else:
            # If this code is reached then there is a
            # bug which needs to be fixed.
            raise Exception("Internal Exception")

    def OnToggleIncomingProtocol(self, evt):
        proto = wx.xrc.XRCCTRL(self.currentPanel, "INCOMING_PROTOCOL")
        port = wx.xrc.XRCCTRL(self.currentPanel, "INCOMING_PORT")

        IMAP = proto.GetSelection() == 0

        fields = self.panelsInfo[self.currentPanelType]['fields']
        fieldInfo = fields['INCOMING_SECURE']

        connectionSecurity = None

        for (button, value) in fieldInfo['buttons'].iteritems():
            control = wx.xrc.XRCCTRL(self.currentPanel, button)
            if control.GetValue():
                connectionSecurity = value
                break

        linkedTo = fieldInfo.get('linkedTo', None)

        if linkedTo is not None:
            imapDict = linkedTo['protocols']["IMAP"][1]
            popDict  = linkedTo['protocols']["POP"][1]

        if IMAP:
            if port.GetValue() in popDict.values():
                port.SetValue(imapDict[connectionSecurity])

            data = self.data[self.currentIndex]['values']

            button = wx.xrc.XRCCTRL(self.currentPanel, "INCOMING_FOLDERS")
            hasFolders = data["INCOMING_FOLDERS"].get("hasFolders", False)
            data["INCOMING_FOLDERS"]["create"] = not hasFolders
            button.SetLabel(self.getButtonVerbage(hasFolders))
            button.GetContainingSizer().Layout()

        else:
            if port.GetValue() in imapDict.values():
                port.SetValue(popDict[connectionSecurity])

        self.toggleIncomingFolders(IMAP)


    def getButtonVerbage(self, hasFolders):
        if hasFolders:
            return REMOVE_TEXT
        return CREATE_TEXT

    def initIncomingPanel(self):
        self.toggleIncomingFolders(self.getIncomingProtocol() == "IMAP", False)

    def toggleIncomingFolders(self, show=True, resize=True):
        widgets = ("INCOMING_FOLDERS", "INCOMING_FOLDERS_VERBAGE",
                   "INCOMING_FOLDERS_VERBAGE2", "INCOMING_FOLDERS_BUFFER",
                   "INCOMING_FOLDERS_BUFFER2")

        for widgetName in widgets:
            widget = wx.xrc.XRCCTRL(self.currentPanel, widgetName)

            if show:
                widget.Show()
            else:
                widget.Hide()

        if resize:
            self.resizeLayout()


    def OnNewAccount(self, evt):
        selection = self.choiceNewType.GetSelection()
        if selection == 0:
            return

        accountType = self.choiceNewType.GetClientData(selection)
        self.choiceNewType.SetSelection(0)
        self.CreateNewAccount(accountType)


    def CreateNewAccount(self, accountType):

        panel = self.panelsInfo[accountType]

        cls = panel['class']
        item = cls(itsView=self.rv)
        newName = panel['fields'][panel['displayName']]['default']
        item.displayName = newName
        protocol = panel['protocol']

        self.creations.add(item)

        values = { }

        for (field, desc) in self.panelsInfo[accountType]['fields'].iteritems():

            if desc['type'] == 'currentPointer':
                setting = False

            elif desc['type'] == 'itemRef':
                setting = None

            elif desc['type'] == 'chandlerFolders':
                if protocol == "IMAP":
                    setting = {"hasFolders": self.hasChandlerFolders(item)}
                else:
                    setting = {}
            else:
                try:
                    setting = desc['default']
                except KeyError:
                    setting = DEFAULTS[desc['type']]

            values[field] = setting

        self.data.append( { "item" : item.itsUUID,
                            "values" : values,
                            "type" : accountType,
                            "protocol" : protocol,
                            "isNew" : True } )

        index = self.accountsList.Append(item.displayName)
        self.selectAccount(index)


    def getSelectedAccount(self):
        index = self.accountsList.GetSelection()
        return self.rv.findUUID(self.data[index]['item'])

    def OnDeleteAccount(self, evt):
        # First, make sure any values that have been modified in the form
        # are stored:
        if self.currentIndex != None:
            self.__StoreFormData(self.currentPanelType, self.currentPanel,
                                 self.data[self.currentIndex]['values'])

        index = self.accountsList.GetSelection()
        item = self.rv.findUUID(self.data[index]['item'])

        deleteHandler = self.panelsInfo[item.accountType].get('deleteHandler',
            None)
        if deleteHandler is None:
            canDelete = True
        else:
            canDelete = deleteHandler(item, self.data[index]['values'],
                self.data)

        if canDelete:
            self.deletions.append(self.data[index])
            del self.data[index]
            self.innerSizer.Detach(self.currentPanel)
            self.currentPanel.Hide()
            self.currentIndex = None
            self.selectAccount(-1)
            self.accountsList.Delete(index)
            for messageWidget in self.currentMessages:
                messageWidget.Hide()

            self.currentMessages = []

    def OnTestAccount(self, evt):
        account = self.getSelectedAccount()

        if account is None:
            # If this code is reached then there is a
            # bug which needs to be fixed.
            raise Exception("Internal Exception")

        if account.accountType == "INCOMING":
            self.OnTestIncoming()
        elif account.accountType  == "OUTGOING":
            self.OnTestOutgoing()
        elif account.accountType  == "SHARING_DAV":
            self.OnTestSharingDAV()
        elif account.accountType  == "SHARING_MORSECODE":
            self.OnTestSharingMorsecode()
        elif account.accountType  == "SHARING_HUB":
            self.OnTestSharingHub(account)
        else:
            # If this code is reached then there is a
            # bug which needs to be fixed.
            return alertError(_(u"This type of account does not support testing"), self)

    def OnIncomingDiscovery(self, evt):
        if not Globals.mailService.isOnline():
            return alertOffline(self)

        self.__StoreFormData(self.currentPanelType, self.currentPanel,
                             self.data[self.currentIndex]['values'])

        data = self.data[self.currentIndex]['values']

        host = data['INCOMING_SERVER']

        if len(host.strip()) == 0:
            s = wx.xrc.XRCCTRL(self.currentPanel, "INCOMING_SERVER")
            s.SetFocus()
            return alertError(HOST_REQUIRED, self)

        AutoDiscoveryDialog(self, host, False, self.rv, self.OnAutoDiscovery)

    def OnOutgoingDiscovery(self, evt):
        if not Globals.mailService.isOnline():
            return alertOffline(self)

        self.__StoreFormData(self.currentPanelType, self.currentPanel,
                             self.data[self.currentIndex]['values'])

        data = self.data[self.currentIndex]['values']

        host = data['OUTGOING_SERVER']

        if len(host.strip()) == 0:
            s = wx.xrc.XRCCTRL(self.currentPanel, "OUTGOING_SERVER")
            s.SetFocus()
            return alertError(HOST_REQUIRED, self)

        AutoDiscoveryDialog(self, host, True, self.rv, self.OnAutoDiscovery)

    def getIncomingAccount(self):
        self.__StoreFormData(self.currentPanelType, self.currentPanel,
                             self.data[self.currentIndex]['values'])

        data = self.data[self.currentIndex]['values']

        proto = data["INCOMING_PROTOCOL"]

        if proto == "IMAP":
            account = schema.ns('osaf.app', self.rv).TestIMAPAccount
        elif proto == "POP":
            account = schema.ns('osaf.app', self.rv).TestPOPAccount
        else:
            # If this code is reached then there is a
            # bug which needs to be fixed.
            raise Exception("Internal Exception")

        account.displayName = data['INCOMING_DESCRIPTION']
        account.host = data['INCOMING_SERVER']
        account.port = data['INCOMING_PORT']
        account.connectionSecurity = data['INCOMING_SECURE']
        account.username = data['INCOMING_USERNAME']
        try:
            waitForDeferred(account.password.encryptPassword(data['INCOMING_PASSWORD'], window=self))
        except password.NoMasterPassword:
            return None

        self.rv.commit()

        return account

    def incomingAccountValid(self):
        self.__StoreFormData(self.currentPanelType, self.currentPanel,
                             self.data[self.currentIndex]['values'])

        data = self.data[self.currentIndex]['values']

        host = data['INCOMING_SERVER']
        port = data['INCOMING_PORT']
        username = data['INCOMING_USERNAME']
        pw = data['INCOMING_PASSWORD']

        error = False

        if len(host.strip()) == 0 or \
           len(username.strip()) == 0 or \
           len(pw.strip()) == 0:

            error = True

        try:
            # Test that the port value is an integer
            int(port)
        except:
            error = True

        if error:
            alertError(FIELDS_REQUIRED, self)

        return not error

    def OnTestIncoming(self):
        if not Globals.mailService.isOnline():
            return alertOffline(self)

        if self.incomingAccountValid():
            account = self.getIncomingAccount()
            if account is not None:
                MailTestDialog(self, account)

    def outgoingAccountValid(self):
        self.__StoreFormData(self.currentPanelType, self.currentPanel,
                             self.data[self.currentIndex]['values'])

        data = self.data[self.currentIndex]['values']

        host = data['OUTGOING_SERVER']
        port = data['OUTGOING_PORT']
        useAuth = data['OUTGOING_USE_AUTH']

        error = False
        errorType = 0

        if len(host.strip()) == 0:
            error = True

        try:
            # Test that the port value is an integer
            int(port)
        except:
            error = True

        if useAuth:
            username = data['OUTGOING_USERNAME']
            pw = data['OUTGOING_PASSWORD']

            if len(username.strip()) == 0 or \
               len(pw.strip()) == 0:
                error = True
                errorType = 1

        if error:
            if errorType:
                alertError(FIELDS_REQUIRED, self)

            else:
                alertError(FIELDS_REQUIRED_ONE, self)

        return not error

    def OnTestOutgoing(self):
        if not Globals.mailService.isOnline():
            return alertOffline(self)

        if not self.outgoingAccountValid():
            return

        self.__StoreFormData(self.currentPanelType, self.currentPanel,
                             self.data[self.currentIndex]['values'])

        data = self.data[self.currentIndex]['values']

        account = schema.ns('osaf.app', self.rv).TestSMTPAccount
        account.displayName = data['OUTGOING_DESCRIPTION']
        account.host = data['OUTGOING_SERVER']
        account.port = data['OUTGOING_PORT']
        account.connectionSecurity = data['OUTGOING_SECURE']
        account.useAuth = data['OUTGOING_USE_AUTH']
        account.username = data['OUTGOING_USERNAME']
        try:
            waitForDeferred(account.password.encryptPassword(data['OUTGOING_PASSWORD'], window=self))
        except password.NoMasterPassword:
            return

        self.rv.commit()

        MailTestDialog(self, account)

    def OnTestSharingDAV(self):
        self.__StoreFormData(self.currentPanelType, self.currentPanel,
                             self.data[self.currentIndex]['values'])

        data = self.data[self.currentIndex]['values']

        displayName = data["DAV_DESCRIPTION"]
        host = data['DAV_SERVER']
        port = data['DAV_PORT']
        path = data['DAV_PATH']
        username = data['DAV_USERNAME']
        pw = data['DAV_PASSWORD']
        useSSL = data['DAV_USE_SSL']

        error = False

        if len(host.strip()) == 0 or \
           len(username.strip()) == 0 or \
           len(pw.strip()) == 0 or \
           len(path.strip()) == 0:

            error = True

        try:
            # Test that the port value is an integer
            int(port)
        except:
            error = True

        if error:
            return alertError(FIELDS_REQUIRED_TWO, self)

        SharingTestDialog(self, displayName, host, port, path, username,
                          pw, useSSL, self.rv)

    def OnTestSharingMorsecode(self):
        self.__StoreFormData(self.currentPanelType, self.currentPanel,
                             self.data[self.currentIndex]['values'])

        data = self.data[self.currentIndex]['values']

        displayName = data["MORSECODE_DESCRIPTION"]
        host = data['MORSECODE_SERVER']
        port = data['MORSECODE_PORT']
        path = data['MORSECODE_PATH']
        username = data['MORSECODE_USERNAME']
        pw = data['MORSECODE_PASSWORD']
        useSSL = data['MORSECODE_USE_SSL']

        error = False

        if len(host.strip()) == 0 or \
           len(username.strip()) == 0 or \
           len(pw.strip()) == 0 or \
           len(path.strip()) == 0:

            error = True

        try:
            # Test that the port value is an integer
            int(port)
        except:
            error = True

        if error:
            return alertError(FIELDS_REQUIRED_TWO, self)

        SharingTestDialog(self, displayName, host, port, path, username,
                          pw, useSSL, self.rv, morsecode=True)

    def OnTestSharingHub(self, account):
        self.__StoreFormData(self.currentPanelType, self.currentPanel,
                             self.data[self.currentIndex]['values'])

        data = self.data[self.currentIndex]['values']

        displayName = data["HUBSHARING_DESCRIPTION"]
        host = account.host
        port = account.port
        useSSL = account.useSSL
        path = account.path
        username = data['HUBSHARING_USERNAME']
        pw = data['HUBSHARING_PASSWORD']

        if len(username.strip()) == 0 or len(pw.strip()) == 0:
            return alertError(FIELDS_REQUIRED_THREE, self)

        SharingTestDialog(self, displayName, host, port, path, username,
                          pw, useSSL, self.rv, morsecode=True)

    def OnAccountSel(self, evt):
        # Huh? This is always False!
        # if not evt.IsSelection(): return

        sel = evt.GetSelection()
        self.selectAccount(sel)

    def OnFocusGained(self, evt):
        """ Select entire text field contents when focus is gained. """
        control = evt.GetEventObject()
        wx.CallAfter(control.SetSelection, -1, -1)

    def OnFocusLostIncomingEmail(self, evt):
        control = evt.GetEventObject()
        wx.CallAfter(self.incomingEmailChange, control.GetValue())

    def OnFocusLostOutgoingEmail(self, evt):
        control = evt.GetEventObject()
        wx.CallAfter(self.outgoingEmailChange, control.GetValue())

    def incomingEmailChange(self, email):
        try:
            username, domain = email.split('@')
        except ValueError:
            return
        if not domain:
            return
        
        entry = PREFILLED_INCOMING_EMAIL.get(domain, None)
        if entry is None:
            return
        
        server   = entry['server']
        port     = entry['port']
        useSSL   = entry['useSSL']
        protocol = entry['protocol']
        user     = entry['user']
            
        control = wx.xrc.XRCCTRL(self.currentPanel, 'INCOMING_SERVER')
        control.SetValue(server)

        if not user:
            username = email
        control = wx.xrc.XRCCTRL(self.currentPanel, 'INCOMING_USERNAME')
        control.SetValue(username)

        control = wx.xrc.XRCCTRL(self.currentPanel, 'INCOMING_PROTOCOL')
        control.SetStringSelection(protocol)

        fields = self.panelsInfo[self.currentPanelType]['fields']
        fieldInfo = fields['INCOMING_SECURE']

        for (button, value) in fieldInfo['buttons'].iteritems():
            if useSSL == value:
                control = wx.xrc.XRCCTRL(self.currentPanel, button)
                control.SetValue(True)
                break

        control = wx.xrc.XRCCTRL(self.currentPanel, 'INCOMING_PORT')
        control.SetValue(str(port))

    def outgoingEmailChange(self, email):
        try:
            username, domain = email.split('@')
        except ValueError:
            return
        if not domain:
            return
        
        entry = PREFILLED_OUTGOING_EMAIL.get(domain, None)
        if entry is None:
            return
        
        server = entry['server']
        port   = entry['port']
        useSSL = entry['useSSL']
        auth   = entry['auth']
        user   = entry['user']

        control = wx.xrc.XRCCTRL(self.currentPanel, 'OUTGOING_SERVER')
        control.SetValue(server)

        fields = self.panelsInfo[self.currentPanelType]['fields']
        fieldInfo = fields['OUTGOING_SECURE']

        for (button, value) in fieldInfo['buttons'].iteritems():
            if useSSL == value:
                control = wx.xrc.XRCCTRL(self.currentPanel, button)
                control.SetValue(True)
                break

        control = wx.xrc.XRCCTRL(self.currentPanel, 'OUTGOING_PORT')
        control.SetValue(str(port))

        if auth:
            control = wx.xrc.XRCCTRL(self.currentPanel, 'OUTGOING_USE_AUTH')
            control.SetValue(True)
                        
            if not user:
                username = email
            control = wx.xrc.XRCCTRL(self.currentPanel, 'OUTGOING_USERNAME')
            control.SetValue(username)

    def OnLinkedControl(self, evt):
        # A "linked" control has been clicked -- we need to modify the value
        # of the field this is linked to, but only if that field is already
        # set to one of the predefined values.

        control = evt.GetEventObject()

        # Determine current panel
        panel = self.panelsInfo[self.currentPanelType]

        # Scan through fields, seeing if this control corresponds to one
        # If marked as linkedTo, change the linked field
        ##        "linkedTo" : ("INCOMING_PORT", { True:993, False:143 } )
        for (field, fieldInfo) in panel['fields'].iteritems():

            ids = []
            if fieldInfo['type'] == 'radioEnumeration':
                for (button, fieldValue) in fieldInfo['buttons'].iteritems():
                    buttonId = wx.xrc.XmlResource.GetXRCID(button)
                    ids.append(buttonId)
                    if buttonId == control.GetId():
                        value = fieldValue
            else:
                ids = [wx.xrc.XmlResource.GetXRCID(field)]
                value = control.GetValue()

            if control.GetId() in ids:
                linkedTo = fieldInfo.get('linkedTo', None)
                if linkedTo is not None:
                    if type(linkedTo) == dict:
                        allValues = []
                        for (protocol, linkedFields) in linkedTo['protocols'].iteritems():
                            for v in linkedFields[1].values():
                                allValues.append(v)

                        cb = getattr(self, linkedTo['callback'])
                        res = cb()
                        linkedTo = linkedTo['protocols'][res]
                        linkedField = linkedTo[0]
                        linkedValues = linkedTo[1]
                    else:
                        linkedField = linkedTo[0]
                        linkedValues = linkedTo[1]
                        allValues = linkedValues.values()


                    linkedControl = wx.xrc.XRCCTRL(self.currentPanel,
                                                   linkedField)
                    if linkedControl.GetValue() in allValues:
                        linkedControl.SetValue(linkedValues[value])
                break


    def getIncomingProtocol(self):
        proto = wx.xrc.XRCCTRL(self.currentPanel, "INCOMING_PROTOCOL")
        return proto.GetSelection() and "POP" or "IMAP"

    def OnExclusiveRadioButton(self, evt):
        """ When an exclusive attribute (like default) is set on one account,
            set that attribute to False on all other accounts of the same kind.
        """
        control = evt.GetEventObject()

        # Determine current panel
        # Scan through fields, seeing if this control corresponds to one
        # If marked as exclusive, set all other accounts of this type to False
        panel = self.panelsInfo[self.currentPanelType]

        for (field, fieldInfo) in panel['fields'].iteritems():

            if wx.xrc.XmlResource.GetXRCID(field) == control.GetId():
                # This control matches

                # Double check it is an exclusive:
                if fieldInfo.get('exclusive', False):

                    # Set all other accounts sharing this current pointer to
                    # False:

                    index = 0
                    for accountData in self.data:

                        # Skip the current account
                        if index != self.currentIndex:

                            aPanel = self.panelsInfo[accountData['protocol']]
                            for (aField, aFieldInfo) in \
                                aPanel['fields'].iteritems():
                                if aFieldInfo.get('type') == 'currentPointer':
                                    if aFieldInfo.get('pointer', '') == \
                                        fieldInfo.get('pointer'):
                                            accountData['values'][aField] = \
                                                False
                        index += 1
                    break

    def resizeLayout(self):
        self.innerSizer.Layout()
        self.outerSizer.Layout()
        self.outerSizer.SetSizeHints(self)
        self.outerSizer.Fit(self)

    def hasChandlerFolders(self, account):
        found = 0

        for folder in account.folders:
            name = folder.displayName

            if name in constants.CURRENT_IMAP_FOLDERS:
                found += 1

        # All three folders are in the account.folders list
        return found == 3

    def updateChandlerFolders(self, account, completed, nameToPathDict):
        # Here, we update account.folders to match the operations that
        # are reported in completed.
        #
        # completed is a list of tuples. For folder creation, these
        # have the form:
        #
        #   ('created', name)
        #   ('renamed', oldName, newName)
        #   ('exists', name)
        #
        # while for deletion, they look like:
        #
        #   ('deleted', name)
        #   ('nonexistent', name)
        #
        # Here the "name" arguments are one of the names that appear in
        # constants.CHANDLER_xxx_FOLDER. The nameToPathDict argument
        # maps these names to IMAP folder paths on the server.
        #
        folderNameToType = {
            constants.CHANDLER_MAIL_FOLDER: "MAIL",
            constants.CHANDLER_STARRED_FOLDER: "TASK",
            constants.CHANDLER_EVENTS_FOLDER: "EVENT"
        }
        
        def getFolderByName(name):
            folderName = nameToPathDict[name]
            for folder in account.folders:
                if folder.folderName == folderName:
                    return folder
            # otherwise return None
                    
        def createOrUpdateFolder(folder, name):
            # if folder is None, we will create a new folder of the
            # correct type, server path, displayName. Otherwise, we
            # will change folder.
            changes = dict(
                displayName=name,
                folderName=nameToPathDict[name],
                type=folderNameToType[name]
            )
            if folder is None:
                folder = Mail.IMAPFolder(itsView=account.itsView, **changes)
                account.folders.append(folder)
            else:
                for key, value in changes.iteritems():
                    setattr(folder, key, value)
            return folder

        def deleteFolder(folder):
            # if folder is not None, remove it from account.folders and
            # also delete it from the repository.
            if folder is not None:
                account.folders.remove(folder)
                folder.delete(recursive=True)
        
        for t in completed:
            if t[0] in ('created', 'exists'):
                createOrUpdateFolder(getFolderByName(t[1]), t[1])
 
            elif t[0] == 'renamed':
                oldFolder = getFolderByName(t[1])
                newFolder = getFolderByName(t[2])

                if newFolder is not None:
                    createOrUpdateFolder(newFolder, t[2])
                    deleteFolder(oldFolder)
                else:
                    createOrUpdateFolder(oldFolder, t[2])
                
            elif t[0] in ('deleted', 'nonexistent'):
                oldFolder = getFolderByName(t[1])
                deleteFolder(oldFolder)
                    

def ShowAccountPreferencesDialog(account=None, rv=None, modal=True,
    create=None):

    # Parse the XRC resource file:
    xrcFile = os.path.join(Globals.chandlerDirectory,
     'application', 'dialogs', 'AccountPreferences.xrc')

    #[i18n] The wx XRC loading method is not able to handle raw 8bit paths
    #but can handle unicode
    xrcFile = unicode(xrcFile, sys.getfilesystemencoding())
    resources = wx.xrc.XmlResource(xrcFile)

    # Display the dialog:
    win = AccountPreferencesDialog(_(u"Account Preferences"),
     resources=resources, account=account, rv=rv, modal=modal, create=create)

    win.CenterOnParent()

    if modal:
        return win.ShowModal()
    else:
        win.Show()
        return win

def alertOffline(parent):
    showOKDialog(_(u"Mail Service Offline"), constants.TEST_OFFLINE, parent)

def alertError(msg, parent):
    showOKDialog(_(u"Account Preferences Error"), msg, parent)
