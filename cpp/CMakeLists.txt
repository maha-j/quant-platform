# libquant — indicateurs critiques C++20.
# Cibles :
#   - quant           : bibliothèque statique cœur.
#   - quant_shared    : DLL/so exportable (interop MQL5).
#   - quant_native    : module Python (pybind11).
#   - quant_tests     : tests GoogleTest (sources dans ../tests/unit).
cmake_minimum_required(VERSION 3.20)
project(quant LANGUAGES CXX VERSION 0.1.0)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()
set(CMAKE_CXX_FLAGS_RELEASE "-O3 -DNDEBUG")

include(FetchContent)
find_package(fmt QUIET)
find_package(spdlog QUIET)
find_package(Eigen3 QUIET)

# --- Bibliothèque cœur --------------------------------------------------------
add_library(quant STATIC src/indicators.cpp)
target_include_directories(quant PUBLIC include)
target_compile_features(quant PUBLIC cxx_std_20)
if(fmt_FOUND)
  target_link_libraries(quant PUBLIC fmt::fmt)
endif()
if(spdlog_FOUND)
  target_link_libraries(quant PUBLIC spdlog::spdlog)
endif()
if(Eigen3_FOUND)
  target_link_libraries(quant PUBLIC Eigen3::Eigen)
endif()

# --- DLL/so exportable (interop MQL5) ----------------------------------------
add_library(quant_shared SHARED src/indicators.cpp)
target_include_directories(quant_shared PUBLIC include)
set_target_properties(quant_shared PROPERTIES OUTPUT_NAME quant)

# --- Module Python (pybind11) ------------------------------------------------
find_package(pybind11 QUIET)
if(pybind11_FOUND)
  pybind11_add_module(quant_native bindings/pybind_module.cpp src/indicators.cpp)
  target_include_directories(quant_native PRIVATE include)
endif()

# --- Tests (GoogleTest) — sources isolées dans tests/ ------------------------
option(QUANT_BUILD_TESTS "Compiler les tests" ON)
if(QUANT_BUILD_TESTS)
  find_package(GTest QUIET)
  if(NOT GTest_FOUND)
    FetchContent_Declare(googletest
      URL https://github.com/google/googletest/archive/refs/tags/v1.14.0.zip)
    FetchContent_MakeAvailable(googletest)
  endif()
  enable_testing()
  add_executable(quant_tests ../tests/unit/test_indicators_cpp.cpp)
  target_link_libraries(quant_tests PRIVATE quant GTest::gtest_main)
  include(GoogleTest)
  gtest_discover_tests(quant_tests)
endif()
