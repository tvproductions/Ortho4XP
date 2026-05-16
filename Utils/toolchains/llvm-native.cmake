set(_ORTHO4XP_LLVM_HINTS)

if(CMAKE_HOST_WIN32)
  list(APPEND _ORTHO4XP_LLVM_HINTS
    "$ENV{ProgramFiles}/LLVM/bin"
    "$ENV{ProgramW6432}/LLVM/bin"
    "$ENV{LOCALAPPDATA}/Programs/LLVM/bin"
  )
endif()

find_program(ORTHO4XP_CLANG
  NAMES clang
  HINTS ${_ORTHO4XP_LLVM_HINTS}
  REQUIRED
)

set(CMAKE_C_COMPILER "${ORTHO4XP_CLANG}" CACHE FILEPATH "LLVM Clang C compiler")

find_program(ORTHO4XP_LLVM_RC
  NAMES llvm-rc
  HINTS ${_ORTHO4XP_LLVM_HINTS}
)

if(ORTHO4XP_LLVM_RC)
  set(CMAKE_RC_COMPILER "${ORTHO4XP_LLVM_RC}" CACHE FILEPATH "LLVM resource compiler")
endif()

find_program(ORTHO4XP_LLD
  NAMES lld lld-link
  HINTS ${_ORTHO4XP_LLVM_HINTS}
)

if(ORTHO4XP_LLD)
  set(CMAKE_EXE_LINKER_FLAGS_INIT "-fuse-ld=lld")
endif()
