# First target is the default if you just say "make"
all: tester

# Note that this compiles for 32 bit mode specifically.  64 bit addresses are
# kind of long to look at and aren't what we see in the MIPS stuff we do.
tester: tester.c util.c heap.c util.h nomalloc.c
	gcc -m32 -static -g -Wall -Werror=vla -Werror \
          -Wno-unused-function -Wno-unused-variable \
          -Wno-error=unused-function -Wno-error=unused-variable \
          -o tester \
          -DMALLOC=xmalloc -DFREE=xfree -DREALLOC=xrealloc -DCALLOC=xcalloc \
          -DREALLOCARRAY=xreallocarray \
          tester.c util.c heap.c nomalloc.c

# Only runs up until the first test that fails
tests: all
	python3 -m unittest --verbose --failfast test_heap.py

# Always tries to run all tests
all-tests: all
	python3 -m unittest --verbose test_heap.py

grade: all
	python3 test_heap.py --gradescope --skip-after-fail

submission: all
	@echo -n "# " > diffs.diff
	@echo -n $(shell whoami) >> diffs.diff
	@echo -n " (" >> diffs.diff
	@echo -n "$(shell getent passwd ${USER} | cut -d: -f 5 | cut -d, -f 1)" >> diffs.diff
	@echo ")" >> diffs.diff
	@echo "-----------------------------------" >> diffs.diff
	@git diff heap.c >> diffs.diff
	@echo "-----------------------------------" >> diffs.diff
	@git diff journal.md >> diffs.diff
	@zip submission.zip diffs.diff journal.md heap.c
	@rm diffs.diff

clean:
	@rm -f tester diffs.diff submission.zip
	@rm -rf __pycache__
