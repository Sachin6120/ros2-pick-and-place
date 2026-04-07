cmake_minimum_required(VERSION 3.8)
project(pick_and_place)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)

# ---------------------------------------------------------------------------
# Install directories
# ---------------------------------------------------------------------------
install(DIRECTORY
  urdf
  config
  launch
  worlds
  rviz
  DESTINATION share/${PROJECT_NAME}
)

install(PROGRAMS
  scripts/pick_and_place_node.py
  scripts/metrics_logger.py
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()
