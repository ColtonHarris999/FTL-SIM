#include <sim/ftl/ftl-config.hpp>
#include <stdexcept>
#include <sys/mman.h>
#include <unistd.h>

namespace sim::ftl {

void* mmap_large(std::size_t bytes) {
#ifdef _WIN32
    void* ptr = VirtualAlloc(
        nullptr,
        bytes,
        MEM_RESERVE | MEM_COMMIT,
        PAGE_READWRITE
    );
    if (!ptr) {
        throw std::runtime_error("VirtualAlloc failed");
    }
    return ptr;
#else
    void* ptr = mmap(nullptr, bytes,
                     PROT_READ | PROT_WRITE,
                     MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE,
                     -1, 0);
    if (ptr == MAP_FAILED) {
        throw std::runtime_error("mmap failed");
    }
    return ptr;
#endif
}

void mmap_free(void* ptr, std::size_t bytes) {
#ifdef _WIN32
    if (ptr) {
        VirtualFree(ptr, 0, MEM_RELEASE);
    }
#else
    if (ptr) {
        munmap(ptr, bytes);
    }
#endif
}

} // namespace sim::ftl
