// Various utility functions
// Mostly this is stuff that serves similar purposes as printf() and assert()
// but without using heap memory.

#include <stdint.h>

typedef const char * Str;

#define XSTR(x) #x
#define STR(x) XSTR(x)
#define ASSERT(x) _x_assert(x, __PRETTY_FUNCTION__, STR(__FILE__), STR(__LINE__), NULL)
#define ASSERT2(x,y) _x_assert(x, __PRETTY_FUNCTION__, STR(__FILE__), STR(__LINE__), y)


void printhex (uint32_t x, int chars); // print hex
void printhex32 (uint32_t x); // Print 0x1234beef
void nl (); // Print newline
void sp (); // Print space
void print (const char * s);
void println (const char * s);

uint32_t struint32 (char * str);

void _x_assert (int c, Str s, Str f, Str l, Str d); // Helper for ASSERT
