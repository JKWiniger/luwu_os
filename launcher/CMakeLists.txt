cmake_minimum_required(VERSION 3.16)
project(luwu_launcher LANGUAGES CXX)

find_package(Qt6 REQUIRED COMPONENTS Widgets)

qt_add_executable(luwu_launcher main.cpp)
target_link_libraries(luwu_launcher PRIVATE Qt6::Widgets)
