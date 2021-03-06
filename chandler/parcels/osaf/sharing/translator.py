#   Copyright (c) 2006-2008 Open Source Applications Foundation
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

from application import schema
from osaf import pim
from osaf.pim import mail
from osaf.sharing import (
    eim, model, shares, utility, accounts, conduits, cosmo, webdav_conduit,
    recordset_conduit, eimml, ootb
)
from utility import (splitUUID, fromICalendarDateTime, getDateUtilRRuleSet,
    code_to_triagestatus, triagestatus_to_code, getMasterAlias)

from itertools import chain
import os
import calendar
from email import Utils
from datetime import datetime, date, timedelta
from decimal import Decimal

from vobject.icalendar import (RecurringComponent, VEvent, timedeltaToString,
                               stringToDurations)
from osaf.timemachine import getNow
import osaf.pim.calendar.TimeZone as TimeZone
from osaf.pim.calendar.Calendar import Occurrence, EventStamp
from osaf.pim.calendar.Recurrence import RecurrenceRuleSet, RecurrenceRule
from dateutil.rrule import rrulestr
import dateutil
from osaf.framework.twisted import waitForDeferred
from osaf.pim.mail import EmailAddress
from osaf.usercollections import UserCollection
from osaf.mail.utils import (
    getEmptyDate, dataToBinary, binaryToData, RFC2822DateToDatetime
)
from osaf.pim.structs import ColorType
from osaf.framework.password import Password
from twisted.internet.defer import Deferred
import logging

__all__ = [
    'SharingTranslator',
    'DumpTranslator',
    'fromICalendarDuration',
    'toICalendarDateTime',
    'toICalendarDuration',
]


logger = logging.getLogger(__name__)

oneDay = timedelta(1)

noChangeOrInherit = (eim.NoChange, eim.Inherit)
emptyValues = (eim.NoChange, eim.Inherit, None)

class MessageState(object):
    FROM_ME, TO_ME, VIA_MAILSERVICE, IS_UPDATED, \
    FROM_EIMML, PREVIOUS_IN_RECIPIENTS = (1<<n for n in xrange(6))

def getEmailAddress(view, record):
    name, email = Utils.parseaddr(record)

    address = EmailAddress.getEmailAddress(view, email, name)
    return address


def addEmailAddresses(view, col, record):
    #, sep list
    addrs = record.split(u", ")

    for addr in addrs:
        name, email = Utils.parseaddr(addr)
        address = EmailAddress.getEmailAddress(view, email, name)
        col.append(address)


def with_nochange(value, converter, view=None):
    if value in (eim.NoChange, eim.Inherit):
        return value
    if view is None:
        return converter(value)
    else:
        return converter(value, view)

def datetimes_really_equal(dt1, dt2):
    return dt1.tzinfo == dt2.tzinfo and dt1 == dt2

def datetimeToDecimal(dt):

    tt = dt.utctimetuple()
    return Decimal(int(calendar.timegm(tt)))

def decimalToDatetime(view, decimal):
    naive = datetime.utcfromtimestamp(float(decimal))
    inUTC = naive.replace(tzinfo=view.tzinfo.UTC)
    # Convert to user's tz:
    return inUTC.astimezone(view.tzinfo.default)


### Event field conversion functions
# incomplete

def fromTransparency(val):
    out = val.lower()
    if out == 'cancelled':
        out = 'fyi'
    elif out not in ('confirmed', 'tentative'):
        out = 'confirmed'
    return out

def fromLocation(val, view):
    if not val: # None or ""
        return None
    return pim.Location.getLocation(view, val)



def fromICalendarDuration(text):
    return stringToDurations(text)[0]

def getTimeValues(view, record):
    """
    Extract start time and allDay/anyTime from a record.
    """
    dtstart  = record.dtstart
    # tolerate empty dtstart, treat it as Inherit, bug 9849
    if dtstart is None:
        dtstart = eim.Inherit
    start = None
    if dtstart not in noChangeOrInherit:
        start, allDay, anyTime = fromICalendarDateTime(view, dtstart)
    else:
        allDay = anyTime = start = dtstart
    # anyTime should be set to True if allDay is true, bug 9041
    anyTime = anyTime or allDay
    return (start, allDay, anyTime)

dateFormat = "%04d%02d%02d"
datetimeFormat = "%04d%02d%02dT%02d%02d%02d"
tzidFormat = ";TZID=%s"
allDayParameter = ";VALUE=DATE"
timedParameter  = ";VALUE=DATE-TIME"
anyTimeParameter = ";X-OSAF-ANYTIME=TRUE"

def formatDateTime(view, dt, allDay, anyTime):
    """Take a date or datetime, format it appropriately for EIM"""
    if allDay or anyTime:
        return dateFormat % dt.timetuple()[:3]
    else:
        base = datetimeFormat % dt.timetuple()[:6]
        if dt.tzinfo == view.tzinfo.UTC:
            return base + 'Z'
        else:
            return base

def toICalendarDateTime(view, dt_or_dtlist, allDay, anyTime=False):
    if isinstance(dt_or_dtlist, datetime):
        dtlist = [dt_or_dtlist]
    else:
        dtlist = dt_or_dtlist

    output = ''
    if allDay or anyTime:
        output += allDayParameter
        if anyTime and not allDay:
            output += anyTimeParameter
    else:
        isUTC = dtlist[0].tzinfo == view.tzinfo.UTC
        output += timedParameter
        tzinfo = TimeZone.olsonizeTzinfo(view, dtlist[0].tzinfo)
        if not isUTC and tzinfo != view.tzinfo.floating:
            output += tzidFormat % tzinfo.tzid

    output += ':'
    output += ','.join(formatDateTime(view, dt, allDay, anyTime)
                       for dt in dtlist)
    return output

def toICalendarDuration(delta, allDay=False):
    """
    The delta serialization format needs to match Cosmo exactly, so while
    vobject could do this, we'll want to be more picky about how exactly to
    serialize deltas.

    """
    if allDay:
        # all day events' actual duration always rounds up to the nearest day
        delta = timedelta(delta.days + 1)
    # but, for now, just use vobject, since we don't know how ical4j serializes
    # deltas yet
    return timedeltaToString(delta)

def getRecurrenceFields(event):
    """
    Take an event, return EIM strings for rrule, exrule, rdate, exdate, any
    or all of which may be None.

    """
    if event.occurrenceFor is not None:
        return (eim.Inherit, eim.Inherit, eim.Inherit, eim.Inherit)
    elif event.rruleset is None:
        return (None, None, None, None)

    view = event.itsItem.itsView

    vobject_event = RecurringComponent()
    vobject_event.behavior = VEvent
    start = event.startTime
    if event.allDay or event.anyTime:
        start = start.date()
    elif start.tzinfo is view.tzinfo.floating:
        start = start.replace(tzinfo=None)
    vobject_event.add('dtstart').value = start
    vobject_event.rruleset = event.createDateUtilFromRule(False, True, False)

    if hasattr(vobject_event, 'rrule'):
        rrules = vobject_event.rrule_list
        rrule = ':'.join(obj.serialize(lineLength=1000)[6:].strip() for obj in rrules)
    else:
        rrule = None

    if hasattr(vobject_event, 'exrule'):
        exrules = vobject_event.exrule_list
        exrule = ':'.join(obj.serialize(lineLength=1000)[7:].strip() for obj in exrules)
    else:
        exrule = None

    rdates = getattr(event.rruleset, 'rdates', [])
    if len(rdates) > 0:
        rdate = toICalendarDateTime(view, rdates, event.allDay, event.anyTime)
    else:
        rdate = None

    exdates = getattr(event.rruleset, 'exdates', [])
    if len(exdates) > 0:
        exdate = toICalendarDateTime(view, exdates, event.allDay, event.anyTime)
    else:
        exdate = None

    return rrule, exrule, rdate, exdate

def fixTimezoneOnModification(modification, tzinfo=None):
    """
    Set timezone on occurrence equal to master to correct for inherited
    UTC timezone values.

    If a tzinfo is passed in, convert recurrenceID (and possibly startTime)
    to that tzinfo, otherwise use the master's timezone.

    """
    mod = EventStamp(modification)
    view = mod.itsItem.itsView
    if tzinfo is None:
        master = mod.occurrenceFor
        assert master is not None
        tzinfo = EventStamp(master).effectiveStartTime.tzinfo
    if tzinfo != view.tzinfo.floating and tzinfo != view.tzinfo.UTC:
        recurrenceID = mod.recurrenceID
        if recurrenceID.tzinfo == view.tzinfo.UTC:
            mod.recurrenceID = recurrenceID.astimezone(tzinfo)
        if (mod.startTime.tzinfo == view.tzinfo.UTC and
            mod.startTime == recurrenceID):
            mod.startTime = mod.startTime.astimezone(tzinfo)    

def handleEmpty(item_or_stamp, attr):
    item = getattr(item_or_stamp, 'itsItem', item_or_stamp)
    if not isinstance(item_or_stamp, Occurrence):
        # type(some_Occurrence).attrname is a getter, not a descriptor, so
        # don't bother changing attr for stamps (it isn't needed anyway in
        # that case)
        attr = getattr(type(item_or_stamp), attr).name
    isOccurrence = isinstance(item, Occurrence)
    if not hasattr(item, attr):
        if not isOccurrence or hasattr(item.inheritFrom, attr):
            return None
        else:
            return eim.Inherit
    if not isOccurrence or item.hasLocalAttributeValue(attr):
        return getattr(item, attr)
    else:
        return eim.Inherit



def getAliasForItem(item_or_stamp):
    item = getattr(item_or_stamp, 'itsItem', item_or_stamp)
    view = item.itsView
    if isinstance(item, Occurrence):
        master = item.inheritFrom
        masterEvent = EventStamp(master)
        recurrenceID = EventStamp(item).recurrenceID
        # If recurrence-id isn't floating but the master is allDay or anyTime,
        # we have an off-rule modification, its recurrence-id shouldn't be
        # treated as date valued.
        dateValue = ((masterEvent.allDay or masterEvent.anyTime) and
                     recurrenceID.tzinfo == view.tzinfo.floating)
        if recurrenceID.tzinfo != view.tzinfo.floating:
            recurrenceID = recurrenceID.astimezone(view.tzinfo.UTC)
        recurrenceID = formatDateTime(view, recurrenceID, dateValue, dateValue)
        return master.itsUUID.str16() + ":" + recurrenceID
    else:
        return item.itsUUID.str16()


eim.add_converter(model.aliasableUUID, schema.Item, getAliasForItem)
eim.add_converter(model.aliasableUUID, pim.Stamp, getAliasForItem)






# Hopefully someday we will be able to remove the following converters:

# Cosmo will generate a value of None even if Chandler hasn't provided a
# value for event status, so treat None as NoChange
eim.add_converter(model.EventRecord.status, type(None), lambda x: eim.NoChange)

# Cosmo will generate a value of empty string even if Chandler hasn't provided
# a value for triage, so treat empty string as NoChange
def emptyToNoChange(s):
    return s if s else eim.NoChange
eim.add_converter(model.ItemRecord.triage, str, emptyToNoChange)
eim.add_converter(model.ItemRecord.triage, unicode, emptyToNoChange)

# Cosmo will generate a value of None for a zero-length duration, but Chandler
# uses "PT0S"
eim.add_converter(model.EventRecord.duration, type(None), lambda x: "PT0S")





class SharingTranslator(eim.Translator):

    URI = "cid:pim-translator@osaf.us"
    version = 1
    description = u"Translator for Chandler PIM items"

    obfuscation = False

    def startImport(self):
        super(SharingTranslator, self).startImport()
        tzprefs = schema.ns("osaf.pim", self.rv).TimezonePrefs
        self.promptForTimezoneAllowed = not tzprefs.showUI and tzprefs.showPrompt



    def resolve(self, cls, field, agreed, internal, external):
        # Return 1 for external to win, -1 for internal, 0 for no decision

        # In general, if there was no agreed state, and one side provides
        # a non-None value while the other side provides a None value, let
        # the non-None value automatically win
        if agreed == eim.NoChange or agreed == eim.Inherit:
            if not (internal and external):
                # Either one or neither have values, but not both
                return -1 if internal else 1

        # Resolve item record conflicts:
        if cls is model.ItemRecord:
            if field.name in ('createdOn', 'hasBeenSent', 'read', 'needsReply'):
                return -1 if internal else 1 # let the non-None value win

            elif field.name == 'triage':
                if external == eim.Inherit:
                    return -1 # internal wins
                if internal == eim.Inherit:
                    return 1  # external wins

                codeInt, tscInt, autoInt = internal.split(" ")
                codeExt, tscExt, autoExt = external.split(" ")
                if codeInt == codeExt:
                    # status is equal, let more recent tsc win
                    return -1 if (float(tscInt) < float(tscExt)) else 1

        if cls is model.EventRecord:
            if field.name == 'lastPastOccurrence':
                # handle "" or None
                if not external:
                    return -1
                elif not internal:
                    return 1
                else:
                    local    = fromICalendarDateTime(self.rv, internal)[0]
                    inbound  = fromICalendarDateTime(self.rv, external)[0]
                    return -1 if local > inbound else 1

        # Resolve note record conflicts:
        if cls is model.NoteRecord:
            if field.name in ('icalUid', 'icalProperties', 'icalParameters',
                'icalExtra'):
                return -1 if internal else 1 # let the non-None value win


        # Resolve mail record conflicts:
        if cls is model.MailMessageRecord:
            if field.name in ('messageId', 'headers', 'dateSent', 'inReplyTo',
                'references'):
                return -1 if internal else 1 # let the non-None value win

        return 0



    ignoreFields = {
        model.MailMessageRecord :
            ("fromAddress", "headers", "messageId", "inReplyTo", "references",
             "dateSent"),
        model.NoteRecord :
            ("icalExtra", "icalUid", "icalProperties", "icalParameters"),
    }

    def isMajorChange(self, diff):
        # Does this diff warrant moving to NOW and marking as Unread?

        for record in chain(diff.inclusions, diff.exclusions):
            if type(record) not in self.ignoreFields.keys():
                return True
            for field in record.__fields__:
                if (not isinstance(field, eim.key) and
                    record[field.offset] != eim.NoChange and
                    field.name not in self.ignoreFields[type(record)]):
                    return True

        return False



    def obfuscate(self, text):
        if text in (eim.Inherit, eim.NoChange):
            return text

        if text and getattr(self, "obfuscation", False):
            def lipsum(length):
                # Return some text that has properties real text would have.
                corpus = "Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum." 
                if length <= len(corpus):
                    return corpus[:length]
                # Need to generate some additional stuff...
                ret = corpus
                words = corpus.split()
                import random
                shuffler = random.Random(1) # fixed seed on purpose
                while True:
                    shuffler.shuffle(words)
                    ret += os.linesep + ' '.join(words)
                    if len(ret) >= length:
                        return ret[:length]

            return lipsum(len(text)) 
        else:
            return text

    def getUUIDForAlias(self, alias):
        if ':' not in alias:
            return alias

        uuid, recurrenceID = splitUUID(self.rv, alias)

        # find the occurrence and return itsUUID
        master = self.rv.findUUID(uuid)
        if master is not None and pim.has_stamp(master, pim.EventStamp):
            masterEvent = pim.EventStamp(master)
            occurrence = masterEvent.getExistingOccurrence(recurrenceID)
            if occurrence is not None:
                if self.getAliasForItem(occurrence) != alias:
                    # don't get fooled by getExistingOccurrence( ) which
                    # thinks that a floating tz matches a non-floater
                    # (related to bug 9207)
                    return None
                return occurrence.itsItem.itsUUID.str16()

        return None


    def getAliasForItem(self, item):
        return getAliasForItem(item)



    # ItemRecord -------------

    code_to_modaction = {
        100 : pim.Modification.edited,
        200 : pim.Modification.queued,
        300 : pim.Modification.sent,
        400 : pim.Modification.updated,
        500 : pim.Modification.created,
    }
    modaction_to_code = dict([[v, k] for k, v in code_to_modaction.items()])

    def deferredUUID(self, recurrence_aware_uuid, create=True):
        master_uuid, recurrenceID = splitUUID(self.rv, recurrence_aware_uuid)
        if recurrenceID is not None:
            d = self.deferredItem(master_uuid, EventStamp)
            @d.addCallback
            def get_occurrence(master):
                if getattr(master, 'rruleset', None) is None:
                    # add a dummy RecurrenceRuleSet so event methods treat
                    # the event as a master
                    master.rruleset = RecurrenceRuleSet(None, itsView=self.rv)
                    # Some event methods won't work if a master doesn't have
                    # a rruleset, but import_event's modification fixing needs
                    # to know if the real master's event has been processed
                    master.itsItem._fake = True
                occurrence = master.getRecurrenceID(recurrenceID)
                if occurrence is None:
                    if create:
                        occurrence = master._createOccurrence(recurrenceID)
                    else:
                        return None
                return occurrence.itsItem.itsUUID.str16()
            return d.addErrback(self.recordFailure)
        d = Deferred()
        d.callback(master_uuid)
        return d

    def deferredItem(self, uuid, itype=schema.Item, **attrs):
        """
        Override to handle special recurrenceID:uuid uuids.
        """
        if isinstance(uuid, basestring) and ':' in uuid:
            uuid = self.deferredUUID(uuid)
        else:
            # if adding a stamp to a master event, be sure to add it to all
            # occurrences
            if issubclass(itype, pim.Stamp):
                d = self.deferredItem(uuid, itype.targetType())
                @d.addCallback
                def add_stamp(item):
                    stamp = itype(item)
                    if not stamp.stamp_types or itype not in stamp.stamp_types:
                        if getattr(item, 'inheritFrom', None):
                            stamp.add()
                        else:
                            proxy = pim.CHANGE_ALL(item)
                            # hack to keep the proxy from setting lastModifiedBy
                            # to the wrong contact. really markEdited should be
                            # item.changeEditState, passing in a who parameter
                            # from the ModifiedByRecord
                            proxy.markEdited = lambda *args : None
                            itype(proxy).add()
                    for attr, val in attrs.items():
                        self.smart_setattr(val, stamp, attr)
                    return stamp # return value for deferreds
                return d.addErrback(self.recordFailure)

        return super(SharingTranslator, self).deferredItem(uuid, itype, **attrs)

    @model.ItemRecord.importer
    def import_item(self, record):

        if record.title is None:
            title = eim.Inherit # to delete the attribute
        else:
            title = record.title

        if record.createdOn not in emptyValues:
            # createdOn is a Decimal we need to change to datetime
            createdOn = decimalToDatetime(self.rv, record.createdOn)
        else:
            createdOn = eim.NoChange

        @self.withItemForUUID(
            record.uuid,
            pim.ContentItem,
            displayName=title,
            createdOn=createdOn,
            needsReply=with_nochange(record.needsReply, bool),
            read=with_nochange(record.read, bool)
        )
        def do(item):

            if record.triage != "" and record.triage not in emptyValues:
                code, timestamp, auto = record.triage.split(" ")

                try:
                    item._triageStatus = code_to_triagestatus[code]
                except KeyError:
                    # assume NOW if illegal code (bug 11606)
                    item._triageStatus = code_to_triagestatus["100"]

                item._triageStatusChanged = float(timestamp)
                if getattr(item, 'inheritFrom', False):
                    # When import_event happens after import_item on recurring
                    # events, triageStatus gets lost if doATODC isn't False,
                    # bug 10124, so always set doATODC to False for recurring
                    # events with inbound explicit triage, we'd expect Inherit
                    # to be used if doATODC was True, anyway.
                    item.doAutoTriageOnDateChange = False
                else:
                    item.doAutoTriageOnDateChange = (auto == "1")
            elif record.triage == eim.Inherit:
                item.doAutoTriageOnDateChange = True
                if isinstance(item, Occurrence):
                    item._triageStatus = pim.EventStamp(item).simpleAutoTriage()
                else:
                    item.setTriageStatus('auto')


            if record.hasBeenSent not in (eim.NoChange, eim.Inherit):
                if record.hasBeenSent:
                    if pim.Modification.sent not in item.modifiedFlags:
                        try:
                            item.modifiedFlags.add(pim.Modification.sent)
                        except AttributeError:
                            item.modifiedFlags = set([pim.Modification.sent])
                else:
                    if pim.Modification.sent in item.modifiedFlags:
                        item.modifiedFlags.remove(pim.Modification.sent)


    @eim.exporter(pim.ContentItem)
    def export_item(self, item):

        # TODO: see why many items don't have createdOn
        if not hasattr(item, 'createdOn'):
            item.createdOn = datetime.now(self.rv.tzinfo.default)

        # createdOn = handleEmpty(item, 'createdOn')
        # elif createdOn not in noChangeOrInherit:
        createdOn = datetimeToDecimal(item.createdOn)

        # For modifications, treat triage status as Inherit if it
        # matches its automatic state
        doATODC = getattr(item, "doAutoTriageOnDateChange", True)
        if item.hasLocalAttributeValue('inheritTo'):
            # recurrence masters don't have a meaningful triage status
            triage = eim.NoChange
        elif (isinstance(item, Occurrence) and 
              EventStamp(item).simpleAutoTriage() == item._triageStatus):
            # This will lose doATODC information, but that happens anyway for
            # modifications when they're unmodified, and doing this avoids
            # spurious conflicts
            triage = eim.Inherit
        else:
            if (pim.has_stamp(item, pim.EventStamp) and
                doATODC and
                EventStamp(item).autoTriage() != item._triageStatus):
                error_msg = ("Item %s has doAutoTriageOnDateChange==True"
                             " but its triageStatus is %s, ought to be %s")
                logger.info(error_msg % (getAliasForItem(item),
                                         item._triageStatus.name,
                                         EventStamp(item).autoTriage().name))

            tsCode = triagestatus_to_code.get(item._triageStatus, "100")
            tsChanged = item._triageStatusChanged or 0.0
            tsAuto = ("1" if doATODC else "0")
            triage = "%s %.2f %s" % (tsCode, tsChanged, tsAuto)

        if item.hasLocalAttributeValue('displayName'):
            title = item.displayName
        else:
            if isinstance(item, Occurrence):
                title = eim.Inherit
            else:
                title = ''

        if isinstance(item, Occurrence):
            hasBeenSent = eim.Inherit
        elif item.hasLocalAttributeValue('modifiedFlags'):
            hasBeenSent = int(pim.Modification.sent in item.modifiedFlags)
        else:
            hasBeenSent = 0

        yield model.ItemRecord(
            item,                                       # uuid
            self.obfuscate(title),                      # title
            triage,                                     # triage
            createdOn,                                  # createdOn
            hasBeenSent,                                # hasBeenSent
            handleEmpty(item, "needsReply"),            # needsReply
            handleEmpty(item, "read"),                  # read
        )

        # Also export a ModifiedByRecord
        lastModifiedBy = ""
        if hasattr(item, "lastModifiedBy"):
            emailAddress = item.lastModifiedBy
            if emailAddress is not None and emailAddress.emailAddress:
                lastModifiedBy = emailAddress.format()

        lastModified = getattr(item, "lastModified", None)
        if lastModified:
            lastModified = datetimeToDecimal(lastModified)
        else:
            lastModified = createdOn

        lastModification = item.lastModification

        yield model.ModifiedByRecord(
            item,
            self.obfuscate(lastModifiedBy),
            lastModified,
            action = self.modaction_to_code.get(lastModification, 500)
        )

        reminder = item.getUserReminder()

        if reminder is None:
            description = None
            trigger = None
            duration = None
            repeat = None

        elif reminder.reminderItem is item: # this is our reminder
            trigger = None
            if reminder.hasLocalAttributeValue('delta'):
                trigger = toICalendarDuration(reminder.delta)
            elif reminder.hasLocalAttributeValue('absoluteTime'):
                # iCalendar Triggers are supposed to be expressed in UTC;
                # EIM may not require that but might as well be consistent
                reminderTime = reminder.absoluteTime.astimezone(self.rv.tzinfo.UTC)
                trigger = toICalendarDateTime(self.rv, reminderTime, False)

            if reminder.duration:
                duration = toICalendarDuration(reminder.duration, False)
            else:
                duration = None

            if reminder.repeat:
                repeat = reminder.repeat
            else:
                repeat = None

            description = getattr(reminder, 'description', None)
            if description is None:
                description = "Event Reminder"

        else: # we've inherited this reminder
            description = eim.Inherit
            trigger = eim.Inherit
            duration = eim.Inherit
            repeat = eim.Inherit

        yield model.DisplayAlarmRecord(
            item,
            description,
            trigger,
            duration,
            repeat,
        )

        if item.private:
            yield model.PrivateItemRecord(item)



    @model.PrivateItemRecord.importer
    def import_privateItem(self, record):
        self.withItemForUUID(record.uuid, pim.ContentItem, private=True)


    # ModifiedByRecord  -------------

    @model.ModifiedByRecord.importer
    def import_modifiedBy(self, record):

        @self.withItemForUUID(record.uuid, pim.ContentItem)
        def do(item):
            # only apply a modifiedby record if timestamp is more recent than
            # what's on the item already

            logger.info("Examining ModifiedByRecord: %s", record)

            existing = getattr(item, "lastModified", None)
            existing = datetimeToDecimal(existing) if existing else 0

            if record.timestamp >= existing:

                # record.userid can never be NoChange.  "" == anonymous
                if not record.userid:
                    item.lastModifiedBy = None
                else:
                    item.lastModifiedBy = \
                        pim.EmailAddress.getEmailAddress(self.rv, record.userid)

                # record.timestamp can never be NoChange, nor None
                # timestamp is a Decimal we need to change to datetime
                try:
                    item.lastModified = decimalToDatetime(self.rv,
                        record.timestamp)
                except ValueError:
                    # Bogus timestamp, ignore it
                    pass

                if record.action is not eim.NoChange:
                    item.lastModification = \
                        self.code_to_modaction[record.action]

                #XXX Brian K: The modified flags were not getting set properly
                # without this addition.
                item.changeEditState(item.lastModification,
                                     item.lastModifiedBy,
                                     item.lastModified)

                logger.info("Applied ModifiedByRecord: %s", record)
                logger.info("Now lastModifiedBy is %s", item.lastModifiedBy)
            else:
                logger.info("Skipped ModifiedByRecord: record %s vs local %s",
                    record.timestamp, existing)


        # Note: ModifiedByRecords are exported by item



    # NoteRecord -------------

    @model.NoteRecord.importer
    def import_note(self, record):

        if record.body is None:
            body = eim.Inherit # to delete the attribute
        else:
            body = record.body

        # Task in Bug 9359, icalUID may be serialized as None or equivalent
        # to UUID, in these cases don't set Chandler's icalUID attribute, it's
        # redundant

        if record.uuid != getMasterAlias(record.uuid):
            # An occurrence
            icalUID = eim.Inherit
        else:
            icalUID = record.icalUid
            if icalUID is None:
                icalUID = eim.NoChange

        if record.icalExtra is None:
            icalExtra = eim.NoChange
        else:
            icalExtra = record.icalExtra

        self.withItemForUUID(
            record.uuid,
            pim.Note,
            icalUID=icalUID,
            body=body,
            icalendarExtra=icalExtra
        )

    @eim.exporter(pim.Note)
    def export_note(self, note):

        if note.hasLocalAttributeValue('body'):
            body = note.body
        else:
            if isinstance(note, Occurrence):
                body = eim.Inherit
            else:
                body = None

        icalUID = handleEmpty(note, 'icalUID')
        if icalUID is None:
            icalUID = note.itsUUID.str16()
        if isinstance(note, Occurrence):
            icalUID = eim.Inherit

        yield model.NoteRecord(
            note,                                       # uuid
            self.obfuscate(body),                       # body
            icalUID,                                    # icalUid
            eim.Inherit,                                # icalendarProperties
            eim.Inherit,                                # icalendarParameters
            handleEmpty(note, 'icalendarExtra'),        # icalendarExtra
        )



    # TaskRecord -------------

    @model.TaskRecord.importer
    def import_task(self, record):
        self.withItemForUUID(
            record.uuid,
            pim.TaskStamp
        )

    @eim.exporter(pim.TaskStamp)
    def export_task(self, task):
        yield model.TaskRecord(
            task
        )


    @model.TaskRecord.deleter
    def delete_task(self, record):
        d = self.deferredUUID(record.uuid, create=False)
        @d.addCallback
        def do_delete(uuid):
            if uuid is not None:
                item = self.rv.findUUID(uuid)
                if not getattr(item, 'inheritFrom', None):
                    # master, make a recurrence change proxy
                    item = pim.CHANGE_ALL(item)
                    item.markEdited = lambda *args: None
                if (item is not None and item.isLive() and
                    pim.has_stamp(item, pim.TaskStamp)):
                    pim.TaskStamp(item).remove()
        d.addErrback(self.recordFailure)


    @model.PasswordRecord.importer
    def import_password(self, record):
        self.withItemForUUID(
            record.uuid,
            Password,
            ciphertext=record.ciphertext,
            iv=record.iv,
            salt=record.salt,
        )

    @model.PasswordRecord.importer
    def import_password(self, record):
        self.withItemForUUID(
            record.uuid,
            Password,
            ciphertext=record.ciphertext,
            iv=record.iv,
            salt=record.salt,
        )

    @eim.exporter(Password)
    def export_password(self, password):

        if self.obfuscation: return

        ciphertext, iv, salt = waitForDeferred(password.recordTuple())
        yield model.PasswordRecord(password, ciphertext, iv, salt)

    @model.PasswordPrefsRecord.importer
    def import_password_prefs(self, record):
        # Hard coded UUID so this is enough for the dummyPassword
        self.withItemForUUID(record.dummyPassword, Password)

        prefs = schema.ns("osaf.framework.MasterPassword",
                  self.rv).masterPasswordPrefs
        prefs.masterPassword = bool(record.masterPassword)
        prefs.timeout = record.timeout
        protect = getattr(record, "protect", 0)
        if protect == 1:
            prefs.protect = True
        elif protect == 2:
            prefs.protect = False

    # Called from finishExport()
    def export_password_prefs(self):

        if self.obfuscation: return

        prefs = schema.ns("osaf.framework.password", self.rv).passwordPrefs
        dummyPassword = prefs.dummyPassword

        prefs = schema.ns("osaf.framework.MasterPassword",
                  self.rv).masterPasswordPrefs
        masterPassword = prefs.masterPassword
        timeout = prefs.timeout
        protect = getattr(prefs, "protect", None)
        if protect is None:
            protect = 0
        elif protect == True:
            protect = 1
        elif protect == False:
            protect = 2

        yield model.PasswordPrefsRecord(dummyPassword,
                                        1 if masterPassword else 0,
                                        timeout,
                                        protect)
        for record in self.export_password(dummyPassword):
            yield record

    # ClientIDRecord
    @model.ClientIDRecord.importer
    def import_client_id(self, record):
        client_id = schema.ns("osaf.app", self.rv).clientID
        client_id.clientID = record.clientID
        
    # Called from finishExport()
    def export_client_id(self):
        client_id = schema.ns("osaf.app", self.rv).clientID
        yield model.ClientIDRecord(client_id.clientID)
        

    # UpdateCheckPrefsRecord
    @model.UpdateCheckPrefsRecord.importer
    def import_update_prefs(self, record):
        updateTask = schema.ns("osaf.app", self.rv).updateCheckTask
        if record.numDays < 0:
            updateTask.stop()
        else:
            interval = timedelta(days=record.numDays)
            updateTask.stopped = False
            if updateTask.interval != interval:
                updateTask.reschedule(interval)

    # Called from finishExport()
    def export_update_prefs(self):
        updateTask = schema.ns("osaf.app", self.rv).updateCheckTask
        if updateTask.stopped:
            numDays = -1
        else:
            numDays = updateTask.interval.days
        yield model.UpdateCheckPrefsRecord(numDays)


    # AutoRestorePrefsRecord
    @model.AutoRestorePrefsRecord.importer
    def import_autorestore_prefs(self, record):
        schema.ns("osaf.app", self.rv).autoRestorePrefs.enabled = bool(record.enabled)

    # Called from finishExport()
    def export_autorestore_prefs(self):
        enabled = schema.ns("osaf.app", self.rv).autoRestorePrefs.enabled
        yield model.AutoRestorePrefsRecord(int(enabled))


    #MailMessageRecord
    @model.MailMessageRecord.importer
    def import_mail(self, record):

        messageId = (eim.Inherit if record.messageId == None
                     else record.messageId)

        inReplyTo = (eim.Inherit if record.inReplyTo == None
                     else record.inReplyTo)

        dateSent = (eim.Inherit if record.dateSent == None
                     else record.dateSent)

        @self.withItemForUUID(
           record.uuid,
           pim.MailStamp,
           dateSentString=dateSent,
           messageId=messageId,
           inReplyTo=inReplyTo
        )
        def do(mail):

            if record.headers not in noChangeOrInherit:
                mail.headers = {}

                if record.headers:
                    headers = record.headers.split(u"\n")

                    prevKey = None

                    for header in headers:
                        try:
                            key, val = header.split(u": ", 1)
                            mail.headers[key] = val

                            # Keep the last valid key around
                            prevKey = key
                        except:
                            if prevKey:
                                mail.headers[prevKey] += "\n" + header

            if record.toAddress not in noChangeOrInherit:
                mail.toAddress = []
                if record.toAddress:
                    addEmailAddresses(self.rv, mail.toAddress, record.toAddress)

            if record.ccAddress not in noChangeOrInherit:
                mail.ccAddress = []

                if record.ccAddress:
                    addEmailAddresses(self.rv, mail.ccAddress, record.ccAddress)

            if record.bccAddress not in noChangeOrInherit:
                mail.bccAddress = []

                if record.bccAddress:
                    addEmailAddresses(self.rv, mail.bccAddress, record.bccAddress)

            if record.fromAddress not in noChangeOrInherit:
               if record.fromAddress:
                    mail.fromAddress = getEmailAddress(self.rv, record.fromAddress)
               else:
                   mail.fromAddress = None

            # text or email addresses in Chandler from field
            if record.originators not in noChangeOrInherit:
                if record.originators:
                    res = EmailAddress.parseEmailAddresses(self.rv, record.originators)

                    mail.originators = [ea for ea in res[1]]
                else:
                    mail.originators = []

            # references mail message id list
            if record.references not in noChangeOrInherit:
                mail.referencesMID = []

                if record.references:
                    refs = record.references.split()

                    for ref in refs:
                        ref = ref.strip()

                        if ref: mail.referencesMID.append(ref)

            if record.dateSent not in noChangeOrInherit:
                if record.dateSent and record.dateSent.strip():
                    mail.dateSentString = record.dateSent

                    timestamp = Utils.parsedate_tz(record.dateSent)
                    mail.dateSent = RFC2822DateToDatetime(record.dateSent, self.rv.tzinfo.default)
                else:
                    mail.dateSent = getEmptyDate(self.rv)
                    mail.dateSentString = u""

            if record.mimeContent not in noChangeOrInherit:
                if record.mimeContent:
                    # There is no attachment support for
                    # 1.0. This is a place holder for
                    # future enhancements
                    pass

            if record.rfc2822Message not in noChangeOrInherit:
                if record.rfc2822Message:
                    mail.rfc2822Message = dataToBinary(mail, "rfc2822Message",
                                                       record.rfc2822Message,
                                                      'message/rfc822', 'bz2',
                                                       False)

            if record.previousSender not in noChangeOrInherit:
               if record.previousSender:
                    mail.previousSender = getEmailAddress(self.rv, record.previousSender)
               else:
                   mail.previousSender = None

            if record.replyToAddress not in noChangeOrInherit:
               if record.replyToAddress:
                    mail.replyToAddress = getEmailAddress(self.rv, record.replyToAddress)
               else:
                   mail.replyToAddress = None

            if record.messageState not in noChangeOrInherit:
                state = record.messageState
                mail.fromMe         = bool(state & MessageState.FROM_ME)
                mail.toMe           = bool(state & MessageState.TO_ME)
                mail.viaMailService = bool(state & MessageState.VIA_MAILSERVICE)
                mail.isUpdated      = bool(state & MessageState.IS_UPDATED)
                mail.fromEIMML      = bool(state & MessageState.FROM_EIMML)
                mail.previousInRecipients = \
                               bool(state & MessageState.PREVIOUS_IN_RECIPIENTS)


    @eim.exporter(pim.MailStamp)
    def export_mail(self, mail):
        # Move to a local variable for a slight performance increase
        obf = self.obfuscation

        def format(ea):
            if obf:
                return u"%s@example.com" % ea.itsUUID

            return ea.format()


        headers = []

        for header in getattr(mail, 'headers', []):
            if obf:
                headers.append(u"%s: %s" % (header, self.obfuscate(mail.headers[header])))

            else:
                headers.append(u"%s: %s" % (header, mail.headers[header]))

        if headers:
            # Sort the headers to ensure they are serialized in a
            # consistent manner.
            headers.sort()
            headers = u"\n".join(headers)
        else:
            headers = None

        toAddress = []

        for addr in getattr(mail, 'toAddress', []):
            toAddress.append(format(addr))

        if toAddress:
            toAddress = u", ".join(toAddress)
        else:
            toAddress = u''

        ccAddress = []

        for addr in getattr(mail, 'ccAddress', []):
            ccAddress.append(format(addr))

        if ccAddress:
            ccAddress = u", ".join(ccAddress)
        else:
            ccAddress = u''

        bccAddress = []

        for addr in getattr(mail, 'bccAddress', []):
            bccAddress.append(format(addr))

        if bccAddress:
            bccAddress = u", ".join(bccAddress)
        else:
            bccAddress = u''

        originators = []

        if getattr(mail, "originators", None) is not None:
            for addr in mail.originators:
                originators.append(format(addr))


        if originators:
            originators = u", ".join(originators)
        else:
            originators = None

        fromAddress = u''

        if getattr(mail, "fromAddress", None) is not None:
            fromAddress = format(mail.fromAddress)


        references = []

        for ref in getattr(mail, "referencesMID", []):
            ref = ref.strip()

            if ref:
                if obf:
                    references.append(self.obfuscate(ref))

                else:
                    references.append(ref)

        if references:
            references = u" ".join(references)
        else:
            references = None

        inReplyTo = None

        if getattr(mail, "inReplyTo", None) is not None:
            if obf:
                 inReplyTo = self.obfuscate(mail.inReplyTo)
            else:
                inReplyTo = mail.inReplyTo

        messageId = None

        if getattr(mail, "messageId", None) is not None:
            if obf:
                messageId = self.obfuscate(mail.messageId)
            else:
                messageId = mail.messageId

        dateSent = None

        if getattr(mail, "dateSentString", None) is not None:
            dateSent = mail.dateSentString

        # Place holder for attachment support
        mimeContent = None
        rfc2822Message = None

        if getattr(mail, "rfc2822Message", None) is not None:
            if obf:
                rfc2822Message = self.obfuscate(binaryToData(mail.rfc2822Message))
            else:
                rfc2822Message = binaryToData(mail.rfc2822Message)

        previousSender = None

        if getattr(mail, "previousSender", None) is not None:
            previousSender = format(mail.previousSender)

        replyToAddress = None

        if getattr(mail, "replyToAddress", None) is not None:
            replyToAddress = format(mail.replyToAddress)

        messageState = 0

        if mail.fromMe:
            messageState |= MessageState.FROM_ME

        if mail.toMe:
            messageState |= MessageState.TO_ME

        if mail.viaMailService:
            messageState |= MessageState.VIA_MAILSERVICE

        if mail.isUpdated:
            messageState |= MessageState.IS_UPDATED

        if mail.fromEIMML:
            messageState |= MessageState.FROM_EIMML

        if mail.previousInRecipients:
            messageState |= MessageState.PREVIOUS_IN_RECIPIENTS


        yield model.MailMessageRecord(
            mail,                  # uuid
            messageId,             # messageId
            headers,               # headers
            fromAddress,           # fromAddress
            toAddress,             # toAddress
            ccAddress,             # ccAddress
            bccAddress,            # bccAddress
            originators,           # originators
            dateSent,              # dateSent
            inReplyTo,             # inReplyTo
            references,            # references
            mimeContent,           #mimeContent
            rfc2822Message,        #rfc2822Message
            previousSender,        #previousSender
            replyToAddress,        #replyToAddress
            messageState,          #messageState
        )


    @model.MailMessageRecord.deleter
    def delete_mail(self, record):
        d = self.deferredUUID(record.uuid, create=False)
        @d.addCallback
        def do_delete(uuid):
            if uuid is not None:
                item = self.rv.findUUID(uuid)
                if not getattr(item, 'inheritFrom', None):
                    # master, make a recurrence change proxy
                    item = pim.CHANGE_ALL(item)
                    item.markEdited = lambda *args: None
                if (item is not None and item.isLive() and
                    pim.has_stamp(item, pim.MailStamp)):
                    pim.MailStamp(item).remove()
        d.addErrback(self.recordFailure)

    # EventRecord -------------

    # TODO: EventRecord fields need work, for example: rfc3339 date strings

    @model.EventRecord.importer
    def import_event(self, record):

        start, allDay, anyTime = getTimeValues(self.rv, record)

        uuid, recurrenceID = splitUUID(self.rv, record.uuid)
        if recurrenceID and start == eim.Inherit:
            start = recurrenceID

        if (self.promptForTimezoneAllowed and start not in emptyValues
            and start.tzinfo not in (self.rv.tzinfo.floating, None)):
            # got a timezoned event, prompt (non-modally) to turn on
            # timezones
            if self.rv.isReindexingDeferred():
                self.timezonePromptRequested = True
            else:
                import wx
                app = wx.GetApp()
                if app is not None:
                    from application.dialogs.TurnOnTimezones import ShowTurnOnTimezonesDialog
                    def ShowTimezoneDialogCallback():
                        ShowTurnOnTimezonesDialog(view=app.UIRepositoryView)
                    app.PostAsyncEvent(ShowTimezoneDialogCallback)
            self.promptForTimezoneAllowed = False


        @self.withItemForUUID(
            record.uuid,
            EventStamp,
            startTime=start,
            transparency=with_nochange(record.status, fromTransparency),
            location=with_nochange(record.location, fromLocation, self.rv),
        )
        def do(item):
            event = EventStamp(item)
            duration = with_nochange(record.duration, fromICalendarDuration)
            
            # allDay and anyTime shouldn't be set if they match the master
            master = event.getMaster()
            # a master may be "faked" to allow a modification to be imported
            # with a dummy master
            fakeMaster = getattr(master.itsItem, '_fake', False)
            if master == event:
                if fakeMaster:
                    del master.itsItem._fake
                if allDay in (True, False):
                    event.allDay = allDay
                    # modifications may have been created before the master, so
                    # they may have unnecessarily set allDay
                    for mod in master.modifications:
                        modEvent = EventStamp(mod)
                        if modEvent.allDay == allDay:
                            delattr(modEvent, 'allDay')

                if anyTime in (True, False):
                    event.anyTime = anyTime
                    # modifications may have been created before the master, so
                    # they may have unnecessarily set anyTime
                    for mod in master.modifications:
                        modEvent = EventStamp(mod)
                        if modEvent.anyTime == anyTime:
                            delattr(modEvent, 'anyTime')
                
                if duration not in emptyValues:
                    if event.anyTime or event.allDay:
                        duration -= oneDay
                    event.duration = duration

            else:
                # a modification
                # set attributes that may want to be inherited.
                if allDay in (True, False) and (fakeMaster or
                                                allDay != master.allDay):
                    event.allDay = allDay
                elif allDay == eim.Inherit:
                    delattr(event, 'allDay')

                if anyTime in (True, False) and (fakeMaster or
                                                 anyTime != master.anyTime):
                    event.anyTime = anyTime
                elif anyTime == eim.Inherit:
                    delattr(event, 'anyTime')

                if not fakeMaster:
                    fixTimezoneOnModification(event)
                    if duration not in emptyValues:
                        if event.anyTime or event.allDay:
                            duration -= oneDay
                        event.duration = duration

                else:
                    if duration not in emptyValues:
                        if allDay not in emptyValues:
                            if anyTime or allDay:
                                duration -= oneDay
                        else:
                            # handling duration when the master hasn't yet been
                            # imported and the modification has no changes to 
                            # start time means we have to look at recurrenceID
                            # to determine allDay-ness for duration translation
                            pos = record.uuid.find(':')
                            if pos != -1:
                                if record.uuid[pos + 1] == ':':
                                    # old style pseudo-uuid, two colons in a row
                                    pos += 1
                                ignore, allDayFromID, anyTimeFromID = \
                                  fromICalendarDateTime(self.rv, 
                                                        record.uuid[pos + 1:])
                                if allDayFromID or anyTimeFromID:
                                    duration -= oneDay

                        event.duration = duration
                    
                # modifications don't have recurrence rule information, so stop
                return

            # notify of recurrence changes once at the end
            if event.rruleset is not None:
                ignoreChanges = getattr(event.rruleset, '_ignoreValueChanges',
                    False)
                event.rruleset._ignoreValueChanges = True
            elif (record.rrule in emptyValues and
                  record.rdate in emptyValues):
                # since there's no recurrence currently, avoid creating a
                # rruleset if all the positive recurrence fields are None
                return
            
            newRule = event.rruleset is None or fakeMaster
            rruleset = (RecurrenceRuleSet(None, itsView=self.rv) if newRule 
                        else event.rruleset)

            for ruletype in 'rrule', 'exrule':
                record_field = getattr(record, ruletype)
                if record_field is not eim.NoChange:
                    if record_field in (None, eim.Inherit):
                        # this isn't the right way to delete the existing
                        # rules, what is?
                        setattr(rruleset, ruletype + 's', [])
                    else:
                        du_rruleset = getDateUtilRRuleSet(ruletype,
                            record_field, event.effectiveStartTime)
                        rules = getattr(du_rruleset, '_' + ruletype)
                        if rules is None:
                            rules = []
                        itemlist = []
                        for du_rule in rules:
                            ruleItem = RecurrenceRule(None, None, None, self.rv)
                            ruleItem.setRuleFromDateUtil(du_rule)
                            itemlist.append(ruleItem)
                        setattr(rruleset, ruletype + 's', itemlist)
            
            floating = self.rv.tzinfo.floating
            mastertz = event.effectiveStartTime.tzinfo
            masterAllDay = event.allDay or event.anyTime

            for datetype in 'rdate', 'exdate':
                record_field = getattr(record, datetype)
                if record_field is not eim.NoChange:
                    if record_field is None:
                        dates = []
                    else:
                        dates = fromICalendarDateTime(self.rv, record_field,
                                                      multivalued=True)[0]
                        if not masterAllDay and mastertz != floating: 
                            dates = [d.replace(tzinfo=mastertz) if 
                                     d.tzinfo == floating else d for d in dates]
                            
                    setattr(rruleset, datetype + 's', dates)

            if (len(getattr(rruleset, 'rrules', ())) == 0 and
                len(getattr(rruleset, 'rdates', ())) == 0):
                event.removeRecurrence()
            else:
                # if the master is in the past but not triaged DONE before
                # recurrence is added, a modification will be created that is
                # pinned to now, which is undesirable, bug 9414
                event.itsItem.setTriageStatus('auto')
                event.itsItem.purgeSectionTriageStatus()
                if not newRule:
                    # changed existing recurrence
                    event.rruleset._ignoreValueChanges = ignoreChanges
                    event.cleanRule()
                else:
                    # new recurrence
                    event.rruleset = rruleset
                    # fix bug 11475, when recurrence is initially added,
                    # don't let occurring-now events be triaged NOW
                    for mod in event.modifications:
                        if mod._triageStatus == pim.TriageEnum.now:
                            mod._triageStatus = pim.TriageEnum.done
                            mod.purgeSectionTriageStatus()
                    
                # search through modifications in case they were created before
                # the master, if they're timezoned they'll have recurrenceID in
                # UTC, worse, if they inherit startTime it'll be in UTC
                tzinfo = event.effectiveStartTime.tzinfo
                if tzinfo != self.rv.tzinfo.floating:
                    for mod in event.modifications:
                        fixTimezoneOnModification(mod, tzinfo)

    @eim.exporter(EventStamp)
    def export_event(self, event):
        item = event.itsItem

        location = handleEmpty(event, 'location')
        if location not in emptyValues:
            location = location.displayName

        rrule, exrule, rdate, exdate = getRecurrenceFields(event)

        transparency = handleEmpty(event, 'transparency')
        if transparency not in emptyValues:
            transparency = str(event.transparency).upper()
            if transparency == "FYI":
                transparency = "CANCELLED"

        has_change = event.hasLocalAttributeValue


        # if recurring and the modification isn't off-rule, dtstart has changed
        # if allDay or anyTime has a local change, or if effectiveStartTime !=
        # recurrenceID.  If it's an off-rule modification, its
        # effectiveStartTime may not match up because of disagreements in
        # anyTime/allDay, in that case compare starTime to recurrenceID instead
        # of effectiveStartTime
        dtstart = None
        if (isinstance(item, Occurrence) and
                  not has_change('allDay') and 
                  not has_change('anyTime')):
            floating = self.rv.tzinfo.floating
            master = event.getMaster()
            masterFloating = (master.allDay or master.anyTime or
                              master.startTime.tzinfo == floating)
            recurrenceIDFloating = (event.recurrenceID.tzinfo == floating)
            if masterFloating != recurrenceIDFloating:
                comparisonDate = event.startTime
            else:
                comparisonDate = event.effectiveStartTime

            if datetimes_really_equal(comparisonDate, event.recurrenceID):
                dtstart = eim.Inherit

        if dtstart is None:
            dtstart = toICalendarDateTime(self.rv, event.effectiveStartTime, 
                                          event.allDay, event.anyTime)

        # if recurring, duration has changed if allDay, anyTime, or duration has
        # a local change
        if (not isinstance(item, Occurrence) or
            has_change('allDay') or 
            has_change('anyTime') or 
            has_change('duration')):
            duration = toICalendarDuration(event.duration, 
                                           event.allDay or event.anyTime)
        else:
            duration = eim.Inherit

        lastPast = eim.NoChange
        if event.occurrenceFor is None and event.rruleset is not None:
            rruleset = event.createDateUtilFromRule()
            lastPast = rruleset.before(getNow(self.rv.tzinfo.default))
            if lastPast is not None:
                # convert to UTC if not floating
                if lastPast.tzinfo != self.rv.tzinfo.floating:
                    lastPast = lastPast.astimezone(self.rv.tzinfo.UTC)
                lastPast = toICalendarDateTime(self.rv, lastPast, event.allDay,
                                               event.anyTime)
            
            

        yield model.EventRecord(
            event,                                      # uuid
            dtstart,                                    # dtstart
            duration,                                   # duration
            self.obfuscate(location),                   # location
            rrule,                                      # rrule
            exrule,                                     # exrule
            rdate,                                      # rdate
            exdate,                                     # exdate
            transparency,                               # status
            lastPast                                    # lastPastOccurrence
        )

    @model.EventRecord.deleter
    def delete_event(self, record):
        uuid, recurrenceID = splitUUID(self.rv, record.uuid)
        item = self.rv.findUUID(uuid)
        if item is not None and item.isLive() and pim.has_stamp(item,
            EventStamp):
            if recurrenceID:
                occurrence = EventStamp(item).getRecurrenceID(recurrenceID)
                occurrence.unmodify(partial=True)
            else:
                EventStamp(item).remove()

    # DisplayAlarmRecord -------------

    @model.DisplayAlarmRecord.importer
    def import_alarm(self, record):

        @self.withItemForUUID(record.uuid, pim.ContentItem)
        def do(item):
            # Rather than simply leaving out a DisplayAlarmRecord, we're using
            # a trigger value of None to indicate there is no alarm:
            if record.trigger is None:
                item.reminders = []

            elif record.trigger not in noChangeOrInherit:
                # trigger translates to either a pim.Reminder (if a date(time),
                # or a pim.RelativeReminder (if a timedelta).
                kw = dict(itsView=item.itsView)
                reminderFactory = None

                try:
                    val = fromICalendarDateTime(self.rv, record.trigger)[0]
                    val = val.astimezone(self.rv.tzinfo.default)
                except:
                    pass
                else:
                    reminderFactory = pim.Reminder
                    kw.update(absoluteTime=val)

                if reminderFactory is None:
                    try:
                        val = stringToDurations(record.trigger)[0]
                    except:
                        pass
                    else:
                        reminderFactory = pim.RelativeReminder
                        kw.update(delta=val)

                if reminderFactory is not None:
                    item.reminders = [reminderFactory(**kw)]


            reminder = item.getUserReminder()
            if reminder is not None:

                if (record.description not in noChangeOrInherit and
                    record.description is not None):
                    reminder.description = record.description

                if record.duration not in noChangeOrInherit:
                    if record.duration is None:
                        delattr(reminder, 'duration') # has a defaultValue
                    else:
                        reminder.duration = stringToDurations(record.duration)[0]

                if record.repeat not in noChangeOrInherit:
                    if record.repeat is None:
                        reminder.repeat = 0
                    else:
                        reminder.repeat = record.repeat

    @model.DisplayAlarmRecord.deleter
    def delete_alarm(self, record):
        item = self.rv.findUUID(self.getUUIDForAlias(record.uuid))
        item.reminders = []






class DumpTranslator(SharingTranslator):

    URI = "cid:dump-translator@osaf.us"
    version = 1
    description = u"Translator for Chandler items (PIM and non-PIM)"


    # Mapping for well-known names to/from their current repository path
    path_to_name = {
        "//parcels/osaf/app/sidebarCollection" : "@sidebar",
    }
    name_to_path = dict([[v, k] for k, v in path_to_name.items()])


    approvedClasses = (
        pim.Note, Password, pim.SmartCollection, shares.Share,
        conduits.BaseConduit, shares.State, accounts.SharingAccount,
        mail.AccountBase, mail.IMAPFolder, accounts.Proxy
    )

    def exportItem(self, item):
        """
        Export an item and its stamps, if any.

        Recurrence changes:
        - Avoid exporting occurrences unless they're modifications.
        - Don't serialize recurrence rule items

        """

        if not isinstance(item, self.approvedClasses):
            return

        elif isinstance(item, Occurrence):
            if not EventStamp(item).modificationFor:
                return

        for record in super(DumpTranslator, self).exportItem(item):
            yield record


    # - - Collection  - - - - - - - - - - - - - - - - - - - - - - - - - - -
    @model.CollectionRecord.importer
    def import_collection(self, record):
        @self.withItemForUUID(record.uuid, pim.SmartCollection)
        def add_source(collection):
            if record.mine == 1:
                schema.ns('osaf.pim', self.rv).mine.addSource(collection)
            if record.colorRed is not None:
                UserCollection(collection).color = ColorType(
                    record.colorRed, record.colorGreen, record.colorBlue,
                    record.colorAlpha
                )
            UserCollection(collection).checked = bool(record.checked)

    @eim.exporter(pim.SmartCollection)
    def export_collection(self, collection):
        try:
            color = UserCollection (collection).color
            red = color.red
            green = color.green
            blue = color.blue
            alpha = color.alpha
        except AttributeError: # collection has no color
            red = green = blue = alpha = None

        yield model.CollectionRecord(
            collection,
            int (collection in schema.ns('osaf.pim', self.rv).mine.sources),
            red,
            green,
            blue,
            alpha,
            int(UserCollection(collection).checked)
        )
        for record in self.export_collection_memberships (collection):
            yield record


    def export_collection_memberships(self, collection):
        index = 0

        # For well-known collections, use their well-known name rather than
        # their UUID
        collectionID = self.path_to_name.get(str(collection.itsPath),
            collection.itsUUID.str16())

        for item in collection.inclusions:
            # We iterate inclusions directly because we want the proper
            # trash behavior to get reloaded -- we want to keep track that
            # a trashed item was in the inclusions of a collection.
            # By default we don't include items that are in
            # //parcels since they are not created by the user


            # For items in the sidebar, if they're not of an approved class
            # then skip them.
            # TODO: When we have a better solution for filtering plugin data
            # this check should be removed:
            if (collectionID == "@sidebar" and
                not isinstance(item, self.approvedClasses)):
                continue


            if (not str(item.itsPath).startswith("//parcels") and
                not isinstance(item, Occurrence)):
                yield model.CollectionMembershipRecord(
                    collectionID,
                    item.itsUUID,
                    index,
                )
                index = index + 1

    if __debug__:
        def indexIsInSequence (self, collection, index):
            if not hasattr (self, "collectionToIndex"):
                self.collectionToIndex = {}
            expectedIndex = self.collectionToIndex.get (collection, 0)
            self.collectionToIndex[collection] = index + 1
            return expectedIndex == index


    @model.CollectionMembershipRecord.importer
    def import_collectionmembership(self, record):

        # Don't add non-masters to collections:
        if record.itemUUID != getMasterAlias(record.itemUUID):
            return

        id = record.collectionID

        # Map old hard-coded sidebar UUID to its well-known name
        if id == "3c58ae62-d8d6-11db-86bb-0017f2ca1708":
            id = "@sidebar"

        id = self.name_to_path.get(id, id)

        if id.startswith("//"):
            collection = self.rv.findPath(id)
            # We're preserving order of items in collections
            # assert (self.indexIsInSequence (collection, record.index))
            @self.withItemForUUID(record.itemUUID, pim.ContentItem)
            def do(item):
                collection.add(item)

        else:
            # Assume that non-existent collections should be created as
            # SmartCollections; otherwise don't upgrade from ContentCollection
            # base
            collectionType = (
                pim.SmartCollection if self.rv.findUUID(id) is None
                else pim.ContentCollection
            )
            @self.withItemForUUID(id, collectionType)
            def do(collection):
                # We're preserving order of items in collections
                # assert (self.indexIsInSequence (collection, record.index))
                @self.withItemForUUID(record.itemUUID, pim.ContentItem)
                def do(item):
                    collection.add(item)


    @model.DashboardMembershipRecord.importer
    def import_dashboard_membership(self, record):

        # Don't add non-masters to collections:
        if record.itemUUID != getMasterAlias(record.itemUUID):
            return

        @self.withItemForUUID(record.itemUUID, pim.ContentItem)
        def do(item):
            dashboard = schema.ns("osaf.pim", self.rv).allCollection
            dashboard.add(item)


    @model.TrashMembershipRecord.importer
    def import_trash_membership(self, record):

        # Don't add non-masters to collections:
        if record.itemUUID != getMasterAlias(record.itemUUID):
            return

        @self.withItemForUUID(record.itemUUID, pim.ContentItem)
        def do(item):
            trash = schema.ns("osaf.pim", self.rv).trashCollection
            trash.add(item)




    # - - Sharing-related items - - - - - - - - - - - - - - - - - - - - - -

    @model.ShareRecord.importer
    def import_sharing_share(self, record):

        @self.withItemForUUID(record.uuid,
            shares.Share,
            established=True,
            error=record.error,
            errorDetails=record.errorDetails,
            mode=record.mode
        )
        def do(share):
            if record.lastSuccess not in (eim.NoChange, None):
                # lastSuccess is a Decimal we need to change to datetime
                share.lastSuccess = decimalToDatetime(self.rv, record.lastSuccess)

            if record.lastAttempt not in (eim.NoChange, None):
                # lastAttempt is a Decimal we need to change to datetime
                share.lastAttempt = decimalToDatetime(self.rv, record.lastAttempt)

            if record.subscribed == 0:
                share.sharer = schema.ns('osaf.pim',
                    self.rv).currentContact.item

            if record.contents not in (eim.NoChange, None):
                # contents is the UUID of a SharedItem
                @self.withItemForUUID(record.contents, shares.SharedItem)
                def do_contents(sharedItem):
                    share.contents = sharedItem.itsItem

            if record.conduit not in (eim.NoChange, None):
                @self.withItemForUUID(record.conduit, conduits.Conduit)
                def do_conduit(conduit):
                    share.conduit = conduit



    @eim.exporter(shares.Share)
    def export_sharing_share(self, share):

        if self.obfuscation: return

        try:
            contents = share.contents.itsUUID
        except AttributeError:
            # bug 12353, this should never happen, but if it does, just ignore
            # the share
            return

        conduit = share.conduit.itsUUID

        subscribed = 0 if utility.isSharedByMe(share) else 1

        error = getattr(share, "error", "")

        errorDetails = getattr(share, "errorDetails", "")

        mode = share.mode

        if hasattr(share, "lastSuccess"):
            lastSuccess = datetimeToDecimal(share.lastSuccess)
        else:
            lastSuccess = None

        if hasattr(share, "lastAttempt"):
            lastAttempt = datetimeToDecimal(share.lastAttempt)
        else:
            lastAttempt = None

        yield model.ShareRecord(
            share,
            contents,
            conduit,
            subscribed,
            error,
            errorDetails,
            mode,
            lastSuccess,
            lastAttempt
        )



    @model.ShareConduitRecord.importer
    def import_sharing_conduit(self, record):
        self.withItemForUUID(record.uuid,
            conduits.BaseConduit,
            sharePath=record.path,
            shareName=record.name
        )

    @eim.exporter(conduits.BaseConduit)
    def export_sharing_conduit(self, conduit):

        if self.obfuscation: return

        path = conduit.sharePath
        name = conduit.shareName

        yield model.ShareConduitRecord(
            conduit,
            path,
            name
        )




    @model.ShareRecordSetConduitRecord.importer
    def import_sharing_recordset_conduit(self, record):

        @self.withItemForUUID(record.uuid,
            recordset_conduit.RecordSetConduit,
            syncToken=record.syncToken
        )
        def do(conduit):
            if record.serializer == "eimml":
                conduit.serializer = eimml.EIMMLSerializer
            elif record.serializer == "eimml_lite":
                conduit.serializer = eimml.EIMMLSerializerLite
            elif record.serializer == "ics":
                import ics # TODO: fix interdependencies between ics.py
                conduit.serializer = ics.ICSSerializer

            # if record.translator == "sharing":
            conduit.translator = SharingTranslator

            if record.filters not in (None, eim.NoChange):
                for filter in record.filters.split(","):
                    if filter:
                        conduit.filters.add(filter)

    @eim.exporter(recordset_conduit.RecordSetConduit)
    def export_sharing_recordset_conduit(self, conduit):

        if self.obfuscation: return

        import ics # TODO: fix interdependencies between ics.py

        translator = "sharing"

        serializer = getattr(conduit, 'serializer', None)
        if serializer is None:
            serializer = ''
        elif serializer is eimml.EIMMLSerializer:
            serializer = 'eimml'
        elif serializer is eimml.EIMMLSerializerLite:
            serializer = 'eimml_lite'
        elif serializer is ics.ICSSerializer:
            serializer = 'ics'

        filters = ",".join(conduit.filters)

        syncToken = conduit.syncToken

        yield model.ShareRecordSetConduitRecord(
            conduit,
            translator,
            serializer,
            filters,
            syncToken
        )


    @model.ShareMonolithicRecordSetConduitRecord.importer
    def import_sharing_monolithic_recordset_conduit(self, record):
        self.withItemForUUID(record.uuid,
            recordset_conduit.MonolithicRecordSetConduit, etag=record.etag)


    @eim.exporter(recordset_conduit.MonolithicRecordSetConduit)
    def export_sharing_monolithic_recordset_conduit(self, conduit):
        yield model.ShareMonolithicRecordSetConduitRecord(
            conduit,
            conduit.etag
        )

    @model.ShareWebDAVMonolithicRecordSetConduitRecord.importer
    def import_sharing_webdav_monolithic_recordset_conduit(self, record):
        self.withItemForUUID(record.uuid,
            webdav_conduit.WebDAVMonolithicRecordSetConduit
        )

    @eim.exporter(webdav_conduit.WebDAVMonolithicRecordSetConduit)
    def export_sharing_webdav_monolithic_recordset_conduit(self, conduit):
        yield model.ShareWebDAVMonolithicRecordSetConduitRecord(conduit)


    @model.ShareHTTPConduitRecord.importer
    def import_sharing_http_conduit(self, record):

        @self.withItemForUUID(record.uuid, conduits.HTTPMixin,
            ticket=record.ticket,
            ticketReadWrite=record.ticket_rw,
            ticketReadOnly=record.ticket_ro)
        def do(conduit):
            if record.account is not eim.NoChange:
                if record.account:
                    @self.withItemForUUID(record.account,
                        accounts.SharingAccount)
                    def do_account(account):
                        conduit.account = account
                else:
                    conduit.account = None
                    if record.host is not eim.NoChange:
                        conduit.host = record.host
                    if record.port is not eim.NoChange:
                        conduit.port = record.port
                    if record.ssl is not eim.NoChange:
                        conduit.useSSL = True if record.ssl else False
                    if record.username is not eim.NoChange:
                        conduit.username = record.username
                    if record.password not in (eim.NoChange, None):
                        @self.withItemForUUID(record.password, Password)
                        def do_password(password):
                            if hasattr(conduit, 'password'):
                                conduit.password.delete()
                            conduit.password = password

    @eim.exporter(conduits.HTTPMixin)
    def export_sharing_http_mixin(self, conduit):

        if self.obfuscation: return

        ticket = conduit.ticket
        ticket_rw = conduit.ticketReadWrite
        ticket_ro = conduit.ticketReadOnly

        if conduit.account:
            account = conduit.account.itsUUID
            host = None
            port = None
            ssl = None
            username = None
            password = None
        else:
            account = None
            host = conduit.host
            port = conduit.port
            ssl = 1 if conduit.useSSL else 0
            username = conduit.username
            password = getattr(conduit, "password", None)

        yield model.ShareHTTPConduitRecord(
            conduit,
            ticket,
            ticket_rw,
            ticket_ro,
            account,
            host,
            port,
            ssl,
            username,
            password
        )




    @model.ShareCosmoConduitRecord.importer
    def import_sharing_cosmo_conduit(self, record):

        self.withItemForUUID(record.uuid,
            cosmo.CosmoConduit,
            morsecodePath = record.morsecodepath
        )

    @eim.exporter(cosmo.CosmoConduit)
    def export_sharing_cosmo_conduit(self, conduit):

        if self.obfuscation: return

        yield model.ShareCosmoConduitRecord(
            conduit,
            conduit.morsecodePath
        )



    @model.ShareWebDAVConduitRecord.importer
    def import_sharing_webdav_conduit(self, record):

        self.withItemForUUID(record.uuid,
            webdav_conduit.WebDAVRecordSetConduit
        )

    @eim.exporter(webdav_conduit.WebDAVRecordSetConduit)
    def export_sharing_webdav_conduit(self, conduit):

        if self.obfuscation: return

        yield model.ShareWebDAVConduitRecord(
            conduit
        )




    @model.ShareStateRecord.importer
    def import_sharing_state(self, record):
        from osaf.dumpreload import UnknownRecord, PickleSerializer as ps

        agreed = eim.RecordSet()
        pending = eim.Diff()

        if record.stateRecords:
            stateRecords = ps.loads(record.stateRecords)

            # We only want to restore the agreed/pending state if there are
            # no unknown record types...  otherwise we just skip it.
            for rl in stateRecords:
                if any(r for r in rl if isinstance(r, UnknownRecord)):
                    break   
            else:
                agreed, inclusions, exclusions = stateRecords
                agreed = eim.RecordSet(agreed)
                pending = eim.Diff(inclusions, exclusions)

        @self.withItemForUUID(record.uuid,
            shares.State, agreed=agreed, pending=pending,
            pendingRemoval=bool(record.pendingRemoval)
        )
        def do(state):
            if record.share not in (eim.NoChange, None):

                @self.withItemForUUID(record.share, shares.Share)
                def do_share(share):

                    if state not in share.states:
                        share.states.append(state, record.alias)
                    state.peer = share

                    if record.conflict_share:
                        state.conflictingShare = share

            if record.conflict_item:
                @self.withItemForUUID(record.conflict_item, shares.SharedItem)
                def do_item(sharedItem):
                    state.conflictFor = sharedItem.itsItem

    @eim.exporter(shares.State)
    def export_sharing_state(self, state):
        from osaf.dumpreload import PickleSerializer as ps

        if self.obfuscation: return

        share = state.share.itsUUID if getattr(state, "share", None) else None
        if share is not None:
            alias = state.share.states.getAlias(state)
        else:
            alias = None

        conflict_item = getattr(state, "conflictFor", None)
        conflict_share = getattr(state, "conflictingShare", None)

        agreed = state.agreed
        pending = state.pending

        yield model.ShareStateRecord(
            state,
            share,
            alias,
            conflict_item,
            conflict_share,
            None,
            None,
            ps.dumps(
                map(list,
                   [agreed.inclusions, pending.inclusions, pending.exclusions]
                )
            ),
            1 if state.pendingRemoval else 0
        )



    @model.SharePeerStateRecord.importer
    def import_sharing_peer_state(self, record):

        @self.withItemForUUID(record.uuid, shares.State,
            peerRepoId=record.peerrepo,
            peerItemVersion=record.peerversion
        )
        def do(state):
            if record.peer not in (eim.NoChange, None):
                @self.withItemForUUID(record.peer, schema.Item)
                def do_peer(peer):
                    state.peer = peer

            if record.item not in (eim.NoChange, None):
                @self.withItemForUUID(record.item, shares.SharedItem)
                def do_item(sharedItem):
                    if not hasattr(sharedItem, 'peerStates'):
                        sharedItem.peerStates = []
                    if state not in sharedItem.peerStates:
                        sharedItem.peerStates.append(state, record.peer)

    # SharePeerStateRecords are generated in SharedItem's exporter


    @model.ShareSharedInRecord.importer
    def import_sharing_shared_in(self, record):

        @self.withItemForUUID(record.item, shares.SharedItem)
        def do_item(sharedItem):
            @self.withItemForUUID(record.share, shares.Share)
            def do_share(share):
                sharedItem.sharedIn.append(share)


    @eim.exporter(shares.SharedItem)
    def export_sharing_shared_item(self, sharedItem):

        if self.obfuscation: return

        for share in sharedItem.sharedIn:
            yield model.ShareSharedInRecord(
                sharedItem.itsItem,
                share
            )

        for state in getattr(sharedItem, "peerStates", []):
            alias = sharedItem.peerStates.getAlias(state)
            uuid = state
            peer = state.peer
            item = sharedItem.itsItem
            peerrepo = state.peerRepoId
            peerversion = state.peerItemVersion

            yield model.SharePeerStateRecord(
                uuid,
                peer,
                item,
                peerrepo,
                peerversion
            )

            if isinstance(peer, mail.EmailAddress):
                yield model.EmailAddressRecord(
                    peer,
                    peer.fullName,
                    peer.emailAddress
                )



    @model.ShareResourceStateRecord.importer
    def import_sharing_resource_state(self, record):

        self.withItemForUUID(record.uuid,
            recordset_conduit.ResourceState,
            path=record.path,
            etag=record.etag
        )

    @eim.exporter(recordset_conduit.ResourceState)
    def export_sharing_resource_state(self, state):

        if self.obfuscation: return

        path = getattr(state, "path", None)
        etag = getattr(state, "etag", None)

        yield model.ShareResourceStateRecord(
            state,
            path,
            etag
        )



    @model.ShareAccountRecord.importer
    def import_sharing_account(self, record):

        @self.withItemForUUID(record.uuid,
            accounts.SharingAccount,
            host=record.host,
            port=record.port,
            path=record.path,
            username=record.username
        )
        def do(account):
            if record.ssl not in (eim.NoChange, None):
                account.useSSL = True if record.ssl else False
            if record.password not in (eim.NoChange, None):
                @self.withItemForUUID(record.password, Password)
                def do_password(password):
                    if hasattr(account, 'password'):
                        account.password.delete()
                    account.password = password


    @eim.exporter(accounts.SharingAccount)
    def export_sharing_account(self, account):

        if self.obfuscation: return

        yield model.ShareAccountRecord(
            account,
            account.host,
            account.port,
            1 if account.useSSL else 0,
            account.path,
            account.username,
            getattr(account, "password", None)
        )




    @model.ShareWebDAVAccountRecord.importer
    def import_sharing_webdav_account(self, record):

        self.withItemForUUID(record.uuid,
            accounts.WebDAVAccount
        )

    @eim.exporter(accounts.WebDAVAccount)
    def export_sharing_webdav_account(self, account):

        if self.obfuscation: return

        yield model.ShareWebDAVAccountRecord(account)



    @model.ShareCosmoAccountRecord.importer
    def import_sharing_cosmo_account(self, record):

        self.withItemForUUID(record.uuid,
            cosmo.CosmoAccount,
            pimPath=record.pimpath,
            morsecodePath=record.morsecodepath,
            davPath=record.davpath
        )

    @eim.exporter(cosmo.CosmoAccount)
    def export_sharing_cosmo_account(self, account):

        if self.obfuscation: return

        yield model.ShareCosmoAccountRecord(
            account,
            account.pimPath,
            account.morsecodePath,
            account.davPath
        )



    @model.ShareHubAccountRecord.importer
    def import_sharing_hub_account(self, record):

        self.withItemForUUID(record.uuid, cosmo.HubAccount)

    @eim.exporter(cosmo.HubAccount)
    def export_sharing_hub_account(self, account):

        if self.obfuscation: return

        yield model.ShareHubAccountRecord(account)



    @model.ShareProxyRecord.importer
    def import_sharing_proxy(self, record):

        @self.withItemForUUID(record.uuid,
            accounts.Proxy,
            host=record.host,
            port=record.port,
            protocol=record.protocol,
            username=record.username,
            bypass=record.bypass,
        )
        def do(proxy):
            if record.useAuth not in (eim.NoChange, None):
                proxy.useAuth = True if record.useAuth else False
            if record.active not in (eim.NoChange, None):
                proxy.active = True if record.active else False
            if record.password not in (eim.NoChange, None):
                @self.withItemForUUID(record.password, Password)
                def do_password(password):
                    if hasattr(proxy, 'password'):
                        proxy.password.delete()
                    proxy.password = password


    @eim.exporter(accounts.Proxy)
    def export_sharing_proxy(self, proxy):

        if self.obfuscation: return

        yield model.ShareProxyRecord(proxy,
            proxy.host,
            proxy.port,
            proxy.protocol,
            1 if proxy.useAuth else 0,
            proxy.username,
            getattr(proxy, "password", None),
            1 if proxy.active else 0,
            proxy.bypass
        )







    # - - Mail-related items - - - - - - - - - - - - - - - - - - - - - -


    @model.MailAccountRecord.importer
    def import_mail_account(self, record):
        @self.withItemForUUID(record.uuid,
            mail.AccountBase,
            host=record.host,
            username=record.username,
            numRetries=record.retries,
            pollingFrequency=record.frequency,
            #Timeout removed from MailStamp schema
            #timeout=record.timeout,
        )
        def do(account):
            if record.connectionType not in (eim.NoChange, None):
                account.connectionSecurity = record.connectionType == 0 and 'NONE' or \
                                             record.connectionType == 1 and 'TLS' or 'SSL'

            if record.active not in (eim.NoChange, None):
                account.isActive = record.active == 1

    @eim.exporter(mail.AccountBase)
    def export_mail_account(self, account):

        if self.obfuscation: return

        connectionType = 0

        if account.connectionSecurity == "TLS":
            connectionType = 1
        elif account.connectionSecurity == "SSL":
            connectionType = 2

        yield model.MailAccountRecord(
            account,
            account.numRetries,
            account.username,
            account.host,
            connectionType,
            account.pollingFrequency,
            #Timeout removed from MailStamp schema
            None,
            account.isActive and 1 or 0,)


    @model.SMTPAccountRecord.importer
    def import_smtp_account(self, record):
        @self.withItemForUUID(record.uuid, mail.SMTPAccount)
        def do(account):
            if record.password not in (eim.NoChange, None):
                @self.withItemForUUID(record.password, Password)
                def do_password(password):
                    if hasattr(account, 'password'):                    
                        account.password.delete()
                    account.password = password

            if record.useAuth not in (eim.NoChange, None):
                account.useAuth = record.useAuth == 1

            if record.fromAddress not in (eim.NoChange, None):
                account.fromAddress = getEmailAddress(self.rv, record.fromAddress)

            if record.port not in (eim.NoChange, None):
                account.port = record.port

            if record.isDefault not in (eim.NoChange, None) and \
                record.isDefault:
                ns = schema.ns("osaf.pim", self.rv)

                oldAccount = getattr(ns.currentOutgoingAccount, "item", None)

                if oldAccount and not oldAccount.host.strip():
                    # The current account is empty
                    oldAccount.isActive = False

                ns.currentOutgoingAccount.item = account

    @eim.exporter(mail.SMTPAccount)
    def export_smtp_account(self, account):

        if self.obfuscation: return

        ns = schema.ns("osaf.pim", self.rv)

        if hasattr(account, "fromAddress") and account.fromAddress:
            fromAddress = account.fromAddress.format()
        else:
            fromAddress = None

        currentOutgoing = getattr(ns.currentOutgoingAccount, "item", None)

        isDefault = currentOutgoing == account and 1 or 0

        yield model.SMTPAccountRecord(
            account,
            getattr(account, 'password', None),
            fromAddress,
            account.useAuth and 1 or 0,
            account.port,
            isDefault)

        for record in self.export_smtp_account_queue(account):
            yield record

    def export_smtp_account_queue(self, account):
        for msg in account.messageQueue:
            yield model.SMTPAccountQueueRecord(
                    account,
                    msg.itsUUID,)

    @model.SMTPAccountQueueRecord.importer
    def import_smtp_account_queue(self, record):
        @self.withItemForUUID(record.smtpAccountUUID)
        def do(account):
            @self.withItemForUUID(record.itemUUID, pim.ContentItem)
            def do(item):
                account.messageQueue.append(item)

    @model.IMAPAccountRecord.importer
    def import_imap_account(self, record):
        @self.withItemForUUID(record.uuid, mail.IMAPAccount)
        def do(account):
            #The Inbox is created by default so clear it out
            inbox = account.folders.first()
            account.folders = []
            inbox.delete()

            if record.password not in (eim.NoChange, None):
                @self.withItemForUUID(record.password, Password)
                def do_password(password):
                    if hasattr(account, 'password'):
                        account.password.delete()
                    account.password = password

            if record.replyToAddress not in (eim.NoChange, None):
                account.replyToAddress = getEmailAddress(self.rv, record.replyToAddress)

            if record.port not in (eim.NoChange, None):
                account.port = record.port

            if record.isDefault not in (eim.NoChange, None) and \
                record.isDefault:
                ns = schema.ns("osaf.pim", self.rv)

                oldAccount = getattr(ns.currentIncomingAccount, "item", None)

                if oldAccount and not oldAccount.host.strip():
                    # The current account is empty
                    oldAccount.isActive = False

                ns.currentIncomingAccount.item = account


    @eim.exporter(mail.IMAPAccount)
    def export_imap_account(self, account):

        if self.obfuscation: return

        ns = schema.ns("osaf.pim", self.rv)

        if hasattr(account, "replyToAddress") and account.replyToAddress:
            replyToAddress = account.replyToAddress.format()
        else:
            replyToAddress = None

        currentIncoming = getattr(ns.currentIncomingAccount, "item", None)

        isDefault = currentIncoming == account and 1 or 0

        yield model.IMAPAccountRecord(
            account,
            getattr(account, 'password', None),
            replyToAddress,
            account.port,
            isDefault)

        for record in self.export_imap_account_folders(account):
            yield record

    def export_imap_account_folders(self, account):
        for folder in account.folders:
            yield model.IMAPAccountFoldersRecord(
                    account,
                    folder.itsUUID,)

    @model.IMAPAccountFoldersRecord.importer
    def import_imap_account_folders(self, record):
        @self.withItemForUUID(record.imapAccountUUID)
        def do(account):
            @self.withItemForUUID(record.imapFolderUUID, mail.IMAPFolder)
            def do(folder):
                account.folders.append(folder)


    @model.IMAPFolderRecord.importer
    def import_imap_folder(self, record):
        @self.withItemForUUID(record.uuid, mail.IMAPFolder,
                              folderName=record.name,
                              folderType=record.type,
                              lastMessageUID=record.lastUID,
                              downloaded=record.downloaded,
                              downloadMax=record.downloadMax)
        def do(folder):
            folder.deleteOnDownload = record.delete == 1


    @eim.exporter(mail.IMAPFolder)
    def export_imap_folder(self, folder):

        if self.obfuscation: return

        yield model.IMAPFolderRecord(
            folder,
            folder.folderName,
            folder.folderType,
            folder.lastMessageUID,
            folder.deleteOnDownload and 1 or 0,
            folder.downloaded,
            folder.downloadMax,
        )

    @model.POPAccountRecord.importer
    def import_pop_account(self, record):
        @self.withItemForUUID(record.uuid, mail.POPAccount,
                              actionType=record.type,
                              downloaded=record.downloaded,
                              downloadMax=record.downloadMax)
        def do(account):
            if record.password not in (eim.NoChange, None):
                @self.withItemForUUID(record.password, Password)
                def do_password(password):
                    if hasattr(account, 'password'):
                        account.password.delete()
                    account.password = password

            if record.replyToAddress not in (eim.NoChange, None):
                account.replyToAddress = getEmailAddress(self.rv, record.replyToAddress)

            if record.delete not in (eim.NoChange, None):
                account.deleteOnDownload = record.delete == 1

            account.seenMessageUIDS = {}

            if record.seenUIDS not in (eim.NoChange, None):
                uids = record.seenUIDS.split("\n")

                for uid in uids:
                    account.seenMessageUIDS[uid] = "True"

            if record.port not in (eim.NoChange, None):
                account.port = record.port

            if record.isDefault not in (eim.NoChange, None) and \
                record.isDefault:
                ns = schema.ns("osaf.pim", self.rv)

                oldAccount = getattr(ns.currentIncomingAccount, "item", None)

                if oldAccount and not oldAccount.host.strip():
                    # The current account is empty
                    oldAccount.isActive = False

                ns.currentIncomingAccount.item = account


    @eim.exporter(mail.POPAccount)
    def export_pop_account(self, account):

        if self.obfuscation: return

        ns = schema.ns("osaf.pim", self.rv)

        if hasattr(account, "replyToAddress") and account.replyToAddress:
            replyToAddress = account.replyToAddress.format()
        else:
            replyToAddress = None

        seenUIDS = []

        for uid in account.seenMessageUIDS:
            seenUIDS.append(uid)

        if seenUIDS:
            seenUIDS = "\n".join(seenUIDS)
        else:
            seenUIDS = None

        currentIncoming = getattr(ns.currentIncomingAccount, "item", None)

        isDefault = currentIncoming == account and 1 or 0

        yield model.POPAccountRecord(
            account,
            getattr(account, 'password', None),
            replyToAddress,
            account.actionType,
            account.deleteOnDownload and 1 or 0,
            account.downloaded,
            account.downloadMax,
            seenUIDS,
            account.port,
            isDefault,
        )



    @model.MailPrefsRecord.importer
    def import_mail_prefs(self, record):
        if record.isOnline not in (eim.NoChange, None):
            isOnline = record.isOnline == 1
            schema.ns("osaf.pim", self.rv).MailPrefs.isOnline = isOnline


        if record.meAddressHistory not in (eim.NoChange, None):
            col = schema.ns("osaf.pim", self.rv).meEmailAddressCollection
            addresses = record.meAddressHistory.split("\n")

            for address in addresses:
                col.append(getEmailAddress(self.rv, address))

    # Called from finishExport()
    def export_mail_prefs(self):
        isOnline = schema.ns("osaf.pim", self.rv).MailPrefs.isOnline and 1 or 0
        col = schema.ns("osaf.pim", self.rv).meEmailAddressCollection

        meAddressHistory = []

        for ea in col:
            meAddressHistory.append(ea.format())

        if meAddressHistory:
            meAddressHistory = "\n".join(meAddressHistory)
        else:
            meAddressHistory = None

        yield model.MailPrefsRecord(isOnline, meAddressHistory)



    @model.EmailAddressRecord.importer
    def import_email_address(self, record):
        self.withItemForUUID(record.uuid, mail.EmailAddress,
            fullName=record.fullName, emailAddress=record.address)

    # Currently, EmailAddressRecords are only yielded from SharedItem exporter



    # - - Preference items - - - - - - - - - - - - - - - - - - - - - - - - - -

    @model.PrefCalendarHourHeightRecord.importer
    def import_prefcalendarhourheight(self, record):
        pref = schema.ns('osaf.framework.blocks.calendar',
            self.rv).calendarPrefs
        pref.hourHeightMode = record.hourHeightMode
        pref.visibleHours = record.visibleHours

    # Called from finishExport( )
    def export_prefcalendarhourheight(self):
        pref = schema.ns('osaf.framework.blocks.calendar',
            self.rv).calendarPrefs

        yield model.PrefCalendarHourHeightRecord(
            pref.hourHeightMode,
            pref.visibleHours
        )

    @model.PrefTimezonesRecord.importer
    def import_preftimezones(self, record):

        pref = schema.ns('osaf.pim', self.rv).TimezonePrefs
        pref.showUI = bool(record.showUI)
        pref.showPrompt = bool(record.showPrompt)

        tzitem = TimeZone.TimeZoneInfo.get(self.rv)
        tzitem.default = self.rv.tzinfo.getInstance(record.default)
        tzitem.wellKnownIDs = record.wellKnownIDs.split(',')

    # Called from finishExport( )
    def export_preftimezones(self):

        pref = schema.ns('osaf.pim', self.rv).TimezonePrefs
        tzitem = TimeZone.TimeZoneInfo.get(self.rv)
        yield model.PrefTimezonesRecord(
            pref.showUI,
            pref.showPrompt,
            TimeZone.olsonizeTzinfo(self.rv, tzitem.default).tzid,
            ",".join(tzitem.wellKnownIDs)
        )


    @model.ApplicationPrefsRecord.importer
    def import_application_prefs(self, record):
        prefs = schema.ns("osaf.app", self.rv).prefs
        prefs.isOnline = bool(record.isOnline)

        backup = getattr(record, "backupOnQuit", 0)
        if backup == 1:
            prefs.backupOnQuit = True
        elif backup == 2:
            prefs.backupOnQuit = False

        prefs.showTip = bool(record.showTip)
        prefs.tipIndex = record.tipIndex

    # Called from finishExport()
    def export_application_prefs(self):
        prefs = schema.ns("osaf.app", self.rv).prefs
        
        backup = getattr(prefs, "backupOnQuit", None)
        if backup is None:
            backup = 0
        elif backup == True:
            backup = 1
        elif backup == False:
            backup = 2

        yield model.ApplicationPrefsRecord(1 if prefs.isOnline else 0,
                                           backup,
                                           1 if prefs.showTip else 0,
                                           prefs.tipIndex)

    @model.SharePrefsRecord.importer
    def import_share_prefs(self, record):
        prefs = schema.ns("osaf.sharing", self.rv).prefs
        prefs.isOnline = bool(record.isOnline)

    # Called from finishExport()
    def export_share_prefs(self):
        prefs = schema.ns("osaf.sharing", self.rv).prefs
        yield model.SharePrefsRecord(1 if prefs.isOnline else 0)


    # - - Finishing up - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

    def finishImport(self):
        super(DumpTranslator, self).finishImport()
        ootb.prepareAccounts(self.rv)


    def finishExport(self):
        for record in super(DumpTranslator, self).finishExport():
            yield record

        # emit the CollectionMembership records for the sidebar collection
        for record in self.export_collection_memberships(schema.ns("osaf.app",
            self.rv).sidebarCollection):
            yield record

        # emit the DashboardMembership records
        for item in schema.ns("osaf.pim", self.rv).allCollection.inclusions:
            if (not str(item.itsPath).startswith("//parcels") and
                not isinstance(item, Occurrence)):
                yield model.DashboardMembershipRecord(item)

        # emit the TrashMembership records
        for item in schema.ns("osaf.pim", self.rv).trashCollection.inclusions:
            if (not str(item.itsPath).startswith("//parcels") and
                not isinstance(item, Occurrence)):
                yield model.TrashMembershipRecord(item)

        if not self.obfuscation:

            # mail
            for record in self.export_mail_prefs():
                yield record

            # calendar prefs
            for record in self.export_prefcalendarhourheight():
                yield record
            for record in self.export_preftimezones():
                yield record

            # passwords prefs
            for record in self.export_password_prefs():
                yield record

            # sharing prefs
            for record in self.export_share_prefs():
                yield record

            # application prefs
            for record in self.export_application_prefs():
                yield record

            # update prefs
            for record in self.export_update_prefs():
                yield record

            # auto-restore prefs
            for record in self.export_autorestore_prefs():
                yield record

            # client id
            for record in self.export_client_id():
                yield record



def test_suite():
    import doctest, __future__
    return doctest.DocFileSuite(
        'Translator.txt',
        globs={'with_statement': __future__.with_statement},
        optionflags=doctest.ELLIPSIS|doctest.REPORT_ONLY_FIRST_FAILURE,
    )

