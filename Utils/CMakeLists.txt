cmake_minimum_required(VERSION 3.25)
cmake_policy(VERSION 3.25)

project(Ortho4XP VERSION 1.4 LANGUAGES C)

set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(CMAKE_VERBOSE_MAKEFILE OFF)
set(CMAKE_INTERPROCEDURAL_OPTIMIZATION OFF)
set(CMAKE_POSITION_INDEPENDENT_CODE OFF)

if(NOT CMAKE_C_COMPILER_ID MATCHES "Clang")
  message(FATAL_ERROR "Triangle4XP must be built with LLVM/Clang. Use `cmake --preset llvm-release`.")
endif()

add_executable(Triangle4XP src/Triangle4XP.c)
target_compile_features(Triangle4XP PRIVATE c_std_17)
if(WIN32)
  target_compile_definitions(Triangle4XP PRIVATE _CRT_SECURE_NO_WARNINGS)
endif()
if(NOT WIN32)
  target_link_libraries(Triangle4XP m)
endif()
