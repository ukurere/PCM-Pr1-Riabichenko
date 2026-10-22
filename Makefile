# Збирання: mingw32-make (Windows, MinGW-w64) або make (Linux/WSL)

CXX      ?= g++
CXXFLAGS := -std=c++17 -O2 -Wall -Wextra -pthread -Isrc
LDFLAGS  := -pthread
LDLIBS   :=

COMMON_SRC   := $(wildcard src/common/*.cpp)
VERSIONS_SRC := $(wildcard src/versions/*.cpp)
INVIDX_SRC   := src/main.cpp $(COMMON_SRC) $(VERSIONS_SRC)
HEADERS      := $(wildcard src/common/*.h) $(wildcard src/versions/*.h)

ifeq ($(OS),Windows_NT)
  EXE := .exe
  RM_BUILD := if exist build rmdir /s /q build
  MK_BUILD := if not exist build mkdir build
else
  EXE :=
  RM_BUILD := rm -rf build
  MK_BUILD := mkdir -p build
endif

INVIDX := build/invidx$(EXE)
FS     := build/false_sharing$(EXE)

.PHONY: all clean

all: $(INVIDX) $(FS)

$(INVIDX): $(INVIDX_SRC) $(HEADERS) | build
	$(CXX) $(CXXFLAGS) $(LDFLAGS) -o $@ $(INVIDX_SRC) $(LDLIBS)

$(FS): src/false_sharing/fs.cpp | build
	$(CXX) $(CXXFLAGS) $(LDFLAGS) -o $@ $<

build:
	$(MK_BUILD)

clean:
	$(RM_BUILD)
