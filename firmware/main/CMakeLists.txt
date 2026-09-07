cmake_minimum_required(VERSION 3.16)

project(fractal_pulse)

# Main component
idf_component_register(
    SRCS 
        "app_main.c"
    INCLUDE_DIRS 
        "."
    REQUIRES 
        esp_system
        esp_event
        nvs_flash
        freertos
        driver
)

# TFLite Micro component (would need to be added to esp-idf components)
# For prototype: using ESP-NN or pre-built TFLite library

target_link_libraries(${COMPONENT_LIB} PUBLIC m)  # Link math library
