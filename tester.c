#include <malloc.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <stdbool.h>
#include "util.h"

void * MALLOC (size_t sz);
void FREE (void * ptr);
void * REALLOC (void * ptr, size_t sz);
void * CALLOC (size_t nmemb, size_t size);
void * REALLOCARRAY (void * ptr, size_t nmemb, size_t size);

typedef struct
{
  size_t size;
  int is_used;
} Block;

extern Block * first_block;

typedef struct
{
  void * ptr;
  size_t sz;
} AllocInfo;

static AllocInfo slots[256];

static int relative_addrs = 0;
static int verbose = 1;

static void dumpaddr (void * a)
{
  intptr_t aa = (intptr_t)a;
  if (relative_addrs) aa -= (intptr_t)first_block;
  printhex32(aa);
}

static uint8_t hash (void * ptr, size_t sz, int offset)
{
  intptr_t data = (intptr_t)(ptr+offset);
  data += sz;
  uint8_t * p = (void*)&data;
  uint32_t h = 0;
  h =          (*p++);
  h = h *  7 ^ (*p++);
  h = h * 13 ^ (*p++);
  h = h * 41 ^ (*p++);
  return h & 0xff;
}

static void do_sbrk (char ** args)
{
  sbrk(struint32(args[0]));
}

static void do_showbrk (char ** args)
{
  print("brk: ");
  dumpaddr(sbrk(0));
  nl();
}

static void do_alignbrk (char ** args)
{
  intptr_t b = (intptr_t)sbrk(0);
  if (b % 8)
  {
    int rest = 8 - (b % 8);
    sbrk(rest);
  }
}

static void do_checksentinel (char ** args)
{
  // Checks that there seems to be a sentinel right beofre program break
  // checksentinel
  Block * b = sbrk(0);
  b -= 1;
  ASSERT2(b->size == 0, "Bad sentinel");
  ASSERT2(b->is_used == 1, "Bad sentinel");
}

static void do_mark (char ** args)
{
  print("----\n");
}

static void do_showheap (char ** args)
{
  Block * b = (Block *)first_block;
  if (verbose) print("-- heap --\n");
  while (true)
  {
    dumpaddr(b);sp();printhex32(b->size);sp();
    if (b->is_used && !b->size) print("XXXX");
    else if (b->is_used && b->size) print("USED");
    else if (!b->is_used && b->size) print("FREE");
    else print("????");
    nl();
    if (b->size == 0) break;
    b = (Block *)(((char *)b)+b->size);
  }
}

static void showslot (int i)
{
  print("slot num:");
  printhex32(i);
  print(" ptr:");
  dumpaddr(slots[i].ptr);
  print(" sz:");
  printhex32(slots[i].sz);
}

static void do_showslot (char ** args)
{
  uint32_t slot = struint32(args[0]);
  showslot((int)slot);
  nl();
}

static void do_showslots (char ** args)
{
  if (verbose) print("-- slots --\n");
  for (int i = 0; i < sizeof(slots)/sizeof(slots[0]); ++i)
  {
    if (!slots[i].ptr && !slots[i].sz) continue;
    showslot(i);
    nl();
  }
}

static int enable_check = 1;

static void do_checks (char ** args)
{
  // Turn checks on or off
  // checks <0 or 1>
  enable_check = atoi(args[0]) != 0;
}

static void do_rel (char ** args)
{
  // Turns printing of relative addresses on
  // rel <0 for absolute addresses, 1 for relative addresses>
  relative_addrs = atoi(args[0]) != 0;
}

static void do_v (char ** args)
{
  // Turns on and off verbose mode
  verbose = atoi(args[0]) != 0;
}

static void check2 (void * data, size_t sz, uint8_t chk, int force, const char * prefix)
{
  if (!enable_check && !force) return;
  //dumpaddr(data);sp();printhex32(sz);sp();printhex32(chk);nl();
  uint8_t * d = data;
  for (int i = 0; i < sz; ++i)
  {
    if (d[i] != chk)
    {
      if (prefix) print(prefix); else print("** ");
      print("Bad check value at ");
      dumpaddr((d+i));
      print(" (real 0x");
      printhex(d[i], 2);
      print(" != expected 0x");
      printhex(chk, 2);
      print(")");
      nl();
      exit(1);
    }
  }
}

static void check (void * data, size_t sz)
{
  uint8_t chk = hash(data, sz, 0);
  check2(data, sz, chk, 0, 0);
}

static void fillcheck (void * data, size_t sz, int offset)
{
  if (!enable_check) return;
  uint8_t chk = hash(data, sz, offset);
  uint8_t * d = data;
  for (int i = 0; i < sz; ++i)
  {
    d[i] = chk;
  }
}

static void do_malloc (char ** args)
{
  uint32_t slot = struint32(args[0]);
  uint32_t size = struint32(args[1]);
  slots[slot].ptr = MALLOC(size);
  slots[slot].sz = size;
  fillcheck(slots[slot].ptr, size, 0);
}

static void freeslot (uint32_t slot)
{
  void * mem = slots[slot].ptr;
  size_t sz = slots[slot].sz;
  if (mem) check(mem, sz);
  FREE(mem);
  slots[slot].ptr = NULL;
  slots[slot].sz = 0;
}

static void do_free (char ** args)
{
  uint32_t slot = struint32(args[0]);
  freeslot(slot);
}

static void do_doublefree (char ** args)
{
  uint32_t slot = struint32(args[0]);
  AllocInfo ai = slots[slot];
  do_free(args);
  slots[slot] = ai;
  do_free(args);
}

static void do_freeall (char ** args)
{
  for (uint32_t i = 0; i < sizeof(slots)/sizeof(slots[0]); ++i)
  {
    if (!slots[i].ptr && !slots[i].sz) continue;
    freeslot(i);
  }
}

static void do_realloc (char ** args)
{
  uint32_t slot = struint32(args[0]);
  uint32_t size = struint32(args[1]);
  uint8_t chk = hash(slots[slot].ptr, slots[slot].sz, 0);
  slots[slot].ptr = REALLOC(slots[slot].ptr, size);
  if (slots[slot].ptr)
  {
    // Check that old data was copied
    size_t sz = slots[slot].sz;
    if (sz > size) sz = size;
    check2(slots[slot].ptr, sz, chk, 0, "** realloc step 1: ");

    slots[slot].sz = size;
    fillcheck(slots[slot].ptr, size, 0);
  }
  else
  {
    print("** realloc() failed.\n");
    exit(3);
  }
}

static void do_killslot (char ** args)
{
  uint32_t slot = struint32(args[0]);
  slots[slot].ptr = NULL;
  slots[slot].sz = 0;
}

static void do_poke (char ** args)
{
  uint32_t slot = struint32(args[0]);
  uint32_t offset = struint32(args[1]);
  uint8_t value = (uint8_t)struint32(args[2]);

  uint8_t * m = slots[slot].ptr;
  m += offset;
  *m = value;
}

static void do_pokes (char ** args)
{
  uint32_t slot = struint32(args[0]);
  uint32_t offset = struint32(args[1]);
  char * m = slots[slot].ptr;
  m += offset;
  strcpy(m, args[2]);
}

static void do_fillslot (char ** args)
{
  // fillslot <slot> <offset> <byte value to fill with or -1 for automatic>
  uint32_t slot = struint32(args[0]);
  uint32_t offset = struint32(args[1]);
  int byte = (int)struint32(args[2]);
  if (byte == -1) byte = hash(slots[slot].ptr, slots[slot].sz, 0);

  char * m = slots[slot].ptr;
  m += offset;
  memset(m, byte & 0xff, slots[slot].sz - offset);
}

static void do_checkslot (char ** args)
{
  // checkslot <slot> <byte value to check or -1 for automatic>
  uint32_t slot = struint32(args[0]);
  int byte = (int)struint32(args[1]);
  if (byte == -1) byte = hash(slots[slot].ptr, slots[slot].sz, 0);
  check2(slots[slot].ptr, slots[slot].sz, byte & 0xff, 1, NULL);
}

static void do_peeks (char ** args)
{
  uint32_t slot = struint32(args[0]);
  uint32_t offset = struint32(args[1]);
  char * m = slots[slot].ptr;
  m += offset;
  print("peeks slot+off:");
  printhex32(slot);
  print("+");
  printhex32(offset);
  print(" ptr:");
  dumpaddr(m);
  print(" str:");
  print(m);
  nl();
}

static void do_peek (char ** args)
{
  // Peek one byte
  uint32_t slot = struint32(args[0]);
  uint32_t offset = struint32(args[1]);
  uint8_t * m = slots[slot].ptr;
  m += offset;
  print("peek ");
  dumpaddr(m);
  print(" 0x");
  printhex(*m, 2);
  nl();
}

static void hexdump (void * ptr, size_t sz, char * prefix)
{
  char * p = ptr;
  size_t xsz = (sz+15) / 16 * 16;
  if (xsz < 16) xsz = 16;

  for (size_t i = 0; i < xsz; ++i)
  {
    if ((i % 16) == 0)
    {
      if (i != 0) nl();
      if (prefix) print(prefix);
      dumpaddr(p+i);
      print(":");
    }
    if (i >= sz) print(" ..");
    else { sp(); printhex(p[i], 2); }
  }
  nl();
}

static void do_dumpslot (char ** args)
{
  // Do a hexdump of a slot
  // dumpslot <slot>
  uint32_t slot = struint32(args[0]);
  if (verbose)
  {
    print("-- ");
    showslot(slot);
    print(" --\n");
  }
  char * m = slots[slot].ptr;
  m -= sizeof(Block);
  Block * b = (Block *)m;
  hexdump(b, sizeof(Block), "H ");
  hexdump(m+sizeof(Block), slots[slot].sz, "  ");
  size_t sz = b->size;
  sz -= slots[slot].sz;
  ASSERT(sz >= sizeof(Block));
  sz -= sizeof(Block);
  if (sz) hexdump(m + sizeof(Block) + slots[slot].sz, sz, "X ");
}

static void do_blocktoslot (char ** args)
{
  // Makes a slot that corresponds to a block
  // blocktoslot <block number> <slot>
  uint32_t block = struint32(args[0]);
  uint32_t slot = struint32(args[1]);

  Block * b = (Block *)first_block;
  for (uint32_t i = 0; i < block; ++i)
  {
    ASSERT2(b->size, "Hit sentinel before finding block");
    b = (Block *)(((char *)b)+b->size);
  }
  slots[slot].ptr = (b + 1);
  slots[slot].sz = b->size - sizeof(Block);
}

static void do_peek32 (char ** args)
{
  uint32_t slot = struint32(args[0]);
  int32_t offset = (int32_t)struint32(args[1]);
  char * m = slots[slot].ptr;
  m += offset;
  print("peek32 slot+off:");
  printhex32(slot);
  print("+");
  printhex32(offset);
  print(" ptr:");
  dumpaddr(m);
  print(" val:");
  printhex32( *(uint32_t*)m );
  nl();
}



#define CMD(name, count)                                                   \
  if (0 == strcmp(#name, argv[i])) {                                       \
    if (remaining < count) {                                               \
      print("Bad number of arguments for '"); print(#name); print("'.\n"); \
      return 1;                                                            \
    }                                                                      \
    do_ ## name(argv + i + 1);                                             \
    i += count;                                                            \
    continue;                                                              \
  }


int main (int argc, char * argv[])
{
  int remaining = argc - 1;
  for (int i = 1; i < argc; ++i, --remaining)
  {
    if (0 == strcmp(argv[i], "--")) continue;
    CMD(sbrk, 1);
    CMD(showbrk, 0);
    CMD(alignbrk, 0);
    CMD(showslot, 1);
    CMD(showslots, 0);
    CMD(malloc, 2);
    CMD(realloc, 2);
    CMD(free, 1);
    CMD(doublefree, 1);
    CMD(freeall, 0);
    CMD(killslot, 1);
    CMD(poke, 3);
    CMD(pokes, 3);
    CMD(peeks, 2);
    CMD(peek, 2);
    CMD(peek32, 2);
    CMD(fillslot, 3);
    CMD(checkslot, 2);
    CMD(checksentinel, 0);
    CMD(dumpslot, 1);
    CMD(blocktoslot, 2);
    CMD(mark, 0);
    CMD(showheap, 0);
    CMD(checks, 1);
    CMD(rel, 1);
    CMD(v, 1);
    print("Command not found: ");print(argv[i]);nl();
    exit(1);
  }

  return 0;
}
