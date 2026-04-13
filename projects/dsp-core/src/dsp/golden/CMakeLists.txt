cmake_minimum_required(VERSION 3.16)
project(_raw_bindings LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(GOLDEN_C_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../../../golden_c")
set(OPS_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../ops")

# pybind11: 优先用 -Dpybind11_DIR 传入的路径，否则从 Python 包查
if(NOT pybind11_DIR)
    execute_process(
        COMMAND ${PYTHON_EXECUTABLE} -c "import pybind11; print(pybind11.get_cmake_dir())"
        OUTPUT_VARIABLE _pybind11_cmake_dir
        OUTPUT_STRIP_TRAILING_WHITESPACE
        RESULT_VARIABLE _pybind11_result
    )
    if(_pybind11_result EQUAL 0)
        set(pybind11_DIR "${_pybind11_cmake_dir}")
    endif()
endif()

find_package(pybind11 REQUIRED)

# 自动收集所有 op 目录下的 bind.cpp
file(GLOB_RECURSE OP_BIND_SOURCES "${OPS_ROOT}/*/bind.cpp")

# 自动收集所有包含 .h 文件的 op 子目录作为 include path
file(GLOB_RECURSE _OP_HEADERS "${OPS_ROOT}/*/*.h")
set(_OP_INCLUDE_DIRS "")
foreach(_header ${_OP_HEADERS})
    get_filename_component(_dir ${_header} DIRECTORY)
    list(APPEND _OP_INCLUDE_DIRS ${_dir})
endforeach()
list(REMOVE_DUPLICATES _OP_INCLUDE_DIRS)

pybind11_add_module(_raw_bindings
    bindings.cpp
    ${OP_BIND_SOURCES}
)

target_include_directories(_raw_bindings PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}        # bind_helpers.h
    ${GOLDEN_C_ROOT}/current/include   # golden_convert.h 等硬件头文件
    ${_OP_INCLUDE_DIRS}                # ops/*/dsp_*.h（自动收集）
)

# 链接硬件 .so（解压到 golden_c/current/ 下）
if(EXISTS "${GOLDEN_C_ROOT}/current")
    target_link_directories(_raw_bindings PRIVATE ${GOLDEN_C_ROOT}/current)
endif()

install(TARGETS _raw_bindings DESTINATION .)
