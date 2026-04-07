cmake_minimum_required(VERSION 3.18)
project(_raw_bindings LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# golden_c 目录（硬件团队提供的 .h 和 .so）
set(GOLDEN_C_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../../../golden_c")

find_package(pybind11 REQUIRED)

pybind11_add_module(_raw_bindings bindings.cpp)

# 包含硬件头文件
target_include_directories(_raw_bindings PRIVATE ${GOLDEN_C_DIR}/include)

# 链接硬件 .so（如果存在）
if(EXISTS "${GOLDEN_C_DIR}/lib")
    target_link_directories(_raw_bindings PRIVATE ${GOLDEN_C_DIR}/lib)
    # target_link_libraries(_raw_bindings PRIVATE golden)  # 取消注释接真 .so
endif()

install(TARGETS _raw_bindings DESTINATION .)
