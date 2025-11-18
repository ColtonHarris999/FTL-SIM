cmake_minimum_required(VERSION 3.16)

project(ssd_simulator
    VERSION 1.0
    LANGUAGES CXX
)

# -------------------------------
# Global compiler settings
# -------------------------------
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# Enable warnings (optional)
if (MSVC)
    add_compile_options(/W4)
else()
    add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# -------------------------------
# Add yaml-cpp from submodule
# -------------------------------
add_subdirectory(external/yaml-cpp)

# -------------------------------
# Add your simulator source
# -------------------------------
add_subdirectory(src)
