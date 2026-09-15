cmake_minimum_required(VERSION 3.16)

# Main component
idf_component_register(
    SRCS
        "app_main.cc"
    INCLUDE_DIRS
        "."
    REQUIRES
        esp_system
        esp_event
        nvs_flash
        freertos
        driver
        esp-tflite-micro
)

target_link_libraries(${COMPONENT_LIB} PUBLIC m)  # Link math library
