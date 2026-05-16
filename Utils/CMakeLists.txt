cmake_minimum_required(VERSION 3.13)
cmake_policy(VERSION 3.13)

project(Ortho4XP VERSION 1.4 LANGUAGES C)

set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(CMAKE_VERBOSE_MAKEFILE OFF)
set(CMAKE_INTERPROCEDURAL_OPTIMIZATION OFF)
set(CMAKE_POSITION_INDEPENDENT_CODE OFF)

add_executable(Triangle4XP src/Triangle4XP.c)
if(NOT WIN32)
  target_link_libraries(Triangle4XP m)
endif()


