import codecs, json, re, os, sys, threading;
# Prevent unicode strings from throwing exceptions when output to the console.
sys.stdout = codecs.getwriter("cp437")(sys.stdout, "replace");
# The CWD may not be this script's folder; make sure it looks there for modules first:
sBaseFolderPath = os.path.dirname(__file__);
for sPath in [sBaseFolderPath] + [os.path.join(sBaseFolderPath, x) for x in ["modules"]]:
  sys.path.insert(0, sPath);

from dxConfig import dxConfig;
try:
  from cBugId import cBugId;
except:
  print "*" * 80;
  print "BugId.py depends on cBugId, which you can download at:";
  print "    https://github.com/SkyLined/cBugId/";
  print "After downloading, please copy the files to the \"modules\\cBugId\" folder.";
  print "*" * 80;
  raise;
try:
  import FileSystem;
except:
  print "*" * 80;
  print "BugId.py depends on FileSystem, which you can download at:";
  print "    https://github.com/SkyLined/FileSystem/";
  print "After downloading, please copy the files to the \"modules\\FileSystem\" folder.";
  print "*" * 80;
  raise;

# Rather than a command line, a known application keyword can be provided. The default command line for such applications can be provided below and will
# be used if the keyword is provided as the command line by the user:
sProgramFilesPath = os.getenv("ProgramFiles");
sProgramFilesPath_x86 = os.getenv("ProgramFiles(x86)") or os.getenv("ProgramFiles");
sProgramFilesPath_x64 = os.getenv("ProgramW6432");
gdApplication_asCommandLine_by_sKeyword = {
  "aoo-writer": [r"%s\OpenOffice 4\program\swriter.exe" % sProgramFilesPath_x86, "-norestore", "-view", "-nologo", "-nolockcheck"],
  "chrome": [r"%s\Google\Chrome\Application\chrome.exe" % sProgramFilesPath_x86, "--disable-default-apps", "--disable-extensions", "--disable-popup-blocking", "--disable-prompt-on-repost", "--force-renderer-accessibility", "--no-sandbox"],
  "firefox": [r"%s\Mozilla Firefox\firefox.exe" % sProgramFilesPath_x86, "--no-remote", "-profile", "%s\Firefox-profile" % os.getenv("TEMP")],
  "foxit": [r"%s\Foxit Software\Foxit Reader\FoxitReader.exe" % sProgramFilesPath_x86],
  "msie": [r"%s\Internet Explorer\iexplore.exe" % sProgramFilesPath],
  "msie64": [r"%s\Internet Explorer\iexplore.exe" % sProgramFilesPath_x64],
  "msie86": [r"%s\Internet Explorer\iexplore.exe" % sProgramFilesPath_x86],
  "nightly": [r"%s\Mozilla Firefox Nightly\build\dist\bin\firefox.exe" % os.getenv("LocalAppData"), "--no-remote", "-profile", r"%s\Firefox-nightly-profile" % os.getenv("TEMP")], # has no default path; this is what I use.
};
DEFAULT_BROWSER_TEST_URL = {}; # Placeholder for dxConfig["sDefaultBrowserTestURL"]
gdApplication_asDefaultAdditionalArguments_by_sKeyword = {
  "chrome": [DEFAULT_BROWSER_TEST_URL],
  "firefox": [DEFAULT_BROWSER_TEST_URL],
  "nightly": [DEFAULT_BROWSER_TEST_URL],
  "msie": [DEFAULT_BROWSER_TEST_URL],
  "msie64": [DEFAULT_BROWSER_TEST_URL],
  "msie86": [DEFAULT_BROWSER_TEST_URL],
  "foxit": ["repro.pdf"],
};
dxBrowserSettings = {
  # Settings used by all browsers (these should eventually be fine-tuned for each browser)
  "nExcessiveCPUUsageCheckInitialTimeout": 30.0, # Give browser some time to load repro
  "BugId.nExcessiveCPUUsageCheckInterval": 30.0, # Browser may be busy for a bit, but no longer than 30 seconds.
  "BugId.nExcessiveCPUUsagePercent": 95,      # Browser msust be very, very busy.
  "BugId.nExcessiveCPUUsageWormRunTime": 0.5, # Any well written function should return within half a second IMHO.
};

gdApplication_dxSettings_by_sKeyword = {
  "aoo-writer": {
    "nApplicationMaxRunTime": 10.0, # Writer can be a bit slow to load, so give it some time.
    "nExcessiveCPUUsageCheckInitialTimeout": 10.0, # Give application some time to load repro
    "BugId.nExcessiveCPUUsageCheckInterval": 5.0, # Application should not be busy for more than 5 seconds.
    "BugId.nExcessiveCPUUsagePercent": 75,      # Application must be relatively busy.
    "BugId.nExcessiveCPUUsageWormRunTime": 0.5, # Any well written function should return within half a second IMHO.
  },
  "chrome": dxBrowserSettings,
  "edge": dxBrowserSettings,
  "firefox": dxBrowserSettings,
  "foxit": {
    "nApplicationMaxRunTime": 3.0, # Normally loads within 2 seconds, but give it one more to be sure.
    "nExcessiveCPUUsageCheckInitialTimeout": 10.0, # Give application some time to load repro
    "BugId.nExcessiveCPUUsageCheckInterval": 5.0, # Application should not be busy for more than 5 seconds.
    "BugId.nExcessiveCPUUsagePercent": 75,      # Application must be relatively busy.
    "BugId.nExcessiveCPUUsageWormRunTime": 0.5, # Any well written function should return within half a second IMHO.
  },
  "nightly": dxBrowserSettings,
  "msie": dxBrowserSettings, 
  "msie86": dxBrowserSettings,
  "msie64": dxBrowserSettings,
};

# Known applications can have regular expressions that map source file paths in its output to URLs, so the details HTML for any detected bug can have clickable
# links to an online source repository:
srMozillaCentralSourceURLMappings = "".join([
  r"c:[\\/]builds[\\/]moz2_slave[\\/][^\\/]+[\\/]build[\\/](?:src[\\/])?", # absolute file path
  r"(?P<path>[^:]+\.\w+)", # relative file path
  r"(:| @ |, line )", # separator
  r"(?P<lineno>\d+)",  # line number
]);
gdApplication_sURLTemplate_by_srSourceFilePath_by_sKeyword = {
  "firefox": {srMozillaCentralSourceURLMappings: "https://mxr.mozilla.org/mozilla-central/source/%(path)s#%(lineno)s"},
  "nightly": {srMozillaCentralSourceURLMappings: "https://dxr.mozilla.org/mozilla-central/source/%(path)s#%(lineno)s"},
};
# Known applications can also have regular expressions that detect important lines in its stdout/stderr output. These will be shown prominently in the details
# HTML for any detected bug.
gdApplication_rImportantStdOutLines_by_sKeyword = {};
gdApplication_rImportantStdErrLines_by_sKeyword = {
  "nightly": re.compile("^((\?h)+: C)*(%s)$" % "|".join([
    r"Assertion failure: .*",
    r"Hit MOZ_CRASH: .*",
    r"\[Child \w+\] ###!!!ABORT: .*",
  ])),
};

asApplicationKeywords = sorted(list(set(
  gdApplication_asCommandLine_by_sKeyword.keys() +
  gdApplication_asDefaultAdditionalArguments_by_sKeyword.keys() +
  gdApplication_dxSettings_by_sKeyword.keys() +
  gdApplication_sURLTemplate_by_srSourceFilePath_by_sKeyword.keys() + 
  gdApplication_rImportantStdOutLines_by_sKeyword.keys() +
  gdApplication_rImportantStdErrLines_by_sKeyword.keys()
)));

def fApplyConfigSetting(sSettingName, xValue, sIndentation  = ""):
  asGroupNames = sSettingName.split("."); # last element is not a group name
  sFullName = ".".join(asGroupNames);
  sSettingName = asGroupNames.pop();          # so pop it.
  dxConfigGroup = dxConfig;
  asHandledGroupNames = [];
  for sGroupName in asGroupNames:
    asHandledGroupNames.append(sGroupName);
    assert sGroupName in dxConfigGroup, \
        "Unknown config group %s in setting name %s." % (repr(".".join(asHandledGroupNames)), repr(sFullName));
    dxConfigGroup = dxConfigGroup.get(sGroupName, {});
  assert sSettingName in dxConfigGroup, \
      "Unknown setting name %s%s." % (sSettingName, \
          len(asHandledGroupNames) > 0 and " in config group %s" % ".".join(asHandledGroupNames) or "");
  if json.dumps(dxConfigGroup[sSettingName]) == json.dumps(xValue):
    print "%s* The default value for config setting %s is %s." % (sIndentation, sFullName, repr(dxConfigGroup[sSettingName]));
  else:
    print "%s+ Changed config setting %s from %s to %s." % (sIndentation, sFullName, repr(dxConfigGroup[sSettingName]), repr(xValue));
    dxConfigGroup[sSettingName] = xValue;

if __name__ == "__main__":
  asArguments = sys.argv[1:];
  if len(asArguments) == 0:
    print "Usage:";
    print "  BugId.py [options] \"path\\to\\binary.exe\" [arguments]";
    print "    Start the binary in the debugger with the provided arguments.";
    print "";
    print "  BugId.py [options] @application [additional arguments]";
    print "    (Where \"application\" is a known application keyword, see below)";
    print "    Start the application identified by the keyword in the debugger";
    print "    using the application's default command-line and arguments followed";
    print "    by the additional arguments provided and apply application specific";
    print "    settings.";
    print "";
    print "  BugId.py [options] @application=\"path\\to\\binary.exe\" [arguments]";
    print "    Start the application identified by the keyword in the debugger";
    print "    using the provided binary and arguments and apply application specific";
    print "    settings. (i.e. the application's default command-line is ignored in";
    print "    favor of the provided binary and arguments).";
    print "";
    print "  BugId.py [options] --pids=[comma separated list of process ids]";
    print "    Attach debugger to the process(es) provided in the list. The processes must";
    print "    all have been suspended, as they will be resumed by the debugger.";
    print "";
    print "Options are of the form --[name]=[JSON value]. Note that you may need to do a";
    print "bit of quote juggling because Windows likes to eat quotes from the JSON value";
    print "for no obvious reason. So, if you want to specify --a=\"b\", you will need to";
    print "use \"--a=\\\"b\\\"\", or BugId will see --a=b (b is not valid JSON). *sigh*";
    print "  --bSaveReport=false";
    print "    Do not save a HTML formatted crash report.";
    print "  \"--sReportFolderPath=\\\"BugId\\\"\"";
    print "    Save report to the specified folder, in this case \"BugId\". The quotes";
    print "    mess is needed because of the Windows quirck explained above.";
    print "  --BugId.bSaveDump=true";
    print "    Save a dump file when a crash is detected.";
    print "  --BugId.bOutputStdIn=true, --BugId.bOutputStdOut=true,";
    print "      --BugId.bOutputStdErr=true";
    print "    Show verbose cdb input / output during debugging.";
    print "  --BugId.asSymbolServerURLs=[\"http://msdl.microsoft.com/download/symbols\"]";
    print "    Use http://msdl.microsoft.com/download/symbols as a symbol server.";
    print "  --BugId.asSymbolCachePaths=[\"C:\\Symbols\"]";
    print "    Use C:\\Symbols to cache symbol files.";
    print "  See dxConfig.py and srv\dxBugIdConfig.py for a list of settings that you can";
    print "  change. All values must be valid JSON of the appropriate type. No checks are";
    print "  made to ensure this. Providing illegal values may result in exceptions at any";
    print "  time during execution. You have been warned.";
    print "";
    print "Known application keywords:";
    for sApplicationKeyword in asApplicationKeywords:
      print "  @%s" % sApplicationKeyword;
    print "Run BugId.py @application? for an overview of the application specific command";
    print "line, arguments and settings.";
    os._exit(0);
  auApplicationProcessIds = [];
  sApplicationKeyword = None;
  asApplicationCommandLine = [];
  asAdditionalArguments = [];
  while asArguments:
    sArgument = asArguments[0];
    if sArgument.startswith("@"):
      asArguments.pop(0);
      if sApplicationKeyword is not None:
        print "- Cannot provide more than one application keyword";
        os._exit(1);
      if "=" in sArgument:
        sApplicationKeyword, sApplicationBinary = sArgument[1:].split("=", 1);
        asApplicationCommandLine = [sApplicationBinary];
      else:
        sApplicationKeyword = sArgument[1:];
      if sApplicationKeyword.endswith("?"):
        sApplicationKeyword = sApplicationKeyword[:-1];
        if sApplicationKeyword not in asApplicationKeywords:
          print "- Unknown application keyword";
          os._exit(1);
        print "Known application settings for @%s" % sApplicationKeyword;
        if sApplicationKeyword in gdApplication_asCommandLine_by_sKeyword:
          print "  Base command-line:";
          print "    %s" % " ".join(gdApplication_asCommandLine_by_sKeyword[sApplicationKeyword]);
        if sApplicationKeyword in gdApplication_asDefaultAdditionalArguments_by_sKeyword:
          print "  Default additional arguments:";
          print "    %s" % " ".join([
            sArgument is DEFAULT_BROWSER_TEST_URL and dxConfig["sDefaultBrowserTestURL"] or sArgument
            for sArgument in gdApplication_asDefaultAdditionalArguments_by_sKeyword[sApplicationKeyword]
          ]);
        if sApplicationKeyword in gdApplication_dxSettings_by_sKeyword:
          print "  Application specific settings:";
          for sSettingName, xValue in gdApplication_dxSettings_by_sKeyword[sApplicationKeyword].items():
            print "    %s = %s" % (sSettingName, json.dumps(xValue));
        os._exit(0);
      if sApplicationKeyword not in asApplicationKeywords:
        print "- Unknown application keyword";
        os._exit(1);
    elif sArgument.startswith("--"):
      asArguments.pop(0);
      sSettingName, sValue = sArgument[2:].split("=", 1);
      if sSettingName in ["pid", "pids"]:
        auApplicationProcessIds += [long(x) for x in sValue.split(",")];
      else:
        try:
          xValue = json.loads(sValue);
        except ValueError:
          print "- Cannot decode argument JSON value %s" % sValue;
          os._exit(1);
        fApplyConfigSetting(sSettingName, xValue); # Apply and show result
    else:
      asAdditionalArguments = asArguments;
      break;
  if sApplicationKeyword in gdApplication_dxSettings_by_sKeyword:
    print "* Applying application specific settings:";
    for (sSettingName, xValue) in gdApplication_dxSettings_by_sKeyword[sApplicationKeyword].items():
      fApplyConfigSetting(sSettingName, xValue, "  "); # Apply and show result indented.

  if sApplicationKeyword in gdApplication_asCommandLine_by_sKeyword and len(asApplicationCommandLine) == 0:
    # Translate known application keyword to its command line:
    asApplicationCommandLine = gdApplication_asCommandLine_by_sKeyword[sApplicationKeyword];
  if sApplicationKeyword in gdApplication_asDefaultAdditionalArguments_by_sKeyword and len(asAdditionalArguments) == 0:
    asAdditionalArguments = gdApplication_asDefaultAdditionalArguments_by_sKeyword[sApplicationKeyword];
  asApplicationCommandLine += asAdditionalArguments;
  if asApplicationCommandLine:
    if auApplicationProcessIds:
      print "You cannot specify both an application command-line and its process ids";
      os._exit(1);
    asApplicationCommandLine += [
      sArgument is DEFAULT_BROWSER_TEST_URL and dxConfig["sDefaultBrowserTestURL"] or sArgument
      for sArgument in asAdditionalArguments
    ];
  elif not auApplicationProcessIds:
    print "You must specify an application command-line or its process ids";
    os._exit(1);
  elif asAdditionalArguments:
    print "You cannot specify command-line arguments to an application that is already running";
    os._exit(1);
  dsURLTemplate_by_srSourceFilePath = {};
  if sApplicationKeyword in gdApplication_sURLTemplate_by_srSourceFilePath_by_sKeyword:
    dsURLTemplate_by_srSourceFilePath = gdApplication_sURLTemplate_by_srSourceFilePath_by_sKeyword.get(sApplicationKeyword, {});
  rImportantStdOutLines = None;
  if sApplicationKeyword in gdApplication_rImportantStdOutLines_by_sKeyword:
    rImportantStdOutLines = gdApplication_rImportantStdOutLines_by_sKeyword.get(sApplicationKeyword);
  rImportantStdErrLines = None;
  if sApplicationKeyword in gdApplication_rImportantStdErrLines_by_sKeyword:
    rImportantStdErrLines = gdApplication_rImportantStdErrLines_by_sKeyword.get(sApplicationKeyword);
  
  oBugId = None;
  
  bApplicationIsStarted = asApplicationCommandLine is None; # if we're attaching the application is already started.
  bCheckForExcessiveCPUUsageTimeoutSet = False;
  def fApplicationRunningHandler():
    global bApplicationIsStarted, bCheckForExcessiveCPUUsageTimeoutSet;
    if not bApplicationIsStarted:
      # Running for the first time after being started.
      bApplicationIsStarted = True;
      print "+ The application was started successfully and is running...";
      if dxConfig["nApplicationMaxRunTime"] is not None:
        oBugId.fxSetTimeout(dxConfig["nApplicationMaxRunTime"], fHandleApplicationRunTimeout);
    else:
      # Running after being resumed.
      print "  * T+%.1f The application was resumed successfully and is running..." % oBugId.fnApplicationRunTime();
    if not bCheckForExcessiveCPUUsageTimeoutSet:
      # Start checking for excessive CPU usage
      bCheckForExcessiveCPUUsageTimeoutSet = True;
      oBugId.fSetCheckForExcessiveCPUUsageTimeout(dxConfig["nExcessiveCPUUsageCheckInitialTimeout"]);
  
  def fExceptionDetectedHandler(uCode, sDescription):
    if uCode:
      print "  * T+%.1f Exception code 0x%X (%s) was detected and is being analyzed..." % (oBugId.fnApplicationRunTime(), uCode, sDescription);
    else:
      print "  * T+%.1f A potential bug (%s) was detected and is being analyzed..." % (oBugId.fnApplicationRunTime(), sDescription);
  
  def fHandleApplicationRunTimeout():
    print "  * T+%.1f Terminating the application because it has been running for %.1f seconds without crashing." % \
        (oBugId.fnApplicationRunTime(), dxConfig["nApplicationMaxRunTime"]);
    oBugId.fStop();
  
  def fApplicationExitHandler():
    print "  * T+%.1f The application has exited..." % oBugId.fnApplicationRunTime();
    oBugId.fStop();
  
  oInternalException = None;
  def fInternalExceptionCallback(oException):
    global oInternalException;
    oInternalException = oException;
    raise;
  
  if asApplicationCommandLine:
    print "+ The debugger is starting the application...";
    print "  Command line: %s" % " ".join(asApplicationCommandLine);
  else:
    print "+ The debugger is attaching to the application...";
  oBugId = cBugId(
    asApplicationCommandLine = asApplicationCommandLine or None,
    auApplicationProcessIds = auApplicationProcessIds or None,
    asSymbolServerURLs = dxConfig["asSymbolServerURLs"],
    dsURLTemplate_by_srSourceFilePath = dsURLTemplate_by_srSourceFilePath,
    rImportantStdOutLines = rImportantStdOutLines,
    rImportantStdErrLines = rImportantStdErrLines,
    bGetDetailsHTML = dxConfig["bSaveReport"],
    fApplicationRunningCallback = fApplicationRunningHandler,
    fExceptionDetectedCallback = fExceptionDetectedHandler,
    fApplicationExitCallback = fApplicationExitHandler,
    fInternalExceptionCallback = fInternalExceptionCallback,
  );
  oBugId.fWait();
  if not bApplicationIsStarted:
    print "- BugId was unable to debug the application.";
  elif oInternalException is not None:
    print "+ BugId run into an internal error:";
    print "  %s" % repr(oInternalException);
    print;
    print "  Please report this issue at the below web-page so it can be addressed:";
    print "  https://github.com/SkyLined/BugId/issues/new";
  elif oBugId.oBugReport is not None:
    print "+ A bug was detected in the application.";
    print;
    print "  Id:               %s" % oBugId.oBugReport.sId;
    print "  Description:      %s" % oBugId.oBugReport.sBugDescription;
    print "  Location:         %s" % oBugId.oBugReport.sBugLocation;
    if oBugId.oBugReport.sBugSourceLocation:
      print "  Source:           %s" % oBugId.oBugReport.sBugSourceLocation;
    print "  Security impact:  %s" % oBugId.oBugReport.sSecurityImpact;
    print "  Run time:         %s seconds" % (long(oBugId.fnApplicationRunTime() * 1000) / 1000.0);
    if dxConfig["bSaveReport"]:
      # We'd like a report file name base on the BugId, but the later may contain characters that are not valid in a file name
      sDesiredReportFileName = "%s @ %s.html" % (oBugId.oBugReport.sId, oBugId.oBugReport.sBugLocation);
      # Thus, we need to translate these characters to create a valid filename that looks very similar to the BugId
      sValidReportFileName = FileSystem.fsValidName(sDesiredReportFileName, bUnicode = dxConfig["bUseUnicodeReportFileNames"]);
      if dxConfig["sReportFolderPath"] is not None:
        sReportFilePath = FileSystem.fsPath(dxConfig["sReportFolderPath"], sValidReportFileName);
      else:
        sReportFilePath = FileSystem.fsPath(sValidReportFileName);
      eWriteDataToFileResult = FileSystem.feWriteDataToFile(
        oBugId.oBugReport.sDetailsHTML,
        sReportFilePath,
        fbRetryOnFailure = lambda: False,
      );
      if eWriteDataToFileResult:
        print "  Bug report:       Cannot be saved (%s)" % repr(eWriteDataToFileResult);
      else:
        print "  Bug report:       %s (%d bytes)" % (sValidReportFileName, len(oBugId.oBugReport.sDetailsHTML));
  else:
    print "- The application has terminated without crashing.";
    print "  Run time:         %s seconds" % (long(oBugId.fnApplicationRunTime() * 1000) / 1000.0);
  
  if dxConfig["bShowLicenseAndDonationInfo"]:
    print;
    print "This version of BugId is provided free of charge for non-commercial use only.";
    print "If you find it useful and would like to make a donation, you can send bitcoin";
    print "to 183yyxa9s1s1f7JBpPHPmzQ346y91Rx5DX. Please contact the author if you wish to";
    print "use BugId commercially. Contact and licensing information can be found at";
    print "https://github.com/SkyLined/BugId#license.";
