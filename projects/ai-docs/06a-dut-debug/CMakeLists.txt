cmake_minimum_required(VERSION 3.16)
project(sut C)

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

add_compile_options(-Wall -Wextra -O2 -g)
add_compile_definitions(SUT_RECORD=1)

# 目录角色：
#   common/   工程公共头（bug_check / 类型 typedef）
#   dut/      DUT 嵌入物（被测固件侧）
#   stub_cpu/ 桩 CPU 侧（host 跑）
#   smoke/    集成测试入口
#
# 3.16 起 CONFIGURE_DEPENDS 让 GLOB 在文件增删时自动重新配置
file(GLOB SUT_CORE_SRCS CONFIGURE_DEPENDS
    "${CMAKE_CURRENT_SOURCE_DIR}/dut/*.c"
    "${CMAKE_CURRENT_SOURCE_DIR}/stub_cpu/*.c"
)

add_library(sut STATIC ${SUT_CORE_SRCS})
target_include_directories(sut PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/common
    ${CMAKE_CURRENT_SOURCE_DIR}/dut
    ${CMAKE_CURRENT_SOURCE_DIR}/stub_cpu
)

file(GLOB SMOKE_SRCS CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/smoke/*.c")

add_executable(smoke ${SMOKE_SRCS})
target_include_directories(smoke PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/smoke
)

find_package(Threads REQUIRED)
target_link_libraries(smoke PRIVATE sut Threads::Threads)

enable_testing()
add_test(NAME smoke COMMAND smoke)
