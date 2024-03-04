import unittest
import subprocess
import os
import io
import shlex
import inspect
import sys
import time


def _indent (s, spaces = 2, add_newline = False):
  p = " " * spaces
  o = []
  for x in s.split("\n"):
    x = x.strip()
    if x: x = p + x
    o.append(x)
  o = "\n".join(o)
  if add_newline and o and not o.endswith("\n"): o = o + "\n"
  return o


_fail_cache = {}

def testFailed (test):
  cached = _fail_cache.get(test, None)
  #if cached is not None: print(test, "cached", cached)
  if cached is not None: return cached
  #print(test, "not cached")

  out = io.StringIO()
  tr = unittest.TextTestRunner(stream=out, failfast=True)
  ts = unittest.defaultTestLoader.loadTestsFromTestCase(test)
  result = tr.run(ts)
  #dir(result)
  def cacheit (v):
    _fail_cache[test] = v
    return v
  if result.errors: return cacheit(True)
  if result.failures: return cacheit(True)
  if result.skipped: return cacheit(True)
  return cacheit(False)

def skipIfFailed (*tests):
  def f (cls):
    for test in tests:
      si = unittest.skipIf(testFailed(test), "Skipped because %s was required to pass" % (test.__name__,))
    return si(cls)
  return f


def _run (cmd, *args):
  # Don't use this!
  want_stderr = False
  if cmd is True:
    want_stderr = True
    cmd = args[0]
    args = args[1:]
  rc,out,err = run_ex(cmd, None, *args)
  if want_stderr:
    return rc,out,err
  return rc,out


_default_timeout = None
def set_default_timeout (t):
  global _default_timeout
  _default_timeout = t;


def run_ex (cmd, inp, *args, timeout=None):
  if timeout is None: timeout = _default_timeout
  if args:
    cmd = [cmd] + [str(s) for s in args]
  else:
    cmd = cmd.split()

  if inp is None:
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       stdin=subprocess.DEVNULL, timeout=timeout)
  else:
    if isinstance(inp, str):
      inp = inp.encode("utf8")
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       input=inp, timeout=timeout)

  return r.returncode,r.stdout.decode("utf8").strip(),r.stderr.decode("utf8").strip()


def lines (s):
  if not s: return []
  return s.split("\n")


def setscore (f, score):
  f.SCORE = score


class Valgrind (object):
  class Case (unittest.TestCase):
    #NOTE: To disable one of the tests, set it to None in the subclass, e.g.:
    # class Foo (Valgrind.Case):
    #   test_no_possibly_lost = None
    prog = None
    args = ()
    stdin = None
    stdin_newline = True
    timeout = 5

    def setUp (self):
      a = self.args
      if isinstance(self.args, str): self.args = shlex.split(self.args)
      a = [str(x) for x in self.args]
      arg = [self.prog] + a
      if not os.path.isfile(arg[0]): self.skipTest("Program doesn't exist")

      arg = ["--leak-check=full"] + arg
      stdin = self.stdin
      if isinstance(stdin, str) and self.stdin_newline:
        if not stdin.endswith("\n"): stdin += "\n"
      self.rc,self.r,self.v = run_ex("valgrind", stdin, *arg,
                                     timeout=self.timeout)
      if self.rc < 0: self.skipTest("Program crashed")
      if self.rc == 127: self.skipTest("Valgrind error?")
      #self.assertEqual(self.rc, 0, "Expected 0 return value")
      l = [x[2:] for x in lines(self.v) if x.startswith("==")]
      l = [x.split("==",1)[-1] for x in l]
      self.v = l

    def test_no_definitely_lost (self):
      l = [x for x in self.v if x.strip().startswith("definitely lost: ")]
      if len(l) == 0: return
      assert len(l) == 1
      l = l[0]
      l = int(l.split(":",1)[1].strip().split()[0].replace(",",""))
      self.assertEqual(l, 0, "Some memory definitely lost")

    def test_no_indirectly_lost (self):
      l = [x for x in self.v if x.strip().startswith("indirectly lost: ")]
      if len(l) == 0: return
      assert len(l) == 1
      l = l[0]
      l = int(l.split(":",1)[1].strip().split()[0].replace(",",""))
      self.assertEqual(l, 0, "Some memory indirectly lost")

    def test_no_possibly_lost (self):
      l = [x for x in self.v if x.strip().startswith("possibly lost: ")]
      if len(l) == 0: return
      assert len(l) == 1
      l = l[0]
      l = int(l.split(":",1)[1].strip().split()[0].replace(",",""))
      self.assertEqual(l, 0, "Some memory possibly lost")

    def test_reachable_lost (self):
      l = [x for x in self.v if x.strip().startswith("still reachable: ")]
      if len(l) == 0: return
      assert len(l) == 1
      l = l[0]
      l = int(l.split(":",1)[1].strip().split()[0].replace(",",""))
      self.assertEqual(l, 0, "Some memory is still reachable (and may be lost)")

    def test_jump_or_move_on_uninitialized_data (self):
      l = [x for x in self.v if x.strip().startswith("Conditional jump or move depends on uninitialised ")]
      self.assertEqual(len(l), 0, "Conditional jump/move depends on uninitialized data")

    def test_use_of_uninitialized_data (self):
      l = [x for x in self.v if x.strip().startswith("Use of uninitialised value ")]
      self.assertEqual(len(l), 0, "Use of uninitialized data")

    def test_invalid_memory_access (self):
      l1 = [x for x in self.v if x.strip().startswith("Invalid read of ")]
      l2 = [x for x in self.v if x.strip().startswith("Invalid write of ")]
      self.assertEqual(len(l1)+len(l2), 0, "Invalid memory access")


class SimpleTest (object):
  class Case (unittest.TestCase):
    prog = None
    args = ()
    stdin = None
    stdin_newline = True # Ensure stdin ends with newline
    expect = False # Fail
    expect_fail = False
    expect_err = ""
    timeout = 5
    maxDiff = 2048

    def _extraSetUp (self):
      pass

    def setUp (self):
      a = self.args
      if isinstance(self.args, str): self.args = shlex.split(self.args)
      a = [str(x) for x in self.args]
      if not os.path.isfile(self.prog): self.skipTest("Program doesn't exist")
      self._extraSetUp()
      stdin = self.stdin
      if isinstance(stdin, str) and self.stdin_newline:
        if not stdin.endswith("\n"): stdin += "\n"
      self.rc,self.r,self.e = run_ex(self.prog, stdin, *a, timeout=self.timeout)

    def test (self):
      sout = _indent(self.r).rstrip()
      serr = _indent(self.e).rstrip()
      msg = [""]
      if sout:
        msg.append("** Standard output **")
        msg.append(sout)
      if serr:
        msg.append("** Standard error **")
        msg.append(serr)
      msg = "\n".join(msg)
      if self.rc < 0: self.fail("Program crashed!")
      if self.expect_fail:
        self.assertNotEqual(self.rc, 0, "Expected nonzero return value" + msg)
        self._check_output()
      else:
        self.assertEqual(self.rc, 0, "Expected zero return value" + msg)
        self._check_output()

    def _check_output (self):
      if self.expect is not False:
        self.assertEqual(self.r, self.expect)
      if self.expect_err is not False:
        self.assertEqual(self.e, self.expect_err)



class AllTestResult (unittest.TestResult):
  """
  Subclass of TestResult which keeps track of all tests

  The default TestResult doesn't keep track of all tests in a useful way, and
  doesn't keep track of successful tests at all.  This does.
  Also keeps track of start and stop time.
  """
  _marked_start_time = None
  _marked_stop_time = None

  @property
  def _start_time (self):
    return self._marked_start_time

  @property
  def _stop_time (self):
    if self._marked_stop_time is None:
      self._marked_stop_time = time.time()
    return self._marked_stop_time

  def __init__ (self, *args, **kw):
    super().__init__(*args, **kw)
    self._all_tests = []
    self._successful_tests = set()

  def startTest (self, test):
    self._marked_start_time = time.time()
    self._all_tests.append(test)
    return super().startTest(test)

  def stopTest (self, test):
    self._marked_stop_time = time.time()
    return super().stopTest(test)

  def addSuccess (self, test):
    self._successful_tests.add(test)
    return super().addSuccess(test)



def tabulate (results, skip_after_fail=False):
  """
  Tabulates scores in a way compatible with GradeScope

  Tests may have a "score" attribute if you want them scored.
  If skip_after_fail, any tests after a failed one will not be scored.
  Expects the results to be kept with AllTestResult.

  Example usage:
    runner = unittest.TextTestRunner()
    runner.failfast = False
    runner.resultclass = AllTestResult
    r = unittest.main(exit=False, testRunner=runner)
    j = tabulate(r.result, skip_after_fail=True)
    s = json.dumps(j, indent=2)
    open("result.json", "w").write(s + "\n")
  """
  def getdesc (test, count=0):
    n = type(test).__name__
    l = n
    desc = test.__doc__
    if desc:
      desc = desc.strip().split("\n",1)[0]
      l += " (" + desc + ")"
    assert n
    if count > 1:
      l += " - " + test._testMethodName
    return n, l

  err_tests = dict(results.errors)
  fail_tests = dict(results.failures)
  skip_tests = dict(results.skipped)

  def handle_successful (d, t, r, score):
    if t not in results._successful_tests: return
    if 'score' in r: r['score'] = score
    r['status'] = 'passed'
    return True

  def handle_error (d, t, r):
    info = err_tests.get(t, False)
    if info is False: return
    r["output"] = info
    return True

  def handle_failure (d, t, r):
    info = fail_tests.get(t, False)
    if info is False: return
    r["output"] = info
    return True

  def handle_skipped (d, t, r):
    info = skip_tests.get(t, False)
    if info is False: return
    r["output"] = info
    return True

  def handle_unexpected (d, t, r):
    r['output'] = "Unexpected test result!  Contact your instructor!"
    pass

  # First, figure out which classes have multiple tests
  cls_tests = {}
  for t in results._all_tests:
    getdesc(t) # Fix names
    if type(t) not in cls_tests: cls_tests[type(t)] = 0
    cls_tests[type(t)] += 1
  cls_success =  {}

  failed_test = None
  output = []
  prev_module = None
  for t in results._all_tests:
    count = cls_tests[type(t)]
    count = cls_tests[type(t)]
    n,d = getdesc(t, count=count)
    r = dict(name=d, visibility="visible", status="failed")
    score = 0
    if getattr(t, "score", None) is not None:
      r['score'] = 0
      score = t.score / count
    method = getattr(type(t), t._testMethodName)
    if hasattr(method, "SCORE"): score = method.SCORE
    output.append((type(t),r))

    if failed_test and skip_after_fail:
      if failed_test == n:
        r['output'] = (f"Invalid since another test in the '{failed_test}'"
                       +" group failed.")
      else:
        r['output'] = f"Invalid since '{failed_test}' failed."
      continue

    if handle_successful(d, t, r, score):
      if type(t) not in cls_success: cls_success[type(t)] = 0
      cls_success[type(t)] += 1
      continue

    failed_test = n

    if handle_error(d, t, r): continue
    if handle_failure(d, t, r): continue
    if handle_skipped(d, t, r): continue
    handle_unexpected(d, t, r)

  real_out = []
  for t,data in output:
    if cls_success.get(t,0) != cls_tests[t]:
      if 'score' in data:
        data['score'] = 0
        if data['status'] == 'passed':
          #data['status'] = 'failed'
          #data['output'] = "No points awarded because a test in this group failed."
          msg = ("Passed, but no points were awarded because a prior test failed "
                 + f"(see the results for '{failed_test}').")
          data['output'] = msg
    real_out.append(data)

  return real_out



def gradescope_score (skip_after_fail=False, failfast=False, filename=None,
                      postprocess=None, extra=None, module='__main__'):
  if filename is None:
    filename = "/autograder/results/results.json"
  elif filename == "-" or filename is False:
    filename = None
  runner = unittest.TextTestRunner()
  runner.failfast = failfast
  runner.resultclass = AllTestResult
  start_time = time.time()
  r = unittest.main(module, exit=False, testRunner=runner)
  j = tabulate(r.result, skip_after_fail=skip_after_fail)

  #elapsed_time = r.result._stop_time - r.result._start_time
  elapsed_time = time.time() - start_time

  j = dict(
           tests = j,
           #visibility = "visible",
           #stdout_visibility = "visible",
           execution_time = elapsed_time
          )
  if extra: j.update(extra)
  if postprocess: j = postprocess(j)

  import json
  s = json.dumps(j, indent=2)
  if not filename:
    print(s)
  else:
    with open(filename, "w") as f:
      f.write(s)
      f.write("\n")


_test_modules = []

def main (gs_postprocess=None):
  gs = False
  saf = False
  ff = False
  modules = []
  args = []
  extra = {}
  extra_args = "output visibility stdout_visibility".split()
  for arg in sys.argv[1:]:
    if arg.startswith("--gradescope="):
      gs = arg.split("=", 1)[1]
    elif arg == "--gradescope":
      gs = None
    elif arg.replace("_","-") == "--skip-after-fail":
      saf = True
    elif arg == "--failfast":
      ff = True
    elif arg.startswith("--modules="):
      modules = arg.split("=",1)[1].split(",")
    else:
      for a in extra_args:
        if arg.startswith(f"--{a}="):
          extra[a] = arg.split("=", 1)[1]
          break
      else:
        args.append(arg)

  del sys.argv[1:]
  sys.argv.extend(args)

  module = '__main__'
  # Wow, this is truly, truly terrible.
  if modules:
    _test_modules.extend(modules)
    import importlib
    spec = importlib.machinery.ModuleSpec("tests",None)
    tmod = importlib.util.module_from_spec(spec)
    module = tmod
    #tmod = sys.modules['__main__']
    setattr(tmod, "load_tests", load_tests)
    for mn in modules:
      m = __import__(mn)
      for ed in dir(m):
        e = getattr(m, ed)
        if not isinstance(e, type): continue
        if issubclass(e, unittest.TestCase):
          assert not hasattr(tmod, ed)
          setattr(tmod, ed, getattr(m, ed))

  if gs is not False:
    gradescope_score(filename=gs, skip_after_fail=saf, failfast=ff,
                     postprocess=gs_postprocess, extra=extra, module=module)
  else:
    unittest.main(module)



def load_tests (loader, standard_tests, pattern):
  """
  Runs discovered test classes in order

  This has lots of limitations, but it works right for the expected cases,
  where each test is implemented in its own class and we use standard
  test discovery, test suite types, etc.

  Python's discovered tests are passed in standard_tests, which is a
  TestSuite.  In our case, each entry in that is one of our test
  classes, which we assume are all in the same file.  However, they
  are not in the same order they're defined in the file.  So for each one,
  we get the first line number of the class and use that to return
  a new TestSuite sorted in line-number order.
  """
  if not isinstance(standard_tests, unittest.TestSuite): return standard_tests
  subsuites = []
  for suite in standard_tests:
    for test in suite:
      cls = type(test)
      method = getattr(cls, test._testMethodName)
      mod = inspect.getmodule(cls)
      if mod is None:
        mod = cls.__name__
      elif not isinstance(mod, str):
        mod = mod.__name__
      if mod in _test_modules:
        mod = f'_{_test_modules.index(mod)}'
      first_line_m = inspect.getsourcelines(method)[1]
      first_line_cls = inspect.getsourcelines(cls)[1]
      subsuites.append((mod,first_line_cls,first_line_m,test))
  subsuites.sort()
  subsuites = [x[-1] for x in subsuites]
  return unittest.TestSuite(subsuites)



if __name__ == "__main__":
  main()
