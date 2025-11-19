# Gather ONLY your simulator source files
file(GLOB_RECURSE SIM_SRC CONFIGURE_DEPENDS
     "${CMAKE_CURRENT_SOURCE_DIR}/sim/**/*.cpp"
     "${CMAKE_CURRENT_SOURCE_DIR}/sim/**/*.hpp"
)

add_library(sim STATIC ${SIM_SRC})

# Make src/ the include root so <sim/...> works
target_include_directories(sim
    PUBLIC
        ${PROJECT_SOURCE_DIR}/src
)

# yaml-cpp must be PUBLIC so anything linking sim gets yaml-cpp
target_link_libraries(sim
    PUBLIC yaml-cpp
)

# Main executable
add_executable(ssd_simulator main.cpp)
target_link_libraries(ssd_simulator PRIVATE sim)
