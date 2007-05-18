#   Copyright (c) 2007-2007 Open Source Applications Foundation
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

import wx, threading
from datetime import datetime, timedelta
from PyICU import DateFormat

from application import schema
from osaf import startup, sharing
from i18n import ChandlerMessageFactory as _m_


class CompactDialog(wx.Dialog):
    COUNTDOWN = 30

    def __init__(self, compact, lastCompact, versions):

        self.compact = compact
        self.compacting = None

        pre = wx.PreDialog()
        pre.Create(None, -1, _m_(u"Compact Repository"),
                   wx.DefaultPosition, wx.DefaultSize, wx.DEFAULT_DIALOG_STYLE)
        self.this = pre.this

        sizer = wx.BoxSizer(wx.VERTICAL)
        grid = wx.FlexGridSizer(3, 1, 2, 2)

        # compact message
        format = DateFormat.createDateInstance(DateFormat.kMedium)
        since = format.format(lastCompact)
        text = _m_(u"Your repository hasn't been compacted since %(since)s and has %(versions)d versions that should be compacted. This operation may take a while but improves performance.") %{ 'since': since, 'versions': versions }
        message = wx.StaticText(self, -1, text)
        message.Wrap(360)
        grid.Add(message, 0, wx.ALIGN_LEFT|wx.ALL, 3)

        # status message
        self.auto = _m_("Compacting will start automatically in %d seconds.")
        self.status = wx.StaticText(self, -1, self.auto %(self.COUNTDOWN))
        self.status.Wrap(360)

        grid.Add(self.status, 0, wx.ALIGN_LEFT|wx.ALL, 3)

        # progress bar
        self.gauge = wx.Gauge(self, size=(360, 15))
        grid.Add(self.gauge, 0, wx.ALIGN_CENTRE|wx.ALL, 5)

        sizer.Add(grid, 0, wx.GROW|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

        # now and later/cancel buttons
        grid = wx.GridSizer(1, 2, 2, 2)
        self.now = wx.Button(self, wx.ID_OK, _m_(u"Compact Now"))
        grid.Add(self.now, 0, wx.ALIGN_CENTRE|wx.ALL, 5)
        self.later = wx.Button(self, wx.ID_CANCEL, _m_(u"Compact Later"))
        grid.Add(self.later, 0, wx.ALIGN_CENTRE|wx.ALL, 5)

        sizer.Add(grid, 0, wx.GROW|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

        self.Bind(wx.EVT_BUTTON, self.onNow, id=wx.ID_OK)
        self.Bind(wx.EVT_BUTTON, self.onLater, id=wx.ID_CANCEL)
        
        self.SetSizer(sizer)
        self.SetAutoLayout(True)
        sizer.Fit(self)

    def onNow(self, event):
        try:
            self.condition.acquire()
            if self.compacting is None:
                self.compacting = True
                self.condition.notify()
                compact = True
            else:
                compact = False
        finally:
            self.condition.release()

        if compact:
            self.later.SetLabel(_m_(u'Cancel'))
            progressMessage = _m_(u'Compacting repository (stage %d)')
            stages = set()
            def progress(stage, percent):
                stages.add(stage)
                self.status.SetLabel(progressMessage %(len(stages)))
                self.gauge.SetValue(percent)
                wx.Yield()   # to enable updating and pressing 'Cancel'
                return self.compacting
            self.compact(progress)

        event.Skip(True)

    def onLater(self, event):
        try:
            self.condition.acquire()
            if self.compacting is None:
                self.compacting = False
                self.condition.notify()
            elif self.compacting is True:
                self.compacting = False
        finally:
            self.condition.release()

        event.Skip(True)

    def autoStart(self):

        countDown = self.COUNTDOWN
        while countDown:
            try:
                self.condition.acquire()
                self.condition.wait(1.0)
                if self.compacting is None:
                    countDown -= 1
                    if countDown > 0:
                        self.status.SetLabel(self.auto %(countDown))
                    else:
                        evt = wx.CommandEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED,
                                              wx.ID_OK)
                        evt.SetEventObject(self.now)
                        self.AddPendingEvent(evt)
                else:
                    break
            finally:
                self.condition.release()

    def ShowModal(self):

        self.condition = threading.Condition(threading.Lock())
        threading.Thread(target=self.autoStart).start()

        return super(CompactDialog, self).ShowModal()


class CompactTask(startup.DurableTask):
    """
    A DurableTask that compacts the repository once a week.

    The actual compaction happens inside main UI view and blocks.
    The user is presented with a dialog asking to confirm the compaction.
    If declined, the compaction is rescheduled for the next day.
    """

    REGULAR_INTERVAL = timedelta(days=7)
    RETRY_INTERVAL = timedelta(days=1)
    MIN_VERSIONS = 1

    lastCompact = schema.One(
        schema.DateTime,
        initialValue = datetime.now(),
    )

    lastVersion = schema.One(
        schema.Integer,
        initialValue = 0,
    )

    def __setup__(self):
        self.interval = CompactTask.REGULAR_INTERVAL

    # the target is the periodic task
    def getTarget(self):
        return self

    # the target is already constructed as self
    def __call__(self, task):
        return self

    def fork(self):
        return startup.fork_item(self, pruneSize=300, notify=False)

    def reschedule(self, interval=None):
        interval = super(CompactTask, self).reschedule(interval)
        self.itsView.logger.info("Repository compacting scheduled in %s",
                                 interval)
        return interval

    # target implementation
    def run(self, *args, **kwds):

        app = wx.GetApp()
        if app is None:   # no UI, retry later
            self.reschedule(CompactTask.RETRY_INTERVAL)
            self.itsView.commit()
        else:
            app.PostAsyncEvent(app.UIRepositoryView[self.itsUUID].compact)

        return False # bypass auto-rescheduling

    # compacting should block and be done in the MainThread
    # this method must run in the MainThread via app.PostAsyncEvent()
    def compact(self):

        view = self.itsView   # view is MainThread view
        view.refresh()

        toVersion = sharing.getOldestVersion(view) 
        versions = toVersion - self.lastVersion

        if versions < CompactTask.MIN_VERSIONS:  # nothing much to do
            view.logger.info("Only %d versions to compact, skipping", versions)
            self.reschedule(CompactTask.REGULAR_INTERVAL)
            view.commit()
            return

        from osaf.framework.blocks.Block import Block
        setStatusMessage = Block.findBlockByName('StatusBar').setStatusMessage
        self.compacted = None

        def compact(progress):
            try:
                counts = view.repository.compact(toVersion, progressFn=progress)
            except:
                view.logger.exception("while compacting repository")
                setStatusMessage(_m_(u"Compacting repository failed, see chandler.log"))
                self.compacted = False
            else:
                setStatusMessage(_m_(u'Reclaimed %d items, %d values, %d refs, %d index entries, %d names, %d lobs, %d blocks, %d lucene documents') %(counts))
                self.compacted = True

        dialog = CompactDialog(compact, self.lastCompact, versions)
        dialog.CenterOnScreen()
        cmd = dialog.ShowModal()
        dialog.Destroy()

        if cmd == wx.ID_OK:
            if self.compacted is True:
                self.lastVersion = int(toVersion)
                self.lastCompact = datetime.now()
                self.reschedule(CompactTask.REGULAR_INTERVAL)
            elif self.compacted is False:
                self.reschedule(CompactTask.RETRY_INTERVAL)
        else:
            self.reschedule(CompactTask.RETRY_INTERVAL)

        view.commit()