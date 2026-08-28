cmake_minimum_required(VERSION 3.10)
project(vision_cpp)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# OpenCV
find_package(OpenCV REQUIRED)

# pybind11 (선택적)
find_package(pybind11 QUIET)

# C++ 라이브러리 생성
add_library(vision_cpp SHARED
    src/fast_vision.cpp
)

target_include_directories(vision_cpp PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${OpenCV_INCLUDE_DIRS}
)

target_link_libraries(vision_cpp
    ${OpenCV_LIBS}
)

# pybind11 Python 모듈 (pybind11이 설치된 경우에만)
if(pybind11_FOUND)
    message(STATUS "pybind11 found - building Python bindings")

    pybind11_add_module(fast_vision
        bindings/py_fast_vision.cpp
        src/fast_vision.cpp
    )

    target_include_directories(fast_vision PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/include
        ${OpenCV_INCLUDE_DIRS}
    )

    target_link_libraries(fast_vision PRIVATE
        ${OpenCV_LIBS}
    )

    # Python 모듈 설치 경로
    # Vision/Python 폴더에 설치
    set(PYTHON_INSTALL_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../Python")

    install(TARGETS fast_vision
        LIBRARY DESTINATION ${PYTHON_INSTALL_DIR}
    )
else()
    message(WARNING "pybind11 not found - Python bindings will not be built")
    message(STATUS "Install pybind11: pip install pybind11 or apt install pybind11-dev")
endif()

# C++ 라이브러리 설치
install(TARGETS vision_cpp
    LIBRARY DESTINATION lib
)

install(DIRECTORY include/
    DESTINATION include
)
