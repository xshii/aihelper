# PURPOSE: Build and run dsp-connect tests WITHOUT libdwarf
# Usage: make        — build and run
#        make clean  — remove build artifacts

CC      = cc
CFLAGS  = -Wall -Wextra -std=c11 -g -O0
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

# Mock and test sources
SRC_MOCKS = \
	mocks/mock_transport.c \
	mocks/mock_arch.c

SRC_TESTS = \
	test_util.c \
	test_arch.c \
	test_transport_factory.c \
	test_resolve.c \
	test_format.c \
	test_errors.c \
	test_integration.c \
	test_main.c

ALL_SRC = $(SRC_UTIL) $(SRC_CORE) $(SRC_DWARF_TYPES) \
          $(SRC_RESOLVE) $(SRC_MEMORY) $(SRC_FORMAT) \
          $(SRC_TRANSPORT) $(SRC_MOCKS) $(SRC_TESTS)

TARGET = run_tests

.PHONY: all clean test

all: test

$(TARGET): $(ALL_SRC)
	$(CC) $(CFLAGS) -lm -o $@ $^

test: $(TARGET)
	./$(TARGET)

clean:
	rm -f $(TARGET)
