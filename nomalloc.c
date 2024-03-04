/*
 * This is an unintelligent malloc() implementation which only works with
 * fixed size blocks.  It's really not good, but it's good enough to get
 * various parts of the C standard library (like printf()) to work, since
 * some of them need a working malloc().
 *
 */

#include <stdlib.h>
#include <string.h>
#include <stddef.h>
#include <stdint.h>

#include <unistd.h>

#include "util.h"

#ifndef BLOCK_SIZE
  #define BLOCK_SIZE 2048
#endif
#ifndef BLOCK_COUNT
  #define BLOCK_COUNT 64
#endif

static char mem[BLOCK_SIZE * BLOCK_COUNT];
static int used[BLOCK_COUNT];

#define DBG(x)

void * malloc (size_t sz)
{
  DBG(print("malloc sz:"); printhex32(sz); print(" "););
  ASSERT(sz < BLOCK_SIZE);
  for (int i = 0; i < BLOCK_COUNT; ++i)
  {
    if (used[i] == 0)
    {
      used[i] = 1;
      DBG(print("blk:");printhex32(i);print(" ptr:");printhex32((intptr_t)(mem + BLOCK_SIZE*i));nl(););
      return mem + BLOCK_SIZE * i;
    }
  }
  DBG(print("---");nl();)
  return NULL;
}

void free (void * ptr)
{
  DBG(print("free "); printhex32((intptr_t)ptr); nl(););
  if (!ptr) return;
  ptrdiff_t off = ((char *)ptr) - mem;
  ASSERT((off % BLOCK_SIZE) == 0); // Bad ptr
  off /= BLOCK_SIZE;
  ASSERT(off < BLOCK_COUNT); // Too large to be valid
  ASSERT(used[off]); // Not allocated
  used[off] = 0;
}

void * realloc (void * ptr, size_t sz)
{
  DBG(print("realloc "); printhex32((intptr_t)ptr); print(" "); printhex32(sz); nl(););
  // Special case -- if ptr is NULL, this is equivalent to malloc().
  if (ptr == NULL) return malloc(sz);

  // Special case -- if sz is 0, this is equivalent to free().
  if (sz == 0) { free(ptr); return NULL; }

  if (sz > BLOCK_SIZE) return NULL;

  return ptr;
}

// Once you implement malloc(), this should just work.
void * calloc (size_t nmemb, size_t size)
{
  // We actually are supposed to check for overflow, but don't.
  void * ptr = malloc(nmemb * size);
  if (!ptr) return NULL;
  memset(ptr, 0, size);
  return ptr;
}

// Once you implement realloc(), this should just work.
void * reallocarray (void * ptr, size_t nmemb, size_t size)
{
  // We actually are supposed to check for overflow, but don't.
  return realloc(ptr, nmemb * size);
}
