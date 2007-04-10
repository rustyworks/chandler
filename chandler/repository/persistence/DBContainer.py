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


import sys, threading, time

from struct import pack, unpack

from chandlerdb.util.c import \
    UUID, isuuid, _hash, HashTuple, Nil, Default, SkipList
from chandlerdb.item.c import CItem, CValues
from chandlerdb.persistence.c import \
    Record, DB, DBEnv, \
    CContainer, CValueContainer, CRefContainer, CItemContainer, \
    DBNotFoundError, DBLockDeadlockError, DBNoSuchFileError

from repository.item.Access import ACL, ACE
from repository.persistence.Repository import Repository
from repository.persistence.RepositoryView import RepositoryView
from repository.persistence.RepositoryError import \
    RepositoryFormatVersionError, RepositorySchemaVersionError

NONE_PAIR = (None, None)


class DBContainer(object):

    def __init__(self, store):

        self.store = store
        self._db = None

    def openDB(self, txn, name, dbname, ramdb, create, mvcc):

        db = DB(self.store.env)
        db.lorder = 4321
        
        flags = DB.DB_THREAD

        if ramdb:
            name = None
            dbname = None
        elif mvcc:
            flags |= DB.DB_MULTIVERSION
            
        if create:
            flags |= DB.DB_CREATE

        db.open(filename = name, dbname = dbname,
                dbtype = DB.DB_BTREE, flags = flags, txn = txn)

        return db

    def openC(self):

        self.c = CContainer(self._db, self.store)

    def open(self, name, txn, **kwds):

        self._db = self.openDB(txn, name, kwds.get('dbname', None),
                               kwds.get('ramdb', False),
                               kwds.get('create', False),
                               kwds.get('mvcc', False))
        self.openC()

    def openIndex(self, name, dbname, txn, **kwds):

        index = self.openDB(txn, name, dbname,
                            kwds.get('ramdb', False),
                            kwds.get('create', False),
                            kwds.get('mvcc', False))

        self.associateIndex(index, dbname, txn)

        return index

    def associateIndex(self, index, name, txn):

        raise NotImplementedError, "%s.associateIndex" %(type(self))

    def close(self):

        if self._db is not None:
            self._db.close()
            self._db = None

    def compact(self, txn):

        self._db.compact(txn)

    def attachView(self, view):

        pass

    def detachView(self, view):

        pass

    def put(self, key, value, db=None):

        if db is None:
            db = self._db

        db.put(key, value, self.store.txn)
        return len(key) + len(value)

    def put_record(self, key, value, db=None):

        if db is None:
            db = self._db

        db.put_record(key, value, self.store.txn)
        return key.size + value.size

    def delete(self, key, txn=None):

        try:
            self._db.delete(key, txn or self.store.txn)
        except DBNotFoundError:
            pass

    def get(self, key, db=None):

        if db is None:
            db = self._db

        while True:
            try:
                return db.get(key, self.store.txn, self.c.flags, None)
            except DBLockDeadlockError:
                self.store._logDL()
                if self.store.txn is not None:
                    raise

    def get_record(self, key, args, db=None):

        if db is None:
            db = self._db

        while True:
            try:
                return db.get_record(key, args,
                                     self.store.txn, self.c.flags, None)
            except DBLockDeadlockError:
                self.store._logDL()
                if self.store.txn is not None:
                    raise


class RefContainer(DBContainer):

    KEY_TYPES = (Record.UUID,
                 Record.INT,
                 Record.UUID)
    HEAD_TYPES = (Record.UUID_OR_NONE,
                  Record.UUID_OR_NONE,
                  Record.INT,
                  Record.UUID_OR_KEYWORD)
    REF_TYPES = (Record.UUID_OR_NONE,
                 Record.UUID_OR_NONE,
                 Record.KEYWORD,
                 Record.UUID_OR_KEYWORD)

    def __init__(self, store):

        super(RefContainer, self).__init__(store)
        self._history = None
        
    def open(self, name, txn, **kwds):

        super(RefContainer, self).open(name, txn, dbname = 'data', **kwds)
        self._history = self.openIndex(name, 'history', txn, **kwds)

    def associateIndex(self, index, name, txn):

        self.c.associateHistory(index, txn, DB.DB_IMMUTABLE_KEY)

    def openC(self):

        self.c = CRefContainer(self._db, self.store)

    def close(self):

        if self._history is not None:
            self._history.close()
            self._history = None

        super(RefContainer, self).close()

    def compact(self, txn):

        super(RefContainer, self).compact(txn)
        self._history.compact(txn)

    def iterHistory(self, view, uuid, fromVersion, toVersion, refsOnly=False):

        store = self.store
        
        class _iterator(object):

            def __init__(_self):

                _self.cursor = None
                _self.txnStatus = 0

            def __del__(_self):

                try:
                    self.c.closeCursor(_self.cursor, self._history)
                    store.commitTransaction(view, _self.txnStatus)
                except:
                    store.repository.logger.exception("in __del__")
                _self.cursor = None
                _self.txnStatus = 0

            def next(_self):

                _self.txnStatus = store.startTransaction(view)
                _self.cursor = cursor = self.c.openCursor(self._history)
                
                try:
                    key = Record(Record.UUID, uuid,
                                 Record.INT, fromVersion + 1)
                    keyTypes = RefContainer.KEY_TYPES
                    dataTypes = RefContainer.REF_TYPES
                    flags = self.c.flags

                    key, ref = cursor.find_record(key, keyTypes, dataTypes,
                                                  flags, NONE_PAIR)

                    while ref is not None:
                        uCol, version, uRef = key.data
                        if version > toVersion or uCol != uuid:
                            break

                        if refsOnly:
                            yield uRef
                        else:
                            if ref.size == 1: # deleted ref
                                yield version, (uuid, uRef), None
                            else:
                                yield version, (uuid, uRef), ref.data

                        key, ref = cursor.next_record(key, ref,
                                                      flags, NONE_PAIR)

                    yield False

                except DBLockDeadlockError:
                    if _self.txnStatus & store.TXN_STARTED:
                        store._logDL()
                        yield True
                    else:
                        raise

        while True:
            for result in _iterator().next():
                if result is True:
                    break
                if result is False:
                    return
                yield result

    def deleteRef(self, uCol, version, uRef):

        return self.put_record(Record(Record.UUID, uCol,
                                      Record.UUID, uRef,
                                      Record.INT, ~version),
                               Record(Record.NONE, None))

    def loadRef(self, view, uCol, version, uRef, head=False):

        store = self.store

        if head:
            types = RefContainer.HEAD_TYPES
        else:
            types = RefContainer.REF_TYPES

        while True:
            txnStatus = 0
            cursor = None

            try:
                txnStatus = store.startTransaction(view)
                cursor = self.c.openCursor()

                return self.c.find_ref(cursor, uCol, uRef, ~version, types,
                                       self.c.flags)
            
            except DBLockDeadlockError:
                if txnStatus & store.TXN_STARTED:
                    store._logDL()
                    continue
                else:
                    raise

            finally:
                self.c.closeCursor(cursor)
                store.abortTransaction(view, txnStatus)

    def refIterator(self, view, uCol, version):

        store = self.store

        class _iterator(object):

            def __init__(_self):

                _self.cursor = None
                _self.txnStatus = store.startTransaction(view)
                _self.cursor = self.c.openCursor()

            def __del__(_self):

                if _self.cursor is not None:
                    try:
                        self.c.closeCursor(_self.cursor)
                        store.commitTransaction(view, _self.txnStatus)
                    except:
                        store.repository.logger.exception("in __del__")
                    _self.cursor = None
                    _self.txnStatus = 0

            def close(_self):

                if _self.cursor is not None:
                    self.c.closeCursor(_self.cursor)
                    store.commitTransaction(view, _self.txnStatus)
                    _self.cursor = None
                    _self.txnStatus = 0

            def next(_self, uRef):

                try:
                    return self.c.find_ref(_self.cursor, uCol, uRef, ~version,
                                           RefContainer.REF_TYPES, self.c.flags)
                except DBLockDeadlockError:
                    if _self.txnStatus & store.TXN_STARTED:
                        store._logDL()
                        return True
                    else:
                        raise

        return _iterator()

    def iterKeys(self, view, uCol, version, firstKey=None, lastKey=None):

        iterator = self.refIterator(view, uCol, version)
        if firstKey is None or lastKey is None:
            ref = iterator.next(uCol)
            if ref is None:
                iterator.close()
                raise KeyError, ('refIterator', uCol)
            _firstKey, _lastKey, x, x = ref
            if firstKey is None:
                firstKey = _firstKey
            if lastKey is None:
                lastKey = _lastKey

        nextKey = firstKey
        while nextKey != lastKey:
            key = nextKey
            ref = iterator.next(key)
            if ref is None:
                iterator.close()
                raise KeyError, ('refIterator', key)
            previousKey, nextKey, x, x = ref
            yield key

        if lastKey is not None:
            yield lastKey

        iterator.close()

    def purgeRefs(self, txn, uCol, keepOne):

        count = 0
        cursor = None

        try:
            cursor = self.c.openCursor()
            key = uCol._uuid
            value = cursor.set_range(key, self.c.flags, None)

            if not keepOne:
                while value is not None and value[0].startswith(key):
                    cursor.delete(self.c.flags)
                    count += 1
                    value = cursor.next(self.c.flags, None)

            else:
                prevRef = None
                while value is not None and value[0].startswith(key):
                    ref = value[0][16:32]
                    if ref == prevRef or len(value[1]) == 1:
                        cursor.delete(self.c.flags)
                        count += 1
                    prevRef = ref
                    value = cursor.next(self.c.flags, None)

        finally:
            self.c.closeCursor(cursor)

        return count, self.store._names.purgeNames(txn, uCol, keepOne)

    def undoRefs(self, txn, uCol, version):

        cursor = None

        try:
            cursor = self.c.openCursor()
            key = uCol._uuid
            value = cursor.set_range(key, self.c.flags, None)

            while value is not None and value[0].startswith(key):
                keyVer = ~unpack('>l', value[0][32:36])[0]
                if keyVer == version:
                    cursor.delete(self.c.flags)
                value = cursor.next(self.c.flags, None)

        finally:
            self.c.closeCursor(cursor)

        self.store._names.undoNames(txn, uCol, version)


class NamesContainer(DBContainer):

    KEY_TYPES = (Record.UUID,   # key
                 Record.HASH,   # name hash
                 Record.INT)    # ~version
    NAME_TYPES = (Record.UUID,) # corresponding uuid

    def writeName(self, version, key, name, uuid):

        if uuid is None:
            uuid = key

        return self.put_record(Record(Record.UUID, key,
                                      Record.HASH, name,
                                      Record.INT, ~version),
                               Record(Record.UUID, uuid))

    def purgeNames(self, txn, uuid, keepOne):

        count = 0
        cursor = None

        try:
            cursor = self.c.openCursor()
            key = uuid._uuid
            prevHash = None
            value = cursor.set_range(key, self.c.flags, None)

            if not keepOne:
                while value is not None and value[0].startswith(key):
                    cursor.delete(self.c.flags)
                    count += 1
                    value = cursor.next(self.c.flags, None)

            else:
                while value is not None and value[0].startswith(key):
                    hash = value[0][16:20]
                    if hash == prevHash or key == value[1]:
                        cursor.delete(self.c.flags)
                        count += 1
                    prevHash = hash
                    value = cursor.next(self.c.flags, None)

        finally:
            self.c.closeCursor(cursor)

        return count

    def undoNames(self, txn, uuid, version):

        cursor = None

        try:
            cursor = self.c.openCursor()
            key = uuid._uuid
            prevHash = None
            value = cursor.set_range(key, self.c.flags, None)

            while value is not None and value[0].startswith(key):
                nameVer = ~unpack('>l', value[0][-4:])[0]
                if nameVer == version:
                    cursor.delete(self.c.flags)
                value = cursor.next(self.c.flags, None)

        finally:
            self.c.closeCursor(cursor)

    def readName(self, view, version, uKey, name):

        store = self.store
        key = Record(Record.UUID, uKey,
                     Record.HASH, name,
                     Record.INT, ~version)
        
        while True:
            txnStatus = 0
            cursor = None

            try:
                txnStatus = store.startTransaction(view)
                cursor = self.c.openCursor()
                
                name = self.c.find_record(cursor, key,
                                          NamesContainer.NAME_TYPES,
                                          self.c.flags, None)
                if name is not None:
                    uValue = name[0]
                    if uValue == uKey:    # deleted name
                        return None

                    return uValue

                return None

            except DBLockDeadlockError:
                if txnStatus & store.TXN_STARTED:
                    store._logDL()
                    continue
                else:
                    raise

            finally:
                self.c.closeCursor(cursor)
                store.abortTransaction(view, txnStatus)

    def readNames(self, view, version, uKey):

        results = []
        store = self.store

        key = Record(Record.UUID, uKey)
        keyTypes = NamesContainer.KEY_TYPES
        dataTypes = NamesContainer.NAME_TYPES
        flags = self.c.flags

        while True:
            txnStatus = 0
            cursor = None

            try:
                txnStatus = store.startTransaction(view)
                cursor = self.c.openCursor()
                
                key, name = cursor.find_record(key, keyTypes, dataTypes,
                                               flags, NONE_PAIR)
                if name is None:
                    return results

                currentHash = None
                
                while name is not None:
                    uuid, hash, nameVer = key.data
                    if uuid != uKey:
                        break

                    if hash != currentHash and ~nameVer <= version:
                        currentHash = nameHash
                        uValue = name[0]
                        if uValue != uKey:    # !deleted name
                            results.append(uValue)

                    key, name = cursor.next_record(key, name, flags, NONE_PAIR)

                return results

            except DBLockDeadlockError:
                if txnStatus & store.TXN_STARTED:
                    store._logDL()
                    continue
                else:
                    raise

            finally:
                self.c.closeCursor(cursor)
                store.abortTransaction(view, txnStatus)


class ACLContainer(DBContainer):

    KEY_TYPES = (Record.UUID,   # uKey
                 Record.HASH,   # name hash or 0
                 Record.INT)    # ~version

    ACL_TYPES = (Record.BYTE,   # number of aces
                 Record.RECORD) # aces

    def writeACL(self, version, key, name, acl):

        if name is None:
            key = Record(Record.UUID, key,
                         Record.INT, 0,
                         Record.INT, ~version)
        else:
            key = Record(Record.UUID, key,
                         Record.HASH, name,
                         Record.INT, ~version)

        if acl is None:    # deleted acl
            record = Record(Record.BYTE, 0)
        else:
            record = Record(Record.BYTE, len(acl))
            acesRecord = Record()
            for ace in acl:
                acesRecord += (Record.UUID, ace.pid,
                               Record.INT, ace.perms)
            record += (Record.RECORD, acesRecord)

        return self.put_record(key, record)

    def readACL(self, view, version, uKey, name):

        store = self.store
        
        if name is None:
            key = Record(Record.UUID, uKey,
                         Record.INT, 0,
                         Record.INT, ~version)
        else:
            key = Record(Record.UUID, uKey,
                         Record.HASH, name,
                         Record.INT, ~version)

        while True:
            txnStatus = 0
            cursor = None

            try:
                txnStatus = store.startTransaction(view)
                cursor = self.c.openCursor()
                
                acl = self.c.find_record(cursor, key,
                                         ACLContainer.ACL_TYPES,
                                         self.c.flags, None)
                if acl is not None:
                    if acl.size == 1:  # deleted acl
                        return None

                    count, aces = acl.data
                    acl = ACL()
                    for i in xrange(0, count*2, 2):
                        acl.append(ACE(*aces[i:i+2]))
                    return acl

                return None

            except DBLockDeadlockError:
                if txnStatus & store.TXN_STARTED:
                    store._logDL()
                    continue
                else:
                    raise

            finally:
                self.c.closeCursor(cursor)
                store.abortTransaction(view, txnStatus)


class IndexesContainer(DBContainer):

    KEY_TYPES = (Record.UUID,     # uIndex
                 Record.UUID,     # uKey
                 Record.INT)      # ~version
    ENTRY_TYPES = (Record.BYTE,   # level
                   Record.INT,    # entry value
                   Record.RECORD) # points

    def saveKey(self, uIndex, version, uKey, node):

        if node is not None:
            level = len(node)
            record = Record(Record.BYTE, level,
                            Record.INT, node._entryValue)
            pointsRecord = Record()
            for lvl in xrange(1, level + 1):
                point = node[lvl]
                pointsRecord += (Record.UUID_OR_NONE, point.prevKey,
                                 Record.UUID_OR_NONE, point.nextKey,
                                 Record.INT, point.dist)
            record += (Record.RECORD, pointsRecord)
        else:
            record = Record(Record.BYTE, 0)

        return self.put_record(Record(Record.UUID, uIndex,
                                      Record.UUID, uKey,
                                      Record.INT, ~version),
                               record)

    def loadKey(self, view, uIndex, version, uKey):
        
        store = self.store
        
        key = Record(Record.UUID, uIndex,
                     Record.UUID, uKey,
                     Record.INT, ~version)

        while True:
            txnStatus = 0
            cursor = None

            try:
                txnStatus = store.startTransaction(view)
                cursor = self.c.openCursor()

                entry = self.c.find_record(cursor, key,
                                           IndexesContainer.ENTRY_TYPES,
                                           self.c.flags, None)
                if entry is not None:
                    level, entryValue, points = entry.data
                    if level == 0:  # deleted entry
                        return None
                    
                    node = SkipList.Node(level)
                    node._entryValue = entryValue

                    for lvl in xrange(0, level):
                        point = node[lvl+1]
                        (point.prevKey, point.nextKey,
                         point.dist) = points[lvl*3:(lvl+1)*3]

                    return node

                return None
                        
            except DBLockDeadlockError:
                if txnStatus & store.TXN_STARTED:
                    store._logDL()
                    continue
                else:
                    raise

            finally:
                self.c.closeCursor(cursor)
                store.abortTransaction(view, txnStatus)

    def purgeIndex(self, txn, uIndex, keepOne):

        count = 0
        cursor = None

        try:
            cursor = self.c.openCursor()
            key = uIndex._uuid
            value = cursor.set_range(key, self.c.flags, None)

            if not keepOne:
                while value is not None and value[0].startswith(key):
                    cursor.delete(self.c.flags)
                    count += 1
                    value = cursor.next(self.c.flags, None)

            else:
                prevRef = None
                while value is not None and value[0].startswith(key):
                    ref = value[0][16:32]
                    if ref == prevRef or value[1][0] == '\0':
                        cursor.delete(self.c.flags)
                        count += 1
                    prevRef = ref
                    value = cursor.next(self.c.flags, None)

        finally:
            self.c.closeCursor(cursor)

        return count

    def undoIndex(self, txn, uIndex, version):

        cursor = None

        try:
            cursor = self.c.openCursor()
            key = uIndex._uuid
            value = cursor.set_range(key, self.c.flags, None)

            while value is not None and value[0].startswith(key):
                keyVer = ~unpack('>l', value[0][32:36])[0]
                if keyVer == version:
                    cursor.delete(self.c.flags)

                value = cursor.next(self.c.flags, None)

        finally:
            self.c.closeCursor(cursor)

    def nodeIterator(self, view, uIndex, version):
        
        store = self.store

        class _iterator(object):

            def __init__(_self):

                _self.cursor = None
                _self.txnStatus = store.startTransaction(view)
                _self.cursor = self.c.openCursor()

            def __del__(_self):

                try:
                    self.c.closeCursor(_self.cursor)
                    store.commitTransaction(view, _self.txnStatus)
                except:
                    store.repository.logger.exception("in __del__")
                _self.cursor = None
                _self.txnStatus = 0

            def next(_self, uKey):

                key = Record(Record.UUID, uIndex,
                             Record.UUID, uKey,
                             Record.INT, ~version)

                try:
                    entry = self.c.find_record(_self.cursor, key,
                                               IndexesContainer.ENTRY_TYPES,
                                               self.c.flags, None)
                    if entry is not None:
                        level, entryValue, points = entry.data
                        if level == 0:  # deleted entry
                            return None
                    
                        node = SkipList.Node(level)
                        node._entryValue = entryValue

                        for lvl in xrange(0, level):
                            point = node[lvl+1]
                            (point.prevKey, point.nextKey,
                             point.dist) = points[lvl*3:(lvl+1)*3]

                        return node

                    return None

                except DBLockDeadlockError:
                    if _self.txnStatus & store.TXN_STARTED:
                        store._logDL()
                        return True
                    else:
                        raise

        return _iterator()


class ItemContainer(DBContainer):

    KEY_TYPES = (Record.UUID,           # item uuid
                 Record.INT)            # ~version

    ITEM_TYPES = (Record.UUID,          # kind
                  Record.INT,           # status
                  Record.UUID,          # parent
                  Record.RECORD,        # values
                  Record.UUID_OR_NONE,  # previous kind or None
                  Record.KEYWORD,       # name or None
                  Record.SYMBOL,        # module name or None
                  Record.SYMBOL,        # class name or None
                  Record.RECORD)        # dirty values

    KIND_TYPES = ITEM_TYPES[0:1]
    PARENT_TYPES = ITEM_TYPES[0:3]
    VALUES_TYPES = ITEM_TYPES[0:4]
    NAME_TYPES = ITEM_TYPES[0:6]
    NO_DIRTIES_TYPES = ITEM_TYPES[0:-1]

    def __init__(self, store):

        super(ItemContainer, self).__init__(store)

        self._kinds = None
        self._versions = None
        
    def open(self, name, txn, **kwds):

        super(ItemContainer, self).open(name, txn, dbname = 'data', **kwds)

        self._kinds = self.openIndex(name, 'kinds', txn, **kwds)
        self._versions = self.openIndex(name, 'versions', txn, **kwds)

    def associateIndex(self, index, name, txn):

        if name == 'kinds':
            self.c.associateKind(index, txn, DB.DB_IMMUTABLE_KEY)
        elif name == 'versions':
            self.c.associateVersion(index, txn, DB.DB_IMMUTABLE_KEY)
        else:
            raise ValueError, name

    def openC(self):

        self.c = CItemContainer(self._db, self.store)

    def close(self):

        if self._kinds is not None:
            self._kinds.close()
            self._kinds = None

        if self._versions is not None:
            self._versions.close()
            self._versions = None

        super(ItemContainer, self).close()

    def compact(self, txn):

        super(ItemContainer, self).compact(txn)

        self._kinds.compact(txn)
        self._versions.compact(txn)

    def saveItem(self, uItem, version, uKind, prevKind, status,
                 uParent, name, moduleName, className,
                 values, dirtyValues, dirtyRefs):

        record = Record(Record.UUID, uKind,
                        Record.INT, status,
                        Record.UUID, uParent)

        valuesRecord = Record()
        for valueName, uValue in values:
            valuesRecord += (Record.HASH, valueName, Record.UUID, uValue)
        record += (Record.RECORD, valuesRecord)

        record += (Record.UUID_OR_NONE, prevKind,
                   Record.KEYWORD, name,
                   Record.SYMBOL, moduleName,
                   Record.SYMBOL, className)

        dirtiesRecord = Record()
        for name in dirtyValues:
            dirtiesRecord += (Record.HASH, name)
        for name in dirtyRefs:
            dirtiesRecord += (Record.HASH, name)
        record += (Record.RECORD, dirtiesRecord)

        # (uItem, ~version), (uKind, status, uParent, values, ...)

        return self.put_record(Record(Record.UUID, uItem,
                                      Record.INT, ~version),
                               record)

    def _itemFinder(self, view):

        store = self.store

        class _finder(object):

            def __init__(_self):

                _self.txnStatus = store.startTransaction(view)
                _self.cursor = self.c.openCursor()

            def __del__(_self):

                try:
                    self.c.closeCursor(_self.cursor)
                    store.commitTransaction(view, _self.txnStatus)
                except:
                    store.repository.logger.exception("in __del__")
                _self.cursor = None
                _self.txnStatus = 0

            def _find(_self, version, uuid, dataTypes):

                key = Record(Record.UUID, uuid,
                             Record.INT, ~version)

                try:
                    key, item = self.c.find_record(_self.cursor, key, dataTypes,
                                                   self.c.flags, NONE_PAIR, True)
                    if item is not None:
                        return ~key[1], item

                    return NONE_PAIR

                except DBLockDeadlockError:
                    if _self.txnStatus & store.TXN_STARTED:
                        store._logDL()
                        return True, None
                    else:
                        raise

            def findItem(_self, version, uuid):

                while True:
                    v, i = _self._find(version, uuid, ItemContainer.ITEM_TYPES)
                    if v is True:
                        continue
                    if i is None:
                        return NONE_PAIR
                    return v, i

            def getVersion(_self, version, uuid):

                while True:
                    v, i = _self._find(version, uuid, Nil)
                    if v is True:
                        continue
                    if i is None:
                        return None
                    return v

        return _finder()

    def getItemValues(self, version, uuid):

        item = self.get_record(Record(Record.UUID, uuid,
                                      Record.INT, ~version),
                               ItemContainer.VALUES_TYPES)
        if item is None:
            return None

        values = item[-1]
        return dict(values[offset:offset+2]
                    for offset in xrange(0, len(values), 2))

    def purgeItem(self, txn, uuid, version):

        self.delete(pack('>16sl', uuid._uuid, ~version), txn)
        return 1

    def isValue(self, view, version, uItem, uValue, exact=False):

        if exact:
            item = self.get_record(Record(Record.UUID, uuid,
                                          Record.INT, ~version),
                                   ItemContainer.VALUES_TYPES)
        else:
            version, item = self.c.findItem(view, version, uItem,
                                            ItemContainer.VALUES_TYPES)

        if item is not None:
            return uValue in item[-1]

        return False

    def findValue(self, view, version, uuid, hash, exact=False):

        if exact:
            item = self.get_record(Record(Record.UUID, uuid,
                                          Record.INT, ~version),
                                   ItemContainer.VALUES_TYPES)
        else:
            version, item = self.c.findItem(view, version, uuid,
                                            ItemContainer.VALUES_TYPES)

        if item is not None:
            i = iter(item[-1].data)
            for h in i:
                value = i.next()
                if h == hash:
                    return item[1], value

            return None, Default

        return None, Nil

    # hashes is a list of attribute name hashes or None (meaning all)
    # return list may contain None (for deleted or not found values)
    def findValues(self, view, version, uuid, hashes=None, exact=False):

        assert hashes is None or type(hashes) is list

        if exact:
            item = self.get_record(Record(Record.UUID, uuid,
                                          Record.INT, ~version),
                                   ItemContainer.VALUES_TYPES)
        else:
            version, item = self.c.findItem(view, version, uuid,
                                            ItemContainer.VALUES_TYPES)

        if item is not None:
            values = item[-1].data
            if hashes is None: # return all values
                return item[1], [uValue for uValue in values if isuuid(uValue)]

            uValues = [None] * len(hashes)
            i = iter(values)
            for h in i:
                uValue = i.next()
                if h in hashes:
                    uValues[hashes.index(h)] = uValue

            return item[1], uValues

        return None, Nil

    def getItemParentId(self, view, version, uuid):

        version, item = self.c.findItem(view, version, uuid,
                                        ItemContainer.PARENT_TYPES)
        if item is not None:
            return item[-1]

        return None

    def getItemKindId(self, view, version, uuid):

        version, item = self.c.findItem(view, version, uuid,
                                        ItemContainer.KIND_TYPES)
        if item is not None:
            return item[-1]

        return None

    def getItemName(self, view, version, uuid):

        version, item = self.c.findItem(view, version, uuid,
                                        ItemContainer.NAME_TYPES)
        if item is not None:
            return item[-1]

        return None

    def getItemVersion(self, view, version, uuid):

        version, item = self.c.findItem(view, version, uuid, Nil)
        if item is not None:
            return version

        return None

    def kindQuery(self, view, version, uuid, keysOnly=False):

        store = self.store

        class _query(object):

            def __init__(_self):

                _self.cursor = None
                _self.txnStatus = 0

            def __del__(_self):

                try:
                    self.c.closeCursor(_self.cursor, self._kinds)
                    store.commitTransaction(view, _self.txnStatus)
                except:
                    store.repository.logger.exception("in __del__")
                _self.cursor = None
                _self.txnStatus = 0

            def run(_self):

                _self.txnStatus = store.startTransaction(view)
                _self.cursor = cursor = self.c.openCursor(self._kinds)

                keyTypes = (Record.UUID, Record.UUID, Record.INT)
                if keysOnly:
                    dataTypes = Nil
                else:
                    dataTypes = ItemContainer.NO_DIRTIES_TYPES

                flags = self.c.flags

                try:
                    key = Record(Record.UUID, uuid)
                    key, item = cursor.find_record(key, keyTypes, dataTypes,
                                                   flags, NONE_PAIR)
                    if item is None:
                        yield False

                    lastItem = None
                    while item is not None:
                        uKind, uItem, vItem = key.data
                        if uKind != uuid:
                            break

                        vItem = ~vItem
                        if vItem <= version and uItem != lastItem:
                            if keysOnly:
                                yield uItem, vItem
                            else:
                                yield uItem, vItem, item
                            lastItem = uItem

                        key, item = cursor.next_record(key, item,
                                                       flags, NONE_PAIR)

                    yield False

                except DBLockDeadlockError:
                    if _self.txnStatus & store.TXN_STARTED:
                        store._logDL()
                        yield True
                    else:
                        raise

        while True:
            for result in _query().run():
                if result is True:
                    break
                if result is False:
                    return
                yield result

    def iterHistory(self, view, fromVersion, toVersion, keysOnly=False):

        store = self.store
        
        class _iterator(object):

            def __init__(_self):

                _self.cursor = None
                _self.txnStatus = 0

            def __del__(_self):

                try:
                    self.c.closeCursor(_self.cursor, self._versions)
                    store.commitTransaction(view, _self.txnStatus)
                except:
                    store.repository.logger.exception("in __del__")
                _self.cursor = None
                _self.txnStatus = 0

            def next(_self):

                _self.txnStatus = store.startTransaction(view)
                _self.cursor = cursor = self.c.openCursor(self._versions)

                keyTypes = (Record.INT, Record.UUID)
                if keysOnly:
                    dataTypes = ()
                else:
                    dataTypes = ItemContainer.ITEM_TYPES
                flags = self.c.flags

                try:
                    key = Record(Record.INT, fromVersion + 1)
                    key, item = cursor.find_record(key, keyTypes, dataTypes,
                                                   flags, NONE_PAIR)

                    while item is not None:
                        version, uItem = key.data
                        if version > toVersion:
                            break

                        if keysOnly:
                            yield uItem, version

                        else:
                            (uKind, status, uParent, x, prevKind,
                             x, x, x, dirties) = item.data

                            if status & CItem.DELETED:
                                dirties = HashTuple()
                            else:
                                dirties = HashTuple(dirties.data)

                            yield (uItem, version,
                                   uKind, status, uParent, prevKind,
                                   dirties)
                        
                        key, item = cursor.next_record(key, item,
                                                       flags, NONE_PAIR)

                    yield False

                except DBLockDeadlockError:
                    if _self.txnStatus & store.TXN_STARTED:
                        store._logDL()
                        yield True
                    else:
                        raise

        while True:
            for result in _iterator().next():
                if result is True:
                    break
                if result is False:
                    return
                yield result

    def iterItems(self, view):

        store = self.store
        
        class _iterator(object):

            def __init__(_self):

                _self.cursor = None
                _self.txnStatus = 0

            def __del__(_self):

                try:
                    self.c.closeCursor(_self.cursor)
                    store.commitTransaction(view, _self.txnStatus)
                except:
                    store.repository.logger.exception("in __del__")
                _self.cursor = None
                _self.txnStatus = 0

            def next(_self):

                _self.txnStatus = store.startTransaction(view)
                _self.cursor = cursor = self.c.openCursor()

                key = ItemContainer.KEY_TYPES
                item = ItemContainer.VALUES_TYPES
                flags = self.c.flags
                
                try:
                    while True:
                        key, item = cursor.next_record(key, item,
                                                       flags, NONE_PAIR)
                        if item is None:
                            break

                        uuid, version = key.data
                        x, status, x, values = item.data

                        yield (uuid, ~version, status,
                               tuple([uValue for uValue in values.data
                                      if isuuid(uValue)]))

                    yield False

                except DBLockDeadlockError:
                    if _self.txnStatus & store.TXN_STARTED:
                        store._logDL()
                        yield True
                    else:
                        raise

        while True:
            for result in _iterator().next():
                if result is True:
                    break
                if result is False:
                    return
                yield result

    def iterVersions(self, view, uItem, fromVersion=1, toVersion=0):

        store = self.store
        
        class _iterator(object):

            def __init__(_self):

                _self.cursor = None
                _self.txnStatus = 0

            def __del__(_self):

                try:
                    self.c.closeCursor(_self.cursor)
                    store.abortTransaction(view, _self.txnStatus)
                except:
                    store.repository.logger.exception("in __del__")
                _self.cursor = None
                _self.txnStatus = 0

            def next(_self):

                _self.txnStatus = store.startTransaction(view)
                _self.cursor = cursor = self.c.openCursor()

                key = Record(Record.UUID, uItem,
                             Record.INT, ~fromVersion)
                keyTypes = ItemContainer.KEY_TYPES
                dataTypes = (Record.UUID, Record.INT)
                flags = self.c.flags

                try:
                    key, item = cursor.find_record(key, keyTypes, dataTypes,
                                                   flags, NONE_PAIR)

                    if not (key is None or key[0] == uItem):
                        key, item = cursor.prev_record(key, item,
                                                       flags, NONE_PAIR)

                    while key is not None:
                        uuid, version = key.data
                        if uuid != uItem:
                            break

                        version = ~version
                        if toVersion and version > toVersion:
                            break

                        if version >= fromVersion:
                            yield version, item[1]

                        key, item = cursor.prev_record(key, item,
                                                       flags, NONE_PAIR)

                    yield False

                except DBLockDeadlockError:
                    if _self.txnStatus & store.TXN_STARTED:
                        store._logDL()
                        yield True
                    else:
                        raise

        while True:
            for result in _iterator().next():
                if result is True:
                    break
                if result is False:
                    return
                yield result


class ValueContainer(DBContainer):

    # 0.5.0: first tracked format version
    # 0.5.1: 'Long' values saved as long long (64 bit)
    # 0.5.2: added support for 'Set' type and 'set' cardinality
    # 0.5.3: added core schema version to version info
    # 0.5.4: endianness on index dbs set to 4321
    # 0.5.5: lob 'indexed' attribute now saved as -1, 0, 1
    # 0.5.6: lob encryption reworked to include IV
    # 0.5.7: string length incremented before saved to preserve sign
    # 0.5.8: date/time type formats optimized
    # 0.5.9: value flags and enum values saved as byte instead of int
    # 0.5.10: added support for storing selection ranges on indexes
    # 0.6.0: version reimplemented as 64 bit sequence, removed value index
    # 0.6.1: version purge support
    # 0.6.2: added KDIRTY flag and storing of previous kind to item record
    # 0.6.3: changed persisting if a value is full-text indexed
    # 0.6.4: changed version persistence to no longer use sequence
    # 0.6.5: added support for sub-indexes
    # 0.6.6: added support for dictionaries of ref collections
    # 0.6.7: version back to unsigned long
    # 0.6.8: added commits log db
    # 0.6.9: Term vectors stored in Lucene indexes
    # 0.6.10: FileContainer changed to contain both file info and data blocks
    # 0.6.11: Renamed DB_VERSION to DB_INFO
    # 0.6.12: added Record C type to serialize into DB
    # 0.6.13: added support for persisting Empty for ref collections
    # 0.6.14: 'descending' bit moved to NumericIndex

    FORMAT_VERSION = 0x00060e00

    SCHEMA_KEY  = pack('>16sl', Repository.itsUUID._uuid, 0)
    VERSION_KEY = pack('>16sl', Repository.itsUUID._uuid, 1)

    def __init__(self, store):

        self._version = None
        super(ValueContainer, self).__init__(store)
        
    def open(self, name, txn, **kwds):

        super(ValueContainer, self).open(name, txn, dbname = 'data', **kwds)

        format_version = ValueContainer.FORMAT_VERSION
        schema_version = RepositoryView.CORE_SCHEMA_VERSION

        self._version = self.openDB(txn, name, 'version',
                                    kwds.get('ramdb', False),
                                    kwds.get('create', False),
                                    kwds.get('mvcc', False))

        if kwds.get('create', False):
            self._version.put(ValueContainer.SCHEMA_KEY,
                              pack('>16sll', UUID()._uuid,
                                   format_version, schema_version), txn)
        else:
            try:
                versionID, format, schema = self.getSchemaInfo(txn, True)
            except AssertionError:
                raise RepositoryFormatVersionError, (format_version, '< 0.6.4')

            if format != format_version:
                raise RepositoryFormatVersionError, (format_version, format)
            if schema != schema_version:
                raise RepositorySchemaVersionError, (schema_version, schema)

    def openC(self):

        self.c = CValueContainer(self._db, self.store)

    def close(self):

        if self._version is not None:
            self._version.close()
            self._version = None

        super(ValueContainer, self).close()

    def compact(self, txn):

        super(ValueContainer, self).compact(txn)
        self._version.compact(txn)

    def getSchemaInfo(self, txn=None, open=False):

        value = self._version.get(ValueContainer.SCHEMA_KEY,
                                  txn, self.c.flags, None)
        if value is None:
            raise AssertionError, 'schema record is missing'

        versionId, format, schema = unpack('>16sll', value)

        return UUID(versionId), format, schema
        
    def getVersion(self):

        value = self._version.get(ValueContainer.VERSION_KEY,
                                  self.store.txn, self.c.flags, None)
        if value is None:
            return 0
        else:
            return unpack('>l', value)[0]

    def setVersion(self, version):

        self._version.put(ValueContainer.VERSION_KEY, pack('>l', version),
                          self.store.txn)

    def nextVersion(self):

        version = self.getVersion() + 1
        self._version.put(ValueContainer.VERSION_KEY, pack('>l', version),
                          self.store.txn)

        return version

    def purgeValue(self, txn, uuid):

        self.delete(uuid._uuid, txn)
        return 1



class CommitsContainer(DBContainer):

    def logCommit(self, view, version, commitCount):

        key = pack('>l', version)
        data = pack('>Qii', long(time.time() * 1000), len(view),
                    commitCount) + view.name

        self.put(key, data)

    def getCommit(self, version):

        data = self.get(pack('>l', version))
        if data is not None:
            return self._readCommit(data)

        return None

    def purgeCommit(self, version):

        self.delete(pack('>l', version))

    def _readCommit(self, data):

        then, size, commitCount = unpack('>Qii', data[0:16])
        name = data[16:]
                        
        return then / 1000.0, size, commitCount, name

    def iterCommits(self, view, fromVersion=1, toVersion=0):

        store = self.store

        class _iterator(object):

            def __init__(_self):

                _self.cursor = None
                _self.txnStatus = 0

            def __del__(_self):

                try:
                    self.c.closeCursor(_self.cursor)
                    store.abortTransaction(view, _self.txnStatus)
                except:
                    store.repository.logger.exception("in __del__")
                _self.cursor = None
                _self.txnStatus = 0

            def next(_self):

                _self.txnStatus = store.startTransaction(view)
                _self.cursor = self.c.openCursor()
                
                try:
                    value = _self.cursor.set_range(pack('>l', fromVersion),
                                                   self.c.flags, None)

                    while value is not None:
                        key, data = value
                        version, = unpack('>l', key)
                        if toVersion and version > toVersion:
                            break

                        yield version, self._readCommit(data)

                        value = _self.cursor.next(self.c.flags, None)

                    yield False

                except DBLockDeadlockError:
                    if _self.txnStatus & store.TXN_STARTED:
                        store._logDL()
                        yield True
                    else:
                        raise

        while True:
            for result in _iterator().next():
                if result is True:
                    break
                if result is False:
                    return
                yield result
