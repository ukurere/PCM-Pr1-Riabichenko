cmake_minimum_required(VERSION 3.13)
project(PCM_Pr1_Riabichenko LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()
# Release у CMake дає -O3; методика вимагає -O2 або -O3
set(CMAKE_CXX_FLAGS_RELEASE "-O2")

find_package(Threads REQUIRED)

file(GLOB COMMON_SRC   src/common/*.cpp)
file(GLOB VERSIONS_SRC src/versions/*.cpp)

add_executable(invidx src/main.cpp ${COMMON_SRC} ${VERSIONS_SRC})
target_include_directories(invidx PRIVATE src)
target_compile_options(invidx PRIVATE -Wall -Wextra)
target_link_libraries(invidx PRIVATE Threads::Threads)

add_executable(false_sharing src/false_sharing/fs.cpp)
target_compile_options(false_sharing PRIVATE -Wall -Wextra)
target_link_libraries(false_sharing PRIVATE Threads::Threads)
