project(OMSimulatorGuiPy)

## Pure Python, no compile step -- imports the already-installed OMSimulator
## package at runtime. Mirrors OMSimulatorPython/CMakeLists.txt's pattern.

configure_file("${CMAKE_CURRENT_SOURCE_DIR}/__init__.py" "${CMAKE_CURRENT_BINARY_DIR}/__init__.py" @ONLY)
configure_file("${CMAKE_CURRENT_SOURCE_DIR}/OMSimulatorGui.in" "${CMAKE_CURRENT_BINARY_DIR}/OMSimulatorGui" @ONLY)

install(FILES "${CMAKE_CURRENT_BINARY_DIR}/__init__.py"
              "${CMAKE_CURRENT_SOURCE_DIR}/__main__.py"
              "${CMAKE_CURRENT_SOURCE_DIR}/app.py"
              "${CMAKE_CURRENT_SOURCE_DIR}/main_window.py"
        DESTINATION ${CMAKE_INSTALL_LIBDIR}/OMSimulatorGui)

install(FILES "${CMAKE_CURRENT_SOURCE_DIR}/models/__init__.py"
              "${CMAKE_CURRENT_SOURCE_DIR}/models/system_tree_model.py"
        DESTINATION ${CMAKE_INSTALL_LIBDIR}/OMSimulatorGui/models)

install(FILES "${CMAKE_CURRENT_SOURCE_DIR}/views/__init__.py"
              "${CMAKE_CURRENT_SOURCE_DIR}/views/system_tree_view.py"
              "${CMAKE_CURRENT_SOURCE_DIR}/views/diagram_canvas.py"
              "${CMAKE_CURRENT_SOURCE_DIR}/views/diagram_items.py"
        DESTINATION ${CMAKE_INSTALL_LIBDIR}/OMSimulatorGui/views)

install(FILES "${CMAKE_CURRENT_SOURCE_DIR}/dialogs/__init__.py"
              "${CMAKE_CURRENT_SOURCE_DIR}/dialogs/create_model_dialog.py"
              "${CMAKE_CURRENT_SOURCE_DIR}/dialogs/add_system_dialog.py"
              "${CMAKE_CURRENT_SOURCE_DIR}/dialogs/add_submodel_dialog.py"
              "${CMAKE_CURRENT_SOURCE_DIR}/dialogs/add_connector_dialog.py"
        DESTINATION ${CMAKE_INSTALL_LIBDIR}/OMSimulatorGui/dialogs)

if(MSVC)
  install(FILES OMSimulatorGui.bat TYPE BIN
          PERMISSIONS OWNER_EXECUTE OWNER_WRITE OWNER_READ
                      GROUP_EXECUTE GROUP_READ
                      WORLD_EXECUTE WORLD_READ)
elseif(MINGW)
  install(FILES "${CMAKE_CURRENT_BINARY_DIR}/OMSimulatorGui" OMSimulatorGui.bat
          TYPE BIN
          PERMISSIONS OWNER_EXECUTE OWNER_WRITE OWNER_READ
                      GROUP_EXECUTE GROUP_READ
                      WORLD_EXECUTE WORLD_READ)
else()
  install(FILES "${CMAKE_CURRENT_BINARY_DIR}/OMSimulatorGui"
          TYPE BIN
          PERMISSIONS OWNER_EXECUTE OWNER_WRITE OWNER_READ
                      GROUP_EXECUTE GROUP_READ
                      WORLD_EXECUTE WORLD_READ)
endif()
