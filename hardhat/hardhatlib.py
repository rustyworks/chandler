__version__     = "$Revision$"
__date__        = "$Date$"
__copyright__   = "Copyright (c) 2003 Open Source Applications Foundation"
__license__     = "GPL -- see LICENSE.txt"


"""
hardhatlib

hardhatlib provides a set of methods for controlling the build process of
multiple sub-projects in a uniform way.  The typical way to interact with
this library is via the hardhat.py command-line script, but you could
call these methods directly from some automated build system or GUI.
Each sub- project needs a __hardhat__.py file which defines build, clean,
and execute methods; these methods are passed a dictionary describing
the build environment.  The __hardhat__.py methods also log their status
to a structured log, and alert hardhatlib of problems via Exceptions.

"""

import os, sys, glob, errno, string, shutil, fileinput, re


# Earlier versions of Python don't define these, so let's include them here:
True = 1
False = 0

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

defaults = {
    'verbosity'         : 1,
    'showenv'           : 0,
    'version'           : 'release',
    'showlog'           : False,
    'interactive'       : True,
    'outputdir'         : "",
}

def init(buildenv):
    """
    Initialize the build environment, which is a dictionary containing
    various values for OS type, PATH, compiler, debug/release setting, etc.
    Parameters:
        root: fully qualified path to the top of the build hierarchy
    Returns:
        buildenv:  a dictionary containing the following environment settings:
            - root: the root path passed in (which should be the parent of osaf)
            - os: win, posix, unknown
            - path: system executable search path
            - compiler: full path to C compiler (currently windows only)
            - python: full path to release verion of python we are building
            - python_d: full path to debug verion of python we are building
            - verbose: 0 for quiet, > 0 for messages displayed to stdout
            - log: a time-ordered list of log entries
            - version: 'debug' or 'release'
    """

    if not buildenv.has_key('root'):
        raise HardHatBuildEnvError, "Missing 'root'"

    if not buildenv.has_key('hardhatroot'):
        raise HardHatBuildEnvError, "Missing 'hardhatroot'"

    for key in defaults.keys():
        if not buildenv.has_key(key):
            buildenv[key] = defaults[key]

    if not buildenv.has_key('logfile'):
        buildenv['logfile'] = os.path.join(buildenv['root'], "hardhat.log")

    # normalize what python thinks the OS is to a string that we like:
    buildenv['os'] = 'unknown'
    if os.name == 'nt':
        buildenv['os'] = 'win'
        buildenv['oslabel'] = 'win'
        buildenv['root_dos'] = buildenv['root']
        buildenv['path'] = os.environ['path']
    elif os.name == 'posix':
        buildenv['os'] = 'posix'
        buildenv['oslabel'] = 'linux'
        buildenv['path'] = os.environ['PATH']
        if sys.platform == 'darwin':
            # It turns out that Mac OS X happens to have os.name of 'posix'
            # but the steps to build things under OS X is different enough
            # to warrant its own 'os' value:
            buildenv['os'] = 'osx'
            buildenv['oslabel'] = 'osx'
        if sys.platform == 'cygwin':
            buildenv['os'] = 'win'
            buildenv['oslabel'] = 'win'
            buildenv['path'] = os.environ['PATH']
            try:
                cygpath = os.popen("/bin/cygpath -w " + buildenv['root'], "r")
                buildenv['root_dos'] = cygpath.readline()
                buildenv['root_dos'] = buildenv['root_dos'][:-1]
                cygpath.close()
            except Exception, e:
                print e
                print "Unable to call 'cygpath' to determine DOS-equivalent for project path."
                print "Either make sure that 'cygpath' is in your PATH or run the Windows version"
                print "of Python from http://python.org/, rather than the Cygwin Python"
                raise HardHatError

    else:
        raise HardHatUnknownPlatformError

    # set up paths to the pythons we are building (release and debug)
    buildenv['python'] = buildenv['root'] + os.sep + 'release' + os.sep + \
     'bin' + os.sep + 'python'
    buildenv['python_d'] = buildenv['root'] + os.sep + 'debug' + os.sep + \
     'bin' + os.sep + 'python_d'

    buildenv['sh']   = findInPath(buildenv['path'], "sh")
    buildenv['make'] = findInPath(buildenv['path'], "make")
    buildenv['cvs']  = findInPath(buildenv['path'], "cvs")
    buildenv['scp']  = findInPath(buildenv['path'], "scp")
    buildenv['tar']  = findInPath(buildenv['path'], "tar")
    buildenv['gzip'] = findInPath(buildenv['path'], "gzip")
    buildenv['zip']  = findInPath(buildenv['path'], "zip")

    
    # set OS-specific variables
    if buildenv['os'] == 'win':

        buildenv['python'] = buildenv['root'] + os.sep + 'release' + os.sep + \
         'bin' + os.sep + 'python.exe'
        buildenv['python_d'] = buildenv['root'] + os.sep + 'debug' + os.sep + \
         'bin' + os.sep + 'python_d.exe'

        import os_win
        
        vs = os_win.VisualStudio();
        buildenv['compilerVersion'] = vs.version
        
        # log(buildenv, HARDHAT_MESSAGE, "HardHat", "Looking for devenv.exe...")
        devenv_file = vs.find_exe( "devenv.exe")
        if( devenv_file ):
            # log(buildenv, HARDHAT_MESSAGE, "HardHat", "Found " + devenv_file)
            buildenv['compiler'] = devenv_file
        else:
            log(buildenv, HARDHAT_ERROR, "HardHat", "Can't find devenv.exe")
            log_dump(buildenv)
            raise HardHatMissingCompilerError

        # log(buildenv, HARDHAT_MESSAGE, "HardHat", "Looking for nmake.exe...")
        nmake_file = vs.find_exe( "nmake.exe")
        if( nmake_file ):
            # log(buildenv, HARDHAT_MESSAGE, "HardHat", "Found " + nmake_file)
            buildenv['nmake'] = nmake_file
        else:
            log(buildenv, HARDHAT_ERROR, "HardHat", "Can't find nmake.exe")
            log_dump(buildenv)
            raise HardHatMissingCompilerError
        include_path = vs.get_msvc_paths('include')
        include_path = string.join( include_path, ";")
        # log(buildenv, HARDHAT_MESSAGE, "HardHat", "Include: " + include_path)
        os.putenv('INCLUDE', include_path)
        lib_path = vs.get_msvc_paths('library')
        lib_path = string.join( lib_path, ";")
        # log(buildenv, HARDHAT_MESSAGE, "HardHat", "lib: " + lib_path)
        os.putenv('LIB', lib_path)

        cl_dir = os.path.dirname(nmake_file)
        buildenv['path'] = cl_dir + os.pathsep + buildenv['path']
        devenv_dir = os.path.dirname(devenv_file)
        buildenv['path'] = devenv_dir + os.pathsep + buildenv['path']

        buildenv['swig'] = buildenv['root'] + os.sep + 'release' + os.sep + \
         'bin' + os.sep + 'swig.exe'
        buildenv['swig_d'] = buildenv['root'] + os.sep + 'debug' + os.sep + \
         'bin' + os.sep + 'swig.exe'

    if buildenv['os'] == 'posix':
        buildenv['swig'] = buildenv['root'] + os.sep + 'release' + os.sep + \
         'bin' + os.sep + 'swig'
        buildenv['swig_d'] = buildenv['root'] + os.sep + 'debug' + os.sep + \
         'bin' + os.sep + 'swig'


    if buildenv['os'] == 'osx':
        buildenv['swig'] = buildenv['root'] + os.sep + 'release' + os.sep + \
         'bin' + os.sep + 'swig'
        buildenv['swig_d'] = buildenv['root'] + os.sep + 'debug' + os.sep + \
         'bin' + os.sep + 'swig'

        buildenv['python'] = os.path.join(buildenv['root'], 'release', 
         'Library', 'Frameworks', 'Python.framework', 'Versions', 'Current', 
         'Resources', 'Python.app', 'Contents', 'MacOS', 'python')

        buildenv['python_d'] = os.path.join(buildenv['root'], 'debug', 
         'Library', 'Frameworks', 'Python.framework', 'Versions', 'Current', 
         'Resources', 'Python.app', 'Contents', 'MacOS', 'python')

    # Determine the Python lib directory (the parent of site-packages)
    if buildenv['os'] == 'posix':
        lib_dir_release = buildenv['root'] + os.sep + 'release' + os.sep + \
         'lib' + os.sep + 'python2.3'
        lib_dir_debug = buildenv['root'] + os.sep + 'debug' + os.sep + \
         'lib' + os.sep + 'python2.3'
    if buildenv['os'] == 'win':
        lib_dir_release = buildenv['root'] + os.sep + 'release' + os.sep + \
         'bin' + os.sep + 'Lib'
        lib_dir_debug = buildenv['root'] + os.sep + 'debug' + os.sep + \
         'bin' + os.sep + 'Lib'
    if buildenv['os'] == 'osx':
        lib_dir_release = buildenv['root'] + os.sep + 'release' + os.sep + \
         'Library/Frameworks/Python.framework/Versions/Current/lib/python2.3'
        lib_dir_debug = buildenv['root'] + os.sep + 'debug' + os.sep + \
         'Library/Frameworks/Python.framework/Versions/Current/lib/python2.3'

    buildenv['pythonlibdir'] = lib_dir_release
    buildenv['pythonlibdir_d'] = lib_dir_debug


    return buildenv
# end init()

def inspectSystem():
    print "Not implemented yet"
    return

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Log-related functions and message types

# Types of log messages, used as 2nd parameter to log()
HARDHAT_MESSAGE = 0  # Normal log message
HARDHAT_WARNING = 1  # Warning message
HARDHAT_ERROR   = 2  # Error message


def log(buildenv, status, module_name, message):
    """
    Store a message to the hardhat log.  Display the message on stdout if
    verbose parameter is > 0.
    Parameters:
        buildenv: the build environment dictionary
        status: one of the three types defined above
        module_name: a string identifying the source of this message
        message: the message string itself
    Returns:
        nothing
    """

    if not buildenv.has_key('log'):
        buildenv['log'] = []
    buildenv['log'].append((status, module_name, message))
    if buildenv.has_key('verbosity'):
        if buildenv['verbosity'] > 0:
            entry_dump((status, module_name, message))

    output = file(buildenv['logfile'], 'a+', 0)
    entry_dump((status, module_name, message), output)
    output.close()

# end log()


def entry_dump(entry, file=sys.stdout):
    """
    Print a single entry to stdout.
    Parameters:
        entry: a tuple of the following format (status, module_name, message)
    Returns:
        nothing
    """

    file.write("[ " + entry[1] + " ]")
    if entry[0] == HARDHAT_WARNING:
        file.write(" WARNING ")
    if entry[0] == HARDHAT_ERROR:
        file.write(" ***ERROR*** ")
    file.write(": " + entry[2] + "\n")
# end entry_dump()


def log_dump(buildenv):
    """
    Display the entire log to stdout.
    Parameters:
        buildenv: the build environment dictionary containing the log.
    Returns:
        nothing
    """

    if buildenv.has_key('log'):
        for entry in buildenv['log']:
            entry_dump(entry)
# end log_dump()


def log_rotate(buildenv):
    """
    Rotates log files by renaming hardhat.log --> hardhat.log.1
    and so on up to hardhat.log.5
    """
    logfiles = [buildenv['logfile']]
    for i in range(1,6):
        logfiles.append(buildenv['logfile'] + "." + str(i))
    for i in range(len(logfiles)-1,-1,-1):
        if os.path.isfile(logfiles[i]):
            if( i == 5 ):
                os.remove(logfiles[i])
            else:
                os.rename(logfiles[i], logfiles[i+1])


            
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Build, clean, execute functions

def clean(buildenv, module_name):
    """
    Prepare then invoke the clean() method for the given module_name.  Current
    working directory is set to the subproject's directory before executing
    its clean() method.
    Parameters:
        buildenv: the build environment dictionary
        module_name: the directory name of the subproject to clean
    Returns:
        nothing
    """

    os.chdir(buildenv['root'])
    # log(buildenv, HARDHAT_MESSAGE, module_name, "Cleaning")
    module_path = buildenv['root'] + os.sep + module_name + os.sep + \
     "__hardhat__.py"
    module = module_from_file(buildenv, module_path, module_name)
    os.chdir(module_name)
    module.clean(buildenv)
    # log(buildenv, HARDHAT_MESSAGE, module_name, "Back from clean")
# end clean()


def cleanDependencies(buildenv, module_name, history):
    """
    Based on the list of dependencies in the module's __hardhat_.py file, 
    call each one's clean(), and then call module's clean().
    Parameters:
        buildenv: the build environment dictionary
        module_name: the directory name of the subproject
        history: keeps track of which subprojects have been cleaned, so that
         each is cleaned only once
    Returns:
        nothing
    """

    module_path = buildenv['root'] + os.sep + module_name + os.sep + \
     "__hardhat__.py"
    module = module_from_file(buildenv, module_path, module_name)
    clean(buildenv, module_name)
    history[module_name] = 1
    dep_list = list(module.dependencies)
    dep_list.reverse()
    for dependency in dep_list:
        if not history.has_key(dependency):
            cleanDependencies(buildenv, dependency, history)
# end cleanDependencies()




def build(buildenv, module_name):
    """
    Prepare then invoke the build() method for the given module_name.  Current
    working directory is set to the subproject's directory before executing
    its build() method.
    Parameters:
        buildenv: the build environment dictionary
        module_name: the directory name of the subproject to build
    Returns:
        nothing
    """

    os.chdir(buildenv['root'])
    # log(buildenv, HARDHAT_MESSAGE, module_name, "Building")
    module_path = buildenv['root'] + os.sep + module_name + os.sep + \
     "__hardhat__.py"
    module = module_from_file(buildenv, module_path, module_name)
    os.chdir(module_name)
    module.build(buildenv)
    # log(buildenv, HARDHAT_MESSAGE, module_name, "Back from build")
# end build()

    
def buildDependencies(buildenv, module_name, history):
    """
    Based on the list of dependencies in the module's __hardhat_.py file, 
    call each one's build(), and then call module's build().
    Parameters:
        buildenv: the build environment dictionary
        module_name: the directory name of the subproject
        history: keeps track of which subprojects have been built, so that
         each is built only once
    Returns:
        nothing
    """

    module_path = buildenv['root'] + os.sep + module_name + os.sep + \
     "__hardhat__.py"
    module = module_from_file(buildenv, module_path, module_name)
    for dependency in module.dependencies:
        if not history.has_key(dependency):
            buildDependencies(buildenv, dependency, history)
    build(buildenv, module_name)
    history[module_name] = 1
# end buildDependencies()



def scrub(buildenv, module_name):
    """
    Calls cleanCVS to remove all local files that aren't under CVS control.
    This is helpful when you want to make sure that the module is really clean!
    Parameters:
        buildenv: the build environment dictionary
        module_name: the directory name of the subproject to scrub
    Returns:
        nothing
    """

    os.chdir(buildenv['root'])
    # log(buildenv, HARDHAT_MESSAGE, module_name, "Building")
    module_path = buildenv['root'] + os.sep + module_name 
    cvsClean(buildenv, [module_path])
    # log(buildenv, HARDHAT_MESSAGE, module_name, "Back from build")
# end scrub()

    
def scrubDependencies(buildenv, module_name):
    """
    Based on the list of dependencies in the module's __hardhat_.py file, 
    call scrub() on each one, and then call scrub() on the module.
    Parameters:
        buildenv: the build environment dictionary
        module_name: the directory name of the subproject
    Returns:
        nothing
    """

    dependencies = {}
    getDependencies(buildenv, module_name, dependencies)
    dirsToScrub = []
    for dep in dependencies.keys():
        dirsToScrub.append(buildenv['root'] + os.sep + dep)
    cvsClean(buildenv, dirsToScrub)
# end scrubDependencies()

def getDependencies(buildenv, module_name, history):
    module_path = buildenv['root'] + os.sep + module_name + os.sep + \
     "__hardhat__.py"
    module = module_from_file(buildenv, module_path, module_name)
    for dependency in module.dependencies:
        if not history.has_key(dependency):
            getDependencies(buildenv, dependency, history)
    history[module_name] = 1



def run(buildenv, module_name):
    """
    Execute the run() method for the given module.  Current working directory
    is set to that of the subproject before execution.
    Parameters:
        buildenv: the build environment dictionary
        module_name:  the directory name of the subproject whose execute() 
         method we are calling.
    Returns:    
        nothing
    """
    log(buildenv, HARDHAT_MESSAGE, module_name, "Executing")
    os.chdir(buildenv['root'])
    module_path = buildenv['root'] + os.sep + module_name + os.sep + \
     "__hardhat__.py"
    module = module_from_file(buildenv, module_path, module_name)
    os.chdir(module_name)

    # Under Windows, python gets part of sys.path from the registry,
    # but this can be a problem since it might get site-packages from
    # the wrong python installation.  By setting PYTHONPATH we can
    # guarantee that our site-packages will be first in the path
    if buildenv['os'] == 'win':
        pythonPath = buildenv['root'] + '\\' + \
         buildenv['version'] + '\\bin\\lib\\site-packages' 
        os.putenv('PYTHONPATH', pythonPath)

    module.run(buildenv)
    log(buildenv, HARDHAT_MESSAGE, module_name, "Execution complete")
# end run()


def removeRuntimeDir(buildenv, module_name):
    """
    Remove the "release" or "debug" directory for the module.  [Can someone
    think of a better name for what these directories are, besides "runtime"?]
    Current working directory is set to that of the subproject before 
    execution.
    Parameters:
        buildenv: the build environment dictionary
        module_name:  the directory name of the subproject whose
         removeRuntimeDir() method we are calling
    Returns:    
        nothing
    """

    log(buildenv, HARDHAT_MESSAGE, module_name, "Removing runtime directory")
    os.chdir(buildenv['root'])
    module_path = buildenv['root'] + os.sep + module_name + os.sep + \
     "__hardhat__.py"
    module = module_from_file(buildenv, module_path, module_name)
    os.chdir(module_name)
    module.removeRuntimeDir(buildenv)
    log(buildenv, HARDHAT_MESSAGE, module_name, "Removal complete")
# end removeRuntimeDir()


def distribute(buildenv, module_name, buildVersion):
    """
    Execute the distribute() method for the given module.  Current working 
    directory is set to that of the subproject before execution.
    Parameters:
        buildenv: the build environment dictionary
        module_name:  the directory name of the subproject whose execute() 
         method we are calling.
    Returns:    
        nothing
    """
    log(buildenv, HARDHAT_MESSAGE, module_name, "Creating distribution")
    os.chdir(buildenv['root'])
    module_path = buildenv['root'] + os.sep + module_name + os.sep + \
     "__hardhat__.py"
    module = module_from_file(buildenv, module_path, module_name)
    os.chdir(module_name)

    buildenv["buildVersion"] = buildVersion
    module.distribute(buildenv)
    log(buildenv, HARDHAT_MESSAGE, module_name, "Distribution complete")
# end distribute()

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Unit testing functions


def recursiveTest(buildenv, path):
    path = os.path.abspath(path)
    os.chdir(path)

    if buildenv['version'] == 'debug':
        python = buildenv['python_d']
        libdir = buildenv['pythonlibdir_d']
    if buildenv['version'] == 'release':
        python = buildenv['python']
        libdir = buildenv['pythonlibdir']

    if os.path.isdir("tests"):
        fullTestPath = os.path.join(path, "tests")
        os.chdir(fullTestPath) 
        testFiles = glob.glob('Test*.py')
        for testFile in testFiles:
            fullTestFilePath = os.path.join(fullTestPath, testFile)
            exit_code = executeCommand( buildenv, testFile, [python, testFile,
            "-v"], "Testing " + fullTestFilePath, HARDHAT_NO_RAISE_ON_ERROR)
            if exit_code != 0:
                buildenv['test_failures'] = buildenv['test_failures'] + 1
                buildenv['failed_tests'].append(fullTestFilePath)

    os.chdir(path)
    for name in os.listdir(path):
        full_name = os.path.join(path, name)
        if os.path.isdir(full_name):
            recursiveTest(buildenv, full_name)


def test(buildenv, module_name):
    """
    This needs to be fleshed out a bit more, but it will invoke all tests
    under the folder "module_name" that live in any folder called "tests"
    and that has a file named "Test*.py"
    """

    os.chdir(buildenv['root'])
    buildenv['test_failures'] = 0
    buildenv['failed_tests'] = []
    recursiveTest(buildenv, module_name)
    failures = buildenv['test_failures']

    if failures == 0:
        log(buildenv, HARDHAT_MESSAGE, 'Tests', "All tests successful")
    else:
        log(buildenv, HARDHAT_ERROR, 'Tests', "%d test(s) failed" % failures)
        for testFile in buildenv['failed_tests']:
            log(buildenv, HARDHAT_ERROR, 'Tests', "Failed: %s" % testFile)
        raise HardHatUnitTestError

# end test()


def generateDocs(buildenv, module_name):
    os.chdir(buildenv['root'])
    # log(buildenv, HARDHAT_MESSAGE, module_name, "Building")
    module_path = buildenv['root'] + os.sep + module_name + os.sep + \
     "__hardhat__.py"
    module = module_from_file(buildenv, module_path, module_name)
    os.chdir(module_name)
    module.generateDocs(buildenv)
    # log(buildenv, HARDHAT_MESSAGE, module_name, "Back from build")
# end build()



# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Module import functions

def module_from_file(buildenv, module_path, module_name):
    """ 
    Load a module from a file into a code object.
    Parameters:
        buildenv: the build environment dictionary
        module_path: absolute path to python file
        module_name: name assigned to code object
    Returns:
        code module object
    """


    if os.access(module_path, os.R_OK):
        module_file = open(module_path)

        # Here's a cool bug I had to workaround:  if module_name has a "." in
        # it, bad things happen down the road (exceptions get created within
        # invalid package); example:  if module_name is 'wxWindows-2.4' then
        # hardhatlib throws an exception and it gets created as 
        # wxWindows-2.hardhatlib.HardHatError.  The fix is to replace "." with
        # "_"
        module_name = module_name.replace(".", "_")

        module = import_code(module_file, module_name)
        return module
    else:
        if buildenv:
            log(buildenv, HARDHAT_ERROR, 'hardhat', module_path + \
             "doesn't exist")
        raise HardHatMissingFileError, "Missing " + module_path
# end module_from_file()


def import_code(code, name):
    """
    Imports python code from open file handle into a code module object.
    Parameters:
        code: an open file handle containing python code
        name: a name to assign to this module
    Returns:
        code module object
    """

    import imp
    module = imp.new_module(name)
    sys.modules[name] = module
    exec code in module.__dict__
    return module
# end import_code()


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Utility functions

def rmdir_recursive(dir):
    """
    Recursively remove a directory.
    Parameters:
        dir: directory path
    Returns:
        nothing
    """

    if os.path.islink(dir):
        os.remove(dir)
        return

    for name in os.listdir(dir):
        full_name = os.path.join(dir, name)
        # on Windows, if we don't have write permission we can't remove
        # the file/directory either, so turn that on
        if os.name == 'nt':
            if not os.access(full_name, os.W_OK):
                os.chmod(full_name, 0600)
        if os.path.isdir(full_name):
            rmdir_recursive(full_name)
        else:
            # print "removing file", full_name
            os.remove(full_name)
    os.rmdir(dir)
# rmdir_recurisve()

def rm_files(dir, pattern):
    """
    Remove files in a directory matching pattern
    Parameters:
        dir: directory path
        patter: filename pattern
    Returns:
        nothing
    """

    pattern = '^%s$' %(pattern)
    pattern = pattern.replace('.', '\\.').replace('*', '.*').replace('?', '.')
    exp = re.compile(pattern)
    
    for name in os.listdir(dir):
        if exp.match(name):
            full_name = os.path.join(dir, name)
            if not os.path.isdir(full_name):

                # on Windows, if we don't have write permission we can't remove
                # the file/directory either, so turn that on
                if os.name == 'nt':
                    if not os.access(full_name, os.W_OK):
                        os.chmod(full_name, 0600)

                os.remove(full_name)
# rm_files()

def executeScript(buildenv, args):

    if buildenv['version'] == 'debug':
        python = buildenv['python_d']

    if buildenv['version'] == 'release':
        python = buildenv['python']

    # script = args[0]
    print [python] + args
    executeCommandNoCapture( buildenv, "HardHat",
     [python] + args, "Running" )

def findHardHatFile(dir):
    """ Look for __hardhat__.py in directory "dir", and if it's not there,
        keep searching up the directory hierarchy; return the first directory
        that contains a __hardhat__.py file.  If / is reached without finding
        one, return None.
    """
    absPath = os.path.abspath(dir)
    if os.path.isfile(os.path.join(absPath, "__hardhat__.py")):
        return os.path.join(absPath, "__hardhat__.py")
    prevHead = None
    (head, tail) = os.path.split(absPath)
    print "Looking for __hardhat__.py in..."
    while head != prevHead:
        print " ", head,
        if os.path.isfile(os.path.join(head, "__hardhat__.py")):
            print " ...found one"
            print
            return os.path.join(head, "__hardhat__.py")
        prevHead = head
        print " ...no"
        (head, tail) = os.path.split(head)
    print
    return None


def lint(buildenv, args):
    """ Run PyChecker against the scripts passed in as args """

    if buildenv['version'] == 'debug':
        python = buildenv['python_d']
        sitePackages = os.path.join(buildenv['pythonlibdir_d'], "site-packages")

    if buildenv['version'] == 'release':
        python = buildenv['python']
        sitePackages = os.path.join(buildenv['pythonlibdir'], "site-packages")

    checkerFile = os.path.join(sitePackages, "pychecker", "checker.py")

    executeCommandNoCapture( buildenv, "HardHat",
     [python, checkerFile] + args, "Running PyChecker" )


def mirrorDirSymlinks(src, dest):
    """ Recreate the directory structure of src under dest, with symlinks
        pointing to the files in src.  src and dest must be absolute.  """

    if not os.path.exists(dest):
        os.mkdir(dest)

    for name in os.listdir(src):
        fullName = os.path.join(src, name)
        if os.path.isdir(fullName):
            mirrorDirSymlinks(fullName, os.path.join(dest, name))
        if os.path.isfile(fullName):
            if not os.path.exists(os.path.join(dest, name)):
                os.symlink(fullName, os.path.join(dest, name))


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# External program control functions

def setupEnvironment(buildenv):

    if buildenv['version'] == 'debug':
        path = buildenv['root'] + os.sep + 'debug' + os.sep + 'bin' + \
         os.pathsep + buildenv['path']
        os.putenv('BUILDMODE', 'debug')

    if buildenv['version'] == 'release':
        path = buildenv['root'] + os.sep + 'release' + os.sep + 'bin' + \
         os.pathsep + buildenv['path']
        os.putenv('BUILDMODE', 'release')

    # to run Chandler-related scripts from directories other than 
    # osaf/chandler/Chandler, PYTHONPATH is needed
    pythonpaths = []
    prevPath = os.getenv('PYTHONPATH')
    if prevPath:
        pythonpaths.append(prevPath)

    # need to add Chandler and Chandler/parcels to PYTHONPATH
    pythonpaths.append(os.path.join(buildenv['root'], "Chandler"))
    pythonpaths.append(os.path.join(buildenv['root'], "Chandler", "parcels"))
    pythonpath = os.pathsep.join(pythonpaths)

    # log(buildenv, HARDHAT_MESSAGE, 'hardhat', "Setting path to " + path)
    # os.putenv('path', path)
    if (sys.platform == 'cygwin'):
        # Even though we're under cygwin, we're going to be launching 
        # external programs that expect PATH to be in DOS format, so
        # convert it
        try:
            if('.'.join(map(str, sys.version_info[:3])) < '2.3.0'):
                # we only need to fix the path on versions before 2.3
                cygpath = os.popen("/bin/cygpath -wp \"" + path + "\"", "r")
                path = cygpath.readline()
                path = path[:-1]
                cygpath.close()

            # also convert PYTHONPATH to DOS format
            cygpath = os.popen("/bin/cygpath -wp \"" + pythonpath + "\"", "r")
            pythonpath = cygpath.readline()
            pythonpath = pythonpath[:-1]
            cygpath.close()

        except Exception, e:
            print e
            print "Unable to call 'cygpath' to determine DOS-equivalent for PATH"
            print "Either make sure that 'cygpath' is in your PATH or run the Windows version"
            print "of Python from http://python.org/, rather than the Cygwin Python"
            raise HardHatError

    os.putenv('PATH', path)
    os.putenv('PYTHONPATH', pythonpath)

    if buildenv['os'] == 'win':
        # Use DOS format paths under windows
        os.putenv('CHANDLERDIR', buildenv['root_dos']+"\\Chandler")
        os.putenv('CHANDLERHOME', buildenv['root_dos'])
    else:
        os.putenv('CHANDLERDIR', buildenv['root']+os.sep+"Chandler")
        os.putenv('CHANDLERHOME', buildenv['root'])


    if buildenv['os'] == 'posix':
        ld_library_path = os.environ.get('LD_LIBRARY_PATH', '')
        ver = buildenv['version']
        additional_path=os.path.join(buildenv['root'],ver,'lib')+\
         os.pathsep + os.path.join(buildenv['root'],ver,'db','lib')+\
         os.pathsep + os.path.join(buildenv['root'],ver,'dbxml','lib')
        ld_library_path = additional_path + os.pathsep + ld_library_path
        os.putenv('LD_LIBRARY_PATH', ld_library_path)

    if buildenv['os'] == 'osx':
        dyld_library_path = os.environ.get('DYLD_LIBRARY_PATH', '')
        ver = buildenv['version']
        additional_path=os.path.join(buildenv['root'],ver,'lib')+\
         os.pathsep + os.path.join(buildenv['root'],ver,'db','lib')+\
         os.pathsep + os.path.join(buildenv['root'],ver,'dbxml','lib')
        dyld_library_path = additional_path + os.pathsep + dyld_library_path
        os.putenv('DYLD_LIBRARY_PATH', dyld_library_path)

        dyld_framework_path = os.environ.get('DYLD_FRAMEWORK_PATH', '')
        additional_path = os.path.join( buildenv['root'], ver, 'Library',
         'Frameworks')
        dyld_framework_path = additional_path + os.pathsep + dyld_framework_path
        os.putenv('DYLD_FRAMEWORK_PATH', dyld_framework_path)

def quoteString(str):
    return "\'" + str + "\'"

def escapeSpaces(str):
    return str.replace(" ", "|")

def escapeBackslashes(str):
    return str.replace("\\", "\\\\")

HARDHAT_NO_RAISE_ON_ERROR = 1

def executeCommand(buildenv, name, args, message, flags=0, extlog=None):

    setupEnvironment(buildenv)

    wrapper = buildenv['hardhatroot'] + os.sep + "wrapper.py"
    logfile = buildenv['logfile']

    if buildenv['showenv']:
        showenv = "yes"
    else:
        showenv = "no"

    # spawnl wants the name of the file we're executing twice -- however,
    # on windows the second one can't have spaces in it, so we just pass
    # in the basename()
    if buildenv['os'] == 'win' and sys.platform != 'cygwin':
        # args[0] is the path to the exe we want wrapper to run.  If it has
        # a space in it, it doesn't get passed to wrapper correctly (under
        # windows), so convert spaces to pipes (which windows filenames
        # aren't allowed to contain).  These will then get converted back
        # to spaces inside wrapper.py
        args[0] = escapeSpaces(args[0])
        args[:0] = [sys.executable, os.path.basename(sys.executable), wrapper, 
         logfile, showenv]
    else:
        args[:0] = [sys.executable, sys.executable, wrapper, 
         logfile, showenv]
    args = map(escapeBackslashes, args)

    if not os.path.exists(args[0]):
        log(buildenv, HARDHAT_ERROR, name, "Program does not exist: " + \
         args[0])
        if not (flags & HARDHAT_NO_RAISE_ON_ERROR):
            raise HardHatExternalCommandError
        return 127 # standard not found exit code

    # all args need to be quoted
    args = map(quoteString, args)

    args_str = ','.join(args)
    execute_str = "exit_code = os.spawnl(os.P_WAIT," + args_str + ")"
    # print execute_str

    log(buildenv, HARDHAT_MESSAGE, name, message)
    
    exec(execute_str)

    if extlog:
        # The program just executed put its output to an external log file
        # (specifically this is for Visual Studio, which apparently doesn't
        # want to send output to stdout).  Read the external log file and
        # inject it into our hardhat log.
        try:
            extlogfile = file(extlog, 'r')
            lines = extlogfile.readlines()
            buildlog = file(buildenv['logfile'], 'a+', 0)
            for line in lines:
                buildlog.write(line)
            extlogfile.close()

        except Exception, e:
            log(buildenv, HARDHAT_ERROR, name, "Trouble opening " + extlog + \
             ":" + str(e))
       

    if exit_code == 0:
        log(buildenv, HARDHAT_MESSAGE, name, "OK")
    else:
        log(buildenv, HARDHAT_ERROR, name, "Exit code = " + str(exit_code) )
        if not (flags & HARDHAT_NO_RAISE_ON_ERROR):
            raise HardHatExternalCommandError
    
    return exit_code


def executeCommandNoCapture(buildenv, name, args, message, flags=0):

    setupEnvironment(buildenv)

    # spawnl wants the name of the file we're executing twice -- the first
    # one is the full path, the second is just the filename
    if buildenv['os'] == 'win' and sys.platform != 'cygwin':
        args[1:0] = [ os.path.basename(args[0]) ]
    else:
        args[:0] = [ args[0] ]
    args = map(escapeBackslashes, args)

    # all args need to be quoted
    args = map(quoteString, args)

    args_str = ','.join(args)
    execute_str = "exit_code = os.spawnl(os.P_WAIT," + args_str + ")"

    log(buildenv, HARDHAT_MESSAGE, name, message)
    log(buildenv, HARDHAT_MESSAGE, name, ",".join(args[0:]))
    

    print "\nExecution output - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -\n"
    exec(execute_str)
    print "\nExecution complete - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -\n"

    if exit_code == 0:
        log(buildenv, HARDHAT_MESSAGE, name, "OK")
    else:
        log(buildenv, HARDHAT_ERROR, name, "Command exited with code = " + str(exit_code) )
        if not (flags & HARDHAT_NO_RAISE_ON_ERROR):
            raise HardHatExternalCommandError
    
    return exit_code


def executeShell(buildenv):

    setupEnvironment(buildenv)

    shell = os.environ['SHELL']
    args = [shell]
    name = "HardHat"
    message = "Running shell"

    os.putenv('PROMPT', "HardHat Shell>")

    # spawnl wants the name of the file we're executing twice
    args[:0] = [ args[0] ]
    args = map(escapeBackslashes, args)

    if buildenv['os'] == 'win':
        args = map(escapeArgForWindows, args)

    # all args need to be quoted
    args = map(quoteString, args)

    args_str = ','.join(args)
    execute_str = "exit_code = os.spawnl(os.P_WAIT," + args_str + ")"

    log(buildenv, HARDHAT_MESSAGE, name, message)
    log(buildenv, HARDHAT_MESSAGE, name, ",".join(args[1:]))
    
    print execute_str

    print "\nYou are now in an interactive shell; don't forget to 'exit' when done"
    exec(execute_str)
    print "\nBack from interactive shell"

    if exit_code == 0:
        log(buildenv, HARDHAT_MESSAGE, name, "OK")
    else:
        log(buildenv, HARDHAT_ERROR, name, "Exit code = " + str(exit_code) )
    
    return exit_code


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Manifest processing functions

# A manifest file describes which files to copy and where they should go in
# order to create a binary distribution.  Comments are denoted by #; empty
# lines are skipped.  There are four "variables" that you set in order to
# control what's going on:  src, dest, recursive, and glob.  The file is
# processed sequentially; variables maintain their values until reassigned.
# The "src" variable should be set to a path relative to buildenv['root'],
# and "dest" should be set to a path relative to buildenv['distdir']; either
# can be set to an empty string (e.g. "dest=").  When a non-assignment line
# is reached (meaning it doesn't have an "=" in it), that line is assumed
# to represent a path relative to "src".  If a file exists there, that file
# is copied to the "dest" directory; if instead a directory exists there, 
# then the patterns specified in the most recent "glob" line are used to
# look for matching files to copy.  Then if "recursive" is set to "yes",
# subdirectories are recursively copied (but only the files matching the
# current pattern).

def handleManifest(buildenv, filename):

    params = {}
    params["src"] = None
    params["dest"] = None
    params["recursive"] = True
    params["glob"] = "*"
    srcdir = buildenv['root']
    destdir = buildenv['distdir']

    for line in fileinput.input(filename):
        line = line.strip()
        if len(line) == 0:
            continue
        if line[0:1] == "#":
            continue

        if line.find("=") != -1:
            (name,value) = line.split("=")
            params[name] = value
            if name == "src":
                srcdir = os.path.join(buildenv['root'],value)
                log(buildenv, HARDHAT_MESSAGE, "HardHat", "src=" + srcdir)
            if name == "dest":
                destdir = os.path.join(buildenv['distdir'],value)
                log(buildenv, HARDHAT_MESSAGE, "HardHat", "dest=" + destdir)
            if name == "glob":
                params['glob'] = value.split(",")
                log(buildenv, HARDHAT_MESSAGE, "HardHat", "pattern=" + value)
            if name == "recursive":
                if value == "yes":
                    params["recursive"] = True
                else:
                    params["recursive"] = False
                log(buildenv, HARDHAT_MESSAGE, "HardHat", "recursive=" + value)

        else:
            abspath = os.path.join(srcdir,line)
            if os.path.isdir(abspath):
                log(buildenv, HARDHAT_MESSAGE, "HardHat", abspath)
                copyto = os.path.join(buildenv['distdir'], params["dest"], line)
                _copyTree(abspath, copyto, params["recursive"], params["glob"])
            else:
                if os.path.exists(abspath):
                    log(buildenv, HARDHAT_MESSAGE, "HardHat", abspath)
                    copyto = os.path.join(buildenv['distdir'], params["dest"],
                     line)
                    createpath = os.path.dirname(copyto)
                    _mkdirs(createpath)
                    shutil.copy(abspath, copyto)
                else:
                    log(buildenv, HARDHAT_WARNING, "HardHat", "File missing: " 
                     + abspath)
                    continue

def _copyTree(srcdir, destdir, recursive, patterns):
    os.chdir(srcdir)
    for pattern in patterns:
        matches = glob.glob(pattern)
        for match in matches:
            if os.path.isfile(match):
                if not os.path.exists(destdir):
                    _mkdirs(destdir)
                shutil.copy(match, destdir)
    if recursive:
        for name in os.listdir(srcdir):
            full_name = os.path.join(srcdir, name)
            if os.path.isdir(full_name):
                _copyTree(full_name, os.path.join(destdir, name), True, 
                 patterns)

def _mkdirs(newdir, mode=0777):
    try: 
        os.makedirs(newdir, mode)
    except OSError, err:
        # Reraise the error unless it's about an already existing directory 
        if err.errno != errno.EEXIST or not os.path.isdir(newdir): 
            raise

def copyFile(srcfile, destdir):
    _mkdirs(destdir)
    shutil.copy(srcfile, destdir)


def copyFiles(srcdir, destdir, patterns):
    for pattern in patterns:
        matches = glob.glob(os.path.join(srcdir, pattern))
        for match in matches:
            if os.path.isfile(match):
                if not os.path.exists(destdir):
                    _mkdirs(destdir)
                shutil.copy(match, destdir)

def copyTree(srcdir, destdir, patterns):
    for pattern in patterns:
        matches = glob.glob(os.path.join(srcdir, pattern))
        for match in matches:
            if os.path.isfile(match):
                if not os.path.exists(destdir):
                    _mkdirs(destdir)
                shutil.copy(match, destdir)
    for name in os.listdir(srcdir):
        fullpath = os.path.join(srcdir, name)
        if os.path.isdir(fullpath):
            copyTree(fullpath, os.path.join(destdir, name), patterns)


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# CVS-cleaning methods

def cvsFindRemovables(dir):
    """ Find all files in the given directory (and its children) that aren't 
    checked into CVS and return them in a list """

    removables = []
    dir = os.path.abspath(dir)
    cvsEntriesFile = os.path.join(dir, "CVS", "Entries")
    cvsEntriesLogFile = os.path.join(dir, "CVS", "Entries.Log")
    if(os.path.isfile(cvsEntriesFile)):

        """
        According to http://www.cvshome.org/docs/manual/cvs_2.html#IDX42
        you will find an Entries file inside CVS/ and possibly an Entries.log
        file.  Files/dirs listed in Entries are considered to be under CVS
        control, and are added to our cvsFiles dict.
        Next, if Entries.log exists, all lines beginning with "A " are
        treated as if they were read from Entries.  All lines beginning with
        "R " have been removed from CVS, so lines from the Entries.log file
        modify the cvsFiles dict accordingly.  
        Once we have the list of CVS files, each local file is compared
        to that list and those not under CVS control are added to the
        removeables list.
        """

        cvsFiles = {}
        for line in fileinput.input(cvsEntriesFile):
            line = line.strip()
            fields = line.split("/")
            if len(fields) > 1 and fields[1]:
                cvsFiles[fields[1]] = 1 # this one is in CVS

        if(os.path.isfile(cvsEntriesLogFile)):
            for line in fileinput.input(cvsEntriesLogFile):
                line = line.strip()
                if line[0] == "A" and line[1] == " ":
                    # Consider this as if it were in "Entries"
                    line = line[2:]
                    fields = line.split("/")
                    if len(fields) > 1 and fields[1]:
                        cvsFiles[fields[1]] = 1 # this one is in CVS
                else:
                    if line[0] == "R" and line[1] == " ":
                        # Consider this as if it were not in "Entries"
                        line = line[2:]
                        fields = line.split("/")
                        if len(fields) > 1 and fields[1]:
                            cvsFiles[fields[1]] = 0 # not in CVS

        for file in os.listdir(dir):
            if file != "CVS": # always skip "CVS" directory
                absFile = os.path.join(dir,file)
                if not cvsFiles.has_key(file) or not cvsFiles[file]:
                    # not in cvs, so add to removeables
                    removables.append(absFile)
                else:
                    # if in CVS, see if a directory and recurse
                    if os.path.isdir(absFile):
                        childremovables = cvsFindRemovables(absFile)
                        removables += childremovables
    else:
        print "Did not find CVS/Entries file in", dir

    return removables

def cvsClean(buildenv, dirs):
    allRemovables = []
    for dir in dirs:
        dir = os.path.abspath(dir)
        log(buildenv, HARDHAT_MESSAGE, "HardHat", "Examining " + dir + "...")
        removables = cvsFindRemovables(dir)
        allRemovables += removables
    allRemovables.sort()
    if len(allRemovables) == 0:
        log(buildenv, HARDHAT_MESSAGE, "HardHat", "No local files to remove")
        return

    if buildenv['interactive']:
        print
        print "The following files and directories are not in CVS:"
        print
        for removable in allRemovables:
            print removable
        print
        yn = raw_input("Would you like to remove these files?  y/n: ")
    else:
        yn = "y"

    if yn == "y" or yn == "Y":
        log(buildenv, HARDHAT_MESSAGE, "HardHat", "Removing files...")
        for removable in allRemovables:
            log(buildenv, HARDHAT_MESSAGE, "HardHat", removable)
            if os.path.isdir(removable):
                rmdir_recursive(removable)
            elif os.path.isfile(removable) or os.path.islink(removable):
                os.remove(removable)
            elif not os.path.exists(removable):
                log(buildenv, HARDHAT_WARNING, "HardHat", "Tried to remove "+\
                 removable +" but it doesn't exist")

        log(buildenv, HARDHAT_MESSAGE, "HardHat", "Files removed")
    else:
        log(buildenv, HARDHAT_MESSAGE, "HardHat", "Not removing files")

# - - - - - - -
def compressDirectory(buildenv, directories, fileRoot):
    """This assumes that directory is an immediate child of the current dir"""
    if buildenv['os'] == 'win':
        executeCommand(buildenv, "HardHat",
         [buildenv['zip'], "-r", fileRoot + ".zip"] + directories,
        "Zipping up to " + fileRoot + ".zip")
        return fileRoot + ".zip"
    else:
        executeCommand(buildenv, "HardHat",
         [buildenv['tar'], "cf", fileRoot+".tar"] + directories,
        "Tarring to " + fileRoot + ".tar")
        executeCommand(buildenv, "HardHat", 
         [buildenv['gzip'], "-f", fileRoot+".tar"],
        "Running gzip on " + fileRoot + ".tar")
        return fileRoot + ".tar.gz"

def findInPath(path,fileName):
    dirs = path.split(os.pathsep)
    for dir in dirs:
        if os.path.isfile(os.path.join(dir, fileName)):
            return os.path.join(dir, fileName)
        if os.name == 'nt' or sys.platform == 'cygwin':
            if os.path.isfile(os.path.join(dir, fileName + ".exe")):
                return os.path.join(dir, fileName + ".exe")
    return None

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Exception Classes

class HardHatError(Exception):
    """ General HardHat exception; more specific errors subclass this. """
    pass

class HardHatBuildEnvError(Exception):
    """ Exception thrown when the buildenv has invalid or missing values. """
    
    def __init__(self,args=None):
        self.args = args

class HardHatInspectionError(HardHatError):
    """ Exception thrown when the system fails inspection. """
    pass

class HardHatMissingCompilerError(HardHatError):
    """ Exception thrown when a compiler cannot be located. """
    pass

class HardHatUnknownPlatformError(HardHatError):
    """ Exception thrown when run on an unsupported platform. """
    pass

class HardHatExternalCommandError(HardHatError):
    """ Exception thrown when an external command returns non-zero exit code """
    pass

class HardHatRegistryError(HardHatError):
    """ Exception thrown when we can't read the windows registry """
    pass

class HardHatUnitTestError(HardHatError):
    """ Exception thrown when at least one unit test fails """
    pass

class HardHatMissingFileError(HardHatError):
    """ Exception thrown when a __hardhat__.py file cannot be found. """

    def __init__(self,args=None):
        self.args = args

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -




