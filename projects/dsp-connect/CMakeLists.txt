# PURPOSE: CMake 构建系统 — 静态库 + demo + 分级测试 (ut/it/st)
# PATTERN: 单根 CMakeLists，enable_testing + CTest 分级标签
# FOR: 弱 AI 参考如何用 CMake 组织 C 项目

cmake_minimum_required(VERSION 3.16)
project(dsp-connect C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
add_compile_options(-Wall -Wextra -Wpedantic)

# ------------------------------------------------------------------ #
# Option: link libdwarf for real DWARF parsing                       #
# ------------------------------------------------------------------ #
# Static library: libdsc                                             #
# ------------------------------------------------------------------ #
file(GLOB_RECURSE LIB_SRCS src/*/*.c)
list(FILTER LIB_SRCS EXCLUDE REGEX "demo_main\\.c$")

add_library(dsc STATIC ${LIB_SRCS})
target_include_directories(dsc PUBLIC src)

# Linux 需要显式链接 math 和 POSIX 库
include(CheckLibraryExists)
check_library_exists(m sin "" HAVE_LIBM)
if(HAVE_LIBM)
    target_link_libraries(dsc PUBLIC m)
endif()
find_package(Threads)
if(Threads_FOUND)
    target_link_libraries(dsc PUBLIC Threads::Threads)
endif()

# ------------------------------------------------------------------ #
# 交叉编译时只构建静态库，跳过 demo 和 tests                          #
# ------------------------------------------------------------------ #
if(DSC_CROSS_COMPILING)
    message(STATUS "Cross-compiling: skipping demo and tests")
    return()
endif()

# ------------------------------------------------------------------ #
# Demo executable                                                    #
# ------------------------------------------------------------------ #
add_executable(dsc_demo src/demo_main.c)
target_link_libraries(dsc_demo PRIVATE dsc)

# ------------------------------------------------------------------ #
# Tests — CTest with ut/it/st labels                                #
# ------------------------------------------------------------------ #
enable_testing()

# Common test sources: mocks + test runner
set(TEST_MOCKS
    tests/mocks/mock_transport.c
    tests/mocks/mock_arch.c
)

# Unit tests
set(TEST_UT
    tests/ut/test_errors.c
    tests/ut/test_util.c
    tests/ut/test_arch.c
    tests/ut/test_transport_factory.c
    tests/ut/test_resolve.c
    tests/ut/test_format.c
)

# Integration tests
set(TEST_IT
    tests/it/test_integration.c
)

# Unity test framework (ThrowTheSwitch)
set(UNITY_SRC tests/unity/unity.c)

# Full test runner (ut + it)
add_executable(test_runner
    tests/test_main.c
    ${UNITY_SRC}
    ${TEST_MOCKS}
    ${TEST_UT}
    ${TEST_IT}
)
target_include_directories(test_runner PRIVATE tests)
target_link_libraries(test_runner PRIVATE dsc)

# Register in CTest with labels for selective running
add_test(NAME all_tests COMMAND test_runner)
set_tests_properties(all_tests PROPERTIES LABELS "ut;it")

# ------------------------------------------------------------------ #
# Convenience targets (cmake --build . --target check)               #
# ------------------------------------------------------------------ #
add_custom_target(check
    COMMAND ${CMAKE_COMMAND} --build ${CMAKE_BINARY_DIR} --clean-first
    COMMAND ${CMAKE_CTEST_COMMAND} --output-on-failure
    COMMENT "Clean build + run all tests"
)
