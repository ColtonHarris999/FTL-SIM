# Gather all source files recursively
file(GLOB_RECURSE SIM_SRC
    "*.cpp"
    "*.hpp"
)

# Build simulator as an executable
add_executable(ssd_simulator ${SIM_SRC})

# Link yaml-cpp
target_link_libraries(ssd_simulator
    PRIVATE yaml-cpp
)

# Include directories (your own headers)
target_include_directories(ssd_simulator
    PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}
)
