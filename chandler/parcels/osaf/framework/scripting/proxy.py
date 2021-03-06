#   Copyright (c) 2005-2008 Open Source Applications Foundation
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


import wx
from datetime import datetime
from application import schema
from osaf.framework.blocks import Block

def app_ns(view=None):
    if view is None:
        view = wx.GetApp().UIRepositoryView
    return AppProxy(view)

class EventTiming(dict):
    """
    dictionary of event timings for events that have
    been sent by CPIA Script since this dictionary was reset.
    Use clear() to reset timings.
    """
    def start_timer(self):
        return datetime.now()

    def end_timer(self, startTime, eventName):
        self.setdefault(eventName, []).append(datetime.now()-startTime)

    def get_strings(self):
        strTimings = {}
        for eName, timingList in self.iteritems():
            strList = []
            for timing in timingList:
                strList.append(str(timing))
            strTimings[eName] = strList
        return strTimings

    strings = property(get_strings)

class BlockProxy(object):
    """
    Proxy for a Block which is dynamically located by name.
    Since Blocks come and go in CPIA, this proxy helps
    provide a solid reference point for locating the
    currently rendered Block by name.
    """
    def __init__(self, blockName, app_ns):
        # create an attribute that looks up this block by name
        self.proxy = blockName
        self.app_ns = app_ns

    def __getattr__(self, attr):
        # if it's a block that's our child, return it
        child = getattr(self.app_ns, attr, None)
        if child is not None:
            return child
        
        # delegate the lookup to our View
        block = getattr(self.app_ns, self.proxy)
        return getattr(block, attr)

    def focus(self):
        block = getattr(self.app_ns, self.proxy)
        block.widget.SetFocus()


def postEvent(eventName, event, argDict=None, timing=None, **keys):
    # Post the supplied event, keeping track of the timing if requested.
    # Also, call Yield() on the application, so it gets some time during
    #   script execution.
    if argDict is None:
        argDict = {}
    try:
        argDict.update(keys)
    except AttributeError:
        # make sure the first parameter was a dictionary, or give a friendly error
        message = "BlockEvents may only have one positional parameter - a dict"
        raise AttributeError, message
    # remember timing information
    if timing is not None:
        startTime = timing.start_timer()
    # post the event
    result = Block.Block.post(event, argDict)
    # finish timing
    if timing is not None:
        timing.end_timer(startTime, eventName)
    # Next propagate notifications so the UI will match the data.
    # Then call Yeild to process an pending events
    wx.GetApp().propagateAsynchronousNotifications()
    wx.GetApp().Yield(True)

    return result


class RootProxy(BlockProxy):
    """ 
    Proxy to the Main View Root block. 
    Handles BlockEvents as methods.
    """

    def __init__(self, *args, **keys):
        super(RootProxy, self).__init__(*args, **keys)
        # our timing object
        self.timing = EventTiming()

    def post_script_event(self, eventName, event, argDict=None, timing=None,
                          **keys):
        return postEvent(eventName, event, argDict, timing, **keys)

    """
    We need to find the best BlockEvent at runtime on each invokation,
    because the BlockEvents come and go from the soup as UI portions
    are rendered and unrendered.  The best BlockEvent is the one copied
    into the soup and attached to rendered blocks that were also copied.
    """

    # Attributes that are BlockEvents get converted to functions
    # that invoke that event.
    # All other attributes are redirected to the root view.
    def __getattr__(self, attr):
        def scripted_blockEvent(argDict=None, **keys):
            # merge the named parameters, into the dictionary positional arg
            return self.post_script_event(attr, best, argDict, timing=self.timing, **keys)
        best = Block.Block.findBlockEventByName(attr)
        assert best is not False, "Your attribute can't be resolved"
        return scripted_blockEvent


class EventProxy(object):
    """
    A proxy modeled on the others that works with events defined in a given
    namespace such as the debug plugin.
    """

    def __init__(self, ns):
        self.ns = ns
        self.timing = EventTiming()

    def __getattr__(self, name):
        best = getattr(self.ns, name, None)
        assert best is not None, "Your attribute can't be resolved"

        def scripted_blockEvent(argDict=None, **keys):
            # merge the named parameters, into the dictionary positional arg
            return postEvent(name, best, argDict, timing=self.timing, **keys)

        return scripted_blockEvent


"""
Children to use for the Detail View.
This is a mapping of the form:
attribute_name: block_name
"""
class AppProxy(object):
    """
    Proxy for the app namespace, and the items you'd expect
    in that namespace.
    Provides easy access to useful attributes, like "view".
    Has attributes for its major children blocks, like
    "root", "sidebar", "calendar", etc.
    All BlockEvents are mapped onto methods in this class, 
    so you can say AppProxy.NewNote() to post the "NewNote"
    event.
    """
    def __init__(self, view):
        # our view attribute
        self.itsView = view
        # we proxy to the app name space
        self.app_ns = schema.ns('osaf.app', view)
        # view proxies
        self.root = RootProxy('MainViewRoot', self)
        self.appbar = BlockProxy('ApplicationBar', self)
        self.markupbar = BlockProxy('MarkupBar', self)
        self.sidebar = BlockProxy('Sidebar', self)
        self.calendar = BlockProxy('CalendarSummaryView', self)
        self.summary = BlockProxy('DashboardSummaryView', self)
        self.detail = BlockProxy('DetailRoot', self)

    def namespaceProxy(self, packageName):
        return EventProxy(schema.ns(packageName, self.view))

    def item_named(self, itemClass, itemName):
        for item in itemClass.iterItems(self.itsView):
            if self._name_of(item) == itemName:
                return item
        return None

    @staticmethod
    def _name_of(item):
        try:
            return item.displayName
        except AttributeError:
            pass
        try:
            return item.blockName
        except AttributeError:
            pass
        try:
            return item.itsName
        except AttributeError:
            pass
        return None

    # Attributes that are named blocks are found by name.
    # All other attributes are redirected to the app name space.
    def __getattr__(self, attr):
        block = Block.Block.findBlockByName(attr)
        if block is not None:
            return block
        else:
            return getattr(self.app_ns, attr)


