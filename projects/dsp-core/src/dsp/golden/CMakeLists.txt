cmake_minimum_required(VERSION 3.18)
project(_raw_bindings LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(GOLDEN_C_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../../../golden_c")

find_package(pybind11 REQUIRED)

pybind11_add_module(_raw_bindings
    bindings.cpp
    bind_convert.cpp
    bind_matrix.cpp
    bind_vector.cpp
)

target_include_directories(_raw_bindings PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}    # bind_helpers.h
    ${GOLDEN_C_ROOT}               # dsp/ wrapper
    ${GOLDEN_C_ROOT}/current       # include/ 硬件头文件
)

# 链接硬件 .so（解压到 golden_c/current/ 下）
if(EXISTS "${GOLDEN_C_ROOT}/current")
    target_link_directories(_raw_bindings PRIVATE ${GOLDEN_C_ROOT}/current)
    # target_link_libraries(_raw_bindings PRIVATE golden)  # 取消注释接真 .so
endif()

install(TARGETS _raw_bindings DESTINATION .)
