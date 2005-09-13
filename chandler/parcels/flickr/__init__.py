__version__ = "$Revision: $"
__date__ = "$Date:  $"
__copyright__ = "Copyright (c) 2005 Open Source Applications Foundation"
__license__ = "http://osafoundation.org/Chandler_0.1_license_terms.htm"

import application.dialogs.Util
import application.Globals as Globals
from application import schema
import flickr
from osaf import pim
from photos import PhotoMixin
import osaf.framework.blocks.Block as Block
import osaf.framework.blocks.detail.Detail as Detail
from osaf.pim.collections import KindCollection, FilteredCollection
from repository.util.URL import URL
from datetime import datetime
import dateutil
import wx
import os, logging
from i18n import OSAFMessageFactory as _

#XXX[i18n] this file needs to have displayName converted to _()

logger = logging.getLogger(__name__)


class FlickrPhotoMixin(PhotoMixin):

    schema.kindInfo(displayName="Flickr Photo Mixin",
                    displayAttribute="displayName")

    flickrID = schema.One(schema.String, displayName=_("Flickr ID"))
    imageURL = schema.One(schema.URL, displayName=_("imageURL"))
    datePosted = schema.One(schema.DateTime, displayName=_("Upload Date"))
    tags = schema.Sequence(displayName=_("Tag"))
    owner = schema.One(schema.String, displayName=_("owner"))

    # about = schema.Role(redirectTo="title")
    who = schema.One(redirectTo="owner")

    schema.addClouds(sharing = schema.Cloud(owner, flickrID, imageURL, tags))

    def __init__(self, photo=None,*args,**kwargs):
        super(FlickrPhotoMixin,self).__init__(*args,**kwargs)
        if photo:
            self.populate(photo)

    def populate(self, photo):
        #XXX: [i18n] why are these encoding in ascii why not utf-8?
        self.flickrID = photo.id.encode('ascii', 'replace')
        self.displayName = photo.title.encode('ascii', 'replace')
        self.description = photo.description.encode('ascii', 'replace')
        self.owner = photo.owner.realname.encode('ascii', 'replace')
        self.imageURL = URL(photo.getURL(urlType="source"))
        self.datePosted = datetime.utcfromtimestamp(int(photo.dateposted))
        self.dateTaken = dateutil.parser.parse(photo.datetaken)
        try:
            if photo.tags:
                self.tags = [Tag.getTag(self.itsView, tag.text) for tag in photo.tags]
        except Exception, e:
            print "tags failed", e
        self.importFromURL(self.imageURL)

class FlickrPhoto(FlickrPhotoMixin, pim.Note):
    schema.kindInfo(displayName = _("Flickr Photo"))

#copied from Location class
class Tag(pim.ContentItem):

    schema.kindInfo(displayName=_("Flickr Tag"))

    itemsWithTag = schema.Sequence(FlickrPhotoMixin, inverse=FlickrPhotoMixin.tags, displayName=_("Tag"))

    def __str__ (self):
        """
          User readable string version of this Tag
        """
        #XXX: [i18n] displayName will be unicode. Should need __unicode__ method
        #     and will need to encode displayName to str but is this the correct behavior?
        if self.isStale():
            return super(Tag, self).__str__()
            # Stale items can't access their attributes
        return self.getItemDisplayName ()

    def getTag (cls, view, tagName):
        """
        Factory Method for getting a Tag.

        Lookup or create a Tag based on the supplied name string.

        If a matching Tag object is found in the repository, it
        is returned.  If there is no match, then a new item is created
        and returned.  

        @param tagName: name of the Tag
        @type tagName: C{String}
        @return: C{Tag} created or found
        """
        # make sure the tagName looks reasonable
        assert tagName, "Invalid tagName passed to getTag factory"

        # get all Tag objects whose displayName match the param
        # return the first match found, if any
        for i in Tag.iterItems(view, exact=True):
            if i.displayName == tagName:
                return i

        # make a new Tag
        newTag = Tag(view=view)
        newTag.displayName = tagName
        return newTag

    getTag = classmethod (getTag)
    
def getPhotoByFlickrID(view, id):
    try:
        for x in FlickrPhotoMixin.iterItems(view, exact=True):
            if x.flickrID == id:
                return x
    except:
        return None

def getPhotoByFlickrTitle(view, title):
    photos = KindCollection('FlickrPhotoQuery', FlickrPhotoMixin)
    filteredPhotos = FilteredCollection('FilteredFlicrkPhotoQuery', photos)
    for x in filteredPhotos:
        return x

class PhotoCollection(pim.ContentItem):

    schema.kindInfo(displayName=_("Collection of Flickr Photos"))

    photos = schema.Sequence(FlickrPhotoMixin, displayName=_("Flickr Photos"))
    username = schema.One(
        schema.String, displayName=_("Username"), initialValue=''
    )
    tag = schema.One(
        Tag, otherName="itemsWithTag", displayName="Tag", initialValue=None
    )
       
    def getCollectionFromFlickr(self,repView):
        coll = pim.ListCollection(view = repView)
        if self.username:
            flickrUsername = flickr.people_findByUsername(self.username)
            flickrPhotos = flickr.people_getPublicPhotos(flickrUsername.id,10)
            coll.displayName = self.username
        elif self.tag:
            flickrPhotos = flickr.photos_search(tags=self.tag,per_page=10,sort="date-posted-desc")
            coll.displayName = self.tag.displayName
            
        self.sidebarCollection = coll

        for i in flickrPhotos:
            photoItem = getPhotoByFlickrID(repView, i.id)
            if photoItem is None:
                photoItem = FlickrPhoto(photo=i,view=repView,parent=coll)
            coll.add(photoItem)
        repView.commit()

    def update(self,repView):
        self.getCollectionFromFlickr(repView)

#
# Block related code
#

class FlickrCollectionController(Block.Block):
    def onNewFlickrCollectionByOwnerEvent(self, event):
        return CreateCollectionFromUsername(self.itsView, Globals.views[0])

    def onNewFlickrCollectionByTagEvent(self, event):
        return CreateCollectionFromTag(self.itsView, Globals.views[0])

def CreateCollectionFromUsername(repView, cpiaView):
    username = application.dialogs.Util.promptUser(wx.GetApp().mainFrame,
                                                   _("Username"),
                                                   _("Enter a Flickr Username"),
                                                   "")
    if username:
        myPhotoCollection = PhotoCollection(view = repView)
        myPhotoCollection.username = username
        try:
            myPhotoCollection.getCollectionFromFlickr(repView)

            # Add the channel to the sidebar
            return cpiaView.postEventByName('AddToSidebarWithoutCopying',
                                     {'items': [myPhotoCollection.sidebarCollection]})
        except flickr.FlickrError, fe: 
            #XXX: [i18n] will need to capture exception and localize error text
            application.dialogs.Util.ok(wx.GetApp().mainFrame,
                                        _("Flickr Error"),
                                        str(fe))

def CreateCollectionFromTag(repView, cpiaView):
    tagstring = application.dialogs.Util.promptUser(wx.GetApp().mainFrame,
                                                   _("Tag"),
                                                   _("Enter a Flickr Tag"),
                                                   "")
    if tagstring:
        myPhotoCollection = PhotoCollection(view = repView)
        myPhotoCollection.tag = Tag.getTag(repView, tagstring)
        try:
            myPhotoCollection.getCollectionFromFlickr(repView)

            # Add the channel to the sidebar
            return cpiaView.postEventByName('AddToSidebarWithoutCopying',
                                     {'items': [myPhotoCollection.sidebarCollection]})
        except flickr.FlickrError, fe:
            application.dialogs.Util.ok(wx.GetApp().mainFrame,
                                        _("Flickr Error"),
                                        str(fe))

#
# Wakeup caller
#

class UpdateTask:
    def __init__(self, item):
        self.view = item.itsView

    def run(self):
        logger.info("receiveWakeupCall()")

        # We need the view for most repository operations
        self.view.refresh()

        # We need the Kind object for PhotoCollection
        for myPhotoCollection in PhotoCollection.iterItems(self.view):
            myPhotoCollection.update(self.view)

        # We want to commit the changes to the repository
        self.view.commit()
        return True

from osaf.framework.blocks.Block import BlockEvent
from osaf.framework.blocks.MenusAndToolbars import MenuItem
from osaf.startup import PeriodicTask
from datetime import timedelta

def installParcel(parcel, oldVersion=None):

    controller = FlickrCollectionController.update(parcel, 'FlickrCollectionControllerItem')

    ownerEvent = BlockEvent.update(parcel, 'NewFlickrCollectionByOwnerEvent',
                      blockName = 'NewFlickrCollectionByOwner',
                      dispatchEnum = 'SendToBlockByReference',
                      destinationBlockReference = controller,
                      commitAfterDispatch = True)

    tagEvent = BlockEvent.update(parcel, 'NewFlickrCollectionByTagEvent',
                      blockName = 'NewFlickrCollectionByTag',
                      dispatchEnum = 'SendToBlockByReference',
                      destinationBlockReference = controller,
                      commitAfterDispatch = True)

    newItemMenu = schema.ns('osaf.views.main', parcel).NewItemMenu

    MenuItem.update(parcel, 'NewFlickrCollectionByOwner',
                    blockName = 'NewFlickrCollectionByOwnerItem',
                    title = 'New Flickr Collection by Owner',
                    event = ownerEvent,
                    parentBlock = newItemMenu)
 
    MenuItem.update(parcel, 'NewFlickrCollectionByTag',
                    blockName = 'NewFlickrCollectionByTagItem',
                    title = 'New Flickr Collection by Tag',
                    event = tagEvent,
                    parentBlock = newItemMenu)


    PeriodicTask.update(parcel, 'FlickrUpdateTask',
                        invoke = 'osaf.examples.flickr.UpdateTask',
                        run_at_startup = True,
                        interval = timedelta(minutes=2))


    blocks = schema.ns('osaf.framework.blocks', parcel)
    detail = schema.ns('osaf.framework.blocks.detail', parcel)

    detail.DetailTrunkSubtree.update(parcel, "flickr_detail_view",
        key = FlickrPhoto.getKind(parcel.itsView),
        rootBlocks = [
            detail.DetailSynchronizedLabeledTextAttributeBlock.update(
                parcel, "AuthorArea",
                position = 0.6,
                viewAttribute="owner",
                stretchFactor = 0,
                childrenBlocks = [
                    detail.StaticRedirectAttributeLabel.update(
                        parcel, "AuthorLabel",
                        title = "author",
                        characterStyle = blocks.LabelStyle,
                        stretchFactor = 0.0,
                        textAlignmentEnum = "Right",
                        minimumSize = blocks.SizeType(70, 24),
                        border = blocks.RectType(0.0, 0.0, 0.0, 5.0),
                    ),
                    detail.StaticRedirectAttribute.update(
                        parcel  , "AuthorAttribute",
                        title = "author",
                        characterStyle = blocks.LabelStyle,
                        stretchFactor = 0.0,
                        textAlignmentEnum = "Left",
                    ),
                ]
            )
        ]
    )


