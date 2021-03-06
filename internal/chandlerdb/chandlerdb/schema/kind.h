/*
 *  Copyright (c) 2003-2007 Open Source Applications Foundation
 *
 *  Licensed under the Apache License, Version 2.0 (the "License");
 *  you may not use this file except in compliance with the License.
 *  You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 *  Unless required by applicable law or agreed to in writing, software
 *  distributed under the License is distributed on an "AS IS" BASIS,
 *  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 *  See the License for the specific language governing permissions and
 *  limitations under the License.
 */


typedef struct {
    PyObject_HEAD
    t_item *kind;
    unsigned long flags;
    PyObject *descriptors;
    PyObject *inheritedSuperKinds;
    PyObject *notifyAttributes;
    PyObject *allAttributes;
    PyObject *allNames;
    PyObject *inheritedAttributes;
    PyObject *notFoundAttributes;
    PyObject *allCorrelations;
} t_kind;

enum {
    K_MONITOR_SCHEMA         = 0x0001,
    K_ATTRIBUTES_CACHED      = 0x0002,
    K_SUPERKINDS_CACHED      = 0x0004,
    K_DESCRIPTORS_INSTALLED  = 0x0008,
    K_DESCRIPTORS_INSTALLING = 0x0010,
    K_NOTIFY                 = 0x0020,
};
