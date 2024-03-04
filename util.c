// Various utility functions
// Mostly this is stuff that serves similar purposes as printf() and assert()
// but without using heap memory.

#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include "util.h"

void printhex (uint32_t x, int chars)
{
  static char * cc = "0123456789abcdef";
  char out[8] = "00000000";
  char * o = out + 7;
  for (int i = 0; i < chars; ++i)
  {
    *o = cc[x & 0xf];
    x >>= 4;
    --o;
  }
  write(2, out + (8-chars), chars);
}

void printhex32 (uint32_t x)
{
  write(2, "0x", 2);
  printhex(x, 8);
}

void nl ()
{
  write(2, "\n", 1);
}

void sp ()
{
  write(2, " ", 1);
}

void print (const char * s)
{
  write(2, s, strlen(s));
}

void println (const char * s)
{
  print(s);
  nl();
}

void _x_assert (int c, Str s, Str f, Str l, Str d)
{
  if (!c)
  {
    print("** ASSERTION FAILED in ");
    print(s);
    print("() at ");
    print(f);
    print(":");
    print(l);
    if (d)
    {
      print(" : ");
      print(d);
    }
    nl();
    exit(1);
  }
}

uint32_t struint32 (char * str)
{
  if (0 == strcmp(str, "on")) return 1;
  if (0 == strcmp(str, "off")) return 0;
  if (0 == strcmp(str, "true")) return 1;
  if (0 == strcmp(str, "false")) return 0;
  return (uint32_t)(strtoll(str, NULL, 0) & 0xffFFffFF);
}
