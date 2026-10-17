# Nix supplies a verified, unpacked Release asset. Other builds fetch the
# same pinned archive during configuration, outside the source tree.
if(NOT WETYPE_RUNTIME_SOURCE_DIR)
  find_package(Python3 3.8 REQUIRED COMPONENTS Interpreter)
  execute_process(
    COMMAND "${Python3_EXECUTABLE}" -c
      "import json,sys; a=json.load(open(sys.argv[1])); print(a['url']); print(a['sha256'])"
      "${CMAKE_CURRENT_SOURCE_DIR}/runtime/asset.json"
    RESULT_VARIABLE runtime_metadata_status
    OUTPUT_VARIABLE runtime_metadata
    OUTPUT_STRIP_TRAILING_WHITESPACE)
  if(NOT runtime_metadata_status EQUAL 0)
    message(FATAL_ERROR "Unable to read runtime/asset.json")
  endif()
  string(REPLACE "\n" ";" runtime_metadata "${runtime_metadata}")
  list(GET runtime_metadata 0 runtime_url)
  list(GET runtime_metadata 1 runtime_sha256)
  FetchContent_Declare(wetypex_runtime
    URL "${runtime_url}"
    URL_HASH "SHA256=${runtime_sha256}")
  FetchContent_GetProperties(wetypex_runtime)
  if(NOT wetypex_runtime_POPULATED)
    FetchContent_Populate(wetypex_runtime)
  endif()
  set(WETYPE_RUNTIME_SOURCE_DIR "${wetypex_runtime_SOURCE_DIR}")
endif()

foreach(required IN ITEMS
    share/fcitx5-wetypex/runtime/manifest.txt
    share/fcitx5-wetypex/runtime/flurry/manifest.txt
    share/fcitx5-wetypex/runtime/wxp2p/manifest.txt
    share/fcitx5-wetypex/ui/icons/input.svg
    NOTICE SHA256SUMS)
  if(NOT EXISTS "${WETYPE_RUNTIME_SOURCE_DIR}/${required}")
    message(FATAL_ERROR "Incomplete runtime asset: ${required}")
  endif()
endforeach()
