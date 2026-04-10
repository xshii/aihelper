# PURPOSE: Build and run dsp-connect tests WITHOUT libdwarf
# Usage: make        — build and run
#        make clean  — remove build artifacts

CC      = cc
CFLAGS  = -Wall -Wextra -std=c11 -g -O0 -I.
SRCDIR  = ../src

# Source files from the project (no dwarf_parser — needs libdwarf)
SRC_UTIL = \
	$(SRCDIR)/util/hashmap.c \
	$(SRCDIR)/util/strbuf.c \
	$(SRCDIR)/util/log.c

SRC_CORE = \
	$(SRCDIR)/core/dsc_errors.c

SRC_DWARF_TYPES = \
	$(SRCDIR)/dwarf/dwarf_types.c \
	$(SRCDIR)/dwarf/dwarf_symbols.c

SRC_RESOLVE = \
	$(SRCDIR)/resolve/resolve.c

SRC_MEMORY = \
	$(SRCDIR)/memory/memory.c

SRC_FORMAT = \
	$(SRCDIR)/format/format.c \
	$(SRCDIR)/format/format_primitive.c \
	$(SRCDIR)/format/format_enum.c \
	$(SRCDIR)/format/format_struct.c \
	$(SRCDIR)/format/format_array.c

SRC_TRANSPORT = \
	$(SRCDIR)/transport/transport_factory.c

# Mock sources
SRC_MOCKS = \
	mocks/mock_transport.c \
	mocks/mock_arch.c

# Test sources by level
SRC_UT = \
	ut/test_util.c \
	ut/test_arch.c \
	ut/test_transport_factory.c \
	ut/test_resolve.c \
	ut/test_format.c \
	ut/test_errors.c

SRC_IT = \
	it/test_integration.c

SRC_ST =

# Library sources (shared by all test levels)
SRC_LIB = $(SRC_UTIL) $(SRC_CORE) $(SRC_DWARF_TYPES) \
           $(SRC_RESOLVE) $(SRC_MEMORY) $(SRC_FORMAT) \
           $(SRC_TRANSPORT) $(SRC_MOCKS)

ALL_SRC = $(SRC_LIB) $(SRC_UT) $(SRC_IT) $(SRC_ST) test_main.c

TARGET = run_tests

.PHONY: all clean test ut it st

all: test

$(TARGET): $(ALL_SRC)
	$(CC) $(CFLAGS) -lm -o $@ $^

test: $(TARGET)
	./$(TARGET)

ut: $(SRC_LIB) $(SRC_UT) test_main.c
	$(CC) $(CFLAGS) -lm -DSKIP_IT -o run_ut $^
	./run_ut

it: $(SRC_LIB) $(SRC_IT) $(SRC_UT) test_main.c
	$(CC) $(CFLAGS) -lm -DSKIP_UT -o run_it $^
	./run_it

clean:
	rm -f $(TARGET) run_ut run_it run_st
