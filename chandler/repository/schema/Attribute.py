#   Copyright (c) 2003-2006 Open Source Applications Foundation
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


from chandlerdb.util.c import _hash, _combine
from chandlerdb.item.c import Nil, Default
from chandlerdb.schema.c import CAttribute
from chandlerdb.item.ItemError import SchemaError
from repository.item.Item import Item
from repository.schema.Kind import Kind
from repository.schema.TypeHandler import TypeHandler


class Attribute(Item):
    
    def __init__(self, name, parent, kind):

        super(Attribute, self).__init__(name, parent, kind)
        self._status |= Item.SCHEMA | Item.PINNED
        self.c = CAttribute(self)

    def _fillItem(self, *args):

        super(Attribute, self)._fillItem(*args)

        self.c = CAttribute(self)
        self._status |= Item.SCHEMA | Item.PINNED

    def onItemCopy(self, view, orig):

        self.c.__init__(self)

    def hasAspect(self, name):

        return self.hasLocalAttributeValue(name)

    def getAspect(self, name, default=Default):

        aspect = self._values.get(name, Nil)
        if aspect is not Nil:
            return aspect

        if name in self._references:
            return self._references._getRef(name)

        if 'superAttribute' in self._references:
            return self.superAttribute.getAspect(name, default)

        if default is not Default:
            return default

        if self._kind is not None:
            aspectAttr = self._kind.getAttribute(name, False, self)
            return aspectAttr.getAttributeValue('defaultValue',
                                                aspectAttr._values, None, None)
        
        return None

    def _walk(self, path, callable, **kwds):

        l = len(path)
        
        if path[0] == '//':
            if l == 1:
                return self
            roots = self.getAttributeValue('roots', self._values, None, Nil)
            if roots is Nil:
                root = None
            else:
                root = roots.get(path[1], None)
            index = 1

        elif path[0] == '/':
            root = self.getAttributeValue('root', self._values, None, None)
            index = 0

        root = callable(self, path[index], root, **kwds)

        if root is not None:
            index += 1
            if index == l:
                return root
            return root.walk(path, callable, index, **kwds)

        return None

    def _hashItem(self):

        hash = 0
        view = self.itsView

        item = self.getAttributeValue('superAttribute', self._references,
                                      None, None)
        if item is not None:
            hash = _combine(hash, item.hashItem())

        def hashValue(hash, type, value):
            if type is not None:
                return _combine(hash, type.hashValue(value))
            else:
                return _combine(hash, TypeHandler.hashValue(view, value))

        for aspect in Attribute.valueAspects:
            value = self.getAttributeValue(aspect, self._values, None, Nil)
                                           
            if value is not Nil:
                hash = _combine(hash, _hash(aspect))
                type = self.getAttributeAspect(aspect, 'type',
                                               False, None, None)
                card = self.getAttributeAspect(aspect, 'cardinality',
                                               False, None, 'single')
                if card == 'single':
                    hash = hashValue(hash, type, value)
                elif card == 'list':
                    for v in value:
                        hash = hashValue(hash, type, v)
                else:
                    raise NotImplementedError, card

        item = self.getAttributeValue('type', self._references, None, None)
        if item is not None:
            if isinstance(item, Kind):
                hash = _combine(hash, _hash(str(item.itsPath)))
            else:
                hash = _combine(hash, item.hashItem())

        return hash

    def hashItem(self):

        if 'schemaHash' in self._values:
            return self.schemaHash

        self.schemaHash = hash = self._hashItem()
        return hash

    def _afterAspectChange(self, name):

        if 'schemaHash' in self._values:
            del self.schemaHash
            if 'kinds' in self._references:
                for kind in self.kinds:
                    kind._afterAttributeHashChange()

    def _afterCardinalityChange(self, name):

        self.c.cardinality = self._values
        
    def _afterPersistedChange(self, name):

        self.c.persisted = self._values.get('persisted', True)

    def _afterRequiredChange(self, name):

        self.c.required = self._values.get('required', False)

    def _afterIndexedChange(self, name):

        self.c.indexed = self._values.get('indexed', False)

    def _afterInheritFromChange(self, name):

        self.c.noInherit = (self._values, 'inheritFrom', 'redirectTo')

    def _afterDefaultValueChange(self, name):

        self.c.defaultValue = self._values

    def _afterRedirectToChange(self, name):

        self.c.redirectTo = (self._values, 'redirectTo', 'inheritFrom')

    def _afterOtherNameChange(self, name):

        self.c.otherName = self._values

    def _afterTypeChange(self, name):

        self.c.typeID = self._references

    def _afterAfterChangeChange(self, name):

        self.c.afterChange = self._values

    def findMatch(self, view, matches=None):

        uuid = self._uuid

        if matches is not None:
            match = matches.get(uuid)
        else:
            match = None
            
        if match is None:
            match = view.find(uuid)
            if match is None:
                match = view.find(self.itsPath)
                if not (match is None or matches is None):
                    if not (self is match or
                            self.hashItem() == match.hashItem()):
                        raise SchemaError, ("Attribute matches are incompatible: %s %s", self.itsPath, match.itsPath)
                    matches[uuid] = match

        return match

    valueAspects = ('required', 'persisted', 'indexed', 'notify',
                    'cardinality', 'defaultValue', 'initialValue',
                    'inheritFrom', 'redirectTo', 'otherName', 'afterChange',
                    'deletePolicy', 'copyPolicy', 'countPolicy', 'domains')

    refAspects = ('type', 'superAttribute')
