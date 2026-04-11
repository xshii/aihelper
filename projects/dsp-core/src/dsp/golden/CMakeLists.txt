cmake_minimum_required(VERSION 3.18)
project(_raw_bindings LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# golden_c 目录（硬件团队提供的 .h 和 .so，平铺结构）
set(GOLDEN_C_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../../../golden_c")

find_package(pybind11 REQUIRED)

pybind11_add_module(_raw_bindings
    bindings.cpp
    bind_convert.cpp
    bind_matrix.cpp
    bind_vector.cpp
)

# 绑定文件 include bind_helpers.h（在当前目录）
target_include_directories(_raw_bindings PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})

# 包含硬件头文件（.h 直接在 golden_c/ 下）
target_include_directories(_raw_bindings PRIVATE ${GOLDEN_C_DIR})

# 链接硬件 .so（.so 直接在 golden_c/ 下）
if(EXISTS "${GOLDEN_C_DIR}")
    target_link_directories(_raw_bindings PRIVATE ${GOLDEN_C_DIR})
    # target_link_libraries(_raw_bindings PRIVATE golden)  # 取消注释接真 .so
endif()

install(TARGETS _raw_bindings DESTINATION .)
