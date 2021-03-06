#   Copyright (c) 2003-2007 Open Source Applications Foundation
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


__parcel__ = "osaf.framework.blocks"

from application import schema
import wx
import logging
from osaf.pim.structs import ColorType

logger = logging.getLogger(__name__)

class fontFamilyEnumType(schema.Enumeration):
    values = "DefaultUIFont", "SerifFont", "SansSerifFont", "FixedPitchFont"


class Style(schema.Item):
    pass

class CharacterStyle(Style):

    fontFamily = schema.One(
        fontFamilyEnumType, initialValue = 'DefaultUIFont',
    )

    # we default to 11 points, which'll get scaled to the platform's
    # default GUI font
    fontSize = schema.One(schema.Float, initialValue = 11.0)

    # Currently, fontStyle is a string containing any of the following words:
    # bold light italic underline fakesuperscript
    # but others will be included in the future
    fontStyle = schema.One(schema.Text, initialValue = '')

    fontName = schema.One(schema.Text, initialValue = '')

class ColorStyle(Style):
    """ 
    Class for Color Style
    Attributes for backgroundColor and foregroundColor
    """

    foregroundColor = schema.One(
        ColorType, initialValue = ColorType(0, 0, 0, 255),
    )

    backgroundColor = schema.One(
        ColorType, initialValue = ColorType(255, 255, 255, 255),
    )

    schema.addClouds(
        sharing = schema.Cloud(literal=[foregroundColor, backgroundColor])
    )

        
fontCache = {}
measurementsCache = {}

platformDefaultFaceName = None
platformDefaultFamily = None
platformSizeScalingFactor = 0.0

# "Fake" superscript (implemented in this file, wx doesn't seem to have any
# concept of super- or subscripting) is smaller, but its top is supposed to
# line up with non-fakesuperscript text.
#
# NB: unlike normal text, the CharacterStyle.fontSize will be different
# (bigger) than the post-scaling height reported by dc.GetTextExtent(), since wx
# fonts don't know about super/subscriptness.

fakeSuperscriptSizeScalingFactor = 0.7

# We default to an 11-point font, which gets scaled by the size of the
# platform's default GUI font (which we measured just above). It's 11
# because that's the size of the Mac's default GUI font, which is what
# Mimi thinks in terms of. (It's a float so the math works out.)
rawDefaultFontSize = 11.0

def getFont(characterStyle=None, family=None, size=rawDefaultFontSize, 
            style=wx.NORMAL, underline=False, weight=wx.NORMAL, name=""):
    """
    Retrieve a font, using a CharacterStyle item or discrete specifications.
    Scales the requested point size relative to the idealized 11-point size 
    on Mac that Mimi bases her specs on.
    """
    # Check the cache if we're using a style that we've used before
    if characterStyle is not None:
        key = getattr(characterStyle, 'fontKey', None)
        if key is not None:
            font = fontCache.get(key)
            if font is not None:
                return font
            
    # First time, get a couple of defaults
    global platformDefaultFaceName, platformDefaultFamily, platformSizeScalingFactor
    if platformDefaultFaceName is None:
        defaultGuiFont = wx.SystemSettings_GetFont(wx.SYS_DEFAULT_GUI_FONT)
        platformDefaultFaceName = defaultGuiFont.GetFaceName()
        platformDefaultFamily = defaultGuiFont.GetFamily()
        platformSizeScalingFactor = \
            defaultGuiFont.GetPointSize() / rawDefaultFontSize
        
    family = family or platformDefaultFamily
    
    if characterStyle is not None:
        size = characterStyle.fontSize
        name = characterStyle.fontName        

        if characterStyle.fontFamily == "SerifFont":
            family = wx.ROMAN
        elif characterStyle.fontFamily == "SanSerifFont":
            family = wx.SWISS
        elif characterStyle.fontFamily == "FixedPitchFont":
            family = wx.MODERN
                    
        for theStyle in characterStyle.fontStyle.split():
            lowerStyle = theStyle.lower()
            if lowerStyle == "bold":
                weight = wx.BOLD
            elif lowerStyle == "light":
                weight = wx.LIGHT
            elif lowerStyle == "italic":
                style = wx.ITALIC
            elif lowerStyle == "underline":
                underline = True
            elif lowerStyle == "fakesuperscript":
                size *= fakeSuperscriptSizeScalingFactor
        
    if family == platformDefaultFamily:
        name = platformDefaultFaceName

    # Scale the requested size by the platform's scaling factor (then round to int)
    scaledSize = int((platformSizeScalingFactor * size) + 0.5)
    
    # Do we have this already?
    key = (scaledSize, family, style, weight, underline)
    font = fontCache.get(key)
    if font is None:
        font = wx.Font(scaledSize, family, style, weight, underline, name)
        # For a while, this assert was commented out, saying: "Don't do this 
        # for now: it upsets Linux". It doesn't seem to be upsetting Linux
        # anymore, so I'm putting it back.
        assert key == getFontKey(font)
        
        # Put the key in the font, as well as the characterStyle if we have one;
        # they'll let us shortcut the lookup process later.
        font.fontKey = key
        if characterStyle is not None:
            characterStyle.fontKey = key
        
        fontCache[key] = font

    return font

def getFontKey(font):
    key = getattr(font, 'fontKey', None)
    if key is None:
        key = (font.GetPointSize(), font.GetFamily(), font.GetStyle(), 
               font.GetWeight(), font.GetUnderlined())
    return key
    
def getMeasurements(font):
    key = getFontKey(font)
    try:
        m = measurementsCache[key]
    except KeyError:
        m = FontMeasurements(font)
        measurementsCache[key] = m
    return m

class FontMeasurements(object):
    """ Measurements that we cache with each font """    
    def __init__(self, font):
        aWidget = wx.GetApp().mainFrame
        dc = wx.ClientDC(aWidget)
        oldWidgetFont = aWidget.GetFont()
        try:
            dc.SetFont(font)
            aWidget.SetFont(font)

            self.height = self.descent = self.leading = 0
            (ignored, self.height, self.descent, self.leading) = \
             dc.GetFullTextExtent("M", font)
            self.spaceWidth = dc.GetFullTextExtent(" ", font)[0]

            # @@@ These result in too-big boxes - so fake it.
            if False:
                # How big is an instance of each of these controls with this font?
                for (fieldName, ctrl) in {
                    'textCtrlHeight': wx.TextCtrl(aWidget, -1, '', wx.DefaultPosition,
                                                  wx.DefaultSize, wx.STATIC_BORDER),
                    'choiceCtrlHeight': wx.Choice(aWidget, -1, wx.DefaultPosition,
                                                  wx.DefaultSize, ['M']),
                    'checkboxCtrlHeight': wx.CheckBox(aWidget, -1, 'M')
                    }.items():
                    setattr(self, fieldName, ctrl.GetSize()[1])
                    ctrl.Destroy()
                
                # We end up just getting the size of the box if we ask a checkbox,
                # so make sure we're at least as big as the text
                self.checkboxCtrlHeight += self.descent
            else:
                self.textCtrlHeight = self.height + 6
                self.choiceCtrlHeight = self.height + 8
                self.checkboxCtrlHeight  = self.height + 6
            
            # Don't need to worry about descenders/leaders bcs digits dont have 'em (i think?)
            # Lots of proportional fonts seem to have monospaced digits, so using
            #  max() instead of random.choice() is just safety
            
            digitDimensions = [dc.GetTextExtent(str(digit)) for digit in range(10)]
            self.digitWidth  = max([w for w,h in digitDimensions])
            self.digitHeight = max([h for w,h in digitDimensions])

        finally:
            aWidget.SetFont(oldWidgetFont)
            
def testFonts():
    # To try to work out font differences between the platforms, I wrote the
    # following: 
    # 
    # Gather info about each of wx's "specified" defaults:
    for fam in wx.SYS_DEFAULT_GUI_FONT, wx.SYS_OEM_FIXED_FONT, \
        wx.SYS_ANSI_FIXED_FONT, wx.SYS_ANSI_VAR_FONT, wx.SYS_SYSTEM_FONT, \
        wx.SYS_DEVICE_DEFAULT_FONT, wx.SYS_SYSTEM_FONT:
        f = wx.SystemSettings_GetFont(fam)
        logger.debug("%d -> %s, %s %s (%s)" % (fam, f.GetFamily(), f.GetFaceName(), f.GetPointSize(), f.GetFamilyString()))
        
    # Also see what a completely-default Font looks like
    f = wx.Font(12, wx.DEFAULT, wx.NORMAL, wx.NORMAL, False, "")
    logger.debug("default -> %s, %s %s (%s)" % (f.GetFamily(), f.GetFaceName(), f.GetPointSize(), f.GetFamilyString()))
    # On Mac, where the grid uses Lucida Grande 13 when no font is specified, this says:
    #2005-05-09 13:53:43,536 styles DEBUG: 17 -> 70, Lucida Grande 11 (wxDEFAULT)
    #2005-05-09 13:53:43,548 styles DEBUG: 10 -> 70, Lucida Grande 13 (wxDEFAULT)
    #2005-05-09 13:53:43,550 styles DEBUG: 11 -> 70, Lucida Grande 13 (wxDEFAULT)
    #2005-05-09 13:53:43,552 styles DEBUG: 12 -> 70, Lucida Grande 11 (wxDEFAULT)
    #2005-05-09 13:53:43,553 styles DEBUG: 13 -> 70, Lucida Grande 11 (wxDEFAULT)
    #2005-05-09 13:53:43,555 styles DEBUG: 14 -> 70, Lucida Grande 11 (wxDEFAULT)
    #2005-05-09 13:53:43,557 styles DEBUG: 13 -> 70, Lucida Grande 11 (wxDEFAULT)
    #2005-05-09 13:53:43,559 styles DEBUG: default -> 70, Geneva 12 (wxDEFAULT)
    #
    # and this on PC, where the grid uses MS Shell Dlg 8 by default
    #2005-05-09 13:53:24,812 styles DEBUG: 17 -> 74, MS Shell Dlg 8 (wxSWISS)
    #2005-05-09 13:53:24,812 styles DEBUG: 10 -> 74, Terminal 9 (wxSWISS)
    #2005-05-09 13:53:24,812 styles DEBUG: 11 -> 74, Courier 9 (wxSWISS)
    #2005-05-09 13:53:24,812 styles DEBUG: 12 -> 74, MS Sans Serif 9 (wxSWISS)
    #2005-05-09 13:53:24,812 styles DEBUG: 13 -> 74, System 12 (wxSWISS)
    #2005-05-09 13:53:24,812 styles DEBUG: 14 -> 74, System 12 (wxSWISS)
    #2005-05-09 13:53:24,812 styles DEBUG: 13 -> 74, System 12 (wxSWISS)
    #2005-05-09 13:53:24,812 styles DEBUG: default -> 70, MS Sans Serif 12 (wxDEFAULT)
    #2005-05-09 13:53:24,812 styles DEBUG: got font: 70 12.0 -> MS Shell Dlg 8 (wxDEFAULT)    
    #
    # This is interesting because you'd expect the grid to be using one of the
    # selectors above, but it's not: you only get Lucida Grande 13 if you specify
    # SYS_OEM_FIXED_FONT or SYS_ANSI_FIXED_FONT on Mac, and you only get MS Shell
    # Dlg 8 on the PC if you specify DEFAULT_GUI_FONT or use a "completely-default"
    # font.
    # 
    # Anyway, it turns out that Mimi wants the summary view to use Lucida Grande
    # 11 for the grid anyway, so I've modified the Table block to always tell
    # the grid to use something, and that mechanism defaults to DEFAULT_GUI_FONT,
    # so the right thing is now happening.
    # 
    # This means that we don't need to do anything explicitly platform-specific,
    # other than the mechanism above that uses the DEFAULT_GUI_FONT's size as
    # a scaling factor.


def testSuperscript():
    cs = CharacterStyle()
    

    class TestFrame(wx.Frame):
        def __init__(self, *args, **kwds):
            super(TestFrame, self).__init__(*args, **kwds)
            self.Bind(wx.EVT_PAINT, self.OnPaint)
            self.SetSize((1000, 500))
        def OnPaint(self, event):
            dc = wx.PaintDC(self)
            dc.Clear()
            
            
            text = "lorem ipsum forever"
            
            y=0
            cs.fontSize = 15
            dc.SetFont( getFont(cs) )
            width, height  =  dc.GetTextExtent(text)
            dc.DrawText(text, 0,y)
            
            cs.fontStyle = 'fakesuperscript'
            dc.SetFont( getFont(cs) )
            dc.DrawText("exponent", width, y)
            
            y += height
            x = 0
            cs.fontSize = 11
            
            for h in range(8,14):
                h = str(h)
                for m in ("15", "30", "45"):                    
                    cs.fontStyle = 'normal'
                    dc.SetFont(getFont(cs))
                    width, height = dc.GetTextExtent(h)
                    dc.DrawText(h,  x,y)
                    x+= width
                    
                    cs.fontStyle = 'fakesuperscript'
                    dc.SetFont(getFont(cs))
                    width, height = dc.GetTextExtent(m)
                    dc.DrawText(m,  x,y)
                    x+= width + 5
                x += 10
            
            ##padding = 10
            ##r = wx.Rect(padding, padding, self.GetRect().width - padding*2, self.GetRect().height-padding*2)
            
            ##dc.DrawRectangle(*iter(r))
    
    class TestApp(wx.App):
        def OnInit(self):
            frame = TestFrame(None, -1, "Test frame.")
            frame.Show(True)
            self.SetTopWindow(frame)
            return True
     
    app = TestApp(0)
    app.MainLoop()


if __name__ == '__main__':
    # relative import weirdness, you may have to make a wrapper script
    # RunPython -c 'from osaf.framework.blocks.Styles import testSuperscript; testSuperscript()'

    testSuperscript()
