#!/usr/bin/env python3

import unittest
import subprocess
import os
import tempfile
from unittest import skipIf

from test_common import Valgrind, SimpleTest, skipIfFailed, load_tests

_WEIGHT = 0.5

def clean (s):
  """
  Strips leading spaces from each line
  """
  if isinstance(s, list): s = "\n".join(s)
  s = s.strip().split("\n")
  s = [x.strip() for x in s]
  s = "\n".join(s)
  if s and not s.endswith("\n"): s += "\n"
  return s


class HeapTest:
  # We put the superclass inside another class just so that the test discovery
  # system won't find it and try to run the superclass as a test!
  #@skipIfFailed()
  class Case (SimpleTest.Case):
    args = """
    """
    expected = """
    """

    expect_fail = False
    prog = "./tester"

    def _check_output (self):
      self.assertEqual(clean(self.expected), clean(self.e))



class OneAllocation (HeapTest.Case):
  args = """
  rel 1 -- alignbrk -- malloc 1 8 -- showbrk -- checksentinel -- showheap
  """

  expected = """
  brk: 0x00000018
  -- heap --
  0x00000000 0x00000010 USED
  0x00000010 0x00000000 XXXX
  """


class ZeroLengthAlloc (HeapTest.Case):
  """
  Checks program break before and after a single zero-length allocation.

  Should be exactly two headers' worth apart.
  """
  args = """
  rel 0 -- alignbrk -- showbrk -- malloc 1 0 -- showbrk
  """.strip().split()

  def _check_output (self):
    r = self.e.strip().split("\n")
    self.assertEqual(len(r), 2)
    n = []
    for i,l in enumerate(r):
      l = l.split()
      self.assertEqual(len(l), 2, "\n"+self.e)
      self.assertEqual(l[0], "brk:", "\n"+self.e)
      n.append(int(l[1], 0))
    self.assertEqual(n[1]-n[0], 16, "\n"+self.e)


class InitialAlign (HeapTest.Case):
  """
  Checks that an initially unaligned program break gets aligned
  """
  args = """
  rel 0 -- alignbrk -- sbrk 1 -- showbrk -- malloc 1 0 -- showbrk
  """.strip().split()

  def _check_output (self):
    r = self.e.strip().split("\n")
    self.assertEqual(len(r), 2)
    n = []
    for i,l in enumerate(r):
      l = l.split()
      self.assertEqual(len(l), 2, "\n"+self.e)
      self.assertEqual(l[0], "brk:", "\n"+self.e)
      n.append(int(l[1], 0))
    # Should now be 23 apart because we would have gotten 7 bytes of padding
    self.assertEqual(n[1]-n[0], 23, "\n"+self.e)


class TwoAllocations (HeapTest.Case):
  args = """
  rel 1 -- alignbrk -- malloc 1 8 -- malloc 1 8 -- showheap
  """

  expected = """
  -- heap --
  0x00000000 0x00000010 USED
  0x00000010 0x00000010 USED
  0x00000020 0x00000000 XXXX
  """


class OddSizeAllocation (HeapTest.Case):
  args = """
  rel 1 -- alignbrk -- malloc 1 8 -- malloc 1 15 -- showheap
  """

  expected = """
  -- heap --
  0x00000000 0x00000010 USED
  0x00000010 0x00000018 USED
  0x00000028 0x00000000 XXXX
  """


class AlignsBlocks (HeapTest.Case):
  score = 1 * _WEIGHT

  args = """
  rel 1 -- alignbrk -- malloc 1 10 -- malloc 1 15 -- showheap
  """

  expected = """
  -- heap --
  0x00000000 0x00000018 USED
  0x00000018 0x00000018 USED
  0x00000030 0x00000000 XXXX
  """


class FreeNull (HeapTest.Case):
  args = """
  free 0
  """

  expected = """
  """


class FreeNull2 (HeapTest.Case):
  args = """
  rel 1
  alignbrk
  malloc 1 1
  free 0
  showbrk
  checksentinel
  """

  expected = """
  brk: 0x00000018
  """


class FreeFirst (HeapTest.Case):
  args = """
  rel 1
  alignbrk
  malloc 1 8
  malloc 2 8
  showheap
  free 1
  showheap
  checksentinel
  """

  expected = """
  -- heap --
  0x00000000 0x00000010 USED
  0x00000010 0x00000010 USED
  0x00000020 0x00000000 XXXX
  -- heap --
  0x00000000 0x00000010 FREE
  0x00000010 0x00000010 USED
  0x00000020 0x00000000 XXXX
  """


class FreeEmpty (HeapTest.Case):
  score = 1 * _WEIGHT

  args = """
  rel 1
  alignbrk
  malloc 1 0
  malloc 2 8
  showheap
  free 1
  showheap
  checksentinel
  """

  expected = """
  -- heap --
  0x00000000 0x00000008 USED
  0x00000008 0x00000010 USED
  0x00000018 0x00000000 XXXX
  -- heap --
  0x00000000 0x00000008 FREE
  0x00000008 0x00000010 USED
  0x00000018 0x00000000 XXXX
  """


class MergeAfter (HeapTest.Case):
  """
  When a block is freed, a following free block should be merged

  Allocate four blocks, free the third and then the second
  """
  args = """
  rel 1
  alignbrk
  malloc 1 8
  malloc 2 0x18
  malloc 3 0x38
  malloc 4 0x78
  free 3
  showheap
  free 2
  showheap
  checksentinel
  """

  expected = """
  -- heap --
  0x00000000 0x00000010 USED
  0x00000010 0x00000020 USED
  0x00000030 0x00000040 FREE
  0x00000070 0x00000080 USED
  0x000000f0 0x00000000 XXXX
  -- heap --
  0x00000000 0x00000010 USED
  0x00000010 0x00000060 FREE
  0x00000070 0x00000080 USED
  0x000000f0 0x00000000 XXXX
  """


class MergeBefore (HeapTest.Case):
  """
  When a block is freed, a previous free block should be merged

  Allocate four blocks, free the second and then the third
  """
  args = """
  rel 1
  alignbrk
  malloc 1 8
  malloc 2 0x18
  malloc 3 0x38
  malloc 4 0x78
  free 2
  showheap
  free 3
  showheap
  checksentinel
  """

  expected = """
  -- heap --
  0x00000000 0x00000010 USED
  0x00000010 0x00000020 FREE
  0x00000030 0x00000040 USED
  0x00000070 0x00000080 USED
  0x000000f0 0x00000000 XXXX
  -- heap --
  0x00000000 0x00000010 USED
  0x00000010 0x00000060 FREE
  0x00000070 0x00000080 USED
  0x000000f0 0x00000000 XXXX
  """


class MergeBeforeAndAfter (HeapTest.Case):
  """
  When a block is freed, previous and next free blocks should be merged

  Allocate four blocks, frees first, then third, then second
  """
  score = 1 * _WEIGHT

  args = """
  rel 1
  alignbrk
  malloc 1 8
  malloc 2 0x18
  malloc 3 0x38
  malloc 4 0x78
  free 1
  free 3
  showheap
  free 2
  showheap
  checksentinel
  """

  expected = """
  -- heap --
  0x00000000 0x00000010 FREE
  0x00000010 0x00000020 USED
  0x00000030 0x00000040 FREE
  0x00000070 0x00000080 USED
  0x000000f0 0x00000000 XXXX
  -- heap --
  0x00000000 0x00000070 FREE
  0x00000070 0x00000080 USED
  0x000000f0 0x00000000 XXXX
  """


class FirstFit (HeapTest.Case):
  """
  Tests reusing a freed block
  """
  args = """
  rel 1
  alignbrk
  malloc 1 32
  malloc 2 32
  malloc 3 32
  malloc 4 32
  free 1
  free 3
  showheap
  malloc 9 32
  showheap
  checksentinel
  """

  expected = """
  -- heap --
  0x00000000 0x00000028 FREE
  0x00000028 0x00000028 USED
  0x00000050 0x00000028 FREE
  0x00000078 0x00000028 USED
  0x000000a0 0x00000000 XXXX
  -- heap --
  0x00000000 0x00000028 USED
  0x00000028 0x00000028 USED
  0x00000050 0x00000028 FREE
  0x00000078 0x00000028 USED
  0x000000a0 0x00000000 XXXX
  """


class FirstFit2 (HeapTest.Case):
  """
  Tests reusing a freed block
  """
  args = """
  rel 1
  alignbrk
  malloc 1 0x10
  malloc 2 0x20
  malloc 3 0x40
  malloc 4 0x80
  free 1
  free 3
  malloc 9 0x40
  showheap
  checksentinel
  """

  expected = """
  -- heap --
  0x00000000 0x00000018 FREE
  0x00000018 0x00000028 USED
  0x00000040 0x00000048 USED
  0x00000088 0x00000088 USED
  0x00000110 0x00000000 XXXX
  """


class NoFit (HeapTest.Case):
  """
  Tests failing to reuse a freed block
  """
  args = """
  rel 1
  alignbrk
  malloc 1 0x10
  malloc 2 0x20
  malloc 3 0x40
  malloc 4 0x80
  free 1
  free 3
  malloc 9 0x90
  showheap
  checksentinel
  """

  expected = """
  -- heap --
  0x00000000 0x00000018 FREE
  0x00000018 0x00000028 USED
  0x00000040 0x00000048 FREE
  0x00000088 0x00000088 USED
  0x00000110 0x00000098 USED
  0x000001a8 0x00000000 XXXX
  """


class SegFault (HeapTest.Case):
  """
  Cause a segfault
  """
  score = 1 * _WEIGHT

  args = """
  rel 1
  alignbrk
  malloc 1 20
  showheap poke 1 4200
  """

  def test (self):
    self.assertLess(self.rc, 0)


class Split (HeapTest.Case):
  """
  A large free block is split when it's reused for a small allocation
  """
  args = """
  rel 1
  alignbrk
  malloc 1 0x48
  malloc 2 0x08
  free 1
  showheap
  malloc 9 0x08
  showheap
  checksentinel
  """

  expected = """
  -- heap --
  0x00000000 0x00000050 FREE
  0x00000050 0x00000010 USED
  0x00000060 0x00000000 XXXX
  -- heap --
  0x00000000 0x00000010 USED
  0x00000010 0x00000040 FREE
  0x00000050 0x00000010 USED
  0x00000060 0x00000000 XXXX
  """


class BarelyDoNotSplit (HeapTest.Case):
  """
  Don't split a block that's not quite large enough
  """
  args = """
  rel 1
  alignbrk
  malloc 1 0x20
  malloc 2 0x08
  free 1
  showheap
  malloc 9 8
  showheap
  checksentinel
  """

  expected = """
  -- heap --
  0x00000000 0x00000028 FREE
  0x00000028 0x00000010 USED
  0x00000038 0x00000000 XXXX
  -- heap --
  0x00000000 0x00000028 USED
  0x00000028 0x00000010 USED
  0x00000038 0x00000000 XXXX
  """


class BarelyDoSplit (HeapTest.Case):
  """
  Split a block that's just barely large enough to split
  """
  args = """
  rel 1
  alignbrk
  malloc 1 0x21
  malloc 2 0x08
  free 1
  showheap
  malloc 9 8
  showheap
  checksentinel
  """

  expected = """
  -- heap --
  0x00000000 0x00000030 FREE
  0x00000030 0x00000010 USED
  0x00000040 0x00000000 XXXX
  -- heap --
  0x00000000 0x00000010 USED
  0x00000010 0x00000020 FREE
  0x00000030 0x00000010 USED
  0x00000040 0x00000000 XXXX
  """


class SplitMultiple (HeapTest.Case):
  """
  A large free block is split when it's reused for small allocations
  """
  score = 1 * _WEIGHT

  args = """
  rel 1
  alignbrk
  malloc 1 0xf0
  malloc 2 0x08
  free 1
  malloc 10 8
  malloc 11 24
  malloc 12 40
  malloc 13 88
  showheap
  checksentinel
  """

  expected = """
  -- heap --
  0x00000000 0x00000010 USED
  0x00000010 0x00000020 USED
  0x00000030 0x00000030 USED
  0x00000060 0x00000060 USED
  0x000000c0 0x00000038 FREE
  0x000000f8 0x00000010 USED
  0x00000108 0x00000000 XXXX
  """


class ReleaseOne (HeapTest.Case):
  """
  Checks that memory is given back to the OS when possible.

  When the last block is freed, we can call sbrk() with a negative value to
  give memory back.
  """
  args = """
  rel 0
  alignbrk
  showbrk
  malloc 1 0xf0
  free 1
  showbrk
  """

  def _check_output (self):
    r = self.e.strip().split("\n")
    self.assertEqual(len(r), 2)
    n = []
    for i,l in enumerate(r):
      l = l.split()
      self.assertEqual(len(l), 2, "\n"+self.e)
      self.assertEqual(l[0], "brk:", "\n"+self.e)
      n.append(int(l[1], 0))
    # n[0] is initial break
    # n[1] is final break
    # n[1] should be 8 larger (because of the sentinel)
    self.assertEqual(n[1]-n[0], 8, "\n"+self.e)


class ReleaseMerged (HeapTest.Case):
  """
  Checks that memory is given back to the OS when possible.

  When the last block is freed, both it and the previous block should be
  released back to the OS.
  """
  score = 0.5 * _WEIGHT

  args = """
  rel 1
  alignbrk
  malloc 1 8
  showbrk
  malloc 2 24
  malloc 3 40
  showbrk
  free 2
  showbrk
  free 3
  showbrk
  """

  expected = """
  brk: 0x00000018
  brk: 0x00000068
  brk: 0x00000068
  brk: 0x00000018
  """


class AllocFreeAssortment (HeapTest.Case):
  """
  Just do a bunch of stuff

  It should end up freeing everthing, so you should end up with an empty heap
  """
  score = 0.5 * _WEIGHT

  args = """
  rel 1
  alignbrk
  malloc 24 165
  malloc 18 141
  malloc 23 9
  malloc 25 26
  malloc 11 204
  malloc 8 197
  malloc 1 172
  malloc 26 67
  malloc 17 120
  malloc 27 206
  free 23
  free 17
  malloc 21 101
  malloc 7 21
  malloc 29 216
  free 7
  malloc 9 130
  malloc 5 89
  free 24
  free 11
  malloc 28 18
  malloc 20 119
  malloc 6 120
  malloc 19 59
  malloc 15 201
  free 26
  malloc 2 80
  free 21
  malloc 0 15
  free 27
  free 9
  malloc 12 174
  free 18
  free 0
  free 5
  malloc 14 31
  malloc 10 151
  malloc 13 65
  free 29
  free 15
  malloc 4 124
  free 2
  malloc 22 149
  free 1
  free 13
  free 14
  free 12
  malloc 3 243
  free 25
  malloc 16 179
  free 10
  free 20
  free 28
  free 22
  free 3
  free 4
  free 16
  free 8
  free 6
  free 19
  showheap
  """

  expected = """
  -- heap --
  0x00000000 0x00000000 XXXX
  """


class ReallocSame (HeapTest.Case):
  """
  Checks that reallocing with the same block size does nothing.
  """
  args = """
  rel 1
  alignbrk
  malloc 1 8
  malloc 2 24
  showheap
  realloc 1 8
  showheap
  checksentinel
  """

  expected = """
  -- heap --
  0x00000000 0x00000010 USED
  0x00000010 0x00000020 USED
  0x00000030 0x00000000 XXXX
  -- heap --
  0x00000000 0x00000010 USED
  0x00000010 0x00000020 USED
  0x00000030 0x00000000 XXXX
  """


class ReallocBasicallySame (HeapTest.Case):
  """
  Checks that reallocing with the same block size does nothing.
  """
  args = """
  rel 1
  alignbrk
  malloc 1 7
  malloc 2 24
  showheap
  realloc 1 8
  showheap
  checksentinel
  """

  expected = """
  -- heap --
  0x00000000 0x00000010 USED
  0x00000010 0x00000020 USED
  0x00000030 0x00000000 XXXX
  -- heap --
  0x00000000 0x00000010 USED
  0x00000010 0x00000020 USED
  0x00000030 0x00000000 XXXX
  """


class ReallocNoSplit (HeapTest.Case):
  """
  Reallocates a block only slightly smaller -- won't split.
  """
  args = """
  rel 1
  alignbrk
  malloc 1 0x80
  malloc 2 24
  showheap
  realloc 1 0x70
  showheap
  checksentinel
  """

  expected = """
  -- heap --
  0x00000000 0x00000088 USED
  0x00000088 0x00000020 USED
  0x000000a8 0x00000000 XXXX
  -- heap --
  0x00000000 0x00000088 USED
  0x00000088 0x00000020 USED
  0x000000a8 0x00000000 XXXX
  """


class ReallocSplit (HeapTest.Case):
  """
  Reallocates a block such that it splits.
  """
  args = """
  rel 1
  alignbrk
  malloc 1 0x80
  malloc 2 24
  showheap
  realloc 1 0x60
  showheap
  checksentinel
  """

  expected = """
  -- heap --
  0x00000000 0x00000088 USED
  0x00000088 0x00000020 USED
  0x000000a8 0x00000000 XXXX
  -- heap --
  0x00000000 0x00000068 USED
  0x00000068 0x00000020 FREE
  0x00000088 0x00000020 USED
  0x000000a8 0x00000000 XXXX
  """


class ReallocSplitMerge (HeapTest.Case):
  """
  When realloc()s cause a split, the leftover should be mergeable

  To test this, we allocate three blocks, call them A, B and C.
  We free B.
  We then realloc() A smaller so that it splits; the new leftover block is A2.
  At this point, we have four blocks: A, A2, B, and C.
  A2 and B are both free, so they should merge.
  """
  args = """
  rel 1
  alignbrk
  malloc 1 0x72
  malloc 2 24
  malloc 3 8
  free 2
  showheap
  realloc 1 0x8
  showheap
  """

  expected = """
  -- heap --
  0x00000000 0x00000080 USED
  0x00000080 0x00000020 FREE
  0x000000a0 0x00000010 USED
  0x000000b0 0x00000000 XXXX
  -- heap --
  0x00000000 0x00000010 USED
  0x00000010 0x00000090 FREE
  0x000000a0 0x00000010 USED
  0x000000b0 0x00000000 XXXX
  """


class ReallocGrow (HeapTest.Case):
  """
  A realloc() should be able to be larger than the original
  """
  args = """
  rel 1
  alignbrk
  malloc 1 8
  malloc 2 24
  showheap
  realloc 1 0x70
  showheap
  """

  expected = """
  -- heap --
  0x00000000 0x00000010 USED
  0x00000010 0x00000020 USED
  0x00000030 0x00000000 XXXX
  -- heap --
  0x00000000 0x00000010 FREE
  0x00000010 0x00000020 USED
  0x00000030 0x00000078 USED
  0x000000a8 0x00000000 XXXX
  """


class ReallocGrowMergeNoSplit (HeapTest.Case):
  """
  A realloc() should be able to grow into a following smallish free block
  """
  args = """
  rel 1
  alignbrk
  malloc 1 8
  malloc 2 0x16
  malloc 3 8
  showheap
  free 2
  realloc 1 0x10
  showheap
  """

  expected = """
  -- heap --
  0x00000000 0x00000010 USED
  0x00000010 0x00000020 USED
  0x00000030 0x00000010 USED
  0x00000040 0x00000000 XXXX
  -- heap --
  0x00000000 0x00000030 USED
  0x00000030 0x00000010 USED
  0x00000040 0x00000000 XXXX
  """


class ReallocGrowMergeSplit (HeapTest.Case):
  """
  A realloc() should be able to grow into and split a following free block
  """
  args = """
  rel 1
  alignbrk
  malloc 1 8
  malloc 2 0x32
  malloc 3 8
  showheap
  free 2
  realloc 1 0x10
  showheap
  """

  expected = """
  -- heap --
  0x00000000 0x00000010 USED
  0x00000010 0x00000040 USED
  0x00000050 0x00000010 USED
  0x00000060 0x00000000 XXXX
  -- heap --
  0x00000000 0x00000018 USED
  0x00000018 0x00000038 FREE
  0x00000050 0x00000010 USED
  0x00000060 0x00000000 XXXX
  """


class ReallocRelease (HeapTest.Case):
  """
  If you shrink the last block, it should release the leftover to the OS
  """
  score = 0.5 * _WEIGHT

  args = """
  rel 1
  alignbrk
  malloc 1 0x70
  showheap
  realloc 1 0x8
  showheap
  showbrk
  checksentinel
  """

  expected = """
  -- heap --
  0x00000000 0x00000078 USED
  0x00000078 0x00000000 XXXX
  -- heap --
  0x00000000 0x00000010 USED
  0x00000010 0x00000000 XXXX
  brk: 0x00000018
  """


class AllocReallocFreeAssortment (HeapTest.Case):
  """
  Just do a bunch of stuff

  It should end up freeing everthing, so you should end up with an empty heap
  """
  score = 0.5 * _WEIGHT

  args = """
  rel 1
  alignbrk
  malloc 8 167
  malloc 10 71
  malloc 9 12
  malloc 11 37
  malloc 14 73
  malloc 6 24
  malloc 5 8
  showheap
  realloc 11 60
  realloc 14 45
  showheap
  realloc 14 104
  showheap
  malloc 0 122
  malloc 4 121
  showheap
  free 8
  showheap
  realloc 14 104
  malloc 7 45
  realloc 10 242
  realloc 4 243
  malloc 2 210
  malloc 13 8
  malloc 3 20
  realloc 14 129
  realloc 13 170
  realloc 4 150
  realloc 13 123
  realloc 14 201
  realloc 4 55
  realloc 10 41
  free 7
  realloc 3 100
  realloc 10 216
  malloc 12 62
  realloc 11 143
  realloc 13 32
  realloc 10 39
  free 5
  realloc 12 137
  realloc 4 234
  realloc 4 64
  realloc 6 110
  free 12
  malloc 1 194
  free 14
  realloc 3 101
  realloc 6 212
  realloc 3 205
  free 2
  realloc 1 239
  realloc 11 109
  realloc 10 81
  realloc 11 222
  realloc 6 157
  realloc 9 127
  free 6
  free 0
  showheap
  realloc 11 12
  realloc 1 88
  free 4
  free 10
  free 1
  free 3
  free 11
  free 9
  free 13
  showheap
  """

  expected = """
  -- heap --
  0x00000000 0x000000b0 USED
  0x000000b0 0x00000050 USED
  0x00000100 0x00000018 USED
  0x00000118 0x00000030 USED
  0x00000148 0x00000058 USED
  0x000001a0 0x00000020 USED
  0x000001c0 0x00000010 USED
  0x000001d0 0x00000000 XXXX
  -- heap --
  0x00000000 0x000000b0 USED
  0x000000b0 0x00000050 USED
  0x00000100 0x00000018 USED
  0x00000118 0x00000030 FREE
  0x00000148 0x00000038 USED
  0x00000180 0x00000020 FREE
  0x000001a0 0x00000020 USED
  0x000001c0 0x00000010 USED
  0x000001d0 0x00000048 USED
  0x00000218 0x00000000 XXXX
  -- heap --
  0x00000000 0x000000b0 USED
  0x000000b0 0x00000050 USED
  0x00000100 0x00000018 USED
  0x00000118 0x00000088 FREE
  0x000001a0 0x00000020 USED
  0x000001c0 0x00000010 USED
  0x000001d0 0x00000048 USED
  0x00000218 0x00000070 USED
  0x00000288 0x00000000 XXXX
  -- heap --
  0x00000000 0x000000b0 USED
  0x000000b0 0x00000050 USED
  0x00000100 0x00000018 USED
  0x00000118 0x00000088 USED
  0x000001a0 0x00000020 USED
  0x000001c0 0x00000010 USED
  0x000001d0 0x00000048 USED
  0x00000218 0x00000070 USED
  0x00000288 0x00000088 USED
  0x00000310 0x00000000 XXXX
  -- heap --
  0x00000000 0x000000b0 FREE
  0x000000b0 0x00000050 USED
  0x00000100 0x00000018 USED
  0x00000118 0x00000088 USED
  0x000001a0 0x00000020 USED
  0x000001c0 0x00000010 USED
  0x000001d0 0x00000048 USED
  0x00000218 0x00000070 USED
  0x00000288 0x00000088 USED
  0x00000310 0x00000000 XXXX
  -- heap --
  0x00000000 0x00000060 USED
  0x00000060 0x000000a0 USED
  0x00000100 0x00000240 FREE
  0x00000340 0x00000110 USED
  0x00000450 0x000000e8 USED
  0x00000538 0x000000b8 FREE
  0x000005f0 0x00000028 USED
  0x00000618 0x00000048 USED
  0x00000660 0x000000d8 USED
  0x00000738 0x00000000 XXXX
  -- heap --
  0x00000000 0x00000000 XXXX
  """


"""
# Generates random events for testing

import random
def generate_events (num_blocks, sizes_f, num_reallocs_f):
  block_events = [] # "Stacks" of events
  stacks_choice = []

  for i in range(num_blocks):
    events = []
    block_events.append(events)
    events.append(f"malloc {i} {sizes_f(i,0)}")
    for j in range(num_reallocs_f(i)):
      events.append(f"realloc {i} {sizes_f(i,1+j)}")
    events.append(f"free {i}")
    stacks_choice.extend([i] * len(events))

  all_events = []
  random.shuffle(stacks_choice)
  for stack in stacks_choice:
    e = block_events[stack].pop(0)
    all_events.append(e)

  return all_events

def get_size (block, alloc_num):
  return random.randint(0, 256)

def get_num_reallocs (block):
  return 0
  r = random.randint(0, 8)
  if r > 5: r = 0
  return r

print("\n".join(generate_events(30, get_size, get_num_reallocs)))
import sys
sys.exit()
"""




if __name__ == "__main__":
  from test_common import main
  main()
